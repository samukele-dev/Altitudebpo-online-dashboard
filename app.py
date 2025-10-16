import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import json # Import json for better data serialization

# --- Configuration ---
app = Flask(__name__)
# IMPORTANT: Keep the security best practice for SECRET_KEY
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}


# --- NEW: Custom Jinja Filter Registration ---
def to_localized_string(value):
    """Formats a number (integer or float) with local commas."""
    try:
        # Convert to integer and format with commas
        return f"{int(value):,}"
    except (TypeError, ValueError):
        # Handle cases where value is None or non-numeric gracefully
        return str(value)

# Register the custom filter with Jinja
app.jinja_env.filters['to_localized_string'] = to_localized_string


# --- Global Data Store ---
# New structure: a dictionary where the key is the user's group/floor
# The value is the DataFrame rows associated with that group.
# { 'Floor 1': [{'Team': 'A', 'Target': 100, ...}, {...}],
#   'Floor 2': [{'Team': 'X', 'Target': 200, ...}, {...}] }
CALL_CENTER_DATA = {} 


def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- User Configuration ---
# 1. NEW USER DATA STRUCTURE: Assign users to a specific 'group' (Floor)
USERS = {
    'floor1_manager': {'password': 'pass1', 'group': 'Floor 1'},
    'floor2_manager': {'password': 'pass2', 'group': 'Floor 2'}
} 

# --- Helper Function for Data Retrieval ---
def get_all_stats():
    """Combines stats from all floors into a single list for global totals."""
    all_stats = []
    for floor_stats in CALL_CENTER_DATA.values():
        all_stats.extend(floor_stats)
    return all_stats

# --- Routes ---

@app.route('/')
def index():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check username and password, then set user group in session
        if username in USERS and USERS[username]['password'] == password:
            session['logged_in'] = True
            session['username'] = username
            # Store the user's floor/group in the session
            session['user_group'] = USERS[username]['group'] 
            flash(f"Login successful! Welcome to {session['user_group']}.", 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Handles user logout."""
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('user_group', None) # Clean up the new user_group key
    flash('You have been logged out.', 'info')
    return redirect(url_for('login')) # This line correctly calls 'login'

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Handles file upload and associates data with the logged-in user's floor."""
    if 'logged_in' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))
    
    # Get the current user's group
    user_group = session.get('user_group')
    if not user_group:
        flash('User session missing group information. Please log in again.', 'danger')
        return redirect(url_for('login'))
        
    global CALL_CENTER_DATA
    
    if request.method == 'POST':
        # ... (Keep file handling checks the same) ...
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
            
        if file and allowed_file(file.filename):
            # We don't need to save the file, we can process it directly from the memory stream
            try:
                # Read the Excel file into a pandas DataFrame from the file stream
                df = pd.read_excel(file)

                # --- Calculation Logic ---
                if 'Team' in df.columns and 'Target' in df.columns and 'Current' in df.columns:
                    df.dropna(subset=['Team', 'Target', 'Current'], inplace=True)
                    df['Target'] = pd.to_numeric(df['Target'], errors='coerce')
                    df['Current'] = pd.to_numeric(df['Current'], errors='coerce')
                    df['Shortfall'] = df['Target'] - df['Current']

                    required_cols = ['Team', 'Target', 'Current', 'Shortfall']
                    df_stats = df[[col for col in required_cols if col in df.columns]]
                    
                    # Store the data under the user's group/floor key
                    CALL_CENTER_DATA[user_group] = df_stats.to_dict('records')
                    
                    flash(f'File "{file.filename}" successfully uploaded and data loaded for {user_group}!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Error: Excel file must contain "Team", "Target", and "Current" columns.', 'danger')
                    return redirect(request.url)
                    
            except Exception as e:
                flash(f'Error processing file: {e}', 'danger')
                return redirect(request.url)
        else:
            flash('File type not allowed. Use .xlsx or .xls.', 'danger')
            return redirect(request.url)

    return render_template('upload.html')


@app.route('/dashboard')
def dashboard():
    """Displays dashboard: global totals and filtered team stats."""
    if 'logged_in' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))
    
    user_group = session.get('user_group')
    
    # 1. Calculate GLOBAL Totals (from ALL floors)
    all_stats = get_all_stats()
    totals = {'Total Target': 0, 'Total Current': 0, 'Total Shortfall': 0}
    
    if all_stats:
        df_all = pd.DataFrame(all_stats)
        for col in ['Target', 'Current', 'Shortfall']:
            if col in df_all.columns:
                totals[f'Total {col}'] = df_all[col].sum()
    
    # 2. Get FILTERED Team Stats (only for the logged-in user's floor)
    filtered_stats = CALL_CENTER_DATA.get(user_group, [])

    return render_template('dashboard.html', 
                           stats=filtered_stats,  # Only the user's floor data
                           totals=totals,       # Global totals
                           user_group=user_group)


@app.route('/health')
def health_check():
    """Returns a simple 200 OK status for external monitoring services."""
    return {'status': 'ok', 'service': 'altitude-bpo-dashboard'}, 200


# --- API Endpoint (Updated to serve only filtered data) ---
@app.route('/api/stats')
def get_stats():
    """Returns the current stats data ONLY for the logged-in user's floor."""
    if 'logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    user_group = session.get('user_group')
    
    # Return only the data associated with the user's group
    filtered_data = CALL_CENTER_DATA.get(user_group, [])
    
    return {'data': filtered_data}


if __name__ == '__main__':
    # Initial setup for testing: load some dummy data if needed
    # CALL_CENTER_DATA = { 
    #     'Floor 1': [{'Team': 'Red', 'Target': 100, 'Current': 110, 'Shortfall': -10}], 
    #     'Floor 2': [{'Team': 'Blue', 'Target': 200, 'Current': 150, 'Shortfall': 50}]
    # }
    app.run(debug=True)