"""Pure-Python IoT sensor simulation model.

This module has no Flask / database dependency so that exactly the same
signal model is used by:

* the live background simulator (``app.services.simulation_engine``), and
* the synthetic training-data generator (``ml/generate_dataset.py``).

The simulator state is a plain JSON-serialisable ``dict`` so it can be
persisted in the database and resumed after pause or an application restart.

Signal model (per reading)
--------------------------
* Temperature and humidity follow a mean-reverting random walk
  (an AR(1) / Ornstein-Uhlenbeck-style process) around a set-point inside the
  product's configured range.
* WARNING / CRITICAL modes randomly trigger *excursion events*: the set-point
  temporarily moves outside the range, and the reading ramps towards it.
* Transport *delays* stop location progress for a while; in WARNING and
  CRITICAL modes delays also raise the probability of excursions
  (e.g. doors opened, reefer unit stressed while idling).
* Location is interpolated between source and destination with a gentle
  curved path plus GPS noise.

Rates are defined per 15-minute *reference interval* and rescaled to the
actual reading interval, so a journey sampled every 5 minutes behaves like
the same journey sampled every 30 minutes (just with more points).

All readings are SIMULATED. They are not real-world IoT measurements.
"""
import math
import random

REFERENCE_STEP_MINUTES = 15.0

# Behaviour of each simulation mode.
#   p_*        : probability of an event starting within a 15-minute interval
#   *_minutes  : (min, max) event duration in simulated minutes
#   *_mag      : (min, max) distance beyond the violated limit (°C or %RH)
MODE_PARAMS = {
    "NORMAL": {
        "p_temp_exc": 0.0,
        "p_hum_exc": 0.0,
        "temp_exc_minutes": (0, 0),
        "hum_exc_minutes": (0, 0),
        "temp_exc_mag": (0.0, 0.0),
        "hum_exc_mag": (0.0, 0.0),
        "p_delay": 0.01,
        "delay_minutes": (15, 45),
        "drift_per_hour": 0.0,
        "max_drift": 0.0,
    },
    "WARNING": {
        "p_temp_exc": 0.05,
        "p_hum_exc": 0.05,
        "temp_exc_minutes": (15, 45),
        "hum_exc_minutes": (15, 45),
        "temp_exc_mag": (0.5, 3.5),
        "hum_exc_mag": (2.0, 8.0),
        "p_delay": 0.03,
        "delay_minutes": (30, 75),
        "drift_per_hour": 0.0,
        "max_drift": 0.0,
    },
    "CRITICAL": {
        "p_temp_exc": 0.14,
        "p_hum_exc": 0.11,
        "temp_exc_minutes": (45, 150),
        "hum_exc_minutes": (45, 120),
        "temp_exc_mag": (2.0, 8.0),
        "hum_exc_mag": (5.0, 15.0),
        "p_delay": 0.06,
        "delay_minutes": (45, 120),
        # Gradual cooling-unit degradation: set-point creeps upward (°C / hour)
        "drift_per_hour": 0.12,
        "max_drift": 6.0,
    },
}


def _interp(a, b, t):
    return a + (b - a) * t


def _scaled_prob(p_ref, k):
    """Probability over an interval k times the reference interval."""
    if p_ref <= 0:
        return 0.0
    return 1.0 - (1.0 - min(p_ref, 0.999)) ** k


def initial_state(profile: dict, mode: str, rng: random.Random, intensity: float = 1.0) -> dict:
    """Create the starting simulator state for a journey."""
    if mode not in MODE_PARAMS:
        raise ValueError(f"Unknown simulation mode: {mode}")
    t_span = profile["max_temp"] - profile["min_temp"]
    h_span = profile["max_humidity"] - profile["min_humidity"]
    t_mid = (profile["max_temp"] + profile["min_temp"]) / 2
    h_mid = (profile["max_humidity"] + profile["min_humidity"]) / 2
    # Per-journey set-point offset (each truck / container behaves slightly differently)
    t_set = t_mid + rng.uniform(-0.2, 0.2) * t_span
    h_set = h_mid + rng.uniform(-0.2, 0.2) * h_span
    return {
        "mode": mode,
        "intensity": float(intensity),
        "temp": t_set + rng.gauss(0, 0.05 * t_span),
        "hum": h_set + rng.gauss(0, 0.05 * h_span),
        "temp_setpoint": t_set,
        "hum_setpoint": h_set,
        "drift": 0.0,
        "progress": 0.0,
        "elapsed_minutes": 0.0,
        "sequence": 0,
        "temp_exc_remaining": 0.0,  # minutes
        "temp_exc_target": None,
        "hum_exc_remaining": 0.0,
        "hum_exc_target": None,
        "delay_remaining": 0.0,
        "route_curve": rng.uniform(-0.08, 0.08),
    }


def _maybe_start_events(state, profile, params, rng, k):
    intensity = state.get("intensity", 1.0)
    delay_factor = 2.0 if state["delay_remaining"] > 0 else 1.0

    if state["temp_exc_remaining"] <= 0 and params["p_temp_exc"] > 0:
        if rng.random() < _scaled_prob(params["p_temp_exc"] * intensity * delay_factor, k):
            state["temp_exc_remaining"] = rng.uniform(*params["temp_exc_minutes"])
            mag = rng.uniform(*params["temp_exc_mag"]) * intensity
            if rng.random() < 0.8:  # warm excursions are far more common
                state["temp_exc_target"] = profile["max_temp"] + mag
            else:
                state["temp_exc_target"] = profile["min_temp"] - mag

    if state["hum_exc_remaining"] <= 0 and params["p_hum_exc"] > 0:
        if rng.random() < _scaled_prob(params["p_hum_exc"] * intensity * delay_factor, k):
            state["hum_exc_remaining"] = rng.uniform(*params["hum_exc_minutes"])
            mag = rng.uniform(*params["hum_exc_mag"]) * intensity
            if rng.random() < 0.5:
                state["hum_exc_target"] = min(100.0, profile["max_humidity"] + mag)
            else:
                state["hum_exc_target"] = max(5.0, profile["min_humidity"] - mag)

    if state["delay_remaining"] <= 0 and rng.random() < _scaled_prob(params["p_delay"], k):
        state["delay_remaining"] = rng.uniform(*params["delay_minutes"])


def next_reading(
    state: dict,
    profile: dict,
    route: dict,
    step_minutes: float,
    expected_duration_minutes: float,
    rng: random.Random,
) -> dict:
    """Advance the simulator by one reading.

    ``state`` is mutated in place. Returns a reading dict with keys
    ``temperature, humidity, latitude, longitude, progress, is_delayed,
    elapsed_minutes, sequence``.
    """
    mode = state["mode"]
    params = MODE_PARAMS[mode]
    t_min, t_max = profile["min_temp"], profile["max_temp"]
    h_min, h_max = profile["min_humidity"], profile["max_humidity"]
    t_span = max(t_max - t_min, 0.5)
    h_span = max(h_max - h_min, 1.0)
    k = step_minutes / REFERENCE_STEP_MINUTES
    noise_k = math.sqrt(min(k, 4.0))

    _maybe_start_events(state, profile, params, rng, k)

    # ---------------- temperature
    state["drift"] = min(
        params["max_drift"],
        state["drift"] + params["drift_per_hour"] * state.get("intensity", 1.0) * step_minutes / 60.0,
    )
    if state["temp_exc_remaining"] > 0:
        target, alpha_ref = state["temp_exc_target"], 0.55
        state["temp_exc_remaining"] -= step_minutes
    else:
        target, alpha_ref = state["temp_setpoint"] + state["drift"], 0.35
    alpha = 1.0 - (1.0 - alpha_ref) ** k
    temp = state["temp"] + alpha * (target - state["temp"]) + rng.gauss(0, 0.05 * t_span * noise_k)
    if mode == "NORMAL":
        # NORMAL mode: conditions are kept inside the configured range
        temp = min(max(temp, t_min + 0.05 * t_span), t_max - 0.05 * t_span)
    state["temp"] = temp

    # ---------------- humidity
    if state["hum_exc_remaining"] > 0:
        h_target, h_alpha_ref = state["hum_exc_target"], 0.55
        state["hum_exc_remaining"] -= step_minutes
    else:
        h_target, h_alpha_ref = state["hum_setpoint"], 0.3
    h_alpha = 1.0 - (1.0 - h_alpha_ref) ** k
    hum = state["hum"] + h_alpha * (h_target - state["hum"]) + rng.gauss(0, 0.04 * h_span * noise_k)
    if mode == "NORMAL":
        hum = min(max(hum, h_min + 0.05 * h_span), h_max - 0.05 * h_span)
    hum = min(max(hum, 0.0), 100.0)
    state["hum"] = hum

    # ---------------- movement / delays
    is_delayed = state["delay_remaining"] > 0
    if is_delayed:
        state["delay_remaining"] -= step_minutes
    else:
        speed = min(max(rng.gauss(1.0, 0.12), 0.6), 1.35)
        state["progress"] = min(
            1.0, state["progress"] + speed * step_minutes / max(expected_duration_minutes, step_minutes)
        )
    p = state["progress"]
    lat = _interp(route["source_lat"], route["destination_lat"], p)
    lon = _interp(route["source_lon"], route["destination_lon"], p)
    # Curved path: offset perpendicular to the straight line, zero at both ends
    d_lat = route["destination_lat"] - route["source_lat"]
    d_lon = route["destination_lon"] - route["source_lon"]
    bend = state.get("route_curve", 0.0) * math.sin(math.pi * p)
    lat += -d_lon * bend + rng.gauss(0, 0.0015)
    lon += d_lat * bend + rng.gauss(0, 0.0015)

    state["elapsed_minutes"] += step_minutes
    state["sequence"] += 1

    return {
        "sequence": state["sequence"],
        "temperature": round(temp, 2),
        "humidity": round(hum, 2),
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "progress": round(p, 4),
        "is_delayed": is_delayed,
        "elapsed_minutes": state["elapsed_minutes"],
    }


def is_complete(state: dict) -> bool:
    return state["progress"] >= 1.0
