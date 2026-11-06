# Project: AIoT-Based Product Journey Condition Intelligence

## Architecture
- **Backend**: Flask 3.1.x, SQLAlchemy 2.0 with SQLite WAL mode, scikit-learn pre-trained Random Forest models, pure NumPy Saabas tree path contributions, ReportLab PDF generation.
- **Frontend**: React 19, Vite 8, React Router v7, Chart.js, React-ChartJS-2, Leaflet mapping, Apple-inspired responsive UI with mobile drawer and tab bar.
- **Cross-Service**: REST API with CORS, JSON payloads, bearer token authentication, serverless-ready architecture.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | User Authentication | Login, registration, token issuance, logout token invalidation | M1 | Survey / M1 Spec |
| 2 | RBAC Security Enforcement | Admin vs Operator role gating on sensitive operations | M1 | Survey / M1 Spec |
| 3 | Executive Dashboard | KPI summary cards, status chart, risk distribution chart, environmental monitoring | M3 | Survey / M1 Spec |
| 4 | Shipment Management CRUD | Create, view details, edit shipment, delete with modal confirmation | M1, M3 | Survey / M2 Spec |
| 5 | Shipment Journey Lifecycle | Start, pause, resume, stop, and mark completed | M1 | Survey / M2 Spec |
| 6 | Automatic IoT Sensor Simulator | NORMAL, WARNING, CRITICAL modes, fluctuations, location progression | M1 | Survey / M3 Spec |
| 7 | Simulator State Machine Guard | Prevent illegal transitions and validate mode on journey restarts | M1 | Survey / M3 Spec |
| 8 | Leaflet Route Visualization | Real-time truck marker, route polyline, origin/destination pins without memory leaks | M3 | Survey / M3 Spec |
| 9 | Harmful Exposure Detection | Temp/humidity threshold violations, duration tracking, severity calculation (Low/Med/High/Critical) | M1 | Survey / M4 Spec |
| 10 | Alert Lifecycle & IDs | Grace periods, sensitivity multipliers, unique ALT-<HEX> identifiers | M1 | Survey / M4 Spec |
| 11 | Genuine ML Risk Classifier | Pre-trained Random Forest Classifier predicting Low/Medium/High risk | M2 | Survey / M5 Spec |
| 12 | Genuine ML Risk Regressor | Pre-trained Random Forest Regressor predicting continuous 0-100 quality risk score | M2 | Survey / M5 Spec |
| 13 | Global Feature Importance | Grouped permutation importance over synthetic test journeys | M2 | Survey / M6 Spec |
| 14 | Local Saabas Attribution | Exact tree path contributions computed in pure NumPy from fitted trees | M2 | Survey / M6 Spec |
| 15 | What-If Journey Simulator Backend | Isolated counterfactual inference, shift factors, scenario persistence | M2 | Survey / M7 Spec |
| 16 | What-If Simulator Frontend UI | Sliders for 6 dimensions (including humidity exposure), delta banner, comparison chart | M3 | Survey / M7 Spec |
| 17 | Shipment Risk Comparison | Side-by-side comparison of 2+ shipments, cross-category warning, safest journey identification | M2, M3 | Survey / M8 Spec |
| 18 | Journey Condition PDF Report | ReportLab PDF with metadata, timeline, thresholds, ML risk assessment, Saabas contributions, alerts | M2, M3 | Survey / M9 Spec |
| 19 | Test Runner & Discovery Config | Frictionless pytest discovery with root conftest/pytest.ini | M1 | Survey / Test Infra |
| 20 | Multi-Tier Test Verification | 100% passage across Tier 1 (Feature), Tier 2 (Boundary), Tier 3 (Cross-Feature), Tier 4 (Real-World) | M4 | E2E Testing Track |
| 21 | Adversarial Integrity Audit | Forensic verification ensuring genuine computation, zero hardcoding, zero cheating | M4 | Final Milestone Phase 2 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Backend Core & Security Remediation | RBAC enforcement (`admin_required` on products/delete, secure registration), simulator restart mode fix, null handling in feature vectors, pytest config | none | DONE |
| M2 | Backend ML, Analytics & Report Remediation | Safe unauthenticated `user_id` in what-if, human-readable category labels in comparison, PDF edge case robustness | M1 | DONE |
| M3 | Frontend Defect Remediation & UI Features | Shipment Edit modal, styled delete modal, humidity slider in What-If, Leaflet marker leak & bounds fix, dashboard environmental cards, RBAC UI gating, loading/error states | M1, M2 | DONE |
| M4 | Final Milestone: Full Test Pass & Adversarial Verification | Phase 1: Pass 100% of Tiers 1-4 E2E/whitebox tests. Phase 2: Adversarial coverage hardening (Tier 5) with Challenger and Forensic Auditor | M1, M2, M3, TEST_READY | DONE |

## Code Layout
- `backend/app/`
  - `auth.py`: JWT/serializer auth decorators, `login_required`, `admin_required`
  - `models.py`: SQLAlchemy ORM models (`User`, `ProductProfile`, `Shipment`, `SensorReading`, `ExposureAlert`, `MLPrediction`, `SimulationScenario`)
  - `config.py`: App configuration, SQLite PRAGMA, JWT secret, CORS origins
  - `core/`: Core business logic (`sensor_model.py`, `exposure.py`, `features.py`, `explain.py`)
  - `services/`: Services (`simulation_engine.py`, `ml_service.py`, `analytics.py`, `seed.py`)
  - `routes/`: Blueprint endpoints (`auth_routes.py`, `shipment_routes.py`, `simulation_routes.py`, `ml_routes.py`, `report_routes.py`, `dashboard_routes.py`, `product_routes.py`)
- `backend/ml/`
  - `models/`: `risk_classifier.joblib`, `risk_regressor.joblib`, `metrics.json`
- `backend/tests/`: Pytest whitebox and API integration tests
- `frontend/src/`
  - `components/`: `Layout.jsx`, `Sidebar.jsx`, UI modals and widgets
  - `context/`: `AuthContext.jsx`
  - `pages/`: `DashboardPage.jsx`, `ShipmentsPage.jsx`, `CreateShipmentPage.jsx`, `MonitoringPage.jsx`, `AlertsPage.jsx`, `MLAnalysisPage.jsx`, `WhatIfPage.jsx`, `ComparePage.jsx`, `ReportsPage.jsx`, `ProductsPage.jsx`
  - `services/`: `api.js`

## Interface Contracts
### Auth & RBAC
- `POST /api/auth/register`: body `{username, password, email, full_name, role}` -> role defaults to `operator`. `admin` registration rejected unless requested by existing admin.
- `DELETE /api/shipments/<id>`: Protected by `@admin_required`. Returns 403 for operator.
- `POST /api/products` & `PUT /api/products/<id>`: Protected by `@admin_required`. Returns 403 for operator.

### Simulator Mode Transitions
- `POST /api/simulation/start/<id>`: body `{mode, interval_seconds, step_minutes, intensity}`. Validates `mode in ('NORMAL', 'WARNING', 'CRITICAL')` even on restarted shipments.

### ML & What-If
- `POST /api/simulator/what-if`: body `{shipment_id, avg_temp, max_temp, avg_humidity, temp_exposure_hours, humidity_exposure_hours, journey_duration_hours, violation_count, name}`. Safely handles missing/anonymous `user_id`.
- `POST /api/compare`: body `{shipment_ids: [...]}`. Returns `category_label` formatted with human-readable string.
