from pathlib import Path
import pytest
from database.init_db import get_connection
from services.rainfall import daily_rainfall
from models import hydrus_adapter as hydrus


def seed(records):
    with get_connection() as conn:
        conn.execute("INSERT INTO raw_files VALUES ('rainfile','fixture.csv','hash',1,'now','rain-v1','observation')")
        conn.execute("INSERT INTO data_versions VALUES ('rain-v1','now','{}','{}','isolated test')")
        for i,(day,hour,value,flag) in enumerate(records):
            conn.execute('INSERT INTO obs_long VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (f'rain{i}','rainplot','source:lujiangba:environment1',day+'T'+hour,day,'rainfall_raw',None,
                 str(value),value,'mm','rainfile',i+2,flag,'rain-v1',0))


def test_counter_residue_zero_spikes_qc_missing_and_no_reset(client):
    seed([('2026-06-09','00:00',99,'ok'),('2026-06-09','00:10',0,'ok'),
          ('2026-06-09','03:00',2.8,'ok'),('2026-06-09','04:00',0,'ok'),
          ('2026-06-09','05:00',2.8,'ok'),('2026-06-09','06:00',100,'out_of_range'),
          ('2026-06-10','01:00',3,'ok'),('2026-06-10','02:00',5,'ok'),
          ('2026-06-11','01:00',7,'ok')])
    r=daily_rainfall('rainplot',None,'2026-06-09','2026-06-12')
    assert [p['rain_mm'] for p in r['items']]==[2.8,5,0,None]
    assert r['items'][0]['discarded_before_reset']==1
    assert r['items'][1]['warnings'] and r['items'][3]['warnings']
    with get_connection() as conn:
        assert conn.execute("SELECT value FROM obs_long WHERE obs_id='rain0'").fetchone()[0]==99
    with pytest.raises(ValueError):daily_rainfall('rainplot','7a59d3a9','2026-06-09','2026-06-12')
    with pytest.raises(ValueError):daily_rainfall('rainplot',None,'2026-06-12','2026-06-09')
    assert all(p['rain_mm'] is None for p in daily_rainfall('other',None,'2026-06-09','2026-06-12')['items'])


def test_frozen_counter_written_and_read_back_from_atmosphere(client,tmp_path):
    expected=[2.8,25,21.8,7,.2,1.4,.8]
    seed([(f'2026-06-{9+i:02d}',hour,value,'ok') for i,rain in enumerate(expected)
          for hour,value in [('00:00',0),('02:00',rain)]])
    data={'plot_id':'rainplot','start_date':'2026-06-09','plot_info':{'rainfall_counter_review':{'model_daily_rain_enabled':True}}}
    base,_=hydrus._build_hydrus_input(data)
    changed,_=hydrus._build_hydrus_input({**data,'scenario':{'extra_irrigation_mm':20}})
    out=hydrus._prepare_input_files(base,tmp_path)
    assert out['daily_prec_cm']==pytest.approx([x/10 for x in expected],abs=.001)
    assert [b-a for a,b in zip(base['daily_prec_cm'],changed['daily_prec_cm'])]==pytest.approx([2,0,0,0,0,0,0])
    assert sum(expected)==pytest.approx(59)
    from services.rainfall import query_daily
    result=query_daily({'plot_id':'rainplot','parameter':'rainfall_daily','start':'2026-06-09','end':'2026-06-15'})
    assert result['status']=='success' and result['outputs']['total']==pytest.approx(59)


def test_unfrozen_counter_cannot_enter_model(client):
    seed([('2026-06-09','00:00',0,'ok'),('2026-06-09','01:00',99,'ok')])
    with get_connection() as conn:conn.execute("DELETE FROM data_versions WHERE data_version='rain-v1'")
    assert daily_rainfall('rainplot',None,'2026-06-09','2026-06-09')['items'][0]['rain_mm'] is None
