"""Authentication endpoints: register, login, current user, logout."""
from flask import Blueprint, g, jsonify

from ..auth import get_current_user, issue_token, login_required
from ..extensions import db
from ..models import User, utcnow
from ..utils import ApiError, error_response, get_json, parse_choice, parse_str

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.errorhandler(ApiError)
def _handle_api_error(err):
    return error_response(err)


@auth_bp.post("/register")
def register():
    data = get_json()
    username = parse_str(data, "username", required=True, max_len=64).lower()
    email = parse_str(data, "email", required=True, max_len=120).lower()
    password = parse_str(data, "password", required=True, max_len=128)
    full_name = parse_str(data, "full_name", required=False, max_len=120, default="")
    role = parse_choice(data, "role", choices=User.ROLES, required=False, default="operator")

    if role == "admin":
        requester = get_current_user()
        if not requester or getattr(g.current_user, "role", None) != "admin":
            raise ApiError("Only administrators can register admin accounts.", 403)

    if len(password) < 6:
        raise ApiError("Password must be at least 6 characters.", 400, {"password": "Too short"})

    if User.query.filter_by(username=username).first():
        raise ApiError("Username is already taken.", 409, {"username": "Already in use"})
    if User.query.filter_by(email=email).first():
        raise ApiError("Email is already registered.", 409, {"email": "Already registered"})

    user = User(
        username=username,
        email=email,
        full_name=full_name or username.capitalize(),
        role=role,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = issue_token(user)
    return jsonify({"message": "Registration successful", "token": token, "user": user.to_dict()}), 201


@auth_bp.post("/login")
def login():
    data = get_json()
    username = parse_str(data, "username", required=True, max_len=64).lower()
    password = parse_str(data, "password", required=True, max_len=128)

    user = User.query.filter((User.username == username) | (User.email == username)).first()
    if not user or not user.check_password(password):
        raise ApiError("Invalid username or password.", 401)

    if not user.is_active:
        raise ApiError("Account has been deactivated.", 403)

    user.last_login_at = utcnow()
    db.session.commit()

    token = issue_token(user)
    return jsonify({"message": "Login successful", "token": token, "user": user.to_dict()}), 200


@auth_bp.get("/me")
@login_required
def me():
    return jsonify({"user": g.current_user.to_dict()})


@auth_bp.post("/logout")
@login_required
def logout():
    # Invalidate existing tokens by bumping token_version
    g.current_user.token_version += 1
    db.session.commit()
    return jsonify({"message": "Logged out successfully"})

