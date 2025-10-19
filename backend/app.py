from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, jsonify
from flask_cors import CORS
import jwt
from QR_generation_validation import generate_qr
import uuid
from database import save_user, check_password, get_db_connection, get_user_by_email, update_user, delete_user_by_email, get_all_roles
import base64
from io import BytesIO, StringIO
from PIL import Image
import csv
from datetime import datetime, timedelta, timezone
import time
from dotenv import load_dotenv
import os

load_dotenv()  #Load environment variables from .env file

app = Flask(
    __name__,
    template_folder='../frontend/templates',
    static_folder='../frontend/static'
    )

app.secret_key = os.getenv("SECRET_KEY")

CORS(app, supports_credentials=True) #Allow communication between frontend and backend
SIGNATURE_KEY = os.getenv("SIGNATURE_KEY").encode('utf-8')

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

ADMIN_REGISTRATION_KEY = os.getenv("ADMIN_KEY")
SIGNATURE_KEY = os.getenv("SIGNATURE_KEY").encode('utf-8')


@app.route('/api/roles', methods=['GET'])
def api_get_roles():
    """Obtain all available roles from database"""
    try:
        roles = get_all_roles()
        return jsonify(roles), 200
    except Exception as e:
        return jsonify({'message': f'Internal server error: {e}'}), 500

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')

    if not all([name, email, password, role]):
        return jsonify({'message': 'All fields must be filled in'}), 400

    if get_user_by_email(email):
        return jsonify({'message': 'This email is already registered for another account'}), 409

    try:
        user_id = str(uuid.uuid4())
        qr_image, last_qr_time = generate_qr(user_id, SIGNATURE_KEY)
        registered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        save_user(user_id, name, email, password, role, qr_image, last_qr_time, registered_at)
        
        return jsonify({'message': 'User successfully registered!'}), 201
    except Exception as e:
        return jsonify({'message': f'Internal server error: {e}'}), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'message': 'All fields must be filled in'}), 400

    user = get_user_by_email(email)

    if not user or not check_password(password, user['password']):
        return jsonify({'message': 'Invalid credentials'}), 401

    try:
        #Create JWT token
        payload = {
            'user_id': user['id'],
            'role': user['role'],
            'exp': datetime.now(timezone.utc) + timedelta(hours=1)  #Token expires in 1 hour
        }
        token = jwt.encode(payload, app.secret_key, algorithm="HS256")

        return jsonify({'token': token}), 200
    except Exception as e:
        return jsonify({'message': f'Error in token generation: {e}'}), 500








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
        cur = conn.cursor()
        
        cur.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cur.fetchone()
        cur.close()
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


#Registration page
@app.route('/register', methods=['GET', 'POST'])
def register():
    errors = {}
    values = {}
    available_roles = get_all_roles()

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
            cur = conn.cursor()
            
            cur.execute('SELECT * FROM users WHERE email = %s', (email,))
            
            if cur.fetchone():
                errors['email'] = "This email is already registered."
            else:
                user_id = generate_unique_id()
                qrimage, last_qr_time = generate_qr(user_id, SIGNATURE_KEY)
                registered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                save_user(user_id, name, email, password, role, qrimage, last_qr_time, registered_at)
                
                cur.close()
                conn.close()
                return redirect(url_for('login'))
            
            cur.close()
            conn.close()

    return render_template('register.html', errors=errors, values=values, available_roles=available_roles)


#Dashboard
@app.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')

    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cur.fetchone()

    if not user:
        cur.close()
        conn.close()
        return redirect(url_for('login'))

    last_qr_time = int(user['last_qr_time']) if user and user['last_qr_time'] else 0

    #Calculate how many seconds are left before QR expires
    qr_lifetime = 30  #seconds
    now = int(time.time())
    remaining = qr_lifetime - (now - last_qr_time)
    if remaining < 0:
        remaining = 0

    #Convert BLOB QR image to base64 string
    image = Image.open(BytesIO(user['qr_image']))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    #Fetch last successful access
    cur.execute('''
        SELECT access_time, area FROM logs 
        WHERE user_id = %s AND entry_allowed = 1 
        ORDER BY access_time DESC LIMIT 1
    ''', (user_id,))
    last_access = cur.fetchone()

    #Fetch all successful accesses
    cur.execute('''
        SELECT access_time, area FROM logs 
        WHERE user_id = %s AND entry_allowed = 1 
        ORDER BY access_time DESC
    ''', (user_id,))
    history = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'dashboard.html',
        name=user['name'],
        email=user['email'],
        role=user['role'],
        qr_base64=qr_base64,
        last_qr_time=last_qr_time,
        last_access=(f"{last_access['access_time']} / {last_access['area']}" if last_access else None),
        history=[f"{row['access_time']} / {row['area']}" for row in history] if history else [],
        remaining=remaining
    )

    
@app.route('/refresh_qr')
def refresh_qr():
    user_id = session.get('user_id')
    if not user_id:
        return {"error": "Unauthorized"}, 401

    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cur.fetchone()
    
    if not user:
        cur.close()
        conn.close()
        return {"error": "User not found"}, 404

    #Generate new QR
    new_qr, timestamp = generate_qr(user_id, SIGNATURE_KEY)

    cur.execute("UPDATE users SET qr_image = %s, last_qr_time = %s WHERE id = %s", 
               (new_qr, timestamp, user_id))
    conn.commit()
    
    #Return new QR as base64
    qr_base64 = base64.b64encode(new_qr).decode("utf-8")
    
    cur.close()
    conn.close()
    
    return {"qr_base64": qr_base64}

def get_last3_logs():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM logs ORDER BY access_time DESC LIMIT 3")
    logs = cur.fetchall()
    cur.close()
    conn.close()
    return logs

def get_all_logs():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM logs ORDER BY access_time DESC")
    logs = cur.fetchall()
    cur.close()
    conn.close()
    return logs

def get_last_3_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users ORDER BY registered_at DESC LIMIT 3')
    users = cur.fetchall()
    cur.close()
    conn.close()
    return users

def get_all_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users ORDER BY registered_at DESC')
    users = cur.fetchall()
    cur.close()
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
    cur = conn.cursor()
    cur.execute('SELECT name FROM users WHERE id = %s', (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    name = user['name'] if user else "Administrator"

    return render_template('administrator.html', name=name, last_3_logs=last_3_logs, last_3_users=last_3_users)


@app.route('/download_logs')
def download_logs():
    logs = get_all_logs()
    output = StringIO()
    writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['User ID', 'Role', 'Area', 'Access Time', 'Entry Allowed?', 'Reason'])
    output.write('\ufeff')

    for log in logs:
        writer.writerow([
            log['user_id'] if log['user_id'] else 'N/A',
            log['role'] if log['role'] else 'N/A',
            log['area'] if log['area'] else 'N/A',
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


@app.route('/edit-user-redirect', methods=['POST'])
def edit_user_redirect():
    email = request.form.get('edit_email', '').strip()
    if not email:
        return render_template('administrator.html',
                            name=session.get('name', 'Administrator'),
                            last_3_logs=get_last3_logs(),
                            last_3_users=get_last_3_users(),
                            edit_redirect_error="No email provided",
                            edit_email=email)
    
    user = get_user_by_email(email)
    if not user:
        return render_template('administrator.html',
                            name=session.get('name', 'Administrator'),
                            last_3_logs=get_last3_logs(),
                            last_3_users=get_last_3_users(),
                            edit_redirect_error="User not found",
                            edit_email=email)

    session['edit_user_email'] = email
    return redirect(url_for('edit_user_form'))


@app.route('/edit-user', methods=['GET', 'POST'])
def edit_user_form():
    email = session.get('edit_user_email')
    if not email:
        return redirect(url_for('administrator'))
    
    user = get_user_by_email(email)
    if not user:
        return redirect(url_for('administrator'))

    message = None
    if request.method == 'POST':
        if request.form.get('action') == 'apply':
            new_name = request.form.get('name', '').strip()
            new_email = request.form.get('email', '').strip()
            new_role = request.form.get('role', '').strip()
            
            if not all([new_name, new_email, new_role]):
                message = ("error", "All fields are required")
            else:
                try:
                    update_user(email, new_name, new_email, new_role)
                    session['edit_user_email'] = new_email
                    message = ("success", "User updated successfully")
                except Exception as e:
                    message = ("error", f"Error updating user: {str(e)}")
    
    user = get_user_by_email(session.get('edit_user_email'))
    if not user:
        return redirect(url_for('administrator'))
    
    return render_template("edit_user.html", 
                         user=user,
                         message=message)



@app.route('/delete-user', methods=['POST'])
def delete_user():
    email = request.form.get('delete_email', '').strip()
    error = None
    
    if not email:
        error = "No email provided"
    else:
        user = get_user_by_email(email)
        if not user:
            error = "User not found"
        else:
            delete_user_by_email(email)
            error = "User deleted successfully"
    
    #Pass the error to administrator template
    last_3_logs = get_last3_logs()
    last_3_users = get_last_3_users()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT name FROM users WHERE id = %s', (session.get('user_id'),))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    return render_template('administrator.html', 
                         name=user['name'] if user else "Administrator",
                         last_3_logs=last_3_logs,
                         last_3_users=last_3_users,
                         delete_error=error,
                         delete_email=email)


#Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))



if __name__ == "__main__":
    app.run(debug=True, port=5000)