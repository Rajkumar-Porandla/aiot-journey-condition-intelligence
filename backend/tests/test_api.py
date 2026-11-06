"""Integration and unit tests for the entire AIoT backend."""
import json
import pytest
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import ProductProfile, Shipment, User
from app.services.seed import seed_database


@pytest.fixture
def client():
    app = create_app(config_class=TestConfig, start_engine=False)
    with app.app_context():
        db.create_all()
        seed_database()
        with app.test_client() as test_client:
            yield test_client
        db.session.remove()
        db.drop_all()


def test_auth_and_login(client):
    # Test valid login
    res = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@1234"})
    assert res.status_code == 200
    data = res.get_json()
    assert "token" in data
    assert data["user"]["role"] == "admin"
    token = data["token"]

    # Test me endpoint
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.get_json()["user"]["username"] == "admin"


def test_dashboard_stats(client):
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    data = res.get_json()
    assert data["summary"]["total_shipments"] >= 5
    assert "Low Risk" in data["risk_distribution"]


def test_product_profiles(client):
    res = client.get("/api/products")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["products"]) >= 5


def test_what_if_simulator(client):
    res = client.get("/api/shipments")
    shipment_id = res.get_json()["shipments"][0]["id"]

    what_if_payload = {
        "shipment_id": shipment_id,
        "avg_temp": 15.5,
        "max_temp": 24.0,
        "temp_exposure_hours": 6.5,
        "violation_count": 8,
    }
    sim_res = client.post("/api/simulator/what-if", json=what_if_payload)
    assert sim_res.status_code == 200
    sim_data = sim_res.get_json()
    assert "simulated_prediction" in sim_data
    assert "score_difference" in sim_data
    assert sim_data["simulated_prediction"]["risk_score"] >= 0


def test_compare_shipments(client):
    res = client.get("/api/shipments")
    shipments = res.get_json()["shipments"]
    ids = [shipments[0]["id"], shipments[1]["id"]]

    cmp_res = client.post("/api/compare", json={"shipment_ids": ids})
    assert cmp_res.status_code == 200
    cmp_data = cmp_res.get_json()
    assert len(cmp_data["shipments"]) == 2
    assert "safest_shipment" in cmp_data


def test_pdf_report_generation(client):
    res = client.get("/api/shipments")
    shipment_id = res.get_json()["shipments"][0]["id"]

    pdf_res = client.get(f"/api/reports/{shipment_id}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["Content-Type"] == "application/pdf"
    assert len(pdf_res.data) > 1000  # valid pdf bytes

