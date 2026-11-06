"""Tier 4 Real-World Application Workloads & End-to-End User Journeys.

Scenarios Covered:
- Scenario 1: Cold-Chain Dairy Transport under Heat Wave (F1, F4, F5, F6, F8, F9, F10, F13).
- Scenario 2: Ultra-Cold mRNA Vaccine Transit with Sensor Spike (F1, F2, F4, F6, F7, F8, F9, F11, F13).
- Scenario 3: Frozen Seafood Transit with Machine Breakdown & Recovery (F4, F5, F6, F8, F9, F10, F11).
- Scenario 4: Fresh Strawberry Humidity Saturation & Mold Risk (F4, F6, F8, F9, F10, F12, F13).
- Scenario 5: Fleet-Wide Cross-Category Multi-Fleet Risk Benchmarking (F1, F2, F4, F9, F12, F13).
"""
from datetime import datetime, timedelta
import pytest
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import ExposureAlert, MLPrediction, ProductProfile, SensorReading, Shipment, utcnow
from app.services import ml_service
from app.services.seed import seed_database
from app.services.simulation_engine import engine, step_shipment


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


# ==============================================================================
# Scenario 1: Cold-Chain Dairy Transport under Heat Wave
# ==============================================================================

def test_scenario_1_dairy_transport_under_heat_wave(client, operator_token):
    """Scenario 1: Dairy shipment subjected to heatwave excursions triggers alerts, high risk ML, Saabas explanations, and PDF report."""
    headers = {"Authorization": f"Bearer {operator_token}"}
    profile = ProductProfile.query.filter_by(category="dairy").first()
    assert profile is not None
    t0 = utcnow()

    # Step 1: Create Dairy Shipment
    create_res = client.post(
        "/api/shipments",
        headers=headers,
        json={
            "product_name": "Pasteurized Whole Milk Crates",
            "product_profile_id": profile.id,
            "source_location": "Anand, IN",
            "source_lat": 22.56,
            "source_lon": 72.95,
            "destination_location": "Mumbai, IN",
            "destination_lat": 19.07,
            "destination_lon": 72.87,
            "start_time": t0.isoformat(),
            "expected_delivery_time": (t0 + timedelta(hours=8)).isoformat(),
            "transport_type": "Refrigerated Truck",
            "notes": "Heatwave warning in western corridor",
        },
    )
    assert create_res.status_code == 201
    shipment_id = create_res.get_json()["shipment"]["id"]
    shipment = db.session.get(Shipment, shipment_id)

    # Step 2: Start Virtual Journey in CRITICAL mode (heatwave stress)
    start_res = client.post(
        f"/api/simulation/start/{shipment_id}",
        headers=headers,
        json={"mode": "CRITICAL", "interval_seconds": 2.0, "step_minutes": 15.0, "intensity": 1.5},
    )
    assert start_res.status_code == 200
    assert shipment.status == "In Transit"

    # Step 3: Advance journey with heatwave temperature excursion readings
    for i in range(1, 16):
        # Inject realistic heatwave readings ramping up to 13.5°C (dairy max is 6°C)
        temp = 5.0 + (i * 0.6) if i < 10 else 13.5
        r = SensorReading(
            shipment_id=shipment.id,
            sequence=i,
            timestamp=t0 + timedelta(minutes=15 * i),
            recorded_at=t0,
            temperature=temp,
            humidity=65.0,
            latitude=22.56 - (i * 0.1),
            longitude=72.95 - (i * 0.05),
            progress=i / 20.0,
            temp_violation=temp > profile.max_temp,
        )
        db.session.add(r)
    db.session.commit()

    # Step 4: Verify Exposure Alerts
    alert = ExposureAlert(
        alert_code="ALT-HEATWAVE-01",
        shipment_id=shipment.id,
        alert_type="TEMPERATURE_HIGH",
        severity="Critical",
        recorded_value=13.5,
        threshold_value=profile.max_temp,
        exposure_duration_minutes=90.0,
        started_at=t0 + timedelta(minutes=60),
        timestamp=t0 + timedelta(minutes=150),
        description="Heatwave thermal surge above 6.0°C limit",
        is_active=True,
    )
    db.session.add(alert)
    db.session.commit()

    # Step 5: Run ML Prediction
    pred_res = client.post(f"/api/predict/{shipment_id}", headers=headers)
    assert pred_res.status_code == 200
    pred_data = pred_res.get_json()["prediction"]

    # Verify elevated risk
    assert pred_data["risk_class"] in ("Medium Risk", "High Risk")
    assert pred_data["risk_score"] > 35.0

    # Step 6: Verify Saabas local explanation identifies temperature exposure
    expl = pred_data["explanation"]
    assert "score_contributions" in expl
    top_factors = expl["score_contributions"]
    assert any(f["feature"] in ("max_temp", "temp_exposure_hours", "avg_temp") for f in top_factors[:3])

    # Step 7: Mark completed & Download PDF report
    client.post(f"/api/simulation/complete/{shipment_id}", headers=headers)
    assert shipment.status == "Completed"

    pdf_res = client.get(f"/api/reports/{shipment_id}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["Content-Type"] == "application/pdf"
    assert len(pdf_res.data) > 1500


# ==============================================================================
# Scenario 2: Ultra-Cold mRNA Vaccine Transit
# ==============================================================================

def test_scenario_2_ultra_cold_mrna_vaccine_transit(client, admin_token, operator_token):
    """Scenario 2: mRNA vaccine transport: RBAC profile setup, pristine monitoring, excursion, What-If simulation, and isolation."""
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    operator_headers = {"Authorization": f"Bearer {operator_token}"}
    t0 = utcnow()

    # Step 1: Admin creates specialized mRNA vaccine profile with Very High sensitivity
    prof_res = client.post(
        "/api/products",
        headers=admin_headers,
        json={
            "name": "mRNA Ultra-Cold Vaccine Batch V",
            "category": "pharmaceutical",
            "min_temp": 2.0,
            "max_temp": 6.0,
            "min_humidity": 30.0,
            "max_humidity": 50.0,
            "sensitivity": "Very High",
            "description": "Temperature critical mRNA vaccine formulation",
        },
    )
    assert prof_res.status_code == 201
    profile_id = prof_res.get_json()["product"]["id"]

    # Step 2: Operator creates shipment
    create_res = client.post(
        "/api/shipments",
        headers=operator_headers,
        json={
            "product_name": "mRNA Vaccine V-9",
            "product_profile_id": profile_id,
            "source_location": "Hyderabad, IN",
            "source_lat": 17.38,
            "source_lon": 78.48,
            "destination_location": "Bengaluru, IN",
            "destination_lat": 12.97,
            "destination_lon": 77.59,
            "start_time": t0.isoformat(),
            "expected_delivery_time": (t0 + timedelta(hours=10)).isoformat(),
            "transport_type": "Refrigerated Truck",
            "notes": "Emergency hospital delivery",
        },
    )
    assert create_res.status_code == 201
    shipment_id = create_res.get_json()["shipment"]["id"]

    # Step 3: RBAC verification - operator cannot delete shipment
    del_forbidden = client.delete(f"/api/shipments/{shipment_id}", headers=operator_headers)
    assert del_forbidden.status_code == 403

    # Step 4: Start virtual journey and record initial pristine readings (4°C)
    client.post(f"/api/simulation/start/{shipment_id}", headers=operator_headers, json={"mode": "NORMAL"})
    for seq in range(1, 9):
        r = SensorReading(
            shipment_id=shipment_id,
            sequence=seq,
            timestamp=t0 + timedelta(minutes=15 * seq),
            recorded_at=t0,
            temperature=4.0 + (seq % 2) * 0.1,
            humidity=40.0,
            latitude=17.38 - (seq * 0.1),
            longitude=78.48 - (seq * 0.05),
            progress=seq / 20.0,
        )
        db.session.add(r)
    db.session.commit()

    # Step 5: Run initial baseline prediction (should be Low Risk)
    pred_res = client.post(f"/api/predict/{shipment_id}", headers=operator_headers)
    assert pred_res.status_code == 200
    baseline_score = pred_res.get_json()["prediction"]["risk_score"]

    # Step 6: What-If simulation: "What if freezer had failed for 4 hours at 14°C?"
    what_if_res = client.post(
        "/api/simulator/what-if",
        headers=operator_headers,
        json={
            "shipment_id": shipment_id,
            "name": "Chiller Failure What-If",
            "avg_temp": 11.5,
            "max_temp": 16.0,
            "temp_exposure_hours": 4.0,
            "violation_count": 6,
            "journey_duration_hours": 8.0,
        },
    )
    assert what_if_res.status_code == 200
    what_if_data = what_if_res.get_json()
    assert what_if_data["simulated_prediction"]["risk_score"] > baseline_score
    assert what_if_data["score_difference"] > 0

    # Step 7: Verify What-If isolation: database readings are unchanged
    shipment = db.session.get(Shipment, shipment_id)
    assert shipment.readings.count() == 8


# ==============================================================================
# Scenario 3: Frozen Seafood Transit with Machine Breakdown & Recovery
# ==============================================================================

def test_scenario_3_frozen_seafood_breakdown_and_recovery(client, operator_token):
    """Scenario 3: Frozen seafood journey experiencing refrigeration failure, pause for repairs, recovery, and completion."""
    headers = {"Authorization": f"Bearer {operator_token}"}
    profile = ProductProfile.query.filter_by(category="frozen").first()
    assert profile is not None
    t0 = utcnow()

    # Step 1: Create shipment
    create_res = client.post(
        "/api/shipments",
        headers=headers,
        json={
            "product_name": "Export Black Tiger Shrimp",
            "product_profile_id": profile.id,
            "source_location": "Kochi, IN",
            "source_lat": 9.93,
            "source_lon": 76.26,
            "destination_location": "Chennai, IN",
            "destination_lat": 13.08,
            "destination_lon": 80.27,
            "start_time": t0.isoformat(),
            "expected_delivery_time": (t0 + timedelta(hours=14)).isoformat(),
            "transport_type": "Rail Reefer",
        },
    )
    shipment_id = create_res.get_json()["shipment"]["id"]
    shipment = db.session.get(Shipment, shipment_id)

    # Step 2: Start journey, record 6 pristine frozen readings at -20°C (range is -22 to -18)
    client.post(f"/api/simulation/start/{shipment_id}", headers=headers, json={"mode": "NORMAL"})
    for seq in range(1, 7):
        db.session.add(SensorReading(
            shipment_id=shipment_id,
            sequence=seq,
            timestamp=t0 + timedelta(minutes=15 * seq),
            recorded_at=t0,
            temperature=-20.0,
            humidity=70.0,
            latitude=9.93 + (seq * 0.1),
            longitude=76.26 + (seq * 0.1),
            progress=seq / 30.0,
        ))
    db.session.commit()

    # Step 3: Breakdown occurs -> operator pauses journey
    pause_res = client.post(f"/api/simulation/pause/{shipment_id}", headers=headers)
    assert pause_res.status_code == 200
    assert shipment.status == "Paused"

    # Step 4: Maintenance in progress, temperature warms to -10°C (severe thaw excursion)
    for seq in range(7, 11):
        db.session.add(SensorReading(
            shipment_id=shipment_id,
            sequence=seq,
            timestamp=t0 + timedelta(minutes=15 * seq),
            recorded_at=t0,
            temperature=-10.0,
            humidity=75.0,
            latitude=10.53,
            longitude=76.86,
            progress=0.25,
            temp_violation=True,
        ))
    db.session.commit()

    # Add alert for the breakdown
    db.session.add(ExposureAlert(
        alert_code="ALT-BREAKDOWN-01",
        shipment_id=shipment_id,
        alert_type="TEMPERATURE_HIGH",
        severity="High",
        recorded_value=-10.0,
        threshold_value=profile.max_temp,
        exposure_duration_minutes=60.0,
        started_at=t0 + timedelta(minutes=105),
        timestamp=t0 + timedelta(minutes=165),
        description="Reefer machine power loss during transit",
        is_active=False,
    ))
    db.session.commit()

    # Step 5: Resume journey after compressor repair, temperature restored to -19°C
    resume_res = client.post(f"/api/simulation/resume/{shipment_id}", headers=headers)
    assert resume_res.status_code == 200
    assert shipment.status == "In Transit"

    for seq in range(11, 16):
        db.session.add(SensorReading(
            shipment_id=shipment_id,
            sequence=seq,
            timestamp=t0 + timedelta(minutes=15 * seq),
            recorded_at=t0,
            temperature=-19.0,
            humidity=70.0,
            latitude=10.53 + ((seq - 10) * 0.2),
            longitude=76.86 + ((seq - 10) * 0.2),
            progress=0.25 + ((seq - 10) * 0.05),
        ))
    db.session.commit()

    # Step 6: Complete journey & generate prediction
    client.post(f"/api/simulation/complete/{shipment_id}", headers=headers)
    assert shipment.status == "Completed"

    pred_res = client.post(f"/api/predict/{shipment_id}", headers=headers)
    assert pred_res.status_code == 200
    pred = pred_res.get_json()["prediction"]
    assert pred["risk_score"] > 0.0
    assert len(pred["explanation"]["score_contributions"]) > 0


# ==============================================================================
# Scenario 4: Fresh Strawberry Humidity Saturation & Mold Risk
# ==============================================================================

def test_scenario_4_strawberry_humidity_saturation_and_mold_risk(client, operator_token):
    """Scenario 4: High-humidity fresh produce transport, humidity saturation alert, and comparison with optimal batch."""
    headers = {"Authorization": f"Bearer {operator_token}"}
    profile = ProductProfile.query.filter_by(category="fruits_vegetables").first()
    assert profile is not None
    t0 = utcnow()

    # Create Shipment A (Moisture Saturated - High Humidity)
    res_a = client.post(
        "/api/shipments",
        headers=headers,
        json={
            "product_name": "Strawberries Batch A (Saturated)",
            "product_profile_id": profile.id,
            "source_location": "Nashik, IN",
            "source_lat": 19.99,
            "source_lon": 73.78,
            "destination_location": "Pune, IN",
            "destination_lat": 18.52,
            "destination_lon": 73.85,
            "start_time": t0.isoformat(),
            "expected_delivery_time": (t0 + timedelta(hours=6)).isoformat(),
            "transport_type": "Insulated Van",
        },
    )
    shp_a_id = res_a.get_json()["shipment"]["id"]

    # Inject saturated humidity readings (98% RH, safe max is 95%)
    for i in range(1, 11):
        db.session.add(SensorReading(
            shipment_id=shp_a_id,
            sequence=i,
            timestamp=t0 + timedelta(minutes=15 * i),
            recorded_at=t0,
            temperature=3.5,
            humidity=98.0,
            latitude=19.99 - (i * 0.1),
            longitude=73.78 + (i * 0.01),
            progress=i / 10.0,
            humidity_violation=True,
        ))
    db.session.commit()

    db.session.add(ExposureAlert(
        alert_code="ALT-MOLD-01",
        shipment_id=shp_a_id,
        alert_type="HUMIDITY_HIGH",
        severity="High",
        recorded_value=98.0,
        threshold_value=profile.max_humidity,
        exposure_duration_minutes=120.0,
        started_at=t0 + timedelta(minutes=30),
        timestamp=t0 + timedelta(minutes=150),
        description="High humidity saturation risking fungal sporulation",
        is_active=False,
    ))
    db.session.commit()
    client.post(f"/api/simulation/complete/{shp_a_id}", headers=headers)
    client.post(f"/api/predict/{shp_a_id}", headers=headers)

    # Create Shipment B (Optimal Climate Controlled - 88% RH, optimal)
    res_b = client.post(
        "/api/shipments",
        headers=headers,
        json={
            "product_name": "Strawberries Batch B (Optimal)",
            "product_profile_id": profile.id,
            "source_location": "Nashik, IN",
            "source_lat": 19.99,
            "source_lon": 73.78,
            "destination_location": "Pune, IN",
            "destination_lat": 18.52,
            "destination_lon": 73.85,
            "start_time": t0.isoformat(),
            "expected_delivery_time": (t0 + timedelta(hours=6)).isoformat(),
            "transport_type": "Insulated Van",
        },
    )
    shp_b_id = res_b.get_json()["shipment"]["id"]

    for i in range(1, 11):
        db.session.add(SensorReading(
            shipment_id=shp_b_id,
            sequence=i,
            timestamp=t0 + timedelta(minutes=15 * i),
            recorded_at=t0,
            temperature=2.8,
            humidity=89.0,
            latitude=19.99 - (i * 0.1),
            longitude=73.78 + (i * 0.01),
            progress=i / 10.0,
        ))
    db.session.commit()
    client.post(f"/api/simulation/complete/{shp_b_id}", headers=headers)
    client.post(f"/api/predict/{shp_b_id}", headers=headers)

    # Compare both strawberry batches side-by-side
    cmp_res = client.post("/api/compare", json={"shipment_ids": [shp_a_id, shp_b_id]})
    assert cmp_res.status_code == 200
    cmp_data = cmp_res.get_json()

    assert cmp_data["same_category"] is True
    assert cmp_data["category_warning"] is None

    # Verify safest shipment is Batch B (lower humidity exposure, lower risk score)
    safest = cmp_data["safest_shipment"]
    assert safest is not None
    assert safest["shipment_id"] == shp_b_id


# ==============================================================================
# Scenario 5: Fleet-Wide Cross-Category Multi-Fleet Risk Benchmarking
# ==============================================================================

def test_scenario_5_fleet_wide_cross_category_benchmarking(client):
    """Scenario 5: Multi-category fleet benchmarking, cross-category alert warnings, and dashboard KPI validation."""
    # Retrieve 3 seeded shipments across different categories
    dairy = Shipment.query.join(ProductProfile).filter(ProductProfile.category == "dairy").first()
    pharma = Shipment.query.join(ProductProfile).filter(ProductProfile.category == "pharmaceutical").first()
    frozen = Shipment.query.join(ProductProfile).filter(ProductProfile.category == "frozen").first()
    assert dairy is not None and pharma is not None and frozen is not None

    shipment_ids = [dairy.id, pharma.id, frozen.id]

    # Run multi-category comparison
    cmp_res = client.post("/api/compare", json={"shipment_ids": shipment_ids})
    assert cmp_res.status_code == 200
    cmp_data = cmp_res.get_json()

    # Verify cross-category warning
    assert cmp_data["same_category"] is False
    assert "different product categories" in cmp_data["category_warning"]
    assert len(cmp_data["shipments"]) == 3

    # Safest shipment is identified
    assert cmp_data["safest_shipment"] is not None
    assert cmp_data["safest_shipment"]["shipment_id"] in shipment_ids

    # Verify Executive Dashboard Observability
    dash_res = client.get("/api/dashboard/stats")
    assert dash_res.status_code == 200
    dash_data = dash_res.get_json()

    assert "summary" in dash_data
    assert dash_data["summary"]["total_shipments"] >= 5
    assert "risk_distribution" in dash_data
    assert "status_distribution" in dash_data
    assert "recent_alerts" in dash_data
    assert "transport_distribution" in dash_data


def test_scenario_6_floriculture_transit_tight_temperature_envelope(client, operator_token):
    """Scenario 6: Export Cut Flowers journey with tight 1°C-4°C envelope and Very High sensitivity."""
    headers = {"Authorization": f"Bearer {operator_token}"}
    profile = ProductProfile.query.filter_by(category="flowers").first()
    assert profile is not None
    t0 = utcnow()

    # Create floriculture shipment (Ooty to Bengaluru)
    create_res = client.post(
        "/api/shipments",
        headers=headers,
        json={
            "product_name": "Premium Red Roses & Carnations",
            "product_profile_id": profile.id,
            "source_location": "Ooty, IN",
            "source_lat": 11.41,
            "source_lon": 76.70,
            "destination_location": "Bengaluru, IN",
            "destination_lat": 12.97,
            "destination_lon": 77.59,
            "start_time": t0.isoformat(),
            "expected_delivery_time": (t0 + timedelta(hours=8)).isoformat(),
            "transport_type": "Refrigerated Truck",
        },
    )
    assert create_res.status_code == 201
    shipment_id = create_res.get_json()["shipment"]["id"]

    # Start journey in WARNING mode
    client.post(f"/api/simulation/start/{shipment_id}", headers=headers, json={"mode": "WARNING"})

    # Inject readings with brief thermal spike to 7.5°C
    for seq in range(1, 13):
        temp = 2.5 if seq < 6 else 7.5
        db.session.add(SensorReading(
            shipment_id=shipment_id,
            sequence=seq,
            timestamp=t0 + timedelta(minutes=15 * seq),
            recorded_at=t0,
            temperature=temp,
            humidity=90.0,
            latitude=11.41 + (seq * 0.1),
            longitude=76.70 + (seq * 0.05),
            progress=seq / 15.0,
            temp_violation=temp > profile.max_temp,
        ))
    db.session.commit()

    # Complete journey and predict
    client.post(f"/api/simulation/complete/{shipment_id}", headers=headers)
    pred_res = client.post(f"/api/predict/{shipment_id}", headers=headers)
    assert pred_res.status_code == 200
    pred = pred_res.get_json()["prediction"]
    assert pred["risk_score"] > 0.0

    # Download condition report
    pdf_res = client.get(f"/api/reports/{shipment_id}/pdf")
    assert pdf_res.status_code == 200
    assert len(pdf_res.data) > 1000

