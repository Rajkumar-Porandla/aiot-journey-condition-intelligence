# Empirical Challenger Report (Milestone 1) — Challenger 2

**Verdict**: `REQUEST_CHANGES`

---

## 1. Observation

### Observation 1.1: Direct Pytest Suite Execution
Command executed from workspace root:
```bash
/Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests
```
Result: Exited with code 1.
```text
=================== 6 failed, 97 passed, 8 errors in 38.68s ====================
FAILED backend/tests/test_exposure_ml.py::test_exposure_tracker_incremental_events
FAILED backend/tests/test_milestone1_challenge.py::test_challenge1_api_restart_invalid_mode_returns_400[HACKED]
FAILED backend/tests/test_milestone1_challenge.py::test_challenge1_api_restart_invalid_mode_returns_400[normal]
FAILED backend/tests/test_milestone1_challenge.py::test_challenge1_api_restart_invalid_mode_returns_400[WARNING_UPPER]
FAILED backend/tests/test_milestone1_challenge.py::test_challenge1_api_restart_invalid_mode_returns_400[invalid]
FAILED backend/tests/test_milestone1_challenge.py::test_challenge3_register_admin_matrix
ERROR backend/tests/test_milestone1_challenge.py::test_challenge1_direct_engine_restart_invalid_modes[HACKED]
ERROR backend/tests/test_milestone1_challenge.py::test_challenge1_direct_engine_restart_invalid_modes[None]
ERROR backend/tests/test_milestone1_challenge.py::test_challenge1_direct_engine_restart_invalid_modes[]
ERROR backend/tests/test_milestone1_challenge.py::test_challenge1_direct_engine_restart_invalid_modes[normal]
ERROR backend/tests/test_milestone1_challenge.py::test_challenge1_direct_engine_restart_invalid_modes[critical]
ERROR backend/tests/test_milestone1_challenge.py::test_challenge1_direct_engine_restart_invalid_modes[12345]
ERROR backend/tests/test_milestone1_challenge.py::test_challenge1_direct_engine_restart_invalid_modes[DROP TABLE]
ERROR backend/tests/test_milestone1_challenge.py::test_challenge1_valid_restart_after_invalid_attempts
```

### Observation 1.2: Critical Security Vulnerability in `get_current_user()` (`backend/app/auth.py:44-51`)
Code in `backend/app/auth.py`:
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
Empirical reproduction script executed:
```python
with app.test_request_context(headers={"Authorization": f"Bearer {operator_token}"}):
    u1 = get_current_user()  # returns operator

# Subsequent request without Authorization headers (Anonymous user):
with app.test_request_context():
    u2 = get_current_user()
```
Output:
```text
Request 1 with Operator token: user=operator, role=operator
Request 2 ANONYMOUS (no headers): user=operator
CRITICAL SECURITY VULNERABILITY: Anonymous request hijacked prior session user from g!
```
When an anonymous user or a different user sends a request in an environment where application context persists, `get_current_user()` returns the cached `g.current_user` without checking `request.headers.get("Authorization")`.

### Observation 1.3: Boundary Stress Testing on `build_feature_row` (`backend/app/core/features.py:37-43`)
Code in `backend/app/core/features.py`:
```python
def build_feature_row(category: str, stats: dict) -> list:
    """Return the model input vector (ordered as FEATURE_NAMES)."""
    if category not in CATEGORY_KEYS:
        raise ValueError(f"Unknown product category: {category}")
    row = [float(stats.get(name) or 0.0) for name in NUMERIC_FEATURES]
    row += [1.0 if c == category else 0.0 for c in CATEGORY_KEYS]
    return row
```
Empirical boundary test results:
- Missing keys, `None` values, `{}`: Cleanly defaults to `0.0`.
- Negative numbers (e.g. `avg_temp = -25.0`): Preserved as `-25.0`.
- Subnormal numbers (`1e-308`), integers, booleans: Converted cleanly.
- `NaN` (`float('nan')`): Returns `[nan, ...]`. Downstream Random Forest inference in `predict_from_stats` executes without crashing (`risk_class="Medium Risk"`, score `1.37`).
- `Infinity` (`float('inf')`, `float('-inf')`): Returns `[inf, ...]`. When passed downstream to `predict_from_stats`, scikit-learn raises:
  `ValueError: Input X contains infinity or a value too large for dtype('float32')`.
- Invalid category strings: Cleanly raises `ValueError: Unknown product category: ...`.
- REST API layer protection: `backend/app/utils.py:parse_float` line 56 explicitly rejects `NaN` and `+/-inf` with HTTP 400 (`"must be a finite number"`).

### Observation 1.4: Concurrency Stress Testing
Tested via multi-threaded concurrent execution against Flask application and SQLite DB:
1. **Simultaneous Start on Same Shipment** (10 threads):
   - Result: Exactly 1 start succeeded (`In Transit`).
   - 9 threads cleanly caught `SimulationError` (`409 Conflict`), guarded by `engine.lock` and `db.session.refresh(shipment)`.
   - Zero database corruption, zero deadlocks.
2. **Simultaneous Stop on Running Shipment** (10 threads):
   - Result: Exactly 1 stop succeeded (`Stopped`).
   - 9 threads cleanly rejected with `SimulationError`.
3. **High-Contention Interleaved Race** (20 threads concurrently spamming Start/Stop):
   - Result: Handled cleanly under `engine.lock`. Zero uncaught exceptions. Final status settled deterministically in `"Stopped"` or `"In Transit"`.
4. **Concurrent Product Modifications** (10 threads concurrently updating product thresholds via `PUT /api/products/<id>`):
   - Result: All 10 succeeded with HTTP 200 without SQLite locking errors.
5. **Concurrent Stepping Caveat**:
   - Calling `step_shipment` concurrently across threads without passing through `engine.lock` or without calling `db.session.refresh(shipment)` causes duplicate sequence numbers (`sqlite3.IntegrityError: UNIQUE constraint failed: sensor_readings.shipment_id, sensor_readings.sequence`). In production, this is mitigated because `engine._tick()` is the single-threaded background driver.

---

## 2. Logic Chain

1. **Test Suite Failure**:
   - Running `/Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests` fails with 6 failures and 8 errors (Observation 1.1).
   - This directly invalidates the requirement that the entire test suite must pass cleanly without manual intervention.

2. **Session Hijacking / Privilege Escalation Root Cause**:
   - In `backend/app/routes/auth_routes.py:27`, the registration route checks:
     ```python
     if role == "admin":
         requester = get_current_user()
         if not requester or getattr(g.current_user, "role", None) != "admin":
             raise ApiError("Only administrators can register admin accounts.", 403)
     ```
   - In `backend/app/auth.py:46`, `get_current_user()` checks `if hasattr(g, "current_user") and g.current_user is not None: return g.current_user`.
   - When multiple requests are processed in an environment where application context persists (such as test suites or persistent workers), `get_current_user()` returns the user from a previous request without checking `request.headers.get("Authorization")` (Observation 1.2).
   - This leads to two critical flaws:
     - A legitimate admin request is evaluated as the prior operator user (failing with 403 Forbidden).
     - An unauthenticated anonymous request can inherit an admin `g.current_user` and register new admin accounts.
   - **Remediation**: `get_current_user()` must always invoke `_user_from_request()` to read the request's `Authorization` header directly:
     ```python
     def get_current_user():
         user, _ = _user_from_request()
         g.current_user = user
         return user
     ```

3. **Broken Test Fixtures in `backend/tests/test_milestone1_challenge.py`**:
   - `stopped_shipment` fixture queries `ProductProfile.query` without taking `app` as a dependency, raising `RuntimeError: Working outside of application context` on 7 tests.
   - Tests calling `engine._tick()` fail with `AttributeError: 'NoneType' object has no attribute 'config'` because `engine.app` was never initialized (`start_engine=False`).

4. **Boundary and Concurrency Soundness**:
   - Concurrency locking in `SimulationEngine` (`self.lock` + `db.session.refresh`) was empirically proven to be robust against multi-threaded race conditions (Observation 1.4).
   - `build_feature_row` cleanly handles nulls, missing keys, and negative numbers. Infinite inputs are trapped by `parse_float` at the REST layer, though a check in `build_feature_row` or `predict_from_stats` would provide defense-in-depth against direct Python calls.

---

## 3. Caveats

- Tests were run against SQLite in WAL mode with accelerated simulation timings. High-concurrency performance under multi-process WSGI deployments (e.g. multiple Gunicorn worker processes) relies on SQLite WAL concurrency and file locking.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

Before Milestone 1 can be approved, the following two issues must be resolved:
1. **Fix `get_current_user()` in `backend/app/auth.py`**: Always parse the current request header via `_user_from_request()`; never return a cached `g.current_user` without verifying the request header.
2. **Fix Test Suite in `backend/tests/`**: Fix the `stopped_shipment` fixture in `test_milestone1_challenge.py` to depend on `app` context, guard `engine._tick()` against `None` app, and ensure all tests in `backend/tests` pass with zero failures and zero errors.

---

## 5. Verification Method

1. Run the full backend pytest test suite:
   ```bash
   /Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests
   ```
   **Pass Condition**: 100% passed (0 failed, 0 errors).

2. Verify session isolation in `get_current_user()`:
   ```bash
   PYTHONPATH=backend /Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/python -c "
   from app import create_app
   from app.config import TestConfig
   from app.auth import get_current_user, issue_token
   from app.models import User
   from app.extensions import db
   from app.services.seed import seed_database

   app = create_app(TestConfig, start_engine=False)
   with app.app_context():
       db.create_all()
       seed_database()
       op = User.query.filter_by(username='operator').first()
       token = issue_token(op)
       with app.test_request_context(headers={'Authorization': f'Bearer {token}'}):
           assert get_current_user().username == 'operator'
       with app.test_request_context():
           assert get_current_user() is None, 'Security flaw: Anonymous request inherited operator session!'
       print('VERIFIED: get_current_user session isolation confirmed!')
   "
   ```
   **Pass Condition**: Prints `VERIFIED: get_current_user session isolation confirmed!` without assertion error.
