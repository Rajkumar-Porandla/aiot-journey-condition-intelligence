"""Documented synthetic risk-target formula.

Used ONLY to label the synthetic training dataset (``ml/generate_dataset.py``).
The live application never calls this formula to produce predictions; live
predictions come from the trained Random Forest models.

Formula (all components are in 0-100)::

    S_temp  = 100 * (1 - exp(-(warm_dh * w_warm + cold_dh * w_cold) / K_temp))
    S_hum   = 100 * (1 - exp(-humidity_pct_hours / K_hum))
    S_peak  = 100 * min(1, max_temp_deviation / peak_tolerance)
    S_dur   = 100 * min(1, journey_hours / freshness_window_hours)
    S_viol  = 100 * min(1, violation_count / 8)
    S_long  = 100 * min(1, longest_episode_hours / 6)

    risk = 0.40*S_temp + 0.17*S_hum + 0.13*S_peak + 0.10*S_dur + 0.10*S_viol + 0.10*S_long
           + Normal(0, 3)   (unmodelled variability), clipped to [0, 100]

    Low Risk < 35 <= Medium Risk < 65 <= High Risk

``warm_dh`` / ``cold_dh`` are degree-hours above the maximum / below the
minimum temperature, ``humidity_pct_hours`` is %RH-hours outside the humidity
range. The per-category constants below encode that, e.g., pharmaceuticals
tolerate far fewer degree-hours than fresh produce, and that colder-than-range
exposure matters little for frozen goods but a lot for medicines (freezing).

These constants are demonstration assumptions, not validated spoilage models.
"""
import math

CATEGORY_RISK_PARAMS = {
    #                  K_temp  K_hum  peak_tol  window_h  w_warm  w_cold
    "fruits_vegetables": dict(K_temp=10.0, K_hum=80.0, peak_tol=6.0, window_h=96.0, w_warm=1.0, w_cold=0.8),
    "dairy": dict(K_temp=5.0, K_hum=150.0, peak_tol=4.0, window_h=72.0, w_warm=1.0, w_cold=0.5),
    "frozen": dict(K_temp=4.0, K_hum=250.0, peak_tol=5.0, window_h=240.0, w_warm=1.0, w_cold=0.2),
    "pharmaceutical": dict(K_temp=2.5, K_hum=60.0, peak_tol=3.0, window_h=168.0, w_warm=1.0, w_cold=1.2),
    "flowers": dict(K_temp=6.0, K_hum=60.0, peak_tol=5.0, window_h=72.0, w_warm=1.0, w_cold=0.7),
}

WEIGHTS = {"temp": 0.40, "hum": 0.17, "peak": 0.13, "dur": 0.10, "viol": 0.10, "long": 0.10}
CLASS_THRESHOLDS = (35.0, 65.0)
RISK_CLASSES = ("Low Risk", "Medium Risk", "High Risk")


def risk_components(category: str, stats: dict) -> dict:
    p = CATEGORY_RISK_PARAMS[category]
    eff_dh = stats["warm_degree_hours"] * p["w_warm"] + stats["cold_degree_hours"] * p["w_cold"]
    return {
        "temp": 100.0 * (1 - math.exp(-eff_dh / p["K_temp"])),
        "hum": 100.0 * (1 - math.exp(-stats["humidity_pct_hours"] / p["K_hum"])),
        "peak": 100.0 * min(1.0, stats["max_temp_deviation"] / p["peak_tol"]),
        "dur": 100.0 * min(1.0, stats["journey_duration_hours"] / p["window_h"]),
        "viol": 100.0 * min(1.0, stats["violation_count"] / 8.0),
        "long": 100.0 * min(1.0, stats["longest_episode_hours"] / 6.0),
    }


def risk_score(category: str, stats: dict, noise: float = 0.0) -> float:
    comps = risk_components(category, stats)
    score = sum(WEIGHTS[k] * v for k, v in comps.items()) + noise
    return max(0.0, min(100.0, score))


def risk_class(score: float) -> str:
    if score < CLASS_THRESHOLDS[0]:
        return RISK_CLASSES[0]
    if score < CLASS_THRESHOLDS[1]:
        return RISK_CLASSES[1]
    return RISK_CLASSES[2]

