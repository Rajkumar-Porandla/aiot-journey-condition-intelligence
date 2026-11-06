"""Shared helpers for request validation and API responses."""
from datetime import datetime, timezone

from flask import jsonify, request


class ApiError(Exception):
    """Raised for expected client errors; converted to a JSON response."""

    def __init__(self, message, status=400, fields=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.fields = fields or {}


def error_response(err: ApiError):
    body = {"error": err.message}
    if err.fields:
        body["fields"] = err.fields
    return jsonify(body), err.status


def get_json():
    data = request.get_json(silent=True)
    if data is None:
        raise ApiError("Request body must be valid JSON.", 400)
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object.", 400)
    return data


def parse_datetime(value, field):
    """Parse ISO-8601 input to a naive UTC datetime."""
    if not value or not isinstance(value, str):
        raise ApiError(f"{field} is required.", 400, {field: "Required (ISO 8601 date-time)."})
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ApiError(f"{field} is not a valid date-time.", 400, {field: "Invalid date-time."})
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def parse_float(data, field, required=True, min_value=None, max_value=None, default=None):
    value = data.get(field, default)
    if value is None or value == "":
        if required:
            raise ApiError(f"{field} is required.", 400, {field: "Required."})
        return default
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ApiError(f"{field} must be a number.", 400, {field: "Must be a number."})
    if value != value or value in (float("inf"), float("-inf")):
        raise ApiError(f"{field} must be a finite number.", 400, {field: "Must be finite."})
    if min_value is not None and value < min_value:
        raise ApiError(f"{field} must be >= {min_value}.", 400, {field: f"Minimum {min_value}."})
    if max_value is not None and value > max_value:
        raise ApiError(f"{field} must be <= {max_value}.", 400, {field: f"Maximum {max_value}."})
    return value


def parse_str(data, field, required=True, max_len=120, default=""):
    value = data.get(field, default)
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ApiError(f"{field} must be text.", 400, {field: "Must be text."})
    value = value.strip()
    if required and not value:
        raise ApiError(f"{field} is required.", 400, {field: "Required."})
    if len(value) > max_len:
        raise ApiError(f"{field} is too long (max {max_len}).", 400, {field: f"Max {max_len} characters."})
    return value


def parse_choice(data, field, choices, required=True, default=None):
    value = data.get(field, default)
    if value in (None, ""):
        if required:
            raise ApiError(f"{field} is required.", 400, {field: "Required."})
        return default
    if value not in choices:
        raise ApiError(
            f"{field} must be one of: {', '.join(map(str, choices))}.", 400, {field: "Invalid choice."}
        )
    return value

