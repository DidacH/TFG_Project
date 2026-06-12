import os
import bcrypt
import psycopg2
from psycopg2 import extras
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# =================================================
# === CORE CONNECTION MANAGEMENT ===
# =================================================

def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor_factory = extras.DictCursor
    return conn


# =================================================
# === DATABASE INITIALIZATION & SEEDING ===
# =================================================

def initialize_database():
    """
    Master initialization function.
    Creates all required tables if they do not exist and populates
    essential default data (roles, system configs, default access rules).
    Ensures the database is ready for application startup.
    """
    init_roles_table()
    init_users_table()
    init_logs_table()
    init_access_rules_table()
    init_system_config_table()
    init_alert_rules_table()

    # Seed initial required data if tables are empty
    insert_default_system_config()
    insert_initial_access_rules()
    insert_initial_alert_rules()


def init_roles_table():
    """Initializes the roles table and inserts default system roles."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS roles (
                name TEXT PRIMARY KEY
            );
        ''')
        
        # Ensure default roles exist without duplicating
        initial_roles = ['Student', 'Professor', 'Staff', 'Admin']
        for role_name in initial_roles:
            cur.execute("INSERT INTO roles (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (role_name,))

        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"[DB ERROR] init_roles_table: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()


def init_users_table():
    """Initializes the main users table with foreign key reference to roles."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password BYTEA NOT NULL,
                role TEXT NOT NULL REFERENCES roles(name) ON DELETE RESTRICT,
                qr_image BYTEA NOT NULL,
                last_qr_time TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                is_blocked BOOLEAN DEFAULT FALSE
            )
        ''')
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"[DB ERROR] init_users_table: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()


def init_logs_table():
    """Initializes the audit logs table for access tracking and AI anomaly results."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                user_id TEXT,
                role TEXT,
                area TEXT NOT NULL,
                access_time TIMESTAMP NOT NULL,
                entry_allowed BOOLEAN DEFAULT TRUE,
                reason TEXT NOT NULL,
                error_code TEXT,
                risk_score FLOAT DEFAULT 0.0,
                is_reviewed BOOLEAN DEFAULT FALSE,
                is_threat BOOLEAN DEFAULT FALSE,
                is_anomaly BOOLEAN DEFAULT FALSE,
                ai_explanation TEXT DEFAULT NULL
            )
        ''')
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"[DB ERROR] init_logs_table: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()


def init_access_rules_table():
    """Initializes the dynamic role-based access rules table."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS access_rules (
                id SERIAL PRIMARY KEY,
                role VARCHAR(50) NOT NULL,
                allowed_area VARCHAR(100) NOT NULL,
                allowed_days VARCHAR(50) DEFAULT '0,1,2,3,4,5,6',
                start_time TIME DEFAULT '00:00:00',
                end_time TIME DEFAULT '23:59:59',
                is_active BOOLEAN DEFAULT TRUE
            );
        ''')
        
        # Safe schema migration for older database versions
        try:
            cur.execute("ALTER TABLE access_rules ADD COLUMN IF NOT EXISTS allowed_days VARCHAR(50) DEFAULT '0,1,2,3,4,5,6'")
            cur.execute("ALTER TABLE access_rules ADD COLUMN IF NOT EXISTS start_time TIME DEFAULT '00:00:00'")
            cur.execute("ALTER TABLE access_rules ADD COLUMN IF NOT EXISTS end_time TIME DEFAULT '23:59:59'")
            cur.execute("ALTER TABLE access_rules ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
        except Exception:
            pass # Ignore if columns already exist

        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"[DB ERROR] init_access_rules_table: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()


def insert_initial_access_rules():
    """Seeds basic access rules if the table is completely empty."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM access_rules")
        if cur.fetchone()[0] == 0:
            cur.execute('''
                INSERT INTO access_rules (role, allowed_area, allowed_days, start_time, end_time, is_active) VALUES 
                ('Student', 'Classroom_1', '0,1,2,3,4', '08:00:00', '20:00:00', TRUE),
                ('Student', 'Library', '0,1,2,3,4,5', '08:00:00', '21:00:00', TRUE),
                ('Professor', 'Classroom_1', '0,1,2,3,4,5', '07:00:00', '22:00:00', TRUE),
                ('Admin', 'ALL', '0,1,2,3,4,5,6', '00:00:00', '23:59:59', TRUE);
            ''')
            conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"[DB ERROR] insert_initial_access_rules: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()


def init_system_config_table():
    """Initializes key-value configuration table for dynamic global parameters."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS system_config (
                key_name VARCHAR(50) PRIMARY KEY,
                value_data VARCHAR(255)
            );
        ''')
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"[DB ERROR] init_system_config_table: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()


def insert_default_system_config():
    """Seeds required default global variables."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO system_config (key_name, value_data) VALUES 
            ('system_lockdown', 'false'),
            ('closed_hours', '23,0,1,2,3,4,5,6'),
            ('anomaly_threshold', '-0.025')
            ON CONFLICT (key_name) DO NOTHING;
        ''')
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"[DB ERROR] insert_default_system_config: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()


def init_alert_rules_table():
    """Initializes trigger definitions for automated email alerts."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS alert_rules (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(50) NOT NULL,
                role_filter VARCHAR(50) NOT NULL DEFAULT 'ALL',
                area_filter VARCHAR(100) NOT NULL DEFAULT 'ALL',
                is_active BOOLEAN DEFAULT TRUE
            );
        ''')
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"[DB ERROR] init_alert_rules_table: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()


def insert_initial_alert_rules():
    """Seeds standard notification rules if the table is empty."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM alert_rules")
        if cur.fetchone()[0] == 0:
            alert_configs = [
                ('MALFORMED_QR', 'ALL', 'ALL', True),
                ('FORGED_QR', 'ALL', 'ALL', True),
                ('UNKNOWN_USER', 'ALL', 'ALL', True),
                ('AREA_VIOLATION', 'Student', 'Server_Room', True),
                ('TIME_VIOLATION', 'Student', 'ALL', True)
            ]
            cur.executemany(
                "INSERT INTO alert_rules (event_type, role_filter, area_filter, is_active) VALUES (%s, %s, %s, %s)",
                alert_configs
            )
            conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"[DB ERROR] insert_initial_alert_rules: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()


# =================================================
# === DATA RETRIEVAL & MANAGEMENT ===
# =================================================

def get_all_roles():
    """Returns a list of all existing roles."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM roles ORDER BY name DESC")
        return [row['name'] for row in cur.fetchall()]
    except Exception as e:
        print(f"[DB ERROR] get_all_roles: {e}")
        return []
    finally:
        if cur: cur.close()
        if conn: conn.close()


def hash_password(password):
    """Hashes a plaintext password utilizing bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())


def check_password(password, hashed):
    """Validates a plaintext password against a stored bcrypt hash safely."""
    try:
        if isinstance(hashed, memoryview):
            hashed = bytes(hashed)
        elif hashed.startswith('\\x'):
            hashed = bytes.fromhex(hashed[2:])
        return bcrypt.checkpw(password.encode('utf-8'), hashed)
    except ValueError as e:
        print(f"[DB ERROR] Password Validation Error (Invalid Salt/Format): {e}")
        return False
    except Exception as e:
        print(f"[DB ERROR] check_password: {e}")
        return False


def save_user(id, name, email, password, role, qr_image_bytes, timestamp, registered_at):
    """Creates a new user record in the database."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        hashed_pw = hash_password(password)
        
        cur.execute('''
            INSERT INTO users (id, name, email, password, role, qr_image, last_qr_time, registered_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (id, name, email, hashed_pw, role, qr_image_bytes, timestamp, registered_at))
        
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        raise e 
    finally:
        if cur: cur.close()
        if conn: conn.close()


def update_qr_image(user_id, qr_bytes):
    """Updates the QR code bytes and timestamp for a specific user."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("UPDATE users SET qr_image=%s, last_qr_time=%s WHERE id=%s", (qr_bytes, now, user_id))
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"[DB ERROR] update_qr_image: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()


def get_user_by_email(email):
    """Fetches full user details mapped by their email address."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT id, name, email, password, role, qr_image, last_qr_time 
            FROM users 
            WHERE email = %s
        ''', (email,))
        
        row = cur.fetchone()
        if not row:
            return None

        return {
            'id': row[0],
            'name': row[1],
            'email': row[2],
            'password': row[3],
            'role': row[4],
            'qr_image': row[5],
            'last_qr_time': row[6],
        }
    except Exception as e:
        print(f"[DB ERROR] get_user_by_email: {e}")
        raise e
    finally:
        if cur: cur.close()
        if conn: conn.close()


def delete_user_by_email(email):
    """Permanently deletes a user based on their email."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM users WHERE email = %s', (email,))
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"[DB ERROR] delete_user_by_email: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()


# =================================================
# === UTILITY FUNCTIONS (For Admin/Testing) ===
# =================================================

def delete_tables():
    """WARNING: Destroys all tables in the database. Used only for resets."""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DROP TABLE IF EXISTS logs CASCADE') 
        cur.execute('DROP TABLE IF EXISTS users CASCADE')
        cur.execute('DROP TABLE IF EXISTS roles CASCADE')
        cur.execute('DROP TABLE IF EXISTS access_rules CASCADE')
        cur.execute('DROP TABLE IF EXISTS system_config CASCADE')
        cur.execute('DROP TABLE IF EXISTS alert_rules CASCADE')
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"[DB ERROR] delete_tables: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()