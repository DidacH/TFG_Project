from QR_generation_validation import verify_qr
from pyzbar.pyzbar import decode, ZBarSymbol
import cv2
from dotenv import load_dotenv
import os
from database import get_db_connection
from security_analyzer import predict_anomaly, send_anomaly_alert, train_security_model
import threading

load_dotenv()  #Load environment variables from .env file

SIGNATURE_KEY = os.getenv("SIGNATURE_KEY").encode('utf-8')  #Ensure the key is in bytes format

# --- PRE-LOAD THE MODEL ---
# Load or train the security model once at startup to avoid delays during scanning
print("Initializing security model and AI...")
try:
    train_security_model() # Or load existing model (.pkl)
    print("AI model ready.")
except Exception as e:
    print(f"Alert: Could not load AI model {e}")


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


while True:
    print("Scanning for QR Code... (press ESC to quit)")
    result = scan_qr()
    if result is None:
        break

    print("QR Code Content:", result)

    area = input("Enter target area for access attempt (e.g., Classroom_1, Server_Room): ")
    
    data = verify_qr(result, SIGNATURE_KEY, area)

    #Log the attempt
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO logs (user_id, role, area, access_time, entry_allowed, reason)
        VALUES (COALESCE(%s, 'unknown'), COALESCE(%s, 'unknown'), %s, %s, %s, %s)
    ''', (
        data['user_id'],
        data['role'],
        area,
        data['access_time'],
        int(data['valid']),
        data['reason']
    ))
    conn.commit()
    cur.close()
    conn.close()

    #Notify user
    if data['valid']:
        print("Access Granted!")
    else:
        print(f"Invalid QR Code: {data['reason']}")

    





