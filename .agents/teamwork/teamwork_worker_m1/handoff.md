# Milestone 1 Handoff Report — Backend Core & Security Remediation

## 1. Observation
- Target repository: `/Users/porandlarajkumar/Documents/IOT`
- Target environment: Python 3.11.15 with pytest 8.4.2 in `/Users/porandlarajkumar/Documents/IOT/backend/.venv`
- Initial test execution:
  - Running `/Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests` from the root directory failed with `ModuleNotFoundError: No module named 'app'` because pytest discovery lacked `pytest.ini` with `pythonpath = . app`.
- Prior state of RBAC controls:
  - `backend/app/routes/product_routes.py`: `POST /api/products` (lines 32-34) and `PUT /api/products/<int:profile_id>` (lines 70-72) were decorated with `@login_required` instead of `@admin_required`, allowing non-admin operators to create and mutate product profiles.
  - `backend/app/routes/shipment_routes.py`: `DELETE /api/shipments/<int:shipment_id>` (lines 147-149) was decorated with `@login_required` instead of `@admin_required`, allowing non-admin operators to delete shipments.
  - `backend/app/routes/auth_routes.py`: `POST /api/auth/register` accepted arbitrary roles (`"admin"`, `"operator"`) from unauthenticated anonymous callers without privilege escalation validation.
- Prior state of simulator engine:
  - `backend/app/services/simulation_engine.py`: In `start_journey`, restarting a stopped journey (`shipment.sim_state is not None`, lines 234-237) assigned `state["sensor"]["mode"] = mode` directly without validating whether `mode in Shipment.SIM_MODES` and `mode in MODE_PARAMS`.
- Prior state of feature extraction:
  - `backend/app/core/features.py:build_feature_row`: `row = [float(stats[name]) for name in NUMERIC_FEATURES]` crashed with `TypeError` when any metric in `stats` evaluated to `None` or raised `KeyError` if missing.

## 2. Logic Chain
- Step 1 (Pytest Discovery): Created `backend/pytest.ini` containing:
  ```ini
  [pytest]
  pythonpath = . app
  testpaths = tests
  ```
  When executing `/Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests` from the root directory, pytest detects `backend/pytest.ini`, sets root directory to `backend`, and automatically resolves `app` and test suites without requiring manual `PYTHONPATH` exports.
- Step 2 (RBAC Controls on Products & Shipments):
  - In `backend/app/routes/product_routes.py`, applied `@admin_required` to `create_product` (`POST /api/products`) and `update_product` (`PUT /api/products/<id>`).
  - In `backend/app/routes/shipment_routes.py`, imported `admin_required` and applied `@admin_required` to `delete_shipment` (`DELETE /api/shipments/<id>`).
  - `@admin_required` is composed over `@login_required`, checking `g.current_user.role == 'admin'` and returning HTTP 403 `{"error": "Administrator role required."}` if the caller is an operator.
- Step 3 (Privilege Escalation Defense on Registration):
  - In `backend/app/auth.py`, implemented `get_current_user()` and exposed `user_from_request` to populate `g.current_user` from the `Authorization: Bearer <token>` header when present on non-decorator-gated routes.
  - In `backend/app/routes/auth_routes.py:register`, retained default role as `"operator"`. Added validation:
    ```python
    if role == "admin":
        requester = get_current_user()
        if not requester or getattr(g.current_user, "role", None) != "admin":
            raise ApiError("Only administrators can register admin accounts.", 403)
    ```
    This allows public registration for operator accounts while blocking privilege escalation to admin accounts unless requested by an existing authenticated admin.
- Step 4 (Simulator Restart Mode Validation):
  - In `backend/app/services/simulation_engine.py`:
    - Updated `SimulationError` to accept `status_code`, defaulting to `400` when the error message relates to invalid simulation mode and `409` for illegal state machine transitions.
    - Imported `MODE_PARAMS` from `..core.sensor_model`.
    - Added mode validation before both initial start and restart branches:
      ```python
      if mode not in Shipment.SIM_MODES or mode not in MODE_PARAMS:
          raise SimulationError(f"Invalid simulation mode: {mode}", 400)
      ```
- Step 5 (Feature Vector Null Handling):
  - In `backend/app/core/features.py:build_feature_row`, replaced direct dictionary access with:
    ```python
    row = [float(stats.get(name) or 0.0) for name in NUMERIC_FEATURES]
    ```
    This cleanly maps missing keys, `None`, or empty strings to `0.0`, eliminating `TypeError` and `KeyError` crashes.

## 3. Caveats
- No caveats. All changes strictly adhere to write ownership constraints and the existing system design.

## 4. Conclusion
- All 5 items of Milestone 1 have been implemented cleanly and verified genuinely:
  1. RBAC controls enforced on product endpoints and shipment deletion.
  2. Privilege escalation prevented during user registration.
  3. Simulator mode restart injection fixed with HTTP 400 error mapping.
  4. Null/missing values safely handled in feature row generation.
  5. Frictionless pytest execution confirmed with zero manual environment manipulation.

## 5. Verification Method
Execute the following verification command directly from the workspace root:
```bash
/Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests
```

### Verified Test Run Output:
```text
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-8.4.2, pluggy-1.7.0
rootdir: /Users/porandlarajkumar/Documents/IOT/backend
configfile: pytest.ini
collecting ... collected 49 items

backend/tests/test_api.py ......                                         [ 12%]
backend/tests/test_auth_rbac.py ......................                   [ 57%]
backend/tests/test_shipments_simulator.py .....................          [100%]

============================= 49 passed in 19.04s ==============================
```
