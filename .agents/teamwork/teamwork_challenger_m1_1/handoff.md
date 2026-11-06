# Milestone 1 Empirical Challenge Report

**Verdict**: **REQUEST_CHANGES**

## 1. Observation
- Target environment: macOS, Python 3.11.15 with pytest 8.4.2 in `/Users/porandlarajkumar/Documents/IOT/backend/.venv`.
- Empirical test suite written: `/Users/porandlarajkumar/Documents/IOT/backend/tests/test_milestone1_challenge.py` containing 20 stress and boundary tests covering all 4 empirical challenge criteria.
- Execution command:
  ```bash
  /Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests/test_milestone1_challenge.py -v
  ```
- Summary of results across the 4 challenges:
  1. **Challenge 1 (Invalid Simulator Mode Injection & Crash Resistance)**: **PASSED (11/11 tests pass)**
     - Direct calls to `engine.start_journey(shipment, mode=invalid_mode)` with `"HACKED"`, `None`, `""`, `"normal"`, `"critical"`, `12345`, `"DROP TABLE"` raised `SimulationError` with `status_code == 400` and `"Invalid simulation mode"`.
     - HTTP API calls `POST /api/simulation/start/<id>` with `{"mode": "HACKED"}`, `{"mode": "normal"}`, etc. returned HTTP 400 with `{"error": "mode must be one of: NORMAL, WARNING, CRITICAL."}`.
     - Shipment status remained unchanged ("Stopped"), simulation state was not mutated, engine tick `engine._tick()` executed without crashing, and subsequent valid restart (`mode="WARNING"`) completed successfully.
  2. **Challenge 2 (RBAC Enforcement on Products and Shipments)**: **PASSED (2/2 comprehensive matrix tests pass)**
     - `POST /api/products`: Operator token returned HTTP 403 (`{"error": "Administrator role required."}`), corrupted token returned HTTP 401 (`{"error": "Invalid authentication token."}`), no token returned HTTP 401 (`{"error": "Authentication required."}`), expired token returned HTTP 401 (`{"error": "Session expired. Please log in again."}`). Product was not inserted into database.
     - `DELETE /api/shipments/<id>`: Operator token returned HTTP 403, corrupted token returned HTTP 401, no token returned HTTP 401, expired token returned HTTP 401. Shipment was not deleted from database.
  3. **Challenge 3 (Admin Registration Authorization & Privilege Escalation)**: **FAILED (2 tests failed, exposing a CRITICAL security vulnerability)**
     - Failure 1 (`test_challenge3_privilege_escalation_via_g_pollution`):
       ```text
       FAILED backend/tests/test_milestone1_challenge.py::test_challenge3_privilege_escalation_via_g_pollution - AssertionError: CRITICAL VULNERABILITY: Anonymous attacker registered admin with status 201: {'message': 'Registration successful', 'token': '...', 'user': {'id': 3, 'username': 'escalated_hacker_admin', 'email': 'hacker@evil.local', 'full_name': 'Escalated_hacker_admin', 'role': 'admin', 'is_active': True, ...}}
       assert 201 == 403
       ```
     - Failure 2 (`test_challenge3_register_admin_matrix`):
       ```text
       res_admin = client.post(url, headers={"Authorization": f"Bearer {admin_token}"}, json={"username": "legit_new_admin", "role": "admin", ...})
       assert res_admin.status_code == 201
       AssertionError: assert 403 == 201
       ```
  4. **Challenge 4 (Feature Row Extraction Boundary Edge Cases)**: **PASSED (4/4 tests pass)**
     - All `None` dictionary (`{k: None for k in NUMERIC_FEATURES}`) returned 13-length float vector with 7 numeric features defaulting to `0.0` and correct one-hot category encoding.
     - Empty dictionary `{}` returned all `0.0` for numeric features.
     - Partial dictionary with missing keys and mixed types (string-encoded floats `"45.2"`, integer `12`) converted cleanly to floats without errors.
     - Invalid category string raised `ValueError: Unknown product category`.
- Baseline suite observation:
  Running the full pre-existing suite (`pytest backend/tests`) revealed that `test_scenario_5_fleet_wide_cross_category_benchmarking` in `backend/tests/test_e2e_scenarios.py:517` fails with `AssertionError: assert 'environmental' in ...` on `/api/dashboard/stats`, which belongs to subsequent dashboard/KPI milestones.

## 2. Logic Chain
1. In `backend/app/auth.py` lines 44-52:
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
2. In `backend/app/routes/auth_routes.py` lines 26-30:
   ```python
   if role == "admin":
       requester = get_current_user()
       if not requester or getattr(g.current_user, "role", None) != "admin":
           raise ApiError("Only administrators can register admin accounts.", 403)
   ```
3. Because `/api/auth/register` is an open endpoint without `@login_required`, `g.current_user` is not initialized or cleared by a decorator before handler execution.
4. If any prior request set `g.current_user` in the application context (for example, an admin checking `/api/auth/me` or performing administrative tasks), `get_current_user()` returns the cached `g.current_user` without inspecting `request.headers.get("Authorization")`.
5. Consequently, an unauthenticated attacker sending `POST /api/auth/register` with `{"role": "admin"}` and no credentials bypasses the check (`requester.role == 'admin'` succeeds), successfully obtaining an admin account (HTTP 201).
6. Conversely, if an operator request is processed before an admin registration request, `g.current_user` retains the operator object, causing a legitimate admin with an `Authorization: Bearer <admin_token>` header to be rejected with HTTP 403.
7. To resolve this vulnerability, `get_current_user()` must not trust `hasattr(g, "current_user")` across requests; it must always parse the current request's `Authorization` header via `_user_from_request()`.

## 3. Caveats
- The simulator tick method `SimulationEngine._tick()` references `self.app.config`. In unit/integration tests initialized with `start_engine=False`, calling `engine._tick()` directly requires assigning `engine.app = app` or having `_tick()` fall back to `current_app.config` if `self.app is None`. In production (`start_engine=True`), `engine.start(app)` assigns `self.app = app`.
- `test_e2e_scenarios.py:test_scenario_5_fleet_wide_cross_category_benchmarking` failure relates to dashboard metrics (`environmental` key in `/api/dashboard/stats`), which is part of Milestone 2 / Dashboard scope and not Milestone 1 Core.

## 4. Conclusion
Milestone 1 is **NOT APPROVED** (**REQUEST_CHANGES**).

While Challenges 1, 2, and 4 pass empirical testing with high quality, Challenge 3 uncovered a **CRITICAL security vulnerability**:
- Unauthenticated privilege escalation on `POST /api/auth/register` due to `get_current_user()` caching `g.current_user`.
- Authorization lockout of legitimate administrators when registering new admin accounts after an operator request.

### Actionable Remediation Required:
In `backend/app/auth.py`, update `get_current_user()` to always evaluate credentials from the incoming request:
```python
def get_current_user():
    """Retrieve user from Authorization header for the current request."""
    user, _ = _user_from_request()
    g.current_user = user
    return user
```

## 5. Verification Method
Run the empirical challenge test suite from the repository root:
```bash
/Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests/test_milestone1_challenge.py -v
```

### Invalidation Conditions:
- The challenge verdict remains `REQUEST_CHANGES` until both `test_challenge3_privilege_escalation_via_g_pollution` and `test_challenge3_register_admin_matrix` pass with HTTP 403 returned to anonymous attackers and HTTP 201 returned to authenticated admins.
