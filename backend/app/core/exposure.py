"""Harmful exposure detection (pure logic, no database access).

Two entry points share the same rules:

* :class:`ExposureTracker` processes readings one at a time and emits
  alert create/update events. It is used by the live simulator.
* :func:`analyze_readings` summarises a complete list of readings into
  journey-level exposure statistics (used for ML features and reports).

Duration-aware severity
-----------------------
A reading outside the configured range starts (or extends) an *exposure
episode* for that violation type. Each episode gets a severity score::

    score = sensitivity_multiplier * (60 * min(deviation / range_span, 1.5) * type_weight
                                      + 12 * min(duration_hours, 6))

* ``deviation`` is the peak distance beyond the threshold in the episode.
* ``type_weight`` is 1.0 for temperature and 0.6 for humidity.
* ``sensitivity_multiplier``: Low 0.7, Medium 1.0, High 1.3, Very High 1.6.

Severity bands: Low < 20 <= Medium < 40 <= High < 65 <= Critical.

An alert is only raised once the episode lasts at least the product's
*grace period* (Low 45 min, Medium 30, High 15, Very High 0) **or** its score
already reaches the High band. Brief, small crossings are therefore still
counted as violations but do not flood the operator with alerts.
"""
from statistics import median

SENSITIVITY_MULTIPLIER = {"Low": 0.7, "Medium": 1.0, "High": 1.3, "Very High": 1.6}
GRACE_MINUTES = {"Low": 45, "Medium": 30, "High": 15, "Very High": 0}
TYPE_WEIGHT = {
    "TEMPERATURE_HIGH": 1.0,
    "TEMPERATURE_LOW": 1.0,
    "HUMIDITY_HIGH": 0.6,
    "HUMIDITY_LOW": 0.6,
}
SEVERITY_BANDS = ((65, "Critical"), (40, "High"), (20, "Medium"), (0, "Low"))
SEVERITY_ORDER = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
TYPE_LABELS = {
    "TEMPERATURE_HIGH": "High temperature exposure",
    "TEMPERATURE_LOW": "Low temperature violation",
    "HUMIDITY_HIGH": "High humidity exposure",
    "HUMIDITY_LOW": "Low humidity exposure",
}


def violations_for(temp: float, hum: float, profile: dict) -> dict:
    """Return {alert_type: (deviation, threshold)} for the violated limits."""
    out = {}
    if temp > profile["max_temp"]:
        out["TEMPERATURE_HIGH"] = (temp - profile["max_temp"], profile["max_temp"])
    elif temp < profile["min_temp"]:
        out["TEMPERATURE_LOW"] = (profile["min_temp"] - temp, profile["min_temp"])
    if hum > profile["max_humidity"]:
        out["HUMIDITY_HIGH"] = (hum - profile["max_humidity"], profile["max_humidity"])
    elif hum < profile["min_humidity"]:
        out["HUMIDITY_LOW"] = (profile["min_humidity"] - hum, profile["min_humidity"])
    return out


def severity_score(alert_type: str, peak_deviation: float, duration_minutes: float, profile: dict) -> float:
    if alert_type.startswith("TEMPERATURE"):
        span = max(profile["max_temp"] - profile["min_temp"], 1.0)
    else:
        span = max(profile["max_humidity"] - profile["min_humidity"], 1.0)
    mult = SENSITIVITY_MULTIPLIER.get(profile.get("sensitivity", "Medium"), 1.0)
    dev_term = 60.0 * min(peak_deviation / span, 1.5) * TYPE_WEIGHT[alert_type]
    dur_term = 12.0 * min(duration_minutes / 60.0, 6.0)
    return mult * (dev_term + dur_term)


def severity_from_score(score: float) -> str:
    for limit, label in SEVERITY_BANDS:
        if score >= limit:
            return label
    return "Low"


def should_alert(score: float, duration_minutes: float, profile: dict) -> bool:
    grace = GRACE_MINUTES.get(profile.get("sensitivity", "Medium"), 30)
    return duration_minutes >= grace or score >= 40


def describe(alert_type, peak_value, threshold, duration_minutes, severity, ongoing):
    unit = "°C" if alert_type.startswith("TEMPERATURE") else "% RH"
    direction = "above" if alert_type.endswith("HIGH") else "below"
    state = "ongoing" if ongoing else "ended"
    return (
        f"{TYPE_LABELS[alert_type]} ({state}): peak {peak_value:.1f}{unit} was "
        f"{abs(peak_value - threshold):.1f}{unit} {direction} the configured limit of "
        f"{threshold:g}{unit} for {duration_minutes:.0f} min of simulated journey time. "
        f"Severity rated {severity} using duration-aware, product-specific rules."
    )


class ExposureTracker:
    """Incremental episode tracker.

    ``state`` is a JSON-serialisable dict ``{alert_type: episode}`` stored by
    the caller between readings.
    """

    def __init__(self, profile: dict, state=None):
        self.profile = profile
        self.state = state if state is not None else {}

    def process(self, reading: dict, dt_minutes: float) -> list:
        """Process one reading; return a list of alert events.

        Each event is a dict with ``action`` = ``"create"`` | ``"update"`` | ``"close"``
        plus the alert fields. ``alert_ref`` links events to the same episode.
        """
        events = []
        active = violations_for(reading["temperature"], reading["humidity"], self.profile)
        ts = reading["timestamp"]

        # Close episodes that are no longer violated
        for alert_type in list(self.state.keys()):
            if alert_type not in active:
                ep = self.state.pop(alert_type)
                if ep.get("alerted"):
                    events.append(self._event("close", alert_type, ep, ts, ongoing=False))

        for alert_type, (deviation, threshold) in active.items():
            value = reading["temperature"] if alert_type.startswith("TEMPERATURE") else reading["humidity"]
            ep = self.state.get(alert_type)
            if ep is None:
                ep = {
                    "started_at": ts,
                    "duration": 0.0,
                    "peak_dev": 0.0,
                    "peak_value": value,
                    "threshold": threshold,
                    "alerted": False,
                    "severity": None,
                    "ref": None,
                }
                self.state[alert_type] = ep
            ep["duration"] += dt_minutes
            if deviation >= ep["peak_dev"]:
                ep["peak_dev"] = deviation
                ep["peak_value"] = value
            score = severity_score(alert_type, ep["peak_dev"], ep["duration"], self.profile)
            severity = severity_from_score(score)
            if not ep["alerted"]:
                if should_alert(score, ep["duration"], self.profile):
                    ep["alerted"] = True
                    ep["severity"] = severity
                    events.append(self._event("create", alert_type, ep, ts, ongoing=True))
            else:
                # Severity only escalates within an episode
                if SEVERITY_ORDER[severity] > SEVERITY_ORDER[ep["severity"]]:
                    ep["severity"] = severity
                events.append(self._event("update", alert_type, ep, ts, ongoing=True))
        return events

    def close_all(self, ts) -> list:
        events = []
        for alert_type in list(self.state.keys()):
            ep = self.state.pop(alert_type)
            if ep.get("alerted"):
                events.append(self._event("close", alert_type, ep, ts, ongoing=False))
        return events

    def _event(self, action, alert_type, ep, ts, ongoing):
        return {
            "action": action,
            "alert_type": alert_type,
            "episode": ep,
            "severity": ep["severity"],
            "recorded_value": ep["peak_value"],
            "threshold_value": ep["threshold"],
            "exposure_duration_minutes": ep["duration"],
            "started_at": ep["started_at"],
            "timestamp": ts,
            "is_active": ongoing,
            "description": describe(
                alert_type, ep["peak_value"], ep["threshold"], ep["duration"], ep["severity"], ongoing
            ),
        }


def reading_intervals(minutes: list, default_step: float = 15.0) -> list:
    """Duration (minutes) represented by each reading, from elapsed-minute marks."""
    n = len(minutes)
    if n == 0:
        return []
    if n == 1:
        return [default_step]
    diffs = [max(minutes[i] - minutes[i - 1], 0.0) for i in range(1, n)]
    first = median(diffs) if diffs else default_step
    return [first] + diffs


def analyze_readings(readings: list, profile: dict, default_step: float = 15.0) -> dict:
    """Summarise a journey's readings into exposure statistics.

    ``readings``: list of dicts with ``minutes`` (elapsed journey minutes),
    ``temperature`` and ``humidity``, ordered by time.
    """
    if not readings:
        return {
            "reading_count": 0,
            "avg_temp": None,
            "max_temp": None,
            "min_temp": None,
            "avg_humidity": None,
            "max_humidity": None,
            "min_humidity": None,
            "temp_exposure_hours": 0.0,
            "humidity_exposure_hours": 0.0,
            "journey_duration_hours": 0.0,
            "violation_count": 0,
            "temp_violation_count": 0,
            "humidity_violation_count": 0,
            "temp_degree_hours": 0.0,
            "humidity_pct_hours": 0.0,
            "max_temp_deviation": 0.0,
            "max_humidity_deviation": 0.0,
            "longest_episode_hours": 0.0,
            "warm_degree_hours": 0.0,
            "cold_degree_hours": 0.0,
        }

    dts = reading_intervals([r["minutes"] for r in readings], default_step)
    temps = [r["temperature"] for r in readings]
    hums = [r["humidity"] for r in readings]

    temp_exp = hum_exp = 0.0
    warm_dh = cold_dh = hum_ph = 0.0
    max_t_dev = max_h_dev = 0.0
    temp_episodes = hum_episodes = 0
    in_t = in_h = False
    cur_ep = {"T": 0.0, "H": 0.0}
    longest = 0.0

    for t, h, dt in zip(temps, hums, dts):
        dt_h = dt / 60.0
        v = violations_for(t, h, profile)
        t_viol = "TEMPERATURE_HIGH" in v or "TEMPERATURE_LOW" in v
        h_viol = "HUMIDITY_HIGH" in v or "HUMIDITY_LOW" in v
        if t_viol:
            temp_exp += dt_h
            if "TEMPERATURE_HIGH" in v:
                dev = v["TEMPERATURE_HIGH"][0]
                warm_dh += dev * dt_h
            else:
                dev = v["TEMPERATURE_LOW"][0]
                cold_dh += dev * dt_h
            max_t_dev = max(max_t_dev, dev)
            if not in_t:
                temp_episodes += 1
                cur_ep["T"] = 0.0
            cur_ep["T"] += dt_h
            longest = max(longest, cur_ep["T"])
        in_t = t_viol
        if h_viol:
            hum_exp += dt_h
            dev = v.get("HUMIDITY_HIGH", v.get("HUMIDITY_LOW"))[0]
            hum_ph += dev * dt_h
            max_h_dev = max(max_h_dev, dev)
            if not in_h:
                hum_episodes += 1
                cur_ep["H"] = 0.0
            cur_ep["H"] += dt_h
            longest = max(longest, cur_ep["H"])
        in_h = h_viol

    n = len(readings)
    return {
        "reading_count": n,
        "avg_temp": sum(temps) / n,
        "max_temp": max(temps),
        "min_temp": min(temps),
        "avg_humidity": sum(hums) / n,
        "max_humidity": max(hums),
        "min_humidity": min(hums),
        "temp_exposure_hours": temp_exp,
        "humidity_exposure_hours": hum_exp,
        "journey_duration_hours": sum(dts) / 60.0,
        "violation_count": temp_episodes + hum_episodes,
        "temp_violation_count": temp_episodes,
        "humidity_violation_count": hum_episodes,
        "temp_degree_hours": warm_dh + cold_dh,
        "warm_degree_hours": warm_dh,
        "cold_degree_hours": cold_dh,
        "humidity_pct_hours": hum_ph,
        "max_temp_deviation": max_t_dev,
        "max_humidity_deviation": max_h_dev,
        "longest_episode_hours": longest,
    }

