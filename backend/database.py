import bcrypt
from datetime import datetime
from dotenv import load_dotenv
import os
import psycopg2
from psycopg2 import extras
import random
import uuid
from datetime import datetime, timedelta

load_dotenv()  #Load environment variables from .env file

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor_factory = extras.DictCursor
    return conn

def init_roles_table():
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
        #Initial roles insertion
        initial_roles = ['Student', 'Professor', 'Staff', 'Admin']
        for role_name in initial_roles:
            #ON CONFLICT DO NOTHING prevent errors if role already exists
            cur.execute("INSERT INTO roles (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (role_name,))

        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error in init_roles_table: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

def init_users_table():
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
        print(f"Error in init_users_table: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

def init_logs_table():
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
        print(f"Error in init_logs_table: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

# Table to define access rules per role
def init_access_rules_table():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS access_rules (
                id SERIAL PRIMARY KEY,
                role VARCHAR(50) NOT NULL,
                allowed_area VARCHAR(100) NOT NULL
            );
        ''')
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error in init_access_rules_table: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

# Initial access rules insertion
def insert_initial_access_rules():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Example rules
        cur.execute('''
            INSERT INTO access_rules (role, allowed_area) VALUES 
            ('Student', 'Classroom_1'),
            ('Student', 'Library'),
            ('Student', 'Lab_A'),
            ('Professor', 'Classroom_1'),
            ('Professor', 'Library'),
            ('Professor', 'Lab_A'),
            ('Professor', 'Office_1'),
            ('Staff', 'Office_1'),
            ('Staff', 'Server_Room'),
            ('Staff', 'Lab_A'),
            ('Admin', 'ALL');
        ''')
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error in insert_initial_access_rules: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

#Global configurations table
def init_system_config_table():
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
        print(f"Error in init_system_config_table: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

# Insert default configurations
def insert_default_system_config():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO system_config (key_name, value_data) VALUES 
            ('system_lockdown', 'FALSE'),
            ('closed_hours', '23,0,1,2,3,4,5,6')
            ON CONFLICT (key_name) DO NOTHING;
        ''')
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error in insert_default_system_config: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

def init_alert_rules_table():
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
        print(f"Error in init_alert_rules_table: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

def get_all_roles():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM roles ORDER BY name DESC")
        roles = [row['name'] for row in cur.fetchall()]
        return roles
    except Exception as e:
        print(f"Error in get_all_roles: {e}")
        return []
    finally:
        if cur: cur.close()
        if conn: conn.close()

def delete_tables():
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
        print(f"Error in delete_tables: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

def hash_password(password):
     return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(password, hashed):
    try:
        if isinstance(hashed, memoryview):
            hashed = bytes(hashed)
        elif hashed.startswith('\\x'):
            hashed = bytes.fromhex(hashed[2:])
        return bcrypt.checkpw(password.encode('utf-8'), hashed)
    except ValueError as e:
        print(f"❌ Critical Password Validation Error (Invalid Salt/Format): {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error in check_password: {e}")
        return False

def save_user(id, name, email, password, role, qr_image_bytes, timestamp, registered_at):
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
        print(f"Error in update_qr_image: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

def get_user_by_email(email):
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
        if row is None:
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
        print(f"Database error in get_user_by_email: {e}")
        raise e
    finally:
        if cur: cur.close()
        if conn: conn.close()

def update_user(original_email, new_name, new_email, new_role):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            UPDATE users
            SET name = %s, email = %s, role = %s
            WHERE email = %s
        ''', (new_name, new_email, new_role, original_email))
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error in update_user: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

def delete_user_by_email(email):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM users WHERE email = %s', (email,))
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error in delete_user_by_email: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

def verify_password(stored_hash, input_password):
    return stored_hash == hash_password(input_password)