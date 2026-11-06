"""Dashboard summary statistics endpoint."""
from flask import Blueprint, jsonify
from sqlalchemy import func

from ..extensions import db
from ..models import ExposureAlert, MLPrediction, Shipment

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@dashboard_bp.get("/stats")
def get_dashboard_stats():
    total_shipments = Shipment.query.count()
    active_shipments = Shipment.query.filter(Shipment.status.in_(["In Transit", "Paused"])).count()
    completed_shipments = Shipment.query.filter_by(status="Completed").count()
    total_alerts = ExposureAlert.query.count()

    # Risk distributions from latest predictions of each shipment
    shipments = Shipment.query.all()
    risk_counts = {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0, "Unpredicted": 0}
    scores = []

    for s in shipments:
        pred = s.latest_prediction()
        if pred:
            c = pred.risk_class
            risk_counts[c] = risk_counts.get(c, 0) + 1
            scores.append(pred.risk_score)
        else:
            risk_counts["Unpredicted"] += 1

    avg_risk_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    high_risk_shipments = risk_counts.get("High Risk", 0)

    # Status distribution
    status_counts = {}
    for st in ["Pending", "In Transit", "Paused", "Stopped", "Completed"]:
        status_counts[st] = Shipment.query.filter_by(status=st).count()

    # Category distribution
    cat_query = (
        db.session.query(Shipment.transport_type, func.count(Shipment.id))
        .group_by(Shipment.transport_type)
        .all()
    )
    transport_distribution = {t: c for t, c in cat_query}

    # Recent activity
    recent_shipments = Shipment.query.order_by(Shipment.created_at.desc()).limit(6).all()
    recent_alerts = ExposureAlert.query.order_by(ExposureAlert.timestamp.desc()).limit(6).all()

    return jsonify({
        "summary": {
            "total_shipments": total_shipments,
            "active_shipments": active_shipments,
            "completed_shipments": completed_shipments,
            "high_risk_shipments": high_risk_shipments,
            "total_exposure_alerts": total_alerts,
            "average_risk_score": avg_risk_score,
        },
        "risk_distribution": risk_counts,
        "status_distribution": status_counts,
        "transport_distribution": transport_distribution,
        "recent_shipments": [s.to_dict(include_latest=True) for s in recent_shipments],
        "recent_alerts": [a.to_dict() for a in recent_alerts],
    })

