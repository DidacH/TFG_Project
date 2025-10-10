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

def delete_table():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS users CASCADE')
    conn.commit()
    cur.close()
    conn.close()

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password BYTEA NOT NULL,
            role TEXT NOT NULL,
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
            user_id TEXT NOT NULL,
            role TEXT,
            room TEXT NOT NULL,
            access_time TEXT NOT NULL,
            entry_allowed INTEGER NOT NULL,
            reason TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

def delete_logs():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS logs CASCADE')
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

if __name__ == "__main__":
    
    #Tables creation
    init_db()
    init_logs_table()
    print("Database initialized.")

    #Tables deletion
    # delete_table()
    # delete_logs()
    # print("Tables deleted.")
