"""Automatic IoT sensor simulator (background engine).

A single daemon thread wakes up every ``TICK_SECONDS`` and, for every shipment
whose status is ``In Transit``, generates a new reading when its configured
interval has elapsed. Each reading:

1. advances the shared sensor model (``app.core.sensor_model``),
2. is stored in ``sensor_readings`` with a virtual journey timestamp,
3. is passed through the exposure tracker to create / update alerts,
4. periodically triggers an ML risk prediction, and
5. completes the journey when the destination is reached.

Simulated time is accelerated: each reading advances the journey clock by
``sim_step_minutes`` while only ``sim_interval_seconds`` of real time pass.

All control actions (start / pause / resume / stop / complete) and steps run
under one lock so that the thread and API requests never interleave writes.
"""
import copy
import logging
import random
import threading
import time
import uuid
from datetime import datetime, timedelta

from ..core import sensor_model
from ..core.sensor_model import MODE_PARAMS
from ..core.exposure import ExposureTracker, violations_for
from ..extensions import db
from ..models import ExposureAlert, SensorReading, Shipment, utcnow
from . import ml_service
from .predictions import NoReadings, predict_and_store

log = logging.getLogger(__name__)

TICK_SECONDS = 0.5


class SimulationError(ValueError):
    """Invalid simulator control request (maps to HTTP 409 or specified status_code)."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        elif "Invalid simulation mode" in message or "mode" in message.lower():
            self.status_code = 400
        else:
            self.status_code = 409
        self.code = self.status_code


def _iso(dt):
    return dt.isoformat()


def _route(shipment):
    return {
        "source_lat": shipment.source_lat,
        "source_lon": shipment.source_lon,
        "destination_lat": shipment.destination_lat,
        "destination_lon": shipment.destination_lon,
    }


def expected_minutes(shipment):
    return max((shipment.expected_delivery_time - shipment.start_time).total_seconds() / 60.0, 1.0)


def new_alert_code():
    return f"ALT-{uuid.uuid4().hex[:8].upper()}"


def _apply_alert_events(shipment, events):
    for ev in events:
        ep = ev["episode"]
        if ev["action"] == "create":
            alert = ExposureAlert(
                alert_code=new_alert_code(),
                shipment_id=shipment.id,
                alert_type=ev["alert_type"],
                severity=ev["severity"],
                recorded_value=ev["recorded_value"],
                threshold_value=ev["threshold_value"],
                exposure_duration_minutes=ev["exposure_duration_minutes"],
                started_at=datetime.fromisoformat(ev["started_at"]),
                timestamp=datetime.fromisoformat(ev["timestamp"]),
                description=ev["description"],
                is_active=ev["is_active"],
            )
            db.session.add(alert)
            db.session.flush()
            ep["ref"] = alert.id
        else:
            alert = db.session.get(ExposureAlert, ep.get("ref")) if ep.get("ref") else None
            if alert is None:
                continue
            alert.severity = ev["severity"]
            alert.recorded_value = ev["recorded_value"]
            alert.exposure_duration_minutes = ev["exposure_duration_minutes"]
            alert.timestamp = datetime.fromisoformat(ev["timestamp"])
            alert.description = ev["description"]
            alert.is_active = ev["is_active"]


def _safe_predict(shipment, trigger):
    try:
        predict_and_store(shipment, trigger)
    except (ml_service.ModelUnavailable, NoReadings) as exc:
        log.info("Skipping %s prediction for %s: %s", trigger, shipment.shipment_code, exc)


def _close_episodes(shipment, state, ts):
    tracker = ExposureTracker(shipment.product_profile.thresholds(), state.get("exposure", {}))
    _apply_alert_events(shipment, tracker.close_all(_iso(ts)))
    state["exposure"] = tracker.state


def step_shipment(shipment, rng=None, predict_every=12):
    """Generate one simulated reading for ``shipment`` (caller commits)."""
    if shipment.sim_state is None:
        raise SimulationError("Journey has not been started.")
    rng = rng or random.Random()
    state = copy.deepcopy(shipment.sim_state)
    sensor = state["sensor"]
    profile = shipment.product_profile.thresholds()
    step = float(shipment.sim_step_minutes)

    r = sensor_model.next_reading(sensor, profile, _route(shipment), step, expected_minutes(shipment), rng)
    ts = shipment.start_time + timedelta(minutes=r["elapsed_minutes"])
    viol = violations_for(r["temperature"], r["humidity"], profile)
    reading = SensorReading(
        shipment_id=shipment.id,
        sequence=r["sequence"],
        timestamp=ts,
        recorded_at=utcnow(),
        temperature=r["temperature"],
        humidity=r["humidity"],
        latitude=r["latitude"],
        longitude=r["longitude"],
        progress=r["progress"],
        is_delayed=r["is_delayed"],
        temp_violation=any(k.startswith("TEMPERATURE") for k in viol),
        humidity_violation=any(k.startswith("HUMIDITY") for k in viol),
    )
    db.session.add(reading)

    tracker = ExposureTracker(profile, state.get("exposure", {}))
    events = tracker.process(
        {"temperature": r["temperature"], "humidity": r["humidity"], "timestamp": _iso(ts)}, step
    )
    _apply_alert_events(shipment, events)
    state["exposure"] = tracker.state

    shipment.sim_progress = r["progress"]
    shipment.sim_elapsed_minutes = r["elapsed_minutes"]

    completed = sensor_model.is_complete(sensor)
    if completed:
        _close_episodes(shipment, state, ts)
        shipment.status = "Completed"
        shipment.actual_delivery_time = ts
    shipment.sim_state = state
    db.session.flush()

    if completed:
        _safe_predict(shipment, "completion")
    elif predict_every and r["sequence"] % predict_every == 0:
        _safe_predict(shipment, "auto")
    return reading


class SimulationEngine:
    def __init__(self):
        self.lock = threading.RLock()
        self._thread = None
        self._stop = threading.Event()
        self._last_tick = {}
        self.app = None

    # ------------------------------------------------------------ lifecycle
    def start(self, app):
        if self._thread and self._thread.is_alive():
            return
        self.app = app
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="sensor-simulator", daemon=True)
        self._thread.start()
        log.info("Sensor simulation engine started")

    def shutdown(self):
        self._stop.set()

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())

    def _run(self):
        while not self._stop.is_set():
            try:
                with self.app.app_context():
                    self._tick()
            except Exception:  # keep the engine alive; log the root cause
                log.exception("Simulator tick failed")
            finally:
                time.sleep(TICK_SECONDS)

    def _tick(self):
        predict_every = self.app.config.get("SIM_PREDICT_EVERY_N_READINGS", 12)
        now = time.monotonic()
        try:
            with self.lock:
                ids = [s.id for s in Shipment.query.filter_by(status="In Transit").all()]
                for sid in ids:
                    shipment = db.session.get(Shipment, sid)
                    if shipment is None or shipment.status != "In Transit":
                        continue
                    interval = shipment.sim_interval_seconds or 2.0
                    last = self._last_tick.get(sid)
                    if last is not None and now - last < interval:
                        continue
                    self._last_tick[sid] = now
                    try:
                        step_shipment(shipment, predict_every=predict_every)
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        log.exception("Failed to simulate reading for shipment %s", sid)
        finally:
            db.session.remove()

    # ------------------------------------------------------------ controls
    def start_journey(self, shipment, mode, interval_seconds, step_minutes, intensity=1.0):
        with self.lock:
            db.session.refresh(shipment)  # the engine thread may have advanced it
            if shipment.status not in ("Pending", "Stopped"):
                raise SimulationError(
                    f"Cannot start a journey that is '{shipment.status}'. Only Pending or Stopped shipments can be started."
                )
            if mode not in Shipment.SIM_MODES or mode not in MODE_PARAMS:
                raise SimulationError(f"Invalid simulation mode: {mode}", 400)
            profile = shipment.product_profile.thresholds()
            if shipment.sim_state is None:
                state = {"sensor": sensor_model.initial_state(profile, mode, random.Random(), intensity), "exposure": {}}
                shipment.sim_started_at = utcnow()
            else:  # restart a stopped journey from where it halted, possibly with a new mode
                if mode not in Shipment.SIM_MODES or mode not in MODE_PARAMS:
                    raise SimulationError(f"Invalid simulation mode: {mode}", 400)
                state = copy.deepcopy(shipment.sim_state)
                state["sensor"]["mode"] = mode
                state["sensor"]["intensity"] = float(intensity)
            shipment.sim_state = state
            shipment.sim_mode = mode
            shipment.sim_interval_seconds = interval_seconds
            shipment.sim_step_minutes = step_minutes
            shipment.status = "In Transit"
            self._last_tick.pop(shipment.id, None)
            db.session.commit()

    def pause(self, shipment):
        with self.lock:
            db.session.refresh(shipment)  # the engine thread may have advanced it
            if shipment.status != "In Transit":
                raise SimulationError("Only an In Transit journey can be paused.")
            shipment.status = "Paused"
            db.session.commit()

    def resume(self, shipment):
        with self.lock:
            db.session.refresh(shipment)  # the engine thread may have advanced it
            if shipment.status != "Paused":
                raise SimulationError("Only a Paused journey can be resumed.")
            shipment.status = "In Transit"
            self._last_tick.pop(shipment.id, None)
            db.session.commit()

    def _finish(self, shipment, new_status, trigger):
        state = copy.deepcopy(shipment.sim_state or {"exposure": {}})
        ts = shipment.start_time + timedelta(minutes=shipment.sim_elapsed_minutes or 0)
        _close_episodes(shipment, state, ts)
        shipment.sim_state = state if shipment.sim_state is not None else None
        shipment.status = new_status
        if new_status == "Completed":
            shipment.actual_delivery_time = ts if shipment.readings.count() else utcnow()
        db.session.flush()
        _safe_predict(shipment, trigger)
        db.session.commit()

    def stop(self, shipment):
        with self.lock:
            db.session.refresh(shipment)  # the engine thread may have advanced it
            if shipment.status not in Shipment.ACTIVE_STATUSES:
                raise SimulationError("Only an In Transit or Paused journey can be stopped.")
            self._finish(shipment, "Stopped", "stop")

    def complete(self, shipment):
        with self.lock:
            db.session.refresh(shipment)  # the engine thread may have advanced it
            if shipment.status not in ("In Transit", "Paused", "Stopped"):
                raise SimulationError(
                    "Only shipments whose journey has started (In Transit, Paused or Stopped) can be marked completed."
                )
            self._finish(shipment, "Completed", "completion")


engine = SimulationEngine()
