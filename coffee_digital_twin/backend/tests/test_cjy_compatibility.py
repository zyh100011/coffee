"""Local contract tests, independent of remote model availability or expert accuracy."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from services import evidence_client,tool_registry
from services.evidence_transport import answer_results
from services.tool_result import make_tool_result
from database.init_db import get_connection


def answer(status='generated_unreviewed',citations=None,claims=None):
    return {'answer':'待核验回答','citations':citations or [],'claims':claims or [],
        'limitations':[],'check_items':[],'retrieval_trace':{'status':status},'mock':False}


def test_explicit_knowledge_skips_route_and_tools(client,monkeypatch):
    monkeypatch.setattr(evidence_client,'route',lambda *a,**k:pytest.fail('knowledge route called'))
    monkeypatch.setitem(tool_registry.FUNCTIONS,'query_soil_moisture',lambda *a:pytest.fail('knowledge tool executed'))
    citation={'evidence_id':'FAO-P31','doc_id':'FAO-P31','title':'农技资料','locator':'p31','snippet':'采样方法'}
    def generate(payload,timeout=None):
        assert payload['intent']=='knowledge' and payload['tool_results']==[]
        return answer(citations=[citation],claims=[{'text':'采样方法','evidence_ids':['FAO-P31']}])
    monkeypatch.setattr(evidence_client,'answer',generate)
    response=client.post('/api/assistant/chat',json={'message':'土壤湿度传感器如何维护？','entry_mode':'knowledge'}).get_json()
    assert response['status']=='success' and response['answer_status']=='generated_unreviewed'
    assert any(b.get('answer_status')=='generated_unreviewed' for b in response['blocks'])
    assert not any(b['type']=='fact' for b in response['blocks'])
    with get_connection() as conn:trace=conn.execute('SELECT * FROM assistant_traces WHERE trace_id=?',(response['trace_id'],)).fetchone()
    assert json.loads(trace['route_json'])['guard_trace']==['explicit_knowledge_entry']
    assert json.loads(trace['tool_calls_json'])==[]
    assert client.post('/api/assistant/chat',json={'message':'x'*4001}).status_code==400
    assert client.post('/api/assistant/chat',json={'message':'x','entry_mode':'execute'}).status_code==400


def test_scalar_mapping_preserves_raw_values_and_archive_identity():
    observation=make_tool_result(tool='data_query',plot_id='p',status='success',units={'value':'cm3/cm3'},
        outputs={'mean':.241,'min':.2,'n':2,'series':[{'date':'2026-09-01','value':.241}]})
    archive=json.loads((Path(__file__).resolve().parents[1]/'data/hydrus_cases/case_baseline_0mm.json').read_text(encoding='utf-8'))
    originals=deepcopy([observation,archive])
    prepared,annotations=answer_results([observation,archive])
    assert [observation,archive]==originals
    assert prepared[0]['units']['mean']=='cm3/cm3' and prepared[0]['units']['n']=='条'
    assert prepared[1]['outputs']['profile_theta_40cm']==.1342
    assert prepared[1]['units']['profile_theta_40cm']=='cm3/cm3'
    assert prepared[1]['plot_id'] is None and prepared[1]['task_id']==archive['task_id']
    assert prepared[1]['outputs']['soil_profile_current']==archive['outputs']['soil_profile_current']
    assert annotations[1]['output_aliases']['profile_theta_40cm']=='outputs.soil_profile_current[2].theta'


@pytest.mark.parametrize('status',['generated_unreviewed','verified_numeric_summary','needs_tool_evidence','generation_check_failed'])
def test_status_provenance_and_report_consistency(client,monkeypatch,status):
    client.post('/api/plot/init',json={'plot_id':'p','plot_name':'构造地块'})
    result=make_tool_result(tool='data_query',plot_id='p',status='success',source_type='observation',
        outputs={'mean':.241},units={'value':'cm3/cm3'})
    monkeypatch.setattr(evidence_client,'route',lambda p,timeout=None:{'intent':'data_query','tool_calls':[
        {'name':'query_observation','arguments':{'plot_id':'p','parameter':'soil_moisture','start':'2026-09-01','end':'2026-09-07'}}],
        'missing_fields':[],'clarify_question':None})
    monkeypatch.setitem(tool_registry.FUNCTIONS,'query_observation',lambda *a:deepcopy(result))
    def generate(payload,timeout=None):
        assert payload['tool_results'][0]['units']['mean']=='cm3/cm3'
        citations=[{'evidence_id':result['evidence_id'],'doc_id':result['evidence_id'],'title':'业务工具结果','locator':'历史窗口','snippet':'mean=.241'},
            {'evidence_id':'TOOL-HYDRUS','doc_id':'TOOL-HYDRUS','title':'HYDRUS说明','locator':'工程说明','snippet':'工具边界'}]
        return answer(status,citations,[{'text':'工程摘要0.241','evidence_ids':[result['evidence_id']]}])
    monkeypatch.setattr(evidence_client,'answer',generate)
    response=client.post('/api/assistant/chat',json={'plot_id':'p','message':'查询土壤'}).get_json()
    assert response['answer_status']==status
    labels=[e['label'] for b in response['blocks'] if b['type']=='evidence' for e in b['items']]
    assert labels==['实测','工具说明']
    assert any(b['type']=='fact' and b['value']==.241 for b in response['blocks'])
    rejected=status in {'needs_tool_evidence','generation_check_failed'}
    assert any(b['type']=='text' and b.get('text')=='工程摘要0.241' for b in response['blocks']) is not rejected
    with get_connection() as conn:trace=conn.execute('SELECT * FROM assistant_traces WHERE trace_id=?',(response['trace_id'],)).fetchone()
    assert json.loads(trace['tool_results_json'])[0]==result
    assert json.loads(trace['route_json'])['answer_transport'][0]['unit_mappings']['mean']=='units.value'
    citation=client.get('/api/evidence/TOOL-HYDRUS?plot_id=p').get_json()
    assert citation['source_type']=='internal_tool_description'
    rid=client.post('/api/report/create',json={'trace_id':response['trace_id'],'plot_id':'p'}).get_json()['report_id']
    report=client.get('/api/report/'+rid+'?plot_id=p').get_json()
    assert [r['source_type'] for r in report['evidence']]==['observation','internal_tool_description']
    assert bool(report['sections'][3]['items']) is not rejected


def test_new_mode_does_not_resume_old_pending_question(client,monkeypatch):
    from tools.mock_evidence_service import route_rules,answer_rules
    monkeypatch.setattr(evidence_client,'route',lambda p,timeout=None:route_rules(p))
    messages=[]
    def generate(payload,timeout=None):messages.append(payload['message']);return answer_rules(payload)
    monkeypatch.setattr(evidence_client,'answer',generate)
    response=client.post('/api/assistant/chat',json={'session_id':'mode-test','message':'40cm墒情'}).get_json()
    assert response['status']=='missing_input'
    client.post('/api/assistant/chat',json={'session_id':'mode-test','entry_mode':'knowledge','message':'如何维护传感器','supplement':{'text':'新的问题'}})
    assert messages==['如何维护传感器']
