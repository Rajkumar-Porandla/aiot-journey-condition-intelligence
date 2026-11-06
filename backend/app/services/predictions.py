"""Persisted ML predictions for shipments."""
from ..extensions import db
from ..models import MLPrediction
from . import ml_service
from .analytics import shipment_readings, shipment_stats


class NoReadings(ValueError):
    pass


def compute_shipment_prediction(shipment, readings=None):
    """Return (stats, prediction dict) without saving anything."""
    if readings is None:
        readings = shipment_readings(shipment)
    if not readings:
        raise NoReadings("This shipment has no sensor readings yet. Start its virtual journey first.")
    stats = shipment_stats(shipment, readings)
    return stats, ml_service.predict_from_stats(shipment.category, stats)


def predict_and_store(shipment, trigger="manual"):
    """Run the models on the shipment's readings and add an MLPrediction to the session."""
    readings = shipment_readings(shipment)
    stats, result = compute_shipment_prediction(shipment, readings)
    pred = MLPrediction(
        shipment_id=shipment.id,
        risk_class=result["risk_class"],
        class_probabilities=result["class_probabilities"],
        risk_score=result["risk_score"],
        features=result["features"],
        explanation=result["explanation"],
        model_version=result["model_version"],
        trigger=trigger,
        reading_count=len(readings),
    )
    db.session.add(pred)
    return pred

