"""Model feature definitions shared by training and inference."""
from .product_defaults import CATEGORY_KEYS

NUMERIC_FEATURES = [
    "avg_temp",
    "max_temp",
    "avg_humidity",
    "temp_exposure_hours",
    "humidity_exposure_hours",
    "journey_duration_hours",
    "violation_count",
]
CATEGORY_FEATURES = [f"cat_{c}" for c in CATEGORY_KEYS]
FEATURE_NAMES = NUMERIC_FEATURES + CATEGORY_FEATURES

FEATURE_LABELS = {
    "avg_temp": "Average temperature",
    "max_temp": "Maximum temperature",
    "avg_humidity": "Average humidity",
    "temp_exposure_hours": "Temperature exposure duration",
    "humidity_exposure_hours": "Humidity exposure duration",
    "journey_duration_hours": "Journey duration",
    "violation_count": "Number of violations",
    "product_category": "Product category",
}

# Groups used for the simplified "factor contribution" view
FACTOR_GROUPS = {
    "Temperature exposure": ["avg_temp", "max_temp", "temp_exposure_hours"],
    "Humidity variation": ["avg_humidity", "humidity_exposure_hours"],
    "Journey duration": ["journey_duration_hours"],
    "Environmental violations": ["violation_count"],
    "Product category": CATEGORY_FEATURES,
}


def build_feature_row(category: str, stats: dict) -> list:
    """Return the model input vector (ordered as FEATURE_NAMES)."""
    if category not in CATEGORY_KEYS:
        raise ValueError(f"Unknown product category: {category}")
    row = [float(stats[name]) for name in NUMERIC_FEATURES]
    row += [1.0 if c == category else 0.0 for c in CATEGORY_KEYS]
    return row


def public_features(category: str, stats: dict) -> dict:
    """Human-facing dict of the 8 model inputs (category + 7 numeric)."""
    out = {"product_category": category}
    for name in NUMERIC_FEATURES:
        val = stats.get(name)
        out[name] = round(float(val), 3) if val is not None else None
    return out

