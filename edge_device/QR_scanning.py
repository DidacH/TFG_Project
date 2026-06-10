import cv2
from pyzbar.pyzbar import decode, ZBarSymbol
import requests
import time
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()

# Environment Variables
API_HOST = os.getenv("API_HOST", "http://localhost:5000/api/access/scan")
DEVICE_AREA_NAME = os.getenv("DEVICE_AREA_NAME", "Unknown")
USE_LEDS = os.getenv("USE_LEDS", "false").lower() == "true"

# --- HARDWARE INITIALIZATION ---
if USE_LEDS:
    try:
        from gpiozero import LED
        # LED configuration (Physical Pins 11 and 13)
        green_led = LED(17)
        red_led = LED(27)
    except Exception as e:
        print(f"⚠️ Error initializing GPIO: {e}. Switching to Dummy LEDs.")
        USE_LEDS = False

if not USE_LEDS:
    class DummyLED:
        def on(self): pass
        def off(self): pass
    green_led = DummyLED()
    red_led = DummyLED()

# Camera initialization
cap = cv2.VideoCapture(0)
cap.set(3, 640) # Resolution: Width
cap.set(4, 480) # Resolution: Height

print(f"🟢 Scanner active for area: [{DEVICE_AREA_NAME}]")
print(f"🔗 API Host: {API_HOST}")
print("Press Ctrl+C to stop the scanner")
print("Scan your QR code...")

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        # QR decodification
        qrs = decode(frame, symbols=[ZBarSymbol.QRCODE])
        for qr in qrs:
            qr_data = qr.data.decode('utf-8')
            print("\nQR Detected!")
            print("Sending data to server to validate...")

            # --- BACKEND CALL ---
            try:
                payload = {"qr_data": qr_data, "area": DEVICE_AREA_NAME}
                response = requests.post(API_HOST, json=payload, timeout=5)

                if response.status_code == 200:
                    result = response.json()

                    if result.get("granted"):
                        print(f"✅ ACCESS ALLOWED! Welcome to {DEVICE_AREA_NAME}.")
                        green_led.on()
                        time.sleep(3)  # Maintain LED (door) open 3 seconds. Also prevents multiple scans
                        if USE_LEDS:
                            green_led.off()
                    else:
                        print(f"❌ ACCESS DENIED! Reason: {result.get('reason', 'Unknown')}")
                        red_led.on()
                        time.sleep(3)  # Error signal during 3 seconds
                        red_led.off()
                else:
                    print(f"⚠️ Server Error: Code {response.status_code}")

            except Exception as e:
                print(f"⚠️ Connection Error: {e}")

            # Empty the images buffer to avoid processing old images
            for _ in range(10):
                cap.read()

            print("\nScan your QR code...")

            # break for loop
            break

except KeyboardInterrupt:
    print("\nStopping scanner manually...")
finally:
    # Free resources
    cap.release()
    green_led.off()
    red_led.off()
    print("Scanner off.")