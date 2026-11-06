# Milestone 1 Independent Review & Adversarial Challenge Report

## 1. Observation

### Target Environment & Execution
- **Repository root**: `/Users/porandlarajkumar/Documents/IOT`
- **Virtual environment**: `/Users/porandlarajkumar/Documents/IOT/backend/.venv` (Python 3.11.15, pytest 8.4.2)
- **Direct Pytest Verification Command**:
  ```bash
  /Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests
  ```
- **Observed Pytest Result Across Full Test Suite**:
  ```text
  ============================= test session starts ==============================
  platform darwin -- Python 3.11.15, pytest-8.4.2, pluggy-1.7.0
  rootdir: /Users/porandlarajkumar/Documents/IOT/backend
  configfile: pytest.ini
  collecting ... collected 92 items

  backend/tests/test_auth_rbac.py ......................                   [ 23%]
  backend/tests/test_shipments_simulator.py ........................       [ 50%]
  backend/tests/test_api.py ......                                         [ 56%]
  backend/tests/test_exposure_ml.py ..............F..                      [ 75%]
  backend/tests/test_whatif_compare_reports.py .................           [ 93%]
  backend/tests/test_e2e_scenarios.py ......                               [100%]

  =================================== FAILURES ===================================
  ___________________ test_exposure_tracker_incremental_events ___________________

      def test_exposure_tracker_incremental_events():
          from app.core.exposure import ExposureTracker
          profile = {"min_temp": 2.0, "max_temp": 8.0, "min_humidity": 40.0, "max_humidity": 65.0, "sensitivity": "Very High"}
          tracker = ExposureTracker(profile, {})
          t0 = utcnow()
          r1 = {"temperature": 11.0, "humidity": 50.0, "timestamp": t0.isoformat()}
  >       events_1 = tracker.process(r1, step_minutes=15.0)
  E       TypeError: ExposureTracker.process() got an unexpected keyword argument 'step_minutes'

  backend/tests/test_exposure_ml.py:444: TypeError
  ======================== 1 failed, 91 passed in 35.72s =========================
  ```

### Codebase Observations

1. **`backend/app/auth.py` (lines 44-51)**:
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
2. **`backend/app/routes/auth_routes.py` (lines 26-29)**:
   ```python
   if role == "admin":
       requester = get_current_user()
       if not requester or getattr(g.current_user, "role", None) != "admin":
           raise ApiError("Only administrators can register admin accounts.", 403)
   ```
3. **`backend/app/routes/product_routes.py` (lines 32-34, 70-72)**:
   - Decorated `create_product` (`POST /api/products`) with `@admin_required`.
   - Decorated `update_product` (`PUT /api/products/<int:profile_id>`) with `@admin_required`.
4. **`backend/app/routes/shipment_routes.py` (lines 147-149)**:
   - Decorated `delete_shipment` (`DELETE /api/shipments/<int:shipment_id>`) with `@admin_required`.
5. **`backend/app/services/simulation_engine.py` (lines 235-254)**:
   ```python
   if mode not in Shipment.SIM_MODES or mode not in MODE_PARAMS:
       raise SimulationError(f"Invalid simulation mode: {mode}", 400)
   profile = shipment.product_profile.thresholds()
   if shipment.sim_state is None:
       state = {"sensor": sensor_model.initial_state(profile, mode, random.Random(), intensity), "exposure": {}}
       shipment.sim_started_at = utcnow()
   else:  # restart a stopped journey from where it halted, possibly with a new mode
       if mode not in Shipment.SIM_MODES or mode not in MODE_PARAMS:
           raise SimulationError(f"Invalid simulation mode: {mode}", 400)
       state = copy.deepcopy(shipment.sim_state)
       state["sensor"]["mode"] = mode
       state["sensor"]["intensity"] = float(intensity)
   ```
6. **`backend/app/core/features.py` (lines 37-43)**:
   ```python
   def build_feature_row(category: str, stats: dict) -> list:
       """Return the model input vector (ordered as FEATURE_NAMES)."""
       if category not in CATEGORY_KEYS:
           raise ValueError(f"Unknown product category: {category}")
       row = [float(stats.get(name) or 0.0) for name in NUMERIC_FEATURES]
       row += [1.0 if c == category else 0.0 for c in CATEGORY_KEYS]
       return row
   ```

---

## 2. Logic Chain

### Step 1: Privilege Escalation Attack & Cross-Request Context Bleed
- In `backend/app/auth.py:get_current_user`:
  The function first checks `if hasattr(g, "current_user") and g.current_user is not None: return g.current_user`.
- In scenarios where an application context encompasses consecutive requests (common during test client sessions, persistent connection handlers, or pooled thread contexts):
  - Scenario A (Privilege Escalation):
    An admin user makes a request (e.g. `GET /api/auth/me`), populating `g.current_user` with `<User 1>` (`role='admin'`). Subsequently, an untrusted operator or unauthenticated caller submits `POST /api/auth/register` with `role="admin"` and their own credentials or no token. Because `g.current_user` is already populated and not cleared, `get_current_user()` returns the cached admin user object.
    The check in `auth_routes.py`:
    `if not requester or getattr(g.current_user, "role", None) != "admin":` evaluates to `False`.
    **Empirical Reproduction**:
    ```python
    client.get('/api/auth/me', headers={'Authorization': f'Bearer {admin_token}'})
    res_hack = client.post(
        '/api/auth/register',
        headers={'Authorization': f'Bearer {operator_token}'},
        json={'username': 'hacked_admin', 'email': 'hacked@test.local', 'password': 'Password123', 'role': 'admin'}
    )
    assert res_hack.status_code == 201  # SUCCEEDED: New admin created by operator!
    ```
  - Scenario B (False Denial of Service for Legitimate Admin):
    An operator makes a request first (`g.current_user` is `<User 2>`, `role='operator'`). A legitimate admin subsequently sends `POST /api/auth/register` with `Authorization: Bearer <admin_token>`. `get_current_user()` ignores the admin's bearer token, returns the operator from `g.current_user`, and rejects the legitimate admin with `HTTP 403 Forbidden`.
- **Root Cause**: `get_current_user()` must never trust a stale `g.current_user` without validating it against the current request's incoming `Authorization` header. It should parse `_user_from_request()` for every request and set `g.current_user = user`.

### Step 2: RBAC Enforcement Verification
- Direct testing confirmed that:
  - `POST /api/products` returns 403 for operator tokens and 401 without tokens.
  - `PUT /api/products/<id>` returns 403 for operator tokens and 401 without tokens.
  - `DELETE /api/shipments/<id>` returns 403 for operator tokens and 401 without tokens.
  - Admin tokens are properly authorized for all three actions.
  - In-transit shipments cannot be deleted even by an admin (returns 400).
  - RBAC endpoint decorators are properly wired and functionally correct.

### Step 3: Simulator Restart Mode Validation
- Direct testing confirmed that:
  - Starting or restarting a journey with `mode` not in `Shipment.SIM_MODES` (`NORMAL`, `WARNING`, `CRITICAL`) raises `SimulationError(..., 400)`.
  - HTTP API endpoint `POST /api/simulation/start/<id>` parses mode and validates choice, returning HTTP 400 when invalid modes are supplied.
  - Tested directly against `"INVALID"`, `"HACKED"`, `None`, `""`, `"normal"` (case sensitivity verified).

### Step 4: Null Handling in `features.py`
- Direct testing confirmed that:
  - `build_feature_row` handles empty dictionaries (`{}`), dictionaries with all `None` values, and missing keys cleanly by defaulting to `0.0`.
  - Float conversion operates as expected on numeric values and strings convertible to float.
  - Raises `ValueError` cleanly on unknown category strings.

### Step 5: Test Suite Health
- Running the full pytest command `/Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests` fails due to `backend/tests/test_exposure_ml.py:444` (`TypeError: ExposureTracker.process() got an unexpected keyword argument 'step_minutes'`).
- The 3 test files cited by the worker (`test_api.py`, `test_auth_rbac.py`, `test_shipments_simulator.py`) pass 52/52 tests, but the wider suite in `backend/tests/` contains broken tests that must be remediated.

---

## 3. Caveats
- The context bleed vulnerability in `get_current_user()` manifests when request contexts are reused or when `g` is not unmounted between sequential requests. In a standard WSGI/ASGI per-request worker process with clean teardown, `g` is torn down after each HTTP request; however, in test clients, long-lived thread-local contexts, or middleware configurations that do not tear down the app context, this represents a severe privilege escalation vector.
- No other security regressions or integrity violations were observed.

---

## 4. Conclusion & Findings

### Verdict: REQUEST_CHANGES

### Findings

#### [Critical] Finding 1 — Security / Privilege Escalation via Context Bleed in `get_current_user()`
- **Where**: `backend/app/auth.py`, lines 44-51
- **Why**: Stale `g.current_user` is returned without inspecting the incoming request's `Authorization` header. This allows operators to register admin accounts if an admin previously issued a request in the same context, and falsely blocks admins from registering accounts if an operator previously issued a request.
- **Remediation**:
  Replace lines 44-51 in `backend/app/auth.py` with:
  ```python
  def get_current_user():
      """Retrieve user from Authorization header for the current request."""
      user, _ = _user_from_request()
      g.current_user = user
      return user
  ```

#### [Major] Finding 2 — Full Pytest Suite Failure (`TypeError` in `test_exposure_ml.py`)
- **Where**: `backend/tests/test_exposure_ml.py`, line 444
- **Why**: `ExposureTracker.process()` signature is `def process(self, reading: dict, dt_minutes: float) -> list:`. The test suite calls `tracker.process(r1, step_minutes=15.0)` instead of `dt_minutes=15.0` (or positional `15.0`).
- **Remediation**: Update `test_exposure_ml.py` line 444 to use `dt_minutes=15.0` or positional parameter `15.0`.

---

## 5. Verification Method

To independently verify the findings:

1. **Verify Full Pytest Suite Failure**:
   ```bash
   /Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests
   ```
   *Expected outcome*: Exits with code 1, reporting failure in `test_exposure_ml.py:444`.

2. **Verify Privilege Escalation PoC**:
   ```bash
   PYTHONPATH=backend /Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/python -c "
   from app import create_app
   from app.config import TestConfig
   from app.extensions import db
   from app.services.seed import seed_database
   from flask import g

   app = create_app(config_class=TestConfig, start_engine=False)
   with app.app_context():
       db.create_all()
       seed_database()
       client = app.test_client()
       admin_token = client.post('/api/auth/login', json={'username': 'admin', 'password': 'Admin@1234'}).get_json()['token']
       operator_token = client.post('/api/auth/login', json={'username': 'operator', 'password': 'Operator@1234'}).get_json()['token']

       with client:
           client.get('/api/auth/me', headers={'Authorization': f'Bearer {admin_token}'})
           res = client.post('/api/auth/register', headers={'Authorization': f'Bearer {operator_token}'}, json={'username': 'hacked_admin', 'email': 'hacked@test.local', 'password': 'Password123', 'role': 'admin'})
           print('Exploit Status Code:', res.status_code)
           assert res.status_code == 201, 'Failed to reproduce exploit'
           print('VULNERABILITY CONFIRMED: Operator created admin account!')
   "
   ```
