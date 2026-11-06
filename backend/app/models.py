"""SQLAlchemy ORM models.

Tables
------
users, product_profiles, shipments, sensor_readings, exposure_alerts,
ml_predictions, simulation_scenarios
"""
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite has no timezone support)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    ROLES = ("admin", "operator")

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False, default="")
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="operator")
    # Incremented on logout / password change to revoke previously issued tokens
    token_version = db.Column(db.Integer, nullable=False, default=0)
    preferences = db.Column(db.JSON, nullable=False, default=dict)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "preferences": self.preferences or {},
            "created_at": iso(self.created_at),
            "last_login_at": iso(self.last_login_at),
        }


# --------------------------------------------------------------------------
# Product profiles
# --------------------------------------------------------------------------
class ProductProfile(db.Model):
    __tablename__ = "product_profiles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    category = db.Column(db.String(32), nullable=False, index=True)
    min_temp = db.Column(db.Float, nullable=False)
    max_temp = db.Column(db.Float, nullable=False)
    min_humidity = db.Column(db.Float, nullable=False)
    max_humidity = db.Column(db.Float, nullable=False)
    sensitivity = db.Column(db.String(16), nullable=False, default="Medium")
    description = db.Column(db.Text, nullable=False, default="")
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    shipments = db.relationship("Shipment", back_populates="product_profile")

    def to_dict(self):
        from .core.product_defaults import category_label

        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "category_label": category_label(self.category),
            "min_temp": self.min_temp,
            "max_temp": self.max_temp,
            "min_humidity": self.min_humidity,
            "max_humidity": self.max_humidity,
            "sensitivity": self.sensitivity,
            "description": self.description,
            "is_default": self.is_default,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
            "shipment_count": len(self.shipments),
        }

    def thresholds(self):
        return {
            "category": self.category,
            "min_temp": self.min_temp,
            "max_temp": self.max_temp,
            "min_humidity": self.min_humidity,
            "max_humidity": self.max_humidity,
            "sensitivity": self.sensitivity,
        }


# --------------------------------------------------------------------------
# Shipments
# --------------------------------------------------------------------------
class Shipment(db.Model):
    __tablename__ = "shipments"

    STATUSES = ("Pending", "In Transit", "Paused", "Stopped", "Completed")
    ACTIVE_STATUSES = ("In Transit", "Paused")
    TRANSPORT_TYPES = (
        "Refrigerated Truck",
        "Insulated Van",
        "Air Cargo",
        "Rail Reefer",
        "Sea Container",
    )
    SIM_MODES = ("NORMAL", "WARNING", "CRITICAL")

    id = db.Column(db.Integer, primary_key=True)
    shipment_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    product_name = db.Column(db.String(120), nullable=False)
    product_profile_id = db.Column(
        db.Integer, db.ForeignKey("product_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    source_location = db.Column(db.String(120), nullable=False)
    source_lat = db.Column(db.Float, nullable=False)
    source_lon = db.Column(db.Float, nullable=False)
    destination_location = db.Column(db.String(120), nullable=False)
    destination_lat = db.Column(db.Float, nullable=False)
    destination_lon = db.Column(db.Float, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    expected_delivery_time = db.Column(db.DateTime, nullable=False)
    actual_delivery_time = db.Column(db.DateTime)
    transport_type = db.Column(db.String(32), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="Pending", index=True)
    notes = db.Column(db.Text, nullable=False, default="")

    # ---- Virtual journey / simulator state (persisted so restarts can resume)
    sim_mode = db.Column(db.String(16))
    sim_interval_seconds = db.Column(db.Float)
    sim_step_minutes = db.Column(db.Float)
    sim_progress = db.Column(db.Float, nullable=False, default=0.0)
    sim_elapsed_minutes = db.Column(db.Float, nullable=False, default=0.0)
    sim_state = db.Column(db.JSON)
    sim_started_at = db.Column(db.DateTime)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    product_profile = db.relationship("ProductProfile", back_populates="shipments")
    created_by = db.relationship("User")
    readings = db.relationship(
        "SensorReading",
        back_populates="shipment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SensorReading.sequence",
        lazy="dynamic",
    )
    alerts = db.relationship(
        "ExposureAlert",
        back_populates="shipment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    predictions = db.relationship(
        "MLPrediction",
        back_populates="shipment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    scenarios = db.relationship(
        "SimulationScenario",
        back_populates="shipment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )

    @property
    def category(self):
        return self.product_profile.category if self.product_profile else None

    def latest_prediction(self):
        return self.predictions.order_by(MLPrediction.created_at.desc(), MLPrediction.id.desc()).first()

    def to_dict(self, include_latest=True):
        from .core.product_defaults import category_label

        data = {
            "id": self.id,
            "shipment_code": self.shipment_code,
            "product_name": self.product_name,
            "product_profile_id": self.product_profile_id,
            "product_profile": self.product_profile.name if self.product_profile else None,
            "category": self.category,
            "category_label": category_label(self.category),
            "source_location": self.source_location,
            "source_lat": self.source_lat,
            "source_lon": self.source_lon,
            "destination_location": self.destination_location,
            "destination_lat": self.destination_lat,
            "destination_lon": self.destination_lon,
            "start_time": iso(self.start_time),
            "expected_delivery_time": iso(self.expected_delivery_time),
            "actual_delivery_time": iso(self.actual_delivery_time),
            "transport_type": self.transport_type,
            "status": self.status,
            "notes": self.notes,
            "simulation": {
                "mode": self.sim_mode,
                "interval_seconds": self.sim_interval_seconds,
                "step_minutes": self.sim_step_minutes,
                "progress": round(self.sim_progress or 0.0, 4),
                "elapsed_minutes": round(self.sim_elapsed_minutes or 0.0, 1),
                "started_at": iso(self.sim_started_at),
                "is_delayed": bool((self.sim_state or {}).get("delay_remaining", 0) > 0),
            },
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if include_latest:
            pred = self.latest_prediction()
            data["latest_prediction"] = pred.to_summary() if pred else None
            data["reading_count"] = self.readings.count()
            data["alert_count"] = self.alerts.count()
        return data


# --------------------------------------------------------------------------
# Sensor readings (simulated IoT telemetry)
# --------------------------------------------------------------------------
class SensorReading(db.Model):
    __tablename__ = "sensor_readings"

    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(
        db.Integer, db.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence = db.Column(db.Integer, nullable=False)
    # Virtual journey clock (accelerated simulation time)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    # Wall-clock time at which the simulator generated the reading
    recorded_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    progress = db.Column(db.Float, nullable=False, default=0.0)
    is_delayed = db.Column(db.Boolean, nullable=False, default=False)
    temp_violation = db.Column(db.Boolean, nullable=False, default=False)
    humidity_violation = db.Column(db.Boolean, nullable=False, default=False)

    shipment = db.relationship("Shipment", back_populates="readings")

    __table_args__ = (db.UniqueConstraint("shipment_id", "sequence", name="uq_reading_seq"),)

    def to_dict(self):
        return {
            "id": self.id,
            "sequence": self.sequence,
            "timestamp": iso(self.timestamp),
            "recorded_at": iso(self.recorded_at),
            "temperature": self.temperature,
            "humidity": self.humidity,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "progress": self.progress,
            "is_delayed": self.is_delayed,
            "temp_violation": self.temp_violation,
            "humidity_violation": self.humidity_violation,
        }


# --------------------------------------------------------------------------
# Exposure alerts
# --------------------------------------------------------------------------
class ExposureAlert(db.Model):
    __tablename__ = "exposure_alerts"

    TYPES = ("TEMPERATURE_HIGH", "TEMPERATURE_LOW", "HUMIDITY_HIGH", "HUMIDITY_LOW")
    SEVERITIES = ("Low", "Medium", "High", "Critical")

    id = db.Column(db.Integer, primary_key=True)
    alert_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    shipment_id = db.Column(
        db.Integer, db.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alert_type = db.Column(db.String(32), nullable=False)
    severity = db.Column(db.String(16), nullable=False)
    recorded_value = db.Column(db.Float, nullable=False)  # peak value in the episode
    threshold_value = db.Column(db.Float, nullable=False)
    exposure_duration_minutes = db.Column(db.Float, nullable=False, default=0.0)
    started_at = db.Column(db.DateTime, nullable=False)  # journey clock
    timestamp = db.Column(db.DateTime, nullable=False, index=True)  # last update, journey clock
    description = db.Column(db.Text, nullable=False, default="")
    is_active = db.Column(db.Boolean, nullable=False, default=True)  # episode still ongoing
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    shipment = db.relationship("Shipment", back_populates="alerts")

    def to_dict(self):
        return {
            "id": self.id,
            "alert_code": self.alert_code,
            "shipment_id": self.shipment_id,
            "shipment_code": self.shipment.shipment_code if self.shipment else None,
            "product_name": self.shipment.product_name if self.shipment else None,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "recorded_value": round(self.recorded_value, 2),
            "threshold_value": self.threshold_value,
            "exposure_duration_minutes": round(self.exposure_duration_minutes, 1),
            "started_at": iso(self.started_at),
            "timestamp": iso(self.timestamp),
            "description": self.description,
            "is_active": self.is_active,
            "created_at": iso(self.created_at),
        }


# --------------------------------------------------------------------------
# ML predictions
# --------------------------------------------------------------------------
class MLPrediction(db.Model):
    __tablename__ = "ml_predictions"

    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(
        db.Integer, db.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    risk_class = db.Column(db.String(16), nullable=False)
    class_probabilities = db.Column(db.JSON, nullable=False)
    risk_score = db.Column(db.Float, nullable=False)
    features = db.Column(db.JSON, nullable=False)
    explanation = db.Column(db.JSON, nullable=False)
    model_version = db.Column(db.String(64), nullable=False)
    trigger = db.Column(db.String(16), nullable=False, default="manual")
    reading_count = db.Column(db.Integer, nullable=False, default=0)

    shipment = db.relationship("Shipment", back_populates="predictions")

    def to_summary(self):
        return {
            "id": self.id,
            "risk_class": self.risk_class,
            "risk_score": round(self.risk_score, 1),
            "created_at": iso(self.created_at),
        }

    def to_dict(self):
        return {
            "id": self.id,
            "shipment_id": self.shipment_id,
            "created_at": iso(self.created_at),
            "risk_class": self.risk_class,
            "class_probabilities": self.class_probabilities,
            "risk_score": round(self.risk_score, 2),
            "features": self.features,
            "explanation": self.explanation,
            "model_version": self.model_version,
            "trigger": self.trigger,
            "reading_count": self.reading_count,
        }


# --------------------------------------------------------------------------
# What-if simulation scenarios (never modify real shipment data)
# --------------------------------------------------------------------------
class SimulationScenario(db.Model):
    __tablename__ = "simulation_scenarios"

    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(
        db.Integer, db.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    name = db.Column(db.String(120), nullable=False)
    original_features = db.Column(db.JSON, nullable=False)
    modified_features = db.Column(db.JSON, nullable=False)
    original_prediction = db.Column(db.JSON, nullable=False)
    simulated_prediction = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    shipment = db.relationship("Shipment", back_populates="scenarios")
    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "shipment_id": self.shipment_id,
            "shipment_code": self.shipment.shipment_code if self.shipment else None,
            "name": self.name,
            "created_by": self.user.username if self.user else None,
            "original_features": self.original_features,
            "modified_features": self.modified_features,
            "original_prediction": self.original_prediction,
            "simulated_prediction": self.simulated_prediction,
            "created_at": iso(self.created_at),
        }

