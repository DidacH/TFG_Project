from QR_generation_validation import verify_qr
from pyzbar.pyzbar import decode, ZBarSymbol
import cv2
import sqlite3

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
    data = verify_qr(result)

    room = "room_1"

    #Log the attempt
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO logs (user_id, email, role, room, access_time, entry_allowed, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['user_id'],
        data['email'],
        data['role'],
        room,
        data['access_time'],
        int(data['valid']),
        data['reason']
    ))
    conn.commit()
    conn.close()

    #Notify user
    if data['valid']:
        print("QR Code scanned successfully!")
    else:
        print(f"Invalid QR Code: {data['reason']}")





