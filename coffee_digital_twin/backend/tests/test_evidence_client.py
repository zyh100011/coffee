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
        a=client.answer({'message':'咖啡农技知识','intent':'knowledge','tool_results':[]})
        assert len(a['citations'])==3 and all(c['snippet']=='该问题需要连接知识服务后回答' for c in a['citations'])
        assert a['answer']=='该问题需要连接知识服务后回答' and a['mock'] is True
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


def test_authenticated_transport_and_no_redirect_leak(monkeypatch):
    from flask import Flask,request,jsonify,redirect
    service=Flask(__name__);seen=[]
    @service.get('/health')
    def health():
        assert not request.headers.get('Authorization')
        return jsonify(status='ok',mock=False)
    @service.post('/v1/route')
    @service.post('/v1/answer')
    def protected():
        seen.append((request.path,request.headers.get('Authorization')))
        if request.headers.get('Authorization')!='Bearer test-private-token':
            return jsonify(error='unauthorized'),401
        if request.json['message']=='redirect':return redirect('/unexpected',code=307)
        if request.path.endswith('/route'):
            return jsonify(intent='knowledge',tool_calls=[],missing_fields=[],clarify_question=None,mock=False)
        return jsonify(answer='待核验',citations=[],claims=[],limitations=[],check_items=[],mock=False)
    @service.post('/unexpected')
    def unexpected():pytest.fail('redirect followed with credentials')
    server=make_server('127.0.0.1',0,service)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        monkeypatch.setattr(client,'EVIDENCE_SERVICE_URL',f'http://127.0.0.1:{server.server_port}')
        monkeypatch.delenv('EVIDENCE_API_TOKEN',raising=False)
        assert client.health()['mock'] is False
        with pytest.raises(client.EvidenceServiceError,match='鉴权失败'):
            client.route({'message':'咖啡知识'})
        monkeypatch.setenv('EVIDENCE_API_TOKEN','test-private-token')
        assert client.route({'message':'咖啡知识'})['intent']=='knowledge'
        assert client.answer({'message':'咖啡知识'})['mock'] is False
        with pytest.raises(client.EvidenceServiceError,match='重定向'):
            client.route({'message':'redirect'})
        assert seen[-2:]==[('/v1/answer','Bearer test-private-token'),('/v1/route','Bearer test-private-token')]
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


def test_service_input_limits_before_network(monkeypatch):
    monkeypatch.setattr(client.requests,'post',lambda *a,**k:pytest.fail('invalid payload sent'))
    for payload in ({'message':'a'*4001},{'message':'valid','history':['大'*50000]},{'message':'valid','value':float('nan')}):
        with pytest.raises(client.EvidenceServiceError) as error:client.route(payload)
        assert error.value.code=='E_EVIDENCE_INVALID'


def test_mock_data_answer_is_plain_chinese_and_numbers_are_bound():
    from tools.mock_evidence_service import answer_rules
    result=answer_rules({'intent':'data_query','tool_results':[{'tool':'data_query','status':'success','source_type':'observation',
        'evidence_id':'ev-isolated','time_range':{'start':'2026-06-09','end':'2026-06-15'},
        'inputs':{'layer_interval_cm':{'top':30,'bottom':45}},'units':{'value':'cm3/cm3'},
        'outputs':{'mean':.2439032258,'min':.18,'max':.28,'n':837}}]})
    text=result['answer']
    assert '30–45cm 平均含水率 0.24 cm³/cm³' in text and '范围 0.18–0.28' in text
    assert all(token not in text for token in ('MOCK','{','data_query','mean','source_type'))
    assert result['claims'][0]['evidence_ids']==['ev-isolated'] and result['mock'] is True
