from QR_generation_validation import verify_qr
from pyzbar.pyzbar import decode, ZBarSymbol
import cv2
from dotenv import load_dotenv
import os
from database import get_db_connection

load_dotenv()  #Load environment variables from .env file

SIGNATURE_KEY = os.getenv("SIGNATURE_KEY").encode('utf-8')  #Ensure the key is in bytes format

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





