import pytest
from data_pipeline.ingest_monitoring import ingest
from data_pipeline.profile_raw import precision_suspect
from data_pipeline.freeze import freeze

def fixture(tmp_path):
    root=tmp_path/'raw'; root.mkdir()
    (root/'a.csv').write_text('id,time,theta,rain,temp\n00123,2026-09-01T00:00:00,20,10,20\n00123,2026-09-02T00:00:00,30,15,20\n00123,2026-09-03T00:00:00,90,2,99\n00123,2026-09-04T00:00:00,,5,20\n',encoding='utf-8')
    (root/'b.csv').write_text('id,time,theta,rain,temp\n00123,2026-09-02T00:00:00,40,15,20\n',encoding='utf-8')
    items=[]
    for name,priority in [('a.csv',1),('b.csv',2)]:
        items.append({'file_glob':name,'time_col':'time','time_format':'ISO8601','device_col':'id','crop':'coffee',
          'rain_mode':'cumulative','priority':priority,'data_version':'fixture-september',
          'value_cols':[{'col':'theta','parameter':'soil_moisture','depth_cm':40,'unit':'%'},
                        {'col':'rain','parameter':'rainfall','depth_cm':None,'unit':'mm'},
                        {'col':'temp','parameter':'soil_temperature','depth_cm':40,'unit':'℃'}]})
    return root,{'confirmed':True,'source_type':'fixture','files':items},[{'device_id':'00123','plot_id':'p','depth_cm':'40','valid_from':'','valid_to':''}]

def test_import_query_hand_calculated(client,tmp_path):
    root,mapping,devices=fixture(tmp_path)
    counts=ingest(root,mapping,devices,tmp_path/'log.md')
    assert counts[1]['dedup']==3
    args={'plot_id':'p','parameter':'soil_moisture','depth_cm':40,'start':'2026-09-01','end':'2026-09-04','agg':'daily_mean'}
    result=client.post('/api/data/query',json=args).get_json()
    assert result['status']=='success' and result['source_type']=='demo'
    assert abs(result['outputs']['mean']-.3)<1e-9
    assert result['outputs']['n']==2 and result['outputs']['missing_days']==2
    assert client.get('/api/evidence/'+result['evidence_id']+'?plot_id=p').get_json()['inputs']==result['inputs']
    obs=result['outputs']['source_obs_ids'][0]
    source=client.get('/api/data/source/'+obs).get_json()
    assert source['value_raw']=='20' and source['source_row']==2
    assert client.get('/api/data/source/'+obs+'?plot_id=q').status_code==404
    rain=client.post('/api/data/query',json={**args,'parameter':'rainfall','depth_cm':None,'agg':'raw'}).get_json()
    assert [r['value'] for r in rain['outputs']['series']]==[2,3]
    assert rain['outputs']['series'][0]['qc_flag']=='rain_reset'
    assert client.get('/api/data/catalog?plot_id=q').get_json()['items']==[]
    with pytest.raises(ValueError): freeze('fixture-september')
    from services.weather_service import get_observed_weather
    assert get_observed_weather('p','2026-09-01','2026-09-04')==[]

def test_unconfirmed_precision_and_atomic(client,tmp_path):
    root,mapping,devices=fixture(tmp_path)
    with pytest.raises(ValueError): ingest(root,{'confirmed':False},devices,tmp_path/'log.md')
    assert precision_suspect('1.23E+16') and precision_suspect('123456789000000000')
    assert not precision_suspect('00123')
    (root/'b.csv').write_text('id,time,theta,rain,temp\n1.23E+16,2026-09-02T00:00:00,40,15,20\n',encoding='utf-8')
    with pytest.raises(ValueError): ingest(root,mapping,devices,tmp_path/'log.md')
    assert client.get('/api/data/catalog?plot_id=p').get_json()['items']==[]

def test_query_bounds(client):
    assert client.post('/api/data/query',json={'plot_id':'p'}).status_code==400
    assert client.post('/api/data/query',json={'plot_id':'p','parameter':'soil_moisture','start':'2025-01-01','end':'2026-09-01'}).status_code==400

def test_observation_freeze_immutable_and_crop_isolation(client,tmp_path):
    root,mapping,devices=fixture(tmp_path)
    mapping['source_type']='observation'
    mapping['files'][1]['crop']='tea'
    counts=ingest(root,mapping,devices,tmp_path/'log.md')
    assert counts[1]['skip']=='non_coffee'
    assert freeze('fixture-september')=='fixture-september'
    with pytest.raises(ValueError): ingest(root,mapping,devices,tmp_path/'log.md')
    with pytest.raises(ValueError): freeze('fixture-september')
