"""Tier 1 and Tier 2 Whitebox & API Tests for Authentication and RBAC Controls.

Features Covered:
- Feature 1: User Authentication & Session Lifecycle (Register, login, me, logout token revocation).
- Feature 2: RBAC Security Enforcement (Admin vs Operator permissions, role escalation defense).
"""
import pytest
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import ProductProfile, Shipment, User
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
def admin_token(client):
    """Authenticate default admin and yield valid bearer token."""
    res = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@1234"})
    assert res.status_code == 200, res.get_json()
    return res.get_json()["token"]


@pytest.fixture
def operator_token(client):
    """Authenticate default operator and yield valid bearer token."""
    res = client.post("/api/auth/login", json={"username": "operator", "password": "Operator@1234"})
    assert res.status_code == 200, res.get_json()
    return res.get_json()["token"]


# ==============================================================================
# Tier 1: User Authentication & Session Lifecycle Tests
# ==============================================================================

def test_user_registration_success(client):
    """Verify new user registration with operator role."""
    payload = {
        "username": "new_driver",
        "email": "driver@aiot-journey.local",
        "password": "SecurePassword123",
        "full_name": "Fleet Driver One",
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert "token" in data
    assert data["user"]["username"] == "new_driver"
    assert data["user"]["email"] == "driver@aiot-journey.local"
    assert data["user"]["role"] == "operator"
    assert data["user"]["is_active"] is True

    # Verify user exists in database
    user = User.query.filter_by(username="new_driver").first()
    assert user is not None
    assert user.check_password("SecurePassword123") is True


def test_user_login_with_username_success(client):
    """Verify login with valid username and password."""
    res = client.post("/api/auth/login", json={"username": "operator", "password": "Operator@1234"})
    assert res.status_code == 200
    data = res.get_json()
    assert "token" in data
    assert data["user"]["username"] == "operator"
    assert data["user"]["role"] == "operator"


def test_user_login_with_email_success(client):
    """Verify login using email address as the username field."""
    res = client.post("/api/auth/login", json={"username": "admin@aiot-journey.local", "password": "Admin@1234"})
    assert res.status_code == 200
    data = res.get_json()
    assert "token" in data
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"


def test_get_current_user_me(client, operator_token):
    """Verify /api/auth/me returns current authenticated user profile."""
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {operator_token}"})
    assert res.status_code == 200
    data = res.get_json()
    assert "user" in data
    assert data["user"]["username"] == "operator"
    assert data["user"]["role"] == "operator"
    assert "password_hash" not in data["user"]


def test_logout_token_invalidation(client, operator_token):
    """Verify logging out invalidates the issued bearer token immediately."""
    headers = {"Authorization": f"Bearer {operator_token}"}

    # Verify token works before logout
    check_before = client.get("/api/auth/me", headers=headers)
    assert check_before.status_code == 200

    # Execute logout
    logout_res = client.post("/api/auth/logout", headers=headers)
    assert logout_res.status_code == 200
    assert "Logged out successfully" in logout_res.get_json()["message"]

    # Verify the same token is now rejected with 401
    check_after = client.get("/api/auth/me", headers=headers)
    assert check_after.status_code == 401
    assert "Session is no longer valid" in check_after.get_json()["error"]


# ==============================================================================
# Tier 2: Boundary & Corner Cases / RBAC Controls
# ==============================================================================

def test_login_invalid_password_returns_401(client):
    """Verify login with wrong password returns 401."""
    res = client.post("/api/auth/login", json={"username": "admin", "password": "WrongPassword999"})
    assert res.status_code == 401
    assert "Invalid username or password" in res.get_json()["error"]


def test_login_nonexistent_username_returns_401(client):
    """Verify login with unknown username returns 401."""
    res = client.post("/api/auth/login", json={"username": "nonexistent_ghost", "password": "SomePassword123"})
    assert res.status_code == 401
    assert "Invalid username or password" in res.get_json()["error"]


def test_register_duplicate_username_returns_409(client):
    """Verify registering an existing username is rejected with 409 conflict."""
    res = client.post(
        "/api/auth/register",
        json={
            "username": "admin",
            "email": "different_admin@example.com",
            "password": "Password1234",
        },
    )
    assert res.status_code == 409
    assert "already taken" in res.get_json()["error"].lower()


def test_register_duplicate_email_returns_409(client):
    """Verify registering an existing email is rejected with 409 conflict."""
    res = client.post(
        "/api/auth/register",
        json={
            "username": "brand_new_user",
            "email": "admin@aiot-journey.local",
            "password": "Password1234",
        },
    )
    assert res.status_code == 409
    assert "already registered" in res.get_json()["error"].lower()


def test_register_password_minimum_length_boundary(client):
    """Verify passwords shorter than 6 characters are rejected with 400."""
    # 5 characters: below boundary
    res_short = client.post(
        "/api/auth/register",
        json={
            "username": "short_pw_user",
            "email": "short@example.com",
            "password": "12345",
        },
    )
    assert res_short.status_code == 400
    assert "at least 6 characters" in res_short.get_json()["error"]

    # 6 characters: on boundary (valid)
    res_valid = client.post(
        "/api/auth/register",
        json={
            "username": "boundary_user",
            "email": "boundary@example.com",
            "password": "123456",
        },
    )
    assert res_valid.status_code == 201


def test_role_escalation_attempt_anonymous_rejected(client):
    """Verify unauthenticated user attempting to register role 'admin' is rejected with 403."""
    res = client.post(
        "/api/auth/register",
        json={
            "username": "attacker",
            "email": "attacker@example.com",
            "password": "AttackPassword123",
            "role": "admin",
        },
    )
    assert res.status_code == 403
    assert "administrators" in res.get_json()["error"].lower()


def test_role_escalation_attempt_by_operator_rejected(client, operator_token):
    """Verify operator cannot register an admin account."""
    res = client.post(
        "/api/auth/register",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={
            "username": "escalated_user",
            "email": "escalated@example.com",
            "password": "Password1234",
            "role": "admin",
        },
    )
    assert res.status_code == 403
    assert "administrators" in res.get_json()["error"].lower()


def test_admin_can_register_new_admin(client, admin_token):
    """Verify authenticated administrator can register a new admin account."""
    res = client.post(
        "/api/auth/register",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "username": "secondary_admin",
            "email": "admin2@aiot-journey.local",
            "password": "AdminPassword123",
            "role": "admin",
        },
    )
    assert res.status_code == 201
    assert res.get_json()["user"]["role"] == "admin"


def test_operator_forbidden_from_deleting_shipment(client, operator_token):
    """Verify operator role receives 403 when attempting to delete a shipment."""
    shipment = Shipment.query.filter_by(status="Completed").first()
    assert shipment is not None

    res = client.delete(
        f"/api/shipments/{shipment.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert res.status_code == 403
    assert "Administrator role required" in res.get_json()["error"]


def test_operator_forbidden_from_creating_product_profile(client, operator_token):
    """Verify operator role receives 403 when attempting to create a product profile."""
    profile_payload = {
        "name": "Forbidden Chocolate",
        "category": "dairy",
        "min_temp": 12.0,
        "max_temp": 18.0,
        "min_humidity": 40.0,
        "max_humidity": 65.0,
        "sensitivity": "Medium",
    }
    res = client.post(
        "/api/products",
        headers={"Authorization": f"Bearer {operator_token}"},
        json=profile_payload,
    )
    assert res.status_code == 403
    assert "Administrator role required" in res.get_json()["error"]


def test_operator_forbidden_from_updating_product_profile(client, operator_token):
    """Verify operator role receives 403 when attempting to update a product profile."""
    profile = ProductProfile.query.first()
    assert profile is not None

    res = client.put(
        f"/api/products/{profile.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"name": "Hacked Profile Name"},
    )
    assert res.status_code == 403
    assert "Administrator role required" in res.get_json()["error"]


def test_admin_allowed_to_create_product_profile(client, admin_token):
    """Verify administrator successfully creates a new product profile."""
    profile_payload = {
        "name": "Artisanal Cheese Profile",
        "category": "dairy",
        "min_temp": 4.0,
        "max_temp": 8.0,
        "min_humidity": 75.0,
        "max_humidity": 85.0,
        "sensitivity": "High",
        "description": "Temperature-controlled artisanal cheese storage",
    }
    res = client.post(
        "/api/products",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=profile_payload,
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["product"]["name"] == "Artisanal Cheese Profile"
    assert data["product"]["min_temp"] == 4.0
    assert data["product"]["max_temp"] == 8.0


def test_admin_allowed_to_update_product_profile(client, admin_token):
    """Verify administrator successfully updates an existing product profile."""
    profile = ProductProfile.query.first()
    original_name = profile.name

    res = client.put(
        f"/api/products/{profile.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"description": "Updated by admin test"},
    )
    assert res.status_code == 200
    assert res.get_json()["product"]["description"] == "Updated by admin test"


def test_admin_allowed_to_delete_shipment(client, admin_token):
    """Verify administrator can delete a non-In Transit shipment."""
    shipment = Shipment.query.filter_by(status="Completed").first()
    assert shipment is not None
    shipment_id = shipment.id

    res = client.delete(
        f"/api/shipments/{shipment_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert "deleted successfully" in res.get_json()["message"]

    # Confirm deleted from database
    assert db.session.get(Shipment, shipment_id) is None


def test_cannot_delete_in_transit_shipment(client, admin_token):
    """Verify even an admin cannot delete an In Transit shipment without stopping it first."""
    in_transit_shipment = Shipment.query.filter_by(status="In Transit").first()
    assert in_transit_shipment is not None

    res = client.delete(
        f"/api/shipments/{in_transit_shipment.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400
    assert "Cannot delete an In Transit shipment" in res.get_json()["error"]


def test_unauthenticated_requests_rejected(client):
    """Verify protected endpoints return 401 when Authorization header is missing or malformed."""
    # Missing header
    res_missing = client.get("/api/auth/me")
    assert res_missing.status_code == 401
    assert "Authentication required" in res_missing.get_json()["error"]

    # Invalid token signature
    res_bad = client.get("/api/auth/me", headers={"Authorization": "Bearer forged.token.here"})
    assert res_bad.status_code == 401

    # Non-Bearer prefix
    res_basic = client.get("/api/auth/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert res_basic.status_code == 401


def test_deactivated_user_cannot_login(client):
    """Verify deactivated user cannot login and receives 403."""
    user = User(
        username="deactivated_user",
        email="inactive@example.com",
        password_hash="hash",
        role="operator",
        is_active=False,
    )
    user.set_password("ValidPassword123")
    db.session.add(user)
    db.session.commit()

    res = client.post("/api/auth/login", json={"username": "deactivated_user", "password": "ValidPassword123"})
    assert res.status_code == 403
    assert "deactivated" in res.get_json()["error"].lower()
