from pathlib import Path
import subprocess

import pytest

from models import hydrus_adapter as hydrus
from services.tool_result import validate_tool_result


@pytest.fixture(autouse=True)
def isolate_hydrus(monkeypatch, tmp_path):
    monkeypatch.setattr(hydrus, "HYDRUS_RUN_DIR", tmp_path)
    monkeypatch.setattr(hydrus, "HYDRUS_MODE", "live")
    monkeypatch.setattr(hydrus, "ALLOW_DEMO_FALLBACK", False)


def test_missing_date_does_not_execute(monkeypatch):
    monkeypatch.setattr(hydrus, "_execute_engine", lambda *args: pytest.fail("must not run"))
    result = hydrus.run_hydrus_model({})
    assert result["status"] == "missing_input"
    assert result["missing_fields"] == ["start_date"]
    assert not validate_tool_result(result)


def test_missing_engine_and_explicit_demo(monkeypatch, tmp_path):
    monkeypatch.setattr(hydrus, "HYDRUS_EXE", tmp_path / "not_here.exe")
    data = {"start_date": "2026-09-01"}
    result = hydrus.run_hydrus_model(data)
    assert result["status"] == "failed" and result["outputs"] == {}
    monkeypatch.setattr(hydrus, "ALLOW_DEMO_FALLBACK", True)
    demo = hydrus.run_hydrus_model(data)
    assert demo["status"] == "fallback" and demo["source_type"] == "demo"


def test_daily_input_ignores_outside_window_and_demo_rain(monkeypatch):
    monkeypatch.setattr(hydrus, "_execute_engine", lambda *args: (_ for _ in ()).throw(RuntimeError("inspection only")))
    result = hydrus.run_hydrus_model({"start_date": "2026-09-01", "scenario": {"extra_irrigation_mm": 20},
        "farm_operations": [{"op_type": "irrigation", "date": "2026-08-01", "amount": 99, "unit": "mm"},
                            {"op_type": "irrigation", "date": "2026-09-02", "amount": 10, "unit": "mm"}],
        "weather_series": [{"date": "2026-09-01", "rain_mm": 99, "source": "demo"},
                           {"date": "2026-09-03", "rain_mm": 5, "source": "observation"}]})
    assert result["inputs"]["daily_prec_cm"] == [2, 1, .5, 0, 0, 0, 0]
    assert result["inputs"]["rsoil_cm_d"] == [.15]*7
    assert result["status"] == "failed"


def test_timeout_and_unsafe_task_id(monkeypatch):
    monkeypatch.setattr(hydrus, "_execute_engine", lambda *args: (_ for _ in ()).throw(subprocess.TimeoutExpired("fixture", 1)))
    result = hydrus.run_hydrus_model({"start_date": "2026-09-01"})
    assert result["status"] == "timeout" and not result["outputs"]
    result = hydrus.run_hydrus_model({"task_id": "../escape", "start_date": "2026-09-01"})
    assert result["status"] == "missing_input"


@pytest.mark.skipif(__import__("os").name != "nt", reason="Windows engine regression")
def test_live_regression_and_eight_profiles():
    result = hydrus.run_hydrus_model({"start_date": "2026-09-01", "weather_series": [
        {"date": "2026-09-01", "source": "observation", "rain_mm": 61}]})
    assert result["status"] == "success", result["warnings"]
    assert not validate_tool_result(result)
    assert len(result["outputs"]["soil_moisture_series"]) == 8
    theta = result["outputs"]["soil_moisture_series"][-1]["d40"]
    assert abs(theta-.1935) < .002
    assert result["inputs"]["daily_prec_cm"] == [6.1, 0, 0, 0, 0, 0, 0]
    assert result["outputs"]["soil_moisture_series"][-1]["date"] == "2026-09-08"


def test_replay_keeps_historical_date_plot_and_origin(monkeypatch):
    monkeypatch.setattr(hydrus, "HYDRUS_MODE", "replay")
    result = hydrus.run_hydrus_model({"plot_id": "current_plot", "start_date": "2026-10-14"})
    assert result["status"] == "replay"
    assert result["time_range"]["start"] == "2026-09-01"
    assert result["plot_id"] is None
    assert result["inputs"]["requested_plot_id"] == "current_plot"
    assert result["inputs"]["replay_origin_evidence_id"]
