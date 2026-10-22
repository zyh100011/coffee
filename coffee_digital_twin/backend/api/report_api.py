import json
import uuid
from flask import Blueprint,jsonify,request,Response
from database.init_db import get_connection,now_iso
from services.report_builder import build_report,render_html
report_bp=Blueprint('report_api',__name__,url_prefix='/api/report')
def init_reports(conn): conn.execute('CREATE TABLE IF NOT EXISTS reports(report_id TEXT PRIMARY KEY,plot_id TEXT,source_id TEXT,report_json TEXT,created_at TEXT)')
@report_bp.post('/create')
def create():
    payload=request.get_json(silent=True) or {}
    keys=[k for k in ('trace_id','compare_id') if payload.get(k)]
    if len(keys)!=1 or not isinstance(payload[keys[0]],str): return jsonify(status='error',code='E_PARAM_INVALID',message='指定一个trace_id或compare_id',retryable=False),400
    try: report=build_report(payload[keys[0]],'trace' if keys[0]=='trace_id' else 'compare',payload.get('plot_id'))
    except LookupError as error: return jsonify(status='error',code='E_EVIDENCE_NOT_FOUND',message=str(error),retryable=False),404
    report.update(report_id='rp_'+uuid.uuid4().hex,created_at=now_iso())
    with get_connection() as conn: conn.execute('INSERT INTO reports VALUES (?,?,?,?,?)',(report['report_id'],report['plot_id'],report['source_id'],json.dumps(report,ensure_ascii=False),report['created_at']))
    return jsonify(status='success',report_id=report['report_id'])
@report_bp.get('/list')
def listing():
    plot=request.args.get('plot_id')
    if not plot:return jsonify(status='error',code='E_PLOT_REQUIRED',message='请选择地块',retryable=False),400
    with get_connection() as conn: rows=conn.execute('SELECT report_id,plot_id,source_id,created_at FROM reports WHERE plot_id=? ORDER BY created_at DESC',(plot,)).fetchall()
    return jsonify(status='success',items=[dict(r) for r in rows])
def load(report_id):
    with get_connection() as conn: row=conn.execute('SELECT * FROM reports WHERE report_id=?',(report_id,)).fetchone()
    if row and (not request.args.get('plot_id') or request.args['plot_id']==row['plot_id']): return json.loads(row['report_json'])
    return None
@report_bp.get('/<report_id>.html')
def report_html(report_id):
    report=load(report_id)
    if not report:return jsonify(status='error',code='E_EVIDENCE_NOT_FOUND',message='报告未找到',retryable=False),404
    return Response(render_html(report),mimetype='text/html')
@report_bp.get('/<report_id>')
def detail(report_id):
    report=load(report_id)
    if not report:return jsonify(status='error',code='E_EVIDENCE_NOT_FOUND',message='报告未找到',retryable=False),404
    return jsonify(report)
