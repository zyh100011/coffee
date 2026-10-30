"""Six API steps with explicit synthetic observations, mock evidence, real replay."""
from datetime import date,timedelta
import json
import time
from database.init_db import get_connection
from services import evidence_client
from tests.test_evidence_client import mock_server

def test_six_step_mock_rehearsal(client,monkeypatch):
    started=time.perf_counter()
    assert client.post('/api/plot/init',json={'plot_id':'fixture_demo','plot_name':'明确构造演示地块'}).status_code==200
    plot=client.get('/api/plot/fixture_demo').get_json()['plot']
    assert plot['completeness']['missing']
    with get_connection() as conn:
        conn.execute('INSERT INTO raw_files VALUES (?,?,?,?,?,?,?)',('fixture','synthetic.csv','fixture',7,'now','fixture-phase4','fixture'))
        for i in range(7):
            day=(date.today()-timedelta(days=6-i)).isoformat()
            conn.execute('INSERT INTO obs_long VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('fixture_'+str(i),'fixture_demo','0001',day+'T12:00:00',day,'soil_moisture',40,str(20+i),.2+i*.01,'cm3/cm3','fixture',i+2,'ok','fixture-phase4',1))
    with mock_server() as port:
        monkeypatch.setattr(evidence_client,'EVIDENCE_SERVICE_URL',f'http://127.0.0.1:{port}')
        def chat(text,**kw):
            response=client.post('/api/assistant/chat',json={'plot_id':'fixture_demo','message':text,**kw})
            assert response.status_code==200;return response.get_json()
        k=chat('咖啡根系主要分布在多深？')
        citation=next(b for b in k['blocks'] if b['type']=='evidence')['items'][0]['evidence_id']
        assert client.get('/api/evidence/'+citation+'?plot_id=fixture_demo').get_json()['source_type']=='demo'
        d=chat('40cm最近7天平均含水率')
        assert any(b['type']=='chart' for b in d['blocks'])
        ev=next(b['evidence_id'] for b in d['blocks'] if b['type']=='fact')
        result=client.get('/api/evidence/'+ev+'?plot_id=fixture_demo').get_json()
        assert result['source_type']=='demo'
        obs=result['outputs']['source_obs_ids'][0]
        assert client.get('/api/data/source/'+obs+'?plot_id=fixture_demo').get_json()['source_row']==2
        m=chat('帮我看看墒情',session_id='fixture_m')
        assert any(b['type']=='missing' for b in m['blocks'])
        m2=chat('帮我看看墒情',session_id='fixture_m',supplement={'text':'最近7天'})
        assert any(b['type']=='fact' for b in m2['blocks'])
        payload={'plot_id':'fixture_demo','start_date':date.today().isoformat(),'change':{'extra_irrigation_mm':20},'mode':'replay'}
        assert client.post('/api/scenario/compare',json={**payload,'confirm':False}).get_json()['status']=='confirmation_required'
        compare=client.post('/api/scenario/compare',json={**payload,'confirm':True}).get_json()
        assert compare['status']=='replay' and compare['parameter_verified']
        report=client.post('/api/report/create',json={'compare_id':compare['compare_id'],'plot_id':'fixture_demo'}).get_json()
        html=client.get('/api/report/'+report['report_id']+'.html?plot_id=fixture_demo').get_data(as_text=True)
        assert '历史结果回放' in html and '情景差异' in html
    # This is API automation time; never claim a 3–5 minute human UI demo passed.
    assert time.perf_counter()-started<30
