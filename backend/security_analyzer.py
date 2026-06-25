import pandas as pd
import numpy as np
import os
import smtplib
import pickle
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder, StandardScaler
from apscheduler.schedulers.background import BackgroundScheduler
from psycopg2 import extras
from dotenv import load_dotenv

from database import get_db_connection

load_dotenv() 

# =============================================================================
# === CONFIGURATION & GLOBALS ===
# =============================================================================

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

MODEL_FILE = 'security_model_data.pkl'
model = None
scaler = None
label_encoders = {}
FEATURE_COLUMNS = [
    'role_encoded', 'area_encoded', 'hour', 'weekday', 
    'is_admin', 'time_since_last_access', 'access_frequency_1h'
]

# =============================================================================
# === DATABASE UTILITIES ===
# =============================================================================

def get_anomaly_threshold():
    """
    Fetches the current AI sensitivity threshold from the database in real-time.
    Provides a secure fallback value if the database is unreachable.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT value_data FROM system_config WHERE key_name = 'anomaly_threshold'")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return float(row[0])
    except Exception as e:
        print(f"[DB ERROR] Failed fetching threshold from DB, using fallback: {e}")
    
    return -0.025


def get_admin_emails():
    """Retrieves a list of email addresses for all users with Administrative privileges."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT email FROM users WHERE role = 'Admin'")
        emails = [row[0] for row in cur.fetchall()]
        return emails
    except Exception as e:
        print(f"[DB ERROR] Error fetching admin emails: {e}")
        return []
    finally:
        cur.close()
        conn.close()

# =============================================================================
# === ML MODEL: TRAINING & PREPROCESSING ===
# =============================================================================

def save_model_artifacts():
    """Serializes and saves the active model, scaler, and label encoders to disk."""
    artifacts = {
        'model': model,
        'scaler': scaler,
        'label_encoders': label_encoders
    }
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump(artifacts, f)
    print(f"[AI PIPELINE] Model and artifacts stored in {MODEL_FILE}")


def preprocess_data(df, is_training=False):
    """
    Executes Feature Engineering and Data Scaling.
    Extracts temporal components, flags admin status, encodes categorical variables,
    and scales continuous numerical features.
    """
    global label_encoders, scaler
    
    df['access_time'] = pd.to_datetime(df['access_time'])
    df['hour'] = df['access_time'].dt.hour
    df['weekday'] = df['access_time'].dt.dayofweek
    df['is_admin'] = df['role'].apply(lambda x: 1 if x == 'Admin' else 0)

    for col in ['role', 'area']:
        encoder = label_encoders.get(col, LabelEncoder())
        if is_training:
            df[f'{col}_encoded'] = encoder.fit_transform(df[col])
            label_encoders[col] = encoder
        else:
            df[f'{col}_encoded'] = df[col].apply(
                lambda x: encoder.transform([x])[0] if x in encoder.classes_ else len(encoder.classes_)
            )

    cols_to_scale = ['hour', 'weekday', 'time_since_last_access', 'access_frequency_1h']
    if is_training:
        scaler = StandardScaler()
        df[cols_to_scale] = scaler.fit_transform(df[cols_to_scale])
    else:
        df[cols_to_scale] = scaler.transform(df[cols_to_scale])

    return df


def train_security_model(dataset: pd.DataFrame):
    """
    Initializes and trains the Unsupervised Machine Learning Model (Isolation Forest)
    using the provided normative dataset.
    """
    global model
    
    print("[AI PIPELINE] Starting security model training...")
    df_processed = preprocess_data(dataset, is_training=True)
    
    X_train = df_processed[FEATURE_COLUMNS]
    
    model = IsolationForest(contamination='auto', random_state=42)
    model.fit(X_train)
    
    save_model_artifacts()
    print("[AI PIPELINE] Security model trained successfully.")


def load_or_train_model():
    """
    Loads pre-trained model artifacts into memory upon server startup.
    Returns False if artifacts are missing, requiring an initial training execution.
    """
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
            print(f"[AI ERROR] Failed loading model artifacts: {e}")
    return False

# =============================================================================
# === ML MODEL: INFERENCE & XAI ===
# =============================================================================

def get_user_history_features(user_id):
    """
    Fetches real-time historical context for a specific user to compute
    dynamic features: 'time_since_last_access' and 'access_frequency_1h'.
    """
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
    """
    Evaluates a new access log against the Isolation Forest model.
    Utilizes Explainable AI (XAI) logic to provide human-readable reasoning 
    for why a particular log was flagged as an anomaly.
    
    Returns:
        tuple: (Risk Score, Boolean Anomaly Flag, XAI Explanation String)
    """
    global model
    if not model:
        if not load_or_train_model():
            return 0.0, False, None

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
    threshold = get_anomaly_threshold()
    is_anomaly = score < threshold

    # Explainable AI (XAI) Logic Engine
    explanation = None
    if is_anomaly:
        cols_to_scale = ['hour', 'weekday', 'time_since_last_access', 'access_frequency_1h']
        scaled_values = log_processed[cols_to_scale].iloc[0].abs()
        
        max_num_deviation = scaled_values.max()
        max_num_feature = scaled_values.idxmax()
        
        # Determine if continuous temporal features caused the anomaly (Z-score > 1.5)
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
            # Fallback to categorical/spatial anomaly assumption
            explanation = f"Unusual spatial access pattern: Role '{log_entry['role']}' does not typically access '{log_entry['area']}' under these conditions."
    
    return score, is_anomaly, explanation

# =============================================================================
# === NOTIFICATION SYSTEM ===
# =============================================================================

def send_anomaly_alert(log_entry, risk_score):
    """
    Constructs and dispatches an HTML-formatted email alert to all administrators
    when the AI Engine detects a high-confidence security anomaly.
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("[SMTP WARN] Credentials not set. Cannot send anomaly alert email.")
        return 
    
    admin_emails = get_admin_emails()
    if not admin_emails:
        print("[SMTP WARN] Anomaly detected but no admin emails found.")
        return

    subject = f"⚠️ AI SECURITY ALERT: Anomaly Detected in {log_entry.get('area', 'Unknown')}"
    xai_reason = log_entry.get('ai_explanation', 'No detailed context available.')

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

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10)
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        
        server.sendmail(SMTP_EMAIL, admin_emails, msg.as_string())
        server.quit()
        print(f"[SMTP] AI Alert sent successfully for User {log_entry.get('user_id')}")
        
    except Exception as e:
        print(f"[SMTP ERROR] Failed to send AI alert via Gmail: {e}")


def send_access_denied_alert(log_entry):
    """
    Constructs and dispatches an HTML-formatted email alert to all administrators
    when a critical Hard Rule violation occurs.
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("[SMTP WARN] Credentials not set. Cannot send denied alert email.")
        return 

    admin_emails = get_admin_emails()
    if not admin_emails:
        print("[SMTP WARN] Denied access detected but no admin emails found.")
        return

    subject = f"⛔ UNAUTHORIZED ACCESS: Attempt Blocked in {log_entry.get('area', 'Unknown')}"

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

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10)
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        
        server.sendmail(SMTP_EMAIL, admin_emails, msg.as_string())
        server.quit()
        print(f"[SMTP] Denied access alert sent successfully for User {log_entry.get('user_id')}")
        
    except Exception as e:
        print(f"[SMTP ERROR] Failed to send denied alert via Gmail: {e}")

# =============================================================================
# === AUTOMATED RETRAINING PIPELINE ===
# =============================================================================

def fetch_all_logs():
    """Obtains all raw logs and relevant user data joined from the database."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=extras.DictCursor)
    
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
    
    return pd.DataFrame(logs)


def fetch_recent_normative_logs(limit=10000):
    """
    Fetches the most recent standard (normative) access logs from the database 
    to form the baseline dataset for model retraining. Strictly excludes threats.
    Dynamically recalculates rolling temporal features ('time_since_last_access', 
    'access_frequency_1h') across the queried timeframe.
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
            
            print("[AI PIPELINE] Calculating dynamic temporal features for retraining...")
            
            df['access_time'] = pd.to_datetime(df['access_time'])
            df = df.sort_values('access_time')
            
            df['time_since_last_access'] = df.groupby('user_id')['access_time'].diff().dt.total_seconds()
            df['time_since_last_access'] = df['time_since_last_access'].fillna(86400) # Default to 1 day for initial access
            
            def count_last_hour(series):
                return series.rolling('1h', closed='left').count().fillna(0)
                
            df = df.set_index('access_time')
            df['access_frequency_1h'] = df.groupby('user_id')['user_id'].transform(count_last_hour)
            df = df.reset_index()
            
            df = df.sort_values('access_time', ascending=False)
            
    except Exception as e:
        print(f"[AI ERROR] Error fetching normative logs for retraining: {e}")
    finally:
        cur.close()
        conn.close()
        
    return df


def execute_auto_retraining():
    """
    Executes the automated retraining pipeline to combat model decay (concept drift).
    Fetches fresh normative data and updates the Isolation Forest artifacts.
    """
    print(f"\n[AI PIPELINE] [{datetime.now()}] Initiating scheduled AI auto-retraining...")
    
    df_recent = fetch_recent_normative_logs(limit=10000)
    
    # Validation constraint to prevent underfitting
    if df_recent.empty or len(df_recent) < 1000:
        print("[AI PIPELINE] Insufficient new normative data for retraining. Aborting process.")
        return

    try:
        train_security_model(df_recent)
        print("[AI PIPELINE] ✅ AI Auto-retraining completed successfully. Model artifacts updated.")
    except Exception as e:
        print(f"[AI ERROR] ❌ Error during model retraining: {e}")


def start_retraining_scheduler():
    """
    Initializes a background task scheduler to asynchronously trigger
    the model retraining pipeline during defined low-traffic periods.
    """
    scheduler = BackgroundScheduler()
    
    # Execute retraining job every Sunday at 03:00 AM server time
    scheduler.add_job(execute_auto_retraining, 'cron', day_of_week='sun', hour=3, minute=0)
    
    scheduler.start()
    print("[AI PIPELINE] 🕒 Model auto-retraining scheduler active. Next run scheduled.")