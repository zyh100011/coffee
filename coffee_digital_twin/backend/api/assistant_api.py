from flask import Blueprint,jsonify,request
from services.assistant_service import chat
from services import evidence_client
from services.trace_store import lookup
from database.init_db import get_connection
from config import HYDRUS_MODE
assistant_bp=Blueprint('assistant_api',__name__,url_prefix='/api')
@assistant_bp.post('/assistant/chat')
def assistant_chat():
    p=request.get_json(silent=True)
    if not isinstance(p,dict) or not isinstance(p.get('message'),str) or not p['message'].strip() or len(p['message'])>4000:
        return jsonify(status='error',code='E_PARAM_INVALID',message='请提供1–4000字符的非空问题',retryable=False),400
    if p.get('entry_mode','auto') not in ('auto','knowledge'):
        return jsonify(status='error',code='E_PARAM_INVALID',message='问答入口无效',retryable=False),400
    if (p.get('session_id') is not None and not isinstance(p['session_id'],str)) or (p.get('plot_id') is not None and not isinstance(p['plot_id'],str)) or not isinstance(p.get('history',[]),list) or (p.get('supplement') is not None and not isinstance(p['supplement'],(str,dict))):
        return jsonify(status='error',code='E_PARAM_INVALID',message='请求字段类型无效',retryable=False),400
    return jsonify(chat(p))
@assistant_bp.get('/assistant/health')
def health():
    try: service=evidence_client.health(timeout=3)
    except evidence_client.EvidenceServiceError as error: service={'status':'unavailable','code':error.code,'mock':False}
    with get_connection() as conn:
        versions=[r['data_version'] for r in conn.execute('SELECT data_version FROM data_versions ORDER BY created_at DESC')]
    return jsonify(status='ok',evidence_service=service,hydrus_mode=HYDRUS_MODE,data_versions=versions,mock=service.get('mock',False))
@assistant_bp.get('/evidence/<evidence_id>')
def evidence(evidence_id):
    item=lookup(evidence_id,request.args.get('plot_id'))
    if not item: return jsonify(status='error',code='E_EVIDENCE_NOT_FOUND',message='证据未找到',retryable=False),404
    return jsonify(item)
