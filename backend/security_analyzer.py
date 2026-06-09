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
from apscheduler.schedulers.background import BackgroundScheduler
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

    # --- EXPLAINABLE AI (XAI) LOGIC ---
    explanation = None
    
    if is_anomaly:

        # First, check the deviations in continuous features to identify the most significant anomaly driver
        cols_to_scale = ['hour', 'weekday', 'time_since_last_access', 'access_frequency_1h']
        scaled_values = log_processed[cols_to_scale].iloc[0].abs()
        
        max_num_deviation = scaled_values.max()
        max_num_feature = scaled_values.idxmax()
        
        # If the numerical deviation is significative (Z-score > 1.5)
        if max_num_deviation > 1.5:
            if max_num_feature == 'hour':
                explanation = "Unusual access time based on historical routine."
            elif max_num_feature == 'weekday':
                explanation = "Atypical access day (e.g., weekend vs weekday)."
            elif max_num_feature == 'access_frequency_1h':
                explanation = "Suspiciously high access frequency in the last hour."
            elif max_num_feature == 'time_since_last_access':
                explanation = "Unusual inactivity gap prior to this access."
        else:
            # If the numerical features don't show a clear anomaly driver, we check the categorical features for rare combinations
            explanation = f"Unusual spatial access pattern: Role '{log_entry['role']}' does not typically access '{log_entry['area']}' under these conditions."
    
    return score, is_anomaly, explanation

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

def send_anomaly_alert(log_entry, risk_score):
    """ Sends a formatted HTML email to ALL administrators in case of an AI anomaly. """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("⚠️ SMTP credentials not set. Cannot send anomaly alert email.")
        return 
    
    admin_emails = get_admin_emails()
    if not admin_emails:
        print("ALERT: Anomaly detected but NO ADMINS found in database.")
        return

    subject = f"⚠️ AI SECURITY ALERT: Anomaly Detected in {log_entry.get('area', 'Unknown')}"
    xai_reason = log_entry.get('ai_explanation', 'No detailed context available.')

    # Aesthetic HTML Template for AI Anomaly
    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
        <div style="background-color: #f39c12; color: white; padding: 15px 20px;">
            <h2 style="margin: 0; font-size: 20px;">AI Security Alert</h2>
        </div>
        <div style="padding: 20px; color: #333;">
            <p style="font-size: 16px; margin-top: 0;">The AIloQR Machine Learning Engine has flagged a suspicious access attempt.</p>
            
            <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #f39c12; margin-bottom: 20px;">
                <h3 style="margin-top: 0; color: #2c3e50; font-size: 16px;">📋 Incident Details</h3>
                <ul style="list-style-type: none; padding: 0; margin: 0; line-height: 1.8;">
                    <li><strong>User ID:</strong> {log_entry.get('user_id', 'Unknown')}</li>
                    <li><strong>Role:</strong> {log_entry.get('role', 'Unknown')}</li>
                    <li><strong>Target Area:</strong> {log_entry.get('area', 'Unknown')}</li>
                    <li><strong>Time:</strong> {log_entry.get('access_time', 'Unknown')}</li>
                    <li><strong>Reason:</strong> {log_entry.get('reason', 'AI Detected Anomaly')}</li>
                </ul>
            </div>

            <div style="background-color: #fdf2e9; padding: 15px; border-left: 4px solid #e67e22; margin-bottom: 20px;">
                <h3 style="margin-top: 0; color: #d35400; font-size: 16px;">🧠 AI Analysis</h3>
                <ul style="list-style-type: none; padding: 0; margin: 0; line-height: 1.8;">
                    <li><strong>Risk Score:</strong> <span style="color: #d35400; font-weight: bold;">{risk_score:.4f}</span></li>
                    <li><strong>AI Explanation (XAI):</strong> {xai_reason}</li>
                </ul>
            </div>

            <p style="font-weight: bold; color: #c0392b; font-size: 14px;">Action Required: Please access the Administrator Dashboard to review and resolve this threat.</p>
        </div>
    </div>
    """

    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['Subject'] = subject
        msg['To'] = ", ".join(admin_emails)
        
        msg.attach(MIMEText(body_html, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=5)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        
        text = msg.as_string()
        server.sendmail(SMTP_EMAIL, admin_emails, text)
        server.quit()
        print(f"[EMAIL] AI Alert sent successfully for User {log_entry.get('user_id')}")
        
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send AI alert via Gmail: {e}")


def send_access_denied_alert(log_entry):
    """ Sends a formatted HTML email to ALL administrators in case of a Hard Rule violation. """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("⚠️ SMTP credentials not set. Cannot send denied alert email.")
        return 

    admin_emails = get_admin_emails()
    if not admin_emails:
        print("ALERT: Denied access detected but NO ADMINS found in database.")
        return

    subject = f"⛔ UNAUTHORIZED ACCESS: Attempt Blocked in {log_entry.get('area', 'Unknown')}"

    # Aesthetic HTML Template for Hard Rule Block
    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
        <div style="background-color: #c0392b; color: white; padding: 15px 20px;">
            <h2 style="margin: 0; font-size: 20px;">Unauthorized Access Blocked</h2>
        </div>
        <div style="padding: 20px; color: #333;">
            <p style="font-size: 16px; margin-top: 0;">The system has successfully blocked an access attempt based on strict security rules.</p>
            
            <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #c0392b; margin-bottom: 20px;">
                <h3 style="margin-top: 0; color: #2c3e50; font-size: 16px;">📋 Incident Details</h3>
                <ul style="list-style-type: none; padding: 0; margin: 0; line-height: 1.8;">
                    <li><strong>User ID:</strong> {log_entry.get('user_id', 'Unknown')}</li>
                    <li><strong>Role:</strong> {log_entry.get('role', 'Unknown')}</li>
                    <li><strong>Target Area:</strong> {log_entry.get('area', 'Unknown')}</li>
                    <li><strong>Time:</strong> {log_entry.get('access_time', 'Unknown')}</li>
                    <li><strong>Reason:</strong> <span style="color: #c0392b; font-weight: bold;">{log_entry.get('reason', 'Access Denied')}</span></li>
                </ul>
            </div>

            <p style="font-weight: bold; color: #c0392b; font-size: 14px;">Action Required: Please access the Administrator Dashboard to review this incident.</p>
        </div>
    </div>
    """

    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['Subject'] = subject
        msg['To'] = ", ".join(admin_emails)
        
        msg.attach(MIMEText(body_html, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=5)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        
        text = msg.as_string()
        server.sendmail(SMTP_EMAIL, admin_emails, text)
        server.quit()
        print(f"[EMAIL] Denied access alert sent successfully for User {log_entry.get('user_id')}")
        
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send denied alert via Gmail: {e}")


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


# --- AUTOMATED RETRAINING PIPELINE ---

def fetch_recent_normative_logs(limit=10000):
    """
    Fetches the most recent standard access logs from the database.
    Strictly excludes logs flagged as threats (is_threat = TRUE).
    Calculates the dynamic temporal features before returning the DataFrame.
    """
    conn = get_db_connection()
    df = pd.DataFrame()
    
    try:
        cur = conn.cursor()
        
        query = """
            SELECT user_id, role, area, access_time
            FROM logs
            WHERE entry_allowed = TRUE AND is_threat = FALSE
            ORDER BY access_time DESC
            LIMIT %s
        """
        cur.execute(query, (limit,))
        rows = cur.fetchall()
        
        if rows:
            columns = [desc[0] for desc in cur.description]
            df = pd.DataFrame(rows, columns=columns)
            
            print("⏳ Calculating dynamic temporal features for retraining...")
            
            # Ensure access_time is a datetime object
            df['access_time'] = pd.to_datetime(df['access_time'])
            
            # Sort chronologically for accurate calculations
            df = df.sort_values('access_time')
            
            # Calculate 'time_since_last_access'
            df['time_since_last_access'] = df.groupby('user_id')['access_time'].diff().dt.total_seconds()
            
            # For the first access of each user, set a default large value (e.g., 86400 seconds = 1 day)
            df['time_since_last_access'] = df['time_since_last_access'].fillna(86400)
            
            # Calculate 'access_frequency_1h'
            def count_last_hour(series):
                return series.rolling('1h', closed='left').count().fillna(0)
                
            df = df.set_index('access_time')
            df['access_frequency_1h'] = df.groupby('user_id')['user_id'].transform(count_last_hour)
            df = df.reset_index()
            
            # Restore original descending order (newest first)
            df = df.sort_values('access_time', ascending=False)
            
    except Exception as e:
        print(f"Error fetching normative logs for retraining: {e}")
    finally:
        cur.close()
        conn.close()
        
    return df

def execute_auto_retraining():
    """
    Executes the automated retraining pipeline to adapt to concept drift.
    Retrieves fresh data and updates the Isolation Forest model artifacts.
    """
    print(f"[{datetime.now()}] Initiating scheduled AI auto-retraining...")
    
    df_recent = fetch_recent_normative_logs(limit=10000)
    
    # Ensure there is enough data to build a meaningful Isolation Forest
    if df_recent.empty or len(df_recent) < 1000:
        print("Insufficient new normative data for retraining. Aborting process.")
        return

    try:
        # Call the existing training function with the fresh DataFrame
        train_security_model(df_recent)
        print("✅ AI Auto-retraining completed successfully. Model artifacts updated.")
    except Exception as e:
        print(f"❌ Error during model retraining: {e}")

def start_retraining_scheduler():
    """
    Initializes a background scheduler to retrain the model periodically.
    Configured to run during low-traffic periods to avoid server load.
    """
    scheduler = BackgroundScheduler()
    
    # Schedule the retraining job to run every Sunday at 03:00 AM
    scheduler.add_job(execute_auto_retraining, 'cron', day_of_week='sun', hour=3, minute=0)
    
    scheduler.start()
    print("🕒 Model auto-retraining scheduler started. Next run scheduled.")