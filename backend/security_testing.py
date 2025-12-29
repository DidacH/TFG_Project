import pandas as pd
import os
from dotenv import load_dotenv
from security_analyzer import predict_anomaly, send_anomaly_alert, train_security_model

# 1. Carreguem les variables d'entorn (CRUCIAL per llegir SMTP_PASSWORD)
load_dotenv()

# 2. Assegura't que el model està entrenat i llest
print(" Inicialitzant i entrenant model per a les proves...")
train_security_model()

# --- DEFINICIÓ DE CASOS DE PROVA ---

scenarios = [
    {
        "name": "CAS 1: Accés Normal (Estudiant a l'aula)",
        "description": "Un comportament habitual que NO hauria de generar alerta.",
        "log": {
            "user_id": 101,
            "role": "Student",
            "area": "Classroom_1",
            "access_time": "2025-05-20 10:00:00", # Dia feiner, matí
            "entry_allowed": True # Assumim que ha passat les Hard Rules
        }
    },
    {
        "name": "CAS 2: Patró Sospitós (Estudiant a Sala de Servidors)",
        "description": "Encara que passés la Hard Rule (hipotèticament), la IA mai ha vist un estudiant aquí.",
        "log": {
            "user_id": 102,
            "role": "Student",
            "area": "Server_Room", 
            "access_time": "2025-05-20 10:00:00",
            "entry_allowed": True 
        }
    },
    {
        "name": "CAS 3: Anomalia Temporal (Admin a les 3 AM)",
        "description": "Aquest cas hauria de disparar l'EMAIL real.",
        "log": {
            "user_id": 999,
            "role": "Admin",
            "area": "Office_1",
            "access_time": "2025-05-20 03:00:00", 
            "entry_allowed": True
        }
    }
]

print("\n" + "="*50)
print(" INICIANT PROVES DE SEGURETAT I ENVIAMENT D'EMAILS")
print("="*50 + "\n")

# Verificació prèvia de credencials
if not os.getenv("SMTP_EMAIL") or not os.getenv("SMTP_PASSWORD"):
    print("⚠️  ATENCIÓ: No s'han trobat les credencials SMTP al fitxer .env.")
    print("   Les alertes no s'enviaran realment.\n")

for scenario in scenarios:
    print(f"🔹 Testejant: {scenario['name']}")
    print(f"   Descripció: {scenario['description']}")
    log_entry = scenario['log']
    
    # Executem la predicció d'IA
    score, is_anomaly = predict_anomaly(log_entry)
    
    print(f"   Resultat -> Score: {score:.4f} | És Anomalia?: {is_anomaly}")
        
    if is_anomaly:
        print("   🚨 ANOMALIA DETECTADA! Intentant enviar correu electrònic...")
        
        # Aquí és on es prova la connexió amb Gmail
        send_anomaly_alert(log_entry, score)
        
        print("   >> Revisa la safata d'entrada (i spam) dels administradors.")
    else:
        print("   ✅ Accés considerat segur. Cap acció presa.")
        
    print("-" * 50 + "\n")