import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd

# --- Configuration ---
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))
print(os.urandom(24))
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Allowed extensions for uploads
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

# --- Global Data Store
# database (SQLite)
CALL_CENTER_STATS = None

def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Routes ---

# Simple hardcoded user
USERS = {'admin': 'password123'} 

@app.route('/')
def index():
    """Redirects to login if not logged in, otherwise to dashboard."""
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in USERS and USERS[username] == password:
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Handles user logout."""
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Handles file upload and calculates Shortfall after reading Excel data."""
    if 'logged_in' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))
        
    global CALL_CENTER_STATS
    
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
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                # Read the Excel file into a pandas DataFrame
                df = pd.read_excel(filepath)

                # --- NEW LOGIC: Calculate Shortfall ---
                # Ensure the necessary columns exist and are numeric
                if 'Target' in df.columns and 'Current' in df.columns:
                    # Drop rows where critical columns are missing
                    df.dropna(subset=['Target', 'Current'], inplace=True)
                    
                    # Convert to numeric, coercing errors will turn non-numbers into NaN
                    df['Target'] = pd.to_numeric(df['Target'], errors='coerce')
                    df['Current'] = pd.to_numeric(df['Current'], errors='coerce')

                    # The calculation: Shortfall = Target - Current
                    df['Shortfall'] = df['Target'] - df['Current']

                    # Keep only the columns we need, including the newly calculated Shortfall
                    required_cols = ['Team', 'Target', 'Current', 'Shortfall']
                    df_stats = df[[col for col in required_cols if col in df.columns]]
                    
                    # Convert the DataFrame to a list of dictionaries
                    CALL_CENTER_STATS = df_stats.to_dict('records')
                    
                    flash(f'File "{filename}" successfully uploaded and data loaded!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Error: Excel file must contain "Target" and "Current" columns.', 'danger')
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
    """Displays the main dashboard with loaded data and calculated totals."""
    if 'logged_in' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('login'))
        
    # --- NEW LOGIC: Calculate Total KPIs for Summary Cards ---
    totals = {'Total Target': 0, 'Total Current': 0, 'Total Shortfall': 0}
    
    if CALL_CENTER_STATS:
        df = pd.DataFrame(CALL_CENTER_STATS)
        
        # Ensure columns are numeric before summing
        for col in ['Target', 'Current', 'Shortfall']:
            if col in df.columns:
                totals[f'Total {col}'] = df[col].sum()
    
    return render_template('dashboard.html', stats=CALL_CENTER_STATS, totals=totals)

# --- API Endpoint (For JavaScript/Filtering) ---
@app.route('/api/stats')
def get_stats():
    """Returns the current stats data as JSON for the frontend to consume."""
    if 'logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    # In a real app, you would apply filtering based on query parameters here
    return {'data': CALL_CENTER_STATS or []}


if __name__ == '__main__':
    # When deploying to Render, you will typically use a Gunicorn server, 
    # but for local testing, this is fine.
    app.run(debug=True)