from flask import Flask, render_template, request, flash
import mysql.connector

app = Flask(__name__)
app.secret_key = 'secret'  # Replace with your secret key

# Database configuration
db_config = {
    'host': 'localhost',
    'database': 'bughound',  # Replace with your database name
    'user': 'root',     # Replace with your username
    'password': 'password'  # Replace with your password
}

@app.route('/login', methods=['GET', 'POST'])
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
            # Login successful
            return 'Login Successful'
        else:
            # Login failed
            flash('Invalid username or password')

    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)
