"""Seed default profiles, admin and operator users, and demonstration shipments."""
import random
from datetime import datetime, timedelta, timezone

from ..core import exposure, sensor_model
from ..core.locations import LOCATIONS
from ..core.product_defaults import CATEGORY_KEYS, default_profile
from ..extensions import db
from ..models import ExposureAlert, MLPrediction, ProductProfile, SensorReading, Shipment, User
from . import ml_service
from .simulation_engine import new_alert_code

DEMO_SHIPMENTS = [
    {
        "code": "SHP-1001-DAIRY",
        "product_name": "Pasteurized Whole Milk Crates",
        "category": "dairy",
        "source": "Anand, IN",
        "destination": "Mumbai, IN",
        "transport": "Refrigerated Truck",
        "mode": "NORMAL",
        "hours_ago": 8,
        "duration_hours": 10,
        "completed": True,
        "status": "Completed",
    },
    {
        "code": "SHP-1002-PHARMA",
        "product_name": "Temperature-Sensitive Vaccines (Batch V-9)",
        "category": "pharmaceutical",
        "source": "Hyderabad, IN",
        "destination": "Bengaluru, IN",
        "transport": "Refrigerated Truck",
        "mode": "WARNING",
        "hours_ago": 6,
        "duration_hours": 12,
        "completed": False,
        "status": "In Transit",
    },
    {
        "code": "SHP-1003-FROZEN",
        "product_name": "Export Quality Frozen Seafood",
        "category": "frozen",
        "source": "Kochi, IN",
        "destination": "Chennai, IN",
        "transport": "Rail Reefer",
        "mode": "CRITICAL",
        "hours_ago": 14,
        "duration_hours": 16,
        "completed": True,
        "status": "Completed",
    },
    {
        "code": "SHP-1004-BERRIES",
        "product_name": "Premium Fresh Strawberries",
        "category": "fruits_vegetables",
        "source": "Nashik, IN",
        "destination": "Pune, IN",
        "transport": "Insulated Van",
        "mode": "NORMAL",
        "hours_ago": 2,
        "duration_hours": 5,
        "completed": False,
        "status": "In Transit",
    },
    {
        "code": "SHP-1005-FLOWERS",
        "product_name": "Export Dutch Roses & Carnations",
        "category": "flowers",
        "source": "Ooty, IN",
        "destination": "Bengaluru, IN",
        "transport": "Refrigerated Truck",
        "mode": "WARNING",
        "hours_ago": 7,
        "duration_hours": 8,
        "completed": True,
        "status": "Completed",
    },
]

LOC_MAP = {loc["name"]: loc for loc in LOCATIONS}


def ensure_default_profiles():
    """Ensure that default product profiles exist."""
    for cat in CATEGORY_KEYS:
        existing = ProductProfile.query.filter_by(category=cat, is_default=True).first()
        if not existing:
            p = default_profile(cat)
            profile = ProductProfile(
                name=p["name"],
                category=cat,
                min_temp=p["min_temp"],
                max_temp=p["max_temp"],
                min_humidity=p["min_humidity"],
                max_humidity=p["max_humidity"],
                sensitivity=p["sensitivity"],
                description=p["description"],
                is_default=True,
            )
            db.session.add(profile)
    db.session.commit()


def seed_database():
    """Seed initial users, default profiles, and realistic demo shipments."""
    ensure_default_profiles()

    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@aiot-journey.local",
            full_name="Fleet Administrator",
            role="admin",
        )
        admin.set_password("Admin@1234")
        db.session.add(admin)

    operator = User.query.filter_by(username="operator").first()
    if not operator:
        operator = User(
            username="operator",
            email="operator@aiot-journey.local",
            full_name="Cold-Chain Operator",
            role="operator",
        )
        operator.set_password("Operator@1234")
        db.session.add(operator)

    db.session.commit()

    # Seed shipments if none exist
    if Shipment.query.count() == 0:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rng = random.Random(1337)

        for item in DEMO_SHIPMENTS:
            prof = ProductProfile.query.filter_by(category=item["category"], is_default=True).first()
            src = LOC_MAP.get(item["source"], LOCATIONS[0])
            dst = LOC_MAP.get(item["destination"], LOCATIONS[1])
            start_t = now - timedelta(hours=item["hours_ago"])
            expected_t = start_t + timedelta(hours=item["duration_hours"])

            shipment = Shipment(
                shipment_code=item["code"],
                product_name=item["product_name"],
                product_profile_id=prof.id,
                source_location=src["name"],
                source_lat=src["lat"],
                source_lon=src["lon"],
                destination_location=dst["name"],
                destination_lat=dst["lat"],
                destination_lon=dst["lon"],
                start_time=start_t,
                expected_delivery_time=expected_t,
                transport_type=item["transport"],
                status=item["status"],
                sim_mode=item["mode"],
                sim_interval_seconds=3,
                sim_step_minutes=15,
                created_by_id=admin.id,
                notes=f"Demonstration journey running in {item['mode']} mode.",
            )
            db.session.add(shipment)
            db.session.flush()

            # Pre-populate simulated readings
            sim_state = sensor_model.initial_state(prof.thresholds(), item["mode"], rng)
            tracker = exposure.ExposureTracker(prof.thresholds())
            route = {
                "source_lat": src["lat"],
                "source_lon": src["lon"],
                "destination_lat": dst["lat"],
                "destination_lon": dst["lon"],
            }
            duration_minutes = item["duration_hours"] * 60
            step = 15.0

            # If completed, simulate full 100%. If in transit, simulate up to 50-70%
            target_prog = 1.0 if item["completed"] else 0.65
            readings_list = []
            alerts_map = {}

            while sim_state["progress"] < target_prog:
                r = sensor_model.next_reading(sim_state, prof.thresholds(), route, step, duration_minutes, rng)
                ts = start_t + timedelta(minutes=r["elapsed_minutes"])
                viol = exposure.violations_for(r["temperature"], r["humidity"], prof.thresholds())
                s_reading = SensorReading(
                    shipment_id=shipment.id,
                    sequence=r["sequence"],
                    timestamp=ts,
                    recorded_at=ts,
                    temperature=r["temperature"],
                    humidity=r["humidity"],
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    progress=r["progress"],
                    is_delayed=r["is_delayed"],
                    temp_violation=any(k.startswith("TEMPERATURE") for k in viol),
                    humidity_violation=any(k.startswith("HUMIDITY") for k in viol),
                )
                db.session.add(s_reading)
                readings_list.append(s_reading)

                events = tracker.process(
                    {"temperature": r["temperature"], "humidity": r["humidity"], "timestamp": ts.isoformat()},
                    step,
                )
                for ev in events:
                    ep = ev["episode"]
                    if ev["action"] == "create":
                        alt = ExposureAlert(
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
                        db.session.add(alt)
                        db.session.flush()
                        ep["ref"] = alt.id
                        alerts_map[ep.get("ref")] = alt
                    elif ep.get("ref") in alerts_map:
                        alt = alerts_map[ep["ref"]]
                        alt.severity = ev["severity"]
                        alt.recorded_value = ev["recorded_value"]
                        alt.exposure_duration_minutes = ev["exposure_duration_minutes"]
                        alt.timestamp = datetime.fromisoformat(ev["timestamp"])
                        alt.description = ev["description"]
                        alt.is_active = ev["is_active"]

            shipment.sim_progress = sim_state["progress"]
            shipment.sim_elapsed_minutes = sim_state["elapsed_minutes"]
            shipment.sim_state = {"sensor": sim_state, "exposure": tracker.state}
            if item["completed"]:
                shipment.actual_delivery_time = start_t + timedelta(minutes=sim_state["elapsed_minutes"])

            db.session.flush()

            # Generate initial ML prediction
            stats_rows = [
                {
                    "minutes": (r.timestamp - start_t).total_seconds() / 60.0,
                    "temperature": r.temperature,
                    "humidity": r.humidity,
                }
                for r in readings_list
            ]
            stats = exposure.analyze_readings(stats_rows, prof.thresholds(), default_step=step)
            try:
                pred_res = ml_service.predict_from_stats(shipment.category, stats)
                pred = MLPrediction(
                    shipment_id=shipment.id,
                    risk_class=pred_res["risk_class"],
                    class_probabilities=pred_res["class_probabilities"],
                    risk_score=pred_res["risk_score"],
                    features=pred_res["features"],
                    explanation=pred_res["explanation"],
                    model_version=pred_res["model_version"],
                    trigger="initial_seed",
                    reading_count=len(readings_list),
                )
                db.session.add(pred)
            except Exception as e:
                print(f"Skipping seed prediction for {item['code']}: {e}")

        db.session.commit()

