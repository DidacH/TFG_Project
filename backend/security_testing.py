import pandas as pd
from datetime import datetime
from security_analyzer import predict_anomaly, send_anomaly_alert, train_security_model

# 1. Assegura't que el model està entrenat
print("Entrenant model inicial...")
train_security_model()

# --- DEFINICIÓ DE CASOS DE PROVA ---

scenarios = [
    {
        "name": "CAS 1: Accés Normal (Estudiant a l'aula)",
        "log": {
            "user_id": 101,
            "role": "Student",
            "area": "Classroom_1",
            "access_time": "2025-05-20 10:00:00", # Dia feiner, matí
            "entry_allowed": True
        }
    },
    {
        "name": "CAS 2: Violació Hard Rule (Estudiant al Server Room)",
        "log": {
            "user_id": 102,
            "role": "Student",
            "area": "Server_Room", # PROHIBIT
            "access_time": "2025-05-20 10:00:00",
            "entry_allowed": False
        }
    },
    {
        "name": "CAS 3: Anomalia IA (Admin a les 3 AM)",
        # Els admins poden entrar a tot arreu (Hard Rule OK), 
        # però l'IA hauria de veure les 3 AM com una anomalia si no hi ha dades similars.
        "log": {
            "user_id": 999,
            "role": "Admin",
            "area": "Office_1",
            "access_time": "2025-05-20 03:00:00", 
            "entry_allowed": True
        }
    }
]

print("\n--- INICIANT PROVES DE SEGURETAT ---\n")

for scenario in scenarios:
    print(f"Testejant: {scenario['name']}")
    log_entry = scenario['log']
    
    # Executem la predicció
    score, is_anomaly = predict_anomaly(log_entry)
    
    print(f"Resultat -> Score: {score:.4f} | És Anomalia?: {is_anomaly}")
    
    if log_entry.get('reason'):
        print(f"Raó Hard Rule: {log_entry['reason']}")
        
    if is_anomaly:
        print(">> ENVIANT ALERTA SIMULADA...")
        send_anomaly_alert(log_entry, score)
    else:
        print(">> Accés considerat segur.")
        
    print("-" * 40)