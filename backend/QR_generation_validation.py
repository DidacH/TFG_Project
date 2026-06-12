import qrcode
import hmac
import hashlib
import time
import io
import pytz
from datetime import datetime
from database import get_db_connection

# =============================================================================
# === CACHE CONFIGURATION ===
# =============================================================================

# In-memory cache to prevent excessive database queries during high-traffic 
# scanning events. Refreshes based on the defined Time-To-Live (TTL).
_RULES_CACHE = None
_CONFIG_CACHE = None
_LAST_CACHE_UPDATE = 0
CACHE_TTL = 60  # Cache Time-To-Live in seconds

# =============================================================================
# === QR CRYPTOGRAPHY & GENERATION ===
# =============================================================================

def generate_qr(user_id, secret_key):
    """
    Generates a cryptographically signed QR code payload using HMAC-SHA256.
    
    The payload includes the user ID, the current UNIX timestamp, and the 
    corresponding signature to prevent forgery and ensure temporal validity.
    
    Returns:
        tuple: (QR image as a bytes buffer, UNIX timestamp of generation)
    """
    timestamp = int(time.time())
    message = f"{user_id}:{timestamp}"
    signature = hmac.new(secret_key, message.encode(), hashlib.sha256).hexdigest()
    content = f"{user_id}:{timestamp}:{signature}"
    
    img = qrcode.make(content)

    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes = img_bytes.getvalue()

    return img_bytes, timestamp

# =============================================================================
# === VALIDATION & RBAC LOGIC ===
# =============================================================================

def load_rules_from_db():
    """
    Retrieves dynamic access control rules (RBAC) and global configurations 
    from the PostgreSQL database and caches them in memory.
    Respects the CACHE_TTL to optimize query performance.
    """
    global _RULES_CACHE, _CONFIG_CACHE, _LAST_CACHE_UPDATE
    
    current_time = time.time()
    
    if _RULES_CACHE and _CONFIG_CACHE and (current_time - _LAST_CACHE_UPDATE < CACHE_TTL):
        return

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT role, allowed_area, allowed_days, start_time, end_time, is_active FROM access_rules")
        rules = cur.fetchall()
        
        temp_rules = {}
        for role, area, days, start_time, end_time, is_active in rules:
            if role not in temp_rules:
                temp_rules[role] = []
            
            temp_rules[role].append({
                'area': area,
                'days': [int(d) for d in days.split(',')] if days else [],
                'start_time': start_time,
                'end_time': end_time,
                'is_active': is_active
            })
            
        cur.execute("SELECT key_name, value_data FROM system_config")
        configs = cur.fetchall()
        
        temp_config = {}
        for key, value in configs:
            if key == 'closed_hours':
                try:
                    temp_config['closed_hours'] = [int(h) for h in value.split(',')]
                except:
                    temp_config['closed_hours'] = []
            elif key == 'system_lockdown':
                temp_config['system_lockdown'] = (value == 'true')
            else:
                temp_config[key] = value
                
        _RULES_CACHE = temp_rules
        _CONFIG_CACHE = temp_config
        _LAST_CACHE_UPDATE = current_time
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"[CACHE ERROR] Failed to load rules from DB: {e}")
        if _RULES_CACHE is None: _RULES_CACHE = {}
        if _CONFIG_CACHE is None: _CONFIG_CACHE = {}


def verify_qr(content, secret_key, target_area):
    """
    Validation engine for physical access scans.
    Executes multiple security layers: Payload integrity, HMAC signature verification,
    User block status, Global Lockdown overrides, Timestamp expiration, and 
    Role-Based Access Control (Area, Days, Hours).
    
    Returns:
        dict: Validation results including boolean status, error codes, and contextual reasons.
    """
    now = int(time.time())
    spain_tz = pytz.timezone('Europe/Madrid')
    current_dt = datetime.now(spain_tz)
    time_str = current_dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # 1. Payload structural verification
    try:
        user_id, timestamp_str, received_signature = content.split(":")
        timestamp = int(timestamp_str)
    except ValueError:
        return {
            'valid': False,
            'error_code': 'MALFORMED_QR', 
            'reason': 'Malformed Code',
            'user_id': None,
            'role': None,
            'access_time': time_str
        }

    # 2. Cryptographic signature verification
    message = f"{user_id}:{timestamp}"
    expected_signature = hmac.new(secret_key, message.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received_signature, expected_signature):
        return {
            'valid': False,
            'error_code': 'FORGED_QR', 
            'reason': 'False Signature (Forged)',
            'user_id': user_id,
            'role': None,
            'access_time': time_str
        }

    # 3. User verification and state retrieval
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT role, is_blocked FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user is None:
        return {
            'valid': False,
            'error_code': 'UNKNOWN_USER',
            'reason': 'User ID was not found',
            'user_id': user_id,
            'role': None,
            'access_time': time_str
        }

    role = user['role'] if isinstance(user, dict) or hasattr(user, 'keys') else user[0]
    is_blocked = user['is_blocked'] if isinstance(user, dict) or hasattr(user, 'keys') else user[1]

    # 4. Individual user block evaluation
    if is_blocked:
        return {
            'valid': False,
            'error_code': 'USER_BLOCKED',
            'reason': 'User account is blocked',
            'user_id': user_id,
            'role': role,
            'access_time': time_str
        }

    load_rules_from_db()

    # 5. Global System Lockdown evaluation
    is_locked = _CONFIG_CACHE.get('system_lockdown', False)
    if is_locked:
        # Administrative override exception
        if role != 'Admin':
            return {
                'valid': False, 
                'error_code': 'SYSTEM_LOCKDOWN', 
                'reason': 'System in Lockdown Mode', 
                'user_id': user_id, 
                'role': role, 
                'access_time': time_str
            }

    # 6. Temporal Expiration Check (Replay Attack Prevention)
    expiration_seconds = 30
    grace_period = 5  # Buffer for network latency and clock skew
    if now - timestamp > expiration_seconds + grace_period:
        return {
            'valid': False,
            'error_code': 'EXPIRED_QR',
            'reason': 'QR code expired',
            'user_id': user_id,
            'role': role,
            'access_time': time_str
        }
    
    # 7. Role-Based Access Control (RBAC) Evaluation
    role_rules = _RULES_CACHE.get(role, [])
    current_weekday = current_dt.weekday() # 0 = Monday, 6 = Sunday
    current_time_only = current_dt.time()
    
    has_access = False
    
    # Iterate through all configured rules for the given role (Logical OR)
    for rule in role_rules:
        if not rule.get('is_active', True):
            continue
            
        area_match = (rule['area'] == 'ALL' or rule['area'] == target_area)
        day_match = (current_weekday in rule['days'])
        time_match = (rule['start_time'] <= current_time_only <= rule['end_time'])
        
        if area_match and day_match and time_match:
            has_access = True
            break

    if not has_access:
        return {
            'valid': False, 
            'error_code': 'AREA_VIOLATION',  
            'reason': f'Access denied for {role} at {target_area} (Check schedules/permissions)', 
            'user_id': user_id, 
            'role': role, 
            'access_time': time_str
        }

    # 8. Global Facility Schedule Evaluation
    if current_dt.hour in _CONFIG_CACHE.get('closed_hours', []) and role != 'Admin':
        return {
            'valid': False, 
            'error_code': 'TIME_VIOLATION',  
            'reason': 'Facilities closed', 
            'user_id': user_id, 
            'role': role, 
            'access_time': time_str
        }

    # Access Granted
    return {
        'valid': True,
        'error_code': None,
        'reason': 'Valid access',
        'user_id': user_id,
        'role': role,
        'access_time': time_str
    }