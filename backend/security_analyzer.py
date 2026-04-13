import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder, StandardScaler
from database import get_db_connection
import numpy as np
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from psycopg2 import extras
import pickle
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

# --- SMTP CONFIGURATION ---
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# --- Model and Preprocessing ---
MODEL_FILE = 'security_model_data.pkl'
model = None
scaler = None
label_encoders = {}
FEATURE_COLUMNS = ['role_encoded', 'area_encoded', 'hour', 'weekday', 'is_admin', 'time_since_last_access', 'access_frequency_1h']
raw_threshold = os.getenv("ANOMALY_THRESHOLD", "-0.15") # Threshold for flagging anomalies

try:
    # Convert to float
    ANOMALY_THRESHOLD = float(raw_threshold)
    print(f"Anomaly threshold set to {ANOMALY_THRESHOLD}")
except ValueError:
    print(f"⚠️ Error: The value '{raw_threshold}' in .env isn't valid. Using -0.15 default threshold.")
    ANOMALY_THRESHOLD = -0.15

def save_model_artifacts():
    """Save the model, scaler, and encoders to file."""
    artifacts = {
        'model': model,
        'scaler': scaler,
        'label_encoders': label_encoders
    }
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump(artifacts, f)
    print(f"Model and artifacts stored in {MODEL_FILE}")

def preprocess_data(df, is_training=False):
    """
    Feature engineering and scaling.
    Calculates time-based features and encodes categories.
    """
    global label_encoders, scaler
    
    # Basic time features
    df['access_time'] = pd.to_datetime(df['access_time'])
    df['hour'] = df['access_time'].dt.hour
    df['weekday'] = df['access_time'].dt.dayofweek
    
    # is_admin feature to distinguish admin users (who have more flexible access patterns)
    df['is_admin'] = df['role'].apply(lambda x: 1 if x == 'Admin' else 0)

    # Encoding (Role & Area)
    for col in ['role', 'area']:
        encoder = label_encoders.get(col, LabelEncoder())
        if is_training:
            df[f'{col}_encoded'] = encoder.fit_transform(df[col])
            label_encoders[col] = encoder
        else:
            # Handle unknown labels during prediction
            df[f'{col}_encoded'] = df[col].apply(
                lambda x: encoder.transform([x])[0] if x in encoder.classes_ else len(encoder.classes_)
            )

    # Scaling numerical features
    cols_to_scale = ['hour', 'weekday', 'time_since_last_access', 'access_frequency_1h']
    if is_training:
        scaler = StandardScaler()
        df[cols_to_scale] = scaler.fit_transform(df[cols_to_scale])
    else:
        df[cols_to_scale] = scaler.transform(df[cols_to_scale])

    return df

def train_security_model(dataset: pd.DataFrame):
    """
    Trains the Isolation Forest using a provided DataFrame.
    The dataset should include: role, area, access_time, time_since_last_access, access_frequency_1h.
    """
    global model
    
    print("Starting security model training...")
    df_processed = preprocess_data(dataset, is_training=True)
    
    X_train = df_processed[FEATURE_COLUMNS]
    
    model = IsolationForest(contamination='auto', random_state=42)
    model.fit(X_train)
    
    save_model_artifacts()
    print("Security model trained successfully.")

def load_or_train_model():
    """Loads existing model or triggers training if missing."""
    global model, scaler, label_encoders
    if os.path.exists(MODEL_FILE):
        try:
            with open(MODEL_FILE, 'rb') as f:
                artifacts = pickle.load(f)
            model = artifacts['model']
            scaler = artifacts['scaler']
            label_encoders = artifacts['label_encoders']
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
    return False

def get_user_history_features(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT access_time FROM logs WHERE user_id = %s ORDER BY access_time::timestamp DESC LIMIT 1", (user_id,))
        last_row = cur.fetchone()
        time_since = 3600 
        if last_row:
            db_time = pd.to_datetime(last_row[0])
            diff = datetime.now() - db_time
            time_since = diff.total_seconds()
            
        one_hour_ago = datetime.now() - timedelta(hours=1)
        cur.execute("SELECT COUNT(*) FROM logs WHERE user_id = %s AND access_time::timestamp > %s", (user_id, one_hour_ago))
        count_1h = cur.fetchone()[0]
        
        return time_since, count_1h
    finally:
        cur.close()
        conn.close()

def predict_anomaly(log_entry, provided_features=None):
    global model
    if not model:
        if not load_or_train_model():
            return 0.0, False 

    # Use CSV data features if provided (for testing), otherwise fetch from DB
    if provided_features:
        time_since = provided_features['time_since_last_access']
        count_1h = provided_features['access_frequency_1h']
    else:
        time_since, count_1h = get_user_history_features(log_entry['user_id'])
    
    log_df = pd.DataFrame([log_entry])
    log_df['time_since_last_access'] = time_since
    log_df['access_frequency_1h'] = count_1h
    
    log_processed = preprocess_data(log_df, is_training=False)
    X_predict = log_processed[FEATURE_COLUMNS]

    score = model.decision_function(X_predict)[0]
    is_anomaly = score < ANOMALY_THRESHOLD
    
    return score, is_anomaly

def get_admin_emails():
    """Fetches a list of emails for all users with the 'Admin' role."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT email FROM users WHERE role = 'Admin'")
        # fetchall returns a tuple list. We extract the first element of each tuple.
        emails = [row[0] for row in cur.fetchall()]
        return emails
    except Exception as e:
        print(f"Error fetching admin emails: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def send_anomaly_alert(log_entry, score):
    """ Sends an email to ALL administrators in case of an anomaly. """
    
    # Obtain admin emails from the database
    admin_emails = get_admin_emails()
    
    if not admin_emails:
        print("ALERT: Anomaly detected but NO ADMINS found in database.")
        return

    subject = f"SUSPICIOUS ACCESS ALERT: Score {score:.4f}"
    
    # HTML Body
    body_html = f"""
        <html>
        <body>
            <h2 style="color:red;">Access Anomaly Detected</h2>
            <p>An anomalous access log was recorded by the security model:</p>
            <ul>
                <li><strong>User ID:</strong> {log_entry.get('user_id')}</li>
                <li><strong>Role:</strong> {log_entry.get('role')}</li>
                <li><strong>Area:</strong> {log_entry.get('area')}</li>
                <li><strong>Access Time:</strong> {log_entry.get('access_time')}</li>
                <li><strong>Reason:</strong> {log_entry.get('reason', 'AI Detected Anomaly')}</li>
            </ul>
            <p><strong>Risk Score:</strong> {score:.4f}</p>
        </body>
        </html>
    """

    # --- EMAIL SENDING ---
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['Subject'] = subject
        msg['To'] = ", ".join(admin_emails)
        
        msg.attach(MIMEText(body_html, 'html'))

        # Connect to Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=3)
        server.starttls() # Secure encryption
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        
        # Send the email to all admins
        text = msg.as_string()
        server.sendmail(SMTP_EMAIL, admin_emails, text)
        
        server.quit()
        
    except Exception as e:
        print(f"❌ Error sending email via Gmail: {e}")


def send_access_denied_alert(log_entry):
    """ Sends an email to ALL administrators in case of a Hard Rule violation. """
    # Obtain admin emails from the database
    admin_emails = get_admin_emails()
    
    if not admin_emails:
        print("ALERT: denied access detected but NO ADMINS found in database.")
        return

    subject = f"UNAUTHORIZED ACCESS ALERT"
    
    # HTML Body
    body_html = f"""
        <html>
        <body>
            <h2 style="color:red;">Unauthorized Access Detected</h2>
            <p>A potentially dangerous unauthorized access was recorded:</p>
            <ul>
                <li><strong>User ID:</strong> {log_entry.get('user_id')}</li>
                <li><strong>Role:</strong> {log_entry.get('role')}</li>
                <li><strong>Area:</strong> {log_entry.get('area')}</li>
                <li><strong>Access Time:</strong> {log_entry.get('access_time')}</li>
                <li><strong>Reason:</strong> {log_entry.get('reason', 'AI Detected Anomaly')}</li>
            </ul>
            <p><strong>Action Required:</strong> Please review this incident promptly.</p>
        </body>
        </html>
    """

    # --- EMAIL SENDING ---
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['Subject'] = subject
        msg['To'] = ", ".join(admin_emails)
        
        msg.attach(MIMEText(body_html, 'html'))

        # Connect to Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=3)
        server.starttls() # Secure encryption
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        
        # Send the email to all admins
        text = msg.as_string()
        server.sendmail(SMTP_EMAIL, admin_emails, text)
        
        server.quit()
        
    except Exception as e:
        print(f"❌ Error sending email via Gmail: {e}")


def fetch_all_logs():
    """ Obtain all logs and relevant user data from the database. """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=extras.DictCursor)
    
    # Use JOIN to obtain user data along with logs
    cur.execute("""

        SELECT 
            l.access_time, l.area, l.entry_allowed, l.reason,
            u.role, u.email, u.id AS user_id, u.registered_at
        FROM logs l
        JOIN users u ON l.user_id = u.id
        ORDER BY l.access_time DESC
    """)
    logs = cur.fetchall()
    cur.close()
    conn.close()
    
    # Convert results to DataFrame
    return pd.DataFrame(logs)
