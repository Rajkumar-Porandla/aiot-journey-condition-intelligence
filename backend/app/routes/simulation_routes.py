"""Simulation control and telemetry readings endpoints."""
from flask import Blueprint, jsonify, request

from ..auth import login_required
from ..extensions import db
from ..models import SensorReading, Shipment
from ..services.analytics import downsample, shipment_readings, shipment_stats
from ..services.simulation_engine import SimulationError, engine
from ..utils import ApiError, error_response, get_json, parse_choice, parse_float

sim_bp = Blueprint("simulation", __name__, url_prefix="/api")


@sim_bp.errorhandler(ApiError)
def _handle_api_error(err):
    return error_response(err)


@sim_bp.errorhandler(SimulationError)
def _handle_sim_error(err):
    return jsonify({"error": str(err)}), getattr(err, "status_code", 409) or 409


@sim_bp.post("/simulation/start/<int:shipment_id>")
@login_required
def start_simulation(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if not shipment:
        raise ApiError("Shipment not found", 404)

    data = request.get_json(silent=True) or {}
    mode = parse_choice(data, "mode", choices=Shipment.SIM_MODES, default="NORMAL", required=False)
    interval_seconds = parse_float(data, "interval_seconds", required=False, min_value=1.0, max_value=60.0, default=2.0)
    step_minutes = parse_float(data, "step_minutes", required=False, min_value=1.0, max_value=120.0, default=15.0)
    intensity = parse_float(data, "intensity", required=False, min_value=0.5, max_value=3.0, default=1.0)

    engine.start_journey(shipment, mode, interval_seconds, step_minutes, intensity)
    return jsonify({"message": f"Virtual journey started in {mode} mode", "shipment": shipment.to_dict()})


@sim_bp.post("/simulation/pause/<int:shipment_id>")
@login_required
def pause_simulation(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if not shipment:
        raise ApiError("Shipment not found", 404)
    engine.pause(shipment)
    return jsonify({"message": "Simulation paused", "shipment": shipment.to_dict()})


@sim_bp.post("/simulation/resume/<int:shipment_id>")
@login_required
def resume_simulation(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if not shipment:
        raise ApiError("Shipment not found", 404)
    engine.resume(shipment)
    return jsonify({"message": "Simulation resumed", "shipment": shipment.to_dict()})


@sim_bp.post("/simulation/stop/<int:shipment_id>")
@login_required
def stop_simulation(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if not shipment:
        raise ApiError("Shipment not found", 404)
    engine.stop(shipment)
    return jsonify({"message": "Simulation stopped", "shipment": shipment.to_dict()})


@sim_bp.post("/simulation/complete/<int:shipment_id>")
@login_required
def complete_simulation(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if not shipment:
        raise ApiError("Shipment not found", 404)
    engine.complete(shipment)
    return jsonify({"message": "Shipment marked completed", "shipment": shipment.to_dict()})


@sim_bp.get("/readings/<int:shipment_id>")
def get_readings(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if not shipment:
        raise ApiError("Shipment not found", 404)

    since_seq = request.args.get("since_seq", type=int)
    limit = request.args.get("limit", default=500, type=int)
    sample = request.args.get("sample", default="false").lower() == "true"

    query = SensorReading.query.filter_by(shipment_id=shipment.id).order_by(SensorReading.sequence.asc())
    if since_seq is not None:
        query = query.filter(SensorReading.sequence > since_seq)

    all_readings = query.all()
    if sample and len(all_readings) > 300:
        readings_to_return = downsample(all_readings, 300)
    else:
        readings_to_return = all_readings[-limit:] if limit else all_readings

    latest = SensorReading.query.filter_by(shipment_id=shipment.id).order_by(SensorReading.sequence.desc()).first()

    return jsonify({
        "shipment_id": shipment.id,
        "shipment_code": shipment.shipment_code,
        "total_readings": shipment.readings.count(),
        "latest_reading": latest.to_dict() if latest else None,
        "readings": [r.to_dict() for r in readings_to_return],
        "profile": shipment.product_profile.thresholds(),
        "status": shipment.status,
        "progress": round(shipment.sim_progress, 4),
    })

