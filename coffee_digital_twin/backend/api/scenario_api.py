from flask import Blueprint, jsonify, request
from services.scenario_service import compare, ScenarioInputError
from services.errors import envelope

scenario_bp=Blueprint('scenario_api',__name__,url_prefix='/api/scenario')

@scenario_bp.post('/compare')
def scenario_compare():
    try: result=compare(request.get_json(silent=True))
    except ScenarioInputError as error:
        return jsonify(**envelope(error.code,str(error)),missing_fields=['scenario_inputs']),400
    return jsonify(result)
