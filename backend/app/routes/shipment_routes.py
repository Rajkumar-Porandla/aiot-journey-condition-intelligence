"""Shipment CRUD and management endpoints."""
import uuid
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from ..auth import admin_required, login_required
from ..core.locations import LOCATIONS
from ..extensions import db
from ..models import ProductProfile, Shipment, utcnow
from ..services.analytics import downsample, shipment_readings, shipment_stats
from ..utils import ApiError, error_response, get_json, parse_choice, parse_datetime, parse_float, parse_str

shipments_bp = Blueprint("shipments", __name__, url_prefix="/api/shipments")


@shipments_bp.errorhandler(ApiError)
def _handle_api_error(err):
    return error_response(err)


def generate_shipment_code(category):
    prefix = (category[:4] if category else "SHP").upper()
    return f"SHP-{prefix}-{uuid.uuid4().hex[:6].upper()}"


@shipments_bp.get("/locations")
def get_locations():
    """Return offline locations list for easy pick-list selection."""
    return jsonify({"locations": LOCATIONS})


@shipments_bp.get("")
def list_shipments():
    status = request.args.get("status")
    category = request.args.get("category")
    query = Shipment.query.order_by(Shipment.created_at.desc())

    if status:
        query = query.filter_by(status=status)
    if category:
        query = query.join(ProductProfile).filter(ProductProfile.category == category)

    shipments = query.all()
    return jsonify({"shipments": [s.to_dict(include_latest=True) for s in shipments]})


@shipments_bp.get("/<int:shipment_id>")
def get_shipment(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if not shipment:
        raise ApiError("Shipment not found", 404)
    data = shipment.to_dict(include_latest=True)
    stats = shipment_stats(shipment)
    data["stats"] = stats
    return jsonify({"shipment": data})


@shipments_bp.post("")
@login_required
def create_shipment():
    data = get_json()
    product_name = parse_str(data, "product_name", required=True)
    product_profile_id = data.get("product_profile_id")
    if not product_profile_id:
        raise ApiError("product_profile_id is required", 400)

    profile = db.session.get(ProductProfile, int(product_profile_id))
    if not profile:
        raise ApiError("Specified product profile not found", 404)

    source_location = parse_str(data, "source_location", required=True)
    source_lat = parse_float(data, "source_lat", required=True, min_value=-90, max_value=90)
    source_lon = parse_float(data, "source_lon", required=True, min_value=-180, max_value=180)

    destination_location = parse_str(data, "destination_location", required=True)
    destination_lat = parse_float(data, "destination_lat", required=True, min_value=-90, max_value=90)
    destination_lon = parse_float(data, "destination_lon", required=True, min_value=-180, max_value=180)

    start_time = parse_datetime(data.get("start_time"), "start_time")
    expected_delivery_time = parse_datetime(data.get("expected_delivery_time"), "expected_delivery_time")

    if expected_delivery_time <= start_time:
        raise ApiError("Expected delivery time must be after the start time.", 400)

    transport_type = parse_choice(data, "transport_type", choices=Shipment.TRANSPORT_TYPES, default="Refrigerated Truck")
    notes = parse_str(data, "notes", required=False, default="")

    code = generate_shipment_code(profile.category)

    shipment = Shipment(
        shipment_code=code,
        product_name=product_name,
        product_profile_id=profile.id,
        source_location=source_location,
        source_lat=source_lat,
        source_lon=source_lon,
        destination_location=destination_location,
        destination_lat=destination_lat,
        destination_lon=destination_lon,
        start_time=start_time,
        expected_delivery_time=expected_delivery_time,
        transport_type=transport_type,
        notes=notes,
        status="Pending",
        created_by_id=g.current_user.id,
    )
    db.session.add(shipment)
    db.session.commit()
    return jsonify({"shipment": shipment.to_dict(), "message": "Shipment created successfully"}), 201


@shipments_bp.put("/<int:shipment_id>")
@login_required
def update_shipment(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if not shipment:
        raise ApiError("Shipment not found", 404)

    if shipment.status in ("In Transit", "Completed"):
        raise ApiError(f"Cannot edit a shipment that is already {shipment.status}.", 400)

    data = get_json()
    if "product_name" in data:
        shipment.product_name = parse_str(data, "product_name")
    if "source_location" in data:
        shipment.source_location = parse_str(data, "source_location")
    if "source_lat" in data:
        shipment.source_lat = parse_float(data, "source_lat", min_value=-90, max_value=90)
    if "source_lon" in data:
        shipment.source_lon = parse_float(data, "source_lon", min_value=-180, max_value=180)
    if "destination_location" in data:
        shipment.destination_location = parse_str(data, "destination_location")
    if "destination_lat" in data:
        shipment.destination_lat = parse_float(data, "destination_lat", min_value=-90, max_value=90)
    if "destination_lon" in data:
        shipment.destination_lon = parse_float(data, "destination_lon", min_value=-180, max_value=180)
    if "transport_type" in data:
        shipment.transport_type = parse_choice(data, "transport_type", choices=Shipment.TRANSPORT_TYPES)
    if "notes" in data:
        shipment.notes = parse_str(data, "notes", required=False, default="")

    db.session.commit()
    return jsonify({"shipment": shipment.to_dict(), "message": "Shipment updated successfully"})


@shipments_bp.delete("/<int:shipment_id>")
@admin_required
def delete_shipment(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if not shipment:
        raise ApiError("Shipment not found", 404)

    if shipment.status == "In Transit":
        raise ApiError("Cannot delete an In Transit shipment. Please stop it first.", 400)

    db.session.delete(shipment)
    db.session.commit()
    return jsonify({"message": f"Shipment {shipment.shipment_code} and all associated telemetry deleted successfully"})

