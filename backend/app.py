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
from security_analyzer import get_admin_emails
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_socketio import SocketIO, emit

load_dotenv()  # Load environment variables from .env file

app = Flask(
    __name__,
)

CORS(app, supports_credentials=True) # Allow communication between frontend and backend

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

app.secret_key = os.getenv("SECRET_KEY")
ADMIN_REGISTRATION_KEY = os.getenv("ADMIN_KEY")
SIGNATURE_KEY = os.getenv("SIGNATURE_KEY").encode('utf-8')

SMTP_EMAIL= os.getenv("SMTP_EMAIL")
SMTP_PASSWORD= os.getenv("SMTP_PASSWORD")

# Socket initialization
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Helper function to prevent response caching
def no_cache(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


#=================================================
# === AUTHENTICATION DECORATORS ===
#=================================================

# JWT Authentication Decorator
# This decorator checks for a valid JWT in the Authorization header
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # jwt is passed in the request header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                # Split 'Bearer <token>'
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Bearer token malformed'}), 401

        # return 401 if token is not passed
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            # decoding the payload to fetch the stored details
            data = jwt.decode(token, app.secret_key, algorithms=["HS256"])
            # Pass user_id and role to the decorated function
            kwargs['user_id'] = data['user_id']
            kwargs['role'] = data['role']
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid!'}), 401
        except Exception as e:
             return jsonify({'message': f'Token error: {str(e)}'}), 401

        # returns the current logged in users context to the routes
        return f(*args, **kwargs)

    return decorated

# Decorator to ensure the user has Admin privileges
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # 'role' is injected by @token_required
        if 'role' not in kwargs or kwargs['role'] != 'Admin':
            return jsonify({'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


#=================================================
# === DATA FETCHING FUNCTIONS ===
#=================================================

# Fetches the 3 most recent access logs
def get_last_3_logs():
    conn = get_db_connection()
    cur = conn.cursor()
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

# Fetches the complete history of access logs
def get_all_logs():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, role, access_time, entry_allowed, area, reason
        FROM logs
        ORDER BY access_time DESC
    """)
    logs = cur.fetchall()
    cur.close()
    conn.close()
    return logs

# Fetches the 3 most recently registered users
def get_last_3_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT name, email, role, registered_at FROM users ORDER BY registered_at DESC LIMIT 3')
    users = cur.fetchall()
    cur.close()
    conn.close()
    return users

# Fetches all registered users
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

# Dynamic role fetching for registration
@app.route('/api/roles', methods=['GET'])
def api_get_roles():
    """Obtain all available roles from database"""
    try:
        roles = get_all_roles() # Fetch roles from database
        return jsonify(roles), 200
    except Exception as e:
        return jsonify({'message': f'Internal server error: {e}'}), 500
    
# Checks if the password meets the minimum security requirements
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

# Handles user registration requests
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
            # Create JWT token
            payload = {
                'user_id': user_id,
                'role': role,
                'exp': datetime.now(timezone.utc) + timedelta(hours=1)  # Token expires in 1 hour
            }
            token = jwt.encode(payload, app.secret_key, algorithm="HS256")

            return jsonify({'token': token, 'role': role}), 201
        except Exception as e:
            return jsonify({'message': f'Error in token generation: {e}'}), 500
        
    except Exception as e:
        return jsonify({'message': f'Internal server error: {e}'}), 500


# Handles user login and token generation
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
        # Create JWT token
        payload = {
            'user_id': user['id'],
            'role': user['role'],
            'exp': datetime.now(timezone.utc) + timedelta(hours=1)  # Token expires in 1 hour
        }
        token = jwt.encode(payload, app.secret_key, algorithm="HS256")

        return jsonify({'token': token, 'role': user['role']}), 200
    except Exception as e:
        return jsonify({'message': f'Error in token generation: {e}'}), 500
    

#=================================================
# === PROTECTED API ENDPOINTS (USER) ===
#=================================================

# API Endpoint for Dashboard Data
# Retrieves dashboard data for a specific user
@app.route('/api/dashboard-data', methods=['GET'])
@token_required
def api_dashboard_data(user_id, role): # user_id and role are passed by the decorator
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Fetch user data
        cur.execute('SELECT name, email, role, qr_image, last_qr_time FROM users WHERE id = %s', (user_id,))
        user = cur.fetchone()

        if not user:
            cur.close()
            conn.close()
            return jsonify({'message': 'User not found'}), 404

        # Calculate remaining QR time
        last_qr_time = int(user['last_qr_time']) if user['last_qr_time'] else 0
        qr_lifetime = 30 # seconds - should match frontend constant
        now = int(time.time())
        remaining = qr_lifetime - (now - last_qr_time)
        if remaining < 0:
            remaining = 0 # Clamp at 0

        # Convert QR image blob to base64
        try:
            image = Image.open(BytesIO(user['qr_image']))
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as img_err:
             print(f"Error processing QR image: {img_err}") # Log error
             qr_base64 = None # Send null if image processing fails

        # Fetch last successful access
        cur.execute('''
            SELECT access_time, area FROM logs
            WHERE user_id = %s AND entry_allowed IS TRUE
            ORDER BY access_time DESC LIMIT 1
        ''', (user_id,))
        last_access_record = cur.fetchone()
        last_access_str = f"{last_access_record['access_time']} / {last_access_record['area']}" if last_access_record else None

        # Fetch access history (successful accesses)
        cur.execute('''
            SELECT access_time, area FROM logs
            WHERE user_id = %s AND entry_allowed IS TRUE
            ORDER BY access_time DESC
        ''', (user_id,))
        history_records = cur.fetchall()
        history_list = [f"{row['access_time']} / {row['area']}" for row in history_records] if history_records else []

        cur.close()
        conn.close()

        # Prepare response data
        response_data = {
            'id': user_id,
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
        # Log the exception e
        print(f"Error fetching dashboard data: {e}") # Print error for debugging
        # Close connection if it was opened and an error occurred
        if 'conn' in locals() and conn:
            cur.close()
            conn.close()
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500


# API Endpoint to refresh QR code
# Generates a new QR code for the user
@app.route('/api/refresh-qr', methods=['GET'])
@token_required
def api_refresh_qr(user_id, role): # user_id and role are passed by the decorator
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Generate new QR
        new_qr_bytes, timestamp = generate_qr(user_id, SIGNATURE_KEY)

        # Update database
        cur.execute("UPDATE users SET qr_image = %s, last_qr_time = %s WHERE id = %s",
                   (new_qr_bytes, str(timestamp), user_id))
        conn.commit()

        cur.close()
        conn.close()

        # Convert new QR to base64 for response
        qr_base64 = base64.b64encode(new_qr_bytes).decode("utf-8")

        return jsonify({"qr_base64": qr_base64}), 200

    except Exception as e:
        # Log the exception e
        print(f"Error refreshing QR code: {e}") # Print error for debugging
        if 'conn' in locals() and conn:
           cur.close()
           conn.close()
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500


#=================================================
# === PROTECTED API ENDPOINTS (ADMIN) ===
#=================================================

# Endpoint for Admin Dashboard Data
# Retrieves data for the main admin dashboard
@app.route('/api/admin/dashboard-data', methods=['GET'])
@token_required # Check for valid token (user is logged in)
@admin_required # Check if user is admin
def api_admin_dashboard(user_id, role):
    try:
        last_3_logs = get_last_3_logs()
        last_3_users = get_last_3_users()
        
        # Obtain admin name
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT name FROM users WHERE id = %s', (user_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        admin_name = user['name'] if user else "Admin"

        # Convert results (DictRow) to standard dicts for JSON serialization
        return jsonify({
            'admin_name': admin_name,
            'last_3_logs': [dict(log) for log in last_3_logs],
            'last_3_users': [dict(user) for user in last_3_users]
        }), 200

    except Exception as e:
        print(f"Error fetching admin dashboard data: {e}")
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500

# Endpoint to download logs table
# Generates a CSV file of all access logs
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


# Endpoint to download users table
# Generates a CSV file of all registered users
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
    
# Endpoint to render admin security dashboard
@app.route('/api/admin/security')
def security_dashboard():
    """Renders main security page."""
    return render_template('security.html')


# --- SECURITY ENDPOINTS ---

# Fetches logs flagged as suspicious based on risk score
@app.route('/api/admin/logs/suspicious')
def get_suspicious_logs():
    threshold = float(os.getenv('ANOMALY_THRESHOLD', -0.15))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, user_id, role, area, access_time, risk_score, reason 
        FROM logs 
        WHERE entry_allowed IS TRUE AND risk_score < %s
        ORDER BY access_time DESC LIMIT 50
    """, (threshold,))
    logs = cur.fetchall()
    cur.close()
    conn.close()
    
    data = [{'id': r[0], 'user': r[1], 'role': r[2], 'area': r[3], 
             'time': str(r[4]), 'score': r[5], 'reason': r[6]} for r in logs]
    return jsonify(data)

# Fetches logs where entry was denied
@app.route('/api/admin/logs/denied')
def get_denied_logs():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, user_id, role, area, access_time, reason 
        FROM logs 
        WHERE entry_allowed IS FALSE
        ORDER BY access_time DESC LIMIT 50
    """)
    logs = cur.fetchall()
    cur.close()
    conn.close()
    
    data = [{'id': r[0], 'user': r[1], 'role': r[2], 'area': r[3], 
             'time': str(r[4]), 'reason': r[5]} for r in logs]
    return jsonify(data)

# CRUD endpoint for managing access rules
@app.route('/api/admin/rules/access', methods=['GET', 'POST', 'DELETE'])
def manage_access_rules():
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

# CRUD endpoint for managing alert rules
@app.route('/api/admin/rules/alerts', methods=['GET', 'POST', 'DELETE'])
def manage_alert_rules():
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
    

# Critical Threshold: Above this risk score, system is "Critical" (default to 10)
CRITICAL_THRESHOLD = 10

# Configurable Threshold: How many low-severity errors constitute a threat? (default to 3)
REPETITION_THRESHOLD = 3 

# Toggle Threat Status
# Toggles or sets the threat status of a log entry
@app.route('/api/admin/log/<int:log_id>/toggle-threat', methods=['POST'])
@token_required
@admin_required
def toggle_threat_status(user_id, role, log_id):
    try:
        req_data = request.get_json()
        action = req_data.get('action') # 'resolve' or 'escalate'

        conn = get_db_connection()
        related_ids = find_cluster_ids_for_log(conn, log_id)
        
        if not related_ids:
            return jsonify({'message': 'Log not found'}), 404
            
        cur = conn.cursor()
        
        if action == 'resolve':
            # Mark as safe (Reviewed = True, Threat = False)
            new_threat = False
            new_review = True
        elif action == 'escalate':
            # Mark as threat (Reviewed = False, Threat = True)
            new_threat = True
            new_review = False
        else:
            # Fallback (Toggle based on current state)
            cur.execute("SELECT is_threat, is_reviewed FROM logs WHERE id = %s", (log_id,))
            log_state = cur.fetchone()
            if not log_state: return jsonify({'message': 'Log not found'}), 404
            
            # Extract values safely
            current_threat = log_state['is_threat'] if isinstance(log_state, dict) or hasattr(log_state, 'keys') else log_state[0]
            current_reviewed = log_state['is_reviewed'] if isinstance(log_state, dict) or hasattr(log_state, 'keys') else log_state[1]
            
            if current_threat and not current_reviewed: 
                new_threat = False
                new_review = True
            else:
                new_threat = True
                new_review = False

        format_strings = ','.join(['%s'] * len(related_ids))
        query = f"UPDATE logs SET is_threat = %s, is_reviewed = %s WHERE id IN ({format_strings})"
        
        params = [new_threat, new_review] + related_ids
        cur.execute(query, tuple(params))
        
        rows_affected = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'status': 'success', 
            'new_is_threat': new_threat,
            'updated_count': rows_affected
        }), 200
        
    except Exception as e:
        print(f"Error toggling threat: {e}")
        return jsonify({'message': f'Error toggling status: {str(e)}'}), 500

# Mark as Reviewed Endpoint
# Marks a specific log cluster as reviewed
@app.route('/api/admin/log/<int:log_id>/review', methods=['POST'])
@token_required
@admin_required
def toggle_review_status(user_id, role, log_id):
    try:
        conn = get_db_connection()
        related_ids = find_cluster_ids_for_log(conn, log_id)
        
        if not related_ids:
             related_ids = [str(log_id)]

        new_review = True
        
        cur = conn.cursor()
        format_strings = ','.join(['%s'] * len(related_ids))
        query = f"UPDATE logs SET is_reviewed = %s WHERE id IN ({format_strings})"
        
        params = [new_review] + related_ids
        cur.execute(query, tuple(params))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'status': 'success', 'new_is_reviewed': new_review}), 200
        
    except Exception as e:
        return jsonify({'message': f'Error updating review status: {str(e)}'}), 500


# Endpoint to toggle System Lockdown
# Toggles the global system lockdown state
@app.route('/api/admin/system-lockdown', methods=['POST'])
@token_required
@admin_required
def toggle_system_lockdown(user_id, role):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check current status in system_config table
        cur.execute("SELECT value_data FROM system_config WHERE key_name = 'system_lockdown'")
        row = cur.fetchone()
        
        # Determine new status (Toggle)
        current_status = False
        if row:
             val = row['value_data'] if isinstance(row, dict) or hasattr(row, 'keys') else row[0]
             current_status = val == 'true'

        new_status = not current_status
        new_status_str = 'true' if new_status else 'false'
        
        # Update or Insert based on existence
        if row:
            cur.execute("UPDATE system_config SET value_data = %s WHERE key_name = 'system_lockdown'", (new_status_str,))
        else:
            cur.execute("INSERT INTO system_config (key_name, value_data) VALUES ('system_lockdown', %s)", (new_status_str,))
            
        conn.commit()
        cur.close()
        conn.close()

        try:
            send_lockdown_email(new_status)
        except Exception:
            pass # Fail silently on email
        
        return jsonify({
            'status': 'success', 
            'lockdown_active': new_status
        }), 200
        
    except Exception as e:
        print(f"Error toggling lockdown: {e}")
        return jsonify({'message': f'Error toggling lockdown: {str(e)}'}), 500
    

SESSION_TIMEOUT_MINUTES = 10 # Time window to group logs of the same user
# Risk Score Map
RISK_SCORES = {
    'FORGED_QR': 10,     # Hack attempt / Security breach
    'MALFORMED_QR': 10,  # Fuzzing / Hack attempt
    'SYSTEM_LOCKDOWN': 10, # Serious incident when lockdown is active and access is attempted
    'UNKNOWN_USER': 5,   # Potential brute force or deleted user access
    'AREA_VIOLATION': 3, # Unauthorized internal access (Policy)
    'TIME_VIOLATION': 1, # Process issue
    'EXPIRED_QR': 1,     # Usability issue
    'AI_ANOMALY': 8,     # Suspicious behavior detected by AI
    'UNKNOWN': 1
}

    
# Main Security Dashboard Data Endpoint
# Aggregates complex security data and stats for the admin security dashboard
@app.route('/api/admin/security-data', methods=['GET'])
@token_required
@admin_required
def api_security_dashboard_data(user_id, role):
    try:
        conn = get_db_connection()
        
        # HOUSEKEEPING: Auto-review old safe logs
        auto_review_old_logs(conn)
        
        cur = conn.cursor()

        # Check Lockdown Status
        cur.execute("SELECT value_data FROM system_config WHERE key_name = 'system_lockdown'")
        row_lockdown = cur.fetchone()
        system_lockdown = row_lockdown['value_data'] == 'true' if row_lockdown else False

        # Admin Info
        cur.execute('SELECT name FROM users WHERE id = %s', (user_id,))
        user_row = cur.fetchone()
        admin_name = user_row['name'] if user_row else "Admin"

        # Time Threshold (24h)
        yesterday_obj = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday_obj.strftime("%Y-%m-%d %H:%M:%S")

        # Blocked Counters (Raw count of ALL blocked attempts in 24h)
        cur.execute("SELECT COUNT(*) as blocked FROM logs WHERE entry_allowed IS FALSE AND access_time >= %s", (yesterday_str,))
        row = cur.fetchone()
        blocked_24h = row['blocked'] if row else 0

        # --- SMART LOGIC STARTS HERE ---
        
        # Fetch logs for analysis
        # Get ALL logs from last 24h OR any older logs that are still threats and unreviewed
        # This ensures active threats don't disappear just because 24h passed.
        cur.execute("""
            SELECT id, user_id, role, area, access_time, entry_allowed, reason, error_code, is_threat, is_reviewed, is_anomaly 
            FROM logs 
            WHERE 
                (entry_allowed IS FALSE OR is_threat IS TRUE OR is_anomaly IS TRUE)
            AND 
                (access_time >= %s OR (is_threat IS TRUE AND is_reviewed IS FALSE) OR (is_anomaly IS TRUE AND is_reviewed IS FALSE))
            ORDER BY access_time DESC
        """, (yesterday_str,))
        
        all_logs = cur.fetchall()
        
        # --- TEMPORAL CLUSTERING ---
        
        incidents = []
        
        # We need to group logs that belong to the same "session" of errors.
        # Key for grouping: (user_id, error_code)
        # Constraint: Time difference < SESSION_TIMEOUT_MINUTES
        
        if all_logs:

            # Add AI flagged anomalies to the mix
            cleaned_logs = []
            for log in all_logs:
                d_log = dict(log)

                if d_log['is_anomaly'] and d_log['entry_allowed'] == 1:
                    d_log['error_code'] = 'AI_ANOMALY'
                    d_log['reason'] = 'Behavioral Anomaly Detected'
                
                # Fallback for None error codes
                if not d_log.get('error_code'):
                     d_log['error_code'] = 'UNKNOWN'
                     
                cleaned_logs.append(d_log)

            # Initialize the first cluster with the first log
            current_cluster = {
                'logs': [dict(cleaned_logs[0])],
                'user_id': cleaned_logs[0]['user_id'],
                'error_code': cleaned_logs[0]['error_code'],
                'last_time': cleaned_logs[0]['access_time'] # Most recent time in this cluster
            }
            
            # Iterate starting from the second log
            for i in range(1, len(cleaned_logs)):
                log = dict(cleaned_logs[i])
                
                # Check parsing of timestamp (DB drivers sometimes return str, sometimes datetime)
                log_time = log['access_time']
                if isinstance(log_time, str):
                    log_time = datetime.strptime(log_time, "%Y-%m-%d %H:%M:%S")
                
                prev_time = current_cluster['last_time']
                if isinstance(prev_time, str):
                    prev_time = datetime.strptime(prev_time, "%Y-%m-%d %H:%M:%S")

                # Calculate time difference
                time_diff = prev_time - log_time
                
                is_same_user = log['user_id'] == current_cluster['user_id']
                is_same_error = log['error_code'] == current_cluster['error_code']
                is_within_window = time_diff < timedelta(minutes=SESSION_TIMEOUT_MINUTES)
                
                if is_same_user and is_same_error and is_within_window:
                    # Add to current cluster
                    current_cluster['logs'].append(log)
                else:
                    # Seal the previous cluster and start a new one
                    incidents.append(current_cluster)
                    current_cluster = {
                        'logs': [log],
                        'user_id': log['user_id'],
                        'error_code': log['error_code'],
                        'last_time': log['access_time']
                    }
            
            # Append the final cluster
            incidents.append(current_cluster)

        # --- RISK ANALYSIS ON CLUSTERS ---
        
        total_risk_score = 0
        active_threats_set = set()
        recent_incidents_response = []
        
        for incident in incidents:
            logs_in_group = incident['logs']
            count = len(logs_in_group)
            representative_log = logs_in_group[0] # The most recent one
            
            u_id = representative_log['user_id']
            error_code = representative_log['error_code']
            reason = representative_log['reason']
            
            # Calculate Base Score
            base_score = RISK_SCORES.get(error_code, 1)
            
            # Calculate Severity based on repetition within the short time window
            severity = 'low'
            if base_score >= 10: 
                severity = 'high'
            elif base_score >= 3: 
                severity = 'medium'
            
            # Escalation logic: Brute force detection
            if count >= 3 and severity == 'low':
                severity = 'medium'
            if count >= 5:
                severity = 'high'

            # Determine Threat Status
            # Check if ANY log in this group is marked as unreviewed threat in DB
            # OR if our calculated severity is high
            
            db_threat_flag = any(l.get('is_threat') for l in logs_in_group)
            db_anomaly_flag = any(l.get('is_anomaly') for l in logs_in_group)
            all_reviewed = all(l.get('is_reviewed') for l in logs_in_group)
            
            is_active = False
            if not all_reviewed:
                if db_threat_flag or db_anomaly_flag or severity in ['high', 'medium']:
                    is_active = True
            
            if is_active:
                status = 'pending'
                active_threats_set.add(u_id)
                total_risk_score += base_score * count # Simple additive risk
            else:
                status = 'resolved'

            # Add to Response List
            # Only show if it's pending OR recent (< 24h)
            incident_time_str = str(incident['last_time'])
            is_recent = incident_time_str >= yesterday_str

            if (status == 'pending' or is_recent) and len(recent_incidents_response) < 20:
                 # Visual distinction for AI
                display_type = reason
                if error_code == 'AI_ANOMALY':
                    display_type = f"Possible Threat: {reason}"
                elif count > 1:
                    display_type = f"{reason} ({count} attempts in 10 min)"
                
                recent_incidents_response.append({
                    'id': representative_log['id'], # Use ID of the latest log in group
                    'severity': severity,
                    'type': display_type,
                    'description': error_code,
                    'source_id': u_id,
                    'timestamp': incident_time_str,
                    'status': status,
                    'is_ai': error_code == 'AI_ANOMALY',
                    'count': count,
                    'is_threat': db_threat_flag
                })

        # Sort incidents by time DESC before sending
        recent_incidents_response.sort(key=lambda x: x['timestamp'], reverse=True)
        # Limit to top 10 after sorting
        recent_incidents_response = recent_incidents_response[:10]

        
        return no_cache(jsonify({
            'admin_name': admin_name,
            'system_lockdown': system_lockdown,
            'stats': {
                'active_threats': len(active_threats_set),
                'blocked_attempts_24h': blocked_24h,
                'system_health': 'Critical' if total_risk_score > 50 else ('Warning' if total_risk_score > 0 else 'Good'),
                'risk_score': total_risk_score
            },
            'recent_incidents': recent_incidents_response
        })), 200

    except Exception as e:
        import traceback
        traceback.print_exc() # This will print the full error to your terminal
        print(f"CRITICAL ERROR in security_dashboard: {e}")
        return jsonify({'message': f'Internal Server Error: {str(e)}'}), 500
    

#=================================================
# === HELPER FUNCTIONS ===
#=================================================

def find_cluster_ids_for_log(conn, target_log_id):
    """
    Finds log IDs belonging to the same cluster.
    Different error types from same user in same window are now SPLIT.
    """
    cur = conn.cursor()
    
    # Fetch Target Log Details
    cur.execute("SELECT id, user_id, error_code, is_anomaly, access_time FROM logs WHERE id = %s", (target_log_id,))
    target = cur.fetchone()
    
    if not target:
        cur.close()
        return []

    # Handle Tuple vs Dict
    if isinstance(target, dict) or hasattr(target, 'keys'):
        t_id = target['id']
        t_user_id = target['user_id']
        t_error = target.get('error_code')
        t_anomaly = target.get('is_anomaly')
        t_time = target['access_time']
    else:
        t_id = target[0]
        t_user_id = target[1]
        t_error = target[2]
        t_anomaly = target[3]
        t_time = target[4]
    
    if isinstance(t_time, str):
        try: t_time = datetime.strptime(t_time.split('.')[0], "%Y-%m-%d %H:%M:%S")
        except: t_time = datetime.now()

    if t_anomaly:
        query = "SELECT id, user_id, error_code, is_anomaly, access_time FROM logs WHERE user_id = %s AND is_anomaly = TRUE ORDER BY access_time DESC"
        params = (t_user_id,)
    elif t_error is None:
        query = "SELECT id, user_id, error_code, is_anomaly, access_time FROM logs WHERE user_id = %s AND error_code IS NULL AND is_anomaly IS NOT TRUE ORDER BY access_time DESC"
        params = (t_user_id,)
    else:
        query = "SELECT id, user_id, error_code, is_anomaly, access_time FROM logs WHERE user_id = %s AND error_code = %s ORDER BY access_time DESC"
        params = (t_user_id, t_error)
        
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    
    target_id_str = str(t_id)
    if not rows: return [target_id_str]

    # Clustering Logic
    logs = []
    for r in rows:
        d = dict(r)
        if isinstance(d['access_time'], str):
             try: d['access_time'] = datetime.strptime(d['access_time'].split('.')[0], "%Y-%m-%d %H:%M:%S")
             except: d['access_time'] = datetime.now()
        logs.append(d)

    target_cluster_ids = []
    
    # Build clusters (Since we filtered by error type in SQL, we only check time now)
    if logs:
        current_cluster = [logs[0]]
        cluster_head_time = logs[0]['access_time']
        
        all_clusters = []
        
        for i in range(1, len(logs)):
            log = logs[i]
            time_diff = cluster_head_time - log['access_time']
            is_within = abs(time_diff.total_seconds()) < (SESSION_TIMEOUT_MINUTES * 60)
            
            if is_within:
                current_cluster.append(log)
            else:
                all_clusters.append(current_cluster)
                current_cluster = [log]
                cluster_head_time = log['access_time']
        all_clusters.append(current_cluster)

        for cluster in all_clusters:
            ids_in_cluster = [str(l['id']) for l in cluster]
            if target_id_str in ids_in_cluster:
                target_cluster_ids = ids_in_cluster
                break
    
    if not target_cluster_ids:
        target_cluster_ids = [target_id_str]

    return target_cluster_ids

# Helper to automatically review old non-threatening logs
def auto_review_old_logs(conn):
    """
    Automatically marks as 'reviewed' (resolved) logs that are:
    1. Older than 24h
    2. Marked as NOT a threat (is_threat = FALSE)
    3. Currently unreviewed
    """
    try:
        cur = conn.cursor()
        yesterday_obj = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday_obj.strftime("%Y-%m-%d %H:%M:%S")
        
        cur.execute("""
            UPDATE logs 
            SET is_reviewed = TRUE 
            WHERE access_time < %s 
            AND is_threat = FALSE 
            AND is_reviewed = FALSE
        """, (yesterday_str,))
        
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error in auto-review job: {e}")


def send_lockdown_email(active):
    """Sends an email notification about lockdown status change."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("Skipping email: Credentials not configured.")
        return

    admins = get_admin_emails()
    if not admins:
        return

    subject = "⚠️🔒 SYSTEM LOCKDOWN ALERT 🔒⚠️" if active else "✅ System Lockdown Lifted"
    
    if active:
        body = f"""
        WARNING: SYSTEM LOCKDOWN INITIATED.
        
        This is an automated alert. The system has been placed in LOCKDOWN mode by an administrator.
        
        - All non-admin access is currently BLOCKED.
        - Physical access control points will deny entry.
        
        Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        """
    else:
        body = f"""
        System Lockdown has been LIFTED.
        
        Normal access control rules are now back in effect.
        
        Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        """

    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = ", ".join(admins) # Send to all admins
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Send via SMTP
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, admins, msg.as_string())
        server.quit()
        print(f"Lockdown email sent to {len(admins)} admins.")
    except Exception as e:
        print(f"Failed to send email: {e}")

#=================================================
# === WEBSOCKET IMPLEMENTATION ===
#=================================================
@app.route('/api/internal/trigger-update', methods=['POST'])
def internal_trigger_update():
    """
    Called by QR_scanning.py when a new access event is logged.
    It emits a websocket event to all connected clients to trigger dashboard updates.
    """
    data = request.get_json() or {}
    update_type = data.get('type', 'new_log')
    user_id = data.get('user_id')
    
    # Send update to all clients connected to the dashboard
    socketio.emit('dashboard_update', {
        'type': update_type, 
        'timestamp': time.time(),
        'user_id': user_id,
        })
    
    # Send update to all clients connected to the security page if it's a threat
    if data.get('is_threat'):
        socketio.emit('security_update', {'type': 'new_threat', 'msg': 'Anomaly detected'})

    return jsonify({'status': 'ok'}), 200


#=================================================
# === APPLICATION START ===
#=================================================

if __name__ == "__main__":
    print("Starting Flask Server with WebSocket support...")
    socketio.run(app, debug=True, port=5000)