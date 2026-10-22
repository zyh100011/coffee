"""HTTP checker behavior with explicit isolated synthetic prerequisites."""
from contextlib import closing,contextmanager
import json
from pathlib import Path
import threading
from werkzeug.serving import make_server
from tools.selfcheck import inspect_database,run_checks,write_report
from tools.material_paths import sha256_file
from database import init_db as db
from services import evidence_client as ec
from tools.mock_evidence_service import route_rules,answer_rules

@contextmanager
def server(app):
    s=make_server('127.0.0.1',0,app);t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
    try: yield f'http://127.0.0.1:{s.server_port}'
    finally: s.shutdown();s.server_close();t.join(timeout=3)

def settings(tmp_path):
    return dict(database=db.DATABASE_PATH,version='test-only',mode='replay',engine=tmp_path/'missing.exe',fallback=False,debug=False,timeout=60,evidence_url_valid=True)

def test_missing_checks_still_call_six_apis(client,flask_app,tmp_path,monkeypatch):
    monkeypatch.setattr(ec,'health',lambda timeout=None:{'status':'ok','mock':True})
    monkeypatch.setattr(ec,'route',lambda *a,**kw:(_ for _ in ()).throw(ec.EvidenceServiceError('E_EVIDENCE_DOWN','test')))
    with server(flask_app) as url: rows=run_checks(url,settings(tmp_path))
    results={r['check']:r['status'] for r in rows}
    assert results['frozen_data']==results['evidence_health']=='FAIL'
    assert {'http_ping','http_catalog','http_query','http_assistant','http_compare_replay','http_report'}<=results.keys()
    text=write_report(rows,tmp_path/'report.txt');assert 'FAIL：' in text

def test_complete_checker_contract_and_hash_change(client,flask_app,tmp_path,monkeypatch):
    # Synthetic values exercise PASS mechanics; this is not a live-service acceptance.
    client.post('/api/plot/init',json={'plot_id':'p','plot_name':'explicit test fixture'})
    raw=tmp_path/'synthetic.csv';raw.write_text('TEST ONLY',encoding='utf-8')
    with closing(db.get_connection()) as c:
        with c:
            c.execute('INSERT INTO raw_files VALUES (?,?,?,?,?,?,?)',('f',str(raw),sha256_file(raw),1,'now','test-only','observation'))
            c.execute('INSERT INTO obs_long VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('o','p','001','2026-09-01T00:00:00','2026-09-01','soil_moisture',40,'20',.2,'cm3/cm3','f',2,'ok','test-only',1))
            c.execute('INSERT INTO data_versions VALUES (?,?,?,?,?)',('test-only','now',json.dumps({'f':sha256_file(raw)}),json.dumps({'obs_long':1}),'synthetic selfcheck test only'))
    monkeypatch.setattr(ec,'health',lambda timeout=None:{'status':'ok','mock':False})
    monkeypatch.setattr(ec,'route',lambda p,timeout=None:{**route_rules(p),'mock':False})
    monkeypatch.setattr(ec,'answer',lambda p,timeout=None:{**answer_rules(p),'mock':False})
    with server(flask_app) as url: rows=run_checks(url,settings(tmp_path))
    assert all(r['status']=='PASS' for r in rows),rows
    raw.write_text('changed',encoding='utf-8')
    assert inspect_database(db.DATABASE_PATH,'test-only')[1] is False
    try: write_report(rows,tmp_path/'06_正式测试资料'/'log.txt')
    except ValueError: pass
    else: raise AssertionError('formal path must be rejected')


def test_multisource_diagnostics_and_historical_replay_dates(client,flask_app,tmp_path,monkeypatch):
    import tools.selfcheck as checker
    client.post('/api/plot/init',json={'plot_id':'p','plot_name':'synthetic multisource fixture'})
    raw=tmp_path/'multi.csv';raw.write_text('TEST ONLY MULTISOURCE',encoding='utf-8')
    with closing(db.get_connection()) as conn:
        with conn:
            conn.execute('INSERT INTO raw_files VALUES (?,?,?,?,?,?,?)',('f',str(raw),sha256_file(raw),3,'now','test-only','observation'))
            for i,(device,unit,value) in enumerate([('001','cm3/cm3',.2),('002','cm3/cm3',.4),('001','%',20)]):
                conn.execute('INSERT INTO obs_long VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    ('o'+str(i),'p',device,f'2025-03-01T0{i}:00:00','2025-03-01','soil_moisture',40,str(value),value,unit,'f',i+2,'ok','test-only',1))
    state=inspect_database(db.DATABASE_PATH,'')
    assert state[:2]==(True,False)
    assert state[2]['device_id']=='001' and state[2]['unit']=='%'
    monkeypatch.setattr(ec,'health',lambda timeout=None:{'status':'ok','mock':True})
    monkeypatch.setattr(ec,'route',lambda *a,**kw:(_ for _ in ()).throw(ec.EvidenceServiceError('E_EVIDENCE_DOWN','test')))
    actual_request=checker.requests.request;comparisons=[]
    def record(method,url,**kwargs):
        if url.endswith('/api/scenario/compare'): comparisons.append(kwargs['json'])
        return actual_request(method,url,**kwargs)
    monkeypatch.setattr(checker.requests,'request',record)
    config=settings(tmp_path);config['version']=''
    with server(flask_app) as url: rows=run_checks(url,config)
    statuses={r['check']:r['status'] for r in rows}
    assert statuses['environment']==statuses['frozen_data']==statuses['evidence_health']=='FAIL'
    assert statuses['http_catalog']==statuses['http_query']==statuses['http_compare_replay']=='PASS'
    assert '冻结验收仍未通过' in next(r['detail'] for r in rows if r['check']=='http_query')
    original=json.loads((checker.BACKEND/'data/hydrus_cases/case_baseline_0mm.json').read_text(encoding='utf-8'))
    assert comparisons[0]['start_date']==original['time_range']['start']!='2025-03-01'
    with closing(db.get_connection()) as conn:
        with conn:
            conn.execute('INSERT INTO data_versions VALUES (?,?,?,?,?)',('test-only','now',json.dumps({'f':sha256_file(raw)}),json.dumps({'obs_long':3}),'synthetic test only'))
    frozen=inspect_database(db.DATABASE_PATH,'test-only')
    assert frozen[:2]==(True,True)
    assert frozen[2]['device_id']=='001' and frozen[2]['unit']=='%'
