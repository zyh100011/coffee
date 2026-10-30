import pytest
import requests
from services import evidence_client as ec
from services import tool_registry as registry
from models import hydrus_adapter as hydrus
from services.tool_result import make_tool_result

def check(body,code):
    assert body['code']==code and isinstance(body['retryable'],bool) and body['message'] and body['trace_id']

def test_public_errors_and_internal_details_hidden(client,monkeypatch):
    check(client.get('/api/report/list').get_json(),'E_PLOT_REQUIRED')
    check(client.post('/api/scenario/compare',json=[]).get_json(),'E_PARAM_INVALID')
    check(client.get('/api/evidence/unknown').get_json(),'E_EVIDENCE_NOT_FOUND')
    check(client.get('/api/model/result?plot_id=unknown').get_json(),'E_DATA_EMPTY')
    from api import data_api
    def crash(*args): raise RuntimeError('private internal traceback marker')
    monkeypatch.setattr(data_api,'catalog',crash)
    response=client.get('/api/data/catalog?plot_id=p')
    check(response.get_json(),'E_INTERNAL')
    assert 'private internal' not in response.get_data(as_text=True)

@pytest.mark.parametrize('status,warning,code',[
 ('timeout','超时','E_HYDRUS_TIMEOUT'),('failed','解析失败','E_HYDRUS_FAILED'),
 ('failed','HYDRUS 引擎不存在','E_HYDRUS_UNAVAILABLE')])
def test_scenario_recoverable_errors(client,monkeypatch,status,warning,code):
    client.post('/api/plot/init',json={'plot_id':'p','plot_name':'fixture'})
    monkeypatch.setattr(hydrus,'run_hydrus_model',lambda data:make_tool_result(tool='hydrus',task_id=data['task_id'],status=status,source_type='simulation_uncalibrated',warnings=[warning]))
    response=client.post('/api/scenario/compare',json={'plot_id':'p','start_date':'2026-09-01','change':{'extra_irrigation_mm':20},'confirm':True})
    body=response.get_json();check(body,code)
    assert body['status']=='failed' and not body['rows'] and not body['output_diff']

def test_not_allowed_and_evidence_transport_recovery(client,monkeypatch):
    monkeypatch.setattr(ec,'route',lambda p,timeout=None:{'intent':'other','tool_calls':[{'name':'shell','arguments':{}}],'missing_fields':[]})
    check(client.post('/api/assistant/chat',json={'message':'x'}).get_json(),'E_TOOL_NOT_ALLOWED')
    for exception,code in [(requests.Timeout,'E_EVIDENCE_TIMEOUT'),(requests.ConnectionError,'E_EVIDENCE_DOWN')]:
        def broken(*a,**kw): raise exception('transport')
        monkeypatch.setattr(ec.requests,'post',broken)
        # Restore real transport after the explicit forbidden-tool fixture.
        with pytest.raises(ec.EvidenceServiceError) as error: ec._request('route',{'message':'x'})
        assert error.value.code==code
        monkeypatch.setattr(ec,'route',lambda p,timeout=None,c=code:(_ for _ in ()).throw(ec.EvidenceServiceError(c,'down')))
        response=client.post('/api/assistant/chat',json={'message':'知识'}).get_json()
        check(response['errors'][0],code)
        assert response['service_mode']=='degraded' and any(b['type']=='warning' for b in response['blocks'])
