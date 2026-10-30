from flask import Flask, jsonify, request
import logging
from logging.handlers import RotatingFileHandler
from werkzeug.exceptions import HTTPException
from flask_cors import CORS

from api.advice_api import advice_bp
from api.farmop_api import farmop_bp
from api.model_api import model_bp
from api.model_info_api import model_info_bp
from api.plot_api import plot_bp
from api.result_api import result_bp
from api.data_api import data_bp
from api.assistant_api import assistant_bp
from api.report_api import report_bp
from api.scenario_api import scenario_bp
from config import DEBUG, HOST, PORT, SERVER_DIR, SINGLE_PLOT_ID, ensure_dirs
from services.errors import envelope
from database.init_db import init_db


def create_app():
    # AI辅助生成-DeepSeek-V3 - 2026年4月25日 10:30:15 - 初始化Flask应用与CORS配置
    ensure_dirs()
    init_db()

    app = Flask(__name__)
    app.config['SINGLE_PLOT_ID']=SINGLE_PLOT_ID
    CORS(app)

    @app.before_request
    def default_base():
        plot_id=app.config.get('SINGLE_PLOT_ID')
        if not plot_id or not request.path.startswith('/api/') or request.path=='/api/plot/init':return
        if request.method=='GET' and not request.args.get('plot_id'):
            args=request.args.copy();args['plot_id']=plot_id;request.args=args
        if request.method=='POST':
            payload=request.get_json(silent=True)
            if isinstance(payload,dict) and not payload.get('plot_id'):payload['plot_id']=plot_id
    log_path=SERVER_DIR/'logs'/'backend.log'
    if not any(isinstance(h,RotatingFileHandler) and h.baseFilename==str(log_path.resolve()) for h in app.logger.handlers):
        handler=RotatingFileHandler(log_path,maxBytes=2_000_000,backupCount=2,encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        app.logger.addHandler(handler)

    app.register_blueprint(plot_bp)
    app.register_blueprint(farmop_bp)
    app.register_blueprint(model_bp)
    app.register_blueprint(model_info_bp)
    app.register_blueprint(result_bp)
    app.register_blueprint(advice_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(assistant_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(scenario_bp)

    @app.get("/api/ping")
    def ping():
        return jsonify({
            "status": "ok",
            "message": "面向云南小粒咖啡的多机理模型（APSIM/HYDRUS/BEPS）协同智能决策系统 后端正在运行",
        })

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(envelope('E_DATA_EMPTY','接口或记录未找到')), 404

    @app.errorhandler(Exception)
    def server_error(error):
        if isinstance(error,HTTPException):
            return jsonify(envelope('E_PARAM_INVALID','请求格式或方法无效')),error.code
        body=envelope('E_INTERNAL')
        app.logger.error('Unhandled request trace_id=%s path=%s',body['trace_id'],request.path,exc_info=error)
        return jsonify(body),500

    @app.after_request
    def normalize_errors(response):
        if response.status_code>=400 and response.is_json:
            body=response.get_json()
            if isinstance(body,dict):
                code=body.get('code')
                if not code:
                    missing=body.get('missing_fields',[])
                    code='E_PLOT_REQUIRED' if 'plot_id' in missing else 'E_DATA_EMPTY' if response.status_code==404 or any(x in missing for x in ('observations','valid_observations')) else 'E_PARAM_INVALID' if response.status_code<500 else 'E_INTERNAL'
                body.update(envelope(code,body.get('message'),body.get('trace_id')))
                response.set_data(app.json.dumps(body))
        return response

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)
