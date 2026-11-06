# Backend Architecture and ML Subsystems Survey Report

## 1. Observation

### 1.1 Backend Structure & Application Setup
- **Application Factory**: Located at `backend/app/__init__.py:12-44`. `create_app()` initializes Flask 3.1.x, configures `db.init_app(app)` (`Flask-SQLAlchemy 3.1.x`, `SQLAlchemy 2.0.x`), enables `CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})`, registers error handlers, registers 8 blueprints, invokes `db.create_all()` and `ensure_default_profiles()` within an app context, calls `ml_service.init_app(app)`, and optionally starts the background simulation daemon thread (`engine.start(app)`).
- **SQLite Database & WAL Mode**: In `backend/app/extensions.py:9-26`, an SQLAlchemy event listener on `Engine.connect` sets SQLite PRAGMAs:
  ```python
  cursor.execute("PRAGMA foreign_keys=ON")
  cursor.execute("PRAGMA journal_mode=WAL")
  ```
  This allows concurrent reads during background telemetry simulator writes without database locked errors.
- **ORM Models**: Defined in `backend/app/models.py:27-420`:
  1. `User` (lines 27-63): `id`, `username`, `email`, `full_name`, `password_hash`, `role` (`admin`/`operator`), `token_version`, `preferences`, `is_active`, `created_at`, `last_login_at`.
  2. `ProductProfile` (lines 68-116): `id`, `name`, `category`, `min_temp`, `max_temp`, `min_humidity`, `max_humidity`, `sensitivity`, `description`, `is_default`, `created_by_id`, `created_at`, `updated_at`.
  3. `Shipment` (lines 121-247): `id`, `shipment_code`, `product_name`, `product_profile_id`, `source_location`, `source_lat`, `source_lon`, `destination_location`, `destination_lat`, `destination_lon`, `start_time`, `expected_delivery_time`, `actual_delivery_time`, `transport_type`, `status`, `notes`, `sim_mode`, `sim_interval_seconds`, `sim_step_minutes`, `sim_progress`, `sim_elapsed_minutes`, `sim_state` (JSON), `sim_started_at`.
  4. `SensorReading` (lines 252-292): `id`, `shipment_id` (FK with CASCADE), `sequence`, `timestamp`, `recorded_at`, `temperature`, `humidity`, `latitude`, `longitude`, `progress`, `is_delayed`, `temp_violation`, `humidity_violation`. Unique constraint on `(shipment_id, sequence)`.
  5. `ExposureAlert` (lines 297-339): `id`, `alert_code` (`ALT-<8HEX>`), `shipment_id` (FK with CASCADE), `alert_type`, `severity`, `recorded_value`, `threshold_value`, `exposure_duration_minutes`, `started_at`, `timestamp`, `description`, `is_active`.
  6. `MLPrediction` (lines 344-385): `id`, `shipment_id` (FK with CASCADE), `created_at`, `risk_class`, `class_probabilities` (JSON), `risk_score`, `features` (JSON), `explanation` (JSON), `model_version`, `trigger`, `reading_count`.
  7. `SimulationScenario` (lines 390-420): `id`, `shipment_id` (FK with CASCADE), `user_id` (FK SET NULL), `name`, `original_features` (JSON), `modified_features` (JSON), `original_prediction` (JSON), `simulated_prediction` (JSON), `created_at`.
- **Database Seed Data**: In `backend/app/services/seed.py:105-275`:
  - Default users: `admin` (`Admin@1234`, role admin) and `operator` (`Operator@1234`, role operator).
  - 5 default product profiles for categories `fruits_vegetables`, `dairy`, `frozen`, `pharmaceutical`, `flowers`.
  - 5 realistic demo shipments with pre-simulated historical readings, exposure alerts, and ML predictions: `SHP-1001-DAIRY`, `SHP-1002-PHARMA`, `SHP-1003-FROZEN`, `SHP-1004-BERRIES`, `SHP-1005-FLOWERS`.

### 1.2 Machine Learning Engine (Module 5 & Module 6)
- **Trained Model Artifacts**: Located in `backend/ml/models/`:
  - `risk_classifier.joblib`: 2.8 MB, genuine `RandomForestClassifier(n_estimators=150, max_depth=16, min_samples_leaf=3, class_weight='balanced', random_state=42)`.
  - `risk_regressor.joblib`: 11 MB, genuine `RandomForestRegressor(n_estimators=150, max_depth=16, min_samples_leaf=3, random_state=42)`.
  - `metrics.json`: Evaluation results and permutation importance from model training.
- **Dataset Generation**: `backend/ml/generate_dataset.py:47-96` generated `synthetic_journeys.csv` containing 15,000 snapshot records across 5,000 simulated journeys (using the same sensor model used by live journeys).
- **Features & Vectors**: In `backend/app/core/features.py:4-44`:
  - 7 Numeric features: `avg_temp`, `max_temp`, `avg_humidity`, `temp_exposure_hours`, `humidity_exposure_hours`, `journey_duration_hours`, `violation_count`.
  - 5 One-hot category indicators: `cat_fruits_vegetables`, `cat_dairy`, `cat_frozen`, `cat_pharmaceutical`, `cat_flowers`.
  - Total input vector: 12 floats (`build_feature_row(category, stats)`).
- **Evaluation Performance**: As recorded in `backend/ml/models/metrics.json:52-110`:
  - Classifier Accuracy: 94.53%, Precision Macro: 91.48%, Recall Macro: 94.19%, Macro F1: 92.48%.
  - Regressor MAE: 2.9879, RMSE: 4.0970, R²: 0.9856.
- **Explainable ML (Module 6) - Global Feature Importance**:
  - Computed during training via `grouped_permutation_importance` (`backend/ml/train_models.py:56-75`) on held-out test journeys (GroupShuffleSplit 80/20 by `journey_id`, with one-hot category columns permuted jointly).
  - Regressor top drivers: `temp_exposure_hours` (drop in R²: 1.4525), `humidity_exposure_hours` (0.0423), `max_temp` (0.0159), `journey_duration_hours` (0.0147).
- **Explainable ML (Module 6) - Local Feature Attribution (Saabas Tree Path Contributions)**:
  - Implemented in `backend/app/core/explain.py:28-56`:
    ```python
    for est in forest.estimators_:
        values = _node_values(est, is_classifier)
        feature = est.tree_.feature
        path = np.sort(est.decision_path(x).indices)
        base_total += values[path[0]]
        for parent, child in zip(path[:-1], path[1:]):
            contrib_total[feature[parent]] += values[child] - values[parent]
    ```
  - Calculates the exact algebraic decomposition: `prediction = base_value + sum(contributions)` across all individual decision trees of the scikit-learn random forest without external heavy dependencies.
  - Zero hardcoding: values reflect real model decision path changes.

### 1.3 Harmful Exposure Detection (Module 4)
- **Rules & Bounds**: In `backend/app/core/exposure.py:49-60`, `violations_for()` checks temperature against `[min_temp, max_temp]` and humidity against `[min_humidity, max_humidity]`, emitting `TEMPERATURE_HIGH`, `TEMPERATURE_LOW`, `HUMIDITY_HIGH`, or `HUMIDITY_LOW`.
- **Severity Formula**: In `backend/app/core/exposure.py:63-71`:
  $$\text{score} = \text{mult} \times \left(60 \times \min\left(\frac{\text{peak\_dev}}{\text{span}}, 1.5\right) \times \text{type\_weight} + 12 \times \min\left(\frac{\text{duration\_minutes}}{60}, 6.0\right)\right)$$
  - `mult`: Low (0.7), Medium (1.0), High (1.3), Very High (1.6)
  - `type_weight`: 1.0 (temperature), 0.6 (humidity)
  - Severity bands: Low (<20), Medium (20-39), High (40-64), Critical (>=65).
- **Alert Suppression (Grace Period)**: In `backend/app/core/exposure.py:81-83`, alerts are suppressed during initial crossing unless duration exceeds product grace period (Low: 45 min, Medium: 30 min, High: 15 min, Very High: 0 min) OR severity score already reaches High (score >= 40).
- **Alert IDs & Lifecycle**: In `backend/app/services/simulation_engine.py:60-94`, unique `alert_code` generated as `ALT-<8 hex chars uppercase>`. Severity only escalates during an active episode.

### 1.4 What-If Simulator Backend (Module 7)
- **Endpoint**: `POST /api/simulator/what-if` in `backend/app/routes/ml_routes.py:67-176`.
- **Behavior**: Modifies condition parameters (`avg_temp`, `max_temp`, `avg_humidity`, `temp_exposure_hours`, `humidity_exposure_hours`, `journey_duration_hours`, `violation_count`) without altering recorded telemetry.
- **Inference & Comparison**: Executes genuine models on baseline and modified inputs, computes `score_difference`, `risk_class_changed`, and per-feature `shift_factors`.
- **Persistence**: Persists scenarios to `simulation_scenarios` table if a `name` is provided; scenarios can be listed via `GET /api/simulator/scenarios/<shipment_id>`.

### 1.5 Journey Condition Report (Module 9)
- **Endpoint**: `GET /api/reports/<shipment_id>/pdf` in `backend/app/routes/report_routes.py:238-257`.
- **ReportLab Implementation**: In `backend/app/routes/report_routes.py:25-235`, `build_pdf_report()` generates an official PDF document containing:
  1. Header banner, audit metadata, and branding.
  2. Shipment Overview & Route Profile table.
  3. Configured Environmental Thresholds vs Recorded Extremes/Averages table.
  4. ML Product Quality Risk Assessment (classification badge, score, model architecture, model version, and top Saabas tree path contributing factors with impact points).
  5. Harmful Exposure Incidents table (alert code, severity, type, peak value, duration, trigger time).
  6. Course project disclaimer.
- Returns binary PDF attachment with filename `Journey_Report_<shipment_code>.pdf`.

### 1.6 API Routes & Controllers
- **Module 1 (Auth)**: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`. Uses `URLSafeTimedSerializer` with `token_version` invalidation on logout.
- **Module 2 (Shipments)**: `GET /api/shipments`, `GET /api/shipments/<id>`, `POST /api/shipments`, `PUT /api/shipments/<id>`, `DELETE /api/shipments/<id>`, `GET /api/shipments/locations`. Unique codes formatted `SHP-<CAT>-<HEX>`.
- **Module 3 (Simulator)**: `POST /api/simulation/start/<id>`, `POST /api/simulation/pause/<id>`, `POST /api/simulation/resume/<id>`, `POST /api/simulation/stop/<id>`, `POST /api/simulation/complete/<id>`, `GET /api/readings/<id>`. State machine enforced in `SimulationEngine`.
- **Module 8 (Comparison)**: `POST /api/compare` in `backend/app/routes/ml_routes.py:185-281`. Compares 2+ shipments side-by-side, flags cross-category comparisons with `category_warning`, and identifies `safest_shipment` with reasoning.
- **Dashboard & Products**: `GET /api/dashboard/stats`, `GET /api/products`, `POST /api/products`, `PUT /api/products/<id>`.

### 1.7 Discovered Bugs & Weaknesses
1. **Unsafe User ID Access in What-If Simulator** (`backend/app/routes/ml_routes.py:149`):
   ```python
   user_id=getattr(g, "current_user", None).id if hasattr(g, "current_user") else None,
   ```
   If `g.current_user` is not set or is `None`, accessing `.id` can throw an `AttributeError`. Furthermore, `POST /api/simulator/what-if` has no `@login_required` or auth extraction, so `g.current_user` is never populated even if a valid bearer token is sent.
2. **Category Label Key vs Name Bug in Comparison** (`backend/app/routes/ml_routes.py:237`):
   ```python
   "category_label": s.product_profile.category,
   ```
   This returns the machine category slug (e.g., `"fruits_vegetables"`) instead of the human-readable label (`category_label(s.category)` -> `"Fruits and Vegetables"`), inconsistent with `Shipment.to_dict()` and `ProductProfile.to_dict()`.
3. **Pytest PYTHONPATH Requirement**:
   Running `pytest backend/tests` directly from root fails with `ModuleNotFoundError: No module named 'app'` unless `PYTHONPATH=backend` is supplied or a `conftest.py` adds `backend` to `sys.path`.
4. **N+1 Queries in Listing Endpoints**:
   `GET /api/shipments` and `GET /api/dashboard/stats` execute N subqueries for `latest_prediction()`, `readings.count()`, and `alerts.count()`.

---

## 2. Logic Chain

1. **Premise**: Genuine machine learning requires pre-trained statistical or decision-tree models persisted on disk and loaded into memory, rather than static rule-based lookups or random number generators.
   - **Evidence**: `risk_classifier.joblib` (2.8MB) and `risk_regressor.joblib` (11MB) are binary serialized scikit-learn models. In `backend/app/services/ml_service.py:60-62`, `joblib.load()` loads both models. Direct test execution produced real floating-point probability distributions and continuous regression scores (e.g. 23.31 score, 33.31 base score).
   - **Conclusion**: The ML models are genuine, pre-trained, and properly integrated.

2. **Premise**: Explainable AI requires mathematically sound attribution of model predictions to input features.
   - **Evidence**: `backend/app/core/explain.py:28-56` calculates Saabas tree path contributions by navigating the decision path of each tree in the Random Forest, subtracting parent node values from child node values, and averaging across all 150 estimators. The sum of contributions plus base value exactly equals the predicted score. Global permutation importance was computed on held-out test journeys.
   - **Conclusion**: Explainable ML is genuinely computed from model decision paths, not hardcoded.

3. **Premise**: What-If simulation must allow users to test counterfactual scenarios without corrupting empirical sensor telemetry.
   - **Evidence**: `POST /api/simulator/what-if` accepts modified parameters, builds a synthetic feature row, queries the loaded ML models, and returns deltas. It never creates or modifies rows in `sensor_readings`. Scenario data is stored separately in `simulation_scenarios`.
   - **Conclusion**: What-If journey simulation strictly fulfills the isolation requirement.

4. **Premise**: Report generation must be resilient to empty telemetry and provide comprehensive audit data.
   - **Evidence**: Executing `build_pdf_report()` with zero readings produced a 3,687-byte valid PDF document with N/A placeholders and clean tables without runtime exceptions.
   - **Conclusion**: ReportLab PDF generation handles both normal and empty journeys safely.

---

## 3. Caveats

- **Frontend Client Survey**: This survey focused exclusively on the Backend Architecture and ML subsystems as requested. The React frontend components and state store were not surveyed in this report.
- **Serverless Background Simulation**: In serverless environments (e.g., Vercel), background threads cannot run across ephemeral function invocations; `SIM_ENGINE_ENABLED=0` disables the continuous daemon in serverless mode, relying on API step triggers or local persistent execution.
- **Model Training Speed**: Retraining models (`python -m ml.train_models`) on 15,000 samples takes approximately 10-15 seconds; models should remain pre-trained and loaded from `ml/models/`.

---

## 4. Conclusion

The Backend Architecture and ML subsystems are solidly implemented, well-structured, and fully aligned with the technical specification:
- **Backend**: Flask application factory with SQLite WAL mode, foreign keys, and complete ORM models (`User`, `ProductProfile`, `Shipment`, `SensorReading`, `ExposureAlert`, `MLPrediction`, `SimulationScenario`).
- **ML Subsystems**: Genuine Random Forest models (Classifier 2.8MB, Regressor 11MB) with high accuracy (94.5%) and R² (0.986), loaded via `joblib`.
- **Explainable ML**: Grounded mathematical implementation of Saabas tree path contributions in pure NumPy and grouped permutation importance.
- **Harmful Exposure**: Duration-aware multi-band severity scoring with grace periods, sensitivity multipliers, and unique alert codes.
- **What-If Simulator & Reporting**: Pure counterfactual simulations and ReportLab PDF journey audit generation.
- **Identified Items to Fix**: Two minor bugs in `ml_routes.py` (safe `user_id` retrieval and `category_label` formatting) and a `conftest.py` addition for frictionless test discovery.

---

## 5. Verification Method

To independently verify all findings in this report, execute the following commands in terminal:

1. **Verify Backend Pytest Suite**:
   ```bash
   PYTHONPATH=backend backend/.venv/bin/pytest backend/tests
   ```
   *Expected*: 6 passed tests in ~3.5 seconds.

2. **Verify ML Models & Saabas Attribution**:
   ```bash
   PYTHONPATH=backend backend/.venv/bin/python -c '
   from app import create_app
   from app.services import ml_service
   app = create_app(start_engine=False)
   with app.app_context():
       info = ml_service.model_info()
       print("Model version:", info["model_version"])
       stats = {"avg_temp": 5.2, "max_temp": 8.1, "avg_humidity": 85.0, "temp_exposure_hours": 1.5, "humidity_exposure_hours": 0.5, "journey_duration_hours": 12.0, "violation_count": 2}
       pred = ml_service.predict_from_stats("dairy", stats)
       print("Prediction:", pred["risk_class"], pred["risk_score"])
       print("Base score:", pred["explanation"]["score_base"])
       for f in pred["explanation"]["score_contributions"][:3]:
           print("  Contribution:", f["label"], f["contribution"])
   '
   ```
   *Expected*: Loaded models `rf-20261106085849`, Low Risk score ~23.31, Base score ~33.31, exact Saabas feature contributions.

3. **Verify ReportLab PDF Generation**:
   ```bash
   PYTHONPATH=backend backend/.venv/bin/python -c '
   from app import create_app
   from app.models import Shipment
   from app.routes.report_routes import build_pdf_report
   from app.services.analytics import shipment_stats
   app = create_app(start_engine=False)
   with app.app_context():
       s = Shipment.query.first()
       stats = shipment_stats(s)
       pdf = build_pdf_report(s, stats, s.latest_prediction(), s.alerts.all(), s.readings.all())
       print("ReportLab PDF bytes generated:", len(pdf.getvalue()))
   '
   ```
   *Expected*: Non-empty PDF bytes (>10,000 bytes) generated with tables and styling.
