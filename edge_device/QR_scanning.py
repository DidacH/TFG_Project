import cv2
from pyzbar.pyzbar import decode
import requests
import os
from dotenv import load_dotenv
import time
# from gpiozero import LED

# --- CONFIGURATION ---
load_dotenv()

API_HOST = os.getenv("API_HOST")
DEVICE_AREA_NAME = os.getenv("DEVICE_AREA_NAME", "Unknown")

# green_led = LED(17)
# red_led = LED(27)

# Camera initialization
cap = cv2.VideoCapture(0)
cap.set(3, 640) # Resolution: Width
cap.set(4, 480) # Resolution: Height

print("🟢 Scanner active")
print("Press Ctrl+C to stop the scanner")
print("Scan your QR code...")

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        # Decode QRs
        qrs = decode(frame)
        for qr in qrs:
            qr_data = qr.data.decode('utf-8')
            print(f"\n[+] QR Detected! Data: {qr_data[:20]}...")
            print("Sending data to server to validate...")

            # --- BACKEND CALL ---
            try:
                payload = {"qr_data": qr_data, "area": DEVICE_AREA_NAME}
                response = requests.post(API_HOST, json=payload, timeout=5)

                if response.status_code == 200:
                    result = response.json()

                    if result.get("granted"):
                        print("✅ ACCESS ALLOWED! Opening door...")
                        # green_led.on()
                    else:
                        print(f"❌ ACCESS DENIED! Reason: {result.get('reason', 'Unknown')}")
                        # red_led.on()
                else:
                    print(f"⚠️ Server Error: Code {response.status_code}")

            except Exception as e:
                print(f"⚠️ Connection Error: {e}")

            # Little delay after scanning to keep the door open / avoid multiple scans
            time.sleep(3)

            # green_led.off()
            # red_led.off()

            # Empty the images buffer (read and discard old images)
            for _ in range(10):
                cap.read()

            print("\nScan your QR code...")

            # Exit the for loop to read a new image
            break

except KeyboardInterrupt:
    print("\nStopping scanner manually...")
finally:
    cap.release()
    print("Scanner off.")