"""Unified provenance envelope; missing data stays missing."""
from datetime import date, datetime, timezone
import uuid

from jsonschema import Draft202012Validator


STATUSES = ["success", "missing_input", "timeout", "failed", "fallback", "replay"]
SOURCES = ["observation", "literature", "simulation_uncalibrated", "proxy_model", "simplified_model", "demo"]
SCHEMA = {"type": "object", "required": ["tool", "task_id", "plot_id", "time_range", "status", "source_type",
          "model_version", "parameter_version", "inputs", "assumptions", "outputs", "units", "missing_fields",
          "warnings", "evidence_id", "created_at", "mode"], "properties": {
    "tool": {"enum": ["hydrus", "apsim", "beps", "data_query", "plot_profile"]},
    "task_id": {"type": "string", "minLength": 1}, "plot_id": {"type": ["string", "null"]},
    "time_range": {"type": "object", "required": ["start", "end"], "properties": {
        "start": {"type": ["string", "null"]}, "end": {"type": ["string", "null"]}}},
    "status": {"enum": STATUSES}, "source_type": {"enum": SOURCES},
    "model_version": {"type": "string"}, "parameter_version": {"type": "string"},
    **{key: {"type": "object"} for key in ("inputs", "outputs", "units")},
    **{key: {"type": "array", "items": {"type": "string"}} for key in ("assumptions", "missing_fields", "warnings")},
    "evidence_id": {"type": "string", "minLength": 1}, "created_at": {"type": "string"},
    "mode": {"enum": ["live", "replay"]}}}


def make_tool_result(**kw):
    tool = kw.pop("tool")
    task_id = kw.pop("task_id", None) or "task_" + uuid.uuid4().hex
    result = {"tool": tool, "task_id": task_id, "plot_id": None,
              "time_range": {"start": None, "end": None}, "status": "failed", "source_type": "observation",
              "model_version": "", "parameter_version": "", "inputs": {}, "assumptions": [], "outputs": {},
              "units": {}, "missing_fields": [], "warnings": [],
              "evidence_id": f"ev_{tool}_{task_id}_{uuid.uuid4().hex}",
              "created_at": datetime.now(timezone.utc).isoformat(), "mode": "live"}
    result.update(kw)
    return result


def validate_tool_result(result):
    errors = [f"{'.'.join(map(str, error.path))}: {error.message}" for error in Draft202012Validator(SCHEMA).iter_errors(result)]
    if not isinstance(result, dict):
        return errors
    dates = result.get("time_range", {})
    if not isinstance(dates,dict):
        return errors
    for key in ("start", "end"):
        value = dates.get(key)
        if value is not None:
            try:
                date.fromisoformat(value)
            except (ValueError, TypeError):
                errors.append(f"time_range.{key}: expected ISO date")
    if isinstance(dates.get('start'),str) and isinstance(dates.get('end'),str) and dates['start'] > dates['end']:
        errors.append("time_range: start > end")
    if result.get("status") in {"failed", "timeout", "missing_input"} and result.get("outputs"):
        errors.append("unavailable results must not contain numeric outputs")
    return errors
