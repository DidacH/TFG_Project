import qrcode
import hmac, hashlib
import time
import io

SECRET_KEY = b"secret_key" #Replace with a secure key!

def generate_qr(user_id):
    timestamp = int(time.time())  #current UNIX time
    message = f"{user_id}:{timestamp}"
    signature = hmac.new(SECRET_KEY, message.encode(), hashlib.sha256).hexdigest()
    content = f"{user_id}:{timestamp}:{signature}"
    
    img = qrcode.make(content)

    #Convert image to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes = img_bytes.getvalue()

    return img_bytes, timestamp


def verify_qr(content, expiration_seconds=30):  #QR valid for 30 seconds
    try:
        user_id, timestamp_str, received_signature = content.split(":")
        timestamp = int(timestamp_str)
    except ValueError:
        print("QR code malformed.")
        return False  #Malformed content

    current_time = int(time.time())
    if current_time - timestamp > expiration_seconds:
        print("QR code expired.")
        return False

    message = f"{user_id}:{timestamp}"
    expected_signature = hmac.new(SECRET_KEY, message.encode(), hashlib.sha256).hexdigest()

    return hmac.compare_digest(received_signature, expected_signature)

