from QR_generation_validation import verify_qr
from pyzbar.pyzbar import decode, ZBarSymbol
import cv2
from dotenv import load_dotenv
import os
from database import get_db_connection
from security_analyzer import predict_anomaly, send_anomaly_alert, load_or_train_model, send_access_denied_alert
import threading
from time import sleep
from security_analyzer import send_anomaly_alert

load_dotenv()  #Load environment variables from .env file

SIGNATURE_KEY = os.getenv("SIGNATURE_KEY").encode('utf-8')  #Ensure the key is in bytes format
CURRENT_AREA = os.getenv("DEVICE_AREA_NAME")

print(f"\n" + "="*40)
print(f" System initialized.")
print(f" Area: {CURRENT_AREA}")

# --- PRE-LOAD THE MODEL ---
# Load or train the security model once at startup to avoid delays during scanning
print("Initializing security model and AI...")
try:
    load_or_train_model() # Load .pkl with the AI model or train if not present
    print("AI model ready.")
except Exception as e:
    print(f"Alert: Could not load AI model {e}")


def check_should_notify_hard_rule(qr_data, target_area):
    """
    Check if invalid access needs to be notified.
    Returns True if an email should be sent.
    """
    if qr_data['valid']:
        return False # If valid, no hard rule violation so no notification

    error_code = qr_data.get('error_code')
    role = qr_data.get('role', 'Unknown')
    
    should_notify = False
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = """
            SELECT id FROM alert_rules 
            WHERE is_active = TRUE
            AND event_type = %s
            AND (role_filter = 'ALL' OR role_filter = %s)
            AND (area_filter = 'ALL' OR area_filter = %s)
            LIMIT 1
        """
        cur.execute(query, (error_code, role, target_area))
        result = cur.fetchone()
        
        if result:
            should_notify = True
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error while checking alert rules: {e}")

    return should_notify

def send_hard_rule_alert(qr_data, target_area):
    """ Sends a specific email for Hard Rules (different from the AI one) """
    
    print(f"📧 SENDING HARD RULE BREAK NOTIFICATION: {qr_data['error_code']}")
    
    log_entry = {
        'user_id': qr_data['user_id'],
        'role': qr_data['role'],
        'area': target_area,
        'access_time': qr_data['access_time'],
        'reason': f"HARD RULE: {qr_data['reason']}"
    }
    
    send_access_denied_alert(log_entry)


def process_access_log_async(qr_data, target_area):
    """
    This function is executed at the background.
    It handles the AI, sending emails and saving to the database.
    This way we don't make the user wait at the door.
    """
    # Extract log entry details
    log_entry = {
        'user_id': qr_data['user_id'],
        'role': qr_data['role'],
        'area': target_area,
        'access_time': qr_data['access_time'],
        'entry_allowed': qr_data['valid'], # Will always be True here as we only analyze valid accesses
        'reason': qr_data['reason']
    }

    risk_score = 0.0
    is_anomaly = False

    # Execute AI analysis
    if qr_data['valid']:
        try:
            risk_score, is_anomaly = predict_anomaly(log_entry)
            
            if is_anomaly:
                print(f"\n[BACKGROUND] SECURITY ALERT: Anomaly detected! Score: {risk_score:.4f}")
                # Send the alert without blocking
                send_anomaly_alert(log_entry, risk_score)
            else:
                print(f"\n[BACKGROUND] AI Analysis: Normal behavior. Score: {risk_score:.4f}")
                
        except Exception as e:
            print(f"Error durant l'anàlisi IA: {e}")
    else:
        # Check if we need to send a hard rule violation alert
        if check_should_notify_hard_rule(qr_data, target_area):
            print("[BACKGROUND] ALERT: Hard rule violation. Needs to be notified.")
            send_hard_rule_alert(qr_data, target_area)
        else:
            print("[BACKGROUND] Access denied but no notification needs to be sent.")

    # Store the log in the database
    # Open the connection inside the thread, as it may not be thread-safe to share connections
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            INSERT INTO logs (user_id, role, area, access_time, entry_allowed, reason, risk_score)
            VALUES (COALESCE(%s, 'unknown'), COALESCE(%s, 'unknown'), %s, %s, %s, %s, %s)
        ''', (
            qr_data['user_id'],
            qr_data['role'],
            target_area,
            qr_data['access_time'],
            int(qr_data['valid']),
            qr_data['reason'],
            float(risk_score) # Store risk score
        ))
        conn.commit()
        cur.close()
        conn.close()
        print("[BACKGROUND] Log correctly stored.")
        
    except Exception as e:
        print(f"Error saving to DB: {e}")

def scan_qr():
    cam = cv2.VideoCapture(0)
    while True:
        ret, frame = cam.read()
        if not ret:
            break

        qr_codes = decode(frame, symbols=[ZBarSymbol.QRCODE]) #Decode QR codes in the frame (not any other type of code)

        #Show the camera frame in a window
        cv2.imshow("QR Scanner - Press ESC to exit", frame)

        #Check for ESC key
        key = cv2.waitKey(1)
        if key == 27:  #ESC key ASCII code
            print("Exiting scanner...")
            break

        if qr_codes:
            content = qr_codes[0].data.decode('utf-8')
            cam.release()
            cv2.destroyAllWindows()
            return content

    cam.release()
    cv2.destroyAllWindows()
    return None


#--- MAIN LOOP ---
while True:

    print(f"--- Active scanner in: {CURRENT_AREA} ---")
    print("Scan the QR code...")
    qr_content = scan_qr()
    if qr_content is None:
        break

    print(f"Read: {qr_content[:10]}...")

    validation_result = verify_qr(qr_content, SIGNATURE_KEY, CURRENT_AREA)

    if validation_result['valid']:
        # Immediate feedback to user
        print("\n" + "="*40)
        print(f" ACCESS GRANTED: {validation_result['role']}")
        print(f" Welcome User {validation_result['user_id']}")
        print("="*40 + "\n")
        # HERE GOES THE DOOR UNLOCKING LOGIC
        
        # ASINCHRONOUS PROCESSING (AI + LOGS)
        # Start a thread to handle the background processing
        bg_thread = threading.Thread(
            target=process_access_log_async, 
            args=(validation_result, CURRENT_AREA)
        )
        bg_thread.start()

    else:
        # Immediate feedback to user
        print("\n" + "x"*40)
        print(f" ACCESS DENIED: {validation_result['reason']}")
        print("x"*40 + "\n")
        
        # Store the failed attempt log asynchronously
        bg_thread = threading.Thread(
            target=process_access_log_async, 
            args=(validation_result, CURRENT_AREA)
        )
        bg_thread.start()
    
    sleep(2)  #Small delay before next scan