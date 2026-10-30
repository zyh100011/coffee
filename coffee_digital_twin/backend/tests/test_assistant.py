import json
import time
import pytest
from services import evidence_client as ec,tool_registry as registry
from services.tool_result import make_tool_result,validate_tool_result
from tools.mock_evidence_service import route_rules,answer_rules

def setup(client,monkeypatch):
    client.post('/api/plot/init',json={'plot_id':'p','plot_name':'fixture'})
    monkeypatch.setattr(ec,'route',lambda payload,timeout=None:route_rules(payload))
    monkeypatch.setattr(ec,'answer',lambda payload,timeout=None:answer_rules(payload))

def data_result(args,ctx):
    return make_tool_result(tool='data_query',plot_id='p',status='success',source_type='observation',
        time_range={'start':'2026-09-01','end':'2026-09-07'},inputs=args,units={'value':'cm3/cm3'},
        outputs={'n':2,'mean':.21,'series':[{'date':'2026-09-01','value':.2},{'date':'2026-09-02','value':.22}]})

def test_data_success_trace_and_evidence(client,monkeypatch):
    setup(client,monkeypatch); monkeypatch.setitem(registry.FUNCTIONS,'query_soil_moisture',data_result)
    r=client.post('/api/assistant/chat',json={'plot_id':'p','message':'40cm墒情2026-09-01到2026-09-07'}).get_json()
    assert r['status']=='success' and r['mock']
    assert {'fact','chart','evidence','trace'} <= {b['type'] for b in r['blocks']}
    evidence=next(b['evidence_id'] for b in r['blocks'] if b['type']=='fact')
    assert client.get('/api/evidence/'+evidence).get_json()['outputs']['mean']==.21
    assert client.get('/api/evidence/'+evidence+'?plot_id=q').status_code==404
    assert client.get('/api/evidence/unknown').status_code==404
    from database.init_db import get_connection
    with get_connection() as conn: trace=conn.execute('SELECT * FROM assistant_traces WHERE trace_id=?',(r['trace_id'],)).fetchone()
    assert trace['service_mode']=='mock' and json.loads(trace['tool_results_json'])

def test_clarify_once_then_reset(client,monkeypatch):
    setup(client,monkeypatch)
    p={'session_id':'clarify','plot_id':'p','message':'40cm墒情'}
    a=client.post('/api/assistant/chat',json=p).get_json()
    assert any(b['type']=='missing' for b in a['blocks'])
    b=client.post('/api/assistant/chat',json={**p,'message':'不知道','supplement':{'text':'不知道'}}).get_json()
    assert any(x['type']=='check_items' for x in b['blocks']) and not any(x['type']=='missing' for x in b['blocks'])
    c=client.post('/api/assistant/chat',json=p).get_json()
    assert any(x['type']=='missing' for x in c['blocks'])

def test_failed_hydrus_never_claim_evidence(client,monkeypatch):
    setup(client,monkeypatch)
    failed=make_tool_result(tool='hydrus',plot_id='p',status='failed',warnings=['engine unavailable'])
    monkeypatch.setitem(registry.FUNCTIONS,'run_hydrus_scenario',lambda a,c:failed)
    def answer(payload,timeout=None):
        assert payload['tool_results']==[]
        return {'answer':'伪造42','citations':[], 'claims':[{'text':'吸水42','evidence_ids':[failed['evidence_id']]}],
            'limitations':[],'check_items':[],'mock':True}
    monkeypatch.setattr(ec,'answer',answer)
    r=client.post('/api/assistant/chat',json={'plot_id':'p','message':'如果2026-09-01多浇20mm'}).get_json()
    assert any(b['type']=='warning' and '失败' in b['text'] for b in r['blocks'])
    assert any(b['type']=='text' and b['text'].startswith('[未核验]') for b in r['blocks'])
    from database.init_db import get_connection
    with get_connection() as conn: row=conn.execute('SELECT errors_json FROM assistant_traces WHERE trace_id=?',(r['trace_id'],)).fetchone()
    assert 'unsupported_claim' in json.loads(row['errors_json'])

def test_unknown_claim_marked(client,monkeypatch):
    setup(client,monkeypatch)
    monkeypatch.setattr(ec,'answer',lambda p,timeout=None:{'answer':'假的产量', 'citations':[],
        'claims':[{'text':'产量100','evidence_ids':['ev_unknown']}],'limitations':[],'check_items':[]})
    r=client.post('/api/assistant/chat',json={'plot_id':'p','message':'土壤知识'}).get_json()
    assert any(b['type']=='text' and '[未核验]' in b['text'] for b in r['blocks'])

def test_degraded_only_queries(client,monkeypatch):
    setup(client,monkeypatch)
    def down(*a,**kw): raise ec.EvidenceServiceError('E_EVIDENCE_DOWN','down')
    monkeypatch.setattr(ec,'route',down); monkeypatch.setattr(ec,'answer',lambda *a,**kw:pytest.fail('answer during degradation'))
    monkeypatch.setitem(registry.FUNCTIONS,'query_soil_moisture',data_result)
    r=client.post('/api/assistant/chat',json={'plot_id':'p','message':'40cm墒情最近7天'}).get_json()
    assert r['service_mode']=='degraded' and any(b['type']=='fact' for b in r['blocks'])
    monkeypatch.setitem(registry.FUNCTIONS,'run_hydrus_scenario',lambda *a:pytest.fail('hydrus offline'))
    client.post('/api/assistant/chat',json={'plot_id':'p','message':'如果2026-09-01多浇20mm'})

def test_whitelist_limits_bounds_and_plot(client,monkeypatch):
    setup(client,monkeypatch)
    for calls in ([{'name':'powershell','arguments':{'command':'delete'}}],
                  [{'name':'get_plot_profile','arguments':{'plot_id':'p','path':'C:/'}}],
                  [{'name':'get_plot_profile','arguments':{'plot_id':'q'}}],
                  [{'name':'get_plot_profile','arguments':{'plot_id':'p'}}]*4,
                  [{'name':'run_hydrus_scenario','arguments':{'plot_id':'p','start_date':'2026-09-01','extra_irrigation_mm':20}}]*2):
        monkeypatch.setattr(ec,'route',lambda p,timeout=None,calls=calls:{'intent':'other','tool_calls':calls,'missing_fields':[],'clarify_question':None})
        r=client.post('/api/assistant/chat',json={'plot_id':'p','message':'x'}).get_json()
        assert r['status']=='error'
    _,_,errors=registry.prepare_calls([{'name':'query_observation','arguments':{'plot_id':'p','parameter':'soil_moisture','start':'2020-01-01','end':'2026-01-01'}}],{'plot_id':'p'})
    assert errors
    assert validate_tool_result({'time_range':None})

def test_verified_context_and_exports(client,monkeypatch,tmp_path):
    setup(client,monkeypatch)
    from services.plot_context import load_plot_context
    assert load_plot_context('p')['known']=={}
    client.post('/api/assistant/chat',json={'plot_id':'p','message':'知识'})
    from tools.export_traces import export,redact
    assert export(tmp_path/'traces.jsonl')==1
    with pytest.raises(ValueError): export(tmp_path/'06_正式测试资料'/'trace.jsonl')
    assert redact({'api_key':'secret'})['api_key']=='[REDACTED]'

def test_shared_budget(client,monkeypatch):
    setup(client,monkeypatch)
    from services import assistant_service
    clock={'now':0.0}; monkeypatch.setattr(assistant_service.time,'monotonic',lambda:clock['now'])
    def route(payload,timeout=None):
        assert timeout<=20; clock['now']+=20
        return {'intent':'knowledge','tool_calls':[],'missing_fields':[],'clarify_question':None}
    def answer(payload,timeout=None):
        assert timeout<=60 and timeout<=118-clock['now']; clock['now']+=timeout
        return answer_rules(payload)
    monkeypatch.setattr(ec,'route',route); monkeypatch.setattr(ec,'answer',answer)
    r=client.post('/api/assistant/chat',json={'plot_id':'p','message':'knowledge'}).get_json()
    assert r['status']=='success' and clock['now']<=120
