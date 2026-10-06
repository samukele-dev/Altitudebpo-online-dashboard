import pandas as pd
import os
import time
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit, join_room
from flask_cors import CORS

import suite_client

# --- Configuration & Setup ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_super_secret_key')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# SocketIO configuration
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading'
)

# Simple User/Group Management
USERS = {
    'admin': {'password': 'admin', 'group': 'Global'},
    'floor1_manager': {'password': 'f1pass1', 'group': 'Floor 1'},
    'floor2_manager': {'password': 'f2pass2', 'group': 'Floor 2'}
}
DASHBOARD_GROUPS = ['Global', 'Floor 1', 'Floor 2']
FLOORS = ['Floor 1', 'Floor 2']

# --- Data stores ---
# Team stats are no longer uploaded: they are pulled live (today's sales, average
# talk time) from the Call Centre Reporting Suite backend — see suite_client.py.
# Nothing is saved here (targets live in the Suite). LAST_GOOD only remembers the
# most recent successful pull per group so a brief backend outage shows the
# last numbers (clearly marked) instead of a blank screen.
LAST_GOOD = {}   # group -> (payload, time.time())

# Each floor's Sales Breakdown (still uploaded by hand) is kept fully isolated
# from the other floor. Global has no data of its own - it's a combined view.
BREAKDOWN_BY_FLOOR = {floor: [] for floor in FLOORS}

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Jinja Filters for Localization ---
def to_localized_string(value):
    return f"{value:,.0f}"

def to_talk_time(seconds):
    """Seconds -> 'm:ss' under an hour (91.8 -> '1:32'), 'h:mm:ss' from an hour up
    (13304 -> '3:41:44'); no live agents -> a dash."""
    if seconds is None:
        return '—'
    total = int(round(seconds))
    if total >= 3600:
        return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}"
    return f"{total // 60}:{total % 60:02d}"

app.jinja_env.filters['to_localized_string'] = to_localized_string
app.jinja_env.filters['to_talk_time'] = to_talk_time

# --- Live team stats ---
def load_team_stats(user_group):
    """
    (payload, problem). payload is the Suite's stats dict for this group, or the
    last good one if the Suite can't be reached right now (problem then says so),
    or None if there has never been a good pull.
    """
    try:
        payload = suite_client.get_team_stats(user_group)
        LAST_GOOD[user_group] = (payload, time.time())
        return payload, None
    except suite_client.SuiteError as e:
        last = LAST_GOOD.get(user_group)
        if last:
            return last[0], f'Live data is unavailable right now ({e}) — showing the last numbers loaded.'
        return None, str(e)

# --- Breakdown parsing (unchanged) ---
def process_breakdown_data(df):
    breakdown_data = []

    # Look for the breakdown table structure in the Excel file
    for i in range(len(df)):
        row = df.iloc[i].dropna().astype(str).str.strip()

        # Check if this row contains breakdown categories
        if len(row) >= 2:
            category = row.iloc[0]
            value_str = row.iloc[1]

            # Look for the specific breakdown categories
            if category in ['Vodacom Funeral', 'Media', 'Upsell', 'Total Sales']:
                try:
                    # Clean the value string (remove commas, etc.)
                    value_str_clean = value_str.replace(',', '').replace(' ', '')
                    numeric_value = int(float(value_str_clean))

                    breakdown_data.append({
                        'Category': category,
                        'Value': numeric_value
                    })
                except (ValueError, TypeError):
                    print(f"Could not convert value '{value_str}' to number for category '{category}'")
                    continue

    # If we didn't find the table structure, try alternative parsing
    if not breakdown_data:
        breakdown_data = parse_alternative_breakdown_structure(df)

    print(f"DEBUG: Processed breakdown data: {breakdown_data}")
    return breakdown_data

def parse_alternative_breakdown_structure(df):
    """Alternative parsing for different breakdown file structures"""
    breakdown_data = []

    # Convert entire dataframe to string and look for patterns
    df_str = df.astype(str)

    # Look for the specific values from your image: 300, 300, 300, 900
    funeral_value = None
    media_value = None
    upsell_value = None
    total_value = None

    for i in range(len(df_str)):
        for j in range(len(df_str.columns)):
            cell_value = df_str.iloc[i, j].strip()

            # Look for category names and their adjacent values
            if 'Vodacom Funeral' in cell_value:
                # Check adjacent cells for the value
                funeral_value = find_adjacent_numeric_value(df_str, i, j)
            elif 'Media' in cell_value and cell_value != 'Media':
                media_value = find_adjacent_numeric_value(df_str, i, j)
            elif 'Upsell' in cell_value and cell_value != 'Upsell':
                upsell_value = find_adjacent_numeric_value(df_str, i, j)
            elif 'Total Sales' in cell_value:
                total_value = find_adjacent_numeric_value(df_str, i, j)

    # Add found values to breakdown data
    if funeral_value is not None:
        breakdown_data.append({'Category': 'Vodacom Funeral', 'Value': funeral_value})
    if media_value is not None:
        breakdown_data.append({'Category': 'Media', 'Value': media_value})
    if upsell_value is not None:
        breakdown_data.append({'Category': 'Upsell', 'Value': upsell_value})
    if total_value is not None:
        breakdown_data.append({'Category': 'Total Sales', 'Value': total_value})

    return breakdown_data

def find_adjacent_numeric_value(df_str, row_idx, col_idx):
    """Find numeric value in adjacent cells"""
    # Check right cell
    if col_idx + 1 < len(df_str.columns):
        right_cell = df_str.iloc[row_idx, col_idx + 1].strip()
        try:
            return int(float(right_cell.replace(',', '')))
        except (ValueError, TypeError):
            pass

    # Check left cell
    if col_idx > 0:
        left_cell = df_str.iloc[row_idx, col_idx - 1].strip()
        try:
            return int(float(left_cell.replace(',', '')))
        except (ValueError, TypeError):
            pass

    # Check cell below
    if row_idx + 1 < len(df_str):
        below_cell = df_str.iloc[row_idx + 1, col_idx].strip()
        try:
            return int(float(below_cell.replace(',', '')))
        except (ValueError, TypeError):
            pass

    return None

def get_breakdown_for_group(user_group):
    if user_group == 'Global':
        combined = {}
        for floor in FLOORS:
            for item in BREAKDOWN_BY_FLOOR[floor]:
                category = item['Category']
                combined[category] = combined.get(category, 0) + item['Value']
        return [{'Category': category, 'Value': value} for category, value in combined.items()]
    return BREAKDOWN_BY_FLOOR.get(user_group, [])

# --- Routes ---
@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in USERS and USERS[username]['password'] == password:
            session['logged_in'] = True
            session['username'] = username
            session['user_group'] = USERS[username]['group']
            flash(f'Logged in as {USERS[username]["group"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
    return render_template('login.html', USERS=USERS)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

def _stats_context(user_group):
    payload, problem = load_team_stats(user_group)
    return dict(
        payload=payload,
        problem=problem,
        user_group=user_group,
        # Floor managers set their own floor's targets; the Global (admin) account can set any team's.
        can_edit_targets=user_group in DASHBOARD_GROUPS,
    )

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))

    user_group = session.get('user_group')
    return render_template('dashboard.html',
                          DASHBOARD_GROUPS=DASHBOARD_GROUPS,
                          **_stats_context(user_group))

@app.route('/stats_fragment')
def stats_fragment():
    """Just the KPI cards + table, re-fetched by the page every 30s so numbers stay live without a reload."""
    if 'logged_in' not in session:
        return {'error': 'Not logged in'}, 401
    return render_template('_stats.html', **_stats_context(session.get('user_group')))

@app.route('/update_target', methods=['POST'])
def update_target():
    """
    Sets one team's Target; it is saved in the reporting backend (the DB has no targets).
    A floor manager can only change their own floor's teams; the Global (admin) account
    names the team's floor in the request and can change any.
    """
    if 'logged_in' not in session:
        return {'error': 'Not logged in'}, 401

    user_group = session.get('user_group')
    if user_group not in DASHBOARD_GROUPS:
        return {'error': 'You cannot edit targets.'}, 403

    data = request.get_json(silent=True) or {}
    floor = user_group
    if user_group == 'Global':
        floor = data.get('floor')
        if floor not in FLOORS:
            return {'error': 'Unknown floor.'}, 400
    team = data.get('team')
    try:
        target = int(data.get('target'))
    except (TypeError, ValueError):
        return {'error': 'Target must be a whole number.'}, 400
    if not team or target < 0:
        return {'error': 'Target must be a whole number, 0 or more.'}, 400

    try:
        suite_client.set_team_target(floor, team, target)
    except suite_client.SuiteError as e:
        return {'error': str(e)}, 502

    return {'html': render_template('_stats.html', **_stats_context(user_group))}

@app.route('/upload_breakdown', methods=['POST'])
def upload_breakdown_file():
    if 'logged_in' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))

    user_group = session.get('user_group')
    if user_group not in FLOORS:
        flash('Only Floor 1 and Floor 2 accounts can upload a Sales Breakdown.', 'danger')
        return redirect(url_for('dashboard'))

    if 'breakdown_file' not in request.files:
        flash('No breakdown file part', 'danger')
        return redirect(url_for('dashboard'))

    file = request.files['breakdown_file']

    if file.filename == '' or not allowed_file(file.filename):
        flash('Invalid breakdown file selected.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        df = pd.read_excel(file, header=None)
        BREAKDOWN_BY_FLOOR[user_group] = process_breakdown_data(df)

        flash(f'Sales Breakdown for {user_group} successfully uploaded and data loaded!', 'success')

        # Only notify this floor's room and Global's combined view - the other floor is untouched
        socketio.emit('data_updated', {'type': 'breakdown_stats'}, room=user_group)
        socketio.emit('data_updated', {'type': 'breakdown_stats'}, room='Global')

        return redirect(url_for('dashboard', show_breakdown='true'))
    except Exception as e:
        flash(f'Error processing Breakdown file: {e}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/get_sales_breakdown')
def get_sales_breakdown():
    if 'logged_in' not in session:
        return {'error': 'Not logged in'}, 401

    user_group = session.get('user_group')
    return {'breakdown': get_breakdown_for_group(user_group)}

# Fallback for SocketIO issues
@app.route('/check_updates')
def check_updates():
    """Fallback endpoint for checking updates if WebSockets fail"""
    user_group = session.get('user_group', 'Global')
    return {'status': 'ok', 'group': user_group}

# --- SocketIO Handlers ---
@socketio.on('connect')
def handle_connect():
    print('Client connected:', request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected:', request.sid)

@socketio.on('join_dashboard')
def on_join_dashboard(data):
    room_name = data.get('group')
    if room_name and room_name in DASHBOARD_GROUPS:
        join_room(room_name)
        print(f"Client {request.sid} joined room: {room_name}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"Starting server on port {port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
