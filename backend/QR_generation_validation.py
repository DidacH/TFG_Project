import qrcode
import hmac, hashlib
import time
import io
from datetime import datetime
from database import get_db_connection
import pytz

# --- CACHE FOR HARD RULES AND CONFIG ---
_RULES_CACHE = None
_CONFIG_CACHE = None
_LAST_CACHE_UPDATE = 0
CACHE_TTL = 60  # Cache Time-To-Live in seconds


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


#Load hard rules and config from DB with caching for efficiency
def load_rules_from_db():
    """Loads access rules and config from the database into cache."""
    global _RULES_CACHE, _CONFIG_CACHE, _LAST_CACHE_UPDATE
    
    current_time = time.time()
    
    # Don't reload if cache is still valid and not empty
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
                'end_time': end_time,     # objecte datetime.time
                'is_active': is_active
            })
            
        
        # Load System Config (e.g., closed hours, lockdown status)
        cur.execute("SELECT key_name, value_data FROM system_config")
        configs = cur.fetchall()
        
        temp_config = {}
        # Parse closed hours
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
        print(f"Error loading rules from DB: {e}")
        # If DB fails, keep old cache or empty if first run
        if _RULES_CACHE is None: _RULES_CACHE = {}
        if _CONFIG_CACHE is None: _CONFIG_CACHE = {}


def verify_qr(content, secret_key, target_area):
    now = int(time.time())

    spain_tz = pytz.timezone('Europe/Madrid')
    current_dt = datetime.now(spain_tz)
    time_str = current_dt.strftime('%Y-%m-%d %H:%M:%S')
    
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

    # Verify signature
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

    # Fetch user role and block status from DB
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

    # Extract role and block status, handling both dict and tuple cases
    role = user['role'] if isinstance(user, dict) or hasattr(user, 'keys') else user[0]
    is_blocked = user['is_blocked'] if isinstance(user, dict) or hasattr(user, 'keys') else user[1]

    # INDIVIDUAL USER BLOCK CHECK
    if is_blocked:
        return {
            'valid': False,
            'error_code': 'USER_BLOCKED',
            'reason': 'User account is blocked',
            'user_id': user_id,
            'role': role,
            'access_time': time_str
        }

    # GLOBAL LOCKDOWN CHECK
    load_rules_from_db()
    is_locked = _CONFIG_CACHE.get('system_lockdown', False)
    
    if is_locked:
        # Exception: Admins can bypass lockdown
        if role != 'Admin':
            return {
                'valid': False, 
                'error_code': 'SYSTEM_LOCKDOWN', 
                'reason': 'System in Lockdown Mode', 
                'user_id': user_id, 
                'role': role, 
                'access_time': time_str
            }

    

    # Check expiration
    expiration_seconds = 30  #seconds
    grace_period = 5  #seconds, for clock skew
    if now - timestamp > expiration_seconds+grace_period:
        return {
            'valid': False,
            'error_code': 'EXPIRED_QR',
            'reason': 'QR code expired',
            'user_id': user_id,
            'role': role,
            'access_time': time_str
        }
    
    # Check role permissions
    load_rules_from_db()
    role_rules = _RULES_CACHE.get(role, [])
    
    current_weekday = current_dt.weekday() # 0 = Monday, 6 = Sunday
    current_time_only = current_dt.time()
    
    has_access = False
    
    # Evaluate all rules for the user's role. If any rule grants access, we allow it (logical OR).
    for rule in role_rules:
        # Skip rule if deactivated
        if not rule.get('is_active', True):
            continue
            
        # Has area permission? (either specific area or ALL)
        area_match = (rule['area'] == 'ALL' or rule['area'] == target_area)
        
        # Are we on an allowed day?
        day_match = (current_weekday in rule['days'])
        
        # Are we within allowed time range?
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

    # Check Global Time (Facility Closed Hours) (specifically closed hours to avoid having to restrict by role)
    # Exception: Admins can access anytime
    if current_dt.hour in _CONFIG_CACHE.get('closed_hours', []) and role != 'Admin':
        return {'valid': False, 'error_code': 'TIME_VIOLATION',  'reason': 'Facilities closed', 'user_id': user_id, 'role': role, 'access_time': time_str}

    return {
        'valid': True,
        'error_code': None,
        'reason': 'Valid access',
        'user_id': user_id,
        'role': role,
        'access_time': time_str
    }