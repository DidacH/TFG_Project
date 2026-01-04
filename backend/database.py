import bcrypt
from datetime import datetime
from dotenv import load_dotenv
import os
import psycopg2
from psycopg2 import extras

load_dotenv()  #Load environment variables from .env file

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor_factory = extras.DictCursor
    return conn

def init_roles_table():
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
    cur.close()
    conn.close()

def init_users_table():
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
            registered_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

def init_logs_table():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            user_id TEXT,
            role TEXT,
            area TEXT NOT NULL,
            access_time TEXT NOT NULL,
            entry_allowed INTEGER NOT NULL,
            reason TEXT NOT NULL,
            error_code TEXT,
            risk_score FLOAT DEFAULT 0.0,
            is_reviewed BOOLEAN DEFAULT FALSE,
            is_threat BOOLEAN DEFAULT FALSE
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

# Table to define access rules per role
def init_access_rules_table():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE access_rules (
            id SERIAL PRIMARY KEY,
            role VARCHAR(50) NOT NULL,
            allowed_area VARCHAR(100) NOT NULL
        );
    ''')
    conn.commit()
    cur.close()
    conn.close()

# Initial access rules insertion
def insert_initial_access_rules():
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
    cur.close()
    conn.close()

#Global configurations table
def init_system_config_table():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            key_name VARCHAR(50) PRIMARY KEY,
            value_data VARCHAR(255)
        );
    ''')
    conn.commit()
    cur.close()
    conn.close()

# Insert default configurations
def insert_default_system_config():
    conn = get_db_connection()
    cur = conn.cursor()
    #
    cur.execute('''
        INSERT INTO system_config (key_name, value_data) VALUES 
        ('closed_hours', '23,0,1,2,3,4,5,6');
    ''')
    conn.commit()
    cur.close()
    conn.close()

def init_alert_rules_table():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE alert_rules (
        id SERIAL PRIMARY KEY,
        event_type VARCHAR(50) NOT NULL, -- Ex: 'AREA_VIOLATION', 'TIME_VIOLATION', 'EXPIRED'
        role_filter VARCHAR(50) NOT NULL DEFAULT 'ALL',
        area_filter VARCHAR(100) NOT NULL DEFAULT 'ALL',
        is_active BOOLEAN DEFAULT TRUE
    );
    ''')
    conn.commit()
    cur.close()
    conn.close()
    

def get_all_roles():
    """Obté tots els rols disponibles per al registre."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM roles ORDER BY name DESC")
    roles = [row['name'] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return roles

def delete_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    # DELETE ORDER: logs -> users -> roles
    cur.execute('DROP TABLE IF EXISTS logs CASCADE') 
    cur.execute('DROP TABLE IF EXISTS users CASCADE')
    cur.execute('DROP TABLE IF EXISTS roles CASCADE')
    conn.commit()
    cur.close()
    conn.close()

def hash_password(password):
     return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(password, hashed):
    if isinstance(hashed, memoryview):
        hashed = bytes(hashed)
    return bcrypt.checkpw(password.encode(), hashed)

def save_user(id, name, email, password, role, qr_image_bytes, timestamp, registered_at):
    conn = get_db_connection()
    cur = conn.cursor()
    hashed_pw = hash_password(password)
    cur.execute('''
        INSERT INTO users (id, name, email, password, role, qr_image, last_qr_time, registered_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ''', (id, name, email, hashed_pw, role, qr_image_bytes, timestamp, registered_at))
    conn.commit()
    cur.close()
    conn.close()

def update_qr_image(user_id, qr_bytes):
    conn = get_db_connection()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("UPDATE users SET qr_image=%s, last_qr_time=%s WHERE id=%s", (qr_bytes, now, user_id))
    conn.commit()
    cur.close()
    conn.close()


def get_user_by_email(email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE email = %s', (email,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    
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

def update_user(original_email, new_name, new_email, new_role):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users
        SET name = %s, email = %s, role = %s
        WHERE email = %s
    ''', (new_name, new_email, new_role, original_email))
    conn.commit()
    cursor.close()
    conn.close()
    

def delete_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE email = %s', (email,))
    conn.commit()
    cursor.close()
    conn.close()


def verify_password(stored_hash, input_password):
    return stored_hash == hash_password(input_password)


def get_all_table_names():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    table_names = [row[0] for row in cur.fetchall()] 
    cur.close()
    conn.close()
    print(table_names)


def select_logs():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM logs')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def select_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def select_roles():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM roles')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


if __name__ == "__main__":


    #Tables deletion
    # delete_tables()
    # print("Database tables deleted (users, logs, roles).")
    
    #Tables creation
    # init_roles_table()
    # init_users_table()
    # init_logs_table()
    # print("Database initialized.")

    # print(select_logs())
    # print(select_logs())
    # print(select_users())
    # print(select_roles())
    

    get_all_table_names()