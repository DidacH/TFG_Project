from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
import sqlite3
from QR_generation_validation import generate_qr
import uuid
from database import save_user, check_password
import base64
from io import BytesIO, StringIO
from PIL import Image
import csv
from datetime import datetime
import time

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

                if user['role'] == 'Admin':
                    return redirect(url_for('administrator'))
                else:
                    return redirect(url_for('dashboard'))
            else:
                flash('Incorrect password.')
        else:
            flash('Invalid email.')
    
    return render_template('login.html')

ADMIN_REGISTRATION_KEY = 'admin'

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

        admin_key = request.form.get('admin_key', '')
        

        #Save entered values so user doesn't need to retype
        values = {'name': name, 'email': email, 'role': role, 'admin_key': admin_key}

        #Validate fields
        if not name:
            errors['name'] = "Name is required."
        if not email:
            errors['email'] = "Email is required."
        if not password:
            errors['password'] = "Password is required."

        #Admin key validation
        if values['role'] == 'Admin':
            if not values['admin_key']:
                errors['admin_key'] = "Admin key is required"
            elif values['admin_key'] != ADMIN_REGISTRATION_KEY:
                errors['admin_key'] = "Invalid admin registration key. Please contact the administrator."

        if not errors:
            conn = get_db_connection()
            cursor = conn.execute('SELECT * FROM users WHERE email = ?', (email,))

            if cursor.fetchone():
                errors['email'] = "This email is already registered."
            else:
                
                user_id = generate_unique_id()

                #Generate first QR code for the user and save timestamp
                qrimage, last_qr_time = generate_qr(user_id)

                registered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                save_user(user_id, name, email, password, role, qrimage, last_qr_time, registered_at)

                return redirect(url_for('login'))

            conn.close()


    return render_template('register.html', errors=errors, values=values)


#Dashboard
@app.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    last_qr_time = int(user['last_qr_time']) if user and user['last_qr_time'] else 0

    #Calculate how many seconds are left before QR expires
    qr_lifetime = 30  #seconds
    now = int(time.time())
    remaining = qr_lifetime - (now - last_qr_time)
    if remaining < 0:
        remaining = 0

    if not user:
        conn.close()
        return redirect(url_for('login'))

    #Convert BLOB QR image to base64 string
    image = Image.open(BytesIO(user['qr_image']))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    #Fetch last successful access
    last_access = conn.execute('''
        SELECT access_time, room FROM logs 
        WHERE user_id = ? AND entry_allowed = 1 
        ORDER BY access_time DESC LIMIT 1
    ''', (user_id,)).fetchone()

    #Fetch all successful accesses
    history = conn.execute('''
        SELECT access_time, room FROM logs 
        WHERE user_id = ? AND entry_allowed = 1 
        ORDER BY access_time DESC
    ''', (user_id,)).fetchall()

    conn.close()

    return render_template(
        'dashboard.html',
        name=user['name'],
        email=user['email'],
        role=user['role'],
        qr_base64=qr_base64,
        last_qr_time=last_qr_time,
        last_access=(f"{last_access['access_time']} / {last_access['room']}" if last_access else None),
        history=[f"{row['access_time']} / {row['room']}" for row in history] if history else [],
        remaining=remaining
    )

    
@app.route('/refresh_qr')
def refresh_qr():
    user_id = session.get('user_id')
    if not user_id:
        return {"error": "Unauthorized"}, 401

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        return {"error": "User not found"}, 404

    #Generate new QR
    new_qr, timestamp = generate_qr(user_id)

    #Update DB
    conn.execute("UPDATE users SET qr_image = ?, last_qr_time = ? WHERE id = ?", (new_qr, timestamp, user_id))
    conn.commit()
    conn.close()

    #Return new QR as base64
    qr_base64 = base64.b64encode(new_qr).decode("utf-8")
    return {"qr_base64": qr_base64}

def get_last3_logs():
    conn = get_db_connection()
    logs = conn.execute("SELECT * FROM logs ORDER BY access_time DESC LIMIT 3").fetchall()
    conn.close()
    return logs

def get_all_logs():
    conn = get_db_connection()
    logs = conn.execute("SELECT * FROM logs ORDER BY access_time DESC").fetchall()
    conn.close()
    return logs

def get_last_3_users():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users ORDER BY registered_at DESC LIMIT 3').fetchall()
    conn.close()
    return users


def get_all_users():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users ORDER BY registered_at DESC').fetchall()
    conn.close()
    return users


@app.route('/administrator')
def administrator():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    last_3_logs = get_last3_logs()
    last_3_users = get_last_3_users()

    conn = get_db_connection()
    user = conn.execute('SELECT name FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()

    name = user['name'] if user else "Administrator"

    return render_template('administrator.html', name=name, last_3_logs=last_3_logs, last_3_users=last_3_users)


@app.route('/download_logs')
def download_logs():
    logs = get_all_logs()
    output = StringIO()
    writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['User ID', 'Email', 'Role', 'Room', 'Access Time', 'Entry Allowed?', 'Reason'])
    output.write('\ufeff')

    for log in logs:
        writer.writerow([
            log['user_id'] if log['user_id'] else 'N/A',
            log['email'] if log['email'] else 'N/A',
            log['role'] if log['role'] else 'N/A',
            log['room'] if log['room'] else 'N/A',
            log['access_time'] if log['access_time'] else 'N/A',
            log['entry_allowed'] if log['entry_allowed'] is not None else 'N/A',
            log['reason'] if log['reason'] else 'N/A',
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=logs.csv'}
    )


@app.route('/full_logs')
def full_logs():
    logs = get_all_logs()
    return render_template('full_logs.html', logs=logs)


@app.route('/full_users')
def full_users():
    users = get_all_users()
    return render_template('full_users.html', users=users)


@app.route('/download_users')
def download_users():
    users = get_all_users()

    output = StringIO()
    writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['ID', 'Name', 'Email', 'Role'])
    output.write('\ufeff')

    for user in users:
        writer.writerow([
            user['id'],
            user['name'],
            user['email'],
            user['role'],
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=users.csv'}
    )


#Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
