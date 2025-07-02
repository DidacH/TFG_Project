import sqlite3
from dotenv import load_dotenv
import os

load_dotenv()  #Load environment variables from .env file

DATABASE = os.getenv("DATABASE_PATH", "instance/database.db")

def view_users():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    for user in users:
        print(user)
    conn.close()

def view_logs():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM logs")
    logs = cursor.fetchall()
    for log in logs:
        print(log)
    conn.close()

if __name__ == "__main__":
    print("Current users in the database:")
    view_users()

    print("\n##########################################################\n")

    print("Current logs in the database:")
    view_logs()