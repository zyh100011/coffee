import json
import uuid
import os
import re
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from config import RESULT_JSON_DIR
from database.init_db import get_connection, now_iso
from models.apsim_adapter import run_apsim_model
from models.beps_adapter import run_beps_model
from models.fusion_engine import merge
from models.hydrus_adapter import run_hydrus_model
from services.weather_service import get_observed_weather, get_demo_weather_series
from services.tool_registry import wrap_legacy_result, legacy_inputs


model_bp = Blueprint("model_api", __name__, url_prefix="/api/model")


def _row_json(row, key="raw_json"):
    return json.loads(row[key]) if row and row[key] else None


def _latest_plot(conn, plot_id=None):
    if plot_id:
        row = conn.execute("SELECT raw_json FROM plots WHERE plot_id = ?", (plot_id,)).fetchone()
    else:
        rows = conn.execute("SELECT raw_json FROM plots").fetchall()
        row = rows[0] if len(rows) == 1 else None
    if not row:
        raise ValueError('plot_id')
    return _row_json(row)


def _farm_operations(conn, plot_id):
    rows = conn.execute(
        "SELECT * FROM farm_operations WHERE plot_id = ? ORDER BY op_date ASC, id ASC",
        (plot_id,),
    ).fetchall()
    items = []
    for row in rows:
        items.append(
            {
                "op_type": row["op_type"],
                "date": row["op_date"],
                "amount": row["amount"],
                "unit": row["unit"],
                "fertilizer_type": row["fertilizer_type"],
                "operation_type": row["operation_type"],
                "severity": row["severity"],
                "remark": row["remark"],
            }
        )
    return items


def build_model_input(task_id, plot_id=None, scenario=None, start_date=None):
    with get_connection() as conn:
        plot = _latest_plot(conn, plot_id)
        operations = _farm_operations(conn, plot["plot_id"])

    start = (scenario or {}).get('start_date') or start_date or date.today().isoformat()
    end = (date.fromisoformat(start)+timedelta(days=6)).isoformat()
    weather = get_observed_weather(plot['plot_id'],start,end)
    source = 'observed' if weather else 'none'
    if not weather and os.getenv('ALLOW_DEMO_WEATHER','0') == '1':
        weather = get_demo_weather_series(plot.get('latitude'),plot.get('longitude'),start=start)
        source = 'demo'
    return {
        "task_id": task_id,
        "plot_id": plot["plot_id"],
        "crop": "coffee",
        "plot_info": plot,
        "start_date": start,
        "weather_series": weather,
        "data_sources": {'weather':source,'farm_operations':'db' if operations else 'none'},
        "missing_fields": ([] if operations else ['farm_operations']) + ([] if source=='observed' else ['observed_weather']),
        "warnings": [] if plot_id else ['未指定地块，使用唯一地块 '+plot['plot_id']],
        "farm_operations": operations,
        "scenario": scenario or {
            "scenario_name": "当前管理方案",
            "extra_irrigation_mm": 0,
            "extra_fertilizer_kg_mu": 0,
        },
    }


@model_bp.post("/run")
def run_model():
    payload = request.get_json(silent=True) or {}
    task_id = payload.get("task_id") or f"task_{uuid.uuid4().hex[:8]}"
    scenario = payload.get("scenario") or {}
    scenario.setdefault("scenario_name", payload.get("scenario_name", "当前管理方案"))
    scenario.setdefault("extra_irrigation_mm", payload.get("extra_irrigation_mm", 0))
    scenario.setdefault("extra_fertilizer_kg_mu", payload.get("extra_fertilizer_kg_mu", 0))

    if not isinstance(task_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',task_id):
        return jsonify(status='missing_input',missing_fields=['task_id']),400
    try:
        model_input = build_model_input(task_id, payload.get("plot_id"), scenario,payload.get('start_date'))
    except (ValueError,TypeError) as error:
        field = 'plot_id' if str(error)=='plot_id' else 'start_date'
        return jsonify(status='missing_input',missing_fields=[field],message='请提供有效的'+field),400
    timestamp = now_iso()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO model_tasks
            (task_id, plot_id, scenario_name, status, message, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                model_input["plot_id"],
                scenario.get("scenario_name"),
                "running",
                "model task started",
                timestamp,
                timestamp,
            ),
        )

    try:
        apsim_result = wrap_legacy_result('apsim',run_apsim_model(model_input),model_input)
        hydrus_result = run_hydrus_model(model_input)
        beps_raw = run_beps_model(model_input, apsim_result=legacy_inputs(apsim_result), hydrus_result=legacy_inputs(hydrus_result))
        beps_result = wrap_legacy_result('beps',beps_raw,{**model_input,'upstream':{
            'lai':apsim_result['evidence_id'] if legacy_inputs(apsim_result).get('lai') else None,
            'water_factor':hydrus_result.get('evidence_id') if legacy_inputs(hydrus_result).get('root_uptake_ratio') else None}})
        result = merge(
            apsim_result,
            hydrus_result,
            beps_result,
            task_id=task_id,
            plot_id=model_input["plot_id"],
        )
        result["model_input"] = model_input
        result_path = RESULT_JSON_DIR / f"{task_id}.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        with get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO model_results
                (task_id, plot_id, result_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    task_id,
                    model_input["plot_id"],
                    json.dumps(result, ensure_ascii=False),
                    now_iso(),
                ),
            )
            conn.execute(
                """
                UPDATE model_tasks
                SET status = ?, message = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (result['status'], "model task finished", now_iso(), task_id),
            )
            conn.execute('UPDATE model_tasks SET time_range_json=?,parameter_versions_json=? WHERE task_id=?',
                (json.dumps({'start':model_input['start_date'],'end':(date.fromisoformat(model_input['start_date'])+timedelta(days=7)).isoformat()}),
                 json.dumps({tool:result.get(tool,{}).get('parameter_version') for tool in ('apsim','hydrus','beps')}),task_id))
    except Exception as error:
        with get_connection() as conn:
            conn.execute(
                "UPDATE model_tasks SET status = ?, message = ?, updated_at = ? WHERE task_id = ?",
                ("failed", str(error), now_iso(), task_id),
            )
        raise

    return jsonify(result)


@model_bp.get("/status/<task_id>")
def model_status(task_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM model_tasks WHERE task_id = ?", (task_id,)).fetchone()
    if not row:
        return jsonify({"status": "not_found", "task_id": task_id}), 404
    return jsonify(dict(row))
