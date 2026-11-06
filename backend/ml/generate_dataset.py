"""Synthetic journey dataset generator.

Run from the ``backend`` directory::

    python -m ml.generate_dataset            # 5,000 journeys (default)
    python -m ml.generate_dataset --journeys 8000 --seed 7

How it works
------------
1. For each synthetic journey a product category, simulation mode
   (NORMAL / WARNING / CRITICAL), intensity, expected duration and reading
   interval are sampled.
2. The journey is simulated with **the same sensor model used by the live
   application** (``app.core.sensor_model``) using the category's
   demonstration profile.
3. Snapshots are taken at ~35 %, ~65 % and 100 % of the journey (live
   predictions are also made mid-journey). All snapshots of one journey share
   a ``journey_id`` so the train/test split can be done *by journey*,
   preventing leakage between near-duplicate rows.
4. Each snapshot is summarised with ``app.core.exposure.analyze_readings`` and
   labelled with the documented formula in ``app.core.risk_formula``.

The output is written to ``ml/data/synthetic_journeys.csv``.
"""
import argparse
import math
import random
from pathlib import Path

import pandas as pd

from app.core import exposure, risk_formula, sensor_model
from app.core.features import NUMERIC_FEATURES
from app.core.product_defaults import CATEGORY_KEYS, default_profile

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_OUT = DATA_DIR / "synthetic_journeys.csv"

MODES = ["NORMAL", "WARNING", "CRITICAL"]
MODE_WEIGHTS = [0.33, 0.37, 0.30]
STEP_CHOICES = [5, 10, 15, 20, 30]
TRANSPORT = ["Refrigerated Truck", "Insulated Van", "Air Cargo", "Rail Reefer", "Sea Container"]
SNAPSHOT_FRACTIONS = (0.35, 0.65, 1.0)
DUMMY_ROUTE = {"source_lat": 17.385, "source_lon": 78.4867, "destination_lat": 19.076, "destination_lon": 72.8777}


def simulate_journey(rng: random.Random, journey_id: int) -> list:
    category = rng.choice(CATEGORY_KEYS)
    profile = default_profile(category)
    mode = rng.choices(MODES, MODE_WEIGHTS)[0]
    intensity = rng.uniform(0.5, 1.6)
    transport = rng.choice(TRANSPORT)
    # Log-uniform planned duration between 3 and 120 hours
    expected_hours = math.exp(rng.uniform(math.log(3), math.log(120)))
    step = rng.choice(STEP_CHOICES)
    expected_minutes = expected_hours * 60

    state = sensor_model.initial_state(profile, mode, rng, intensity=intensity)
    readings = []
    max_steps = int(expected_minutes * 2.5 / step) + 5
    while not sensor_model.is_complete(state) and len(readings) < max_steps:
        r = sensor_model.next_reading(state, profile, DUMMY_ROUTE, step, expected_minutes, rng)
        readings.append({"minutes": r["elapsed_minutes"], "temperature": r["temperature"], "humidity": r["humidity"]})

    rows = []
    n = len(readings)
    for frac in SNAPSHOT_FRACTIONS:
        k = max(4, int(round(n * frac)))
        if k > n:
            continue
        stats = exposure.analyze_readings(readings[:k], profile, default_step=step)
        score = risk_formula.risk_score(category, stats, noise=rng.gauss(0, 3.0))
        row = {
            "journey_id": journey_id,
            "snapshot": frac,
            "product_category": category,
            "simulation_mode": mode,
            "intensity": round(intensity, 3),
            "transport_type": transport,
            "step_minutes": step,
            "reading_count": k,
        }
        for f in NUMERIC_FEATURES:
            row[f] = round(stats[f], 4)
        row.update(
            {
                "temp_degree_hours": round(stats["temp_degree_hours"], 4),
                "humidity_pct_hours": round(stats["humidity_pct_hours"], 4),
                "longest_episode_hours": round(stats["longest_episode_hours"], 4),
                "risk_score": round(score, 3),
                "risk_class": risk_formula.risk_class(score),
            }
        )
        rows.append(row)
    return rows


def generate(n_journeys: int = 5000, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []
    for j in range(n_journeys):
        rows.extend(simulate_journey(rng, j))
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--journeys", type=int, default=5000, help="number of synthetic journeys (>= 5000 recommended)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    df = generate(args.journeys, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df):,} snapshot rows from {df['journey_id'].nunique():,} journeys -> {args.out}")
    print("Class distribution:")
    print(df["risk_class"].value_counts().to_string())
    print("Rows per category:")
    print(df["product_category"].value_counts().to_string())


if __name__ == "__main__":
    main()

