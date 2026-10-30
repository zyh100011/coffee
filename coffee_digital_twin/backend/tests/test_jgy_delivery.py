import csv
import json
from datetime import date, timedelta

import pytest

from services import jgy_delivery as delivery
from services.beps_gateway import run_beps_checked
from services.tool_result import make_tool_result, validate_tool_result


def make_delivery(root, bad_hour=False):
    for group in delivery.GROUPS:
        (root/group).mkdir(parents=True, exist_ok=True)
    (root/delivery.GROUPS[0]/'paper.md').write_text('literature fixture', encoding='utf-8')
    # This folder must remain unread and absent from material inventory.
    hidden = root/'06-咖啡农业真实需求与专家评测材料'
    hidden.mkdir(); (hidden/'private.txt').write_text('exclude', encoding='utf-8')
    for res, name in [('daily',delivery.DAILY), ('hourly',delivery.HOURLY)]:
        p = root/name; p.parent.mkdir(parents=True, exist_ok=True)
        columns = ['date_LST','hour_LST','time_standard','latitude_deg','longitude_deg'] + [v[0] for v in delivery.FIELDS[res].values()]
        with p.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader()
            for i in range(2):
                row = {field: 1 for field in columns}
                row.update(date_LST='2024/1/1' if res=='hourly' else f'2024/1/{i+1}',
                           hour_LST=0 if bad_hour else i, time_standard='LST', latitude_deg=22.6347, longitude_deg=101.0027)
                writer.writerow(row)


def test_import_idempotent_and_grid_isolated(client, tmp_path):
    from database.init_db import get_connection
    client.post('/api/plot/init', json={'plot_id':delivery.PLOT,'plot_name':'fixture'})
    root=tmp_path/'delivery'; make_delivery(root)
    first=delivery.ingest(root); second=delivery.ingest(root)
    assert first==second
    with get_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM obs_long').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM gridded_weather').fetchone()[0]==4
    status=client.get('/api/data/team-materials').get_json()
    assert status['knowledge_ingested'] is False
    assert not any(r['path'].startswith('06-') for r in status['items'])
    assert status['items'] and all(len(r['sha256'])==64 for r in status['items'])
    query={'plot_id':delivery.PLOT,'start':'2024-01-01','end':'2024-01-01','resolution':'hourly'}
    result=client.post('/api/data/historical-weather/query',json=query).get_json()
    assert result['source_type']=='gridded_reanalysis' and result['time_standard']=='LST'
    assert [r['ts'] for r in result['items']]==['2024-01-01T00:00:00','2024-01-01T01:00:00']
    assert result['items'][1]['source_row']==3
    assert client.get('/api/data/historical-weather/catalog?plot_id=other').get_json()['items']==[]
    assert client.post('/api/data/historical-weather/query',json={**query,'plot_id':'other'}).status_code==400
    assert client.post('/api/data/historical-weather/query',json={**query,'end':'2026-01-01'}).status_code==400
    assert client.post('/api/data/historical-weather/query',json=[]).status_code==400
    # A failed replacement must preserve the previously imported rows.
    hour=root/delivery.HOURLY
    text=hour.read_text(encoding='utf-8'); hour.write_text(text.replace('2024/1/1,1,','2024/1/1,0,'),encoding='utf-8')
    with pytest.raises(ValueError, match='duplicate'):
        delivery.ingest(root)
    assert len(client.post('/api/data/historical-weather/query',json=query).get_json()['items'])==2


def model_inputs():
    weather=[dict(date=(date(2024,1,1)+timedelta(days=i)).isoformat(),source='observation',
                  tmin=15,tmax=25,radiation_mj=18,wind_ms=1) for i in range(7)]
    data={'task_id':'test_beps','plot_id':'p','start_date':'2024-01-01',
          'plot_info':{'shade_level':'无遮挡'},'weather_series':weather}
    common={'status':'success','plot_id':'p','time_range':{'start':'2024-01-01','end':'2024-01-08'},
            'model_version':'test-model','parameter_version':'test-params'}
    a=make_tool_result(tool='apsim',source_type='proxy_model',outputs={'lai':2.7},**common)
    h=make_tool_result(tool='hydrus',source_type='simulation_uncalibrated',outputs={'root_uptake_ratio':.7},**common)
    return data,a,h


def test_beps_missing_inputs_never_run_default_model(monkeypatch):
    import models.beps_adapter as adapter
    monkeypatch.setattr(adapter,'run_beps_model',lambda *a,**kw: pytest.fail('must not run'))
    data,a,h=model_inputs()
    a['outputs']={}
    result=run_beps_checked(data,a,h)
    assert result['status']=='missing_input' and result['outputs']=={}
    assert 'supported_canopy_input' in result['missing_fields'] and not validate_tool_result(result)
    data,a,h=model_inputs(); h['outputs']['root_uptake_ratio']=0
    assert 'water_factor_supported_range' in run_beps_checked(data,a,h)['missing_fields']
    data,a,h=model_inputs(); data['weather_series'][0].pop('wind_ms')
    assert 'verified_weather_fields' in run_beps_checked(data,a,h)['missing_fields']
    data,a,h=model_inputs(); h['plot_id']='other'
    assert 'hydrus_same_plot_window_provenance' in run_beps_checked(data,a,h)['missing_fields']
    data,a,h=model_inputs(); data['plot_info']['lai_use']='用户确认本期不作为模型输入'
    assert 'supported_canopy_input' in run_beps_checked(data,a,h)['missing_fields']


def test_beps_preflight_maps_confirmed_shade_and_tracks_upstream(monkeypatch):
    import models.beps_adapter as adapter
    captured={}
    def run(data,apsim_result,hydrus_result):
        captured.update(data=data,water=hydrus_result)
        return {'status':'ok','input_summary':{'lai':2.7,'water_factor':.7,'shade_degree':0},'growth_score':70}
    monkeypatch.setattr(adapter,'run_beps_model',run)
    data,a,h=model_inputs()
    result=run_beps_checked(data,a,h)
    assert captured['data']['plot_info']['shade_level']=='无遮阴'
    assert data['plot_info']['shade_level']=='无遮挡'
    assert captured['water']['root_uptake_ratio']==.7
    assert result['status']=='success' and result['inputs']['upstream']['water_factor']==h['evidence_id']
    assert not validate_tool_result(result)
