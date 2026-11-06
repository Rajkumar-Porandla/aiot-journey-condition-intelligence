"""Exposure alerts and statistics endpoints."""
from flask import Blueprint, jsonify, request

from ..auth import login_required
from ..extensions import db
from ..models import ExposureAlert, Shipment
from ..utils import ApiError, error_response

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


@alerts_bp.errorhandler(ApiError)
def _handle_api_error(err):
    return error_response(err)


@alerts_bp.get("")
def list_all_alerts():
    severity = request.args.get("severity")
    is_active = request.args.get("is_active")
    limit = request.args.get("limit", default=100, type=int)

    query = ExposureAlert.query.order_by(ExposureAlert.timestamp.desc(), ExposureAlert.id.desc())
    if severity:
        query = query.filter_by(severity=severity)
    if is_active is not None:
        active_bool = is_active.lower() in ("true", "1")
        query = query.filter_by(is_active=active_bool)

    alerts = query.limit(limit).all()
    return jsonify({
        "alerts": [a.to_dict() for a in alerts],
        "total": ExposureAlert.query.count(),
        "active_count": ExposureAlert.query.filter_by(is_active=True).count(),
    })


@alerts_bp.get("/<int:shipment_id>")
def list_shipment_alerts(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if not shipment:
        raise ApiError("Shipment not found", 404)

    alerts = ExposureAlert.query.filter_by(shipment_id=shipment.id).order_by(ExposureAlert.timestamp.desc()).all()
    return jsonify({
        "shipment_id": shipment.id,
        "shipment_code": shipment.shipment_code,
        "alerts": [a.to_dict() for a in alerts],
        "active_count": sum(1 for a in alerts if a.is_active),
    })

