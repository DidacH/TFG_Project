"""
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder, StandardScaler
from database import get_db_connection
import numpy as np
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# --- Configuració ---
# Llegeix la clau d'API de SendGrid i l'email de l'administrador des de l'entorn.
# ASSEGURA'T D'AFEGIR AQUESTES VARIABLES AL TEU FITXER .env
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

# --- Model i Preprocessament ---
# Aquests objectes s'inicialitzaran amb un dataset d'entrenament, 
# però els declarem aquí per a que estiguin disponibles globalment.
model = None
scaler = None
label_encoders = {}
FEATURE_COLUMNS = ['role_encoded', 'area_encoded', 'hour', 'weekday', 'is_admin']

def _get_dataset_for_training():
    """
"""
    Simula la càrrega de dades per a l'entrenament.
    En un escenari real, aquestes dades haurien de ser molt més extenses i 
    haurien de provenir d'un fitxer CSV o directament de la BD.

    :return: DataFrame amb dades d'entrenament.
"""
    """
    # Exemple de dades inicials (tu les hauries de reemplaçar per les teves dades reals)
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
    """ """Aplica la transformació de característiques al DataFrame.""" """
    global label_encoders, scaler
    
    # Enginyeria de característiques temporals
    df['hour'] = df['access_time'].dt.hour
    df['weekday'] = df['access_time'].dt.dayofweek # Dilluns=0, Diumenge=6

    # Codi per a l'entrenament: ajusta i transforma les columnes categòriques
    # Codi per a la predicció: només transforma les columnes categòriques
    fit_and_transform = (model is None) 
    
    # 1. Codificació de Rol i Sala
    for col in ['role', 'area']:
        encoder = label_encoders.get(col, LabelEncoder())
        if fit_and_transform:
            df[f'{col}_encoded'] = encoder.fit_transform(df[col])
            label_encoders[col] = encoder
        else:
            # Utilitza l'encoder existent i gestiona valors desconeguts
            def safe_transform(val):
                try:
                    return encoder.transform([val])[0]
                except ValueError:
                    # Assigna un valor alt o únic per a valors no vistos
                    return len(encoder.classes_) 
            
            # Crea una nova columna si el valor no existeix a l'entrenament (risc d'anomalia)
            df[f'{col}_encoded'] = df[col].apply(safe_transform)

    # 2. Característica binària: és administrador?
    df['is_admin'] = df['role'].apply(lambda x: 1 if x == 'Admin' else 0)

    # 3. Escalament numèric (hora i dia de la setmana)
    if fit_and_transform:
        scaler = StandardScaler()
        df[['hour', 'weekday']] = scaler.fit_transform(df[['hour', 'weekday']])
    else:
        df[['hour', 'weekday']] = scaler.transform(df[['hour', 'weekday']])

    return df

def train_security_model():
    """ """Entrena el model Isolation Forest amb un dataset inicial.""" """
    global model
    df_train = _get_dataset_for_training()
    df_processed = preprocess_data(df_train)
    
    X_train = df_processed[FEATURE_COLUMNS]

    # Isolation Forest: bo per a la detecció d'anomalies
    model = IsolationForest(contamination='auto', random_state=42)
    model.fit(X_train)
    print("Security model trained successfully.")

def predict_anomaly(log_entry):
    """
"""
    Calcula la puntuació d'anomalia per a una única entrada de log.
    :param log_entry: Diccionari amb les dades del log.
    :return: Puntuació d'anomalia (score), i la classificació (True/False per anomalia)
"""
    """
    global model
    if model is None:
        train_security_model() # Entrena si encara no s'ha fet
    
    # 1. Converteix l'entrada a DataFrame (com el dataset d'entrenament)
    log_df = pd.DataFrame([log_entry])
    log_df['access_time'] = pd.to_datetime(log_df['access_time'])
    
    # 2. Preprocessament
    # IMPORTANT: utilitza els transformadors *existents* (scaler, encoders)
    log_processed = preprocess_data(log_df)
    
    X_predict = log_processed[FEATURE_COLUMNS]

    # 3. Predicció: 
    # - score_samples retorna l'índex d'anomalia. 
    #   Com més baix (més negatiu), més anòmal.
    # - predict retorna 1 (normal) o -1 (anomalia)
    anomaly_score = model.decision_function(X_predict)[0]
    is_anomaly = model.predict(X_predict)[0] == -1
    
    return anomaly_score, is_anomaly

def send_anomaly_alert(log_entry, score):
    """ """Envia un correu electrònic als administradors en cas d'anomalia.""" """
    if not SENDGRID_API_KEY or not ADMIN_EMAIL:
        print("ALERT: SendGrid keys not configured. Email not sent.")
        return

    subject = f"ALERTA D'ANOMALIA D'ACCÉS: Score {score:.4f}"
    body_html = f"""
"""
        <html>
        <body>
            <h2>Access Anomaly Detected</h2>
            <p>An anomalous access log was recorded by the security model:</p>
            <ul>
                <li><strong>User ID:</strong> {log_entry.get('user_id')}</li>
                <li><strong>Role:</strong> {log_entry.get('role')}</li>
                <li><strong>Area:</strong> {log_entry.get('area')}</li>
                <li><strong>Access Time:</strong> {log_entry.get('access_time')}</li>
                <li><strong>Entry Allowed:</strong> {'Yes' if log_entry.get('entry_allowed') else 'No'}</li>
                <li><strong>Reason:</strong> {log_entry.get('reason')}</li>
            </ul>
            <p><strong>Risk Score (lower is worse):</strong> {score:.4f}</p>
            <p>Please review the logs immediately.</p>
        </body>
        </html>
"""
    """

    message = Mail(
        from_email='security-alert@yourinstitution.com',
        to_emails=ADMIN_EMAIL,
        subject=subject,
        html_content=body_html)
    
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"Alert email sent. Status Code: {response.status_code}")
    except Exception as e:
        print(f"Error sending email: {e}")

# Entrena el model a l'inici de l'aplicació
# IMPORTANT: Aquesta crida hauria de ser en un punt d'inici (com ara el final de app.py)
# o en una funció de càrrega per a que el model estigui a memòria.
train_security_model()


def fetch_all_logs():
    """ """Obté tots els logs i dades d'usuari rellevants de la BD.""" """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=extras.DictCursor)
    
    # Utilitza un JOIN per obtenir tota la informació necessària
    cur.execute("""
"""
        SELECT 
            l.access_time, l.area, l.entry_allowed, l.reason,
            u.role, u.email, u.id AS user_id, u.registered_at
        FROM logs l
        JOIN users u ON l.user_id = u.id
        ORDER BY l.access_time DESC
"""
    """)
    logs = cur.fetchall()
    cur.close()
    conn.close()
    
    # Converteix els resultats directament a DataFrame
    return pd.DataFrame(logs)


def batch_analysis_deep_dive():
    """
"""
    Realitza una anàlisi més profunda dels logs, ideal per a l'anàlisi diària/setmanal.
    Aquesta anàlisi pot incloure la detecció de patrons de "Falsos Positius" (FP) o 
    "Amenaces per Patrons de Múltiples Logs".
"""
    """
    df_logs = fetch_all_logs()
    if df_logs.empty:
        print("No logs available for deep dive analysis.")
        return
    
    # Assegura el format de temps
    df_logs['access_time'] = pd.to_datetime(df_logs['access_time'])
    df_logs = preprocess_data(df_logs.copy())

    # --- Anàlisi d'Exemples de Patrons ---

    # 1. Detecció de Patrons Anòmals per Usuari: 
    # (Ex: usuari que només accedeix a la Sala_1, però de sobte intenta la Sala_3)
    
    # Reentrena amb un model més sensible o amb un altre algorisme (IsolationForest del 
    # mòdul global ja s'ha entrenat a l'inici, el reutilitzarem per a consistència)
    X_logs = df_logs[FEATURE_COLUMNS]
    df_logs['deep_anomaly_score'] = model.decision_function(X_logs)
    
    # 2. Detecció d'Abús de Temps (Ex: Intent de molts accessos en poc temps)
    
    # Calcula el temps transcorregut (en segons) des de l'últim accés de cada usuari
    df_logs['time_diff'] = df_logs.groupby('user_id')['access_time'].diff().dt.total_seconds().fillna(0)
    
    # Identifica entrades on la diferència de temps és molt petita (excepte 0, el primer log)
    # LLINDAR_ABÚS: Menys de 5 minuts (300s) d'un mateix usuari a la mateixa sala 
    # (podria indicar abús, a part del límit de 30s del QR)
    df_logs['is_time_abuse'] = (df_logs['time_diff'] > 0) & (df_logs['time_diff'] < 300)
    
    # 3. Detecció de Falsos Positius del QR_Scanner: 
    # (Ex: Logs amb QR invàlid per expiració, però amb un patró temporalment normal)
    
    # Els logs que han estat marcats com a 'expired' (pel validador del QR) però 
    # la IA els va marcar com a 'Normal' (Score > -0.15) en l'anàlisi en temps real.
    false_positives = df_logs[
        (df_logs['reason'].str.contains('expired') & 
         df_logs['deep_anomaly_score'] > ANOMALY_THRESHOLD)
    ]

    # --- Generació d'Informes (simulació) ---
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

# Si vols provar l'anàlisi de batchs:
# batch_analysis_deep_dive()

"""
