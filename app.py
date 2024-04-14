import datetime
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = 'secret'  # Replace with your secret key
app.debug = True
# Database configuration
db_config = {
    'host': 'localhost',
    'database': 'bughound-project',  # Replace with your database name
    'user': 'root'  # Replace with your username
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Ensure you are selecting the user level (e.g., user_level)
        query = "SELECT user_id, username, level FROM users WHERE username = %s AND password = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()

        if user:
            session['logged_in'] = True
            session['user_name'] = user[1]
            session['level'] = int(user[2])  # Store user level in session
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()  # Clear the entire session
    return redirect(url_for('index'))

@app.route('/home')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('home.html', user_name=session.get('user_name'))

@app.route('/create')
def create_report():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    level = session.get('level', 0)  # Default to level 0 if not set
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT program_id, program_name FROM program")  # Query to fetch program names
    programs = cursor.fetchall()
    cursor.execute("SELECT username FROM users")
    users = cursor.fetchall() 
    cursor.execute("SELECT area_id, name FROM `functional-area`")  # Query to fetch area names
    areas = cursor.fetchall()
    return render_template('report.html', level=level,  user_name=session.get('user_name'), programs = programs, users = users, areas = areas)

@app.route('/submit_report', methods=['POST'])
def submit_report():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    # Extract form data
    program_id = request.form.get('program')
    bug_type = request.form.get('bug_type')
    severity = request.form.get('severity')
    problem_summary = request.form.get('problem-summary')
    description = request.form.get('description')
    reproducible = '1' if request.form.get('reproducible') == 'on' else '0'
    suggested_fix = request.form.get('suggested-fix')
    reported_by = request.form.get('reported-by')
    report_date = request.form.get('report-date') or datetime.date.today().isoformat()
    status = request.form.get('status')
    assigned_user = request.form.get('assigned-to')
    date_resolved = request.form.get('resolved-date') or None  # Handle empty date fields properly
    priority = request.form.get('priority')
    tested_by = request.form.get('tested-by')
    area_id = request.form.get('area')
    resolution = request.form.get('resolution')

    sql = """
    INSERT INTO `bug-report` (program_id, bug_type, severity, problem_summary, description, reproducible, suggested_fix, reported_by, date_created, status, assigned_user, date_resolved, priority, tested_by, area_id, resolution)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = (program_id, bug_type, severity, problem_summary, description, reproducible, suggested_fix, reported_by, report_date, status, assigned_user, date_resolved, priority, tested_by, area_id, resolution)

    cursor.execute(sql, values)
    conn.commit()  # Commit to save changes to the database

    cursor.close()
    conn.close()

    flash('Report submitted successfully!')
    return redirect(url_for('home'))

@app.route('/update')
def update_bug_report():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    # username = session.get('username', 0)
    # Assuming you have a function to fetch bug reports from your database:
    bug_reports = fetch_bug_reports()  # You need to define this function

    return render_template('update.html', bug_reports=bug_reports, user_name=session.get('user_name'))

def fetch_bug_reports():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)  # Use dictionary cursor to return data as dictionaries

    cursor.execute("SELECT bug_id, description, assigned_user, priority, status FROM `bug-report`")
    bug_reports = cursor.fetchall()

    cursor.close()
    conn.close()

    return bug_reports

@app.route('/edit_report/<int:bug_id>')
def edit_report(bug_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM `bug-report` WHERE bug_id = %s", (bug_id,))
    bug_details = cursor.fetchone()
    cursor.close()
    conn.close()

    if not bug_details:
        flash('Bug report not found.')
        return redirect(url_for('update_bug_report'))
    return render_template('report.html', bug=bug_details)

if __name__ == '__main__':
    app.run(debug=True)
