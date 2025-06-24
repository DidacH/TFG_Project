import sqlite3
import hashlib
from datetime import datetime

def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            qr_image BLOB NOT NULL,
            last_qr_time TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def save_user(id, name, email, password, role, qr_image_bytes):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    hashed_pw = hash_password(password)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO users (id, name, email, password, role, qr_image, last_qr_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (id, name, email, hashed_pw, role, qr_image_bytes, now))
    conn.commit()
    conn.close()

def update_qr_image(user_id, qr_bytes):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE users SET qr_image=?, last_qr_time=? WHERE id=?", (qr_bytes, now, user_id))
    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM users WHERE email = ?
    ''', (email,))
    row = cursor.fetchone()
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
        "last_qr_time": row[6],
    }


def verify_password(stored_hash, input_password):
    return stored_hash == hash_password(input_password)
