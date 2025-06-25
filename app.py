from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from QR_generation_validation import generate_qr
import uuid
from database import save_user, hash_password, check_password
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  #Replace with a random secure key!

DATABASE = 'users.db'

#Utility function
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def generate_unique_id():
    return str(uuid.uuid4())

#Home page
@app.route('/')
def home():
    return redirect(url_for('login'))

#Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()

        introduced_password = request.form['password'].strip()

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user:
            if check_password(introduced_password, user['password']):
                session['user_id'] = user['id']
                session['email'] = user['email']
                return redirect(url_for('dashboard'))
            else:
                flash('Incorrect password.')
        else:
            flash('Invalid email.')
    
    return render_template('login.html')

#Registration page
@app.route('/register', methods=['GET', 'POST'])
def register():
    errors = {}
    values = {}

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form['role']

        # Save entered values so user doesn't need to retype
        values = {'name': name, 'email': email}

        # Validate fields
        if not name:
            errors['name'] = "Name is required."
        if not email:
            errors['email'] = "Email is required."
        if not password:
            errors['password'] = "Password is required."

        if not errors:
            conn = get_db_connection()
            cursor = conn.execute('SELECT * FROM users WHERE email = ?', (email,))

            if cursor.fetchone():
                errors['email'] = "This email is already registered."
            else:
                #Generate unique user ID
                user_id = generate_unique_id()

                #Generate first QR code for the user and save timestamp
                qrimage, last_qr_time = generate_qr(user_id)

                save_user(user_id, name, email, password, role, qrimage, last_qr_time)

                return redirect(url_for('login'))

            conn.close()


    return render_template('register.html', errors=errors, values=values)


#Dashboard (protected)
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', email=session['email'])

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
