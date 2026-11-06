"""Product profile management endpoints."""
from flask import Blueprint, g, jsonify

from ..auth import admin_required, login_required
from ..core.product_defaults import CATEGORY_KEYS
from ..extensions import db
from ..models import ProductProfile
from ..utils import ApiError, error_response, get_json, parse_choice, parse_float, parse_str

products_bp = Blueprint("products", __name__, url_prefix="/api/products")


@products_bp.errorhandler(ApiError)
def _handle_api_error(err):
    return error_response(err)


@products_bp.get("")
def list_products():
    profiles = ProductProfile.query.order_by(ProductProfile.category, ProductProfile.name).all()
    return jsonify({"products": [p.to_dict() for p in profiles]})


@products_bp.get("/<int:profile_id>")
def get_product(profile_id):
    profile = db.session.get(ProductProfile, profile_id)
    if not profile:
        raise ApiError("Product profile not found", 404)
    return jsonify({"product": profile.to_dict()})


@products_bp.post("")
@admin_required
def create_product():
    data = get_json()
    name = parse_str(data, "name", required=True)
    category = parse_choice(data, "category", choices=CATEGORY_KEYS, required=True)
    min_temp = parse_float(data, "min_temp", required=True)
    max_temp = parse_float(data, "max_temp", required=True)
    min_humidity = parse_float(data, "min_humidity", required=True, min_value=0, max_value=100)
    max_humidity = parse_float(data, "max_humidity", required=True, min_value=0, max_value=100)
    sensitivity = parse_choice(data, "sensitivity", choices=["Low", "Medium", "High", "Very High"], default="Medium")
    description = parse_str(data, "description", required=False, default="")

    if min_temp >= max_temp:
        raise ApiError("Minimum temperature must be strictly less than maximum temperature.", 400)
    if min_humidity >= max_humidity:
        raise ApiError("Minimum humidity must be strictly less than maximum humidity.", 400)

    if ProductProfile.query.filter_by(name=name).first():
        raise ApiError(f"A profile named '{name}' already exists.", 409)

    profile = ProductProfile(
        name=name,
        category=category,
        min_temp=min_temp,
        max_temp=max_temp,
        min_humidity=min_humidity,
        max_humidity=max_humidity,
        sensitivity=sensitivity,
        description=description,
        is_default=False,
        created_by_id=g.current_user.id,
    )
    db.session.add(profile)
    db.session.commit()
    return jsonify({"product": profile.to_dict(), "message": "Product profile created"}), 201


@products_bp.put("/<int:profile_id>")
@admin_required
def update_product(profile_id):
    profile = db.session.get(ProductProfile, profile_id)
    if not profile:
        raise ApiError("Product profile not found", 404)

    data = get_json()
    name = parse_str(data, "name", required=False, default=profile.name)
    min_temp = parse_float(data, "min_temp", required=False, default=profile.min_temp)
    max_temp = parse_float(data, "max_temp", required=False, default=profile.max_temp)
    min_humidity = parse_float(data, "min_humidity", required=False, min_value=0, max_value=100, default=profile.min_humidity)
    max_humidity = parse_float(data, "max_humidity", required=False, min_value=0, max_value=100, default=profile.max_humidity)
    sensitivity = parse_choice(data, "sensitivity", choices=["Low", "Medium", "High", "Very High"], required=False, default=profile.sensitivity)
    description = parse_str(data, "description", required=False, default=profile.description)

    if min_temp >= max_temp:
        raise ApiError("Minimum temperature must be strictly less than maximum temperature.", 400)
    if min_humidity >= max_humidity:
        raise ApiError("Minimum humidity must be strictly less than maximum humidity.", 400)

    existing = ProductProfile.query.filter(ProductProfile.name == name, ProductProfile.id != profile_id).first()
    if existing:
        raise ApiError(f"Another profile with name '{name}' already exists.", 409)

    profile.name = name
    profile.min_temp = min_temp
    profile.max_temp = max_temp
    profile.min_humidity = min_humidity
    profile.max_humidity = max_humidity
    profile.sensitivity = sensitivity
    profile.description = description

    db.session.commit()
    return jsonify({"product": profile.to_dict(), "message": "Product profile updated"})

