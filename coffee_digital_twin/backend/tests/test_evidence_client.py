from contextlib import contextmanager
import threading
import pytest
from werkzeug.serving import make_server
from services import evidence_client as client
from tools.mock_evidence_service import app,route_rules

@contextmanager
def mock_server():
    server=make_server('127.0.0.1',0,app); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try: yield server.server_port
    finally: server.shutdown(); server.server_close(); thread.join(timeout=3)

def test_real_mock_http_and_stopped(monkeypatch):
    with mock_server() as port:
        monkeypatch.setattr(client,'EVIDENCE_SERVICE_URL',f'http://127.0.0.1:{port}')
        assert client.health()['mock'] is True
        r=client.route({'message':'40cm墒情最近7天','plot_context':{'plot_id':'p'}})
        assert r['intent']=='data_query' and not r['missing_fields']
        a=client.answer({'intent':'knowledge','tool_results':[]})
        assert len(a['citations'])==3 and all('MOCK' in c['title'] for c in a['citations'])
    with pytest.raises(client.EvidenceServiceError) as error: client.health(timeout=.2)
    assert error.value.code in {'E_EVIDENCE_DOWN','E_EVIDENCE_TIMEOUT'}

def test_contract_and_supplement():
    with pytest.raises(ValueError): client.validate('route',{'intent':'data_query','tool_calls':[{'name':9,'arguments':[]}],'missing_fields':[]})
    r=route_rules({'message':'40cm墒情','plot_context':{'plot_id':'p'}})
    assert r['missing_fields']==['start','end']
    r=route_rules({'message':'40cm墒情','plot_context':{'plot_id':'p'},'supplement':{'start':'2026-09-01','end':'2026-09-07'}})
    assert not r['missing_fields']

def test_glm_default_off(monkeypatch):
    from services import llm_service
    monkeypatch.delenv('LEGACY_GLM',raising=False)
    monkeypatch.setattr(llm_service,'_call_glm',lambda *a:pytest.fail('external GLM called'))
    assert llm_service.generate_advice({}, {}, {})['source']=='rule_fallback_not_evidence'
