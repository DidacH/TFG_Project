import qrcode
import hmac, hashlib
import time
import io
from datetime import datetime
import sqlite3
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


def verify_qr(content, secret_key):
    now = int(time.time())
    expiration_seconds = 30  #seconds
    
    try:
        user_id, timestamp_str, received_signature = content.split(":")
        timestamp = int(timestamp_str)
    except ValueError:
        return {
            'valid': False,
            'reason': 'malformed',
            'user_id': None,
            'email': None,
            'role': None,
            'access_time': datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S')
        }

    message = f"{user_id}:{timestamp}"
    expected_signature = hmac.new(secret_key, message.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received_signature, expected_signature):
        return {
            'valid': False,
            'reason': 'forged',
            'user_id': user_id,
            'email': None,
            'role': None,
            'access_time': datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S')
        }

    #Fetch user info if signature valid
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT email, role FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user is None:
        return {
            'valid': False,
            'reason': 'not_registered',
            'user_id': user_id,
            'email': None,
            'role': None,
            'access_time': datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S')
        }

    email, role = user

    grace_period = 5  #seconds, for clock skew
    if now - timestamp > expiration_seconds+grace_period:
        return {
            'valid': False,
            'reason': 'expired',
            'user_id': user_id,
            'email': email,
            'role': role,
            'access_time': datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S')
        }

    return {
        'valid': True,
        'reason': 'valid',
        'user_id': user_id,
        'email': email,
        'role': role,
        'access_time': datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S')
    }


    

