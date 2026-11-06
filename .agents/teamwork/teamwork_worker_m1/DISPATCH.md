## 2026-11-06T10:48:53Z
You are teamwork_worker_m1, an implementation worker.
Working directory: /Users/porandlarajkumar/Documents/IOT/.agents/teamwork/teamwork_worker_m1
Original request path: /Users/porandlarajkumar/Documents/IOT/.agents/teamwork/ORIGINAL_REQUEST.md
Scope document: /Users/porandlarajkumar/Documents/IOT/PROJECT.md

MANDATORY FIRST STEP: Read /Users/porandlarajkumar/Documents/IOT/.agents/teamwork/ORIGINAL_REQUEST.md completely.

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write ownership:
You exclusively own and may modify:
- backend/app/auth.py
- backend/app/routes/auth_routes.py
- backend/app/routes/product_routes.py
- backend/app/routes/shipment_routes.py
- backend/app/services/simulation_engine.py
- backend/app/core/features.py
- backend/pytest.ini

Your mission: Implement Milestone 1 (Backend Core & Security Remediation):
1. RBAC Security Controls:
   - Apply `@admin_required` to `POST /api/products` and `PUT /api/products/<id>` in `backend/app/routes/product_routes.py`.
   - Apply `@admin_required` to `DELETE /api/shipments/<id>` in `backend/app/routes/shipment_routes.py`.
   - In `backend/app/routes/auth_routes.py:register`, prevent privilege escalation: default role to "operator". Reject requests to register "admin" unless the requester is an existing authenticated admin (`g.current_user.role == 'admin'`).
2. Simulator Restart Mode Injection Bug:
   - In `backend/app/services/simulation_engine.py:234-237`, when restarting a stopped shipment (`shipment.sim_state is not None`), validate that `mode in Shipment.SIM_MODES` and `mode in MODE_PARAMS`. If invalid, raise `SimulationError(f"Invalid simulation mode: {mode}")` with HTTP 400.
3. Feature Vector Null Handling:
   - In `backend/app/core/features.py:build_feature_row`, protect against `None` values in `stats`: use `float(stats.get(name) or 0.0)` so `None` or missing metrics do not crash with `TypeError`.
4. Pytest Discovery Configuration:
   - Create `backend/pytest.ini` configuring `pythonpath = . app` and `testpaths = tests`.
5. Run tests:
   - Execute `/Users/porandlarajkumar/Documents/IOT/backend/.venv/bin/pytest backend/tests` directly from repository root to confirm all tests pass cleanly without manual PYTHONPATH exports.

Deliver your handoff in /Users/porandlarajkumar/Documents/IOT/.agents/teamwork/teamwork_worker_m1/handoff.md documenting all modified files, exact changes, and test execution output. When done, send a message to your caller.
