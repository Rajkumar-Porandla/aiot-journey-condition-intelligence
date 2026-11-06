"""Application configuration.

All secrets and environment-specific values are read from environment
variables (optionally loaded from ``backend/.env``). Nothing secret is
hard-coded in source control.
"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BACKEND_DIR / "instance"
ML_DIR = BACKEND_DIR / "ml"

load_dotenv(BACKEND_DIR / ".env")


def _load_or_create_secret_key() -> str:
    """Return SECRET_KEY from the environment, or a locally persisted random key.

    For a local student project it is convenient not to require manual setup,
    but the key must never live in source code. If ``SECRET_KEY`` is not set we
    generate a random key once and store it in ``instance/.secret_key`` (which
    is git-ignored) so that login tokens survive restarts.
    """
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    key_file = INSTANCE_DIR / ".secret_key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_hex(32)
    key_file.write_text(key)
    try:
        key_file.chmod(0o600)
    except OSError:
        pass
    return key


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    SECRET_KEY = _load_or_create_secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{INSTANCE_DIR / 'aiot_journey.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 30}}

    # Authentication token lifetime (hours)
    TOKEN_MAX_AGE_HOURS = _int_env("TOKEN_MAX_AGE_HOURS", 12)

    # CORS (only needed when the frontend is not served through the Vite proxy)
    CORS_ORIGINS = [
        o.strip()
        for o in os.environ.get(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if o.strip()
    ]

    # Sensor simulator defaults (can be overridden per journey)
    SIM_DEFAULT_INTERVAL_SECONDS = _int_env("SIM_DEFAULT_INTERVAL_SECONDS", 2)
    SIM_DEFAULT_STEP_MINUTES = _int_env("SIM_DEFAULT_STEP_MINUTES", 15)
    SIM_PREDICT_EVERY_N_READINGS = _int_env("SIM_PREDICT_EVERY_N_READINGS", 12)
    # Start the background simulator thread with the app (disabled in tests)
    SIM_ENGINE_ENABLED = os.environ.get("SIM_ENGINE_ENABLED", "1") == "1"

    MODEL_DIR = Path(os.environ.get("MODEL_DIR", str(ML_DIR / "models")))

    TESTING = False


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SIM_ENGINE_ENABLED = False

