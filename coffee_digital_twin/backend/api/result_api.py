from flask import Blueprint, jsonify, request
from services.result_store import select_result, SelectionError

result_bp = Blueprint('result_api', __name__, url_prefix='/api')


def selected(task_id=None):
    try:
        result = select_result(task_id or request.args.get('task_id'), request.args.get('plot_id'))
    except SelectionError as error:
        return None, (jsonify(status='missing_input',missing_fields=['plot_id'],message=str(error)),400)
    if not result:
        return None, (jsonify(status='empty',missing_fields=['model_result'],dashboard={}),404)
    return result, None


@result_bp.get('/model/result/<task_id>')
def model_result(task_id):
    result,error=selected(task_id)
    return error or jsonify(result)


@result_bp.get('/model/result')
def latest_plot_result():
    result,error=selected()
    return error or jsonify(result)


@result_bp.get('/dashboard')
def dashboard():
    # AI辅助生成-DeepSeek-V3 - 2026年4月30日 11:15:00 - 返回数字孪生控制台的综合聚合数据
    result,error=selected()
    return error or jsonify(result)