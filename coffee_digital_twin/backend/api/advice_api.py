import json

from flask import Blueprint, jsonify, request

from database.init_db import get_connection, now_iso
from services.llm_service import generate_advice, chat_with_context
from services.result_store import select_result, SelectionError


advice_bp = Blueprint("advice_api", __name__, url_prefix="/api/advice")


def _load_latest_result(task_id=None, plot_id=None):
    """显式按任务或地块选择，不读取全局最新。"""
    return select_result(task_id,plot_id) or {}


@advice_bp.post("/generate")
def generate():
    # AI辅助生成-DeepSeek-V3 - 2026年5月2日 16:50:22 - 调度LLM生成结构化农技建议
    """
    一次性生成 what/how/why/model_basis 四段式建议。
    返回结构：
    {
      "status": "success",
      "task_id": "task_xxx",
      "advice": {
        "what": "...", "how": "...", "why": "...",
        "model_basis": {"apsim": "...", "hydrus": "...", "beps": "..."},
        "confidence_note": "...",
        "source": "glm-4-flash"
      },
      "mechanism_explanation": { ... }   // 三模型机理证据
    }
    """
    payload = request.get_json(silent=True) or {}
    task_id = payload.get("task_id")
    try:
        result = _load_latest_result(task_id,payload.get('plot_id'))
    except SelectionError as error:
        return jsonify(status='missing_input',missing_fields=['plot_id'],message=str(error)),400
    if not result:
        return jsonify(status='empty',missing_fields=['model_result']),404

    mechanism = result.get("mechanism_explanation", {})

    advice = generate_advice(
        result.get("apsim", {}),
        result.get("hydrus", {}),
        result.get("beps", {}),
        mechanism_evidence=mechanism,
    )

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO advice_logs (task_id, advice_json, created_at) VALUES (?, ?, ?)",
            (task_id or result.get("task_id"), json.dumps(advice, ensure_ascii=False), now_iso()),
        )

    return jsonify({
        "status": "success",
        "task_id": task_id,
        "advice": advice,
        "mechanism_explanation": mechanism,
        "result_selected_by": result['result_selected_by'],
        "result_created_at": result['result_created_at'],
    })


@advice_bp.post("/chat")
def chat():
    """
    多轮聊天接口。
    请求体：
      {
        "task_id": "xxx",           // 可选，未传必须指定plot_id
        "message": "用户消息",
        "history": [               // 前端维护的历史，每次完整传入
          {"role": "assistant", "content": "..."},
          {"role": "user",      "content": "..."}
        ]
      }
    返回：
      { "status": "success", "reply": "AI 回复内容" }
    """
    payload = request.get_json(silent=True) or {}
    task_id = payload.get("task_id")
    message = (payload.get("message") or "").strip()
    history = payload.get("history") or []

    if not message:
        return jsonify({"status": "error", "message": "message 不能为空"}), 400

    try:
        result = _load_latest_result(task_id,payload.get('plot_id'))
    except SelectionError as error:
        return jsonify(status='missing_input',missing_fields=['plot_id'],message=str(error)),400
    if not result:
        return jsonify(status='empty',missing_fields=['model_result']),404
    mechanism = result.get("mechanism_explanation", {})

    reply = chat_with_context(
        user_message     = message,
        history          = history,
        apsim_result     = result.get("apsim", {}),
        hydrus_result    = result.get("hydrus", {}),
        beps_result      = result.get("beps", {}),
        mechanism_evidence = mechanism,
    )

    return jsonify({"status": "success", "task_id": result.get('task_id'), "reply": reply,
                    'result_selected_by':result['result_selected_by'],'result_created_at':result['result_created_at']})
