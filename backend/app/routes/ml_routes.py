"""ML predictions, evaluation metrics, What-If simulator, and multi-shipment comparison."""
from flask import Blueprint, g, jsonify, request

from ..auth import login_required
from ..core.features import NUMERIC_FEATURES, public_features
from ..extensions import db
from ..models import MLPrediction, Shipment, SimulationScenario
from ..services import ml_service
from ..services.analytics import shipment_readings, shipment_stats
from ..services.predictions import NoReadings, compute_shipment_prediction, predict_and_store
from ..utils import ApiError, error_response, get_json, parse_float, parse_str

ml_bp = Blueprint("ml", __name__, url_prefix="/api")


@ml_bp.errorhandler(ApiError)
def _handle_api_error(err):
    return error_response(err)


@ml_bp.get("/ml/metrics")
def get_ml_metrics():
    """Return trained model performance metrics and permutation feature importance."""
    try:
        metrics = ml_service.model_info()
        return jsonify({"metrics": metrics})
    except ml_service.ModelUnavailable as exc:
        raise ApiError(str(exc), 503)


@ml_bp.post("/predict/<int:shipment_id>")
@login_required
def predict_shipment(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if not shipment:
        raise ApiError("Shipment not found", 404)
    try:
        pred = predict_and_store(shipment, trigger="manual")
        db.session.commit()
        return jsonify({"prediction": pred.to_dict(), "message": "ML prediction generated and persisted"})
    except NoReadings as exc:
        raise ApiError(str(exc), 400)
    except ml_service.ModelUnavailable as exc:
        raise ApiError(str(exc), 503)


@ml_bp.get("/predictions/<int:shipment_id>")
def get_shipment_predictions(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if not shipment:
        raise ApiError("Shipment not found", 404)

    preds = (
        MLPrediction.query.filter_by(shipment_id=shipment.id)
        .order_by(MLPrediction.created_at.desc(), MLPrediction.id.desc())
        .all()
    )
    latest = preds[0].to_dict() if preds else None
    return jsonify({
        "shipment_id": shipment.id,
        "shipment_code": shipment.shipment_code,
        "latest_prediction": latest,
        "history": [p.to_dict() for p in preds],
    })


@ml_bp.post("/simulator/what-if")
def simulate_what_if():
    """Module 7: What-If Journey Simulator.

    Modifies environmental condition parameters for an existing shipment WITHOUT
    changing its actual recorded telemetry, and runs the genuine trained ML models.
    Can also save the scenario for persistent tracking.
    """
    data = get_json()
    shipment_id = data.get("shipment_id")
    if not shipment_id:
        raise ApiError("shipment_id is required", 400)

    shipment = db.session.get(Shipment, int(shipment_id))
    if not shipment:
        raise ApiError("Shipment not found", 404)

    # Get baseline readings and original prediction
    readings = shipment_readings(shipment)
    orig_stats = shipment_stats(shipment, readings) if readings else None

    # Derive original feature values or defaults from shipment
    if orig_stats and orig_stats.get("avg_temp") is not None:
        baseline = {k: orig_stats[k] for k in NUMERIC_FEATURES}
    else:
        prof = shipment.product_profile
        baseline = {
            "avg_temp": (prof.min_temp + prof.max_temp) / 2.0,
            "max_temp": prof.max_temp,
            "avg_humidity": (prof.min_humidity + prof.max_humidity) / 2.0,
            "temp_exposure_hours": 0.0,
            "humidity_exposure_hours": 0.0,
            "journey_duration_hours": max(
                (shipment.expected_delivery_time - shipment.start_time).total_seconds() / 3600.0, 1.0
            ),
            "violation_count": 0,
        }

    # Extract modified parameters
    modified = {}
    modified["avg_temp"] = parse_float(data, "avg_temp", default=baseline["avg_temp"], required=False)
    modified["max_temp"] = parse_float(data, "max_temp", default=baseline["max_temp"], required=False)
    modified["avg_humidity"] = parse_float(data, "avg_humidity", default=baseline["avg_humidity"], min_value=0, max_value=100, required=False)
    modified["temp_exposure_hours"] = parse_float(data, "temp_exposure_hours", default=baseline["temp_exposure_hours"], min_value=0, required=False)
    modified["humidity_exposure_hours"] = parse_float(data, "humidity_exposure_hours", default=baseline["humidity_exposure_hours"], min_value=0, required=False)
    modified["journey_duration_hours"] = parse_float(data, "journey_duration_hours", default=baseline["journey_duration_hours"], min_value=0.1, required=False)
    modified["violation_count"] = int(parse_float(data, "violation_count", default=baseline["violation_count"], min_value=0, required=False))

    # Consistency checks
    if modified["max_temp"] < modified["avg_temp"]:
        modified["max_temp"] = modified["avg_temp"]
    if modified["temp_exposure_hours"] > modified["journey_duration_hours"]:
        modified["temp_exposure_hours"] = modified["journey_duration_hours"]
    if modified["humidity_exposure_hours"] > modified["journey_duration_hours"]:
        modified["humidity_exposure_hours"] = modified["journey_duration_hours"]

    # Run genuine models on both baseline and modified
    try:
        orig_pred = ml_service.predict_from_stats(shipment.category, baseline)
        mod_pred = ml_service.predict_from_stats(shipment.category, modified)
    except ml_service.ModelUnavailable as exc:
        raise ApiError(str(exc), 503)

    # Calculate delta / shift factors
    score_diff = round(mod_pred["risk_score"] - orig_pred["risk_score"], 2)
    shift_factors = []
    for f in NUMERIC_FEATURES:
        delta_val = modified[f] - baseline[f]
        if abs(delta_val) > 0.001:
            shift_factors.append({
                "feature": f,
                "label": f.replace("_", " ").title(),
                "original_value": round(baseline[f], 2),
                "modified_value": round(modified[f], 2),
                "delta": round(delta_val, 2),
            })

    scenario_name = data.get("name")
    saved_scenario_id = None
    if scenario_name:
        scen = SimulationScenario(
            shipment_id=shipment.id,
            user_id=getattr(g, "current_user", None).id if hasattr(g, "current_user") else None,
            name=scenario_name.strip(),
            original_features=baseline,
            modified_features=modified,
            original_prediction=orig_pred,
            simulated_prediction=mod_pred,
        )
        db.session.add(scen)
        db.session.commit()
        saved_scenario_id = scen.id

    return jsonify({
        "shipment": {
            "id": shipment.id,
            "shipment_code": shipment.shipment_code,
            "product_name": shipment.product_name,
            "category": shipment.category,
            "product_profile": shipment.product_profile.name,
        },
        "original_features": baseline,
        "modified_features": modified,
        "original_prediction": orig_pred,
        "simulated_prediction": mod_pred,
        "score_difference": score_diff,
        "risk_class_changed": orig_pred["risk_class"] != mod_pred["risk_class"],
        "shift_factors": shift_factors,
        "saved_scenario_id": saved_scenario_id,
    })


@ml_bp.get("/simulator/scenarios/<int:shipment_id>")
def get_shipment_scenarios(shipment_id):
    scenarios = SimulationScenario.query.filter_by(shipment_id=shipment_id).order_by(SimulationScenario.created_at.desc()).all()
    return jsonify({"scenarios": [s.to_dict() for s in scenarios]})


@ml_bp.post("/compare")
def compare_shipments():
    """Module 8: Multi-Shipment Risk Comparison.

    Select 2 or more shipments for side-by-side comparison, environmental history,
    ML risk predictions, and safer journey identification.
    """
    data = get_json()
    shipment_ids = data.get("shipment_ids", [])
    if not isinstance(shipment_ids, list) or len(shipment_ids) < 2:
        raise ApiError("shipment_ids must be a list of at least 2 shipment IDs.", 400)

    shipments = Shipment.query.filter(Shipment.id.in_(shipment_ids)).all()
    if len(shipments) < len(shipment_ids):
        found = {s.id for s in shipments}
        missing = [sid for sid in shipment_ids if sid not in found]
        raise ApiError(f"Some shipments not found: {missing}", 404)

    # Sort shipments in requested order
    id_order = {sid: idx for idx, sid in enumerate(shipment_ids)}
    shipments.sort(key=lambda s: id_order[s.id])

    categories = {s.category for s in shipments}
    same_category = len(categories) == 1
    category_warning = (
        None
        if same_category
        else "Shipments belong to different product categories! Different categories have distinct sensitivity, temperature thresholds, and risk models."
    )

    comparison_items = []
    for s in shipments:
        readings = shipment_readings(s)
        stats = shipment_stats(s, readings)
        pred = s.latest_prediction()
        pred_dict = pred.to_dict() if pred else None

        if not pred_dict and readings:
            try:
                _, p = compute_shipment_prediction(s, readings)
                pred_dict = p
            except Exception:
                pred_dict = None

        risk_score = pred_dict["risk_score"] if pred_dict else None
        risk_class = pred_dict["risk_class"] if pred_dict else "Unknown"

        comparison_items.append({
            "shipment_id": s.id,
            "shipment_code": s.shipment_code,
            "product_name": s.product_name,
            "category": s.category,
            "category_label": s.product_profile.category,
            "transport_type": s.transport_type,
            "status": s.status,
            "source_location": s.source_location,
            "destination_location": s.destination_location,
            "sim_mode": s.sim_mode,
            "reading_count": len(readings),
            "stats": {
                "avg_temp": round(stats["avg_temp"], 2) if stats["avg_temp"] is not None else None,
                "max_temp": round(stats["max_temp"], 2) if stats["max_temp"] is not None else None,
                "min_temp": round(stats["min_temp"], 2) if stats["min_temp"] is not None else None,
                "avg_humidity": round(stats["avg_humidity"], 2) if stats["avg_humidity"] is not None else None,
                "temp_exposure_hours": round(stats["temp_exposure_hours"], 2),
                "humidity_exposure_hours": round(stats["humidity_exposure_hours"], 2),
                "journey_duration_hours": round(stats["journey_duration_hours"], 2),
                "violation_count": stats["violation_count"],
                "alert_count": s.alerts.count(),
            },
            "ml_risk": {
                "risk_class": risk_class,
                "risk_score": risk_score,
            },
            "thresholds": s.product_profile.thresholds(),
        })

    # Identify the safer journey
    valid_scored = [item for item in comparison_items if item["ml_risk"]["risk_score"] is not None]
    if valid_scored:
        safer_item = min(valid_scored, key=lambda x: x["ml_risk"]["risk_score"])
        safest = {
            "shipment_id": safer_item["shipment_id"],
            "shipment_code": safer_item["shipment_code"],
            "risk_score": safer_item["ml_risk"]["risk_score"],
            "risk_class": safer_item["ml_risk"]["risk_class"],
            "reason": f"Lowest predicted environmental quality risk score ({safer_item['ml_risk']['risk_score']:.1f}/100) with {safer_item['stats']['temp_exposure_hours']:.1f}h temperature exposure and {safer_item['stats']['violation_count']} environmental violations.",
        }
    else:
        safest = None

    return jsonify({
        "same_category": same_category,
        "category_warning": category_warning,
        "shipments": comparison_items,
        "safest_shipment": safest,
    })

