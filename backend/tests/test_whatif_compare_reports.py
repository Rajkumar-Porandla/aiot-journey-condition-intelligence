"""Tier 1 and Tier 2 Whitebox & API Tests for What-If Simulator, Multi-Shipment Comparison, and PDF Reports.

Features Covered:
- Feature 11: What-If Journey Simulator Counterfactuals (Isolated simulation, scenario persistence, bounds clamping).
- Feature 12: Multi-Shipment Risk Comparison & Safest Journey (Same vs cross-category, safest journey identification).
- Feature 13: Journey Condition PDF Audit Report Generation (ReportLab generation, empty readings, heavy alert logs).
"""
from datetime import datetime, timedelta
import pytest
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import ExposureAlert, ProductProfile, SensorReading, Shipment, SimulationScenario, utcnow
from app.services.seed import seed_database


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
def operator_token(client):
    res = client.post("/api/auth/login", json={"username": "operator", "password": "Operator@1234"})
    assert res.status_code == 200
    return res.get_json()["token"]


# ==============================================================================
# Tier 1: What-If Simulation, Comparison, and PDF Reports
# ==============================================================================

def test_what_if_simulation_counterfactual(client):
    """Verify What-If simulation computes simulated prediction and score delta without mutating data."""
    shipment = Shipment.query.filter_by(status="Completed").first()
    assert shipment is not None

    payload = {
        "shipment_id": shipment.id,
        "avg_temp": 16.5,
        "max_temp": 24.0,
        "avg_humidity": 75.0,
        "temp_exposure_hours": 5.0,
        "humidity_exposure_hours": 3.0,
        "journey_duration_hours": 10.0,
        "violation_count": 8,
    }
    res = client.post("/api/simulator/what-if", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    assert "original_prediction" in data
    assert "simulated_prediction" in data
    assert "score_difference" in data
    assert "shift_factors" in data

    orig_score = data["original_prediction"]["risk_score"]
    sim_score = data["simulated_prediction"]["risk_score"]
    assert round(sim_score - orig_score, 2) == data["score_difference"]
    assert len(data["shift_factors"]) > 0


def test_what_if_scenario_persistence(client, operator_token):
    """Verify providing a scenario name saves the counterfactual run to the database."""
    shipment = Shipment.query.filter_by(status="Completed").first()
    assert shipment is not None

    scenario_name = "Heatwave Mitigation Analysis"
    payload = {
        "shipment_id": shipment.id,
        "name": scenario_name,
        "avg_temp": 14.0,
        "max_temp": 20.0,
        "temp_exposure_hours": 4.0,
        "violation_count": 5,
    }
    res = client.post(
        "/api/simulator/what-if",
        headers={"Authorization": f"Bearer {operator_token}"},
        json=payload,
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["saved_scenario_id"] is not None

    # Verify scenario exists in database
    scen = db.session.get(SimulationScenario, data["saved_scenario_id"])
    assert scen is not None
    assert scen.name == scenario_name
    assert scen.shipment_id == shipment.id

    # Verify scenario is returned in scenarios list endpoint
    list_res = client.get(f"/api/simulator/scenarios/{shipment.id}")
    assert list_res.status_code == 200
    scenarios = list_res.get_json()["scenarios"]
    assert any(s["name"] == scenario_name for s in scenarios)


def test_compare_shipments_side_by_side(client):
    """Verify comparing two completed shipments returns side-by-side metrics and safest selection."""
    shipments = Shipment.query.filter_by(status="Completed").limit(2).all()
    assert len(shipments) >= 2
    ids = [s.id for s in shipments]

    res = client.post("/api/compare", json={"shipment_ids": ids})
    assert res.status_code == 200
    data = res.get_json()

    assert len(data["shipments"]) == 2
    assert "same_category" in data
    assert "safest_shipment" in data
    assert data["safest_shipment"]["shipment_id"] in ids


def test_download_pdf_report_success(client):
    """Verify PDF generation endpoint returns valid PDF document headers and binary payload."""
    shipment = Shipment.query.filter_by(status="Completed").first()
    assert shipment is not None

    res = client.get(f"/api/reports/{shipment.id}/pdf")
    assert res.status_code == 200
    assert res.headers["Content-Type"] == "application/pdf"
    assert res.headers["Content-Disposition"].startswith("attachment;")
    assert len(res.data) > 1000
    # PDF magic header %PDF
    assert res.data[:4] == b"%PDF"


# ==============================================================================
# Tier 2: Boundary & Corner Cases / Isolation and Clamping
# ==============================================================================

def test_what_if_isolation_never_mutates_database_telemetry(client):
    """Integrity Check: Confirm What-If simulation NEVER mutates actual shipment or sensor readings."""
    shipment = Shipment.query.filter_by(status="Completed").first()
    assert shipment is not None

    # Snapshot baseline state
    baseline_reading_count = shipment.readings.count()
    baseline_alert_count = shipment.alerts.count()
    baseline_status = shipment.status
    baseline_progress = shipment.sim_progress
    baseline_readings_data = [(r.id, r.temperature, r.humidity) for r in shipment.readings.all()]

    # Run radical What-If simulation with extreme counterfactuals
    extreme_payload = {
        "shipment_id": shipment.id,
        "avg_temp": 45.0,
        "max_temp": 55.0,
        "avg_humidity": 95.0,
        "temp_exposure_hours": 12.0,
        "humidity_exposure_hours": 10.0,
        "journey_duration_hours": 12.0,
        "violation_count": 40,
    }
    res = client.post("/api/simulator/what-if", json=extreme_payload)
    assert res.status_code == 200

    # Refresh shipment from database
    db.session.refresh(shipment)

    # Verify zero database mutation
    assert shipment.readings.count() == baseline_reading_count
    assert shipment.alerts.count() == baseline_alert_count
    assert shipment.status == baseline_status
    assert shipment.sim_progress == baseline_progress

    current_readings_data = [(r.id, r.temperature, r.humidity) for r in shipment.readings.all()]
    assert current_readings_data == baseline_readings_data


def test_what_if_parameter_bounds_clamping(client):
    """Verify What-If clamps illogical inputs: max_temp < avg_temp, exposure > duration."""
    shipment = Shipment.query.first()
    assert shipment is not None

    # Case 1: max_temp < avg_temp -> should be clamped to avg_temp
    # Case 2: temp_exposure_hours > journey_duration_hours -> clamped to journey_duration_hours
    # Case 3: humidity_exposure_hours > journey_duration_hours -> clamped to journey_duration_hours
    payload = {
        "shipment_id": shipment.id,
        "avg_temp": 18.0,
        "max_temp": 12.0,  # Below average!
        "journey_duration_hours": 5.0,
        "temp_exposure_hours": 10.0,  # Longer than journey duration!
        "humidity_exposure_hours": 8.0,  # Longer than journey duration!
    }
    res = client.post("/api/simulator/what-if", json=payload)
    assert res.status_code == 200
    mod = res.get_json()["modified_features"]

    assert mod["max_temp"] == mod["avg_temp"] == 18.0
    assert mod["temp_exposure_hours"] == mod["journey_duration_hours"] == 5.0
    assert mod["humidity_exposure_hours"] == mod["journey_duration_hours"] == 5.0


def test_cross_category_comparison_warning(client):
    """Verify comparing shipments from different categories emits explicit warning and same_category=False."""
    dairy_shipment = Shipment.query.join(ProductProfile).filter(ProductProfile.category == "dairy").first()
    pharma_shipment = Shipment.query.join(ProductProfile).filter(ProductProfile.category == "pharmaceutical").first()
    assert dairy_shipment is not None and pharma_shipment is not None

    res = client.post("/api/compare", json={"shipment_ids": [dairy_shipment.id, pharma_shipment.id]})
    assert res.status_code == 200
    data = res.get_json()

    assert data["same_category"] is False
    assert data["category_warning"] is not None
    assert "different product categories" in data["category_warning"]


def test_same_category_comparison_no_warning(client):
    """Verify comparing shipments of the same category has same_category=True and no warning."""
    profile = ProductProfile.query.filter_by(category="dairy").first()
    t = utcnow()
    # Create two dairy shipments
    s1 = Shipment(
        shipment_code="SHP-CMP-DAIRY-1",
        product_name="Dairy Batch 1",
        product_profile_id=profile.id,
        source_location="City A",
        source_lat=20.0,
        source_lon=70.0,
        destination_location="City B",
        destination_lat=22.0,
        destination_lon=72.0,
        start_time=t,
        expected_delivery_time=t + timedelta(hours=6),
        transport_type="Refrigerated Truck",
        status="Completed",
    )
    s2 = Shipment(
        shipment_code="SHP-CMP-DAIRY-2",
        product_name="Dairy Batch 2",
        product_profile_id=profile.id,
        source_location="City A",
        source_lat=20.0,
        source_lon=70.0,
        destination_location="City B",
        destination_lat=22.0,
        destination_lon=72.0,
        start_time=t,
        expected_delivery_time=t + timedelta(hours=6),
        transport_type="Refrigerated Truck",
        status="Completed",
    )
    db.session.add_all([s1, s2])
    db.session.commit()

    res = client.post("/api/compare", json={"shipment_ids": [s1.id, s2.id]})
    assert res.status_code == 200
    data = res.get_json()

    assert data["same_category"] is True
    assert data["category_warning"] is None


def test_compare_minimum_two_shipments_validation(client):
    """Verify comparison requires at least 2 shipment IDs."""
    # Empty list
    res_empty = client.post("/api/compare", json={"shipment_ids": []})
    assert res_empty.status_code == 400

    # Only 1 shipment
    res_one = client.post("/api/compare", json={"shipment_ids": [1]})
    assert res_one.status_code == 400
    assert "at least 2 shipment IDs" in res_one.get_json()["error"]


def test_compare_nonexistent_shipment_returns_404(client):
    """Verify comparison with missing shipment ID returns 404."""
    res = client.post("/api/compare", json={"shipment_ids": [1, 999999]})
    assert res.status_code == 404
    assert "not found" in res.get_json()["error"].lower()


def test_pdf_generation_with_zero_readings(client):
    """Verify PDF generates cleanly without crashing when a shipment has zero telemetry readings."""
    profile = ProductProfile.query.first()
    t = utcnow()
    empty_shipment = Shipment(
        shipment_code="SHP-PDF-EMPTY",
        product_name="Pristine Empty Milk",
        product_profile_id=profile.id,
        source_location="City A",
        source_lat=20.0,
        source_lon=70.0,
        destination_location="City B",
        destination_lat=22.0,
        destination_lon=72.0,
        start_time=t,
        expected_delivery_time=t + timedelta(hours=6),
        transport_type="Refrigerated Truck",
        status="Pending",
    )
    db.session.add(empty_shipment)
    db.session.commit()

    res = client.get(f"/api/reports/{empty_shipment.id}/pdf")
    assert res.status_code == 200
    assert res.headers["Content-Type"] == "application/pdf"
    assert len(res.data) > 1000


def test_pdf_generation_with_many_alerts(client):
    """Verify PDF generates cleanly and formats alerts table when shipment has 15+ alerts."""
    profile = ProductProfile.query.first()
    t = utcnow()
    shipment = Shipment(
        shipment_code="SHP-PDF-MANY-ALERTS",
        product_name="Troubled Transport",
        product_profile_id=profile.id,
        source_location="City A",
        source_lat=20.0,
        source_lon=70.0,
        destination_location="City B",
        destination_lat=22.0,
        destination_lon=72.0,
        start_time=t,
        expected_delivery_time=t + timedelta(hours=12),
        transport_type="Refrigerated Truck",
        status="Completed",
    )
    db.session.add(shipment)
    db.session.commit()

    # Seed 16 alerts
    alerts = []
    severities = ["Low", "Medium", "High", "Critical"]
    for i in range(16):
        a = ExposureAlert(
            alert_code=f"ALT-HEAVY-{i:04d}",
            shipment_id=shipment.id,
            alert_type="TEMPERATURE_HIGH" if i % 2 == 0 else "HUMIDITY_HIGH",
            severity=severities[i % 4],
            recorded_value=12.0 + i,
            threshold_value=8.0,
            exposure_duration_minutes=30.0 + (i * 10),
            started_at=t + timedelta(minutes=20 * i),
            timestamp=t + timedelta(minutes=20 * i + 30),
            description=f"Automated test incident #{i}",
            is_active=False,
        )
        alerts.append(a)
    db.session.add_all(alerts)
    db.session.commit()

    res = client.get(f"/api/reports/{shipment.id}/pdf")
    assert res.status_code == 200
    assert res.headers["Content-Type"] == "application/pdf"
    assert len(res.data) > 1500


def test_what_if_missing_shipment_id_returns_400(client):
    """Verify What-If returns 400 when shipment_id is missing from request body."""
    res = client.post("/api/simulator/what-if", json={"avg_temp": 12.0})
    assert res.status_code == 400
    assert "shipment_id is required" in res.get_json()["error"]


def test_what_if_nonexistent_shipment_returns_404(client):
    """Verify What-If returns 404 when shipment_id does not exist."""
    res = client.post("/api/simulator/what-if", json={"shipment_id": 999999})
    assert res.status_code == 404
    assert "Shipment not found" in res.get_json()["error"]


def test_what_if_unseeded_shipment_uses_profile_defaults(client):
    """Verify What-If on a shipment with 0 telemetry gracefully uses product profile midpoints as baseline."""
    profile = ProductProfile.query.filter_by(category="dairy").first()
    t = utcnow()
    empty_shipment = Shipment(
        shipment_code="SHP-WHATIF-DEFAULTS",
        product_name="Default Baseline Milk",
        product_profile_id=profile.id,
        source_location="City A",
        source_lat=20.0,
        source_lon=70.0,
        destination_location="City B",
        destination_lat=22.0,
        destination_lon=72.0,
        start_time=t,
        expected_delivery_time=t + timedelta(hours=6),
        transport_type="Refrigerated Truck",
        status="Pending",
    )
    db.session.add(empty_shipment)
    db.session.commit()

    res = client.post("/api/simulator/what-if", json={"shipment_id": empty_shipment.id, "avg_temp": 10.0})
    assert res.status_code == 200
    data = res.get_json()
    assert data["original_features"]["avg_temp"] == (profile.min_temp + profile.max_temp) / 2.0
    assert data["simulated_prediction"]["risk_score"] >= 0.0


def test_compare_with_four_shipments_fleet(client):
    """Verify comparing 4 shipments across multiple routes returns all items and single safest journey."""
    shipments = Shipment.query.limit(4).all()
    assert len(shipments) == 4
    ids = [s.id for s in shipments]

    res = client.post("/api/compare", json={"shipment_ids": ids})
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["shipments"]) == 4
    assert data["safest_shipment"]["shipment_id"] in ids


def test_pdf_report_nonexistent_shipment_returns_404(client):
    """Verify requesting PDF report for a missing shipment returns 404."""
    res = client.get("/api/reports/999999/pdf")
    assert res.status_code == 404
    assert "Shipment not found" in res.get_json()["error"]

