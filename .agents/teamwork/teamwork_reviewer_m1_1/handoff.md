# Milestone 1 Review & Adversarial Audit Report

## 1. Observation

- **Target Workspace**: `/Users/porandlarajkumar/Documents/IOT`
- **Environment**: Python 3.11.15, pytest 8.4.2 in `/Users/porandlarajkumar/Documents/IOT/backend/.venv`
- **Verification Command & Execution**:
  Ran:
  ```bash
  /Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests
  ```
  Result:
  ```text
  ============================= test session starts ==============================
  platform darwin -- Python 3.11.15, pytest-8.4.2, pluggy-1.7.0
  rootdir: /Users/porandlarajkumar/Documents/IOT/backend
  configfile: pytest.ini
  collected 75 items

  backend/tests/test_api.py ......                                         [  8%]
  backend/tests/test_auth_rbac.py ......................                   [ 37%]
  backend/tests/test_exposure_ml.py ..............                         [ 56%]
  backend/tests/test_shipments_simulator.py .....................          [ 84%]
  backend/tests/test_whatif_compare_reports.py ............                [100%]

  ============================= 75 passed in 28.55s ==============================
  ```
- **Codebase Observations**:
  1. `backend/app/routes/product_routes.py`:
     - Line 33: `@admin_required` applied on `create_product` (`POST /api/products`).
     - Line 71: `@admin_required` applied on `update_product` (`PUT /api/products/<int:profile_id>`).
  2. `backend/app/routes/shipment_routes.py`:
     - Line 148: `@admin_required` applied on `delete_shipment` (`DELETE /api/shipments/<int:shipment_id>`).
  3. `backend/app/auth.py`:
     - Lines 44-51:
       ```python
       def get_current_user():
           """Retrieve user from Authorization header if present, populating g.current_user."""
           if hasattr(g, "current_user") and g.current_user is not None:
               return g.current_user
           user, _ = _user_from_request()
           if user is not None:
               g.current_user = user
           return user
       ```
  4. `backend/app/routes/auth_routes.py`:
     - Lines 26-29:
       ```python
       if role == "admin":
           requester = get_current_user()
           if not requester or getattr(g.current_user, "role", None) != "admin":
               raise ApiError("Only administrators can register admin accounts.", 403)
       ```
  5. `backend/app/services/simulation_engine.py`:
     - Lines 39-47:
       ```python
       class SimulationError(ValueError):
           """Invalid simulator control request (maps to HTTP 409 or specified status_code)."""

           def __init__(self, message, status_code=None):
               super().__init__(message)
               self.message = message
               if status_code is not None:
                   self.status_code = status_code
               elif "Invalid simulation mode" in message or "mode" in message.lower():
                   self.status_code = 400
               else:
                   self.status_code = 409
               self.code = self.status_code
       ```
     - Lines 242-243 & 248-249:
       Mode validation `if mode not in Shipment.SIM_MODES or mode not in MODE_PARAMS:` is enforced for both fresh starts and restarts.
  6. `backend/app/routes/simulation_routes.py`:
     - Lines 19-21:
       ```python
       @sim_bp.errorhandler(SimulationError)
       def _handle_sim_error(err):
           return jsonify({"error": str(err)}), 409
       ```
  7. `backend/app/core/features.py`:
     - Line 41:
       ```python
       row = [float(stats.get(name) or 0.0) for name in NUMERIC_FEATURES]
       ```
  8. `backend/pytest.ini`:
     - Contains `pythonpath = . app` and `testpaths = tests`.

- **Adversarial Stress Test Output**:
  Constructed scenario in `test_client` with shared/persistent application context:
  ```python
  # Admin authenticates and accesses /api/auth/me
  admin_tok = c.post("/api/auth/login", json={"username": "admin", "password": "Admin@1234"}).get_json()["token"]
  c.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_tok}"})

  # Subsequent unauthenticated call (NO Authorization header) attempts to register an admin account:
  res = c.post("/api/auth/register", json={
      "username": "attacker", "email": "attacker@test.com", "password": "password123", "role": "admin"
  })
  print("Attacker register status:", res.status_code, res.get_json())
  ```
  Result observed:
  ```text
  Attacker register status: 201 {'message': 'Registration successful', 'token': '...', 'user': {'id': 3, 'username': 'attacker', 'role': 'admin', ...}}
  ```
  The unauthenticated attacker was granted `admin` privileges due to `get_current_user()` reading stale `g.current_user`!

---

## 2. Logic Chain

1. **Integrity Audit**:
   - Inspected all modified files in `backend/app/` and test suites in `backend/tests/`.
   - Verified that all 75 tests perform actual computations against models and SQLite schemas.
   - Verified there are NO hardcoded responses, dummy facades, mocked shortcuts, or falsified test outputs. Zero integrity violations detected.

2. **RBAC Controls Evaluation (Products & Shipments)**:
   - In `backend/app/routes/product_routes.py`, `create_product` and `update_product` are guarded by `@admin_required`. An operator attempting these receives HTTP 403. An unauthenticated user receives HTTP 401. An administrator successfully creates and updates products.
   - In `backend/app/routes/shipment_routes.py`, `delete_shipment` is guarded by `@admin_required`. An operator attempting deletion receives HTTP 403. An unauthenticated caller receives HTTP 401. An administrator successfully deletes non-In Transit shipments, with foreign key cascade deletions verified on readings, alerts, predictions, and scenarios.

3. **Feature Extraction Robustness**:
   - In `backend/app/core/features.py:build_feature_row`, replacing `float(stats[name])` with `float(stats.get(name) or 0.0)` safely defaults missing keys, `None`, and `""` to `0.0`.
   - Verified that negative values (e.g. `-20.5` °C in frozen cold chains), string numeric values, and float zeros are preserved and cast accurately.

4. **Simulation Engine Mode Validation**:
   - In `backend/app/services/simulation_engine.py`, `engine.start_journey` now explicitly validates that `mode` exists in both `Shipment.SIM_MODES` and `MODE_PARAMS` before initializing or restarting.
   - Calling `engine.start_journey` with an invalid mode correctly raises `SimulationError("Invalid simulation mode: ...", 400)`.

5. **Adversarial Failure Mode — Privilege Escalation via Context Bleed**:
   - In `backend/app/auth.py:get_current_user()`:
     ```python
     if hasattr(g, "current_user") and g.current_user is not None:
         return g.current_user
     user, _ = _user_from_request()
     if user is not None:
         g.current_user = user
     return user
     ```
   - Step 5a: `g` in Flask is bound to the active application context.
   - Step 5b: In persistent application contexts (such as pytest test client fixtures `with app.app_context(): with app.test_client() as test_client:`, or CLI/worker contexts), `g` is NOT automatically reset between requests unless the context is explicitly popped.
   - Step 5c: If an admin performs any authenticated action (e.g., login, `/api/auth/me`), `g.current_user` is set to the admin user.
   - Step 5d: When an unauthenticated request subsequently arrives at `POST /api/auth/register` with `{"role": "admin"}`, `get_current_user()` checks `if hasattr(g, "current_user") and g.current_user is not None:`. Because `g.current_user` was set during the previous action, `get_current_user()` returns the admin user without checking `request.headers`.
   - Step 5e: `auth_routes.py:register` checks `if not requester or getattr(g.current_user, "role", None) != "admin":`. Since `requester` is the cached admin, the check passes, and the anonymous caller is granted an administrator account (HTTP 201).
   - Step 5f: Conversely, if an operator token was cached on `g`, and a legitimate admin sends an admin registration with `Authorization: Bearer <admin_token>`, `get_current_user()` returns the cached operator and rejects the admin with 403.
   - Step 5g: Removing `if hasattr(g, "current_user") and g.current_user is not None:` and directly evaluating `user, _ = _user_from_request(); g.current_user = user; return user` ensures that every request is independently validated against its own `Authorization` header, completely eliminating the vulnerability.

6. **Simulation Route Error Handler Inconsistency**:
   - In `backend/app/routes/simulation_routes.py:19-21`:
     `_handle_sim_error` returns `jsonify({"error": str(err)}), 409`, ignoring `err.status_code`.
   - While `parse_choice` protects the HTTP boundary for `/api/simulation/start/<id>`, `SimulationError` was explicitly updated with a `status_code` attribute. Disregarding `err.status_code` in the error handler creates an inconsistency where internal simulation errors cannot signal 400 or other mapped status codes.

---

## 3. Caveats

- In a standard WSGI server (e.g., Gunicorn with single-request context lifecycle), `g` is refreshed on each request when the WSGI request context pops. However, in test suites, persistent connection contexts, and long-lived session contexts, the context bleed in `get_current_user()` causes silent privilege escalation and credential confusion.
- Code changes in Milestone 1 are well-structured and 100% compliant with write boundaries; addressing the two findings requires only targeted modifications to `backend/app/auth.py` and `backend/app/routes/simulation_routes.py`.

---

## 4. Conclusion & Findings

### Verdict: **REQUEST_CHANGES**

### Findings Summary

| ID | Severity | File | Description | Action Required |
|---|---|---|---|---|
| **F-01** | **Major** | `backend/app/auth.py:44-51` | Privilege Escalation / Credential Bleed in `get_current_user()`: Unconditional check of `hasattr(g, "current_user")` returns cached credentials from previous requests, allowing unauthenticated caller to register `admin` account if admin was previously in context. | Update `get_current_user()` to always call `_user_from_request()` and update `g.current_user = user`. |
| **F-02** | **Minor** | `backend/app/routes/simulation_routes.py:19-21` | Disregarded `SimulationError.status_code`: `@sim_bp.errorhandler(SimulationError)` statically returns `409` instead of `getattr(err, "status_code", 409)`. | Change return status in `_handle_sim_error` to `getattr(err, "status_code", 409)`. |

### Verified Claims
- `pytest backend/tests` discovery without manual PYTHONPATH: **PASS** (via `backend/pytest.ini`).
- Product endpoints (`POST /api/products`, `PUT /api/products/<id>`) require admin role: **PASS** (HTTP 403 for operators).
- Shipment delete endpoint (`DELETE /api/shipments/<id>`) requires admin role: **PASS** (HTTP 403 for operators).
- Simulator mode validation on restart: **PASS** (Invalid mode raises `SimulationError`).
- Null/missing values in feature extraction: **PASS** (Safe default to `0.0`).
- Model inference & Saabas tree contributions: **PASS** (75/75 tests pass).

---

## 5. Verification Method

1. **Automated Test Verification**:
   Execute from workspace root:
   ```bash
   /Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests
   ```
   Expected: All 75 tests collect and pass.

2. **Privilege Escalation Regression Test**:
   Execute the following reproduction command to verify that `get_current_user()` does not leak across requests in a test application context:
   ```bash
   PYTHONPATH=backend backend/.venv/bin/python -c '
   from app import create_app
   from app.config import TestConfig
   from app.extensions import db
   from app.services.seed import seed_database

   app = create_app(config_class=TestConfig, start_engine=False)
   with app.app_context():
       db.create_all()
       seed_database()
       with app.test_client() as c:
           # Admin logs in
           admin_tok = c.post("/api/auth/login", json={"username": "admin", "password": "Admin@1234"}).get_json()["token"]
           c.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_tok}"})

           # Anonymous attacker attempts to register admin (must return 403)
           res = c.post("/api/auth/register", json={
               "username": "attacker", "email": "attacker@test.com", "password": "password123", "role": "admin"
           })
           assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}: {res.get_json()}"
           print("PASSED: Anonymous privilege escalation successfully blocked.")
   '
   ```
   **Invalidation Condition**: If `res.status_code == 201`, the vulnerability persists.
