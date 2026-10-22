import json
from pathlib import Path
import pytest
from models import hydrus_adapter as hydrus
from database.init_db import get_connection

def setup(client):
    client.post('/api/plot/init',json={'plot_id':'p','plot_name':'构造情景地块'})
    return {'plot_id':'p','start_date':'2026-09-01','change':{'extra_irrigation_mm':20},'confirm':True}

def test_confirmation_validation_and_no_engine(client,monkeypatch):
    p=setup(client)
    monkeypatch.setattr(hydrus,'run_hydrus_model',lambda *_:pytest.fail('unconfirmed run'))
    r=client.post('/api/scenario/compare',json={**p,'confirm':False}).get_json()
    assert r['status']=='confirmation_required' and r['assumptions'] and not r['confirmation']['recorded_irrigation']
    for patch in ({'change':{'extra_irrigation_mm':20,'shade':.2}}, {'change':{'extra_irrigation_mm':True}},
                  {'change':{'extra_irrigation_mm':101}}, {'confirm':'true'}, {'tool':'beps'}, {'start_date':'bad'}, {'plot_id':'unknown'}):
        assert client.post('/api/scenario/compare',json={**p,**patch}).status_code==400
    with get_connection() as conn: assert conn.execute('SELECT COUNT(*) FROM scenario_compares').fetchone()[0]==0

def test_parameter_failed_no_numeric_diff(client,monkeypatch):
    p=setup(client)
    stored=json.loads((Path(__file__).resolve().parents[1]/'data/hydrus_cases/case_baseline_0mm.json').read_text(encoding='utf-8'))
    def bad(data):
        result=json.loads(json.dumps(stored)); result['task_id']=data['task_id']; return result
    monkeypatch.setattr(hydrus,'run_hydrus_model',bad)
    r=client.post('/api/scenario/compare',json=p).get_json()
    assert r['status']=='failed' and '参数未进入模型' in r['warnings']
    assert not r['output_diff'] and not r['series'] and not r['rows']
    report=client.post('/api/report/create',json={'plot_id':'p','compare_id':r['compare_id']}).get_json()
    d=client.get('/api/report/'+report['report_id']+'?plot_id=p').get_json()
    assert d['sections'][2]['items']==[]

@pytest.mark.skipif(__import__('os').name!='nt',reason='Windows live engine')
def test_live_matches_case_and_replay_history(client,monkeypatch,tmp_path):
    p=setup(client)
    monkeypatch.setattr(hydrus,'HYDRUS_RUN_DIR',tmp_path/'runs')
    r=client.post('/api/scenario/compare',json={**p,'mode':'live'}).get_json()
    assert r['status']=='success',r
    expected=json.loads((Path(__file__).resolve().parents[1]/'data/hydrus_cases/case_compare_0_vs_20.json').read_text(encoding='utf-8'))
    assert r['input_diff']==expected['input_diff'] and r['output_diff']==expected['output_diff']
    assert len(r['series'])==2 and len(r['rows'])==5
    from services import evidence_client
    from tools.mock_evidence_service import answer_rules
    monkeypatch.setattr(evidence_client,'answer',lambda p,timeout=None:answer_rules(p))
    explain=client.post('/api/assistant/chat',json={'plot_id':'p','message':'解释情景对比 '+r['compare_id']}).get_json()
    assert any(b['type']=='fact' for b in explain['blocks'])
    assert client.get('/api/evidence/'+r['variant']['evidence_id']+'?plot_id=p').status_code==200
    assert client.get('/api/evidence/'+r['variant']['evidence_id']+'?plot_id=q').status_code==404
    with get_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM scenario_compares').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM assistant_traces').fetchone()[0]==2
    replay=client.post('/api/scenario/compare',json={**p,'start_date':'2026-10-18','mode':'replay'}).get_json()
    assert replay['status']=='replay' and replay['time_range']['start']=='2026-09-01'
    assert replay['baseline']['plot_id'] is None and replay['output_diff']==expected['output_diff']
    missing=client.post('/api/scenario/compare',json={**p,'change':{'extra_irrigation_mm':30},'mode':'replay'}).get_json()
    assert missing['status']=='failed' and not missing['output_diff']
    rp=client.post('/api/report/create',json={'compare_id':replay['compare_id'],'plot_id':'p'}).get_json()
    report=client.get('/api/report/'+rp['report_id']+'?plot_id=p').get_json()
    assert report['sections'][2]['items'] and '回放' in str(report['sections'][4])
