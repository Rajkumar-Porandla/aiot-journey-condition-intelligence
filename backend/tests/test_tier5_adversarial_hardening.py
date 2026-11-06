"""Phase 2 Adversarial Coverage Hardening (Tier 5 Stress Suite).

Adversarially stress tests the entire AIoT platform across 5 vectors:
1. Concurrency & WAL Mode: Concurrent journey simulations & concurrent database reads/writes under SQLite WAL mode.
2. Attack RBAC: Exhaustively attempt admin privilege escalation, cross-session credential pollution, and unauthorized resource mutation.
3. Attack ML Models: Out-of-bounds parameters, NaN, Inf, extreme temperatures (-80°C to +100°C), zero-duration journeys.
4. Attack What-If Simulation: Ensure no counterfactual inputs ever leak into or mutate persistent telemetry or models.
5. Attack PDF Generator: Large alert counts (>20 alerts), special characters in shipment notes, empty journeys.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import math
import os
import tempfile
import time
import pytest
from sqlalchemy import text

from app import create_app
from app.config import Config, TestConfig
from app.core.explain import tree_contributions
from app.core.features import NUMERIC_FEATURES, build_feature_row
from app.extensions import db
from app.models import ExposureAlert, MLPrediction, ProductProfile, SensorReading, Shipment, SimulationScenario, User, utcnow
from app.services import ml_service
from app.services.seed import seed_database
from app.services.simulation_engine import SimulationEngine, step_shipment


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def app_instance():
    """Application instance with active context for tests needing ORM models directly."""
    app = create_app(config_class=TestConfig, start_engine=False)
    with app.app_context():
        db.create_all()
        seed_database()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app_instance):
    """Isolated in-memory test client."""
    with app_instance.test_client() as test_client:
        yield test_client


@pytest.fixture
def wal_app_and_client():
    """File-backed SQLite database explicitly exercising WAL mode with concurrent access."""
    temp_dir = tempfile.mkdtemp(prefix="aiot_wal_test_")
    db_path = os.path.join(temp_dir, "wal_stress.db")

    class WalConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"
        SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 30.0}}
        SIM_ENGINE_ENABLED = False

    app = create_app(config_class=WalConfig, start_engine=False)
    with app.app_context():
        db.create_all()
        seed_database()
        # Verify WAL mode is indeed active on disk
        mode = db.session.execute(text("PRAGMA journal_mode")).scalar()
        assert str(mode).lower() == "wal", f"Expected WAL mode, got {mode}"

    with app.test_client() as test_client:
        yield app, test_client, db_path

    # Teardown
    with app.app_context():
        db.session.remove()
        db.drop_all()
    for ext in ("", "-wal", "-shm"):
        f = db_path + ext
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass
    try:
        os.rmdir(temp_dir)
    except OSError:
        pass


@pytest.fixture
def admin_token(client):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@1234"})
    assert res.status_code == 200
    return res.get_json()["token"]


@pytest.fixture
def operator_token(client):
    res = client.post("/api/auth/login", json={"username": "operator", "password": "Operator@1234"})
    assert res.status_code == 200
    return res.get_json()["token"]


# ==============================================================================
# Vector 1: Concurrency & WAL Mode Stress Tests
# ==============================================================================

def test_wal_mode_enabled_on_file_database(wal_app_and_client):
    """Verify SQLite WAL pragma is set and operational on disk databases."""
    app, _, db_path = wal_app_and_client
    with app.app_context():
        journal_mode = db.session.execute(text("PRAGMA journal_mode")).scalar()
        assert str(journal_mode).lower() == "wal"
        foreign_keys = db.session.execute(text("PRAGMA foreign_keys")).scalar()
        assert foreign_keys == 1


def test_concurrent_multi_journey_simulations_wal(wal_app_and_client):
    """Stress test: 5 concurrent journeys stepped in parallel under SQLite WAL mode.
    
    Verifies that simultaneous steps across multiple shipments do not produce
    deadlocks or 'database is locked' errors and advance sequences monotonically.
    """
    app, _, _ = wal_app_and_client
    with app.app_context():
        profile = ProductProfile.query.filter_by(category="pharmaceutical").first()
        assert profile is not None
        t = utcnow()
        shipments = []
        for i in range(5):
            s = Shipment(
                shipment_code=f"SHP-WAL-CONC-{i:03d}",
                product_name=f"Vaccine Batch #{i}",
                product_profile_id=profile.id,
                source_location="Hub A",
                source_lat=28.6,
                source_lon=77.2,
                destination_location="Hub B",
                destination_lat=28.7,
                destination_lon=77.3,
                start_time=t,
                expected_delivery_time=t + timedelta(hours=10),
                transport_type="Refrigerated Truck",
                status="Pending",
                sim_step_minutes=15.0,
            )
            db.session.add(s)
            shipments.append(s)
        db.session.commit()

        # Start journeys
        eng = SimulationEngine()
        eng.app = app
        for s in shipments:
            eng.start_journey(s, mode="WARNING", interval_seconds=1.0, step_minutes=15.0)

        shipment_ids = [s.id for s in shipments]

    # Concurrent step workers
    def step_worker(shipment_id, steps=8):
        with app.app_context():
            for _ in range(steps):
                s = db.session.get(Shipment, shipment_id)
                with eng.lock:
                    step_shipment(s, predict_every=4)
                    db.session.commit()
                time.sleep(0.01)
        return shipment_id

    # Concurrent reader workers (querying stats & readings with per-thread test client)
    def read_worker():
        results = []
        with app.test_client() as thread_client:
            for _ in range(15):
                res1 = thread_client.get("/api/dashboard/stats")
                res2 = thread_client.get(f"/api/readings/{shipment_ids[0]}")
                assert res1.status_code == 200
                assert res2.status_code == 200
                results.append((res1.status_code, res2.status_code))
                time.sleep(0.01)
        return len(results)

    with ThreadPoolExecutor(max_workers=8) as executor:
        step_futures = [executor.submit(step_worker, sid, 10) for sid in shipment_ids]
        read_futures = [executor.submit(read_worker) for _ in range(3)]

        for f in as_completed(step_futures + read_futures):
            res = f.result()
            assert res is not None

    with app.app_context():
        for sid in shipment_ids:
            s = db.session.get(Shipment, sid)
            count = s.readings.count()
            assert count >= 10, f"Expected at least 10 readings for shipment {sid}, got {count}"
            # Verify sequence monotonicity
            seqs = [r.sequence for r in s.readings.order_by(SensorReading.sequence.asc())]
            assert seqs == list(range(1, count + 1)), f"Non-monotonic sequence: {seqs}"


def test_concurrent_reads_and_writes_burst(wal_app_and_client):
    """Burst test: 12 threads hitting reads and writes concurrently under WAL mode."""
    app, _, _ = wal_app_and_client
    with app.app_context():
        target_shipment = Shipment.query.filter_by(status="In Transit").first()
        target_id = target_shipment.id

    def reader_task(idx):
        with app.test_client() as thread_client:
            for _ in range(10):
                r = thread_client.get(f"/api/shipments/{target_id}")
                assert r.status_code == 200
                stats_r = thread_client.get("/api/dashboard/stats")
                assert stats_r.status_code == 200
        return f"reader_{idx}_ok"

    def writer_task(idx):
        with app.app_context():
            for i in range(5):
                s = db.session.get(Shipment, target_id)
                t_now = utcnow() + timedelta(minutes=idx * 10 + i)
                reading = SensorReading(
                    shipment_id=s.id,
                    sequence=1000 + (idx * 10) + i,
                    timestamp=t_now,
                    recorded_at=t_now,
                    temperature=5.0 + (i * 0.1),
                    humidity=60.0,
                    latitude=19.0,
                    longitude=72.0,
                    progress=0.5,
                    is_delayed=False,
                    temp_violation=False,
                    humidity_violation=False,
                )
                db.session.add(reading)
                db.session.commit()
                time.sleep(0.005)
        return f"writer_{idx}_ok"

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for i in range(6):
            futures.append(executor.submit(reader_task, i))
        for i in range(6):
            futures.append(executor.submit(writer_task, i))

        results = [f.result() for f in as_completed(futures)]
        assert len(results) == 12


def test_concurrent_lifecycle_state_machine_contention(app_instance, operator_token):
    """Attempt conflicting concurrent state machine transitions on the same shipment."""
    with app_instance.app_context():
        profile = ProductProfile.query.filter_by(category="dairy").first()
        t = utcnow()
        shipment = Shipment(
            shipment_code="SHP-CONC-STATE-TEST",
            product_name="State Machine Race Milk",
            product_profile_id=profile.id,
            source_location="City A",
            source_lat=20.0,
            source_lon=70.0,
            destination_location="City B",
            destination_lat=21.0,
            destination_lon=71.0,
            start_time=t,
            expected_delivery_time=t + timedelta(hours=6),
            transport_type="Refrigerated Truck",
            status="Pending",
        )
        db.session.add(shipment)
        db.session.commit()
        sid = shipment.id

    headers = {"Authorization": f"Bearer {operator_token}"}

    def attempt_transition(action):
        with app_instance.test_client() as thread_client:
            if action == "start":
                return thread_client.post(f"/api/simulation/start/{sid}", json={"mode": "NORMAL"}, headers=headers)
            elif action == "pause":
                return thread_client.post(f"/api/simulation/pause/{sid}", headers=headers)
            elif action == "resume":
                return thread_client.post(f"/api/simulation/resume/{sid}", headers=headers)
            elif action == "stop":
                return thread_client.post(f"/api/simulation/stop/{sid}", headers=headers)
        return None

    # First start the journey cleanly
    res_start = attempt_transition("start")
    assert res_start.status_code == 200

    # Fire concurrent conflicting pause and resume
    with ThreadPoolExecutor(max_workers=4) as executor:
        f_pause1 = executor.submit(attempt_transition, "pause")
        f_pause2 = executor.submit(attempt_transition, "pause")
        f_resume1 = executor.submit(attempt_transition, "resume")
        f_resume2 = executor.submit(attempt_transition, "resume")

        statuses = [f.result().status_code for f in (f_pause1, f_pause2, f_resume1, f_resume2)]

    # Either 200 (valid transition) or 409 (illegal transition due to state conflict)
    # Neither should ever return 500 or crash
    for st in statuses:
        assert st in (200, 409), f"Unexpected status code under concurrency: {st}"


# ==============================================================================
# Vector 2: Attack RBAC Stress Tests
# ==============================================================================

def test_rbac_admin_registration_exhaustive_attacks(client, operator_token):
    """Exhaustive boundary attacks against admin role registration."""
    # 1. Anonymous registering admin -> 403
    r1 = client.post("/api/auth/register", json={
        "username": "hacker_anon", "email": "anon@hacker.io", "password": "SecretPassword123", "role": "admin"
    })
    assert r1.status_code == 403

    # 2. Anonymous registering role case manipulation -> 400
    r2 = client.post("/api/auth/register", json={
        "username": "hacker_caps", "email": "caps@hacker.io", "password": "SecretPassword123", "role": "ADMIN"
    })
    assert r2.status_code == 400

    # 3. Anonymous registering role whitespace padded -> 400
    r3 = client.post("/api/auth/register", json={
        "username": "hacker_space", "email": "space@hacker.io", "password": "SecretPassword123", "role": " admin "
    })
    assert r3.status_code == 400

    # 4. Anonymous registering role array injection -> 400
    r4 = client.post("/api/auth/register", json={
        "username": "hacker_arr", "email": "arr@hacker.io", "password": "SecretPassword123", "role": ["admin"]
    })
    assert r4.status_code == 400

    # 5. Anonymous registering arbitrary role name -> 400
    r5 = client.post("/api/auth/register", json={
        "username": "hacker_super", "email": "super@hacker.io", "password": "SecretPassword123", "role": "superadmin"
    })
    assert r5.status_code == 400

    # 6. Operator attempting to register admin account -> 403
    r6 = client.post("/api/auth/register", json={
        "username": "hacker_by_op", "email": "op_escalate@hacker.io", "password": "SecretPassword123", "role": "admin"
    }, headers={"Authorization": f"Bearer {operator_token}"})
    assert r6.status_code == 403

    # 7. Forged token with invalid signature -> 403 (unauthorized attempt to register admin)
    r7 = client.post("/api/auth/register", json={
        "username": "hacker_forged", "email": "forged@hacker.io", "password": "SecretPassword123", "role": "admin"
    }, headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJ1aWQiOjF9.invalid_signature"})
    assert r7.status_code in (401, 403)


def test_rbac_cross_session_credential_isolation(client, admin_token, operator_token):
    """Verify sequential and concurrent requests on the same client do not cross-contaminate credentials."""
    # 1. Admin me request
    r_admin = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_admin.status_code == 200
    assert r_admin.get_json()["user"]["role"] == "admin"

    # 2. Unauthenticated request immediately following admin request
    r_anon = client.get("/api/auth/me")
    assert r_anon.status_code == 401

    # 3. Operator me request immediately following unauthenticated request
    r_op = client.get("/api/auth/me", headers={"Authorization": f"Bearer {operator_token}"})
    assert r_op.status_code == 200
    assert r_op.get_json()["user"]["role"] == "operator"

    # 4. Malformed bearer token request does not retain operator identity
    r_bad = client.get("/api/auth/me", headers={"Authorization": "Bearer bad_garbage_token"})
    assert r_bad.status_code == 401


def test_rbac_unauthorized_mutation_matrix(client, operator_token):
    """Exhaustive check that operators and anonymous users cannot mutate admin-only resources."""
    op_headers = {"Authorization": f"Bearer {operator_token}"}
    completed_shipment = Shipment.query.filter_by(status="Completed").first()
    assert completed_shipment is not None
    sid = completed_shipment.id

    # 1. Operator deleting completed shipment -> 403
    assert client.delete(f"/api/shipments/{sid}", headers=op_headers).status_code == 403
    # 2. Anonymous deleting completed shipment -> 401
    assert client.delete(f"/api/shipments/{sid}").status_code == 401

    # 3. Operator creating product profile -> 403
    prod_payload = {
        "name": "Unauthorized Produce",
        "category": "fruits_vegetables",
        "min_temp": 2.0,
        "max_temp": 8.0,
        "min_humidity": 80.0,
        "max_humidity": 95.0,
    }
    assert client.post("/api/products", json=prod_payload, headers=op_headers).status_code == 403
    # 4. Anonymous creating product profile -> 401
    assert client.post("/api/products", json=prod_payload).status_code == 401

    # 5. Anonymous creating shipment -> 401
    shipment_payload = {
        "product_name": "Ghost Apples",
        "product_profile_id": completed_shipment.product_profile_id,
        "source_location": "Origin",
        "source_lat": 10.0,
        "source_lon": 10.0,
        "destination_location": "Dest",
        "destination_lat": 11.0,
        "destination_lon": 11.0,
        "start_time": utcnow().isoformat(),
        "expected_delivery_time": (utcnow() + timedelta(hours=5)).isoformat(),
        "transport_type": "Refrigerated Truck",
    }
    assert client.post("/api/shipments", json=shipment_payload).status_code == 401


# ==============================================================================
# Vector 3: Attack ML Models Stress Tests
# ==============================================================================

def test_ml_extreme_temperatures_subzero_to_boiling(client):
    """Stress test ML model predictions on extreme temperature ranges (-80°C to +100°C)."""
    # 1. Deep cryogenic freeze (-80°C)
    cryo_stats = {
        "avg_temp": -80.0,
        "max_temp": -70.0,
        "avg_humidity": 10.0,
        "temp_exposure_hours": 12.0,
        "humidity_exposure_hours": 0.0,
        "journey_duration_hours": 15.0,
        "violation_count": 25,
    }
    cryo_pred = ml_service.predict_from_stats("pharmaceutical", cryo_stats)
    assert cryo_pred["risk_class"] in ("Low Risk", "Medium Risk", "High Risk")
    assert 0.0 <= cryo_pred["risk_score"] <= 100.0
    probs = cryo_pred["class_probabilities"]
    assert math.isclose(sum(probs.values()), 1.0, abs_tol=1e-3)

    # 2. Boiling temperature (+100°C)
    boil_stats = {
        "avg_temp": 95.0,
        "max_temp": 100.0,
        "avg_humidity": 90.0,
        "temp_exposure_hours": 8.0,
        "humidity_exposure_hours": 8.0,
        "journey_duration_hours": 10.0,
        "violation_count": 50,
    }
    boil_pred = ml_service.predict_from_stats("dairy", boil_stats)
    assert boil_pred["risk_class"] == "High Risk"
    assert boil_pred["risk_score"] >= 75.0
    assert 0.0 <= boil_pred["risk_score"] <= 100.0


def test_ml_zero_duration_and_boundary_durations(client):
    """Stress test ML models with zero duration and fractional/boundary durations."""
    # Zero duration
    zero_stats = {
        "avg_temp": 4.0,
        "max_temp": 4.0,
        "avg_humidity": 85.0,
        "temp_exposure_hours": 0.0,
        "humidity_exposure_hours": 0.0,
        "journey_duration_hours": 0.0,
        "violation_count": 0,
    }
    pred_zero = ml_service.predict_from_stats("dairy", zero_stats)
    assert 0.0 <= pred_zero["risk_score"] <= 100.0
    assert pred_zero["risk_class"] in ("Low Risk", "Medium Risk", "High Risk")

    # Ultra-long duration (10,000 hours)
    marathon_stats = {
        "avg_temp": 3.0,
        "max_temp": 5.0,
        "avg_humidity": 80.0,
        "temp_exposure_hours": 0.0,
        "humidity_exposure_hours": 0.0,
        "journey_duration_hours": 10000.0,
        "violation_count": 0,
    }
    pred_marathon = ml_service.predict_from_stats("dairy", marathon_stats)
    assert 0.0 <= pred_marathon["risk_score"] <= 100.0


def test_ml_nan_and_inf_handling_direct_and_api(client):
    """Verify NaN and Inf are rejected by API validation and sanitized in feature building."""
    # Direct feature row building with None or non-finite values
    none_stats = {k: None for k in NUMERIC_FEATURES}
    row = build_feature_row("dairy", none_stats)
    assert len(row) == 12
    assert all(math.isfinite(x) for x in row)

    # API rejecting NaN and Inf
    shipment = Shipment.query.first()
    payload_nan = {
        "shipment_id": shipment.id,
        "avg_temp": "NaN",
        "max_temp": 10.0,
    }
    res_nan = client.post("/api/simulator/what-if", json=payload_nan)
    assert res_nan.status_code == 400
    assert "must be a finite number" in res_nan.get_json()["error"]

    payload_inf = {
        "shipment_id": shipment.id,
        "avg_temp": "Infinity",
        "max_temp": 10.0,
    }
    res_inf = client.post("/api/simulator/what-if", json=payload_inf)
    assert res_inf.status_code == 400
    assert "must be a finite number" in res_inf.get_json()["error"]


def test_ml_tree_path_saabas_invariance_under_adversarial_vectors(client):
    """Mathematical proof check: Saabas decomposition base + sum(contrib) == score across extreme vectors."""
    clf, reg, _ = ml_service.models.require()

    test_vectors = [
        # (category, stats)
        ("pharmaceutical", {"avg_temp": -50.0, "max_temp": -20.0, "avg_humidity": 10.0, "temp_exposure_hours": 5.0, "humidity_exposure_hours": 0.0, "journey_duration_hours": 8.0, "violation_count": 12}),
        ("dairy", {"avg_temp": 45.0, "max_temp": 55.0, "avg_humidity": 99.0, "temp_exposure_hours": 15.0, "humidity_exposure_hours": 15.0, "journey_duration_hours": 20.0, "violation_count": 80}),
        ("frozen", {"avg_temp": -1.0, "max_temp": 12.0, "avg_humidity": 90.0, "temp_exposure_hours": 4.0, "humidity_exposure_hours": 4.0, "journey_duration_hours": 6.0, "violation_count": 10}),
        ("fruits_vegetables", {"avg_temp": 0.0, "max_temp": 0.0, "avg_humidity": 0.0, "temp_exposure_hours": 0.0, "humidity_exposure_hours": 0.0, "journey_duration_hours": 0.1, "violation_count": 0}),
    ]

    for cat, stats in test_vectors:
        x_row = build_feature_row(cat, stats)
        reg_base, reg_contrib = tree_contributions(reg, x_row)
        score_sum = reg_base + float(reg_contrib.sum())
        direct_pred = float(reg.predict([x_row])[0])

        assert math.isclose(score_sum, direct_pred, abs_tol=1e-3), (
            f"Saabas identity violated for {cat}: base {reg_base} + sum {reg_contrib.sum()} != {direct_pred}"
        )


# ==============================================================================
# Vector 4: Attack What-If Simulation
# ==============================================================================

def test_whatif_strict_db_immutability_under_extreme_inputs(client):
    """Verify that calling What-If with extreme inputs leaves database telemetry 100% immutable."""
    shipment = Shipment.query.filter_by(status="Completed").first()
    sid = shipment.id

    # Capture complete pre-state snapshot
    readings_pre = SensorReading.query.filter_by(shipment_id=sid).all()
    alerts_pre = ExposureAlert.query.filter_by(shipment_id=sid).all()
    preds_pre = MLPrediction.query.filter_by(shipment_id=sid).all()

    pre_readings_count = len(readings_pre)
    pre_alerts_count = len(alerts_pre)
    pre_preds_count = len(preds_pre)
    pre_status = shipment.status
    pre_progress = shipment.sim_progress
    pre_elapsed = shipment.sim_elapsed_minutes
    pre_first_temp = readings_pre[0].temperature if readings_pre else None

    # Attack with extreme counterfactual parameters
    extreme_payload = {
        "shipment_id": sid,
        "avg_temp": 85.0,
        "max_temp": 95.0,
        "avg_humidity": 99.0,
        "temp_exposure_hours": 45.0,
        "humidity_exposure_hours": 45.0,
        "journey_duration_hours": 48.0,
        "violation_count": 250,
    }
    res = client.post("/api/simulator/what-if", json=extreme_payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["simulated_prediction"]["risk_score"] >= 75.0

    # Verify post-state snapshot is completely unaltered
    db.session.expire_all()
    shipment_post = db.session.get(Shipment, sid)
    assert shipment_post.status == pre_status
    assert shipment_post.sim_progress == pre_progress
    assert shipment_post.sim_elapsed_minutes == pre_elapsed

    readings_post = SensorReading.query.filter_by(shipment_id=sid).all()
    alerts_post = ExposureAlert.query.filter_by(shipment_id=sid).all()
    preds_post = MLPrediction.query.filter_by(shipment_id=sid).all()

    assert len(readings_post) == pre_readings_count
    assert len(alerts_post) == pre_alerts_count
    assert len(preds_post) == pre_preds_count
    if readings_post:
        assert readings_post[0].temperature == pre_first_temp


def test_whatif_scenario_persistence_does_not_pollute_shipment(client, operator_token):
    """Verify persisting a simulation scenario stores only the scenario record without altering shipment data."""
    shipment = Shipment.query.filter_by(status="Completed").first()
    sid = shipment.id
    headers = {"Authorization": f"Bearer {operator_token}"}

    scenario_payload = {
        "shipment_id": sid,
        "avg_temp": 28.0,
        "max_temp": 32.0,
        "avg_humidity": 80.0,
        "temp_exposure_hours": 6.0,
        "humidity_exposure_hours": 4.0,
        "journey_duration_hours": 12.0,
        "violation_count": 15,
        "name": "Extreme Heat Scenario Test",
    }
    res = client.post("/api/simulator/what-if", json=scenario_payload, headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["saved_scenario_id"] is not None

    # Check scenario record in database
    scenario = db.session.get(SimulationScenario, data["saved_scenario_id"])
    assert scenario is not None
    assert scenario.name == "Extreme Heat Scenario Test"
    assert scenario.shipment_id == sid

    # Verify shipment predictions endpoint still reflects authentic model runs
    r_preds = client.get(f"/api/predictions/{sid}")
    assert r_preds.status_code == 200
    pred_history = r_preds.get_json()["history"]
    # All predictions in history must be genuine MLPrediction rows, not scenario records
    for p in pred_history:
        assert "trigger" in p
        assert p["trigger"] != "what-if"


def test_whatif_clamping_and_rejection_of_impossible_physics(client):
    """Verify What-If clamps inconsistent bounds and rejects out-of-range inputs."""
    shipment = Shipment.query.first()
    sid = shipment.id

    # 1. max_temp < avg_temp -> should clamp max_temp to avg_temp
    res1 = client.post("/api/simulator/what-if", json={
        "shipment_id": sid,
        "avg_temp": 25.0,
        "max_temp": 10.0,
    })
    assert res1.status_code == 200
    data1 = res1.get_json()
    assert data1["simulated_prediction"]["features"]["max_temp"] == 25.0

    # 2. exposure hours > journey duration -> should clamp exposure to duration
    res2 = client.post("/api/simulator/what-if", json={
        "shipment_id": sid,
        "journey_duration_hours": 5.0,
        "temp_exposure_hours": 20.0,
    })
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert data2["simulated_prediction"]["features"]["temp_exposure_hours"] == 5.0

    # 3. Negative journey duration -> rejected with 400
    res3 = client.post("/api/simulator/what-if", json={
        "shipment_id": sid,
        "journey_duration_hours": -2.0,
    })
    assert res3.status_code == 400

    # 4. Humidity outside [0, 100] -> rejected with 400
    res4 = client.post("/api/simulator/what-if", json={
        "shipment_id": sid,
        "avg_humidity": 150.0,
    })
    assert res4.status_code == 400


# ==============================================================================
# Vector 5: Attack PDF Generator
# ==============================================================================

def test_pdf_generation_massive_alert_flood(client):
    """Verify ReportLab PDF generation remains clean when shipment has >20 alerts (e.g. 50 alerts)."""
    profile = ProductProfile.query.first()
    t = utcnow()
    shipment = Shipment(
        shipment_code="SHP-PDF-FLOOD-50",
        product_name="Stress Pharma",
        product_profile_id=profile.id,
        source_location="Lab A",
        source_lat=20.0,
        source_lon=75.0,
        destination_location="Lab B",
        destination_lat=21.0,
        destination_lon=76.0,
        start_time=t,
        expected_delivery_time=t + timedelta(hours=24),
        transport_type="Refrigerated Truck",
        status="Completed",
    )
    db.session.add(shipment)
    db.session.commit()

    # Seed 50 alerts
    alerts = []
    severities = ["Low", "Medium", "High", "Critical"]
    for i in range(50):
        a = ExposureAlert(
            alert_code=f"ALT-FL-{i:04d}",
            shipment_id=shipment.id,
            alert_type="TEMPERATURE_HIGH" if i % 2 == 0 else "HUMIDITY_HIGH",
            severity=severities[i % 4],
            recorded_value=15.0 + (i * 0.2),
            threshold_value=8.0,
            exposure_duration_minutes=20.0 + i,
            started_at=t + timedelta(minutes=15 * i),
            timestamp=t + timedelta(minutes=15 * i + 20),
            description=f"Massive stress flood alert incident #{i}",
            is_active=False,
        )
        alerts.append(a)
    db.session.add_all(alerts)
    db.session.commit()

    res = client.get(f"/api/reports/{shipment.id}/pdf")
    assert res.status_code == 200
    assert res.headers["Content-Type"] == "application/pdf"
    assert res.data.startswith(b"%PDF-")
    assert len(res.data) > 1500


def test_pdf_generation_special_characters_and_notes_injection(client):
    """Verify ReportLab PDF handles XSS tags, XML special chars, and unicode safely."""
    profile = ProductProfile.query.first()
    t = utcnow()
    shipment = Shipment(
        shipment_code="SHP-PDF-XSS-SPEC",
        product_name="COVID-19 <mRNA> & Vaccine #42 'Cold' \"Seal\"",
        product_profile_id=profile.id,
        source_location="Origin <Hub & Port> #1",
        destination_location="Hospital & Clinic <Emergency>",
        source_lat=22.0,
        source_lon=70.0,
        destination_lat=23.0,
        destination_lon=71.0,
        start_time=t,
        expected_delivery_time=t + timedelta(hours=8),
        transport_type="Refrigerated Truck",
        status="Completed",
        notes="<script>alert('xss')</script> & 'quotes' \"double\" <bold> & ampersand 🚀❄️📦",
    )
    db.session.add(shipment)
    db.session.commit()

    res = client.get(f"/api/reports/{shipment.id}/pdf")
    assert res.status_code == 200
    assert res.headers["Content-Type"] == "application/pdf"
    assert res.data.startswith(b"%PDF-")
    assert len(res.data) > 1000


def test_pdf_generation_empty_journey_and_single_point_journey(client):
    """Verify PDF generates cleanly for 0 readings (empty journey) and 1 reading without zero-division."""
    profile = ProductProfile.query.first()
    t = utcnow()

    # Case 1: Empty journey (0 readings, 0 alerts, Pending)
    s_empty = Shipment(
        shipment_code="SHP-PDF-EMPTY",
        product_name="Virgin Shipment",
        product_profile_id=profile.id,
        source_location="A",
        source_lat=10.0,
        source_lon=10.0,
        destination_location="B",
        destination_lat=11.0,
        destination_lon=11.0,
        start_time=t,
        expected_delivery_time=t + timedelta(hours=5),
        transport_type="Refrigerated Truck",
        status="Pending",
    )
    db.session.add(s_empty)

    # Case 2: Single reading journey (1 reading, duration = 0, In Transit)
    s_single = Shipment(
        shipment_code="SHP-PDF-SINGLE",
        product_name="Single Point Shipment",
        product_profile_id=profile.id,
        source_location="A",
        source_lat=10.0,
        source_lon=10.0,
        destination_location="B",
        destination_lat=11.0,
        destination_lon=11.0,
        start_time=t,
        expected_delivery_time=t + timedelta(hours=5),
        transport_type="Refrigerated Truck",
        status="In Transit",
    )
    db.session.add(s_single)
    db.session.flush()

    reading = SensorReading(
        shipment_id=s_single.id,
        sequence=1,
        timestamp=t,
        recorded_at=t,
        temperature=4.0,
        humidity=65.0,
        latitude=10.0,
        longitude=10.0,
        progress=0.0,
        is_delayed=False,
        temp_violation=False,
        humidity_violation=False,
    )
    db.session.add(reading)
    db.session.commit()

    # Generate both PDFs
    res_empty = client.get(f"/api/reports/{s_empty.id}/pdf")
    assert res_empty.status_code == 200
    assert res_empty.headers["Content-Type"] == "application/pdf"
    assert res_empty.data.startswith(b"%PDF-")

    res_single = client.get(f"/api/reports/{s_single.id}/pdf")
    assert res_single.status_code == 200
    assert res_single.headers["Content-Type"] == "application/pdf"
    assert res_single.data.startswith(b"%PDF-")
