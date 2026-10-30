from tests.test_project_raw import sample
from data_pipeline.ingest_project_raw import load_profile,ingest_project
from tests.test_evidence_client import mock_server
from services import evidence_client
from database.init_db import get_connection

def test_real_parameter_chain_and_sql(client,tmp_path,monkeypatch):
    profile=load_profile();profile['sources']=[{'kind':'lujiangba','file_glob':'*.csv','location':'原始地点','data_version':'layer-test'}]
    for station,base in ((1,20),(2,50)):
        sample(tmp_path,f'土壤监测{station}历史数据.csv',[[f'2026/6/{day} 12:00','三层湿度','soilH3',str(base+day-9),'%'] for day in range(9,16)])
    ingest_project(tmp_path,profile)
    with get_connection() as conn:
        expected=conn.execute("SELECT AVG(value)/100 FROM obs_long WHERE device_id='source:lujiangba:soil1' AND parameter='soil_humidity_layer3_raw'").fetchone()[0]
    with mock_server() as port:
        monkeypatch.setattr(evidence_client,'EVIDENCE_SERVICE_URL',f'http://127.0.0.1:{port}')
        for question in ('40cm最近7天墒情怎么样？','30–45cm 最近一周墒情怎么样','第3层最近7天墒情怎么样'):
            r=client.post('/api/assistant/chat',json={'plot_id':profile['plot_id'],'message':question}).get_json()
            assert any(b['type']=='chart' for b in r['blocks'])
            fact=next(b for b in r['blocks'] if b['type']=='fact' and b['label']=='mean')
            assert abs(fact['value']-expected)<1e-9
            evidence=client.get('/api/evidence/'+fact['evidence_id']).get_json()
            assert evidence['time_range']=={'start':'2026-06-09','end':'2026-06-15'}
            assert evidence['inputs']['display_source']=='土壤监测点1'
        r=client.post('/api/assistant/chat',json={'plot_id':profile['plot_id'],'message':'帮我看看墒情'}).get_json()
        missing=next(b for b in r['blocks'] if b['type']=='missing')
        assert missing['fields']==['深度','结束日期','开始日期']
        r=client.post('/api/assistant/chat',json={'plot_id':profile['plot_id'],'session_id':r['session_id'],'message':'帮我看看墒情','supplement':{'text':'30–45cm 最近7天'}}).get_json()
        assert any(b['type']=='chart' for b in r['blocks'])
