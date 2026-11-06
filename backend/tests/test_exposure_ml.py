"""Tier 1, Tier 2, and Tier 3 Whitebox & Mathematical Verification of Exposure and ML Engine.

Features Covered:
- Feature 8: Harmful Exposure & Alert Severity Engine (violations_for, duration-aware severity, grace periods).
- Feature 9: Random Forest Quality Risk Prediction (Classifier probabilities, Regressor continuous risk score).
- Feature 10: Saabas Tree Path Attribution & Explainability (Exact tree path contribution theorem, grouped importance).
"""
from datetime import datetime, timedelta
import numpy as np
import pytest
from app import create_app
from app.config import TestConfig
from app.core import exposure, features
from app.core.explain import tree_contributions
from app.core.exposure import (
    GRACE_MINUTES,
    SENSITIVITY_MULTIPLIER,
    analyze_readings,
    describe,
    severity_from_score,
    severity_score,
    should_alert,
    violations_for,
)
from app.extensions import db
from app.models import ProductProfile, Shipment, utcnow
from app.services import ml_service
from app.services.seed import seed_database


@pytest.fixture
def client():
    """Create isolated test application context with in-memory database."""
    app = create_app(config_class=TestConfig, start_engine=False)
    with app.app_context():
        db.create_all()
        seed_database()
        with app.test_client() as test_client:
            yield test_client
        db.session.remove()
        db.drop_all()


@pytest.fixture
def operator_token(client):
    res = client.post("/api/auth/login", json={"username": "operator", "password": "Operator@1234"})
    assert res.status_code == 200
    return res.get_json()["token"]


# ==============================================================================
# Tier 1: Exposure Detection, Severity Formulas, and ML Prediction
# ==============================================================================

def test_temperature_violations_high_and_low():
    """Verify violations_for accurately detects high and low temperature excursions."""
    profile = {"min_temp": 2.0, "max_temp": 8.0, "min_humidity": 40.0, "max_humidity": 65.0}

    # Within bounds -> no violation
    assert violations_for(5.0, 50.0, profile) == {}

    # Temperature High
    v_high = violations_for(11.5, 50.0, profile)
    assert "TEMPERATURE_HIGH" in v_high
    dev, thresh = v_high["TEMPERATURE_HIGH"]
    assert round(dev, 2) == 3.5  # 11.5 - 8.0
    assert thresh == 8.0

    # Temperature Low
    v_low = violations_for(0.5, 50.0, profile)
    assert "TEMPERATURE_LOW" in v_low
    dev, thresh = v_low["TEMPERATURE_LOW"]
    assert round(dev, 2) == 1.5  # 2.0 - 0.5
    assert thresh == 2.0


def test_humidity_violations_high_and_low():
    """Verify violations_for accurately detects high and low humidity excursions."""
    profile = {"min_temp": 2.0, "max_temp": 8.0, "min_humidity": 40.0, "max_humidity": 65.0}

    # Humidity High
    v_high = violations_for(5.0, 80.0, profile)
    assert "HUMIDITY_HIGH" in v_high
    dev, thresh = v_high["HUMIDITY_HIGH"]
    assert round(dev, 2) == 15.0  # 80.0 - 65.0
    assert thresh == 65.0

    # Humidity Low
    v_low = violations_for(5.0, 25.0, profile)
    assert "HUMIDITY_LOW" in v_low
    dev, thresh = v_low["HUMIDITY_LOW"]
    assert round(dev, 2) == 15.0  # 40.0 - 25.0
    assert thresh == 40.0


def test_severity_score_and_band_mapping():
    """Verify severity_score and severity_from_score mapping into all four bands."""
    profile = {
        "min_temp": 2.0,
        "max_temp": 8.0,
        "min_humidity": 40.0,
        "max_humidity": 65.0,
        "sensitivity": "Medium",  # multiplier = 1.0
    }

    # Low band (< 20)
    score_low = severity_score("TEMPERATURE_HIGH", peak_deviation=0.5, duration_minutes=15.0, profile=profile)
    assert score_low < 20.0
    assert severity_from_score(score_low) == "Low"

    # Medium band (20 <= score < 40)
    score_med = severity_score("TEMPERATURE_HIGH", peak_deviation=2.5, duration_minutes=45.0, profile=profile)
    assert 20.0 <= score_med < 40.0
    assert severity_from_score(score_med) == "Medium"

    # High band (40 <= score < 65)
    score_high = severity_score("TEMPERATURE_HIGH", peak_deviation=3.0, duration_minutes=60.0, profile=profile)
    assert 40.0 <= score_high < 65.0
    assert severity_from_score(score_high) == "High"

    # Critical band (>= 65)
    score_crit = severity_score("TEMPERATURE_HIGH", peak_deviation=9.0, duration_minutes=240.0, profile=profile)
    assert score_crit >= 65.0
    assert severity_from_score(score_crit) == "Critical"


def test_random_forest_classifier_prediction(client):
    """Verify loaded Random Forest Classifier outputs valid risk class and valid probabilities."""
    stats = {
        "avg_temp": 4.5,
        "max_temp": 6.8,
        "avg_humidity": 55.0,
        "temp_exposure_hours": 0.5,
        "humidity_exposure_hours": 0.0,
        "journey_duration_hours": 8.0,
        "violation_count": 1,
    }
    pred = ml_service.predict_from_stats("dairy", stats)

    # Risk class must be one of the known labels
    assert pred["risk_class"] in ("Low Risk", "Medium Risk", "High Risk")

    # Probabilities must be present and sum to 1.0
    probs = pred["class_probabilities"]
    assert "Low Risk" in probs
    assert "Medium Risk" in probs
    assert "High Risk" in probs
    assert abs(sum(probs.values()) - 1.0) < 1e-3


def test_random_forest_regressor_score(client):
    """Verify loaded Random Forest Regressor predicts continuous risk scores between 0 and 100."""
    nominal_stats = {
        "avg_temp": 4.0,
        "max_temp": 5.5,
        "avg_humidity": 50.0,
        "temp_exposure_hours": 0.0,
        "humidity_exposure_hours": 0.0,
        "journey_duration_hours": 6.0,
        "violation_count": 0,
    }
    pred_nominal = ml_service.predict_from_stats("dairy", nominal_stats)
    assert 0.0 <= pred_nominal["risk_score"] <= 100.0

    harsh_stats = {
        "avg_temp": 14.5,
        "max_temp": 22.0,
        "avg_humidity": 85.0,
        "temp_exposure_hours": 6.0,
        "humidity_exposure_hours": 4.0,
        "journey_duration_hours": 8.0,
        "violation_count": 12,
    }
    pred_harsh = ml_service.predict_from_stats("dairy", harsh_stats)
    assert 0.0 <= pred_harsh["risk_score"] <= 100.0

    # Harsh journey must produce higher risk score than nominal journey
    assert pred_harsh["risk_score"] > pred_nominal["risk_score"]


# ==============================================================================
# Tier 2: Boundary & Corner Cases / Alert Suppression & Multipliers
# ==============================================================================

def test_grace_period_suppression():
    """Verify alerts are suppressed if duration < grace period, unless score >= 40."""
    # Low sensitivity has 45 min grace period
    profile_low = {"min_temp": 2.0, "max_temp": 8.0, "min_humidity": 40.0, "max_humidity": 65.0, "sensitivity": "Low"}
    assert GRACE_MINUTES["Low"] == 45

    # Duration 30 min (< 45), low score 25 -> SUPPRESSED (False)
    assert should_alert(score=25.0, duration_minutes=30.0, profile=profile_low) is False

    # Duration 45 min (== grace), score 25 -> ALERTED (True)
    assert should_alert(score=25.0, duration_minutes=45.0, profile=profile_low) is True

    # Duration 10 min (< grace), but High severity score 42.0 (>= 40) -> ALERTED immediately (True)
    assert should_alert(score=42.0, duration_minutes=10.0, profile=profile_low) is True

    # Very High sensitivity has 0 min grace period -> always alerts
    profile_vh = {"sensitivity": "Very High"}
    assert should_alert(score=5.0, duration_minutes=1.0, profile=profile_vh) is True


def test_sensitivity_multipliers_scaling():
    """Verify sensitivity multipliers strictly scale severity scores across all 4 tiers."""
    base_params = {
        "alert_type": "TEMPERATURE_HIGH",
        "peak_deviation": 3.0,
        "duration_minutes": 60.0,
    }
    span_profile = {"min_temp": 0.0, "max_temp": 10.0, "min_humidity": 0.0, "max_humidity": 100.0}

    s_low = severity_score(**base_params, profile=dict(span_profile, sensitivity="Low"))
    s_med = severity_score(**base_params, profile=dict(span_profile, sensitivity="Medium"))
    s_high = severity_score(**base_params, profile=dict(span_profile, sensitivity="High"))
    s_vh = severity_score(**base_params, profile=dict(span_profile, sensitivity="Very High"))

    assert SENSITIVITY_MULTIPLIER["Low"] == 0.7
    assert SENSITIVITY_MULTIPLIER["Medium"] == 1.0
    assert SENSITIVITY_MULTIPLIER["High"] == 1.3
    assert SENSITIVITY_MULTIPLIER["Very High"] == 1.6

    # Verify linear proportionality
    assert abs((s_low / s_med) - 0.7) < 1e-4
    assert abs((s_high / s_med) - 1.3) < 1e-4
    assert abs((s_vh / s_med) - 1.6) < 1e-4


def test_zero_readings_predict_error_400(client, operator_token):
    """Verify requesting ML prediction for a shipment with 0 readings returns 400 error."""
    profile = ProductProfile.query.first()
    t = utcnow()
    empty_shipment = Shipment(
        shipment_code="SHP-NO-READINGS",
        product_name="No Telemetry Milk",
        product_profile_id=profile.id,
        source_location="City A",
        source_lat=20.0,
        source_lon=70.0,
        destination_location="City B",
        destination_lat=22.0,
        destination_lon=72.0,
        start_time=t,
        expected_delivery_time=t + timedelta(hours=6),
        transport_type="Refrigerated Truck",
        status="Pending",
    )
    db.session.add(empty_shipment)
    db.session.commit()

    res = client.post(
        f"/api/predict/{empty_shipment.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert res.status_code == 400
    assert "no sensor readings" in res.get_json()["error"].lower()


def test_out_of_distribution_inputs_handled_safely(client):
    """Verify model gracefully handles out-of-distribution extremes without NaN or crashes."""
    # Extreme heat wave beyond training distribution
    extreme_heat = {
        "avg_temp": 58.0,
        "max_temp": 68.0,
        "avg_humidity": 98.0,
        "temp_exposure_hours": 30.0,
        "humidity_exposure_hours": 20.0,
        "journey_duration_hours": 30.0,
        "violation_count": 80,
    }
    pred_heat = ml_service.predict_from_stats("dairy", extreme_heat)
    assert pred_heat["risk_class"] == "High Risk"
    assert 0.0 <= pred_heat["risk_score"] <= 100.0
    assert not np.isnan(pred_heat["risk_score"])

    # Extreme subzero deep freeze
    deep_freeze = {
        "avg_temp": -45.0,
        "max_temp": -35.0,
        "avg_humidity": 15.0,
        "temp_exposure_hours": 12.0,
        "humidity_exposure_hours": 0.0,
        "journey_duration_hours": 12.0,
        "violation_count": 15,
    }
    pred_freeze = ml_service.predict_from_stats("dairy", deep_freeze)
    assert 0.0 <= pred_freeze["risk_score"] <= 100.0
    assert not np.isnan(pred_freeze["risk_score"])


# ==============================================================================
# Tier 3: Mathematical Proof of Saabas Tree Path Decomposition
# ==============================================================================

def test_saabas_tree_path_contributions_mathematical_identity(client):
    """Algebraic Proof: Verify base_score + sum(contributions) == risk_score for any vector."""
    clf, reg, metrics = ml_service.models.require()

    test_vectors = [
        # nominal dairy
        ("dairy", {"avg_temp": 4.0, "max_temp": 6.0, "avg_humidity": 50.0, "temp_exposure_hours": 0.0, "humidity_exposure_hours": 0.0, "journey_duration_hours": 6.0, "violation_count": 0}),
        # elevated temperature pharma
        ("pharmaceutical", {"avg_temp": 9.5, "max_temp": 14.0, "avg_humidity": 45.0, "temp_exposure_hours": 3.5, "humidity_exposure_hours": 0.0, "journey_duration_hours": 10.0, "violation_count": 4}),
        # extreme violation frozen seafood
        ("frozen", {"avg_temp": -12.0, "max_temp": -5.0, "avg_humidity": 70.0, "temp_exposure_hours": 5.0, "humidity_exposure_hours": 2.0, "journey_duration_hours": 14.0, "violation_count": 9}),
        # high humidity fresh produce
        ("fruits_vegetables", {"avg_temp": 3.0, "max_temp": 5.0, "avg_humidity": 98.0, "temp_exposure_hours": 0.0, "humidity_exposure_hours": 7.0, "journey_duration_hours": 8.0, "violation_count": 5}),
    ]

    for cat, stats in test_vectors:
        x_row = features.build_feature_row(cat, stats)
        raw_reg_pred = float(reg.predict(np.array([x_row]))[0])

        # Exact unclipped Saabas decomposition
        base, contrib = tree_contributions(reg, x_row)
        reconstructed = base + float(np.sum(contrib))

        # Absolute difference must be below 1e-4
        assert abs(reconstructed - raw_reg_pred) < 1e-4, f"Saabas decomposition mismatch: {reconstructed} vs {raw_reg_pred}"

        # Now verify against public API endpoint / service function
        res = ml_service.predict_from_stats(cat, stats)
        expl = res["explanation"]
        expl_base = expl["score_base"]
        expl_contrib_sum = sum(c["contribution"] for c in expl["score_contributions"])
        public_score = res["risk_score"]

        # Public values are rounded to 2 decimal places, so tolerance is within 0.05
        assert abs((expl_base + expl_contrib_sum) - public_score) < 0.05


def test_grouped_permutation_importance_structure(client):
    """Verify global feature importance includes all required factor groups."""
    res = client.get("/api/ml/metrics")
    assert res.status_code == 200
    metrics = res.get_json()["metrics"]

    assert "model_version" in metrics
    assert "regression" in metrics
    assert "classification" in metrics
    assert "permutation_importance" in metrics

    perm = metrics["permutation_importance"]
    assert "classifier" in perm
    assert "regressor" in perm

    # Check that regressor permutation importance contains all major feature groups
    features_present = {item["feature"] for item in perm["regressor"]}
    assert "temp_exposure_hours" in features_present
    assert "humidity_exposure_hours" in features_present
    assert "max_temp" in features_present
    assert "product_category" in features_present

    for item in perm["regressor"]:
        assert item["importance"] >= 0.0, f"Importance value for {item['feature']} must be non-negative"


def test_severity_formula_saturation_bounds():
    """Verify severity formula caps deviation term at 1.5x span and duration term at 6 hours."""
    profile = {"min_temp": 0.0, "max_temp": 10.0, "min_humidity": 0.0, "max_humidity": 100.0, "sensitivity": "Medium"}
    # Span is 10.0. Deviation of 15.0 is exactly 1.5x span.
    # Deviation of 30.0 should saturate at 1.5x span (dev_term = 60 * 1.5 = 90.0).
    score_sat_dev = severity_score("TEMPERATURE_HIGH", peak_deviation=30.0, duration_minutes=0.0, profile=profile)
    score_exact_15 = severity_score("TEMPERATURE_HIGH", peak_deviation=15.0, duration_minutes=0.0, profile=profile)
    assert round(score_sat_dev, 2) == round(score_exact_15, 2) == 90.0

    # Duration of 360 min is 6 hours (dur_term = 12 * 6 = 72.0).
    # Duration of 600 min should saturate at 6 hours.
    score_sat_dur = severity_score("TEMPERATURE_HIGH", peak_deviation=0.0, duration_minutes=600.0, profile=profile)
    score_exact_6h = severity_score("TEMPERATURE_HIGH", peak_deviation=0.0, duration_minutes=360.0, profile=profile)
    assert round(score_sat_dur, 2) == round(score_exact_6h, 2) == 72.0


def test_describe_alert_formatting():
    """Verify describe generates informative descriptions with direction and units."""
    desc_temp = describe("TEMPERATURE_HIGH", peak_value=12.4, threshold=8.0, duration_minutes=45.0, severity="Medium", ongoing=False)
    assert "High temperature exposure (ended)" in desc_temp
    assert "12.4°C" in desc_temp
    assert "4.4°C above" in desc_temp
    assert "8°C" in desc_temp
    assert "45 min" in desc_temp

    desc_hum = describe("HUMIDITY_LOW", peak_value=28.0, threshold=40.0, duration_minutes=90.0, severity="High", ongoing=True)
    assert "Low humidity exposure (ongoing)" in desc_hum
    assert "28.0% RH" in desc_hum
    assert "12.0% RH below" in desc_hum


def test_analyze_readings_edge_cases():
    """Verify analyze_readings calculates stats for empty, normal, and excursion readings."""
    profile = {"min_temp": 2.0, "max_temp": 8.0, "min_humidity": 40.0, "max_humidity": 65.0, "sensitivity": "Medium"}

    # Empty readings
    empty_stats = analyze_readings([], profile)
    assert empty_stats["reading_count"] == 0
    assert empty_stats["avg_temp"] is None
    assert empty_stats["temp_exposure_hours"] == 0.0

    # Normal readings over 4 steps of 15 min (1 hour)
    t0 = utcnow()
    normal_readings = [
        {
            "temperature": 4.0,
            "humidity": 50.0,
            "minutes": 15.0 * i,
            "timestamp": (t0 + timedelta(minutes=15 * i)).isoformat(),
        }
        for i in range(4)
    ]
    norm_stats = analyze_readings(normal_readings, profile)
    assert norm_stats["reading_count"] == 4
    assert round(norm_stats["avg_temp"], 1) == 4.0
    assert norm_stats["violation_count"] == 0
    assert norm_stats["temp_exposure_hours"] == 0.0

    # Excursion readings
    excursion_readings = [
        {
            "temperature": 11.0,
            "humidity": 75.0,
            "minutes": 15.0 * i,
            "timestamp": (t0 + timedelta(minutes=15 * i)).isoformat(),
        }
        for i in range(4)
    ]
    exc_stats = analyze_readings(excursion_readings, profile)
    assert exc_stats["violation_count"] == 2  # 1 temperature episode + 1 humidity episode
    assert exc_stats["temp_violation_count"] == 1
    assert exc_stats["humidity_violation_count"] == 1
    assert exc_stats["temp_exposure_hours"] == 1.0
    assert exc_stats["humidity_exposure_hours"] == 1.0


def test_exposure_tracker_incremental_events():
    """Verify ExposureTracker creates, updates, and closes episodes across simulated time."""
    from app.core.exposure import ExposureTracker
    profile = {"min_temp": 2.0, "max_temp": 8.0, "min_humidity": 40.0, "max_humidity": 65.0, "sensitivity": "Very High"}
    tracker = ExposureTracker(profile, {})

    # Reading 1: Excursion starts (temperature = 11.0°C) -> event created (Very High sensitivity has 0 grace)
    t0 = utcnow()
    r1 = {"temperature": 11.0, "humidity": 50.0, "timestamp": t0.isoformat()}
    events_1 = tracker.process(r1, dt_minutes=15.0)
    assert len(events_1) == 1
    assert events_1[0]["action"] == "create"
    assert events_1[0]["alert_type"] == "TEMPERATURE_HIGH"

    # Reading 2: Excursion continues with higher peak (temperature = 13.0°C) -> event updated
    r2 = {"temperature": 13.0, "humidity": 50.0, "timestamp": (t0 + timedelta(minutes=15)).isoformat()}
    events_2 = tracker.process(r2, dt_minutes=15.0)
    assert len(events_2) == 1
    assert events_2[0]["action"] == "update"
    assert events_2[0]["recorded_value"] == 13.0
    assert events_2[0]["exposure_duration_minutes"] == 30.0

    # Reading 3: Condition returns to safe range (5.0°C) -> episode closed
    r3 = {"temperature": 5.0, "humidity": 50.0, "timestamp": (t0 + timedelta(minutes=30)).isoformat()}
    events_3 = tracker.process(r3, dt_minutes=15.0)
    assert len(events_3) == 1
    assert events_3[0]["action"] == "close"
    assert events_3[0]["is_active"] is False


def test_factor_groups_sum_consistency(client):
    """Verify explanation factor groups cover all logical dimensions and sum reasonably."""
    stats = {
        "avg_temp": 8.5,
        "max_temp": 12.0,
        "avg_humidity": 60.0,
        "temp_exposure_hours": 2.5,
        "humidity_exposure_hours": 1.0,
        "journey_duration_hours": 8.0,
        "violation_count": 3,
    }
    pred = ml_service.predict_from_stats("dairy", stats)
    groups = pred["explanation"]["factor_groups"]
    assert len(groups) == 5

    group_names = {g["factor"] for g in groups}
    assert "Temperature exposure" in group_names
    assert "Humidity variation" in group_names
    assert "Journey duration" in group_names
    assert "Environmental violations" in group_names
    assert "Product category" in group_names


def test_public_features_formatting():
    """Verify public_features produces 8 expected keys with proper rounding and none handling."""
    from app.core.features import public_features
    stats = {
        "avg_temp": 4.123456,
        "max_temp": 7.987654,
        "avg_humidity": 52.333333,
        "temp_exposure_hours": 0.0,
        "humidity_exposure_hours": None,
        "journey_duration_hours": 6.5,
        "violation_count": 0,
    }
    pub = public_features("dairy", stats)
    assert pub["product_category"] == "dairy"
    assert pub["avg_temp"] == 4.123
    assert pub["max_temp"] == 7.988
    assert pub["humidity_exposure_hours"] is None



