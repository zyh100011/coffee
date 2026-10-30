import json
import math
from datetime import date

from flask import Blueprint, jsonify, request

from database.init_db import get_connection, now_iso


farmop_bp = Blueprint("farmop_api", __name__, url_prefix="/api/farmop")


@farmop_bp.post("/add")
def add_farm_operation():
    payload = request.get_json(silent=True) or {}
    with get_connection() as conn:
        plot_id = payload.get("plot_id")
        if not plot_id: return jsonify(status='error',code='E_PLOT_REQUIRED',message='请选择地块',retryable=False),400
        if not conn.execute('SELECT 1 FROM plots WHERE plot_id=?',(plot_id,)).fetchone(): return jsonify(status='error',code='E_PLOT_REQUIRED',message='地块不存在',retryable=False),400
        op_type = payload.get("op_type", "irrigation")
        op_date = payload.get("date") or payload.get("op_date")
        try:
            date.fromisoformat(op_date)
            if op_type not in ('irrigation','fertilization','pruning','pest'): raise ValueError('农事类型无效')
            if op_type in ('irrigation','fertilization'):
                if isinstance(payload.get('amount'),bool): raise ValueError('数量无效')
                amount=float(payload.get('amount'))
                if not math.isfinite(amount) or amount<=0: raise ValueError('数量须大于0')
                units={'irrigation':('mm','吨/亩'),'fertilization':('kg/亩','kg/ha','kg/mu')}
                if payload.get('unit') not in units[op_type]: raise ValueError('单位无效')
                payload['amount']=amount
        except (ValueError,TypeError): return jsonify(status='error',code='E_PARAM_INVALID',message='请核对日期、数量和单位',retryable=False),400
        payload['source']='user_record'
        cursor = conn.execute(
            """
            INSERT INTO farm_operations (
                plot_id, op_type, op_date, amount, unit, fertilizer_type,
                operation_type, severity, remark, raw_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plot_id,
                op_type,
                op_date,
                payload.get("amount"),
                payload.get("unit"),
                payload.get("fertilizer_type"),
                payload.get("operation_type"),
                payload.get("severity"),
                payload.get("remark"),
                json.dumps(payload, ensure_ascii=False),
                now_iso(),
            ),
        )
        op_id = cursor.lastrowid

    return jsonify({"status": "success", "id": op_id, "plot_id": plot_id})


@farmop_bp.get("/list")
def list_farm_operations():
    plot_id = request.args.get("plot_id")
    if not plot_id: return jsonify(status='error',code='E_PLOT_REQUIRED',message='请选择地块',retryable=False),400
    sql = "SELECT * FROM farm_operations"
    args = []
    if plot_id:
        sql += " WHERE plot_id = ?"
        args.append(plot_id)
    sql += " ORDER BY op_date DESC, id DESC"

    with get_connection() as conn:
        rows = conn.execute(sql, args).fetchall()
    return jsonify({"status": "success", "items": [dict(row) for row in rows]})
