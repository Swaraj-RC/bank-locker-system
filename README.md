# Bank Locker Operating System (Bank Locker OS)

An auditable, real-time digital bank locker management platform with integrated AI biometric face verification connected directly to **Project NPN** customer embeddings.

---

## 🏗️ Architecture Overview

```
                      ┌───────────────────────────────────────┐
                      │    Operator Web Portal (React/TS)     │
                      │         http://localhost:3000         │
                      └──────────────────┬────────────────────┘
                                         │  Webcam Biometrics & Requests
                                         ▼
                      ┌───────────────────────────────────────┐
                      │       FastAPI Backend Server          │
                      │         http://localhost:8000         │
                      └────────┬───────────────────┬──────────┘
                               │                   │
                               ▼                   ▼
                ┌─────────────────────────┐  ┌─────────────────────────┐
                │ SQLite / Database State │  │ Project NPN Embeddings  │
                │  Lockers & Audit Logs   │  │   customer001 / 002     │
                └─────────────────────────┘  └─────────────────────────┘
```

---

## 🚀 How to Run in VS Code

### Prerequisites
1. **Python 3.11+** installed.
2. **Node.js (v18+)** installed.
3. **VS Code** with the *Python* and *Tailwind CSS IntelliSense* extensions.

---

### Step 1: Open the Project in VS Code
1. Open VS Code.
2. Click **File** > **Open Folder...**
3. Select `c:\Users\Swaraj\OneDrive\Desktop\bank-locker-os`.

---

### Step 2: Start the Backend Server (Terminal 1)
Open a new terminal in VS Code (`Ctrl + ~` or **Terminal > New Terminal**):

```powershell
# Navigate to the backend directory
cd backend

# Activate the Python virtual environment
.\venv\Scripts\Activate.ps1

# Run the FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> **Backend URL:** [http://localhost:8000](http://localhost:8000)  
> **Interactive Swagger API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Step 3: Start the Operator Web Portal (Terminal 2)
Open a second terminal in VS Code (`+` button in the terminal panel):

```powershell
# Navigate to the admin web directory
cd admin-web

# Install dependencies (only needed the first time)
npm install

# Start the Vite development server
npm run dev -- --port 3000 --host 0.0.0.0
```

> **Operator Portal URL:** [http://localhost:3000](http://localhost:3000)

---

### 🔑 Login Credentials

| Role | Email | Password |
| :--- | :--- | :--- |
| **Bank Operator** | `operator@demo.bank` | `Demo@1234` |
| **System Admin** | `admin@demo.bank` | `Demo@1234` |

---

## 👤 AI Biometric Verification & Project NPN Integration

- **Registered Customers**: Uses data from `project NPN/NPN/data/embeddings/`:
  - `customer001.npy`
  - `customer002.npy`
- **Verification Rule**:
  - Live face matches `customer001` or `customer002` with distance $\le 0.50 \rightarrow$ **Approved & Access Active**.
  - Any unregistered face $\rightarrow$ **Rejected**.
- **Anti-Spoofing & 5-Second Alert**:
  - If a mobile phone screen or photo is placed in front of the lens, a full-screen **Red Alert** activates immediately.
  - If the mobile phone/photo is held for **5 continuous seconds**, face capture automatically cancels and shuts down for security.

---

## 📁 Repository Structure

```
bank-locker-os/
├── backend/                  # FastAPI Backend
│   ├── app/
│   │   ├── ai/               # AI Face Adapter & Project NPN connector
│   │   ├── api/routes/       # REST API Endpoints (Admin, Verification, Audit)
│   │   ├── core/             # Configuration & Database setup
│   │   ├── models/           # SQLAlchemy Database Models
│   │   └── services/         # Locker & Face Verification Services
│   ├── data/                 # SQLite database & embeddings
│   ├── venv/                 # Python virtual environment
│   └── requirements.txt      # Python dependencies
│
├── admin-web/                # Operator Web Portal
│   ├── src/
│   │   ├── components/       # FaceVerificationPanel, LockerGrid, Timeline
│   │   ├── pages/            # Dashboard, Requests, Lockers, Audit
│   │   └── api/              # Axios API Client
│   ├── package.json
│   └── vite.config.ts
│
└── README.md                 # Project Documentation
```
