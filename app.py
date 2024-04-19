import csv
import datetime
from io import StringIO
import mysql.connector
from flask import Flask, make_response, render_template, request, redirect, url_for, flash, session
from datetime import date
from werkzeug.utils import secure_filename
from flask import jsonify
from xml.etree.ElementTree import Element, SubElement, tostring  # XML handling
import xml.etree.ElementTree as ET 

app = Flask(__name__)
app.secret_key = 'secret'  
app.debug = True

db_config = {
    'host': 'localhost',
    'database': 'bughound-project',  
    'user': 'root'  
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

        query = "SELECT user_id, username, level FROM users WHERE username = %s AND password = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()

        if user:
            session['logged_in'] = True
            session['user_name'] = user[1]
            session['level'] = int(user[2]) 
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()  
    return redirect(url_for('index'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        employname = request.form['employname']
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        squery = "SELECT username FROM users "
        cursor.execute(squery)
        results = cursor.fetchall()
        print(results)

        existing_user = [row[0] for row in results]
        if username in existing_user:
            flash('Username already exists. Please choose a different Name.', 'username_error')
        elif password != confirm_password:
            flash('Passwords do not match. Please try again.', 'password_error')
        else:
            insert_query = "INSERT INTO users (employname, username, password, level) VALUES (%s, %s, %s, %s)"
            cursor.execute(insert_query, (employname, username, password, 1))  # Set level to 1 by default
            conn.commit()  # Commit the transaction

            flash('Signup successful! You can now login.', 'success')
            return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/home')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    level = session.get('level', 0)
    return render_template('home.html', level=level, user_name=session.get('user_name'))

@app.route('/create')
def create_report():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    level = session.get('level', 0)  
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT program_id, program_name FROM program")  
    programs = cursor.fetchall()
    cursor.execute("SELECT username FROM users")
    users = cursor.fetchall() 
    cursor.execute("SELECT area_id, name FROM `functional-area`")  
    areas = cursor.fetchall()
    today = date.today().strftime('%Y-%m-%d')
    report_types = [
        ('Coding Error', 'Coding Error'),
        ('Design Issue', 'Design Issue'),
        ('Suggestion', 'Suggestion'),
        ('Documentation', 'Documentation'),
        ('Hardware', 'Hardware'),
        ('Query', 'Query')
    ]

    severity_levels = [
        ('Minor', 'Minor'),
        ('Serious', 'Serious'),
        ('Fatal', 'Fatal')
    ]
    return render_template('report.html', level=level,  user_name=session.get('user_name'), programs = programs, users = users, areas = areas, report_types=report_types, severity_levels=severity_levels, today=today)

@app.route('/adduser', defaults={'user_id': None}, methods=['GET', 'POST'])
@app.route('/adduser/<int:user_id>', methods=['GET', 'POST'])
def adduser(user_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        return submit_or_update_user(request.form, user_id)
    
    user = None if user_id is None else get_user_details(cursor, user_id)
    cursor.close()
    conn.close()

    return render_template('add_user.html', user=user, user_name=session.get('user_name'))

@app.route('/addprogram', defaults={'program_id': None}, methods=['GET', 'POST'])
@app.route('/addprogram/<int:program_id>', methods=['GET', 'POST'])
def addprogram(program_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    print(program_id)
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        return submit_or_update_program(request.form, program_id)
    
    program = None if program_id is None else get_program_details(cursor, program_id)
    if program:
            program['version'] = program['versions'][0] if program.get('versions') else ''
            program['releaseversion'] = program['releases'][0] if program.get('releases') else ''
            if program.get('release-date') and isinstance(program['release-date'][0], date):
                program['release_date'] = program['release-date'][0].strftime('%Y-%m-%d')

    print(program)
    cursor.close()
    conn.close()

    return render_template('add_program.html', program=program, user_name=session.get('user_name'))

@app.route('/addfuncarea', defaults={'area_id': None}, methods=['GET', 'POST'])
@app.route('/addfuncarea/<int:area_id>', methods=['GET', 'POST'])
def addfuncarea(area_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        return submit_or_update_area(request.form, area_id)
    
    area = None if area_id is None else get_area_details(cursor, area_id)
    cursor.execute("SELECT MIN(program_id) as program_id, program_name FROM program GROUP BY program_name ORDER BY program_name")
    programs = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('add_functionalarea.html',area=area, programs=programs, user_name=session.get('user_name'))

@app.route('/report', defaults={'bug_id': None}, methods=['GET', 'POST'])
@app.route('/report/<int:bug_id>', methods=['GET', 'POST'])
def report(bug_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        return submit_or_update_report(request.form, bug_id)

    bug = None if bug_id is None else get_bug_details(cursor, bug_id)
    programs, users, areas = fetch_lookups(cursor)
    report_types = [
        ('Coding Error', 'Coding Error'),
        ('Design Issue', 'Design Issue'),
        ('Suggestion', 'Suggestion'),
        ('Documentation', 'Documentation'),
        ('Hardware', 'Hardware'),
        ('Query', 'Query')
    ]
    severity_levels = [
        ('Minor', 'Minor'),
        ('Serious', 'Serious'),
        ('Fatal', 'Fatal')
    ]
    level = session.get('level', 0)
    cursor.close()
    conn.close()

    return render_template('report.html', bug=bug, programs=programs, users=users, areas=areas, level = level, report_types=report_types, severity_levels=severity_levels, user_name=session.get('user_name'))

def save_attachment_to_database(bug_id, filename, data, cursor):
    sql = """
    INSERT INTO attachment (bug_id, file_name, data)
    VALUES (%s, %s, %s)
    """
    cursor.execute(sql, (bug_id, filename, data))

def allowed_file(filename):
    
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


def submit_or_update_report(form, bug_id=None):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()

    date_resolved = form.get('resolved-date') or None
    report_date = form.get('report-date') or datetime.date.today().isoformat()
    area_id = form.get('area') or None
    assigned_user = form.get('assigned-to') or None
    priority = form.get('priority') or None
    date_tested = form.get('tested-date') or None
    resolution_version = form.get('resolution-version') or None

    # Base data list
    data = [
        form.get('program'), form.get('bug_type'), form.get('severity'), form.get('problem-summary'),
        form.get('description'), '1' if form.get('reproducible') == 'on' else '0',
        form.get('suggested-fix'), form.get('reported-by'), report_date,
        form.get('status'), assigned_user, form.get('comments'), date_resolved, priority,
        form.get('tested-by'), date_tested, area_id, form.get('resolution'), 
        resolution_version, form.get('resolved-by')
    ]

    if bug_id is None:
        
        sql = """INSERT INTO `bug-report` (program_id, bug_type, severity, problem_summary, description, reproducible, suggested_fix,
                 reported_by, date_created, status, assigned_user, comments, date_resolved, priority, tested_by, date_tested, area_id, resolution, resolution_version, resolved_by)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        
        cursor.execute(sql, data)
        flash('Report submitted successfully!' if bug_id is None else 'Report updated successfully!')    
        bug_id = cursor.lastrowid  
    else:
        data.append(bug_id)  
        sql = """UPDATE `bug-report` SET program_id=%s, bug_type=%s, severity=%s, problem_summary=%s, description=%s, 
                 reproducible=%s, suggested_fix=%s, reported_by=%s, date_created=%s, status=%s, assigned_user=%s, comments=%s,
                 date_resolved=%s, priority=%s, tested_by=%s, date_tested=%s, area_id=%s, resolution=%s, resolution_version=%s, resolved_by=%s WHERE bug_id=%s"""
        cursor.execute(sql, data)
        flash('Report submitted successfully!' if bug_id is None else 'Report updated successfully!')

    if 'attachments' in request.files:
        files = request.files.getlist('attachments')
        for file in files:
            if file and allowed_file(file.filename): 
                filename = secure_filename(file.filename)
                file_data = file.read() 
                
                d = [bug_id, filename, file_data]
                print(d)
                sql = """INSERT INTO attachment (bug_id, file_name, data) VALUES (%s, %s, %s)"""
                
                try:
                    cursor.execute(sql, d)
                    print("query is working")
                except Exception as e:
                        print("Failed to insert data:", e)
                        
                        raise
                
    conn.commit()
    cursor.close()
    conn.close()
  
    return redirect(url_for('home'))


def fetch_lookups(cursor):
    cursor.execute("SELECT program_id, program_name FROM program")
    programs = cursor.fetchall()
    cursor.execute("SELECT username FROM users")
    users = cursor.fetchall()
    cursor.execute("SELECT area_id, name FROM `functional-area`")
    areas = cursor.fetchall()
    return programs, users, areas

def get_bug_details(cursor, bug_id):
    cursor.execute("SELECT * FROM `bug-report` WHERE bug_id = %s", (bug_id,))
    return cursor.fetchone()

def get_area_details(cursor, area_id):
    cursor.execute("""
        SELECT fa.area_id, fa.name, p.program_name, p.version, p.releaseversion
        FROM `functional-area` fa
        JOIN program p ON fa.program_id = p.program_id
        WHERE fa.area_id = %s
    """, (area_id,))
    return cursor.fetchone()

def get_program_details(cursor, program_id):
    cursor.execute("SELECT * FROM program WHERE program_id = %s", (program_id,))
    program = cursor.fetchone()
    if program:
        data = {
            "program_id" : program['program_id'],
            "program_name": program['program_name'],
            "versions": [program['version']],
            "releases": [program['releaseversion']],
            "release-date": [program['release_date']]
        }
    else:
        data = {
            "program_id" : program['program_id'],
            "program_name": None,
            "versions": [],
            "releases": [],
            "release-date" : None
        }
    print(data)
    return data

@app.route('/get-program-details/<int:program_id>')
def fetch_program_details(program_id):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    data = get_program_details(cursor, program_id)

    cursor.close()
    conn.close()

    if data['program_name'] is None:
        return jsonify({}), 404  # Return an empty response with a 404 status if no program is found

    return jsonify(data), 200  # Return the data as JSON with a 200 OK status

@app.route('/get-program-details-by-name/<program_name>')
def fetch_program_details_by_name(program_name):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT version, releaseversion FROM program WHERE program_name = %s", (program_name,))
        results = cursor.fetchall()
        if results:
            data = {
                "versions": [result['version'] for result in results],
                "releases": [result['releaseversion'] for result in results]
            }
        else:
            data = {"versions": [], "releases": []}
    finally:
        cursor.close()
        conn.close()

    if not results:
        return jsonify({}), 404  # Return an empty response with a 404 status if no data is found

    return jsonify(data), 200


def get_user_details(cursor, user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    return cursor.fetchone()

@app.route('/update')
def update_bug_report():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    bug_reports = fetch_bug_reports()  

    return render_template('update.html', bug_reports=bug_reports, user_name=session.get('user_name'))

def fetch_bug_reports():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)  

    cursor.execute("SELECT bug_id, description, assigned_user, priority, status FROM `bug-report`")
    bug_reports = cursor.fetchall()

    cursor.close()
    conn.close()

    return bug_reports

def fetch_func_area():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)  

    cursor.execute("SELECT `functional-area`.area_id, `functional-area`.name, program.program_name FROM `functional-area` JOIN program ON `functional-area`.program_id = program.program_id ORDER BY `functional-area`.area_id")
    func_area = cursor.fetchall()

    cursor.close()
    conn.close()

    return func_area

def fetch_programs():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)  

    cursor.execute("SELECT program_id, program_name, version, releaseversion, release_date FROM program")
    program = cursor.fetchall()

    cursor.close()
    conn.close()

    return program

def fetch_users():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)  

    cursor.execute("SELECT user_id, employname, username, password, level FROM users")
    users = cursor.fetchall()

    cursor.close()
    conn.close()

    return users

@app.route('/subdashboard')
def subdashboard_page():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('subdashboard.html', user_name=session.get('user_name'))

@app.route('/user')
def user():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    users = fetch_users()
    return render_template('user.html', users=users, user_name=session.get('user_name'))

@app.route('/program')
def program():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    programs = fetch_programs()
    return render_template('program.html', programs=programs, user_name=session.get('user_name'))

@app.route('/functionalarea')
def functional_area():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    func_area = fetch_func_area()
    return render_template('functionalarea.html', func_area=func_area, user_name=session.get('user_name'))

def submit_or_update_user(form, user_id=None):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    data = (
        form.get('employname'), form.get('username'), form.get('level'), form.get('password')
    )

    if user_id is None:
        sql = """INSERT INTO users (employname, username, level, password)
                 VALUES (%s, %s, %s, %s)"""
    else:
        sql = """UPDATE users SET employname=%s, username=%s, level=%s, password=%s WHERE user_id=%s"""
        data += (user_id,)

    cursor.execute(sql, data)
    conn.commit()
    cursor.close()
    conn.close()

    flash('User added successfully!' if user_id is None else 'User updated successfully!')
    return redirect(url_for('user'))

def submit_or_update_program(form, program_id):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    print(program_id)
    data = (
        form.get('program-name'), form.get('version'), form.get('releaseversion'), form.get('release-date')
    )

    if program_id is None:
        sql = """INSERT INTO program (program_name, version,releaseversion, release_date)
                 VALUES (%s, %s, %s, %s)"""
    else:
        sql = """UPDATE program SET program_name=%s, version=%s, releaseversion=%s, release_date=%s WHERE program_id=%s"""
        data += (program_id,)

    cursor.execute(sql, data)
    conn.commit()
    cursor.close()
    conn.close()

    flash('Program added successfully!' if program_id is None else 'Program updated successfully!')
    return redirect(url_for('program'))

def submit_or_update_area(form, area_id=None):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)  

    program_name = form.get('program')
    version = form.get('program-version')
    releaseversion = form.get('program-release')
    cursor.execute("SELECT program_id FROM program WHERE program_name = %s AND version=%s AND releaseversion=%s", (program_name,version, releaseversion))
    program = cursor.fetchone()
    
    # Check if the program was found
    if program is None:
        flash('Program not found.')
        return redirect(url_for('functional_area'))

    # Prepare data for the functional-area query
    program_id = program['program_id']
    functional_area_name = form.get('functional-area')
    data = (program_id, functional_area_name)

    # Decide if it's an insert or update operation based on area_id
    if area_id is None:
        sql = """INSERT INTO `functional-area` (program_id, name)
                 VALUES (%s, %s)"""
    else:
        sql = """UPDATE `functional-area` SET program_id=%s, name=%s WHERE area_id=%s"""
        data += (area_id,)

    # Execute the query and commit changes
    cursor.execute(sql, data)
    conn.commit()

    # Clean up: close cursor and connection
    cursor.close()
    conn.close()

    # Provide user feedback
    flash('Functional area submitted successfully!' if area_id is None else 'Functional area updated successfully!')
    return redirect(url_for('functional_area'))

# def submit_or_update_area(form, area_id=None):
#     conn = mysql.connector.connect(**db_config)
#     cursor = conn.cursor()
#     data = (
#         form.get('program'), form.get('functional-area')
#     )
#     if area_id is None:
#         sql = """INSERT INTO `functional-area` (program_id, name)
#                  VALUES (%s, %s)"""
#     else:
#         sql = """UPDATE `functional-area` SET program_id=%s, name=%s WHERE area_id=%s"""
#         data += (area_id,)
#     cursor.execute(sql, data)
#     conn.commit()
#     cursor.close()
#     conn.close()
#     flash('Functional area submitted successfully!' if area_id is None else 'Functional area updated successfully!')
#     return redirect(url_for('functional_area'))

@app.route('/user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()
        flash('User deleted successfully!')
    except Exception as e:
        flash(f"Error deleting user: {str(e)}", 'error')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('user'))

@app.route('/program/<int:program_id>', methods=['POST'])
def delete_program(program_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM program WHERE program_id = %s", (program_id,))
        conn.commit()
        flash('Program deleted successfully!')
    except Exception as e:
        flash(f"Error deleting program: {str(e)}", 'error')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('program'))

@app.route('/deletefuncarea/<int:area_id>', methods=['POST'])
def delete_func_area(area_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM `functional-area` WHERE area_id = %s", (area_id,))
        conn.commit()
        flash('Functional area deleted successfully!')
    except Exception as e:
        flash(f"Error deleting functional area: {str(e)}", 'error')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('functional_area'))



@app.route('/delete_bug', defaults={'bug_id': None}, methods=['GET', 'POST'])
@app.route('/delete_bug/<int:bug_id>', methods=['POST'])
def delete_bug(bug_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM `bug-report` WHERE bug_id = %s", (bug_id,))
        conn.commit()
        flash('Bug report deleted successfully!')
    except Exception as e:
        flash(f"Error deleting bug report: {str(e)}", 'error')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('delete'))

@app.route('/delete')
def delete():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM `bug-report`")
    bugs = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('delete.html', bugs=bugs, user_name=session.get('user_name'))


@app.route('/search')
def search_reports():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    level = session.get('level', 0)  
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT program_id, program_name FROM program")  
    programs = cursor.fetchall()
    cursor.execute("SELECT username FROM users")
    users = cursor.fetchall() 
    cursor.execute("SELECT area_id, name FROM `functional-area`")  
    areas = cursor.fetchall()
    
    report_types = [
        ('bug', 'Coding Error'),
        ('issue', 'Design Issue'),
        ('suggestion', 'Suggestion'),
        ('documentation', 'Documentation'),
        ('hardware', 'Hardware'),
        ('query', 'Query')
    ]

    severity_levels = [
        ('Minor', 'Minor'),
        ('Serious', 'Serious'),
        ('Fatal', 'Fatal')
    ]
    return render_template('search.html', level=level, user_name=session.get('user_name'), programs = programs, users = users, areas = areas, report_types=report_types, severity_levels=severity_levels)


@app.route('/search', methods=['POST'])
def search_reports_result():
    report_types = [
        ('bug', 'Coding Error'),
        ('issue', 'Design Issue'),
        ('suggestion', 'Suggestion'),
        ('documentation', 'Documentation'),
        ('hardware', 'Hardware'),
        ('query', 'Query')
    ]

    severity_levels = [
        ('Minor', 'Minor'),
        ('Serious', 'Serious'),
        ('Fatal', 'Fatal')
    ]

    conn = mysql.connector.connect(**db_config)
    program = request.form.get('program')
    report_type = request.form.get('report-type')
    severity = request.form.get('severity')
    functional_area = request.form.get('functional-area')
    assigned_to = request.form.get('assigned-to')
    status = request.form.get('status')
    priority = request.form.get('priority')
    resolution = request.form.get('resolution')
    reported_by = request.form.get('reported-by')
    reported_date = request.form.get('reported-date')
    resolved_by = request.form.get('resolved-by')
    
    print(reported_date)
    print(resolution)

    cursor = conn.cursor()

    query = "SELECT * FROM `bug-report` WHERE 1=1"
    params = ()

    if program:
        query += " AND program_id = %s"
        params = params + (program,)
        print(params)

    if report_type:
        query += " AND bug_type = %s"
        params = params + (report_type,)
        print(params)

    if severity:
        query += " AND severity = %s"
        params = params + (severity,)

    if functional_area:
        query += " AND area_id = %s"
        params = params + (functional_area,)

    if assigned_to:
            query += " AND assigned_user = %s"
            params = params + (assigned_to,)

    if status:
            query += " AND status = %s"
            params = params + (status,)
        
    if priority:
            query += " AND priority = %s"
            params = params + (priority,)

    if resolution:
            query += " AND resolution = %s"
            params = params + (resolution,)

    if reported_by:
            query += " AND reported_by = %s"
            params = params + (reported_by,)
        
    if reported_date:
            query += " AND date_created = %s"
            params = params + (reported_date,)

    if resolved_by:
            query += " AND reported_by = %s"
            params = params + (resolved_by,)

    print(params)
    cursor.execute(query, params ) 
   
    second_results = cursor.fetchall()
    print(second_results)
    cursor.close()
    
    return render_template('search_results.html', user_name=session.get('user_name'),second_results=second_results, report_types=report_types, severity_levels=severity_levels)

@app.route('/searchdashboard')
def search_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    level = session.get('level', 0)
    return render_template('searchdashboard.html', level=level, user_name=session.get('user_name'))

@app.route('/searchprg')
def search_program():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = mysql.connector.connect(**db_config)  
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT DISTINCT program_name FROM program ORDER BY program_name")
    programs = cursor.fetchall()
    return render_template('searchbyprog.html', programs=programs, user_name=session.get('user_name'))

@app.route('/searchprgresult')
def search_program_result():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    program_name = request.args.get('program', default=None)
    if program_name:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT p.program_id, fa.area_id, fa.name AS functional_area
            FROM `functional-area` fa
            JOIN program p ON fa.program_id = p.program_id
            WHERE p.program_name = %s
            ORDER BY fa.area_id
        """, (program_name,))
        areas = cursor.fetchall()

        cursor.close()
        conn.close()
    else:
        areas = [] 
    return render_template('searchprgresults.html', areas=areas, user_name=session.get('user_name'))

@app.route('/export_users_ascii')
def export_users_ascii():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users")
    result = cursor.fetchall()
    cursor.close()
    conn.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(result[0].keys())  # write headers
    cw.writerows([item.values() for item in result])  # write data rows

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=users.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/export_areas_ascii')
def export_areas_ascii():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM `functional-area`")
    result = cursor.fetchall()
    cursor.close()
    conn.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(result[0].keys())  # write headers
    cw.writerows([item.values() for item in result])  # write data rows

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=areas.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/export_users_xml')
def export_users_xml():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users")
    result = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convert query result to XML
    root = ET.Element("users")
    for item in result:
        user_elem = ET.SubElement(root, "user")
        for key, val in item.items():
            child = ET.SubElement(user_elem, key)
            child.text = str(val)

    xmlstr = ET.tostring(root, encoding='utf-8', method='xml')
    output = make_response(xmlstr)
    output.headers["Content-Disposition"] = "attachment; filename=users.xml"
    output.headers["Content-type"] = "text/xml"
    return output

@app.route('/export_areas_xml')
def export_areas_xml():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM `functional-area`")
    result = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convert query result to XML
    root = ET.Element("areas")
    for item in result:
        area_elem = ET.SubElement(root, "area")
        for key, val in item.items():
            child = ET.SubElement(area_elem, key)
            child.text = str(val)

    xmlstr = ET.tostring(root, encoding='utf-8', method='xml')
    output = make_response(xmlstr)
    output.headers["Content-Disposition"] = "attachment; filename=areas.xml"
    output.headers["Content-type"] = "text/xml"
    return output

if __name__ == '__main__':
    app.run(debug=True)
