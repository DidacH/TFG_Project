from dotenv import load_dotenv
import os
from database import get_db_connection


def view_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    for user in users:
        print(user)
    cur.close()
    conn.close()

def view_logs():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM logs")
    logs = cur.fetchall()
    for log in logs:
        print(log)
    cur.close()
    conn.close()

if __name__ == "__main__":
    print("Current users in the database:")
    view_users()

    print("\n##########################################################\n")

    print("Current logs in the database:")
    view_logs()