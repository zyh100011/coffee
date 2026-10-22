import json
from pathlib import Path


def test_ping(client):
    response = client.get("/api/ping")
    assert response.status_code == 200
    assert {"status", "message"} <= response.get_json().keys()
    assert response.get_json()["status"] == "ok"


def test_latest_plot_on_empty_database(client):
    response = client.get("/api/plot/latest")
    assert response.status_code == 200
    assert {"status", "plot"} <= response.get_json().keys()
    assert response.get_json()["plot"] is None


def test_farm_operation_list(client):
    response = client.get("/api/farmop/list", query_string={"plot_id": "smoke_plot"})
    assert response.status_code == 200
    assert {"status", "items"} <= response.get_json().keys()


def test_model_run_persists_result_without_running_engines(client, monkeypatch):
    from api import model_api

    demos = Path(__file__).resolve().parents[1] / "demo_data"
    calls = []

    def stub(tool):
        def run(model_input, **_dependencies):
            calls.append(tool)
            result = json.loads((demos / f"{tool}_result_demo.json").read_text(encoding="utf-8"))
            result.update(status="test_stub", task_id=model_input["task_id"],
                          plot_id=model_input["plot_id"], test_fixture=True)
            return result
        return run

    for tool in ("apsim", "hydrus", "beps"):
        monkeypatch.setattr(model_api, f"run_{tool}_model", stub(tool))
    # Use this test's database directory to isolate result JSON as well.
    from database import init_db as database
    monkeypatch.setattr(model_api, "RESULT_JSON_DIR", database.DATABASE_PATH.parent)

    plot = client.post("/api/plot/init", json={"plot_id": "smoke_plot", "plot_name": "测试地块"})
    assert plot.status_code == 200
    response = client.post("/api/model/run", json={"task_id": "smoke_task", "plot_id": "smoke_plot"})
    assert response.status_code == 200
    result = response.get_json()
    assert {"task_id", "plot_id", "apsim", "hydrus", "beps", "model_input"} <= result.keys()
    assert calls == ["apsim", "hydrus", "beps"]
    stored = client.get("/api/model/result/smoke_task")
    assert stored.status_code == 200
    assert stored.get_json()["plot_id"] == "smoke_plot"
