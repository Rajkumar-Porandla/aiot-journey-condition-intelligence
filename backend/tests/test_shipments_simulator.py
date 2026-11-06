"""Tier 1, Tier 2, and Tier 3 Whitebox & API Tests for Shipment Management and IoT Simulator.

Features Covered:
- Feature 4: Shipment Management CRUD (Create, list, get by ID, filter).
- Feature 5: Journey State Transitions & Lifecycle (Start, pause, resume, stop, complete).
- Feature 6: IoT Sensor Simulation Modes & Progression (Normal/Warning/Critical, progression).
- Feature 7: Simulator Boundary & Anomaly Safeguards (Illegal transitions, invalid mode, coordinates, intensity).
- Downsampling and monotonic tick progression without temporal or spatial drift.
"""
from datetime import datetime, timedelta, timezone
import pytest
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import ProductProfile, SensorReading, Shipment, utcnow
from app.services.analytics import downsample
from app.services.seed import seed_database
from app.services.simulation_engine import SimulationError, engine, step_shipment


@pytest.fixture
def client():
    """Create isolated test application context with in-memory database."""
    app = create_app(config_class=TestConfig, start_engine=False)
    with app.app_context():
        db.create_all()
        seed_database()
        with app.test_client() as test_client:
            yield test_client
        db.session.remove()
        db.drop_all()


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
def pending_shipment(client):
    """Create a pristine Pending shipment for testing."""
    profile = ProductProfile.query.filter_by(category="dairy").first()
    assert profile is not None
    now = utcnow()
    shipment = Shipment(
        shipment_code="SHP-TEST-PENDING",
        product_name="Test Raw Milk",
        product_profile_id=profile.id,
        source_location="Anand, IN",
        source_lat=22.56,
        source_lon=72.95,
        destination_location="Mumbai, IN",
        destination_lat=19.07,
        destination_lon=72.87,
        start_time=now,
        expected_delivery_time=now + timedelta(hours=8),
        transport_type="Refrigerated Truck",
        status="Pending",
    )
    db.session.add(shipment)
    db.session.commit()
    return shipment


# ==============================================================================
# Tier 1: Primary Shipment CRUD and Lifecycle Controls
# ==============================================================================

def test_create_shipment_success(client, operator_token):
    """Verify creating a new shipment returns 201 with unique code and Pending status."""
    profile = ProductProfile.query.filter_by(category="dairy").first()
    now_iso = utcnow().isoformat()
    later_iso = (utcnow() + timedelta(hours=10)).isoformat()

    payload = {
        "product_name": "Organic Whole Milk",
        "product_profile_id": profile.id,
        "source_location": "Anand, IN",
        "source_lat": 22.56,
        "source_lon": 72.95,
        "destination_location": "Surat, IN",
        "destination_lat": 21.17,
        "destination_lon": 72.83,
        "start_time": now_iso,
        "expected_delivery_time": later_iso,
        "transport_type": "Refrigerated Truck",
        "notes": "Fragile organic dairy",
    }
    res = client.post("/api/shipments", headers={"Authorization": f"Bearer {operator_token}"}, json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert "shipment" in data
    shp = data["shipment"]
    assert shp["product_name"] == "Organic Whole Milk"
    assert shp["status"] == "Pending"
    assert shp["shipment_code"].startswith("SHP-")


def test_list_shipments_and_filter(client):
    """Verify listing shipments with status and category query filters."""
    # List all
    res = client.get("/api/shipments")
    assert res.status_code == 200
    shipments = res.get_json()["shipments"]
    assert len(shipments) >= 5

    # Filter by status
    res_completed = client.get("/api/shipments?status=Completed")
    assert res_completed.status_code == 200
    for s in res_completed.get_json()["shipments"]:
        assert s["status"] == "Completed"

    # Filter by category
    res_pharma = client.get("/api/shipments?category=pharmaceutical")
    assert res_pharma.status_code == 200
    for s in res_pharma.get_json()["shipments"]:
        assert s["category"] == "pharmaceutical"


def test_get_shipment_by_id(client):
    """Verify getting a shipment by its database ID includes stats."""
    shipment = Shipment.query.first()
    assert shipment is not None

    res = client.get(f"/api/shipments/{shipment.id}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["shipment"]["id"] == shipment.id
    assert "stats" in data["shipment"]


def test_start_virtual_journey(client, operator_token, pending_shipment):
    """Verify starting a journey transitions status from Pending to In Transit."""
    payload = {
        "mode": "NORMAL",
        "interval_seconds": 2.0,
        "step_minutes": 15.0,
        "intensity": 1.0,
    }
    res = client.post(
        f"/api/simulation/start/{pending_shipment.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
        json=payload,
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["shipment"]["status"] == "In Transit"
    assert data["shipment"]["simulation"]["mode"] == "NORMAL"


def test_pause_and_resume_virtual_journey(client, operator_token, pending_shipment):
    """Verify full pause and resume journey lifecycle."""
    headers = {"Authorization": f"Bearer {operator_token}"}

    # Start first
    client.post(f"/api/simulation/start/{pending_shipment.id}", headers=headers, json={"mode": "WARNING"})

    # Pause
    pause_res = client.post(f"/api/simulation/pause/{pending_shipment.id}", headers=headers)
    assert pause_res.status_code == 200
    assert pause_res.get_json()["shipment"]["status"] == "Paused"

    # Resume
    resume_res = client.post(f"/api/simulation/resume/{pending_shipment.id}", headers=headers)
    assert resume_res.status_code == 200
    assert resume_res.get_json()["shipment"]["status"] == "In Transit"


def test_stop_virtual_journey(client, operator_token, pending_shipment):
    """Verify stopping an In Transit journey sets status to Stopped."""
    headers = {"Authorization": f"Bearer {operator_token}"}
    client.post(f"/api/simulation/start/{pending_shipment.id}", headers=headers, json={})

    res = client.post(f"/api/simulation/stop/{pending_shipment.id}", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["shipment"]["status"] == "Stopped"


def test_mark_virtual_journey_completed(client, operator_token, pending_shipment):
    """Verify marking a started journey completed sets status to Completed."""
    headers = {"Authorization": f"Bearer {operator_token}"}
    client.post(f"/api/simulation/start/{pending_shipment.id}", headers=headers, json={})

    res = client.post(f"/api/simulation/complete/{pending_shipment.id}", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["shipment"]["status"] == "Completed"


# ==============================================================================
# Tier 2: Boundary & Corner Cases / State Machine Safeguards
# ==============================================================================

def test_pause_when_pending_rejected_with_409(client, operator_token, pending_shipment):
    """Verify pausing a Pending journey is rejected."""
    res = client.post(
        f"/api/simulation/pause/{pending_shipment.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert res.status_code == 409
    assert "Only an In Transit journey can be paused" in res.get_json()["error"]


def test_resume_when_stopped_rejected_with_409(client, operator_token, pending_shipment):
    """Verify resuming a Stopped journey is rejected."""
    headers = {"Authorization": f"Bearer {operator_token}"}
    client.post(f"/api/simulation/start/{pending_shipment.id}", headers=headers, json={})
    client.post(f"/api/simulation/stop/{pending_shipment.id}", headers=headers)

    res = client.post(f"/api/simulation/resume/{pending_shipment.id}", headers=headers)
    assert res.status_code == 409
    assert "Only a Paused journey can be resumed" in res.get_json()["error"]


def test_start_when_already_in_transit_rejected_with_409(client, operator_token, pending_shipment):
    """Verify starting an already In Transit journey is rejected."""
    headers = {"Authorization": f"Bearer {operator_token}"}
    client.post(f"/api/simulation/start/{pending_shipment.id}", headers=headers, json={})

    res = client.post(f"/api/simulation/start/{pending_shipment.id}", headers=headers, json={})
    assert res.status_code == 409
    assert "Only Pending or Stopped shipments can be started" in res.get_json()["error"]


def test_pause_when_already_paused_rejected_with_409(client, operator_token, pending_shipment):
    """Verify pausing an already Paused journey is rejected."""
    headers = {"Authorization": f"Bearer {operator_token}"}
    client.post(f"/api/simulation/start/{pending_shipment.id}", headers=headers, json={})
    client.post(f"/api/simulation/pause/{pending_shipment.id}", headers=headers)

    res = client.post(f"/api/simulation/pause/{pending_shipment.id}", headers=headers)
    assert res.status_code == 409


def test_complete_when_pending_rejected_with_409(client, operator_token, pending_shipment):
    """Verify completing a shipment that has never started is rejected."""
    res = client.post(
        f"/api/simulation/complete/{pending_shipment.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert res.status_code == 409
    assert "Only shipments whose journey has started" in res.get_json()["error"]


def test_invalid_simulation_mode_rejected(client, operator_token, pending_shipment):
    """Verify starting with an unknown simulation mode returns 400."""
    res = client.post(
        f"/api/simulation/start/{pending_shipment.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"mode": "INVALID_MODE"},
    )
    assert res.status_code == 400


def test_invalid_simulation_mode_on_restart_rejected(pending_shipment):
    """Verify restarting a stopped journey with invalid simulation mode raises SimulationError."""
    # Start and stop journey
    engine.start_journey(pending_shipment, mode="NORMAL", interval_seconds=2.0, step_minutes=15.0)
    engine.stop(pending_shipment)
    assert pending_shipment.status == "Stopped"

    # Attempt restart with invalid mode
    with pytest.raises(SimulationError) as exc_info:
        engine.start_journey(pending_shipment, mode="INVALID_MODE", interval_seconds=2.0, step_minutes=15.0)
    assert "Invalid simulation mode" in str(exc_info.value)


def test_update_shipment_pending_state_allowed(client, operator_token, pending_shipment):
    """Verify editing a shipment in Pending state succeeds."""
    headers = {"Authorization": f"Bearer {operator_token}"}
    res = client.put(
        f"/api/shipments/{pending_shipment.id}",
        headers=headers,
        json={"product_name": "Updated Organic Milk", "notes": "New delivery instructions"},
    )
    assert res.status_code == 200
    assert res.get_json()["shipment"]["product_name"] == "Updated Organic Milk"


def test_update_shipment_in_transit_or_completed_rejected(client, operator_token, pending_shipment):
    """Verify editing a shipment that is In Transit or Completed is rejected with 400."""
    headers = {"Authorization": f"Bearer {operator_token}"}
    client.post(f"/api/simulation/start/{pending_shipment.id}", headers=headers, json={})

    # Try editing while In Transit
    res_transit = client.put(
        f"/api/shipments/{pending_shipment.id}",
        headers=headers,
        json={"product_name": "Illegal Edit"},
    )
    assert res_transit.status_code == 400
    assert "Cannot edit a shipment that is already In Transit" in res_transit.get_json()["error"]

    # Mark completed and try editing
    client.post(f"/api/simulation/complete/{pending_shipment.id}", headers=headers)
    res_completed = client.put(
        f"/api/shipments/{pending_shipment.id}",
        headers=headers,
        json={"product_name": "Illegal Edit"},
    )
    assert res_completed.status_code == 400
    assert "Cannot edit a shipment that is already Completed" in res_completed.get_json()["error"]


def test_invalid_coordinates_boundary_validation(client, operator_token):
    """Verify latitude outside [-90, 90] and longitude outside [-180, 180] are rejected with 400."""
    profile = ProductProfile.query.first()
    base_payload = {
        "product_name": "Test Coordinates",
        "product_profile_id": profile.id,
        "source_location": "Loc A",
        "source_lat": 20.0,
        "source_lon": 70.0,
        "destination_location": "Loc B",
        "destination_lat": 25.0,
        "destination_lon": 75.0,
        "start_time": utcnow().isoformat(),
        "expected_delivery_time": (utcnow() + timedelta(hours=5)).isoformat(),
    }
    headers = {"Authorization": f"Bearer {operator_token}"}

    # Latitude > 90
    p1 = dict(base_payload, source_lat=91.0)
    assert client.post("/api/shipments", headers=headers, json=p1).status_code == 400

    # Latitude < -90
    p2 = dict(base_payload, destination_lat=-90.5)
    assert client.post("/api/shipments", headers=headers, json=p2).status_code == 400

    # Longitude > 180
    p3 = dict(base_payload, source_lon=180.1)
    assert client.post("/api/shipments", headers=headers, json=p3).status_code == 400

    # Longitude < -180
    p4 = dict(base_payload, destination_lon=-181.0)
    assert client.post("/api/shipments", headers=headers, json=p4).status_code == 400


def test_intensity_bounds_validation(client, operator_token, pending_shipment):
    """Verify intensity outside [0.5, 3.0] is rejected with 400."""
    headers = {"Authorization": f"Bearer {operator_token}"}

    # Intensity < 0.5
    res_low = client.post(
        f"/api/simulation/start/{pending_shipment.id}",
        headers=headers,
        json={"intensity": 0.2},
    )
    assert res_low.status_code == 400

    # Intensity > 3.0
    res_high = client.post(
        f"/api/simulation/start/{pending_shipment.id}",
        headers=headers,
        json={"intensity": 3.5},
    )
    assert res_high.status_code == 400


def test_delivery_time_must_be_after_start_time(client, operator_token):
    """Verify delivery time equal to or earlier than start time is rejected with 400."""
    profile = ProductProfile.query.first()
    t = utcnow()
    payload = {
        "product_name": "Time Machine Delivery",
        "product_profile_id": profile.id,
        "source_location": "Loc A",
        "source_lat": 20.0,
        "source_lon": 70.0,
        "destination_location": "Loc B",
        "destination_lat": 25.0,
        "destination_lon": 75.0,
        "start_time": t.isoformat(),
        "expected_delivery_time": (t - timedelta(hours=1)).isoformat(),
    }
    res = client.post("/api/shipments", headers={"Authorization": f"Bearer {operator_token}"}, json=payload)
    assert res.status_code == 400
    assert "Expected delivery time must be after the start time" in res.get_json()["error"]


# ==============================================================================
# Tier 3: Telemetry Downsampling and Monotonic Progression
# ==============================================================================

def test_telemetry_downsampling_over_300_readings(client, pending_shipment):
    """Verify downsampling accurately windows >300 readings down to exactly 300 points."""
    # Seed 350 readings
    readings = []
    t_start = utcnow()
    for seq in range(1, 351):
        r = SensorReading(
            shipment_id=pending_shipment.id,
            sequence=seq,
            timestamp=t_start + timedelta(minutes=15 * seq),
            recorded_at=t_start,
            temperature=4.0 + (seq % 3) * 0.2,
            humidity=60.0 + (seq % 5) * 0.5,
            latitude=22.56 + (seq * 0.01),
            longitude=72.95 + (seq * 0.01),
            progress=seq / 350.0,
        )
        readings.append(r)
    db.session.add_all(readings)
    db.session.commit()

    # Query with sample=true
    res = client.get(f"/api/readings/{pending_shipment.id}?sample=true")
    assert res.status_code == 200
    sample_data = res.get_json()
    assert "readings" in sample_data
    sampled_readings = sample_data["readings"]

    # Verify count is downsampled to exactly 300
    assert len(sampled_readings) == 300

    # Verify first and last points are preserved
    assert sampled_readings[0]["sequence"] == 1
    assert sampled_readings[-1]["sequence"] == 350

    # Verify strictly monotonic ordering
    sequences = [r["sequence"] for r in sampled_readings]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))  # No duplicate sequences


def test_simulation_tick_progression_without_drift(pending_shipment):
    """Verify step_shipment generates monotonic sequence, consistent time steps, and advancing progress."""
    engine.start_journey(pending_shipment, mode="NORMAL", interval_seconds=2.0, step_minutes=15.0)

    previous_seq = 0
    previous_time = pending_shipment.start_time
    previous_progress = 0.0

    # Step through 10 simulated readings
    for step in range(1, 11):
        reading = step_shipment(pending_shipment, predict_every=0)
        db.session.commit()

        # Verify sequence increments strictly by 1
        assert reading.sequence == previous_seq + 1
        previous_seq = reading.sequence

        # Verify timestamp advances by exactly sim_step_minutes (15 min)
        expected_time = previous_time + timedelta(minutes=15.0)
        assert reading.timestamp == expected_time
        previous_time = reading.timestamp

        # Verify progress is monotonically advancing
        assert reading.progress >= previous_progress
        previous_progress = reading.progress

    assert pending_shipment.sim_elapsed_minutes == 150.0  # 10 steps * 15 min


def test_nonexistent_shipment_endpoints_return_404(client, operator_token):
    """Verify operations on non-existent shipment ID return 404."""
    headers = {"Authorization": f"Bearer {operator_token}"}
    fake_id = 999999

    assert client.get(f"/api/shipments/{fake_id}").status_code == 404
    assert client.post(f"/api/simulation/start/{fake_id}", headers=headers).status_code == 404
    assert client.post(f"/api/simulation/pause/{fake_id}", headers=headers).status_code == 404
    assert client.post(f"/api/simulation/resume/{fake_id}", headers=headers).status_code == 404
    assert client.post(f"/api/simulation/stop/{fake_id}", headers=headers).status_code == 404
    assert client.post(f"/api/simulation/complete/{fake_id}", headers=headers).status_code == 404
    assert client.get(f"/api/readings/{fake_id}").status_code == 404


def test_readings_pagination_and_since_seq(client, pending_shipment):
    """Verify querying readings with since_seq and limit filters correctly."""
    t = utcnow()
    readings = [
        SensorReading(
            shipment_id=pending_shipment.id,
            sequence=i,
            timestamp=t + timedelta(minutes=15 * i),
            recorded_at=t,
            temperature=4.0,
            humidity=55.0,
            latitude=20.0,
            longitude=70.0,
            progress=i / 20.0,
        )
        for i in range(1, 21)
    ]
    db.session.add_all(readings)
    db.session.commit()

    # Query since_seq = 15 -> should return sequences 16 to 20 (5 items)
    res_since = client.get(f"/api/readings/{pending_shipment.id}?since_seq=15")
    assert res_since.status_code == 200
    returned_since = res_since.get_json()["readings"]
    assert len(returned_since) == 5
    assert returned_since[0]["sequence"] == 16
    assert returned_since[-1]["sequence"] == 20

    # Query with limit = 3 -> should return last 3 readings (18, 19, 20)
    res_limit = client.get(f"/api/readings/{pending_shipment.id}?limit=3")
    assert res_limit.status_code == 200
    returned_limit = res_limit.get_json()["readings"]
    assert len(returned_limit) == 3
    assert returned_limit[-1]["sequence"] == 20


def test_location_interpolation_bounding_box(pending_shipment):
    """Verify truck coordinates during virtual journey remain within bounded geographic trajectory."""
    engine.start_journey(pending_shipment, mode="NORMAL", interval_seconds=2.0, step_minutes=15.0)

    min_lat = min(pending_shipment.source_lat, pending_shipment.destination_lat) - 1.0
    max_lat = max(pending_shipment.source_lat, pending_shipment.destination_lat) + 1.0
    min_lon = min(pending_shipment.source_lon, pending_shipment.destination_lon) - 1.0
    max_lon = max(pending_shipment.source_lon, pending_shipment.destination_lon) + 1.0

    for _ in range(8):
        reading = step_shipment(pending_shipment, predict_every=0)
        db.session.commit()
        assert min_lat <= reading.latitude <= max_lat
        assert min_lon <= reading.longitude <= max_lon

