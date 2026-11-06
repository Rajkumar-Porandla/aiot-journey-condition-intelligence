"""Train the two Random Forest models.

Run from the ``backend`` directory (after ``python -m ml.generate_dataset``)::

    python -m ml.train_models

Outputs (in ``ml/models``):

* ``risk_classifier.joblib`` - RandomForestClassifier -> Low / Medium / High Risk
* ``risk_regressor.joblib``  - RandomForestRegressor  -> risk score 0-100
* ``metrics.json``           - evaluation metrics, grouped permutation
  importance, dataset summary and model version

The train/test split is grouped by ``journey_id`` (GroupShuffleSplit) so that
snapshots of the same journey never appear in both sets.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_fscore_support,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import GroupShuffleSplit

from app.core.features import CATEGORY_FEATURES, FEATURE_LABELS, FEATURE_NAMES, NUMERIC_FEATURES, build_feature_row
from app.core.risk_formula import RISK_CLASSES

ML_DIR = Path(__file__).resolve().parent
DEFAULT_DATA = ML_DIR / "data" / "synthetic_journeys.csv"
DEFAULT_MODEL_DIR = ML_DIR / "models"

# Logical feature groups for permutation importance (one-hot category permuted jointly)
PERMUTATION_GROUPS = {name: [name] for name in NUMERIC_FEATURES}
PERMUTATION_GROUPS["product_category"] = CATEGORY_FEATURES


def build_matrix(df: pd.DataFrame) -> np.ndarray:
    return np.array([build_feature_row(row.product_category, row._asdict()) for row in df.itertuples(index=False)])


def grouped_permutation_importance(model, X, y, scorer, n_repeats=5, seed=0):
    """Mean drop in score when each logical feature group is shuffled."""
    rng = np.random.default_rng(seed)
    baseline = scorer(y, model.predict(X))
    results = {}
    for group, cols in PERMUTATION_GROUPS.items():
        idx = [FEATURE_NAMES.index(c) for c in cols]
        drops = []
        for _ in range(n_repeats):
            Xp = X.copy()
            perm = rng.permutation(len(Xp))
            Xp[:, idx] = Xp[perm][:, idx]
            drops.append(baseline - scorer(y, model.predict(Xp)))
        results[group] = {"mean": float(np.mean(drops)), "std": float(np.std(drops))}
    ordered = sorted(results.items(), key=lambda kv: kv[1]["mean"], reverse=True)
    return [
        {"feature": k, "label": FEATURE_LABELS.get(k, k), "importance": round(v["mean"], 5), "std": round(v["std"], 5)}
        for k, v in ordered
    ]


def train(data_path: Path, model_dir: Path, seed: int = 42, n_estimators: int = 150) -> dict:
    df = pd.read_csv(data_path)
    if df["journey_id"].nunique() < 5000:
        print(f"WARNING: only {df['journey_id'].nunique()} journeys; the project spec asks for >= 5,000.")

    X = build_matrix(df)
    y_cls = df["risk_class"].to_numpy()
    y_reg = df["risk_score"].to_numpy()
    groups = df["journey_id"].to_numpy()

    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    train_idx, test_idx = next(splitter.split(X, y_cls, groups))
    train_j, test_j = set(groups[train_idx]), set(groups[test_idx])
    assert not (train_j & test_j), "journey leakage between train and test sets"

    common = dict(n_estimators=n_estimators, min_samples_leaf=3, max_depth=16, random_state=seed, n_jobs=-1)
    clf = RandomForestClassifier(class_weight="balanced", **common)
    reg = RandomForestRegressor(**common)
    clf.fit(X[train_idx], y_cls[train_idx])
    reg.fit(X[train_idx], y_reg[train_idx])

    # ---------------- evaluation on held-out journeys
    Xt = X[test_idx]
    pred_cls = clf.predict(Xt)
    pred_reg = reg.predict(Xt)
    labels = list(RISK_CLASSES)
    p, r, f, s = precision_recall_fscore_support(y_cls[test_idx], pred_cls, labels=labels, zero_division=0)
    classification = {
        "accuracy": round(accuracy_score(y_cls[test_idx], pred_cls), 4),
        "precision_macro": round(precision_score(y_cls[test_idx], pred_cls, average="macro", zero_division=0), 4),
        "recall_macro": round(recall_score(y_cls[test_idx], pred_cls, average="macro", zero_division=0), 4),
        "f1_macro": round(f1_score(y_cls[test_idx], pred_cls, average="macro", zero_division=0), 4),
        "f1_weighted": round(f1_score(y_cls[test_idx], pred_cls, average="weighted", zero_division=0), 4),
        "per_class": [
            {"class": c, "precision": round(p[i], 4), "recall": round(r[i], 4), "f1": round(f[i], 4), "support": int(s[i])}
            for i, c in enumerate(labels)
        ],
        "confusion_matrix": {
            "labels": labels,
            "matrix": confusion_matrix(y_cls[test_idx], pred_cls, labels=labels).tolist(),
        },
    }
    regression = {
        "mae": round(mean_absolute_error(y_reg[test_idx], pred_reg), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_reg[test_idx], pred_reg))), 4),
        "r2": round(r2_score(y_reg[test_idx], pred_reg), 4),
    }

    importance = {
        "classifier": grouped_permutation_importance(clf, Xt, y_cls[test_idx], accuracy_score, seed=seed),
        "regressor": grouped_permutation_importance(reg, Xt, y_reg[test_idx], r2_score, seed=seed),
        "method": "Grouped permutation importance on held-out test journeys "
        "(drop in accuracy / R² when a feature is shuffled; one-hot category columns shuffled together).",
    }

    trained_at = datetime.now(timezone.utc)
    version = f"rf-{trained_at.strftime('%Y%m%d%H%M%S')}"
    metrics = {
        "model_version": version,
        "trained_at": trained_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sklearn_version": sklearn.__version__,
        "features": FEATURE_NAMES,
        "classes": [str(c) for c in clf.classes_],
        "hyperparameters": {k: v for k, v in common.items() if k != "n_jobs"},
        "dataset": {
            "path": str(data_path.name),
            "rows": int(len(df)),
            "journeys": int(df["journey_id"].nunique()),
            "train_rows": int(len(train_idx)),
            "test_rows": int(len(test_idx)),
            "train_journeys": len(train_j),
            "test_journeys": len(test_j),
            "split": "GroupShuffleSplit by journey_id (80/20), no journey in both sets",
            "class_distribution": {k: int(v) for k, v in df["risk_class"].value_counts().items()},
            "category_distribution": {k: int(v) for k, v in df["product_category"].value_counts().items()},
        },
        "classification": classification,
        "regression": regression,
        "permutation_importance": importance,
        "disclaimer": "Models are trained on SIMULATED journeys labelled by a documented formula. "
        "Outputs are environmental quality-risk estimates, not verified spoilage or safety assessments.",
    }

    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, model_dir / "risk_classifier.joblib", compress=3)
    joblib.dump(reg, model_dir / "risk_regressor.joblib", compress=3)
    (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--trees", type=int, default=150)
    args = parser.parse_args()
    if not args.data.exists():
        raise SystemExit(f"Dataset not found: {args.data}. Run `python -m ml.generate_dataset` first.")

    m = train(args.data, args.model_dir, args.seed, args.trees)
    c, r = m["classification"], m["regression"]
    print(f"Model version: {m['model_version']}")
    print(f"Train/test journeys: {m['dataset']['train_journeys']}/{m['dataset']['test_journeys']}")
    print(
        f"Classifier  accuracy={c['accuracy']:.3f} precision={c['precision_macro']:.3f} "
        f"recall={c['recall_macro']:.3f} F1={c['f1_macro']:.3f}"
    )
    print(f"Regressor   MAE={r['mae']:.2f} RMSE={r['rmse']:.2f} R²={r['r2']:.3f}")
    print("Top regressor drivers:", ", ".join(f"{i['label']} ({i['importance']:.3f})" for i in m["permutation_importance"]["regressor"][:4]))


if __name__ == "__main__":
    main()

