import copy
import csv
import json
from pathlib import Path
import pytest

from data_pipeline.ingest_project_raw import ingest_project, load_profile
from database.init_db import get_connection


def sample(root, name, records):
    path=root/name; path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['记录时间','参数名称','参数标识','参数数值','参数单位'])
        writer.writerows(records)
    return path


def setup_source(tmp_path):
    profile=copy.deepcopy(load_profile())
    profile.pop('water_content_convention',None)
    profile.pop('layer_intervals_cm',None)
    profile['sources']=[{'kind':'lujiangba','file_glob':'*.csv','location':'潞江坝','data_version':'test-raw'}]
    path=sample(tmp_path,'土壤监测1历史数据.csv',[
        ['2026/5/10 0:07','第1层土壤湿度','soilH','27.3','%RH'],
        ['2026/5/10 0:07','第1层土壤湿度','soilH','27.3','%RH'],
        ['2026/5/10 0:17','第1层土壤湿度','soilH','28.3','%RH'],
        ['invalid','第1层土壤湿度','soilH','30','%RH'],
        ['2026/5/10 0:17','第3层电导率','soilEC3','152',''],
        ['','','','','']])
    return profile,path


def test_raw_units_depths_lineage_idempotence_and_rollback(client,tmp_path):
    profile,path=setup_source(tmp_path)
    r=ingest_project(tmp_path,profile)['files'][0]
    assert (r['read'],r['imported'],r['duplicate'],r['rejected'],r['blank'])==(6,3,1,1,1)
    with get_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM obs_long WHERE depth_cm IS NOT NULL').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM import_rejections').fetchone()[0]==2
    plot=profile['plot_id']
    args=dict(plot_id=plot,parameter='soil_humidity_layer1_raw',start='2026-05-10',end='2026-05-10',agg='daily_mean')
    q=client.post('/api/data/query',json=args).get_json()
    assert q['status']=='success' and abs(q['outputs']['mean']-27.8)<1e-9
    assert q['units']['value']=='%RH' and 'soil_humidity_basis' in q['missing_fields']
    source=client.get('/api/data/source/'+q['outputs']['source_obs_ids'][0]).get_json()
    assert source['value_raw']=='27.3' and source['source_row']==2
    assert ingest_project(tmp_path,profile)['files'][0]['status']=='already_imported'
    cat=client.get('/api/data/catalog?plot_id='+plot).get_json()['items']
    ec=next(c for c in cat if c['parameter']=='soil_ec_layer3_raw')
    assert ec['unit']=='' and ec['usable_count']==0
    invalid=client.post('/api/data/query',json={**args,'parameter':'soil_ec_layer3_raw'}).get_json()
    assert invalid['code']=='E_DATA_EMPTY' and 'valid_observations' in invalid['missing_fields']
    included=client.post('/api/data/query',json={**args,'parameter':'soil_ec_layer3_raw','include_flagged':True}).get_json()
    assert included['outputs']['mean']==152 and included['units']['value']=='单位未注明'
    path.write_text(path.read_text(encoding='utf-8-sig')+'\n',encoding='utf-8-sig')
    with pytest.raises(ValueError,match='新数据版本'): ingest_project(tmp_path,profile)
    with get_connection() as conn: assert conn.execute('SELECT COUNT(*) FROM obs_long').fetchone()[0]==3


def test_sources_conflicts_and_pagination(client,tmp_path):
    profile,path=setup_source(tmp_path)
    sample(tmp_path,'土壤监测2历史数据.csv',[
        ['2026/5/10 0:07','湿度','soilH','35','%RH'],
        ['2026/5/10 0:17','湿度','soilH','36','%RH'],
        ['2026/5/10 0:17','湿度','soilH','39','%RH']])
    ingest_project(tmp_path,profile)
    args=dict(plot_id=profile['plot_id'],parameter='soil_humidity_layer1_raw',start='2026-05-10',end='2026-05-10',agg='raw')
    r=client.post('/api/data/query',json=args).get_json()
    assert r['missing_fields']==['device_id']
    args['device_id']='source:lujiangba:soil1'
    r=client.post('/api/data/query',json={**args,'limit':1}).get_json()
    assert r['outputs']['series_total']==2 and r['outputs']['next_offset']==1
    assert r['outputs']['mean']==27.8
    page2=client.post('/api/data/query',json={**args,'limit':1,'offset':1}).get_json()
    assert page2['outputs']['series'][0]['value']==28.3 and page2['outputs']['next_offset'] is None
    source2=client.post('/api/data/query',json={**args,'device_id':'source:lujiangba:soil2'}).get_json()
    assert source2['outputs']['n']==1 and source2['outputs']['mean']==35
    assert source2['outputs']['excluded_count']==1


def test_report_preserves_samples_missing_dates_and_no_rain_conversion(client,tmp_path):
    profile,path=setup_source(tmp_path)
    sample(tmp_path,'环境监测1历史数据.csv',[
        ['2026/5/10 0:07','降雨量','rainF','100','mm'],
        ['2026/5/10 0:17','降雨量','rainF','100','mm']])
    env=tmp_path/'环境监测1历史数据.csv'
    env.write_text(env.read_text(encoding='utf-8-sig').replace('参数标识','端口名称').replace('rainF','P11-降雨量'),encoding='utf-8-sig')
    ingest_project(tmp_path,profile)
    from services.weather_service import get_observed_weather
    assert get_observed_weather(profile['plot_id'],'2026-05-10','2026-05-10')==[]
    from data_pipeline.ingest_project_soil import ingest_report
    soil=json.loads(Path('data_pipeline/soil_report_2026T108.json').read_text(encoding='utf-8'))
    (tmp_path/'report.pdf').write_bytes(b'test report bytes only, not a real report')
    soil['source_path']='report.pdf'
    assert ingest_report(soil,tmp_path)['results']==81
    assert ingest_report(soil,tmp_path)['status']=='already_imported'
    r=client.get('/api/data/soil-reports?plot_id='+profile['plot_id']).get_json()
    assert len(r['items'])==9
    assert r['items'][0]['sample_date'] is None and r['items'][0]['depth_top_cm']==0
    assert r['items'][0]['received_date']=='2026-03-26'
    assert [s['sample_label'] for s in r['items'] if s['is_representative']]==['C06']
    assert r['representative_sample']['lab_sample_id']=='2026T108008'
    assert r['sampling_context']['location']=='监测器旁'
    assert all(s['depth_top_cm']==0 and s['depth_bottom_cm']==20 and s['depth_source']=='field_record' for s in r['items'])
    assert sum(len(s['measurements']) for s in r['items'])==81
    final=r['items'][-1]
    assert next(i['value'] for i in final['measurements'] if i['item']=='速效钾')==1320
    assert client.get('/api/data/soil-reports?plot_id=another').get_json()['items']==[]


def test_relink_moved_sources_by_hash_preserves_observations(client,tmp_path,monkeypatch):
    from data_pipeline import relink_sources
    profile,path=setup_source(tmp_path)
    ingest_project(tmp_path,profile)
    with get_connection() as conn:
        before=[tuple(r) for r in conn.execute('SELECT * FROM obs_long ORDER BY obs_id')]
        original=dict(conn.execute('SELECT * FROM raw_files').fetchone())
    moved=tmp_path/'renamed.csv';path.rename(moved)
    monkeypatch.setattr(relink_sources,'RUNTIME_DIR',tmp_path/'runtime')
    preview=relink_sources.relink(tmp_path)
    assert not preview['applied'] and len(preview['changes'])==1
    with get_connection() as conn: assert conn.execute('SELECT path FROM raw_files').fetchone()[0]==str(path)
    applied=relink_sources.relink(tmp_path,apply=True)
    assert Path(applied['backup']).is_file()
    with get_connection() as conn:
        assert [tuple(r) for r in conn.execute('SELECT * FROM obs_long ORDER BY obs_id')]==before
        current=dict(conn.execute('SELECT * FROM raw_files').fetchone())
    assert current=={**original,'path':str(moved)}
    assert not relink_sources.relink(tmp_path,apply=True)['changes']
    moved.write_text('modified',encoding='utf-8')
    with pytest.raises(ValueError,match='内容变化'): relink_sources.relink(tmp_path,apply=True)
    with get_connection() as conn: assert dict(conn.execute('SELECT * FROM raw_files').fetchone())==current


def test_user_confirmed_layers_conversion_keeps_original_rows(client,tmp_path):
    profile,path=setup_source(tmp_path)
    profile.update(water_content_convention='volumetric_percent_user_requested',layer_intervals_cm=[[0,15],[15,30],[30,45]])
    ingest_project(tmp_path,profile)
    args=dict(plot_id=profile['plot_id'],parameter='soil_humidity_layer1_raw',start='2026-05-10',end='2026-05-10',agg='daily_mean')
    result=client.post('/api/data/query',json=args).get_json()
    assert abs(result['outputs']['mean']-.278)<1e-12
    assert result['units']['value']=='cm3/cm3'
    assert result['inputs']['layer_interval_cm']=={'top':0,'bottom':15,'source':'用户确认'}
    assert result['missing_fields']==['sensor_calibration']
    with get_connection() as conn:
        row=conn.execute("SELECT value,value_raw,unit,depth_cm FROM obs_long WHERE parameter='soil_humidity_layer1_raw' ORDER BY ts LIMIT 1").fetchone()
    assert tuple(row)==(27.3,'27.3','%RH',None)
    item=next(c for c in client.get('/api/data/catalog?plot_id='+profile['plot_id']).get_json()['items'] if c['parameter']=='soil_humidity_layer1_raw')
    assert item['parameter_label']=='0–15cm 土壤体积含水率' and item['display_unit']=='cm3/cm3'


def test_remove_only_authorized_plots_with_backup(client,tmp_path,monkeypatch):
    profile,path=setup_source(tmp_path)
    ingest_project(tmp_path,profile)
    from database import init_db as database
    from data_pipeline import apply_catimor_confirmation as migration
    monkeypatch.setattr(migration,'DATABASE_PATH',database.DATABASE_PATH)
    monkeypatch.setattr(migration,'RUNTIME_DIR',tmp_path/'runtime')
    for pid in migration.REMOVED_IDS:
        client.post('/api/plot/init',json={'plot_id':pid,'plot_name':'潞江坝咖啡示范园'})
    result=migration.apply_confirmation()
    assert len(result['removed_plot_ids'])==3 and Path(result['backup']).is_file()
    listed=client.get('/api/plot/list').get_json()['items']
    assert len(listed)==1 and listed[0]['plot_name']=='云南普洱卡蒂姆咖啡基地'
    assert listed[0]['rain_source']=='natural_rainfall'
    with get_connection() as conn: assert conn.execute('SELECT COUNT(*) FROM obs_long').fetchone()[0]==3
    assert migration.apply_confirmation()['removed_plot_ids']==[]


def test_profile_sync_preserves_records_and_exposes_confirmed_fields(client,tmp_path,monkeypatch):
    profile,path=setup_source(tmp_path)
    ingest_project(tmp_path,profile)
    from database import init_db as database
    from data_pipeline import apply_catimor_confirmation as migration
    monkeypatch.setattr(migration,'DATABASE_PATH',database.DATABASE_PATH)
    monkeypatch.setattr(migration,'RUNTIME_DIR',tmp_path/'runtime')
    with get_connection() as conn:
        before=[tuple(r) for r in conn.execute('SELECT * FROM obs_long ORDER BY obs_id')]
        conn.execute('UPDATE plots SET area_mu=NULL WHERE plot_id=?',(profile['plot_id'],))
    client.post('/api/plot/init',json={'plot_id':migration.REMOVED_IDS[0],'plot_name':'潞江坝咖啡示范园'})
    result=migration.apply_confirmation(profile_only=True)
    assert result['removed_plot_ids']==[] and Path(result['backup']).is_file()
    plot=client.get('/api/plot/'+profile['plot_id']).get_json()['plot']
    assert plot['area_mu']==10 and plot['elevation_m']==1050
    assert (plot['latitude'],plot['longitude'])==(22.63470,101.00273)
    assert '15公斤/棵' in plot['irrigation_management'] and '有机肥' in plot['fertilizer_management']
    assert 'area_mu' not in plot['completeness']['missing']
    assert plot['planting_year']==2023 and plot['tree_age']==3
    assert plot['tree_age_reference_year']==2026 and '未提供种植月日' in plot['tree_age_source']
    assert plot['field_sources']['tree_age']=='estimated'
    assert plot['rainfall_input_policy']=='csv_observations_only'
    assert plot['irrigation_input_policy']=='management_description_only'
    assert plot['soil_parameter_policy']=='regional_literature_with_provenance'
    assert 'rainfall_accumulation_mode' not in plot['missing_fields']
    assert 'soil_hydraulic_parameters' in plot['missing_fields']
    assert plot['shade_level']=='无遮挡'
    assert (plot['row_spacing_m'],plot['plant_spacing_m'])==(2,1)
    assert plot['completeness']=={'filled':12,'total':12,'missing':[]}
    assert plot['plant_density']==333
    assert plot['field_sources']['soil_type']=='literature' and plot['field_sources']['plant_density']=='estimated'
    assert plot['auto_apply_to_hydrus'] is False
    with get_connection() as conn:
        assert [tuple(r) for r in conn.execute('SELECT * FROM obs_long ORDER BY obs_id')]==before
        row=conn.execute('SELECT area_mu,elevation_m,tree_age,shade_level,row_spacing_m,plant_spacing_m FROM plots WHERE plot_id=?',(profile['plot_id'],)).fetchone()
        assert tuple(row)==(10,1050,3,'无遮挡',2,1)
        assert conn.execute('SELECT COUNT(*) FROM farm_operations').fetchone()[0]==0
    assert client.get('/api/plot/'+migration.REMOVED_IDS[0]).status_code==200


def test_sampling_confirmation_does_not_rewrite_frozen_lab(client,tmp_path):
    from data_pipeline.ingest_project_soil import ingest_report
    from data_pipeline.ingest_project_raw import sync_confirmed_profile
    profile,path=setup_source(tmp_path)
    ingest_project(tmp_path,profile)
    soil=json.loads(Path('data_pipeline/soil_report_2026T108.json').read_text(encoding='utf-8'))
    (tmp_path/'report.pdf').write_bytes(b'isolated report fixture')
    soil['source_path']='report.pdf'
    ingest_report(soil,tmp_path)
    with get_connection() as conn:
        before=[tuple(r) for r in conn.execute('SELECT * FROM soil_lab_results ORDER BY result_id')]
        sync_confirmed_profile(conn,profile)
        sync_confirmed_profile(conn,profile)
        assert conn.execute('SELECT COUNT(*) FROM soil_reports').fetchone()[0]==81
        assert all(tuple(r)==(0,20,'field_record') for r in conn.execute('SELECT depth_top_cm,depth_bottom_cm,status FROM soil_reports'))
        assert before==[tuple(r) for r in conn.execute('SELECT * FROM soil_lab_results ORDER BY result_id')]
    from services.plot_context import load_plot_context
    context=load_plot_context(profile['plot_id'])
    assert context['reference_fields']['plant_density']['source']=='estimated'
    assert context['reference_fields']['soil_bulk_density']['source']=='literature'
    assert context['auto_apply_to_hydrus'] is False


def test_edit_preserves_hidden_reference_provenance(client,tmp_path,monkeypatch):
    from api.plot_api import PROFILE_FIELDS
    profile,path=setup_source(tmp_path);ingest_project(tmp_path,profile)
    monkeypatch.setitem(client.application.config,'SINGLE_PLOT_ID',profile['plot_id'])
    before=client.get('/api/plot/'+profile['plot_id']).get_json()['plot']
    payload={key:before.get(key) for key in PROFILE_FIELDS}
    payload.update(plot_id=profile['plot_id'],field_sources={key:before.get('field_sources',{}).get(key,'unknown') for key in PROFILE_FIELDS})
    assert client.post('/api/plot/init',json=payload).status_code==200
    after=client.get('/api/plot/'+profile['plot_id']).get_json()['plot']
    assert after['field_sources']['soil_bulk_density']=='literature'
    assert after['field_sources']['soil_texture']=='literature'
    assert after['field_notes']==before['field_notes'] and after['auto_apply_to_hydrus'] is False
