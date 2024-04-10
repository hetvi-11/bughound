import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = 'secret'  # Replace with your secret key
app.debug = True
# Database configuration
db_config = {
    'host': 'localhost',
    'database': 'bughound',  # Replace with your database name
    'user': 'root'     # Replace with your username
}

@app.route('/', methods=['GET', 'POST'])
def login():
  
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Replace 'users' with your actual table name
        query = "SELECT * FROM employees WHERE username = %s AND password = %s"
        cursor.execute(query, (username, password))

        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            # login successful
            print("login successful")
            session['logged_in'] = True  # Set a session variable
            return redirect(url_for('home'))

        else:
            # Login failed
            flash('Invalid username or password')

    return render_template('login.html')

@app.route('/home')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)
