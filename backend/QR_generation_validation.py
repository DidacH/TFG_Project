import qrcode
import hmac, hashlib
import time
import io
from datetime import datetime
from database import get_db_connection


def generate_qr(user_id, secret_key):
    timestamp = int(time.time())  #current UNIX time
    message = f"{user_id}:{timestamp}"
    signature = hmac.new(secret_key, message.encode(), hashlib.sha256).hexdigest()
    content = f"{user_id}:{timestamp}:{signature}"
    
    img = qrcode.make(content)

    #Convert image to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes = img_bytes.getvalue()

    return img_bytes, timestamp


# --- HARD RULES DEFINITIONS ---
ACCESS_POLICY = {
    'Student': ['Classroom_1', 'Library', 'Lab_A'],
    'Professor': ['Classroom_1', 'Library', 'Lab_A', 'Office_1'],
    'Staff': ['Office_1', 'Server_Room', 'Lab_A'],
    'Admin': 'ALL' 
}

GLOBAL_CLOSED_HOURS = [23, 0, 1, 2, 3, 4, 5, 6]


def verify_qr(content, secret_key, target_area):
    now = int(time.time())
    expiration_seconds = 30  #seconds
    current_dt = datetime.fromtimestamp(now)
    time_str = current_dt.strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        user_id, timestamp_str, received_signature = content.split(":")
        timestamp = int(timestamp_str)
    except ValueError:
        return {
            'valid': False,
            'reason': 'Malformed',
            'user_id': None,
            'role': None,
            'access_time': time_str
        }

    message = f"{user_id}:{timestamp}"
    expected_signature = hmac.new(secret_key, message.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received_signature, expected_signature):
        return {
            'valid': False,
            'reason': 'Forged',
            'user_id': user_id,
            'role': None,
            'access_time': time_str
        }

    #Fetch user info if signature valid
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user is None:
        return {
            'valid': False,
            'reason': 'Not registered',
            'user_id': user_id,
            'role': None,
            'access_time': time_str
        }

    role = user[0]

    grace_period = 5  #seconds, for clock skew
    if now - timestamp > expiration_seconds+grace_period:
        return {
            'valid': False,
            'reason': 'Expired',
            'user_id': user_id,
            'role': role,
            'access_time': time_str
        }
    
    # Check role permissions
    allowed_areas = ACCESS_POLICY.get(role, [])
    if allowed_areas != 'ALL' and target_area not in allowed_areas:
        return {'valid': False, 'reason': f'Area violation', 'user_id': user_id, 'role': role, 'access_time': time_str}

    # Check Global Time (Facility Closed Hours)
    # Exception: Admins can access anytime
    if current_dt.hour in GLOBAL_CLOSED_HOURS and role != 'Admin':
        return {'valid': False, 'reason': 'Facilities closed', 'user_id': user_id, 'role': role, 'access_time': time_str}

    return {
        'valid': True,
        'reason': 'valid',
        'user_id': user_id,
        'role': role,
        'access_time': time_str
    }


    

