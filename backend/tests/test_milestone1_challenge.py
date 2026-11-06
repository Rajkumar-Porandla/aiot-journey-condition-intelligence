"""Empirical Challenge Suite for Milestone 1.

Challenge 1: Simulator mode injection & crash resistance
Challenge 2: RBAC enforcement on product creation & shipment deletion
Challenge 3: Admin registration authorization & privilege escalation defense
Challenge 4: build_feature_row robustness with None, empty, and partial stats
"""
from datetime import timedelta
import time
import pytest
from itsdangerous import URLSafeTimedSerializer
from app import create_app
from app.config import TestConfig
from app.core.features import NUMERIC_FEATURES, CATEGORY_FEATURES, FEATURE_NAMES, build_feature_row
from app.core.product_defaults import CATEGORY_KEYS
from app.extensions import db
from app.models import ProductProfile, Shipment, User, utcnow
from app.services.seed import seed_database
from app.services.simulation_engine import SimulationError, engine


@pytest.fixture
def app():
    app = create_app(config_class=TestConfig, start_engine=False)
    engine.app = app
    with app.app_context():
        db.create_all()
        seed_database()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    with app.test_client() as test_client:
        yield test_client


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


@pytest.fixture
def expired_token(app):
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="aiot-journey-auth")
    user = User.query.filter_by(username="operator").first()
    return serializer.dumps({"uid": user.id, "tv": user.token_version})


@pytest.fixture
def corrupted_token():
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.corrupted_payload.invalid_signature"


@pytest.fixture
def stopped_shipment(app):
    profile = ProductProfile.query.filter_by(category="dairy").first()
    now = utcnow()
    shipment = Shipment(
        shipment_code="SHP-CHALLENGE-01",
        product_name="Challenge Milk",
        product_profile_id=profile.id,
        source_location="Anand, IN",
        source_lat=22.56,
        source_lon=72.95,
        destination_location="Mumbai, IN",
        destination_lat=19.07,
        destination_lon=72.87,
        start_time=now,
        expected_delivery_time=now + timedelta(hours=6),
        transport_type="Refrigerated Truck",
        status="Pending",
    )
    db.session.add(shipment)
    db.session.commit()

    # Start and stop to reach Stopped state with prior sim_state
    engine.start_journey(shipment, mode="NORMAL", interval_seconds=2.0, step_minutes=15.0)
    assert shipment.status == "In Transit"
    assert shipment.sim_state is not None
    engine.stop(shipment)
    assert shipment.status == "Stopped"
    return shipment


# ==============================================================================
# Challenge 1: Simulator Mode Injection & Crash Resistance
# ==============================================================================

@pytest.mark.parametrize("invalid_mode", ["HACKED", None, "", "normal", "critical", 12345, "DROP TABLE"])
def test_challenge1_direct_engine_restart_invalid_modes(stopped_shipment, invalid_mode):
    """Verify engine.start_journey cleanly raises SimulationError with 400 on restart and doesn't crash."""
    orig_state = stopped_shipment.sim_state
    orig_status = stopped_shipment.status

    with pytest.raises(SimulationError) as exc_info:
        engine.start_journey(
            stopped_shipment,
            mode=invalid_mode,
            interval_seconds=2.0,
            step_minutes=15.0,
        )

    assert exc_info.value.status_code == 400
    assert "Invalid simulation mode" in str(exc_info.value)

    # Engine must not have mutated state or crashed
    db.session.refresh(stopped_shipment)
    assert stopped_shipment.status == orig_status
    assert stopped_shipment.sim_state == orig_state

    # Engine tick still functions without crashing
    engine._tick()


@pytest.mark.parametrize("invalid_mode", ["HACKED", "normal", "WARNING_UPPER", "invalid"])
def test_challenge1_api_restart_invalid_mode_returns_400(client, operator_token, stopped_shipment, invalid_mode):
    """Verify HTTP API returns 400 when restarting journey with invalid modes."""
    headers = {"Authorization": f"Bearer {operator_token}"}
    res = client.post(
        f"/api/simulation/start/{stopped_shipment.id}",
        headers=headers,
        json={"mode": invalid_mode},
    )
    assert res.status_code == 400
    assert "mode" in res.get_json()["error"].lower()

    # Verify simulation state remains intact
    db.session.refresh(stopped_shipment)
    assert stopped_shipment.status == "Stopped"

    # Engine tick still functions
    engine._tick()


def test_challenge1_valid_restart_after_invalid_attempts(stopped_shipment):
    """Verify the journey can still be properly restarted in a valid mode after failed injection attempts."""
    for bad_mode in ["HACKED", None, "", "normal"]:
        try:
            engine.start_journey(stopped_shipment, mode=bad_mode, interval_seconds=2.0, step_minutes=15.0)
        except SimulationError:
            pass

    # Now restart with valid mode WARNING
    engine.start_journey(stopped_shipment, mode="WARNING", interval_seconds=2.0, step_minutes=15.0)
    db.session.refresh(stopped_shipment)
    assert stopped_shipment.status == "In Transit"
    assert stopped_shipment.sim_mode == "WARNING"
    assert stopped_shipment.sim_state["sensor"]["mode"] == "WARNING"

    # Stop cleanly
    engine.stop(stopped_shipment)
    assert stopped_shipment.status == "Stopped"


# ==============================================================================
# Challenge 2: RBAC Stress Tests (Create Product & Delete Shipment)
# ==============================================================================

def test_challenge2_create_product_rbac_matrix(client, operator_token, corrupted_token, app):
    """Test POST /api/products with operator, expired, corrupted, and no token."""
    url = "/api/products"
    payload = {
        "name": "RBAC Test Milk",
        "category": "dairy",
        "min_temp": 2.0,
        "max_temp": 6.0,
        "min_humidity": 50.0,
        "max_humidity": 70.0,
        "sensitivity": "Medium",
    }

    # 1. Operator token -> 403 Forbidden
    res_op = client.post(url, headers={"Authorization": f"Bearer {operator_token}"}, json=payload)
    assert res_op.status_code == 403
    assert "Administrator role required" in res_op.get_json()["error"]

    # 2. Corrupted token -> 401 Unauthorized
    res_corr = client.post(url, headers={"Authorization": f"Bearer {corrupted_token}"}, json=payload)
    assert res_corr.status_code == 401
    assert "Invalid authentication token" in res_corr.get_json()["error"]

    # 3. No token -> 401 Unauthorized
    res_no = client.post(url, json=payload)
    assert res_no.status_code == 401
    assert "Authentication required" in res_no.get_json()["error"]

    # 4. Expired token -> 401 Unauthorized
    # Create expired token with max_age=0
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="aiot-journey-auth")
    user = User.query.filter_by(username="operator").first()
    token = serializer.dumps({"uid": user.id, "tv": user.token_version})
    # Setting max_age to negative in test request to trigger SignatureExpired
    orig_age = app.config["TOKEN_MAX_AGE_HOURS"]
    app.config["TOKEN_MAX_AGE_HOURS"] = -1
    try:
        res_exp = client.post(url, headers={"Authorization": f"Bearer {token}"}, json=payload)
        assert res_exp.status_code == 401
        assert "Session expired" in res_exp.get_json()["error"]
    finally:
        app.config["TOKEN_MAX_AGE_HOURS"] = orig_age

    # Verify product was NOT created in DB
    assert ProductProfile.query.filter_by(name="RBAC Test Milk").first() is None


def test_challenge2_delete_shipment_rbac_matrix(client, operator_token, corrupted_token, app):
    """Test DELETE /api/shipments/<id> with operator, expired, corrupted, and no token."""
    shipment = Shipment.query.filter_by(status="Completed").first()
    assert shipment is not None
    url = f"/api/shipments/{shipment.id}"

    # 1. Operator token -> 403 Forbidden
    res_op = client.delete(url, headers={"Authorization": f"Bearer {operator_token}"})
    assert res_op.status_code == 403
    assert "Administrator role required" in res_op.get_json()["error"]

    # 2. Corrupted token -> 401 Unauthorized
    res_corr = client.delete(url, headers={"Authorization": f"Bearer {corrupted_token}"})
    assert res_corr.status_code == 401
    assert "Invalid authentication token" in res_corr.get_json()["error"]

    # 3. No token -> 401 Unauthorized
    res_no = client.delete(url)
    assert res_no.status_code == 401
    assert "Authentication required" in res_no.get_json()["error"]

    # 4. Expired token -> 401 Unauthorized
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="aiot-journey-auth")
    user = User.query.filter_by(username="admin").first()
    token = serializer.dumps({"uid": user.id, "tv": user.token_version})
    orig_age = app.config["TOKEN_MAX_AGE_HOURS"]
    app.config["TOKEN_MAX_AGE_HOURS"] = -1
    try:
        res_exp = client.delete(url, headers={"Authorization": f"Bearer {token}"})
        assert res_exp.status_code == 401
        assert "Session expired" in res_exp.get_json()["error"]
    finally:
        app.config["TOKEN_MAX_AGE_HOURS"] = orig_age

    # Verify shipment was NOT deleted
    assert db.session.get(Shipment, shipment.id) is not None


# ==============================================================================
# Challenge 3: Admin Registration Authorization Stress Test
# ==============================================================================

def test_challenge3_register_admin_matrix(client, operator_token, admin_token):
    """Test registering an admin: no credentials, operator credentials, and admin credentials."""
    url = "/api/auth/register"

    # 1. Without credentials -> 403 Forbidden
    res_anon = client.post(
        url,
        json={
            "username": "anon_admin_attempt",
            "email": "anon_admin@test.local",
            "password": "Password123",
            "role": "admin",
        },
    )
    assert res_anon.status_code == 403
    assert "Only administrators can register admin accounts" in res_anon.get_json()["error"]
    assert User.query.filter_by(username="anon_admin_attempt").first() is None

    # 2. With operator credentials -> 403 Forbidden
    res_op = client.post(
        url,
        headers={"Authorization": f"Bearer {operator_token}"},
        json={
            "username": "operator_admin_attempt",
            "email": "op_admin@test.local",
            "password": "Password123",
            "role": "admin",
        },
    )
    assert res_op.status_code == 403
    assert "Only administrators can register admin accounts" in res_op.get_json()["error"]
    assert User.query.filter_by(username="operator_admin_attempt").first() is None

    # 3. With admin credentials -> 201 Created
    res_admin = client.post(
        url,
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "username": "legit_new_admin",
            "email": "legit_admin@test.local",
            "password": "Password123",
            "role": "admin",
        },
    )
    assert res_admin.status_code == 201
    data = res_admin.get_json()
    assert data["user"]["role"] == "admin"
    assert data["user"]["username"] == "legit_new_admin"
    assert "token" in data

    # Verify user in database
    new_admin = User.query.filter_by(username="legit_new_admin").first()
    assert new_admin is not None
    assert new_admin.role == "admin"


def test_challenge3_privilege_escalation_via_g_pollution(client, admin_token):
    """Verify that prior admin requests do not bleed context to allow anonymous admin creation."""
    # 1. Admin accesses /api/auth/me, which sets g.current_user to admin
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_me.status_code == 200

    # 2. Anonymous attacker sends register request with role="admin" and NO Authorization header
    res_attack = client.post(
        "/api/auth/register",
        json={
            "username": "escalated_hacker_admin",
            "email": "hacker@evil.local",
            "password": "Password123",
            "role": "admin",
        },
    )
    assert res_attack.status_code == 403
    assert "Only administrators can register admin accounts" in res_attack.get_json()["error"]
    assert User.query.filter_by(username="escalated_hacker_admin").first() is None


# ==============================================================================
# Challenge 4: build_feature_row Robustness with None, Empty, and Partial Stats
# ==============================================================================

def test_challenge4_build_feature_row_all_none():
    """Verify build_feature_row cleanly handles dictionary with all None values."""
    category = "dairy"
    stats_all_none = {k: None for k in NUMERIC_FEATURES}
    row = build_feature_row(category, stats_all_none)

    assert len(row) == len(FEATURE_NAMES)
    assert len(row) == 7 + len(CATEGORY_KEYS)

    # First 7 numeric values must default to 0.0
    for i in range(7):
        assert row[i] == 0.0
        assert isinstance(row[i], float)

    # One-hot encoding for category
    cat_idx = CATEGORY_KEYS.index(category)
    for i, c in enumerate(CATEGORY_KEYS):
        assert row[7 + i] == (1.0 if i == cat_idx else 0.0)


def test_challenge4_build_feature_row_empty_dict():
    """Verify build_feature_row cleanly handles an empty dictionary."""
    category = "pharmaceutical"
    row = build_feature_row(category, {})

    assert len(row) == len(FEATURE_NAMES)
    for i in range(7):
        assert row[i] == 0.0
        assert isinstance(row[i], float)

    cat_idx = CATEGORY_KEYS.index(category)
    for i, c in enumerate(CATEGORY_KEYS):
        assert row[7 + i] == (1.0 if i == cat_idx else 0.0)


def test_challenge4_build_feature_row_missing_and_mixed_keys():
    """Verify build_feature_row with partial keys, missing keys, and mixed numeric types."""
    category = "frozen"
    stats_mixed = {
        "avg_temp": -18.5,
        "max_temp": None,
        "avg_humidity": "45.2",  # String float convertible
        # temp_exposure_hours missing
        # humidity_exposure_hours missing
        "journey_duration_hours": 12,  # Integer
        "violation_count": 0,
    }
    row = build_feature_row(category, stats_mixed)

    assert len(row) == len(FEATURE_NAMES)
    assert row[0] == -18.5
    assert row[1] == 0.0  # max_temp was None
    assert row[2] == 45.2  # avg_humidity string converted to float
    assert row[3] == 0.0  # temp_exposure_hours missing
    assert row[4] == 0.0  # humidity_exposure_hours missing
    assert row[5] == 12.0  # journey_duration_hours int converted to float
    assert row[6] == 0.0  # violation_count 0

    cat_idx = CATEGORY_KEYS.index(category)
    for i, c in enumerate(CATEGORY_KEYS):
        assert row[7 + i] == (1.0 if i == cat_idx else 0.0)


def test_challenge4_build_feature_row_invalid_category():
    """Verify build_feature_row raises ValueError for unknown category."""
    with pytest.raises(ValueError) as exc:
        build_feature_row("nonexistent_cat", {})
    assert "Unknown product category" in str(exc.value)


# ==============================================================================
# Challenge 5: Milestone 2 Backend Remediation & Status Code Verifications
# ==============================================================================

def test_challenge5_simulation_error_status_code_preservation(client, operator_token, stopped_shipment):
    """Verify SimulationError error handler propagates err.status_code rather than hardcoding 409."""
    from app.routes.simulation_routes import _handle_sim_error

    # 1. Custom status code propagation (e.g. 400, 422)
    err_400 = SimulationError("Invalid simulation mode: UNKNOWN", status_code=400)
    response_400, code_400 = _handle_sim_error(err_400)
    assert code_400 == 400
    assert response_400.get_json()["error"] == "Invalid simulation mode: UNKNOWN"

    err_422 = SimulationError("Custom validation failure", status_code=422)
    response_422, code_422 = _handle_sim_error(err_422)
    assert code_422 == 422

    # 2. Default fallback when status_code is missing
    err_default = SimulationError("Conflict state")
    err_default.status_code = None
    response_def, code_def = _handle_sim_error(err_default)
    assert code_def == 409

    # 3. HTTP endpoint integration test: pausing a stopped shipment raises SimulationError -> 409
    res = client.post(
        f"/api/simulation/pause/{stopped_shipment.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert res.status_code == 409
    assert "In Transit journey can be paused" in res.get_json()["error"]


def test_challenge5_what_if_unauthenticated_scenario_persistence(client):
    """Verify unauthenticated What-If requests can save named scenarios without AttributeError on g.current_user."""
    shipment = Shipment.query.filter_by(status="Completed").first()
    assert shipment is not None

    scenario_name = "Anonymous Scenario Test"
    res = client.post(
        "/api/simulator/what-if",
        json={
            "shipment_id": shipment.id,
            "name": scenario_name,
            "avg_temp": 10.0,
            "max_temp": 15.0,
        },
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["saved_scenario_id"] is not None

    from app.models import SimulationScenario
    scen = db.session.get(SimulationScenario, data["saved_scenario_id"])
    assert scen is not None
    assert scen.user_id is None
    assert scen.name == scenario_name


def test_challenge5_compare_category_label_human_readable(client):
    """Verify /api/compare returns formatted human-readable category_label."""
    from app.core.product_defaults import category_label
    shipments = Shipment.query.filter_by(status="Completed").limit(2).all()
    assert len(shipments) >= 2

    res = client.post("/api/compare", json={"shipment_ids": [s.id for s in shipments]})
    assert res.status_code == 200
    data = res.get_json()

    for item in data["shipments"]:
        shipment_obj = db.session.get(Shipment, item["shipment_id"])
        expected_label = category_label(shipment_obj.category)
        assert item["category_label"] == expected_label

