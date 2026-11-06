"""Loading the trained models and producing explained predictions.

Predictions always come from the persisted scikit-learn models; nothing here
hard-codes a risk class or score.
"""
import json
import logging
import threading

import joblib
import numpy as np
import sklearn

from ..core.explain import tree_contributions
from ..core.features import (
    CATEGORY_FEATURES,
    FACTOR_GROUPS,
    FEATURE_LABELS,
    FEATURE_NAMES,
    NUMERIC_FEATURES,
    build_feature_row,
    public_features,
)
from ..core.product_defaults import category_label

log = logging.getLogger(__name__)

DISCLAIMER = (
    "Simulated-data-based environmental quality risk estimate produced by a model trained on "
    "synthetic journeys. It is not an experimentally verified spoilage or safety assessment."
)
UNITS = {
    "avg_temp": "°C",
    "max_temp": "°C",
    "avg_humidity": "% RH",
    "temp_exposure_hours": "h",
    "humidity_exposure_hours": "h",
    "journey_duration_hours": "h",
    "violation_count": "",
}


class ModelUnavailable(RuntimeError):
    pass


class _Models:
    def __init__(self):
        self.lock = threading.Lock()
        self.classifier = None
        self.regressor = None
        self.metrics = None
        self.model_dir = None
        self.error = None

    def load(self, model_dir):
        with self.lock:
            self.model_dir = model_dir
            try:
                clf = joblib.load(model_dir / "risk_classifier.joblib")
                reg = joblib.load(model_dir / "risk_regressor.joblib")
                metrics = json.loads((model_dir / "metrics.json").read_text())
            except FileNotFoundError:
                self.classifier = self.regressor = self.metrics = None
                self.error = (
                    "Trained models not found. From the backend folder run "
                    "`python -m ml.generate_dataset` and `python -m ml.train_models`."
                )
                log.warning(self.error)
                return False
            if list(metrics.get("features", [])) != FEATURE_NAMES:
                self.classifier = self.regressor = self.metrics = None
                self.error = "Saved models use a different feature set. Please retrain (`python -m ml.train_models`)."
                log.error(self.error)
                return False
            if metrics.get("sklearn_version") != sklearn.__version__:
                log.warning(
                    "Models were trained with scikit-learn %s but %s is installed; retrain if predictions fail.",
                    metrics.get("sklearn_version"),
                    sklearn.__version__,
                )
            for est in (clf, reg):
                if hasattr(est, "n_jobs"):
                    est.n_jobs = 1  # single-row inference is faster without process pools
            self.classifier, self.regressor, self.metrics, self.error = clf, reg, metrics, None
            log.info("Loaded ML models %s", metrics.get("model_version"))
            return True

    def require(self):
        if self.classifier is None or self.regressor is None:
            raise ModelUnavailable(self.error or "Models are not loaded.")
        return self.classifier, self.regressor, self.metrics


models = _Models()


def init_app(app):
    models.load(app.config["MODEL_DIR"])


def model_info():
    _, _, metrics = models.require()
    return metrics


def _contribution_list(contrib, x_row, category):
    """Per logical feature contribution (category one-hots merged)."""
    items = []
    for i, name in enumerate(NUMERIC_FEATURES):
        items.append(
            {
                "feature": name,
                "label": FEATURE_LABELS[name],
                "value": round(float(x_row[i]), 3),
                "unit": UNITS[name],
                "contribution": round(float(contrib[i]), 4),
            }
        )
    cat_idx = [FEATURE_NAMES.index(c) for c in CATEGORY_FEATURES]
    items.append(
        {
            "feature": "product_category",
            "label": FEATURE_LABELS["product_category"],
            "value": category_label(category),
            "unit": "",
            "contribution": round(float(np.sum(contrib[cat_idx])), 4),
        }
    )
    items.sort(key=lambda d: abs(d["contribution"]), reverse=True)
    return items


def _factor_groups(contrib):
    out = []
    for group, names in FACTOR_GROUPS.items():
        idx = [FEATURE_NAMES.index(n) for n in names]
        out.append({"factor": group, "contribution": round(float(np.sum(contrib[idx])), 3)})
    return out


def _summary_sentences(score_items, base, score):
    sentences = [
        f"The model's average risk score over the training journeys is {base:.1f}; "
        f"this journey is estimated at {score:.1f}."
    ]
    for item in score_items[:3]:
        c = item["contribution"]
        if abs(c) < 0.5:
            continue
        direction = "raised" if c > 0 else "lowered"
        value = item["value"] if isinstance(item["value"], str) else f"{item['value']:g}{(' ' + item['unit']) if item['unit'] else ''}"
        sentences.append(f"{item['label']} ({value}) {direction} the risk score by {abs(c):.1f} points.")
    return sentences


def predict_from_stats(category: str, stats: dict) -> dict:
    """Run both models on journey statistics and return an explained prediction."""
    clf, reg, metrics = models.require()
    x_row = build_feature_row(category, stats)
    X = np.array([x_row], dtype=np.float64)

    proba = clf.predict_proba(X)[0]
    classes = [str(c) for c in clf.classes_]
    class_idx = int(np.argmax(proba))
    risk_class = classes[class_idx]
    score = float(np.clip(reg.predict(X)[0], 0.0, 100.0))

    reg_base, reg_contrib = tree_contributions(reg, x_row)
    clf_base, clf_contrib = tree_contributions(clf, x_row)

    score_items = _contribution_list(reg_contrib, x_row, category)
    class_items = _contribution_list(clf_contrib[:, class_idx] * 100.0, x_row, category)

    explanation = {
        "method": "Tree path contributions (Saabas) computed from the trained Random Forests; "
        "prediction = base value + sum of feature contributions.",
        "score_base": round(reg_base, 3),
        "score_contributions": score_items,
        "factor_groups": _factor_groups(reg_contrib),
        "class_name": risk_class,
        "class_base_probability": round(float(clf_base[class_idx]) * 100.0, 2),
        "class_contributions": class_items,
        "summary": _summary_sentences(score_items, reg_base, score),
    }
    return {
        "risk_class": risk_class,
        "class_probabilities": {c: round(float(p), 4) for c, p in zip(classes, proba)},
        "risk_score": round(score, 2),
        "features": public_features(category, stats),
        "explanation": explanation,
        "model_version": metrics.get("model_version", "unknown"),
        "disclaimer": DISCLAIMER,
    }

