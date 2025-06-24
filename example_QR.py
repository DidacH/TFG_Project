import qrcode

qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=10,
    border=4,
)

data = "Example QR Code Data"
qr.add_data(data)
qr.make(fit=True)

# Access the data list and see how it was encoded
# for obj in qr.data_list:
#     print("Data:", obj.data)  # bytes
#     print("Type:", type(obj.data))
#     print("Mode:", obj.mode)  # numeric, alphanumeric, byte, etc.


img = qr.make_image(fill_color="black", back_color="white")
img.show()

