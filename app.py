import pandas as pd
import json
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit, join_room
from flask_cors import CORS

# --- Configuration & Setup ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_super_secret_key') 
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# SocketIO configuration - use threading instead of eventlet
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='threading',  # Use threading instead of eventlet
    logger=True,
    engineio_logger=True
)

# Simple User/Group Management
USERS = {
    'admin': {'password': 'admin', 'group': 'Global'},
    'floor1_manager': {'password': 'f1pass1', 'group': 'Floor 1'},
    'floor2_manager': {'password': 'f2pass2', 'group': 'Floor 2'}
}
DASHBOARD_GROUPS = ['Global', 'Floor 1', 'Floor 2']

# --- Global Data Store ---
ALL_RAW_TEAMS = [] 
TEAM_ALLOCATIONS = {} 
SALES_BREAKDOWN_DATA = [] 

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Jinja Filter for Localization ---
def to_localized_string(value):
    return f"{value:,.0f}"

app.jinja_env.filters['to_localized_string'] = to_localized_string

# --- Helper Functions ---
def find_header_and_prepare_df(df, column_name):
    header_index = -1
    for i in range(min(15, len(df))):
        if column_name in df.iloc[i].values:
            header_index = i
            break
            
    if header_index == -1:
        return None 

    df.columns = df.iloc[header_index]
    df = df[header_index+1:].reset_index(drop=True)
    
    df.columns = df.columns.astype(str).str.strip().str.replace(r'[^A-Za-z0-9_]+', '', regex=True)

    if column_name not in df.columns:
        return None
        
    return df

def process_team_data_from_df(df):
    df_data = find_header_and_prepare_df(df, 'Team')
    
    if df_data is None:
        return None
        
    TEAM_COL = 'Team'
    TARGET_COL = 'Target'
    CURRENT_COL = 'Current'

    if all(col in df_data.columns for col in [TEAM_COL, TARGET_COL, CURRENT_COL]):
        df_stats = df_data.copy()
        
        df_stats = df_stats[df_stats[TEAM_COL].astype(str).str.strip() != ''].copy()
        breakdown_keys = ['Vodacom Funeral', 'Media', 'Upsell', 'Total Sales']
        df_stats = df_stats[~df_stats[TEAM_COL].astype(str).isin(breakdown_keys)].copy()

        if not df_stats.empty:
            df_stats[TARGET_COL] = pd.to_numeric(df_stats[TARGET_COL], errors='coerce').fillna(0).astype(int)
            df_stats[CURRENT_COL] = pd.to_numeric(df_stats[CURRENT_COL], errors='coerce').fillna(0).astype(int)
            df_stats['Shortfall'] = df_stats[TARGET_COL] - df_stats[CURRENT_COL]

            required_cols = [TEAM_COL, TARGET_COL, CURRENT_COL, 'Shortfall']
            df_stats = df_stats[[col for col in required_cols if col in df_stats.columns]]
            
            return df_stats.to_dict('records')
        else:
            return []
    else:
        return None
    

def process_breakdown_data(df):
    global SALES_BREAKDOWN_DATA
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
    
    SALES_BREAKDOWN_DATA = breakdown_data
    print(f"DEBUG: Processed breakdown data: {breakdown_data}")

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

def get_filtered_stats(user_group):
    if user_group == 'Global':
        return ALL_RAW_TEAMS
    
    filtered_stats = []
    for team_stat in ALL_RAW_TEAMS:
        team_name = team_stat.get('Team')
        allocation = TEAM_ALLOCATIONS.get(team_name, 'Global')
        
        if allocation == user_group or allocation == 'Global':
            filtered_stats.append(team_stat)
            
    return filtered_stats

def get_all_stats():
    return ALL_RAW_TEAMS

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

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))
    
    user_group = session.get('user_group')
    
    # Get filtered stats for the table
    filtered_stats = get_filtered_stats(user_group)
    
    # Calculate GLOBAL Totals (for KPI cards)
    all_stats = get_all_stats()
    totals = {'Total Target': 0, 'Total Current': 0, 'Total Shortfall': 0}
    
    if all_stats:
        df_all = pd.DataFrame(all_stats)
        for col in ['Target', 'Current', 'Shortfall']:
            if col in df_all.columns:
                totals[f'Total {col}'] = pd.to_numeric(df_all[col], errors='coerce').sum().astype(int)
    
    # Prepare data for the Dashboard Assignment (Global Admin only)
    allocation_data = {
        team_stat['Team']: TEAM_ALLOCATIONS.get(team_stat['Team'], 'Global')
        for team_stat in ALL_RAW_TEAMS
    }

    return render_template('dashboard.html', 
                          stats=filtered_stats, 
                          totals=totals, 
                          user_group=user_group,
                          allocation_data=allocation_data,
                          DASHBOARD_GROUPS=DASHBOARD_GROUPS)

@app.route('/set_dashboard_assignment', methods=['POST'])
def set_dashboard_assignment():
    global TEAM_ALLOCATIONS
    
    if session.get('user_group') != 'Global':
        return json.dumps({"status": "error", "message": "Unauthorized"}), 403
    
    try:
        data = request.get_json()
        team_name = data.get('team_name')
        dashboard = data.get('dashboard')
        
        if team_name and dashboard in ['Global', 'Floor 1', 'Floor 2']:
            old_dashboard = TEAM_ALLOCATIONS.get(team_name, 'Global')
            TEAM_ALLOCATIONS[team_name] = dashboard
            
            # Notify affected rooms to fetch new, filtered data
            affected_floors = set()
            if old_dashboard != dashboard:
                if old_dashboard != 'Global':
                    affected_floors.add(old_dashboard)
                affected_floors.add(dashboard)
            
            # Ensure Global Admin sees the change immediately too
            if 'Global' not in affected_floors:
                affected_floors.add('Global')
            
            # Notify affected rooms
            for floor in affected_floors:
                socketio.emit('data_updated', 
                            {'type': 'dashboard_assignment', 'group': floor}, 
                            room=floor)
            
            return json.dumps({"status": "success", "message": f"Team {team_name} assigned to {dashboard}"}), 200
        else:
            return json.dumps({"status": "error", "message": "Invalid data"}), 400

    except Exception as e:
        print(f"Error processing dashboard assignment: {e}")
        return json.dumps({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/admin_upload_team_file', methods=['POST'])
def admin_upload_team_file():
    global ALL_RAW_TEAMS, TEAM_ALLOCATIONS

    if session.get('user_group') != 'Global':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('dashboard'))
        
    file = request.files['file']
    
    if file.filename == '' or not allowed_file(file.filename):
        flash('Invalid file selected.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        df = pd.read_excel(file, header=None)
        raw_stats = process_team_data_from_df(df)

        if raw_stats is None:
            flash('Error: Could not process team data from the file format.', 'danger')
            return redirect(url_for('dashboard'))

        # Update the raw data source
        ALL_RAW_TEAMS = raw_stats

        # Update TEAM_ALLOCATIONS for new teams
        for team_stat in ALL_RAW_TEAMS:
            team_name = team_stat.get('Team')
            if team_name and team_name not in TEAM_ALLOCATIONS:
                TEAM_ALLOCATIONS[team_name] = 'Global'

        flash('Team Stats successfully loaded! You can now assign teams to specific floors.', 'success')
        
        # Broadcast to all clients
        socketio.emit('data_updated', {'type': 'team_stats', 'group': 'Global'}) 

        return redirect(url_for('dashboard'))
        
    except Exception as e:
        flash(f'Error processing Team file: {e}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/upload_breakdown', methods=['POST'])
def upload_breakdown_file():
    if 'logged_in' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))
    
    user_group = session.get('user_group')
    
    target_floors = []
    if user_group == 'Global':
        target_floors_list = request.form.getlist('breakdown_target_floors')
        target_floors = [f for f in target_floors_list if f in DASHBOARD_GROUPS]
    else:
        target_floors = [user_group]
    
    if 'breakdown_file' not in request.files:
        flash('No breakdown file part', 'danger')
        return redirect(url_for('dashboard'))
    
    file = request.files['breakdown_file']
    
    if file.filename == '' or not allowed_file(file.filename):
        flash('Invalid breakdown file selected.', 'danger')
        return redirect(url_for('dashboard'))
        
    try:
        df = pd.read_excel(file, header=None)
        process_breakdown_data(df)
        
        flash('Sales Breakdown file successfully uploaded and data loaded!', 'success')
        
        for floor in target_floors:
            socketio.emit('data_updated', {'type': 'breakdown_stats'}, room=floor)
        
        return redirect(url_for('dashboard', show_breakdown='true')) 
    except Exception as e:
        flash(f'Error processing Breakdown file: {e}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/get_sales_breakdown')
def get_sales_breakdown():
    if 'logged_in' not in session:
        return {'error': 'Not logged in'}, 401
    
    return {'breakdown': SALES_BREAKDOWN_DATA}

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
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    print(f"Starting server on port {port} with debug={debug}")
    
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=port, 
        debug=debug,
        allow_unsafe_werkzeug=True
    )