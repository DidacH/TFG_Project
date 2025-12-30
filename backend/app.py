from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, jsonify, send_file
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
import re
from functools import wraps

load_dotenv()  #Load environment variables from .env file

app = Flask(
    __name__,
)

CORS(app, supports_credentials=True) #Allow communication between frontend and backend

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

app.secret_key = os.getenv("SECRET_KEY")
ADMIN_REGISTRATION_KEY = os.getenv("ADMIN_KEY")
SIGNATURE_KEY = os.getenv("SIGNATURE_KEY").encode('utf-8')



#=================================================
# === AUTHENTICATION DECORATORS ===
#=================================================

#JWT Authentication Decorator
#This decorator checks for a valid JWT in the Authorization header
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        #jwt is passed in the request header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                #Split 'Bearer <token>'
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Bearer token malformed'}), 401

        #return 401 if token is not passed
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            #decoding the payload to fetch the stored details
            data = jwt.decode(token, app.secret_key, algorithms=["HS256"])
            #Pass user_id and role to the decorated function
            kwargs['user_id'] = data['user_id']
            kwargs['role'] = data['role']
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid!'}), 401
        except Exception as e:
             return jsonify({'message': f'Token error: {str(e)}'}), 401

        #returns the current logged in users context to the routes
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # 'role' és injectat per @token_required
        if 'role' not in kwargs or kwargs['role'] != 'Admin':
            return jsonify({'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


#=================================================
# === DATA FETCHING FUNCTIONS ===
#=================================================

def get_last_3_logs():
    conn = get_db_connection()
    cur = conn.cursor()
    # SOLUCIÓ: Seleccionem els camps de 'logs', incloent user_id
    cur.execute("""
        SELECT user_id, role, access_time, entry_allowed, area, reason
        FROM logs
        ORDER BY access_time DESC
        LIMIT 3
    """)
    logs = cur.fetchall()
    cur.close()
    conn.close()
    return logs

def get_all_logs():
    conn = get_db_connection()
    cur = conn.cursor()
    # SOLUCIÓ: Seleccionem només de la taula 'logs'
    cur.execute("""
        SELECT user_id, role, access_time, entry_allowed, area, reason
        FROM logs
        ORDER BY access_time DESC
    """)
    logs = cur.fetchall()
    cur.close()
    conn.close()
    return logs

def get_last_3_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT name, email, role, registered_at FROM users ORDER BY registered_at DESC LIMIT 3')
    users = cur.fetchall()
    cur.close()
    conn.close()
    return users

def get_all_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT name, email, role, registered_at FROM users ORDER BY registered_at DESC')
    users = cur.fetchall()
    cur.close()
    conn.close()
    return users


#=================================================
# === PUBLIC API ENDPOINTS ===
#=================================================

#Dynamic role fetching for registration
@app.route('/api/roles', methods=['GET'])
def api_get_roles():
    """Obtain all available roles from database"""
    try:
        roles = get_all_roles() #Fetch roles from database
        return jsonify(roles), 200
    except Exception as e:
        return jsonify({'message': f'Internal server error: {e}'}), 500
    

def validate_password(password):
    """Checks if the password meets the minimum security requirements."""
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number."
    if not re.search(r"[!@#$%^&*.]", password):
        return "Password must contain at least one special character (!@#$%^&*)."
    return None # No error

#User registration endpoint
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')
    admin_key = data.get('admin_key')

    if not all([name, email, password, role]):
        return jsonify({'message': 'All fields must be filled in'}), 400
    
    if role == 'Admin':
        if not admin_key:
            return jsonify({'message': 'Admin key is required for admin registration'}), 400
        if admin_key != ADMIN_REGISTRATION_KEY:
            return jsonify({'message': 'Invalid admin key'}), 403

    if get_user_by_email(email):
        return jsonify({'message': 'This email is already registered for another account'}), 409
    
    password_error = validate_password(password)
    if password_error:
        return jsonify({'message': password_error}), 400

    try:
        user_id = str(uuid.uuid4())
        qr_image, last_qr_time = generate_qr(user_id, SIGNATURE_KEY)
        registered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        save_user(user_id, name, email, password, role, qr_image, last_qr_time, registered_at)

        try:
            #Create JWT token
            payload = {
                'user_id': user_id,
                'role': role,
                'exp': datetime.now(timezone.utc) + timedelta(hours=1)  #Token expires in 1 hour
            }
            token = jwt.encode(payload, app.secret_key, algorithm="HS256")

            return jsonify({'token': token, 'role': role}), 201
        except Exception as e:
            return jsonify({'message': f'Error in token generation: {e}'}), 500
        
    except Exception as e:
        return jsonify({'message': f'Internal server error: {e}'}), 500


#User login endpoint
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

        return jsonify({'token': token, 'role': user['role']}), 200
    except Exception as e:
        return jsonify({'message': f'Error in token generation: {e}'}), 500
    

#=================================================
# === PROTECTED API ENDPOINTS (USER) ===
#=================================================

#API Endpoint for Dashboard Data
@app.route('/api/dashboard-data', methods=['GET'])
@token_required
def api_dashboard_data(user_id, role): #user_id and role are passed by the decorator
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        #Fetch user data
        cur.execute('SELECT name, email, role, qr_image, last_qr_time FROM users WHERE id = %s', (user_id,))
        user = cur.fetchone()

        if not user:
            cur.close()
            conn.close()
            return jsonify({'message': 'User not found'}), 404

        #Calculate remaining QR time
        last_qr_time = int(user['last_qr_time']) if user['last_qr_time'] else 0
        qr_lifetime = 30 #seconds - should match frontend constant
        now = int(time.time())
        remaining = qr_lifetime - (now - last_qr_time)
        if remaining < 0:
            remaining = 0 #Clamp at 0

        #Convert QR image blob to base64
        try:
            image = Image.open(BytesIO(user['qr_image']))
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as img_err:
             print(f"Error processing QR image: {img_err}") #Log error
             qr_base64 = None # Send null if image processing fails

        #Fetch last successful access
        cur.execute('''
            SELECT access_time, area FROM logs
            WHERE user_id = %s AND entry_allowed = 1
            ORDER BY access_time DESC LIMIT 1
        ''', (user_id,))
        last_access_record = cur.fetchone()
        last_access_str = f"{last_access_record['access_time']} / {last_access_record['area']}" if last_access_record else None

        #Fetch access history (successful accesses)
        cur.execute('''
            SELECT access_time, area FROM logs
            WHERE user_id = %s AND entry_allowed = 1
            ORDER BY access_time DESC
        ''', (user_id,))
        history_records = cur.fetchall()
        history_list = [f"{row['access_time']} / {row['area']}" for row in history_records] if history_records else []

        cur.close()
        conn.close()

        #Prepare response data
        response_data = {
            'name': user['name'],
            'email': user['email'],
            'role': user['role'],
            'qr_base64': qr_base64,
            'remaining': remaining,
            'last_access': last_access_str,
            'history': history_list
        }

        return jsonify(response_data), 200

    except Exception as e:
        #Log the exception e
        print(f"Error fetching dashboard data: {e}") #Print error for debugging
        #Close connection if it was opened and an error occurred
        if 'conn' in locals() and conn:
            cur.close()
            conn.close()
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500


#API Endpoint to refresh QR code
@app.route('/api/refresh-qr', methods=['GET'])
@token_required
def api_refresh_qr(user_id, role): #user_id and role are passed by the decorator
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        #Generate new QR
        new_qr_bytes, timestamp = generate_qr(user_id, SIGNATURE_KEY)

        #Update database
        cur.execute("UPDATE users SET qr_image = %s, last_qr_time = %s WHERE id = %s",
                   (new_qr_bytes, str(timestamp), user_id))
        conn.commit()

        cur.close()
        conn.close()

        #Convert new QR to base64 for response
        qr_base64 = base64.b64encode(new_qr_bytes).decode("utf-8")

        return jsonify({"qr_base64": qr_base64}), 200

    except Exception as e:
        #Log the exception e
        print(f"Error refreshing QR code: {e}") #Print error for debugging
        if 'conn' in locals() and conn:
           cur.close()
           conn.close()
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500


#=================================================
# === PROTECTED API ENDPOINTS (ADMIN) ===
#=================================================

#Endpoint for Admin Dashboard Data
@app.route('/api/admin/dashboard-data', methods=['GET'])
@token_required #Check for valid token (user is logged in)
@admin_required #Check if user is admin
def api_admin_dashboard(user_id, role):
    try:
        last_3_logs = get_last_3_logs()
        last_3_users = get_last_3_users()
        
        #Obtain admin name
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT name FROM users WHERE id = %s', (user_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        admin_name = user['name'] if user else "Admin"

        #Convert results (DictRow) to standard dicts for JSON serialization
        return jsonify({
            'admin_name': admin_name,
            'last_3_logs': [dict(log) for log in last_3_logs],
            'last_3_users': [dict(user) for user in last_3_users]
        }), 200

    except Exception as e:
        print(f"Error fetching admin dashboard data: {e}")
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500

#Endpoint to download logs table
@app.route('/api/admin/logs/download', methods=['GET'])
@token_required
@admin_required
def api_download_logs(user_id, role):
    try:
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
        
        mem = BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        output.close()

        return send_file(
            mem,
            mimetype='text/csv; charset=utf-8',
            as_attachment=True,
            download_name='logs.csv'
        )
    except Exception as e:
        print(f"Error downloading logs: {e}")
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500


#Endpoint to download users table
@app.route('/api/admin/users/download', methods=['GET'])
@token_required
@admin_required
def api_download_users(user_id, role):
    try:
        users = get_all_users()
        output = StringIO()
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['ID', 'Name', 'Email', 'Role', 'Registered At'])
        output.write('\ufeff')

        for user in users:
            writer.writerow([
                user['id'],
                user['name'],
                user['email'],
                user['role'],
                user['registered_at']
            ])

        output.seek(0)
        
        mem = BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        output.close()

        return send_file(
            mem,
            mimetype='text/csv; charset=utf-8',
            as_attachment=True,
            download_name='users.csv'
        )
    except Exception as e:
        print(f"Error downloading users: {e}")
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500
    
#Endpoint to render admin security dashboard    
@app.route('/api/admin/security')
def security_dashboard():
    """Renders main security page."""
    return render_template('security.html')

#Endpoint to get suspicious logs
@app.route('/api/admin/logs/suspicious')
def get_suspicious_logs():
    """Returns accepted logs but with a low score below the threshold (suspicious)."""
    threshold = float(os.getenv('ANOMALY_THRESHOLD', -0.15))
    conn = get_db_connection()
    cur = conn.cursor()
    # Query: Allowed entries with risk_score below threshold
    cur.execute("""
        SELECT id, user_id, role, area, access_time, risk_score, reason 
        FROM logs 
        WHERE entry_allowed = TRUE AND risk_score < %s
        ORDER BY access_time DESC LIMIT 50
    """, (threshold,))
    logs = cur.fetchall()
    cur.close()
    conn.close()
    
    # Convert to dicts for JSON response
    data = [{'id': r[0], 'user': r[1], 'role': r[2], 'area': r[3], 
             'time': str(r[4]), 'score': r[5], 'reason': r[6]} for r in logs]
    return jsonify(data)

#Endpoint to get denied logs
@app.route('/api/admin/logs/denied')
def get_denied_logs():
    """Returns DENIED logs (Hard Rules)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, user_id, role, area, access_time, reason 
        FROM logs 
        WHERE entry_allowed = FALSE
        ORDER BY access_time DESC LIMIT 50
    """)
    logs = cur.fetchall()
    cur.close()
    conn.close()
    
    data = [{'id': r[0], 'user': r[1], 'role': r[2], 'area': r[3], 
             'time': str(r[4]), 'reason': r[5]} for r in logs]
    return jsonify(data)

# Endpoint to manage access rules
@app.route('/api/admin/rules/access', methods=['GET', 'POST', 'DELETE'])
def manage_access_rules():
    """Manage access rules (Who can access where)."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'GET':
        cur.execute("SELECT id, role, allowed_area FROM access_rules")
        rows = cur.fetchall()
        data = [{'id': r[0], 'role': r[1], 'area': r[2]} for r in rows]
        conn.close()
        return jsonify(data)
    
    if request.method == 'POST':
        data = request.json
        cur.execute("INSERT INTO access_rules (role, allowed_area) VALUES (%s, %s)", 
                    (data['role'], data['area']))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})

    if request.method == 'DELETE':
        rule_id = request.args.get('id')
        cur.execute("DELETE FROM access_rules WHERE id = %s", (rule_id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'deleted'})

# Endpoint to manage alert rules
@app.route('/api/admin/rules/alerts', methods=['GET', 'POST', 'DELETE'])
def manage_alert_rules():
    """Manage alert rules (When to send email)."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'GET':
        cur.execute("SELECT id, event_type, role_filter, area_filter FROM alert_rules")
        rows = cur.fetchall()
        data = [{'id': r[0], 'event': r[1], 'role': r[2], 'area': r[3]} for r in rows]
        conn.close()
        return jsonify(data)

    if request.method == 'POST':
        data = request.json
        cur.execute("INSERT INTO alert_rules (event_type, role_filter, area_filter) VALUES (%s, %s, %s)", 
                    (data['event'], data['role'], data['area']))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})
        
    if request.method == 'DELETE':
        rule_id = request.args.get('id')
        cur.execute("DELETE FROM alert_rules WHERE id = %s", (rule_id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'deleted'})
    
# Endpoint for Security Dashboard Data
@app.route('/api/admin/security-data', methods=['GET'])
@token_required
@admin_required
def api_security_dashboard_data(user_id, role):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute('SELECT name FROM users WHERE id = %s', (user_id,))
        user_row = cur.fetchone()
        admin_name = user_row['name'] if user_row else "Admin"

        # Blockings during last 24h
        yesterday = datetime.now() - timedelta(days=1)
        cur.execute("""
            SELECT COUNT(*) as blocked 
            FROM logs 
            WHERE entry_allowed = FALSE AND access_time >= %s
        """, (yesterday,))
        blocked_24h = cur.fetchone()['blocked']

        # Active threats (Unique users denied access in last 24h)
        cur.execute("""
            SELECT count(distinct user_id) as threats 
            FROM logs 
            WHERE entry_allowed = FALSE AND access_time >= %s
        """, (yesterday,))
        active_threats = cur.fetchone()['threats']

        # Obtain recent incidents (denied accesses)
        cur.execute("""
            SELECT id, user_id, role, area, access_time, entry_allowed, reason 
            FROM logs 
            WHERE entry_allowed = FALSE 
            ORDER BY access_time DESC LIMIT 10
        """)
        raw_incidents = cur.fetchall()
        
        recent_incidents = []
        for log in raw_incidents:
            severity = 'high' if 'Ban' in log['reason'] or 'Security' in log['reason'] else 'medium'
            
            recent_incidents.append({
                'id': str(log['id']),
                'severity': severity,
                'type': log['reason'] or 'Access Denied',
                'source_ip': log['user_id'], # We use user_id as source identifier
                'timestamp': str(log['access_time']),
                'status': 'pending' # Default status
            })

        cur.close()
        conn.close()

        response_data = {
            'admin_name': admin_name,
            'stats': {
                'active_threats': active_threats,
                'blocked_ips_24h': blocked_24h,
                'system_health': 'Good'
            },
            'recent_incidents': recent_incidents
        }

        return jsonify(response_data), 200

    except Exception as e:
        print(f"Error fetching security data: {e}")
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500


#=================================================
# === APPLICATION START ===
#=================================================

if __name__ == "__main__":
    app.run(debug=True, port=5000)



# @app.route('/administrator')
# def administrator():
#     user_id = session.get('user_id')
#     if not user_id:
#         return redirect(url_for('login'))

#     last_3_logs = get_last_3_logs()
#     last_3_users = get_last_3_users()

#     conn = get_db_connection()
#     cur = conn.cursor()
#     cur.execute('SELECT name FROM users WHERE id = %s', (user_id,))
#     user = cur.fetchone()
#     cur.close()
#     conn.close()

#     name = user['name'] if user else "Administrator"

#     return render_template('administrator.html', name=name, last_3_logs=last_3_logs, last_3_users=last_3_users)


# @app.route('/download_logs')
# def download_logs():
#     logs = get_all_logs()
#     output = StringIO()
#     writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
#     writer.writerow(['User ID', 'Role', 'Area', 'Access Time', 'Entry Allowed?', 'Reason'])
#     output.write('\ufeff')

#     for log in logs:
#         writer.writerow([
#             log['user_id'] if log['user_id'] else 'N/A',
#             log['role'] if log['role'] else 'N/A',
#             log['area'] if log['area'] else 'N/A',
#             log['access_time'] if log['access_time'] else 'N/A',
#             log['entry_allowed'] if log['entry_allowed'] is not None else 'N/A',
#             log['reason'] if log['reason'] else 'N/A',
#         ])

#     output.seek(0)
#     return Response(
#         output.getvalue(),
#         mimetype='text/csv; charset=utf-8',
#         headers={'Content-Disposition': 'attachment; filename=logs.csv'}
#     )


# @app.route('/full_logs')
# def full_logs():
#     logs = get_all_logs()
#     return render_template('full_logs.html', logs=logs)

# @app.route('/full_users')
# def full_users():
#     users = get_all_users()
#     return render_template('full_users.html', users=users)


# @app.route('/download_users')
# def download_users():
#     users = get_all_users()

#     output = StringIO()
#     writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
#     writer.writerow(['ID', 'Name', 'Email', 'Role'])
#     output.write('\ufeff')

#     for user in users:
#         writer.writerow([
#             user['id'],
#             user['name'],
#             user['email'],
#             user['role'],
#         ])

#     output.seek(0)
#     return Response(
#         output.getvalue(),
#         mimetype='text/csv; charset=utf-8',
#         headers={'Content-Disposition': 'attachment; filename=users.csv'}
#     )


# @app.route('/edit-user-redirect', methods=['POST'])
# def edit_user_redirect():
#     email = request.form.get('edit_email', '').strip()
#     if not email:
#         return render_template('administrator.html',
#                             name=session.get('name', 'Administrator'),
#                             last_3_logs=get_last_3_logs(),
#                             last_3_users=get_last_3_users(),
#                             edit_redirect_error="No email provided",
#                             edit_email=email)
    
#     user = get_user_by_email(email)
#     if not user:
#         return render_template('administrator.html',
#                             name=session.get('name', 'Administrator'),
#                             last_3_logs=get_last_3_logs(),
#                             last_3_users=get_last_3_users(),
#                             edit_redirect_error="User not found",
#                             edit_email=email)

#     session['edit_user_email'] = email
#     return redirect(url_for('edit_user_form'))


# @app.route('/edit-user', methods=['GET', 'POST'])
# def edit_user_form():
#     email = session.get('edit_user_email')
#     if not email:
#         return redirect(url_for('administrator'))
    
#     user = get_user_by_email(email)
#     if not user:
#         return redirect(url_for('administrator'))

#     message = None
#     if request.method == 'POST':
#         if request.form.get('action') == 'apply':
#             new_name = request.form.get('name', '').strip()
#             new_email = request.form.get('email', '').strip()
#             new_role = request.form.get('role', '').strip()
            
#             if not all([new_name, new_email, new_role]):
#                 message = ("error", "All fields are required")
#             else:
#                 try:
#                     update_user(email, new_name, new_email, new_role)
#                     session['edit_user_email'] = new_email
#                     message = ("success", "User updated successfully")
#                 except Exception as e:
#                     message = ("error", f"Error updating user: {str(e)}")
    
#     user = get_user_by_email(session.get('edit_user_email'))
#     if not user:
#         return redirect(url_for('administrator'))
    
#     return render_template("edit_user.html", 
#                          user=user,
#                          message=message)



# @app.route('/delete-user', methods=['POST'])
# def delete_user():
#     email = request.form.get('delete_email', '').strip()
#     error = None
    
#     if not email:
#         error = "No email provided"
#     else:
#         user = get_user_by_email(email)
#         if not user:
#             error = "User not found"
#         else:
#             delete_user_by_email(email)
#             error = "User deleted successfully"
    
#     #Pass the error to administrator template
#     last_3_logs = get_last_3_logs()
#     last_3_users = get_last_3_users()
#     conn = get_db_connection()
#     cur = conn.cursor()
#     cur.execute('SELECT name FROM users WHERE id = %s', (session.get('user_id'),))
#     user = cur.fetchone()
#     cur.close()
#     conn.close()
    
#     return render_template('administrator.html', 
#                          name=user['name'] if user else "Administrator",
#                          last_3_logs=last_3_logs,
#                          last_3_users=last_3_users,
#                          delete_error=error,
#                          delete_email=email)


# #Logout
# @app.route('/logout')
# def logout():
#     session.clear()
#     return redirect(url_for('login'))