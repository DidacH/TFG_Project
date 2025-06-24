from QR_generation_validation import generate_qr
from database import save_user, get_user_by_email, init_db, verify_password, update_qr_image
import uuid
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import io
from datetime import datetime
import re

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"
PASSWORD_REGEX = r"^(?=.*[0-9])(?=.*[\W_]).{4,}$"
NAME_REGEX = r"^(?!.*[ '\u2019]{2})(?!.*^[ '\u2019])([A-Za-zÀ-ÿ\u00C0-\u017F'\u2019]+(?: [A-Za-zÀ-ÿ\u00C0-\u017F'\u2019]+)*)$"


def generate_unique_id():
    return str(uuid.uuid4())

def register_user(name, email, role, password):
    email = email.strip().lower()
    name = name.strip()

    user_id = generate_unique_id()
    qr_pil_image = generate_qr(user_id)
    buffer = io.BytesIO()
    qr_pil_image.save(buffer, format="PNG")
    qr_image_bytes = buffer.getvalue()

    save_user(user_id, name, email, password, role, qr_image_bytes)

    messagebox.showinfo("Success", "User registered successfully!")


def login_user(email, password):
    email = email.strip().lower()
    user = get_user_by_email(email)
    if not user:
        print("User not found for:", email)
        messagebox.showerror("Login Error", "Invalid email or password.")
        return

    if not verify_password(user['password'], password):
        print("Password mismatch for:", email)
        messagebox.showerror("Login Error", "Invalid email or password.")
        return

    show_profile(user)


def show_registration():
    clear_frame()

    #Name
    tk.Label(root, text="Name (max 20 characters):").pack(pady=(10, 0))
    name_entry = tk.Entry(root, width=40)
    name_entry.pack()
    name_error = tk.Label(root, text="", fg="red")
    name_error.pack()

    #Email
    tk.Label(root, text="Email:").pack(pady=(10, 0))
    email_entry = tk.Entry(root, width=40)
    email_entry.pack()
    email_error = tk.Label(root, text="", fg="red")
    email_error.pack()

    #Password
    tk.Label(root, text="Password (min 4 chars, 1 number, 1 special char):").pack(pady=(10, 0))
    password_entry = tk.Entry(root, show="*", width=40)
    password_entry.pack()
    password_strength = tk.Label(root, text="", fg="orange")
    password_strength.pack()

    #Role
    tk.Label(root, text="Role:").pack(pady=(10, 0))
    role_combobox = ttk.Combobox(root, values=[], state="readonly")
    role_combobox.pack()
    role_error = tk.Label(root, text="", fg="red")
    role_error.pack()

    #Validation functions
    def validate_name(event=None):
        name = name_entry.get().strip()
        if not re.match(NAME_REGEX, name):
            name_error.config(text="Invalid name format.")
            return False
        name_error.config(text="")
        return True

    def update_role_options_from_email(email):
        email = email.strip().lower()
        is_student_email = email.endswith("@estudiant.upf.edu")
        is_upf_email = email.endswith("@upf.edu")

        if is_student_email:
            valid_roles = ["student"]
        elif is_upf_email:
            valid_roles = ["professor", "staff"]
        else:
            valid_roles = ["student", "professor", "staff"]

        current_values = role_combobox["values"]
        if current_values != valid_roles:
            role_combobox["values"] = valid_roles
            if role_combobox.get() not in valid_roles:
                role_combobox.set("")

    def validate_email(event=None):
        email = email_entry.get().strip().lower()
        if not re.match(EMAIL_REGEX, email):
            email_error.config(text="Invalid email format.")
            update_role_options_from_email(email)
            return False
        if get_user_by_email(email):
            email_error.config(text="Email already registered.")
            update_role_options_from_email(email)
            return False

        email_error.config(text="")
        update_role_options_from_email(email)
        return True

    def validate_password_strength(event=None):
        password = password_entry.get()

        if not re.match(PASSWORD_REGEX, password):
            password_strength.config(text="Invalid password.", fg="red")
            return False

        if len(password) < 6:
            password_strength.config(text="Weak password.", fg="orange")
            return True
        elif 6 <= len(password) <= 10:
            password_strength.config(text="Moderate password.", fg="goldenrod")
            return True
        else:
            password_strength.config(text="Strong password.", fg="green")
            return True

    def validate_role():
        role = role_combobox.get()
        if role not in role_combobox["values"]:
            role_error.config(text="Please select a valid role.")
            return False
        role_error.config(text="")
        return True

    # Event bindings
    name_entry.bind("<FocusOut>", validate_name)
    password_entry.bind("<KeyRelease>", validate_password_strength)
    email_entry.bind("<FocusOut>", validate_email)
    email_entry.bind("<KeyRelease>", lambda e: update_role_options_from_email(email_entry.get()))
    
    # Ensures correct role options appear immediately when combobox is clicked
    role_combobox.bind("<Button-1>", lambda e: update_role_options_from_email(email_entry.get()))

    def on_submit():
        name_valid = validate_name()
        email_valid = validate_email()
        password_valid = validate_password_strength()
        role_valid = validate_role()

        if not (name_valid and email_valid and password_valid and role_valid):
            return

        name = name_entry.get().strip()
        email = email_entry.get().strip().lower()
        password = password_entry.get().strip()
        role = role_combobox.get()

        user_id = generate_unique_id()
        qr_pil_image = generate_qr(user_id)
        buffer = io.BytesIO()
        qr_pil_image.save(buffer, format="PNG")
        qr_image_bytes = buffer.getvalue()

        save_user(user_id, name, email, password, role, qr_image_bytes)
        messagebox.showinfo("Success", "User registered successfully!")
        show_main_menu()

    tk.Button(root, text="Submit Registration", command=on_submit).pack(pady=20)
    tk.Button(root, text="Back to Menu", command=show_main_menu).pack(pady=(0, 10))




def show_login():
    clear_frame()

    tk.Label(root, text="Email:").pack(pady=(20, 0))
    email_entry = tk.Entry(root, width=40)
    email_entry.pack()

    tk.Label(root, text="Password:").pack(pady=(10, 0))
    password_entry = tk.Entry(root, show="*", width=40)
    password_entry.pack()

    def on_login():
        email = email_entry.get().strip()
        password = password_entry.get().strip()

        if not email or not password:
            messagebox.showerror("Input Error", "Please fill in all fields.")
            return

        login_user(email, password)

    tk.Button(root, text="Login", command=on_login).pack(pady=20)

QR_REFRESH_INTERVAL = 30  #seconds


def show_profile(user):
    clear_frame()

    tk.Label(root, text=f"Name: {user['name']}").pack(pady=(10, 0))
    tk.Label(root, text=f"Email: {user['email']}").pack()
    tk.Label(root, text=f"Role: {user['role']}").pack()

    qr_label = tk.Label(root)
    qr_label.pack(pady=10)

    countdown_label = tk.Label(root, text="")
    countdown_label.pack()

    #Extract timestamp from DB if stored, else set current time
    last_qr_time = user.get("last_qr_time")  # should be saved to DB
    if not last_qr_time:
        last_qr_time = datetime.now()
    else:
        last_qr_time = datetime.strptime(last_qr_time, "%Y-%m-%d %H:%M:%S")

    countdown_job = None  #to cancel if needed

    def update_qr_and_restart():
        nonlocal last_qr_time
        last_qr_time = datetime.now()

        #Generate new QR
        qr_pil_image = generate_qr(user['id'])

        #Convert to bytes and update DB
        buffer = io.BytesIO()
        qr_pil_image.save(buffer, format="PNG")
        qr_bytes = buffer.getvalue()
        update_qr_image(user['id'], qr_bytes)
        user['qr_image'] = qr_bytes

        #Update displayed image
        qr_img = Image.open(io.BytesIO(qr_bytes)).resize((200, 200))
        tk_img = ImageTk.PhotoImage(qr_img)
        qr_label.configure(image=tk_img)
        qr_label.image = tk_img

        #Also store updated timestamp in user object
        user["last_qr_time"] = last_qr_time.strftime("%Y-%m-%d %H:%M:%S")

    def countdown():
        nonlocal countdown_job
        now = datetime.now()
        elapsed = (now - last_qr_time).total_seconds()
        remaining = max(0, int(QR_REFRESH_INTERVAL - elapsed))

        countdown_label.config(text=f"QR refreshes in {remaining} seconds")

        if remaining == 0:
            update_qr_and_restart()
        countdown_job = root.after(1000, countdown)

    #Initial display of QR from DB
    qr_img = Image.open(io.BytesIO(user['qr_image'])).resize((200, 200))
    tk_img = ImageTk.PhotoImage(qr_img)
    qr_label.configure(image=tk_img)
    qr_label.image = tk_img

    countdown()  #Start countdown

    def on_back():
        if countdown_job:
            root.after_cancel(countdown_job)
        show_main_menu()

    tk.Button(root, text="Back to Menu", command=on_back).pack(pady=10)



def show_main_menu():
    clear_frame()
    tk.Label(root, text="Choose an option:").pack(pady=20)
    tk.Button(root, text="Register", command=show_registration).pack(pady=10)
    tk.Button(root, text="Login", command=show_login).pack(pady=10)

def clear_frame():
    for widget in root.winfo_children():
        widget.destroy()


if __name__ == "__main__":
    init_db()

    root = tk.Tk()
    root.title("User System")
    root.geometry("400x400")
    root.resizable(False, False)

    show_main_menu()

    root.mainloop()
