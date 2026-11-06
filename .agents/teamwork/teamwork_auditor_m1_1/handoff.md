# Forensic Audit Report — Milestone 1 Work Product

**Work Product**: Milestone 1 code changes (`backend/app/auth.py`, `backend/app/core/features.py`, `backend/app/routes/auth_routes.py`, `backend/app/routes/product_routes.py`, `backend/app/routes/shipment_routes.py`, `backend/app/services/simulation_engine.py`, `backend/pytest.ini`)
**Profile**: General Project
**Verdict**: **CLEAN**

---

## 1. Observation

Direct forensic inspection of the codebase, modified git targets, and test execution environment yielded the following factual observations:

### A. Source Code & Git Diff Observations
1. **RBAC & Cryptographic Authentication (`backend/app/auth.py`, `backend/app/routes/product_routes.py`, `backend/app/routes/shipment_routes.py`, `backend/app/routes/auth_routes.py`)**:
   - `backend/app/auth.py` lines 18-20, 26-41: Uses `itsdangerous.URLSafeTimedSerializer` with application `SECRET_KEY` and salt `aiot-journey-auth` to cryptographically sign and verify bearer tokens.
   - `backend/app/auth.py` lines 44-52: `get_current_user()` lazily resolves `_user_from_request()`, securely validating cryptographic signatures, token expiration (`TOKEN_MAX_AGE_HOURS`), database existence (`db.session.get(User, uid)`), active status (`user.is_active`), and revocation status (`user.token_version == payload['tv']`).
   - `backend/app/auth.py` lines 69-77: `@admin_required` wraps `@login_required`, strictly checking `g.current_user.role != 'admin'` and returning HTTP 403 `{"error": "Administrator role required."}` upon role mismatch.
   - `backend/app/routes/product_routes.py` lines 32-34 and 70-72: Applied `@admin_required` to both `POST /api/products` and `PUT /api/products/<int:profile_id>`.
   - `backend/app/routes/shipment_routes.py` lines 147-149: Applied `@admin_required` to `DELETE /api/shipments/<int:shipment_id>`.
   - `backend/app/routes/auth_routes.py` lines 26-30: In `register()`, enforces that requests with `role == 'admin'` require an authenticated admin caller (`get_current_user()`), rejecting unauthenticated callers and operators with HTTP 403 `{"error": "Only administrators can register admin accounts."}`.

2. **Simulation Mode Validation (`backend/app/services/simulation_engine.py`)**:
   - `backend/app/services/simulation_engine.py` lines 37-48: Enhanced `SimulationError` to accept `status_code`, defaulting to `400` when the error pertains to simulation mode and `409` for lifecycle conflicts.
   - `backend/app/services/simulation_engine.py` lines 242-243 & 249-250: Both initial start and stopped-journey restart explicitly validate:
     ```python
     if mode not in Shipment.SIM_MODES or mode not in MODE_PARAMS:
         raise SimulationError(f"Invalid simulation mode: {mode}", 400)
     ```
     where `Shipment.SIM_MODES` is `("NORMAL", "WARNING", "CRITICAL")` and `MODE_PARAMS` is the model dictionary in `backend/app/core/sensor_model.py`.

3. **Feature Extractor Alignment (`backend/app/core/features.py`)**:
   - Lines 37-43:
     ```python
     def build_feature_row(category: str, stats: dict) -> list:
         if category not in CATEGORY_KEYS:
             raise ValueError(f"Unknown product category: {category}")
         row = [float(stats.get(name) or 0.0) for name in NUMERIC_FEATURES]
         row += [1.0 if c == category else 0.0 for c in CATEGORY_KEYS]
         return row
     ```
   - Features produced: Exactly 12 features (7 numeric features + 5 one-hot category keys), matching `backend/ml/models/metrics.json` lines 5-18 (`FEATURE_NAMES`).
   - Null handling: Missing or `None` values evaluate through `stats.get(name) or 0.0` to valid `0.0` floats, preventing `TypeError` and `KeyError`.

4. **Pytest Discovery Configuration (`backend/pytest.ini`)**:
   - Contains:
     ```ini
     [pytest]
     pythonpath = . app
     testpaths = tests
     ```
     This allows executing `pytest backend/tests` directly from repository root without manual `PYTHONPATH` manipulation.

### B. Forensic Prohibited Patterns Check
- **Check 1: Hardcoded test return values**: Searched codebase for hardcoded test responses or fake bypasses. Found: 0 occurrences.
- **Check 2: Mocking / test cheats**: Searched `backend/tests/` for `mock`, `unittest.mock`, `monkeypatch`, or `patch()`. Found: 0 occurrences. All tests use real Flask client contexts, real SQLite database transactions, genuine itsdangerous cryptographic token validation, and real scikit-learn models.
- **Check 3: Dummy facades**: Verified all mutated endpoints execute real database operations and state transitions. No stubbed return values.
- **Check 4: Pre-populated artifacts**: Searched workspace for pre-existing log/result artifacts (`find . -name "*.log" -o -name "*result*"`). Found: 0 pre-populated result files in project source or `.agents/`.

### C. Independent Behavioral Execution
Ran the test suite independently:
```bash
/Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests
```
Raw execution output:
```text
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-8.4.2, pluggy-1.7.0
rootdir: /Users/porandlarajkumar/Documents/IOT/backend
configfile: pytest.ini
collecting ... collected 80 items

backend/tests/test_api.py ......                                         [  7%]
backend/tests/test_auth_rbac.py ......................                   [ 35%]
backend/tests/test_e2e_scenarios.py .....                                [ 41%]
backend/tests/test_exposure_ml.py ..............                         [ 58%]
backend/tests/test_shipments_simulator.py .....................          [ 85%]
backend/tests/test_whatif_compare_reports.py ............                [100%]

============================= 80 passed in 29.82s ==============================
```

---

## 2. Logic Chain

1. **Step 1 (Integrity Mode & Scope)**:
   - Evaluated against `ORIGINAL_REQUEST.md` constraints: Stack specifies Flask backend, SQLite, scikit-learn models, ReportLab, React frontend. Requirement: genuine ML model predictions, genuine testing without shortcuts or facades.
2. **Step 2 (RBAC Enforcement Verification)**:
   - Tested cryptographic token issuance and verification independently using an adversarial test harness.
   - Verified that unauthenticated requests to `/test-admin-only` return HTTP 401.
   - Verified that tampered token signatures return HTTP 401.
   - Verified that deactivated users (`is_active=False`) return HTTP 401 even with valid signed tokens.
   - Verified that operator tokens accessing `@admin_required` endpoints return HTTP 403 `{"error": "Administrator role required."}`.
   - Verified that admin tokens accessing `@admin_required` endpoints return HTTP 200.
   - Tested registration privilege escalation: anonymous and operator requests specifying `role="admin"` are rejected with HTTP 403. Admin-authenticated requests successfully register admin accounts with HTTP 201.
3. **Step 3 (Simulation Mode Validation Verification)**:
   - Adversarially tested `engine.start_journey` with malformed modes: `""`, `"normal"` (lowercase), `"CRITICAL "` (trailing space), `None`, `123`, `"HACK_MODE"`, `"normal\n"`.
   - Every malformed mode was rejected on initial start with `SimulationError` (HTTP 400).
   - After a journey was started with `"NORMAL"` and transitioned to `"Stopped"`, restarted with the same invalid modes: every malformed mode was rejected on restart with `SimulationError` (HTTP 400).
   - Valid mode restart with `"WARNING"` succeeded and transitioned state to `"In Transit"`.
4. **Step 4 (Feature Extractor Vector Alignment Verification)**:
   - Empirically evaluated `build_feature_row` with full telemetry dictionaries and sparse/null dictionaries (`{'avg_temp': None}`).
   - Verified vector length is exactly 12 (`len(row) == 12`).
   - Verified all 12 elements are genuine Python floats (`isinstance(x, float)`).
   - Verified one-hot category encoding correctly sets index corresponding to `CATEGORY_KEYS` (e.g. index 8 for `dairy`, index 10 for `pharmaceutical`).
   - Verified sparse metrics safely default to `0.0` without raising `TypeError` or `KeyError`.

---

## 3. Caveats

No caveats. All investigated components execute real logic and pass independent verification. No code modifications were performed by the auditor.

---

## 4. Conclusion

**Verdict: CLEAN**

The Milestone 1 work product satisfies all forensic integrity criteria:
1. **Zero Cheating / No Facades**: Zero mocks, zero hardcoded test outputs, zero facade implementations.
2. **Genuine RBAC**: Cryptographic token decoding via `itsdangerous`, active database user lookup, role verification (`g.current_user.role == 'admin'`), and privilege escalation defense on user registration.
3. **Genuine Simulation Validation**: Explicit validation against `Shipment.SIM_MODES` and `MODE_PARAMS` on start and restart, properly raising `SimulationError(..., 400)`.
4. **Genuine ML Feature Extraction**: 12-dimensional float vector generation matching saved model metadata (`metrics.json`), with safe null-to-float coercion.
5. **Clean Verification**: All 80 test cases pass cleanly in independent execution.

---

## 5. Verification Method

To independently verify these audit results, execute:

1. **Test Suite Verification**:
   ```bash
   /Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests
   ```
2. **Feature Extractor Empirical Check**:
   ```bash
   PYTHONPATH=backend /Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/python -c "
   from app.core.features import build_feature_row, FEATURE_NAMES
   row = build_feature_row('dairy', {'avg_temp': 4.5, 'max_temp': 6.2, 'avg_humidity': 65.0, 'temp_exposure_hours': 1.5, 'humidity_exposure_hours': 0.0, 'journey_duration_hours': 12.0, 'violation_count': 2})
   assert len(row) == 12 and all(isinstance(x, float) for x in row)
   sparse = build_feature_row('pharmaceutical', {'avg_temp': None})
   assert len(sparse) == 12 and sparse[0] == 0.0
   print('Verified feature extractor')
   "
   ```
3. **Simulation Mode Validation Check**:
   ```bash
   PYTHONPATH=backend /Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/python -c "
   from app.services.simulation_engine import SimulationError
   err = SimulationError('Invalid simulation mode: BAD', 400)
   assert err.status_code == 400
   print('Verified SimulationError status mapping')
   "
   ```
