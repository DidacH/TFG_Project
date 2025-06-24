from QR_generation_validation import verify_qr

def corrupt_qr_user_id(original_content, fake_user_id="FAKE-ID-1234"):
    try:
        _, timestamp, signature = original_content.split(":")
    except ValueError:
        print("Invalid QR content format.")
        return None

    #Replace the user_id but leave the original timestamp and signature
    tampered_content = f"{fake_user_id}:{timestamp}:{signature}"
    return tampered_content

def tamper_qr_timestamp(original_content, new_timestamp):
    try:
        user_id, _, signature = original_content.split(":")
    except ValueError:
        print("Invalid QR content format.")
        return None

    #Replace the timestamp but keep the original user_id and signature
    tampered_content = f"{user_id}:{new_timestamp}:{signature}"
    return tampered_content



if __name__ == "__main__":
    print("Security Testing Module")
    print("This module tests the integrity of QR codes by tampering with their contents.\n")


    #This is an actual QR code content generated from generate_qr()
    real_qr = "44c9dcd4-aa43-4619-9e15-2fc7ced77c2c:1750679494:d72062d20e426ce4c744bf2b7c3a63d3a39d304cf84b9e1328f8b1f1bd60d08d"

    #Test 1: Corrupt the user_id
    tampered_id = corrupt_qr_user_id(real_qr)
    print("\n[TEST 1] Tampered QR content (user ID):", tampered_id)
    print("Is valid?", verify_qr(tampered_id))  #Should be False

    #Test 2: Change the timestamp (extend validity)
    fake_timestamp = 9999999999  #Far future
    tampered_time = tamper_qr_timestamp(real_qr, fake_timestamp)
    print("\n[TEST 2] Tampered QR content (timestamp):", tampered_time)
    print("Is valid?", verify_qr(tampered_time))  #Should be False





