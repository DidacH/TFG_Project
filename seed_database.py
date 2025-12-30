import bcrypt
from database import get_db_connection

def hash_password(plain_password):
    """Generate a secure hash for the password."""
    # Convert to bytes, generate salt and hash, and return as string for DB storage
    return bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def seed_data():
    conn = get_db_connection()
    cur = conn.cursor()

    print("🌱 Initiating seeding process in the database...")

    try:
        print("   🧹 Cleaning existing tables...")
        cur.execute("TRUNCATE TABLE logs, users, access_rules, system_config RESTART IDENTITY CASCADE;")

        # CREATE DEFAULT USERS
        print("   👤 Creating default users...")
        default_password = hash_password('1234')

        users = [
            # (email, password_hash, role)
            ('admin@uni.edu', default_password, 'Admin'),
            ('student1@uni.edu', default_password, 'Student'),
            ('prof1@uni.edu', default_password, 'Professor'),
            ('staff1@uni.edu', default_password, 'Staff'),
            ('hacker@evil.com', default_password, 'Student') # Attacker simulation
        ]

        cur.executemany(
            "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s)",
            users
        )

        # HARD RULES DEFINITION
        print("   🛡️  Configuring access rules")
        rules = [
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
            ('Admin', 'ALL') # Master access
        ]

        cur.executemany(
            "INSERT INTO access_rules (role, allowed_area) VALUES (%s, %s)",
            rules
        )

        # SYSTEM CONFIGURATIONS
        print("   ⚙️  Establint configuració global...")
        configs = [
            ('closed_hours', '23,0,1,2,3,4,5,6'), # Closed from 11 PM to 7 AM
            ('maintenance_mode', 'false')        # Example of another possible maintenance configuration
        ]

        cur.executemany(
            "INSERT INTO system_config (key_name, value_data) VALUES (%s, %s)",
            configs
        )

        # NOTIFICATION RULES SETUP
        print("   🔔 Configurant regles d'alerta personalitzades...")
        alert_configs = [
            # (Event, Role, Area)

            # Notify always when a malformed QR code is used
            ('MALFORMED_QR', 'ALL', 'ALL'),
            
            # Notify always when a forged QR code is used
            ('FORGED_QR', 'ALL', 'ALL'),

            # Notify always when an unknown user is read in the QR
            ('UNKNOWN_USER', 'ALL', 'ALL'),

            # Notify if student tries to access sensible area (server room)
            ('AREA_VIOLATION', 'Student', 'Server_Room'),
            
            # Notify if student accesses any area during closed hours
            ('TIME_VIOLATION', 'Student', 'ALL')
        ]

        cur.executemany(
            "INSERT INTO alert_rules (event_type, role_filter, area_filter) VALUES (%s, %s, %s)",
            alert_configs
        )

        conn.commit()
        print("\n✅ Database correctly populated!")
        print("   Users created (Password: '1234'):")
        print("   - admin@uni.edu (Admin)")
        print("   - student1@uni.edu (Student)")
        print("   - prof1@uni.edu (Professor)")
        print("   - staff1@uni.edu (Staff)")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error during seeding: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    # Security check before seeding
    confirm = input("This will delete all current data in the database. Are you sure? (y/n): ")
    if confirm.lower() == 'y':
        seed_data()
    else:
        print("Operation cancelled.")