import sys
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from database import get_db_connection, save_user, init_roles_table, init_users_table, init_logs_table, init_access_rules_table, init_system_config_table, init_alert_rules_table, delete_tables
    from QR_generation_validation import generate_qr
except ImportError as e:
    print(f"Error d'importació: {e}")
    print("Assegura't que la carpeta 'backend' existeix i conté database.py i QR_generation_validation.py")
    sys.exit(1)

SIGNATURE_KEY = os.getenv("SIGNATURE_KEY")
if not SIGNATURE_KEY:
    print("Error: No s'ha trobat SIGNATURE_KEY al fitxer .env")
    sys.exit(1)

SIGNATURE_KEY_BYTES = SIGNATURE_KEY.encode('utf-8')


def create_tables_if_not_exist():
    """
    Defineix l'estructura de la base de dades i crea les taules
    si encara no existeixen. Això permet executar el seed en una DB buida.
    """
    print("   🔨 Verificant/Creant estructura de taules...")

    init_roles_table()
    init_users_table()
    init_logs_table()
    init_access_rules_table()
    init_system_config_table()
    init_alert_rules_table()

def seed_data():
    conn = get_db_connection()
    cur = conn.cursor()

    print("🌱 Iniciant el procés de seed a la base de dades...")

    try:
        delete_tables()
        conn.commit()
        create_tables_if_not_exist()

        # Table cleanup
        print("   🧹 Netejant taules existents...")
        cur.execute("TRUNCATE TABLE logs, users, access_rules, system_config, alert_rules RESTART IDENTITY CASCADE;")
        
        conn.commit()

        # USER CREATION
        print("   👤 Creant usuaris per defecte...")
        
        users_to_create = [
            ("Admin User", "didac.hierro@gmail.com", "1234", "Admin"),
            ("Student User", "student1@uni.edu", "1234", "Student"),
            ("Professor User", "prof1@uni.edu", "1234", "Professor"),
            ("Staff User", "staff1@uni.edu", "1234", "Staff"),
            ("Hacker User", "hacker@evil.com", "1234", "Student") # Attacker simulation
        ]

        for name, email, password, role in users_to_create:
            user_id = str(uuid.uuid4())
            qr_image, last_qr_time = generate_qr(user_id, SIGNATURE_KEY_BYTES)
            registered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            save_user(user_id, name, email, password, role, qr_image, last_qr_time, registered_at)
            print(f"      - Creat: {email} ({role})")

        # ACCESS RULES DEFINITION
        print("   🛡️  Configurant regles d'accés...")
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
            ('maintenance_mode', 'false')
        ]

        cur.executemany(
            "INSERT INTO system_config (key_name, value_data) VALUES (%s, %s)",
            configs
        )

        # NOTIFICATION RULES
        print("   🔔 Configurant regles d'alerta personalitzades...")
        alert_configs = [
            # (Event, Role Filter, Area Filter)
            ('MALFORMED_QR', 'ALL', 'ALL'),     # Always notify malformed QR
            ('FORGED_QR', 'ALL', 'ALL'),        # Always notify forged QR
            ('UNKNOWN_USER', 'ALL', 'ALL'),     # Always notify unknown user
            ('AREA_VIOLATION', 'Student', 'Server_Room'), # Specific alert for students (server room is a restricted area)
            ('TIME_VIOLATION', 'Student', 'ALL')          # Always notify time violations for students
        ]

        cur.executemany(
            "INSERT INTO alert_rules (event_type, role_filter, area_filter) VALUES (%s, %s, %s)",
            alert_configs
        )

        conn.commit()
        print("\n✅ Base de dades poblada correctament!")
        print("   Contrasenya per defecte: '1234'")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error durant el seed: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    # Security confirmation
    confirm = input("Això esborrarà totes les dades actuals de la base de dades. Estàs segur? (s/n): ")
    if confirm.lower() == 's' or confirm.lower() == 'y':
        seed_data()
    else:
        print("Operació cancel·lada.")