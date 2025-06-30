from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from QR_generation_validation import generate_qr
import uuid
from database import save_user, check_password
import base64
from io import BytesIO
from PIL import Image

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

        #Save entered values so user doesn't need to retype
        values = {'name': name, 'email': email}

        #Validate fields
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


#Dashboard
@app.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

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
        last_qr_time=user['last_qr_time'],
        last_access=(f"{last_access['access_time']} / {last_access['room']}" if last_access else None),
        history=[f"{row['access_time']} / {row['room']}" for row in history] if history else []
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


#Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
