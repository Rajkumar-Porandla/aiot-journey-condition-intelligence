# E2E Test Infra: AIoT-Based Product Journey Condition Intelligence

## Test Philosophy
- Opaque-box, requirement-driven, and rigorous whitebox verification.
- Verification methodology: Category-Partition, Boundary Value Analysis (BVA), Pairwise Combinatorial Testing, and Realistic Cold-Chain Real-World Workload Testing.
- Zero tolerance for simulated facades or hardcoded values.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 |
|---|---------|---------------------|:------:|:------:|:------:|
| 1 | User Auth & Session Lifecycle | ORIGINAL_REQUEST §M1 | 5 | 5 | ✓ |
| 2 | RBAC Security Controls | ORIGINAL_REQUEST §M1 | 5 | 5 | ✓ |
| 3 | Executive Dashboard KPIs & Observability | ORIGINAL_REQUEST §M1 | 5 | 5 | ✓ |
| 4 | Shipment Management CRUD | ORIGINAL_REQUEST §M2 | 5 | 5 | ✓ |
| 5 | Journey State Transitions & Lifecycle | ORIGINAL_REQUEST §M2 | 5 | 5 | ✓ |
| 6 | IoT Sensor Simulation Modes & Progression | ORIGINAL_REQUEST §M3 | 5 | 5 | ✓ |
| 7 | Simulator Boundary & Anomaly Safeguards | ORIGINAL_REQUEST §M3 | 5 | 5 | ✓ |
| 8 | Harmful Exposure & Alert Severity Engine | ORIGINAL_REQUEST §M4 | 5 | 5 | ✓ |
| 9 | Random Forest Quality Risk Prediction | ORIGINAL_REQUEST §M5 | 5 | 5 | ✓ |
| 10 | Saabas Tree Path Attribution & Explainability | ORIGINAL_REQUEST §M6 | 5 | 5 | ✓ |
| 11 | What-If Journey Simulator Counterfactuals | ORIGINAL_REQUEST §M7 | 5 | 5 | ✓ |
| 12 | Multi-Shipment Risk Comparison & Safest Journey | ORIGINAL_REQUEST §M8 | 5 | 5 | ✓ |
| 13 | Journey Condition PDF Audit Report Generation | ORIGINAL_REQUEST §M9 | 5 | 5 | ✓ |

## Test Architecture
- **Backend Test Runner**: Pytest with `TestConfig` and in-memory/disk SQLite, coverage reporting, running via `pytest backend/tests`.
- **E2E & Whitebox Test Suites**:
  - `backend/tests/test_api.py`: Baseline smoke tests
  - `backend/tests/test_auth_rbac.py`: Tier 1 & 2 Auth, RBAC, session lifecycle, token invalidation
  - `backend/tests/test_shipments_simulator.py`: Tier 1, 2, 3 Shipment CRUD, state machine transitions, sensor model edge cases
  - `backend/tests/test_exposure_ml.py`: Tier 1, 2, 3 Exposure detection, severity formulas, ML prediction fidelity, Saabas algebraic proofs
  - `backend/tests/test_whatif_compare_reports.py`: Tier 1, 2, 3 What-if counterfactual isolation, risk comparison, ReportLab PDF generation
  - `backend/tests/test_e2e_scenarios.py`: Tier 4 Real-world end-to-end journey workloads (Dairy, Pharma, Frozen, Berries, Flowers)
- **Invocation**:
  ```bash
  cd backend && PYTHONPATH=. .venv/bin/pytest tests -v
  ```
- **Pass/Fail Semantics**: All test suites must pass with exit code 0 and zero failed assertions.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Cold-Chain Dairy Transport under Heat Wave | F1, F4, F5, F6, F8, F9, F10, F13 | High |
| 2 | Ultra-Cold mRNA Vaccine Transit with Sensor Spike | F1, F2, F4, F6, F7, F8, F9, F11, F13 | High |
| 3 | Frozen Seafood Transit with Machine Breakdown & Recovery | F4, F5, F6, F8, F9, F10, F11 | High |
| 4 | Fresh Strawberry Humidity Saturation & Mold Risk | F4, F6, F8, F9, F10, F12, F13 | Medium |
| 5 | Cross-Category Multi-Fleet Risk Benchmarking | F1, F2, F4, F9, F12, F13 | High |

## Coverage Thresholds
- Tier 1 (Feature Coverage): ≥5 tests per feature (≥65 tests)
- Tier 2 (Boundary & Corner Cases): ≥5 tests per feature (≥65 tests)
- Tier 3 (Cross-Feature Combinations): ≥15 interaction tests
- Tier 4 (Real-World Application Scenarios): ≥5 complete end-to-end workload tests
- **Total Minimum Target: ~150 comprehensive verification tests**
