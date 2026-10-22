"""Loopback mock plus explicit synthetic observations; never official data."""
from datetime import date,timedelta
import json
from services import evidence_client
from tests.test_evidence_client import mock_server
from database.init_db import get_connection

def test_four_mock_scenarios(client,monkeypatch):
    from models import hydrus_adapter
    from pathlib import Path
    monkeypatch.setattr(hydrus_adapter,'HYDRUS_EXE',Path('not_provided.exe'))
    monkeypatch.setattr(hydrus_adapter,'ALLOW_DEMO_FALLBACK',False)
    client.post('/api/plot/init',json={'plot_id':'fixture_plot','plot_name':'构造联调地块'})
    today=date.today(); start=(today-timedelta(days=6)).isoformat()
    with get_connection() as conn:
        conn.execute('INSERT INTO raw_files VALUES (?,?,?,?,?,?,?)',('fixture','synthetic.csv','fixture-hash',7,'now','fixture-e2e','fixture'))
        for i in range(7):
            day=(today-timedelta(days=6-i)).isoformat()
            conn.execute('INSERT INTO obs_long VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
              ('fixture_'+str(i),'fixture_plot','0001',day+'T12:00:00+08:00',day,'soil_moisture',40,str(20+i),.2+i*.01,'cm3/cm3','fixture',i+2,'ok','fixture-e2e',1))
        expected=conn.execute("SELECT AVG(value) FROM obs_long WHERE plot_id='fixture_plot' AND depth_cm=40 AND date BETWEEN ? AND ?",(start,today.isoformat())).fetchone()[0]
    with mock_server() as port:
        monkeypatch.setattr(evidence_client,'EVIDENCE_SERVICE_URL',f'http://127.0.0.1:{port}')
        def chat(message,**extra):
            r=client.post('/api/assistant/chat',json={'plot_id':'fixture_plot','message':message,**extra})
            assert r.status_code==200
            return r.get_json()
        knowledge=chat('咖啡根系主要分布在多深？')
        assert any(b['type']=='evidence' for b in knowledge['blocks'])
        assert not any(b['type']=='fact' for b in knowledge['blocks'])
        citation=next(b for b in knowledge['blocks'] if b['type']=='evidence')['items'][0]['evidence_id']
        detail=client.get('/api/evidence/'+citation+'?plot_id=fixture_plot').get_json()
        assert detail['source_type']=='demo'
        data=chat('40cm最近7天平均含水率')
        mean=next(b for b in data['blocks'] if b['type']=='fact' and b['label']=='mean')
        assert abs(mean['value']-expected)<1e-9 and mean['source_type']=='demo'
        missing=chat('帮我看看墒情',session_id='e2e-m')
        assert any(b['type']=='missing' for b in missing['blocks'])
        supplement=chat('帮我看看墒情',session_id='e2e-m',supplement={'text':'最近7天'})
        assert any(b['type']=='fact' for b in supplement['blocks'])
        chat('帮我看看墒情',session_id='e2e-check')
        check=chat('帮我看看墒情',session_id='e2e-check',supplement={'text':'不知道'})
        assert any(b['type']=='check_items' for b in check['blocks'])
        failed=chat('如果'+today.isoformat()+'多浇20mm')
        assert any(b['type']=='warning' and 'failed' in b['text'] for b in failed['blocks'])
        assert not any(b['type']=='fact' for b in failed['blocks'])
    with get_connection() as conn:
        traces=conn.execute('SELECT trace_id,route_json,service_mode FROM assistant_traces').fetchall()
        assert len(traces)==7 and all(r['service_mode']=='mock' for r in traces)
