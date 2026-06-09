import gevent.monkey
gevent.monkey.patch_all()

from dotenv import load_dotenv
import os
load_dotenv() 

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import jwt
from QR_generation_validation import generate_qr, verify_qr
from security_analyzer import predict_anomaly, send_anomaly_alert, load_or_train_model, send_access_denied_alert, get_admin_emails, start_retraining_scheduler
import uuid
from database import save_user, check_password, get_db_connection, get_user_by_email, get_all_roles
import base64
from io import BytesIO, StringIO
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

app = Flask(__name__)

CORS(app, supports_credentials=True) 

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

app.secret_key = os.getenv("SECRET_KEY")
ADMIN_REGISTRATION_KEY = os.getenv("ADMIN_KEY")
SIGNATURE_KEY = os.getenv("SIGNATURE_KEY").encode('utf-8')

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# Socket initialization
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

def no_cache(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


#=================================================
# === AUTHENTICATION DECORATORS ===
#=================================================
def token_required(f):
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
    @wraps(f)
    def decorated(*args, **kwargs):
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
@app.route('/api/roles', methods=['GET'])
def api_get_roles():
    try:
        roles = get_all_roles()
        return jsonify(roles), 200
    except Exception as e:
        return jsonify({'message': f'Internal server error: {e}'}), 500
    
def validate_password(password):
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
    

# EDGE DEVICE ENDPOINTS
@app.route('/api/access/scan', methods=['POST'])
def api_access_scan():
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

    socketio.start_background_task(background_access_processing, validation_result, target_area)

    return jsonify(response_data), 200
    

#=================================================
# === PROTECTED API ENDPOINTS (USER) ===
#=================================================
@app.route('/api/dashboard-data', methods=['GET'])
@token_required
def api_dashboard_data(user_id, role):
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


#=================================================
# === PROTECTED API ENDPOINTS (ADMIN) ===
#=================================================
@app.route('/api/admin/dashboard-data', methods=['GET'])
@token_required
@admin_required
def api_admin_dashboard(user_id, role):
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
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500

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
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500

# --- SECURITY ENDPOINTS ---
@app.route('/api/admin/logs/suspicious')
def get_suspicious_logs():
    threshold = float(os.getenv('ANOMALY_THRESHOLD', -0.025))
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

CRITICAL_THRESHOLD = 10
REPETITION_THRESHOLD = 3 

@app.route('/api/admin/log/<int:log_id>/toggle-threat', methods=['POST'])
@token_required
@admin_required
def toggle_threat_status(user_id, role, log_id):
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


@app.route('/api/admin/system-lockdown', methods=['POST'])
@token_required
@admin_required
def toggle_system_lockdown(user_id, role):
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
    

try:
    SESSION_TIMEOUT_MINUTES = int(os.getenv('SESSION_TIMEOUT_MINUTES', 10))
except ValueError:
    SESSION_TIMEOUT_MINUTES = 10
RISK_SCORES = json.loads(os.getenv('RISK_SCORES_JSON', '{}'))

@app.route('/api/admin/security-data', methods=['GET'])
@token_required
@admin_required
def api_security_dashboard_data(user_id, role):
    try:
        conn = get_db_connection()
        
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
        print(f"CRITICAL ERROR in security_dashboard: {e}")
        return jsonify({'message': f'Internal Server Error: {str(e)}'}), 500
    

#=================================================
# === HELPER FUNCTIONS ===
#=================================================
def check_should_notify_hard_rule(qr_data, target_area):
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
    Evaluates the severity of an AI-detected anomaly based on its risk score and a predefined threshold.
    The function categorizes anomalies into "CRITICAL", "Medium", or "Low"
    """
    try:
        threshold = float(os.getenv('ANOMALY_THRESHOLD', -0.025))
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
            # Unpack the 3 variables returned by predict_anomaly
            risk_score, is_anomaly, ai_explanation = predict_anomaly(log_entry)

            log_entry['ai_explanation'] = explanation if is_anomaly else None

            if is_anomaly:
                severity = evaluate_ai_severity(risk_score)
                is_threat = True
                print(f"[AI] ANOMALY DETECTED. Score: {risk_score:.4f} | Severity: {severity}")
                
                # Action according to severity
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
    try:
        cur = conn.cursor()
        
        # Logs older than 24h
        yesterday_obj = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday_obj.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            threshold = float(os.getenv('ANOMALY_THRESHOLD', -0.025))
        except ValueError:
            threshold = -0.025
            
        # Scores classified as "Low" severity anomalies
        low_severity_bound = threshold - 0.04 
        
        # Update logs flagged by AI as low-severity anomalies that are older than 24h to reviewed
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
        pass # Silently pass automated housekeeping

def send_lockdown_email(active):
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return

    admins = get_admin_emails()
    if not admins:
        return

    subject = "⚠️🔒 AILOQR SYSTEM LOCKDOWN ALERT 🔒⚠️" if active else "✅ AILOQR System Lockdown Lifted"
    
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
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = ", ".join(admins)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, admins, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Failed to send email: {e}")


#=================================================
# === APPLICATION START ===
#=================================================

if __name__ == "__main__":

    env = os.environ.get("ENVIRONMENT", "development")
    is_debug = (env == "development")
    port = int(os.environ.get("PORT", 5000))

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