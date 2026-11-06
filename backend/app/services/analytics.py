"""Journey analytics computed from stored sensor readings."""
from ..core.exposure import analyze_readings
from ..models import SensorReading


def shipment_readings(shipment):
    return (
        SensorReading.query.filter_by(shipment_id=shipment.id).order_by(SensorReading.sequence.asc()).all()
    )


def shipment_stats(shipment, readings=None):
    """Exposure statistics for a shipment (based on its product profile thresholds)."""
    if readings is None:
        readings = shipment_readings(shipment)
    if not readings:
        return analyze_readings([], shipment.product_profile.thresholds())
    t0 = shipment.start_time
    rows = [
        {
            "minutes": (r.timestamp - t0).total_seconds() / 60.0,
            "temperature": r.temperature,
            "humidity": r.humidity,
        }
        for r in readings
    ]
    return analyze_readings(rows, shipment.product_profile.thresholds(), default_step=shipment.sim_step_minutes or 15.0)


def downsample(items, max_points=300):
    """Evenly thin a list for charting, always keeping the last element."""
    n = len(items)
    if n <= max_points:
        return items
    step = n / max_points
    picked = [items[int(i * step)] for i in range(max_points - 1)]
    picked.append(items[-1])
    return picked


def rounded_stats(stats):
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in stats.items()}

