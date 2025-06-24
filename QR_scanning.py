from QR_generation_validation import verify_qr
from pyzbar.pyzbar import decode, ZBarSymbol
import cv2

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

    # Example: call your validation function
    is_valid = verify_qr(result)
    if not is_valid:
        print("Invalid QR Code!")
    else:
        print("QR Code scanned successfully!")





