import cv2
import requests
from pyzbar.pyzbar import decode, ZBarSymbol
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_HOST", "http://127.0.0.1:5000") + "/api/access/scan"
CURRENT_AREA = os.getenv("DEVICE_AREA_NAME", "Classroom_1")

def scan_and_send():
    cam = cv2.VideoCapture(0)
    print(f"--- Scanner active in {CURRENT_AREA} ---")
    
    while True:
        ret, frame = cam.read()
        if not ret: break
        
        qr_codes = decode(frame, symbols=[ZBarSymbol.QRCODE])
        cv2.imshow("QR Scanner", frame)
        
        if cv2.waitKey(1) == 27: break # ESC
        
        if qr_codes:
            qr_content = qr_codes[0].data.decode('utf-8')
            print(f"QR Detected! Sending to server...")
            
            # Stop camera and send data to server
            try:
                response = requests.post(API_URL, json={
                    "qr_data": qr_content,
                    "area": CURRENT_AREA
                }, timeout=5)
                
                result = response.json()
                if result.get("granted"):
                    print("✅ ACCESS GRANTED!")
                else:
                    print(f"❌ ACCESS DENIED: {result.get('reason')}")
                    
            except requests.exceptions.RequestException as e:
                print(f"⚠️ Error connecting to the server: {e}")
                
            # Little pause to avoid multiple scans of the same QR
            cv2.waitKey(2000) 

    cam.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    scan_and_send()