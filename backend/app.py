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


# --- SECURITY ENDPOINTS ---

@app.route('/api/admin/logs/suspicious')
def get_suspicious_logs():
    threshold = float(os.getenv('ANOMALY_THRESHOLD', -0.15))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, user_id, role, area, access_time, risk_score, reason 
        FROM logs 
        WHERE entry_allowed = TRUE AND risk_score < %s
        ORDER BY access_time DESC LIMIT 50
    """, (threshold,))
    logs = cur.fetchall()
    cur.close()
    conn.close()
    
    data = [{'id': r[0], 'user': r[1], 'role': r[2], 'area': r[3], 
             'time': str(r[4]), 'score': r[5], 'reason': r[6]} for r in logs]
    return jsonify(data)

@app.route('/api/admin/logs/denied')
def get_denied_logs():
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
    

# Risk Score Map
RISK_SCORES = {
    'FORGED_QR': 10,     # Hack attempt / Security breach
    'MALFORMED_QR': 10,  # Fuzzing / Hack attempt
    'UNKNOWN_USER': 5,   # Potential brute force or deleted user access
    'AREA_VIOLATION': 3, # Unauthorized internal access (Policy)
    'TIME_VIOLATION': 1, # Process issue
    'EXPIRED_QR': 1,     # Usability issue
    'UNKNOWN': 1
}

# Critical Threshold: Above this risk score, system is "Critical" (default to 10)
CRITICAL_THRESHOLD = 10

# Configurable Threshold: How many low-severity errors constitute a threat? (default to 3)
REPETITION_THRESHOLD = 3 

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

# NEW ENDPOINT: Toggle Threat Status
@app.route('/api/admin/log/<int:log_id>/toggle-threat', methods=['POST'])
@token_required
@admin_required
def toggle_threat_status(user_id, role, log_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Get current status and details of the target log
        cur.execute("SELECT user_id, error_code, is_threat, is_reviewed FROM logs WHERE id = %s", (log_id,))
        log = cur.fetchone()
        
        if not log:
            return jsonify({'message': 'Log not found'}), 404
            
        target_user_id = log['user_id']
        target_error_code = log['error_code']
        current_threat_status = log['is_threat']
        current_review_status = log['is_reviewed']
        
        # 2. DETERMINE TARGET STATE (FIXED LOGIC)
        # We assume if it's PENDING (Threat & Not Reviewed), we want to make it SAFE.
        # If it's anything else (Safe or Reviewed Threat), we want to make it ACTIVE THREAT.
        
        is_pending = current_threat_status and not current_review_status
        
        if is_pending:
            # Action: Mark as Safe (False Positive)
            new_threat_status = False
            new_review_status = True
        else:
            # Action: Escalate to Active Threat
            new_threat_status = True
            new_review_status = False
        
        # 3. Apply to ALL related logs (Same User + Same Error Code)
        cur.execute("""
            UPDATE logs 
            SET is_threat = %s, is_reviewed = %s
            WHERE user_id = %s 
            AND error_code = %s
        """, (new_threat_status, new_review_status, target_user_id, target_error_code))
        
        rows_affected = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'status': 'success', 
            'new_is_threat': new_threat_status,
            'updated_count': rows_affected
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error toggling status: {str(e)}'}), 500

# NEW ENDPOINT: Mark as Reviewed
@app.route('/api/admin/log/<int:log_id>/review', methods=['POST'])
@token_required
@admin_required
def toggle_review_status(user_id, role, log_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Get current status
        cur.execute("SELECT user_id, error_code, is_reviewed FROM logs WHERE id = %s", (log_id,))
        log = cur.fetchone()
        
        if not log:
            return jsonify({'message': 'Log not found'}), 404
            
        target_user_id = log['user_id']
        target_error_code = log['error_code']
        # For review button, we only support marking as reviewed (true)
        # We don't support "unreviewing" via this specific button logic for now based on your request
        new_review_status = True
        
        # 3. Batch update similar logs
        # REMOVED 24h constraint
        
        cur.execute("""
            UPDATE logs 
            SET is_reviewed = %s
            WHERE user_id = %s 
            AND error_code = %s
        """, (new_review_status, target_user_id, target_error_code))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'status': 'success', 
            'new_is_reviewed': new_review_status
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Error updating review status: {str(e)}'}), 500

    
# Main Security Dashboard Data Endpoint
@app.route('/api/admin/security-data', methods=['GET'])
@token_required
@admin_required
def api_security_dashboard_data(user_id, role):
    try:
        conn = get_db_connection()
        
        # 0. HOUSEKEEPING: Auto-review old safe logs
        auto_review_old_logs(conn)
        
        cur = conn.cursor()

        # 1. Admin Info
        cur.execute('SELECT name FROM users WHERE id = %s', (user_id,))
        user_row = cur.fetchone()
        admin_name = user_row['name'] if user_row else "Admin"

        # 2. Time Threshold (24h)
        yesterday_obj = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday_obj.strftime("%Y-%m-%d %H:%M:%S")

        # 3. Blocked Counters (Raw count of ALL blocked attempts in 24h)
        cur.execute("SELECT COUNT(*) as blocked FROM logs WHERE entry_allowed = 0 AND access_time >= %s", (yesterday_str,))
        row = cur.fetchone()
        blocked_24h = row['blocked'] if row else 0

        # --- SMART LOGIC STARTS HERE ---
        
        # 4. Fetch logs for analysis
        # Strategy: Get ALL logs from last 24h OR any older logs that are still threats and unreviewed
        # This ensures active threats don't disappear just because 24h passed.
        cur.execute("""
            SELECT id, user_id, role, area, access_time, entry_allowed, reason, error_code, is_threat, is_reviewed 
            FROM logs 
            WHERE entry_allowed = 0 
            AND (access_time >= %s OR (is_threat = TRUE AND is_reviewed = FALSE))
            ORDER BY access_time DESC
        """, (yesterday_str,))
        
        all_logs = cur.fetchall()
        
        # Analyze Repetitions for logs without explicit status yet
        user_failure_counts = {}
        for log in all_logs:
            u_id = log['user_id'] if isinstance(log, dict) or hasattr(log, 'keys') else log[1]
            if u_id not in user_failure_counts:
                user_failure_counts[u_id] = 0
            user_failure_counts[u_id] += 1

        # Process Logs & Calculate Metrics
        total_risk_score = 0
        active_threats_set = set()
        recent_incidents = []
        
        for i, log in enumerate(all_logs):
            log_dict = dict(log)
            reason_text = log_dict.get('reason', '') or ''
            error_code = log_dict.get('error_code') or 'UNKNOWN'
            u_id = log_dict.get('user_id', 'Unknown')
            is_threat = log_dict.get('is_threat') # Boolean from DB
            is_reviewed = log_dict.get('is_reviewed') # Boolean from DB
            
            # Base Score
            score = RISK_SCORES.get(error_code, 1)
            
            # Determine Severity
            severity = 'low'
            if score >= 10: severity = 'high'
            elif score >= 3: severity = 'medium'
            
            # --- STATUS DETERMINATION LOGIC ---
            
            # Initialization logic for logs that have never been processed (NULL in DB)
            if is_threat is None:
                is_repeated = user_failure_counts.get(u_id, 0) >= REPETITION_THRESHOLD
                # Calculate initial threat status
                calculated_is_threat = (severity == 'high' or severity == 'medium' or is_repeated)
                
                # PERSIST THIS CALCULATION TO DB so it sticks!
                # We do this lazily here or could do it in a background job
                # For simplicity, we just use the calculated value for display now
                is_threat = calculated_is_threat
            
            if is_reviewed is None:
                is_reviewed = False

            # Determine Frontend Status ('pending' = Active Threat that needs review)
            if is_threat and not is_reviewed:
                status = 'pending'
                active_threats_set.add(u_id)
                total_risk_score += score # Only count active threats towards risk score
            else:
                status = 'resolved' 
            
            # Add to list (Limit to 10 for display)
            # Only show 'resolved' logs if they are recent (<24h)
            log_time_str = str(log_dict.get('access_time', ''))
            is_recent = log_time_str >= yesterday_str
            
            if (status == 'pending' or is_recent) and len(recent_incidents) < 10:
                display_type = reason_text
                # Add context if it's a repetition threat
                if is_threat and severity == 'low':
                     display_type = f"{reason_text} (Repeated {user_failure_counts.get(u_id)}x)"

                recent_incidents.append({
                    'id': str(log_dict.get('id', i)),
                    'severity': severity,
                    'type': display_type, 
                    'description': error_code,
                    'source_id': u_id, 
                    'timestamp': log_time_str,
                    'status': status 
                })

        # System Health
        if total_risk_score == 0:
            system_health = 'Good'
        elif total_risk_score < CRITICAL_THRESHOLD: 
            system_health = 'Warning'
        else:
            system_health = 'Critical'

        cur.close()
        conn.close()

        response_data = {
            'admin_name': admin_name,
            'stats': {
                'active_threats': len(active_threats_set),
                'blocked_attempts_24h': blocked_24h,
                'system_health': system_health,
                'risk_score': total_risk_score
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