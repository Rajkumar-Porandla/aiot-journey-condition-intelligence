"""Token-based authentication helpers.

Tokens are signed with ``SECRET_KEY`` using itsdangerous (bundled with Flask)
and carry the user id plus a ``token_version``. Logging out increments the
user's ``token_version`` which immediately revokes every token issued before.
"""
from functools import wraps

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .extensions import db
from .models import User

_SALT = "aiot-journey-auth"


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_SALT)


def issue_token(user: User) -> str:
    return _serializer().dumps({"uid": user.id, "tv": user.token_version})


def _user_from_request():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, "Authentication required."
    token = header[7:].strip()
    max_age = current_app.config["TOKEN_MAX_AGE_HOURS"] * 3600
    try:
        payload = _serializer().loads(token, max_age=max_age)
    except SignatureExpired:
        return None, "Session expired. Please log in again."
    except BadSignature:
        return None, "Invalid authentication token."
    user = db.session.get(User, payload.get("uid"))
    if user is None or not user.is_active or user.token_version != payload.get("tv"):
        return None, "Session is no longer valid. Please log in again."
    return user, None


def get_current_user():
    """Retrieve user from Authorization header for the current request."""
    user, _ = _user_from_request()
    g.current_user = user
    return user


user_from_request = _user_from_request


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user, err = _user_from_request()
        if user is None:
            return jsonify({"error": err}), 401
        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if g.current_user.role != "admin":
            return jsonify({"error": "Administrator role required."}), 403
        return fn(*args, **kwargs)

    return wrapper

