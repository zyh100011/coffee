"""Real loopback HTTP on ephemeral ports; own servers always closed."""
import threading
from contextlib import contextmanager
import os
import requests
import pytest
from werkzeug.serving import make_server
from tools.mock_evidence_service import app as mock_app

@contextmanager
def serve(app):
    server=make_server('127.0.0.1',0,app); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try: yield 'http://127.0.0.1:'+str(server.server_port)
    finally: server.shutdown(); server.server_close(); thread.join(timeout=3)

@pytest.mark.skipif(os.name!='nt',reason='Local HYDRUS EXE requires Windows')
def test_three_typical_http_requests(client,flask_app,monkeypatch,tmp_path):
    from services import evidence_client
    from models import hydrus_adapter
    from database.init_db import get_connection
    monkeypatch.setattr(hydrus_adapter,'HYDRUS_RUN_DIR',tmp_path/'runs')
    monkeypatch.setattr(hydrus_adapter,'HYDRUS_MODE','live')
    monkeypatch.setattr(hydrus_adapter,'ALLOW_DEMO_FALLBACK',False)
    client.post('/api/plot/init',json={'plot_id':'http_plot','plot_name':'HTTP假设测试'})
    with serve(mock_app) as mock_url, serve(flask_app) as backend_url:
        monkeypatch.setattr(evidence_client,'EVIDENCE_SERVICE_URL',mock_url)
        health=requests.get(backend_url+'/api/assistant/health',timeout=5).json()
        assert health['mock'] and health['data_versions']==[]
        messages=['根区水分是什么','40cm墒情2026-09-01到2026-09-07','如果2026-09-01多浇20mm']
        results=[]
        for message in messages:
            response=requests.post(backend_url+'/api/assistant/chat',json={'plot_id':'http_plot','message':message},timeout=30)
            assert response.status_code==200
            result=response.json(); results.append(result)
            assert result['mock'] and result['blocks'][-1]['type']=='trace'
        assert any(b['type']=='evidence' for b in results[0]['blocks'])
        assert any(b['type']=='warning' and '缺少' in b['text'] for b in results[1]['blocks'])
        assert any(b['type']=='chart' for b in results[2]['blocks'])
        with get_connection() as conn:
            traces=conn.execute('SELECT tool_results_json FROM assistant_traces').fetchall()
        import json
        scenario=json.loads(traces[-1]['tool_results_json'])[0]
        assert scenario['status']=='success' and scenario['source_type']=='simulation_uncalibrated'
        assert scenario['inputs']['daily_prec_cm'][0]==2 and len(scenario['outputs']['soil_moisture_series'])==8
