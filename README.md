# AIoT-Based Product Journey Condition Intelligence

> **Tagline:** "From Origin to Destination – Every Condition Matters."

An intelligent, software-only Advanced Internet of Things (AIoT) course project platform that simulates IoT sensor readings throughout a product's transportation journey, detects harmful environmental exposure, predicts product quality risk using genuine trained Machine Learning models (Random Forest Classifier & Regressor), explains risk factors via tree path decomposition, evaluates counterfactual What-If scenarios, compares multi-shipment journeys, and generates downloadable PDF audit reports.

---

## 🌟 Key Highlights

- **100% Software-Only & Zero Hardware Required:** Programmatic simulation of temperature, humidity, and GPS progression along journey corridors using an Ornstein-Uhlenbeck stochastic model.
- **Genuine Machine Learning (No Hardcoding):**
  - **Random Forest Classifier:** Predicts categorical risk (*Low Risk*, *Medium Risk*, *High Risk*) with **94.5% test accuracy** and **0.925 macro F1**.
  - **Random Forest Regressor:** Predicts continuous risk score (*0.0 to 100.0*) with **R² = 0.986** and **MAE = 2.99 points**.
  - Trained on **15,000 snapshot records** across **5,000 synthetic journeys** using grouped train/test splits by journey ID to prevent data leakage.
- **Explainable Machine Learning:**
  - Global Permutation Feature Importance evaluated on held-out test journeys.
  - Local tree path contributions (Saabas / TreeInterpreter method) decomposing individual predictions into exact feature points.
- **What-If Counterfactual Simulator:** Interactively alter average temperature, peak excursions, humidity, delay duration, and violation counts without changing original recorded telemetry.
- **Multi-Shipment Comparison:** Side-by-side journey benchmarking, environmental stress comparison, and automated safest route identification.
- **Downloadable PDF Audit Reports:** Automated PDF document generation using ReportLab with complete route metadata, threshold compliance tables, and ML risk breakdowns.
- **Interactive OpenStreetMap Mapping:** Real-time route tracking and animated vehicle markers using Leaflet without any paid API keys.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, JavaScript (ES6+), React Router DOM v7, Chart.js, React-ChartJS-2, Leaflet, Vite |
| **Backend** | Python 3.11+, Flask REST API, Flask-CORS, python-dotenv |
| **Database** | SQLite with SQLAlchemy ORM (WAL mode enabled for concurrent simulator writes) |
| **Machine Learning** | Scikit-learn, Pandas, NumPy, Joblib, Tree Path Decomposition (Saabas method) |
| **PDF Reporting** | ReportLab |
| **Mapping** | Leaflet with OpenStreetMap tiles (100% free & open-source) |

---

## 📁 Project Architecture

```
IOT/
├── backend/
│   ├── app/
│   │   ├── core/              # Domain logic: sensor model, exposure rules, risk formula, features
│   │   ├── routes/            # REST API blueprints (Auth, Shipments, Sim, Alerts, ML, Reports, Dash)
│   │   ├── services/          # Background simulation engine, ML inference, analytics, database seed
│   │   ├── config.py          # App configuration & secure token generation
│   │   ├── extensions.py      # SQLAlchemy with SQLite WAL pragma
│   │   ├── models.py          # ORM models (Users, Shipments, Readings, Alerts, Predictions, Scenarios)
│   │   └── utils.py           # Parameter validation & error formatting
│   ├── ml/
│   │   ├── data/              # Generated synthetic dataset (5,000 journeys / 15,000 snapshots)
│   │   ├── models/            # Saved Joblib models & metrics.json evaluation summary
│   │   ├── generate_dataset.py# Synthetic dataset generator
│   │   └── train_models.py    # Random Forest training & permutation importance
│   ├── tests/                 # Pytest test suite
│   ├── requirements.txt       # Backend Python dependencies
│   └── run.py                 # Backend launch script
├── frontend/
│   ├── src/
│   │   ├── components/        # Layout, Persistent Sidebar Navigation
│   │   ├── context/           # AuthContext (JWT-style token state)
│   │   ├── pages/             # 10 Responsive Views (Dashboard, Shipments, Monitoring, ML, What-If, etc.)
│   │   ├── services/          # Central API client
│   │   ├── App.jsx            # Routing configuration
│   │   └── index.css          # Industrial IoT & SaaS Design System
│   ├── package.json           # Frontend dependencies
│   └── vite.config.js         # Vite configuration with API reverse proxy
└── README.md
```

---

## 🚀 Quickstart & Execution Guide

### Prerequisites
- Python 3.10+ (Python 3.11 recommended)
- Node.js 18+ and npm

---

### Step 1: Set Up & Launch the Backend

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. *(Optional — Already Pre-trained)* To regenerate the 5,000-journey dataset and retrain models:
   ```bash
   python -m ml.generate_dataset
   python -m ml.train_models
   ```

5. Run automated tests to verify API endpoints:
   ```bash
   PYTHONPATH=. pytest tests/
   ```

6. Start the Flask REST API server (runs on port 5001):
   ```bash
   python run.py
   ```
   *Note: On first startup, the database automatically seeds 5 demonstration shipments across all product categories with simulated sensor readings, alerts, and trained ML predictions.*

---

### Step 2: Set Up & Launch the Frontend

1. In a new terminal window, navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```

2. Install npm dependencies:
   ```bash
   npm install
   ```

3. Start the Vite development server:
   ```bash
   npm run dev
   ```

4. Open your browser and navigate to:
   ```
   http://localhost:5173
   ```

---

## 🔑 Default Credentials

The system comes pre-configured with two user roles:

| Role | Username | Password | Access Scope |
|---|---|---|---|
| **Administrator** | `admin` | `Admin@1234` | Full access, user management, profile creation, and simulation controls |
| **Operator** | `operator` | `Operator@1234` | Fleet monitoring, What-If scenarios, comparisons, and PDF downloads |

*You can also register custom accounts directly on the login page.*

---

## 📦 Nine Core Application Modules

1. **Authentication & Dashboard:** Secure token authentication, executive summary cards, risk distribution charts, and shipment status tracking.
2. **Shipment Management:** Full CRUD operations for consignments with unique ID generation (`SHP-DAIR-XXXXXX`), origin/destination selection, and transport modes.
3. **Automatic IoT Sensor Simulator:** Threaded background engine simulating realistic temperature, humidity, and GPS readings with `NORMAL`, `WARNING`, and `CRITICAL` excursion modes. Includes Start, Pause, Resume, and Stop controls.
4. **Harmful Exposure Detection Engine:** Duration-aware severity rating (`Low`, `Medium`, `High`, `Critical`) distinguishing brief crossings from extended damaging excursions.
5. **Machine Learning Prediction Engine:** Random Forest Classifier & Regressor evaluated against held-out journeys (Accuracy: 94.5%, R²: 0.986).
6. **Explainable ML:** Global permutation importance and local tree path decomposition (Saabas method) showing exact point contributions for temperature, humidity, and duration.
7. **What-If Journey Simulator:** Signature feature allowing interactive condition experimentation on existing consignments without altering raw telemetry.
8. **Shipment Risk Comparison:** Side-by-side journey benchmarking, environmental stress history comparison, and automated safest journey determination.
9. **Journey Condition Reports:** Downloadable publication-quality PDF reports generated with ReportLab.

---

## 🎓 Academic Course Project Notice

All sensor telemetry and environmental readings are synthesized programmatically for educational and research demonstration. Machine Learning predictions reflect simulated environmental quality risk estimates and do not represent physical sensor readings or certified laboratory spoilage release certifications.

