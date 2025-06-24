import sqlite3

def view_users():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    for user in users:
        print(user)
    conn.close()

if __name__ == "__main__":
    print("Current users in the database:")
    view_users()
