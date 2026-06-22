# AIloQR - Intelligent Access Control System

![AIloQR Banner](https://img.shields.io/badge/Status-Active-brightgreen) ![Version](https://img.shields.io/badge/Version-1.0.0-lightgrey)

**AIloQR** is a modern, AI-powered Physical Access Control System (PACS) designed to secure physical facilities utilizing dynamic cryptographic QR codes, Role-Based Access Control (RBAC), and Unsupervised Machine Learning for real-time anomaly detection.

This project was developed as a **Bachelor's Thesis (Treball de Final de Grau)**.

## 🌐 Live Demo

You can access the fully functional cloud-deployed application here:
**[https://frontend-tfg-project.onrender.com](https://frontend-tfg-project.onrender.com)**

> **Test Admin Access:**
> - **Admin Key:** `admin`

---

## ✨ Key Features

- **Cryptographic Dynamic QR Codes:** Time-based, HMAC-SHA256 signed QR codes that expire every 30 seconds, entirely preventing replay attacks and unauthorized copying.
- **AI Anomaly Detection:** An integrated Machine Learning engine (Isolation Forest) that analyzes historical user behaviors and flags suspicious access attempts in real-time. Includes an Explainable AI (XAI) module.
- **Real-Time WebSockets:** Live monitoring dashboard for Administrators, receiving instant updates of physical access scans and security threats without page reloads.
- **Granular RBAC & Schedules:** Comprehensive firewall-like policy management. Restrict user access based on roles, specific campus areas, days of the week, and exact time windows.
- **Global System Lockdown:** Emergency physical access termination switch that instantly revokes standard access across all facilities and notifies administrators via email.
- **Comprehensive Audit Logging:** CSV exporting capabilities and detailed historical tracking of all access events, AI scores, and system actions.

---

## 🛠️ Tech Stack

### Frontend
- **React.js** (v18) via **Vite**
- **Tailwind CSS** (for highly responsive, enterprise-grade UI)
- **Lucide-React** (Iconography)
- **Socket.io-client** (Real-time duplex communication)

### Backend
- **Python 3.10+** & **Flask**
- **PostgreSQL** (Relational Database)
- **Scikit-Learn** & **Pandas** (Machine Learning & Data Processing)
- **PyJWT** (Stateless authentication)
- **Gevent** & **Flask-SocketIO** (Async server and WebSockets)

### Edge Device (Hardware)
- **Raspberry Pi** (IoT Access Point Simulator)
- Standard Web Camera & Physical Display

---

## 🚀 Local Installation & Setup

If you wish to run the project locally for development or testing purposes, follow these steps:

### Prerequisites
- Python 3.10 or higher
- Node.js (v18+)
- A running instance of PostgreSQL

### 1. Backend Setup
Navigate to the backend directory and set up the Python environment:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the `backend` folder containing the required secrets and configurations:

```env
DATABASE_URL=postgresql://user:password@localhost/ailoqr_db
SECRET_KEY=your_secure_jwt_key
SIGNATURE_KEY=your_qr_cryptographic_key
ADMIN_KEY=your_admin_registration_passcode
SMTP_EMAIL=your.email@gmail.com
SMTP_PASSWORD=your_google_app_password
SESSION_TIMEOUT_MINUTES=10
RISK_SCORES_JSON='{"FORGED_QR": 10, "MALFORMED_QR": 10, "SYSTEM_LOCKDOWN": 10, "UNKNOWN_USER": 10, "AREA_VIOLATION": 3, "TIME_VIOLATION": 3, "EXPIRED_QR": 1, "UNKNOWN": 1}'
```

Seed the database and run the server by executing `app.py`:

```bash
python app.py
```

### 2. Frontend Setup
Open a new terminal, navigate to the frontend directory, and run the React app:

```bash
cd frontend
npm install
npm run dev
```

---

## Architecture Overview

1. **The Edge (Scanner):** A Python script runs on an IoT device, continuously scanning QR codes. It sends HTTP POST requests containing the scanned payload and target area to the cloud server.
2. **The Cloud (Backend):** Flask intercepts the payload, validates the HMAC-SHA256 signature, verifies RBAC rules against the PostgreSQL database, and runs the data point through the Isolation Forest ML model.
3. **The Interface (Frontend):** React connects via WebSockets to the cloud. Upon a successful or denied scan, the backend emits an event, instantly updating the Admin Dashboard and Security Center.
