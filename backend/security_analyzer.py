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

# --- SMTP CONFIGURATION ---
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# --- Model and Preprocessing ---
MODEL_FILE = 'security_model_data.pkl'
model = None
scaler = None
label_encoders = {}
FEATURE_COLUMNS = ['role_encoded', 'area_encoded', 'hour', 'weekday', 'is_admin']
raw_threshold = os.getenv("ANOMALY_THRESHOLD", "-0.15") # Threshold for flagging anomalies

try:
    # Convert to float
    ANOMALY_THRESHOLD = float(raw_threshold)
    print(f"Anomaly threshold set to {ANOMALY_THRESHOLD}")
except ValueError:
    print(f"⚠️ Error: El valor '{raw_threshold}' al .env no és vàlid. Usant -0.15 per defecte.")
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

def _get_dataset_for_training():
    #Example initial data for training the model
    data = {
        'user_id': ['u1', 'u2', 'u3', 'u4', 'u5'],
        'email': ['u1@inst.edu', 'u2@inst.edu', 'a1@inst.edu', 'u4@inst.edu', 'u5@inst.edu'],
        'role': ['Student', 'Professor', 'Admin', 'Student', 'Staff'],
        'area': ['area_1', 'area_2', 'area_3', 'area_1', 'area_2'],
        'access_time': [
            '2025-10-10 09:00:00', '2025-10-10 10:30:00', '2025-10-10 11:00:00',
            '2025-10-10 20:00:00', '2025-10-11 08:00:00'
        ]
    }
    df = pd.DataFrame(data)
    df['access_time'] = pd.to_datetime(df['access_time'])
    return df

def preprocess_data(df):
    """ Applys preprocessing steps to the dataframe."""
    global label_encoders, scaler
    
    # Time-based feature engineering
    df['hour'] = df['access_time'].dt.hour
    df['weekday'] = df['access_time'].dt.dayofweek # Monday=0, Sunday=6

    # Training code: Adjust and transform categorical columns
    # Prediction code: Only transform categorical columns using existing encoders
    fit_and_transform = (model is None) 
    
    # Role and area encoding
    for col in ['role', 'area']:
        encoder = label_encoders.get(col, LabelEncoder())
        if fit_and_transform:
            df[f'{col}_encoded'] = encoder.fit_transform(df[col])
            label_encoders[col] = encoder
        else:
            # Use existing encoder and handle unseen labels
            def safe_transform(val):
                try:
                    return encoder.transform([val])[0]
                except ValueError:
                    # Assign high value for unseen labels
                    return len(encoder.classes_) 
            
            # Create a new column with if it does not appear in the training set
            df[f'{col}_encoded'] = df[col].apply(safe_transform)

    # Binary feature: is_admin
    df['is_admin'] = df['role'].apply(lambda x: 1 if x == 'Admin' else 0)

    # Numerical feature scaling (hour, weekday)
    if fit_and_transform:
        scaler = StandardScaler()
        df[['hour', 'weekday']] = scaler.fit_transform(df[['hour', 'weekday']])
    else:
        df[['hour', 'weekday']] = scaler.transform(df[['hour', 'weekday']])

    return df

def train_security_model():
    """ Train the model using log data (Isolation Forest) """
    global model
    df_train = _get_dataset_for_training()
    df_processed = preprocess_data(df_train)
    
    X_train = df_processed[FEATURE_COLUMNS]

    # Isolation Forest: Good for anomaly detection in high-dimensional data. Also good since we don't have labeled anomalies
    model = IsolationForest(contamination='auto', random_state=42)
    model.fit(X_train)
    print("Security model trained successfully.")

    save_model_artifacts()

def load_or_train_model(retry_count=0):
    global model, scaler, label_encoders

    MAX_RETRIES = 2

    if retry_count >= MAX_RETRIES:
        print(f"CRITICAL ERROR: Could not load the model after {retry_count} attempts.")
        print("Verify write permissions or training errors.")
        return
    
    if os.path.exists(MODEL_FILE):
        try:
            print("Loading existing model...")
            with open(MODEL_FILE, 'rb') as f:
                artifacts = pickle.load(f)
                
            model = artifacts['model']
            scaler = artifacts['scaler']
            label_encoders = artifacts['label_encoders']
            print("Model loaded successfully from disk.")
            return
        except Exception as e:
            print(f"Error loading the model (corrupt file?): {e}")
            print("Proceeding to retrain...")
    else:
        print("No saved model was found.")

    # Retrain if loading failed or no file
    train_security_model()
    load_or_train_model(retry_count + 1)  # Recursive call to load the newly trained model

def predict_anomaly(log_entry):
    """
    Compute the anomaly score for a single log entry.
    :param log_entry: Dictionary with log data.
    :return: Anomaly score (lower is worse), and classification (True/False for anomaly)
    """
    global model
    if model is None:
        train_security_model() # Train if not already trained
    
    # Convert the entry to dataframe (As in the training dataset)
    log_df = pd.DataFrame([log_entry])
    log_df['access_time'] = pd.to_datetime(log_df['access_time'])
    
    # Preprocessing
    # Using existing transformers (scaler, encoders)
    log_processed = preprocess_data(log_df)
    
    X_predict = log_processed[FEATURE_COLUMNS]

    # Prediction: 
    # - score_samples returns the anomaly index. 
    #   The lower (more negative), the more anomalous.
    # - predict returns 1 (normal) or -1 (anomaly)
    anomaly_score = model.decision_function(X_predict)[0]
    is_anomaly = anomaly_score < ANOMALY_THRESHOLD
    
    return anomaly_score, is_anomaly

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
        # We send hidden to multiple admins
        msg['To'] = SMTP_EMAIL 
        
        msg.attach(MIMEText(body_html, 'html'))

        # Connect to Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls() # Secure encryption
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        
        # Send the email to all admins
        text = msg.as_string()
        server.sendmail(SMTP_EMAIL, admin_emails, text)
        
        server.quit()
        print(f"✅ Alert correctly sent to {len(admin_emails)} administrators.")
        
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
        # We send hidden to multiple admins
        msg['To'] = SMTP_EMAIL 
        
        msg.attach(MIMEText(body_html, 'html'))

        # Connect to Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls() # Secure encryption
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        
        # Send the email to all admins
        text = msg.as_string()
        server.sendmail(SMTP_EMAIL, admin_emails, text)
        
        server.quit()
        print(f"✅ Alert correctly sent to {len(admin_emails)} administrators.")
        
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


def batch_analysis_deep_dive():
    """
    Perform a deeper analysis of the logs. To be done daily or weekly.
    """
    df_logs = fetch_all_logs()
    if df_logs.empty:
        print("No logs available for deep dive analysis.")
        return
    
    df_logs['access_time'] = pd.to_datetime(df_logs['access_time'])
    df_logs = preprocess_data(df_logs.copy())

    # 1. Detection of various anomaly patterns: 
    # (Ex: user that only accesses room_1, but suddenly accesses room_5 at 3 AM)
    X_logs = df_logs[FEATURE_COLUMNS]
    df_logs['deep_anomaly_score'] = model.decision_function(X_logs)
    
    # 2. Time-based Abuse Detection:

    # Calculates the elapsed time (in seconds) since the last access of each user
    df_logs['time_diff'] = df_logs.groupby('user_id')['access_time'].diff().dt.total_seconds().fillna(0)
    
    # Identify accesses that are too close in time
    # ABUSE_THRESHOLD: Less than 1 minute between same user's accesses
    df_logs['is_time_abuse'] = (df_logs['time_diff'] > 0) & (df_logs['time_diff'] < 60)
    
    # 3. Detection of False Positives from QR_Scanner: 
    # (Ex: Logs with expired QR, but with a temporally normal pattern)
    
    # Logs that have been labeled as 'expired' (by QR validator) but 
    # the AI model marked them as 'Normal' (Score > -0.15) in real-time analysis.
    false_positives = df_logs[
        (df_logs['reason'].str.contains('expired') & 
         df_logs['deep_anomaly_score'] > ANOMALY_THRESHOLD)
    ]

    # --- Report Generation ---
    report = {
        'total_logs': len(df_logs),
        'anomalous_logs': df_logs[df_logs['deep_anomaly_score'] < ANOMALY_THRESHOLD].shape[0],
        'time_abuse_incidents': df_logs[df_logs['is_time_abuse']].shape[0],
        'potential_false_positives': false_positives.shape[0]
    }

    print("\n--- DEEP DIVE BATCH ANALYSIS REPORT ---")
    for key, value in report.items():
        print(f"{key}: {value}")
        
    if report['potential_false_positives'] > 0:
        print("\nPotential False Positives (Needs Admin Review to Mark as Safe):")
        print(false_positives[['user_id', 'email', 'access_time', 'reason', 'deep_anomaly_score']].head())
    
    if report['time_abuse_incidents'] > 0:
        print("\nPossible Time Abuse Incidents:")
        print(df_logs[df_logs['is_time_abuse']][['user_id', 'email', 'access_time', 'time_diff']].head())

    # AFEGIR: Lògica per enviar un correu amb el Report d'Anàlisi Global



# To run the deep dive analysis:
# batch_analysis_deep_dive()
