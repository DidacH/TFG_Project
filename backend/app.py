import gevent.monkey
gevent.monkey.patch_all()

from dotenv import load_dotenv
import os
load_dotenv() 

from flask import Flask, render_template, request, jsonify, send_file, Response
from flask_cors import CORS
import jwt
from QR_generation_validation import generate_qr, verify_qr
from security_analyzer import predict_anomaly, send_anomaly_alert, load_or_train_model, send_access_denied_alert, get_admin_emails, start_retraining_scheduler, get_anomaly_threshold
import uuid
from database import save_user, check_password, get_db_connection, get_user_by_email, get_all_roles, initialize_database
import base64
from io import StringIO, BytesIO
from PIL import Image
import csv
from datetime import datetime, timedelta, timezone
import time
import re
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_socketio import SocketIO
import pytz
import json

# =============================================================================
# === APPLICATION CONFIGURATION & INITIALIZATION ===
# =============================================================================

app = Flask(__name__)

# Configure CORS to allow frontend communication with credentials
CORS(app, supports_credentials=True) 

# Security configurations for session cookies
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

# Load environment keys
app.secret_key = os.getenv("SECRET_KEY")
ADMIN_REGISTRATION_KEY = os.getenv("ADMIN_KEY")
SIGNATURE_KEY = os.getenv("SIGNATURE_KEY").encode('utf-8')

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# Initialize WebSocket support (gevent async mode)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

def no_cache(response):
    """
    Appends strict no-cache headers to a Flask response to prevent 
    stale data rendering on the client side.
    """
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# =============================================================================
# === AUTHENTICATION DECORATORS ===
# =============================================================================

def token_required(f):
    """
    Decorator to ensure a valid JWT token is present in the request headers.
    Injects user_id and role into the protected endpoint parameters.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Bearer token malformed'}), 401

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, app.secret_key, algorithms=["HS256"])
            kwargs['user_id'] = data['user_id']
            kwargs['role'] = data['role']
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid!'}), 401
        except Exception as e:
             return jsonify({'message': f'Token error: {str(e)}'}), 401

        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """
    Decorator to enforce Admin-only access.
    Must be chained after @token_required.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'role' not in kwargs or kwargs['role'] != 'Admin':
            return jsonify({'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

# =============================================================================
# === DATA FETCHING HELPER FUNCTIONS ===
# =============================================================================

def get_last_3_logs():
    """Retrieves the 3 most recent access logs for the dashboard preview."""
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


def get_all_logs():
    """Retrieves all standard access logs ordered by recency."""
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


def get_last_3_users():
    """Retrieves the 3 most recently registered users for the dashboard preview."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT name, email, role, registered_at FROM users ORDER BY registered_at DESC LIMIT 3')
    users = cur.fetchall()
    cur.close()
    conn.close()
    return users


def get_all_users():
    """Retrieves all registered users ordered by registration date."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT name, email, role, registered_at FROM users ORDER BY registered_at DESC')
    users = cur.fetchall()
    cur.close()
    conn.close()
    return users

# =============================================================================
# === PUBLIC API ENDPOINTS ===
# =============================================================================

@app.route('/api/roles', methods=['GET'])
def api_get_roles():
    """Returns a list of all available roles dynamically fetched from the database."""
    try:
        roles = get_all_roles()
        return jsonify(roles), 200
    except Exception as e:
        return jsonify({'message': f'Internal server error: {e}'}), 500
    

def validate_password(password):
    """
    Validates password strength requirements via RegEx.
    Returns None if valid, or a descriptive string if invalid.
    """
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
    return None


@app.route('/api/register', methods=['POST'])
def api_register():
    """
    Handles new user registration. Validates credentials, checks admin keys,
    generates the initial dynamic QR code, and issues a JWT token.
    """
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
        spain_tz = pytz.timezone('Europe/Madrid')
        registered_at = datetime.now(spain_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        save_user(user_id, name, email, password, role, qr_image, last_qr_time, registered_at)

        try:
            payload = {
                'user_id': user_id,
                'role': role,
                'exp': datetime.now(timezone.utc) + timedelta(hours=1)
            }
            token = jwt.encode(payload, app.secret_key, algorithm="HS256")

            return jsonify({'token': token, 'role': role}), 201
        except Exception as e:
            return jsonify({'message': f'Error in token generation: {e}'}), 500
        
    except Exception as e:
        return jsonify({'message': f'Internal server error: {e}'}), 500


@app.route('/api/login', methods=['POST'])
def api_login():
    """
    Authenticates existing users and issues a new JWT token for session management.
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'message': 'All fields must be filled in'}), 400

    user = get_user_by_email(email)

    if not user or not check_password(password, user['password']):
        return jsonify({'message': 'Invalid credentials'}), 401

    try:
        payload = {
            'user_id': user['id'],
            'role': user['role'],
            'exp': datetime.now(timezone.utc) + timedelta(hours=1)
        }
        token = jwt.encode(payload, app.secret_key, algorithm="HS256")

        return jsonify({'token': token, 'role': user['role']}), 200
    except Exception as e:
        return jsonify({'message': f'Error in token generation: {e}'}), 500
    
# =============================================================================
# === EDGE DEVICE (HARDWARE) ENDPOINTS ===
# =============================================================================

@app.route('/api/access/scan', methods=['POST'])
def api_access_scan():
    """
    Endpoint intended for IoT Edge Devices (e.g., Raspberry Pi scanners).
    Validates incoming QR code payloads and triggers background AI assessment.
    """
    data = request.get_json()
    
    if not data or 'qr_data' not in data or 'area' not in data:
        return jsonify({"granted": False, "reason": "Missing data in payload"}), 400

    qr_content = data['qr_data']
    target_area = data['area']

    validation_result = verify_qr(qr_content, SIGNATURE_KEY, target_area)

    response_data = {
        "granted": validation_result['valid'],
        "reason": validation_result['reason'],
        "user_id": validation_result['user_id'],
        "role": validation_result['role']
    }

    # Delegate the database writing and AI analysis to a background task
    socketio.start_background_task(background_access_processing, validation_result, target_area)

    return jsonify(response_data), 200
    
# =============================================================================
# === PROTECTED API ENDPOINTS (USER LEVEL) ===
# =============================================================================

def get_user_profile_data(target_user_id):
    """
    Helper function to aggregate user profile details and their 
    historical access logs. Limited to 500 logs to optimize performance.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, name, email, role, registered_at, is_blocked 
            FROM users WHERE id = %s
        """, (target_user_id,))
        user_data = cur.fetchone()
        
        if not user_data:
            return jsonify({'message': 'User not found'}), 404
            
        cur.execute("""
            SELECT id, user_id, role, area, access_time, entry_allowed, reason, error_code, risk_score, is_anomaly, is_threat 
            FROM logs 
            WHERE user_id = %s
            ORDER BY access_time DESC
            LIMIT 500
        """, (target_user_id,))
        logs = cur.fetchall()
        
        cur.close()
        conn.close()
        
        logs_list = []
        for l in logs:
            logs_list.append({
                'id': l['id'],
                'user_id': l['user_id'],
                'role': l['role'],
                'area': l['area'],
                'access_time': str(l['access_time']),
                'entry_allowed': l['entry_allowed'],
                'reason': l['reason'],
                'error_code': l['error_code'],
                'risk_score': l['risk_score'],
                'is_anomaly': l['is_anomaly'],
                'is_threat': l['is_threat']
            })
            
        profile_data = {
            'id': user_data['id'],
            'name': user_data['name'],
            'email': user_data['email'],
            'role': user_data['role'],
            'registered_at': str(user_data['registered_at']),
            'is_blocked': user_data['is_blocked'],
            'logs': logs_list
        }
        
        return jsonify(profile_data), 200
        
    except Exception as e:
        print(f"Error fetching user profile: {e}")
        return jsonify({'message': f'Error fetching profile: {str(e)}'}), 500


@app.route('/api/profile', methods=['GET'])
@token_required
def api_get_my_profile(user_id, role):
    """Returns the profile data exclusively for the requesting user."""
    return get_user_profile_data(user_id)


@app.route('/api/dashboard-data', methods=['GET'])
@token_required
def api_dashboard_data(user_id, role):
    """
    Aggregates required data for the User Dashboard, including their current
    QR code payload and the remaining time until its expiration.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute('SELECT name, email, role, qr_image, last_qr_time FROM users WHERE id = %s', (user_id,))
        user = cur.fetchone()

        if not user:
            cur.close()
            conn.close()
            return jsonify({'message': 'User not found'}), 404

        last_qr_time = int(user['last_qr_time']) if user['last_qr_time'] else 0
        qr_lifetime = 30
        now = int(time.time())
        remaining = qr_lifetime - (now - last_qr_time)
        if remaining < 0:
            remaining = 0

        # Process binary image into Base64 for web rendering
        try:
            image = Image.open(BytesIO(user['qr_image']))
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception:
            qr_base64 = None

        cur.execute('''
            SELECT access_time, area FROM logs
            WHERE user_id = %s AND entry_allowed IS TRUE
            ORDER BY access_time DESC LIMIT 1
        ''', (user_id,))
        last_access_record = cur.fetchone()
        last_access_str = f"{last_access_record['access_time']} / {last_access_record['area']}" if last_access_record else None

        cur.execute('''
            SELECT access_time, area FROM logs
            WHERE user_id = %s AND entry_allowed IS TRUE
            ORDER BY access_time DESC
        ''', (user_id,))
        history_records = cur.fetchall()
        history_list = [f"{row['access_time']} / {row['area']}" for row in history_records] if history_records else []

        cur.close()
        conn.close()

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
        if 'conn' in locals() and conn:
            cur.close()
            conn.close()
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500


@app.route('/api/refresh-qr', methods=['GET'])
@token_required
def api_refresh_qr(user_id, role):
    """
    Generates a new signed QR code payload, updates the database timestamp,
    and returns the Base64 representation to the client.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        new_qr_bytes, timestamp = generate_qr(user_id, SIGNATURE_KEY)

        cur.execute("UPDATE users SET qr_image = %s, last_qr_time = %s WHERE id = %s",
                   (new_qr_bytes, str(timestamp), user_id))
        conn.commit()

        cur.close()
        conn.close()

        qr_base64 = base64.b64encode(new_qr_bytes).decode("utf-8")

        return jsonify({"qr_base64": qr_base64}), 200

    except Exception as e:
        if 'conn' in locals() and conn:
           cur.close()
           conn.close()
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500

# =============================================================================
# === PROTECTED API ENDPOINTS (ADMIN LEVEL) ===
# =============================================================================

@app.route('/api/admin/user/<target_user_id>', methods=['GET'])
@token_required
@admin_required
def api_get_user_profile(user_id, role, target_user_id):
    """Allows administrators to inspect the full profile and logs of any user."""
    return get_user_profile_data(target_user_id)


@app.route('/api/admin/dashboard-data', methods=['GET'])
@token_required
@admin_required
def api_admin_dashboard(user_id, role):
    """Fetches high-level aggregated data for the main Admin Portal."""
    try:
        last_3_logs = get_last_3_logs()
        last_3_users = get_last_3_users()
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT name FROM users WHERE id = %s', (user_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        admin_name = user['name'] if user else "Admin"

        return jsonify({
            'admin_name': admin_name,
            'last_3_logs': [dict(log) for log in last_3_logs],
            'last_3_users': [dict(user) for user in last_3_users]
        }), 200

    except Exception as e:
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500


@app.route('/api/admin/users', methods=['GET'])
@token_required
@admin_required
def api_get_users_list(user_id, role):
    """Returns a lightweight list of all users for the Management Data Grid."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT id, name, email, role, registered_at, is_blocked 
            FROM users 
            ORDER BY registered_at DESC
        ''')
        users = cur.fetchall()
        cur.close()
        conn.close()

        users_list = []
        for u in users:
            users_list.append({
                'id': u['id'] if isinstance(u, dict) else u[0],
                'name': u['name'] if isinstance(u, dict) else u[1],
                'email': u['email'] if isinstance(u, dict) else u[2],
                'role': u['role'] if isinstance(u, dict) else u[3],
                'registered_at': u['registered_at'] if isinstance(u, dict) else u[4],
                'is_blocked': u['is_blocked'] if isinstance(u, dict) else u[5]
            })

        return jsonify(users_list), 200
    except Exception as e:
        return jsonify({'message': f'Error fetching users: {str(e)}'}), 500


@app.route('/api/admin/<export_type>/download', methods=['GET'])
@token_required
@admin_required
def download_csv(user_id, role, export_type):
    """
    Generates and returns a CSV file containing either user data or system logs.
    Utilizes UTF-8 encoding with a BOM for native Excel compatibility.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        output = StringIO()
        output.write('\ufeff')
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        if export_type == 'users':
            cur.execute("SELECT id, name, email, role, registered_at, is_blocked FROM users ORDER BY registered_at DESC")
            users = cur.fetchall()
            writer.writerow(['ID', 'Name', 'Email', 'Role', 'Registered At', 'Is Blocked'])
            
            for u in users:
                row = list(u.values()) if hasattr(u, 'values') else list(u)
                writer.writerow(row)
            filename = "users.csv"
            
        elif export_type == 'logs':
            cur.execute("SELECT user_id, role, area, access_time, entry_allowed, reason, risk_score, is_anomaly, is_threat FROM logs ORDER BY access_time DESC")
            logs = cur.fetchall()
            writer.writerow(['User ID', 'Role', 'Area', 'Time', 'Allowed', 'Reason', 'Risk Score', 'Is Anomaly', 'Is Threat'])
            
            for l in logs:
                row = list(l.values()) if hasattr(l, 'values') else list(l)
                writer.writerow(row)
            filename = "logs.csv"
            
        else:
            cur.close()
            conn.close()
            return jsonify({"message": "Invalid export type"}), 400
            
        cur.close()
        conn.close()
        
        response = Response(output.getvalue(), mimetype='text/csv; charset=utf-8')
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response
        
    except Exception as e:
        return jsonify({'message': f"Internal server error: {str(e)}"}), 500

# =============================================================================
# === FIREWALL & POLICIES ENDPOINTS ===
# =============================================================================

@app.route('/api/admin/rules/access', methods=['GET', 'POST', 'PUT', 'DELETE'])
@token_required
@admin_required
def manage_access_rules(user_id, role):
    """CRUD operations for Role-Based Access Control (RBAC) rules."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'GET':
        cur.execute("SELECT id, role, allowed_area, allowed_days, start_time, end_time, is_active FROM access_rules ORDER BY role, allowed_area")
        rows = cur.fetchall()
        data = []
        for r in rows:
            data.append({
                'id': r['id'],
                'role': r['role'],
                'area': r['allowed_area'],
                'days': r['allowed_days'],
                'start_time': str(r['start_time']),
                'end_time': str(r['end_time']),
                'active': r['is_active']
            })
        cur.close()
        conn.close()
        return jsonify(data)
    
    if request.method == 'POST':
        data = request.json
        days = data.get('days', '0,1,2,3,4,5,6')
        start_time = data.get('start_time', '00:00:00')
        end_time = data.get('end_time', '23:59:59')
        is_active = data.get('active', True)
        
        cur.execute("""
            INSERT INTO access_rules (role, allowed_area, allowed_days, start_time, end_time, is_active) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (data['role'], data['area'], days, start_time, end_time, is_active))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'status': 'success'})

    if request.method == 'PUT':
        data = request.json
        rule_id = data.get('id')
        is_active = data.get('active')
        cur.execute("UPDATE access_rules SET is_active = %s WHERE id = %s", (is_active, rule_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'status': 'success'})

    if request.method == 'DELETE':
        rule_id = request.args.get('id')
        cur.execute("DELETE FROM access_rules WHERE id = %s", (rule_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'status': 'deleted'})


@app.route('/api/admin/config', methods=['GET', 'POST'])
@token_required
@admin_required
def manage_system_config(user_id, role):
    """Reads and updates global system configurations (e.g., AI Threshold)."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'GET':
        cur.execute("SELECT key_name, value_data FROM system_config")
        rows = cur.fetchall()
        data = {r['key_name']: r['value_data'] for r in rows}
        cur.close()
        conn.close()
        return jsonify(data)
        
    if request.method == 'POST':
        data = request.json
        for key, value in data.items():
            cur.execute("""
                INSERT INTO system_config (key_name, value_data) 
                VALUES (%s, %s) 
                ON CONFLICT (key_name) 
                DO UPDATE SET value_data = EXCLUDED.value_data
            """, (key, str(value)))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'status': 'success'})


@app.route('/api/admin/rules/alerts', methods=['GET', 'POST', 'DELETE'])
@token_required
@admin_required
def manage_alert_rules(user_id, role):
    """CRUD operations for targeted email alert triggers."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'GET':
        cur.execute("SELECT id, event_type, role_filter, area_filter FROM alert_rules")
        rows = cur.fetchall()
        data = [{'id': r[0], 'event': r[1], 'role': r[2], 'area': r[3]} for r in rows]
        cur.close()
        conn.close()
        return jsonify(data)

    if request.method == 'POST':
        data = request.json
        cur.execute("INSERT INTO alert_rules (event_type, role_filter, area_filter) VALUES (%s, %s, %s)", 
                    (data['event'], data['role'], data['area']))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'status': 'success'})
        
    if request.method == 'DELETE':
        rule_id = request.args.get('id')
        cur.execute("DELETE FROM alert_rules WHERE id = %s", (rule_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'status': 'deleted'})

# =============================================================================
# === INCIDENT MANAGEMENT ACTIONS ===
# =============================================================================

@app.route('/api/admin/log/<int:log_id>/toggle-threat', methods=['POST'])
@token_required
@admin_required
def toggle_threat_status(user_id, role, log_id):
    """
    Escalates or resolves a security incident. Clusters related repetitive 
    logs and applies the status change to the entire incident cluster simultaneously.
    """
    try:
        req_data = request.get_json()
        action = req_data.get('action')

        conn = get_db_connection()
        related_ids = find_cluster_ids_for_log(conn, log_id)
        
        if not related_ids:
            return jsonify({'message': 'Log not found'}), 404
            
        cur = conn.cursor()
        
        if action == 'resolve':
            new_threat = False
            new_review = True
        elif action == 'escalate':
            new_threat = True
            new_review = False
        else:
            cur.execute("SELECT is_threat, is_reviewed FROM logs WHERE id = %s", (log_id,))
            log_state = cur.fetchone()
            if not log_state: return jsonify({'message': 'Log not found'}), 404
            
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
        return jsonify({'message': f'Error toggling status: {str(e)}'}), 500


@app.route('/api/admin/log/<int:log_id>/review', methods=['POST'])
@token_required
@admin_required
def toggle_review_status(user_id, role, log_id):
    """
    Marks a clustered security incident as reviewed/acknowledged without 
    necessarily changing its threat status.
    """
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


@app.route('/api/admin/user/<target_user_id>/toggle-block', methods=['POST'])
@token_required
@admin_required
def api_toggle_user_block(user_id, role, target_user_id):
    """Inverts the physical access restriction (block) for a specific user account."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT is_blocked, name FROM users WHERE id = %s", (target_user_id,))
        target_user = cur.fetchone()
        
        if not target_user:
            cur.close()
            conn.close()
            return jsonify({'message': 'User not found'}), 404
            
        current_status = target_user['is_blocked'] if isinstance(target_user, dict) or hasattr(target_user, 'keys') else target_user[0]
        user_name = target_user['name'] if isinstance(target_user, dict) or hasattr(target_user, 'keys') else target_user[1]
        
        new_status = not current_status
        
        cur.execute("UPDATE users SET is_blocked = %s WHERE id = %s", (new_status, target_user_id))
        conn.commit()
        cur.close()
        conn.close()
        
        action_str = "blocked" if new_status else "unblocked"
        
        return jsonify({
            'status': 'success', 
            'message': f'User {user_name} has been {action_str}.',
            'new_is_blocked': new_status
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error toggling user block status: {str(e)}'}), 500


@app.route('/api/admin/system-lockdown', methods=['POST'])
@token_required
@admin_required
def toggle_system_lockdown(user_id, role):
    """
    Activates or deactivates the Global System Lockdown mode.
    Triggers critical notification emails to all administrators.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT value_data FROM system_config WHERE key_name = 'system_lockdown'")
        row = cur.fetchone()
        
        current_status = False
        if row:
             val = row['value_data'] if isinstance(row, dict) or hasattr(row, 'keys') else row[0]
             current_status = val == 'true'

        new_status = not current_status
        new_status_str = 'true' if new_status else 'false'
        
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
            pass 
        
        return jsonify({
            'status': 'success', 
            'lockdown_active': new_status
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error toggling lockdown: {str(e)}'}), 500
    
# =============================================================================
# === SECURITY CENTER & LOG AGGREGATION ===
# =============================================================================

try:
    SESSION_TIMEOUT_MINUTES = int(os.getenv('SESSION_TIMEOUT_MINUTES', 10))
except ValueError:
    SESSION_TIMEOUT_MINUTES = 10
RISK_SCORES = json.loads(os.getenv('RISK_SCORES_JSON', '{}'))

@app.route('/api/admin/security-data', methods=['GET'])
@token_required
@admin_required
def api_security_dashboard_data(user_id, role):
    """
    Compiles the main Security Center dashboard data.
    Implements log clustering: groups repetitive rapid access attempts from the same 
    user into single actionable 'Incidents' based on a temporal threshold.
    """
    try:
        conn = get_db_connection()
        
        # Housekeeping logic: Resolve old low-severity AI flags
        auto_review_old_logs(conn)
        
        cur = conn.cursor()
        cur.execute("SELECT value_data FROM system_config WHERE key_name = 'system_lockdown'")
        row_lockdown = cur.fetchone()
        system_lockdown = row_lockdown['value_data'] == 'true' if row_lockdown else False

        cur.execute('SELECT name FROM users WHERE id = %s', (user_id,))
        user_row = cur.fetchone()
        admin_name = user_row['name'] if user_row else "Admin"

        yesterday_obj = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday_obj.strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("SELECT COUNT(*) as blocked FROM logs WHERE entry_allowed IS FALSE AND access_time >= %s", (yesterday_str,))
        row = cur.fetchone()
        blocked_24h = row['blocked'] if row else 0
        
        # Extract meaningful incidents (Denials, AI Anomalies, or Active Threats)
        cur.execute("""
            SELECT id, user_id, role, area, access_time, entry_allowed, reason, error_code, is_threat, is_reviewed, is_anomaly, risk_score 
            FROM logs 
            WHERE 
                (entry_allowed IS FALSE OR is_threat IS TRUE OR is_anomaly IS TRUE)
            AND 
                (access_time >= %s OR (is_threat IS TRUE AND is_reviewed IS FALSE) OR (is_anomaly IS TRUE AND is_reviewed IS FALSE))
            ORDER BY access_time DESC
        """, (yesterday_str,))
        
        all_logs = cur.fetchall()
        incidents = []
        
        if all_logs:
            cleaned_logs = []
            for log in all_logs:
                d_log = dict(log)

                if d_log['is_anomaly'] and d_log['entry_allowed'] == 1:
                    d_log['error_code'] = 'AI_ANOMALY'
                
                if not d_log.get('error_code'):
                     d_log['error_code'] = 'UNKNOWN'
                     
                cleaned_logs.append(d_log)

            # Clustering logic to prevent interface flooding
            current_cluster = {
                'logs': [dict(cleaned_logs[0])],
                'user_id': cleaned_logs[0]['user_id'],
                'error_code': cleaned_logs[0]['error_code'],
                'last_time': cleaned_logs[0]['access_time'] 
            }
            
            for i in range(1, len(cleaned_logs)):
                log = dict(cleaned_logs[i])
                
                log_time = log['access_time']
                if isinstance(log_time, str):
                    log_time = datetime.strptime(log_time, "%Y-%m-%d %H:%M:%S")
                
                prev_time = current_cluster['last_time']
                if isinstance(prev_time, str):
                    prev_time = datetime.strptime(prev_time, "%Y-%m-%d %H:%M:%S")

                time_diff = prev_time - log_time
                
                is_same_user = log['user_id'] == current_cluster['user_id']
                is_same_error = log['error_code'] == current_cluster['error_code']
                is_within_window = time_diff < timedelta(minutes=SESSION_TIMEOUT_MINUTES)
                
                if is_same_user and is_same_error and is_within_window:
                    current_cluster['logs'].append(log)
                else:
                    incidents.append(current_cluster)
                    current_cluster = {
                        'logs': [log],
                        'user_id': log['user_id'],
                        'error_code': log['error_code'],
                        'last_time': log['access_time']
                    }
            incidents.append(current_cluster)

        total_risk_score = 0
        active_threats_set = set()
        recent_incidents_response = []
        
        # Severity evaluation for grouped incidents
        for incident in incidents:
            logs_in_group = incident['logs']
            count = len(logs_in_group)
            representative_log = logs_in_group[0] 
            
            u_id = representative_log['user_id']
            error_code = representative_log['error_code']
            reason = representative_log['reason']

            if error_code == 'AI_ANOMALY':

                ai_severity = evaluate_ai_severity(representative_log['risk_score'])
                
                if ai_severity == "CRITICAL":
                    severity = "high"
                    base_score = 10
                elif ai_severity == "Medium":
                    severity = "medium"
                    base_score = 5
                else:
                    severity = "low"
                    base_score = 2
            else:
                base_score = RISK_SCORES.get(error_code, 1)
                severity = 'low'
                if base_score >= 10: 
                    severity = 'high'
                elif base_score >= 3: 
                    severity = 'medium'
                
                # Escalation logic based on repetition density
                if count >= 3 and severity == 'low':
                    severity = 'medium'
                if count >= 5:
                    severity = 'high'

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
                total_risk_score += base_score * count
            else:
                status = 'resolved'

            incident_time_str = str(incident['last_time'])
            is_recent = incident_time_str >= yesterday_str

            if (status == 'pending' or is_recent) and len(recent_incidents_response) < 20:
                display_type = reason
                if error_code == 'AI_ANOMALY':
                    display_type = f"Possible Threat: {reason}"
                elif count > 1:
                    display_type = f"{reason} ({count} attempts in 10 min)"
                
                recent_incidents_response.append({
                    'id': representative_log['id'],
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

        recent_incidents_response.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_incidents_response = recent_incidents_response[:5]
        
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
        print(f"CRITICAL ERROR in security_dashboard: {e}")
        return jsonify({'message': f'Internal Server Error: {str(e)}'}), 500


@app.route('/api/admin/audit-logs', methods=['GET'])
@token_required
@admin_required
def api_get_audit_logs(user_id, role):
    """
    Fetches the comprehensive list of security incidents using the same
    temporal clustering logic as the Security Center, but spanning a 30-day window.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
            SELECT id, user_id, role, area, access_time, entry_allowed, reason, error_code, is_threat, is_reviewed, is_anomaly, risk_score 
            FROM logs 
            WHERE 
                (entry_allowed IS FALSE OR is_threat IS TRUE OR is_anomaly IS TRUE)
            AND 
                (access_time >= %s OR (is_threat IS TRUE AND is_reviewed IS FALSE) OR (is_anomaly IS TRUE AND is_reviewed IS FALSE))
            ORDER BY access_time DESC
        """, (thirty_days_ago,))
        
        all_logs = cur.fetchall()
        incidents = []
        
        if all_logs:
            cleaned_logs = []
            for log in all_logs:
                d_log = dict(log)
                if d_log['is_anomaly'] and d_log['entry_allowed'] == 1:
                    d_log['error_code'] = 'AI_ANOMALY'
                if not d_log.get('error_code'):
                     d_log['error_code'] = 'UNKNOWN'
                cleaned_logs.append(d_log)

            current_cluster = {
                'logs': [dict(cleaned_logs[0])],
                'user_id': cleaned_logs[0]['user_id'],
                'error_code': cleaned_logs[0]['error_code'],
                'last_time': cleaned_logs[0]['access_time'] 
            }
            
            for i in range(1, len(cleaned_logs)):
                log = dict(cleaned_logs[i])
                log_time = log['access_time']
                if isinstance(log_time, str):
                    log_time = datetime.strptime(log_time, "%Y-%m-%d %H:%M:%S")
                
                prev_time = current_cluster['last_time']
                if isinstance(prev_time, str):
                    prev_time = datetime.strptime(prev_time, "%Y-%m-%d %H:%M:%S")

                time_diff = prev_time - log_time
                
                is_same_user = log['user_id'] == current_cluster['user_id']
                is_same_error = log['error_code'] == current_cluster['error_code']
                is_within_window = time_diff < timedelta(minutes=SESSION_TIMEOUT_MINUTES)
                
                if is_same_user and is_same_error and is_within_window:
                    current_cluster['logs'].append(log)
                else:
                    incidents.append(current_cluster)
                    current_cluster = {
                        'logs': [log],
                        'user_id': log['user_id'],
                        'error_code': log['error_code'],
                        'last_time': log['access_time']
                    }
            incidents.append(current_cluster)

        audit_incidents = []
        
        for incident in incidents:
            logs_in_group = incident['logs']
            count = len(logs_in_group)
            representative_log = logs_in_group[0] 
            
            u_id = representative_log['user_id']
            error_code = representative_log['error_code']
            reason = representative_log['reason']

            if error_code == 'AI_ANOMALY':
                ai_severity = evaluate_ai_severity(representative_log['risk_score'])
                if ai_severity == "CRITICAL":
                    severity = "high"
                    base_score = 10
                elif ai_severity == "Medium":
                    severity = "medium"
                    base_score = 5
                else:
                    severity = "low"
                    base_score = 2
            else:
                base_score = RISK_SCORES.get(error_code, 1)
                severity = 'low'
                if base_score >= 10: severity = 'high'
                elif base_score >= 3: severity = 'medium'
                
                if count >= 3 and severity == 'low': severity = 'medium'
                if count >= 5: severity = 'high'

            db_threat_flag = any(l.get('is_threat') for l in logs_in_group)
            db_anomaly_flag = any(l.get('is_anomaly') for l in logs_in_group)
            all_reviewed = all(l.get('is_reviewed') for l in logs_in_group)
            
            is_active = False
            if not all_reviewed:
                if db_threat_flag or db_anomaly_flag or severity in ['high', 'medium']:
                    is_active = True

            status = 'pending' if is_active else 'resolved'

            display_type = reason
            if error_code == 'AI_ANOMALY':
                display_type = f"Possible Threat: {reason}"
            elif count > 1:
                display_type = f"{reason} ({count} attempts in 10 min)"
            
            audit_incidents.append({
                'id': representative_log['id'],
                'severity': severity,
                'type': display_type,
                'description': error_code,
                'source_id': u_id,
                'timestamp': str(incident['last_time']),
                'status': status,
                'is_ai': error_code == 'AI_ANOMALY',
                'count': count,
                'is_threat': db_threat_flag
            })

        cur.close()
        conn.close()
        
        return jsonify(audit_incidents), 200

    except Exception as e:
        print(f"Error fetching audit logs: {e}")
        return jsonify({'message': f'Internal Server Error: {str(e)}'}), 500


@app.route('/api/admin/logs', methods=['GET'])
@token_required
@admin_required
def api_get_all_logs(user_id, role):
    """Retrieves an unclustered, raw list of the latest 2000 access events."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, user_id, role, area, access_time, entry_allowed, reason, error_code, risk_score, is_anomaly, is_threat 
            FROM logs 
            ORDER BY access_time DESC
            LIMIT 2000
        """)
        logs = cur.fetchall()
        cur.close()
        conn.close()

        logs_list = []
        for l in logs:
            logs_list.append({
                'id': l['id'],
                'user_id': l['user_id'],
                'role': l['role'],
                'area': l['area'],
                'access_time': str(l['access_time']),
                'entry_allowed': l['entry_allowed'],
                'reason': l['reason'],
                'error_code': l['error_code'],
                'risk_score': l['risk_score'],
                'is_anomaly': l['is_anomaly'],
                'is_threat': l['is_threat']
            })
            
        return jsonify(logs_list), 200
        
    except Exception as e:
        print(f"Error fetching all logs: {e}")
        return jsonify({'message': f'Error fetching logs: {str(e)}'}), 500
    
# =============================================================================
# === INTERNAL LOGIC & HELPER FUNCTIONS ===
# =============================================================================

def check_should_notify_hard_rule(qr_data, target_area):
    """
    Evaluates a rejected access event against the active alert rules database
    to determine if a notification email should be dispatched.
    """
    if qr_data['valid']:
        return False

    error_code = qr_data.get('error_code')
    role = qr_data.get('role', 'Unknown')
    should_notify = False
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = """
            SELECT id FROM alert_rules 
            WHERE is_active = TRUE
            AND event_type = %s
            AND (role_filter = 'ALL' OR role_filter = %s)
            AND (area_filter = 'ALL' OR area_filter = %s)
            LIMIT 1
        """
        cur.execute(query, (error_code, role, target_area))
        if cur.fetchone():
            should_notify = True
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error checking alert rules: {e}")

    return should_notify


def evaluate_ai_severity(risk_score):
    """
    Categorizes the severity of an AI-detected anomaly based on its numerical
    deviation distance from the database-configured dynamic threshold.
    """
    try:
        threshold = get_anomaly_threshold()
    except ValueError:
        threshold = -0.025
        
    distance = threshold - risk_score
    
    if distance >= 0.10:
        severity = "CRITICAL"
    elif distance >= 0.04:
        severity = "Medium"
    else:
        severity = "Low"
        
    return severity


def background_access_processing(qr_data, target_area):
    """
    Asynchronous task triggered by physical access scans.
    Evaluates AI anomaly scores, verifies structural rule sets, stores the 
    resulting log entity, emits WebSocket events for real-time interface rendering,
    and dispatches potential email notifications via SMTP.
    """
    risk_score = 0.0
    is_anomaly = False
    is_threat = False

    should_send_anomaly_alert = False
    should_send_hard_rule_alert = False

    log_entry = {
        'user_id': qr_data['user_id'],
        'role': qr_data['role'],
        'area': target_area,
        'access_time': qr_data['access_time'],
        'entry_allowed': qr_data['valid'],
        'reason': qr_data['reason'],
        'error_code': qr_data.get('error_code', 'UNKNOWN'),
        'ai_explanation': None
    }

    if qr_data['valid']:
        try:
            risk_score, is_anomaly, ai_explanation = predict_anomaly(log_entry)
            log_entry['ai_explanation'] = ai_explanation if is_anomaly else None

            if is_anomaly:
                severity = evaluate_ai_severity(risk_score)
                is_threat = True
                print(f"[AI] ANOMALY DETECTED. Score: {risk_score:.4f} | Severity: {severity}")
                
                if severity in ["Medium", "CRITICAL"]:
                    should_send_anomaly_alert = True
                    log_entry['reason'] = f"AI Anomaly ({severity})"
                else:
                    log_entry['reason'] = "AI Anomaly (Low)"
        except Exception as e:
            print(f"Error during AI analysis: {e}")
    else:
        is_threat = True
        if check_should_notify_hard_rule(qr_data, target_area):
            log_entry['reason'] = f"HARD RULE: {log_entry['reason']}"
            should_send_hard_rule_alert = True

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO logs (user_id, role, area, access_time, entry_allowed, reason, risk_score, error_code, is_anomaly, is_threat, ai_explanation)
            VALUES (COALESCE(%s, 'unknown'), COALESCE(%s, 'unknown'), %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            log_entry['user_id'], 
            log_entry['role'], 
            log_entry['area'], 
            log_entry['access_time'],
            log_entry['entry_allowed'], 
            log_entry['reason'], 
            float(risk_score),
            log_entry['error_code'], 
            bool(is_anomaly), 
            bool(is_threat),
            log_entry.get('ai_explanation')
        ))
        conn.commit()
        cur.close()
        conn.close()

        print(f"[WEBSOCKET] Emitting dashboard update for user {qr_data['user_id']}...")
        socketio.emit('dashboard_update', {
            'type': 'new_log', 
            'timestamp': time.time(),
            'user_id': qr_data['user_id']
        })
        
        if is_threat or is_anomaly:
            print("[WEBSOCKET] Emitting security alert...")
            socketio.emit('security_update', {'type': 'new_threat', 'msg': 'Anomaly detected'})

    except Exception as e:
        print(f"Error storing record in DB: {e}")

    if should_send_anomaly_alert:
        socketio.start_background_task(send_anomaly_alert, log_entry, risk_score)
        
    if should_send_hard_rule_alert:
        socketio.start_background_task(send_access_denied_alert, log_entry)


def find_cluster_ids_for_log(conn, target_log_id):
    """
    Groups logically related access events to process status updates uniformly.
    A cluster implies same user, identical error code, occurring within the
    defined temporal SESSION_TIMEOUT window.
    """
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, error_code, is_anomaly, access_time FROM logs WHERE id = %s", (target_log_id,))
    target = cur.fetchone()
    
    if not target:
        cur.close()
        return []

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

    logs = []
    for r in rows:
        d = dict(r)
        if isinstance(d['access_time'], str):
             try: d['access_time'] = datetime.strptime(d['access_time'].split('.')[0], "%Y-%m-%d %H:%M:%S")
             except: d['access_time'] = datetime.now()
        logs.append(d)

    target_cluster_ids = []
    
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


def auto_review_old_logs(conn):
    """
    Automated housekeeping procedure. Discards low-severity AI flags older 
    than 24 hours to maintain dashboard usability and relevancy.
    """
    try:
        cur = conn.cursor()
        
        yesterday_obj = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday_obj.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            threshold = get_anomaly_threshold()
        except ValueError:
            threshold = -0.025
            
        low_severity_bound = threshold - 0.04 
        
        cur.execute("""
            UPDATE logs 
            SET is_reviewed = TRUE 
            WHERE access_time < %s 
            AND is_threat = TRUE 
            AND is_reviewed = FALSE
            AND is_anomaly = TRUE
            AND risk_score >= %s
        """, (yesterday_str, low_severity_bound))
        
        conn.commit()
        cur.close()
    except Exception as e:
        pass


def send_lockdown_email(active):
    """
    Dispatches a critical HTML-formatted system alert to all Admin users
    regarding structural status changes to the Global System Lockdown state.
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("⚠️ SMTP credentials not set. Cannot send lockdown email.")
        return

    admins = get_admin_emails()
    if not admins:
        print("ALERT: Lockdown triggered but NO ADMINS found in database.")
        return

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if active:
        subject = "⚠️🔒 AILOQR SYSTEM LOCKDOWN INITIATED 🔒⚠️"
        body_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #8b0000; color: white; padding: 15px 20px; text-align: center;">
                <h2 style="margin: 0; font-size: 22px;">SYSTEM LOCKDOWN INITIATED</h2>
            </div>
            <div style="padding: 20px; color: #333;">
                <p style="font-size: 16px; margin-top: 0; font-weight: bold; color: #8b0000;">CRITICAL ALERT:</p>
                <p style="font-size: 16px;">This is an automated alert. The system has been placed in <strong>LOCKDOWN</strong> mode by an administrator.</p>
                
                <div style="background-color: #fdf2f2; padding: 15px; border-left: 4px solid #8b0000; margin-bottom: 20px;">
                    <ul style="list-style-type: none; padding: 0; margin: 0; line-height: 1.8; color: #c0392b; font-weight: bold;">
                        <li>🚫 All non-admin access is currently BLOCKED.</li>
                        <li>🚫 Physical access control points will deny entry.</li>
                    </ul>
                </div>
                
                <p style="color: #7f8c8d; font-size: 14px; margin-bottom: 0;"><strong>Timestamp:</strong> {current_time}</p>
            </div>
        </div>
        """
        
    else:
        subject = "✅ AILOQR System Lockdown Lifted"
        body_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #27ae60; color: white; padding: 15px 20px; text-align: center;">
                <h2 style="margin: 0; font-size: 22px;">System Lockdown Lifted</h2>
            </div>
            <div style="padding: 20px; color: #333;">
                <p style="font-size: 16px; margin-top: 0;">The system lockdown has been successfully lifted.</p>
                
                <div style="background-color: #eafaf1; padding: 15px; border-left: 4px solid #27ae60; margin-bottom: 20px;">
                    <ul style="list-style-type: none; padding: 0; margin: 0; line-height: 1.8; color: #2c3e50;">
                        <li>🔓 Normal access control rules are now back in effect.</li>
                        <li>🔓 Physical access control points are operating normally.</li>
                    </ul>
                </div>
                
                <p style="color: #7f8c8d; font-size: 14px; margin-bottom: 0;"><strong>Timestamp:</strong> {current_time}</p>
            </div>
        </div>
        """

    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = ", ".join(admins)
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body_html, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=5)
        server.starttls() 
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        
        server.sendmail(SMTP_EMAIL, admins, msg.as_string())
        server.quit()
        
        print(f"[EMAIL] Lockdown status ({'Active' if active else 'Lifted'}) sent successfully to admins.")
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send lockdown email: {e}")

# =============================================================================
# === APPLICATION STARTUP & INITIALIZATION ===
# =============================================================================

if __name__ == "__main__":

    env = os.environ.get("ENVIRONMENT", "development")
    is_debug = (env == "development")
    port = int(os.environ.get("PORT", 5000))

    # --- DATABASE INITIALIZATION ---
    print("🔄 Verifying database schemas and default configurations...")
    try:
        initialize_database()
        print("✅ Database schemas verified successfully.")
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Database initialization failed: {e}")

    # --- PRE-LOAD AI MODEL ON START ---
    print("Initializing AI model...")
    try:
        load_or_train_model()
        print("✅ AI model prepared and loaded into memory.")
    except Exception as e:
        print(f"⚠️ Warning: Failed to load AI model: {e}")

    print("🕒 Initializing retraining scheduler in the background...")
    start_retraining_scheduler()

    print(f"🚀 Initializing Flask server in mode: {env.upper()}")
    print(f"🔌 WebSocket activated on port {port}...")

    socketio.run(app, host="0.0.0.0", port=port, debug=is_debug, use_reloader=False)