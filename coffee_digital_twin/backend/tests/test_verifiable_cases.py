"""Exporter contract verified on isolated, explicitly constructed fixtures."""
import json
import pytest
from database.init_db import get_connection
from data_pipeline.freeze import freeze
from tools.export_verifiable_cases import export
from tools.material_paths import sha256_file


def test_partial_and_blocked_export(client,tmp_path):
    target = tmp_path/'cases.json'
    with pytest.raises(ValueError,match='冻结实测'): export(target)
    assert not target.exists()
    result = export(target,hydrus_only=True)
    assert result['status']=='partial' and not result['data_cases']
    assert result['missing_fields'] and len(result['hydrus_cases'])==4
    with pytest.raises(ValueError,match='正式测试'): export(tmp_path/'06_正式测试资料'/'cases.json',hydrus_only=True)


def test_export_reexecute_sql_and_snapshot_guard(client,tmp_path):
    # Test-only source labels exercise freeze/export logic; no production database is used.
    raw = tmp_path/'synthetic.csv'; raw.write_text('TEST ONLY SYNTHETIC INPUT',encoding='utf-8')
    with get_connection() as conn:
        conn.execute('INSERT INTO raw_files VALUES (?,?,?,?,?,?,?)',('f',str(raw),sha256_file(raw),18,'now','test-frozen','observation'))
        for plot,depth in [('fixture_p',40),('fixture_q',60)]:
            for i in range(1,11):
                if i==5: continue
                day=f'2026-09-{i:02d}'
                conn.execute('INSERT INTO obs_long VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (plot+str(i),plot,plot+'device',day+'T12:00:00',day,'soil_moisture',depth,str(i),i/100,'cm3/cm3','f',i,'ok','test-frozen',1))
    freeze('test-frozen')
    a=export(tmp_path/'a.json',version='test-frozen')
    b=export(tmp_path/'b.json',version='test-frozen')
    assert a==b and len(a['data_cases'])==20
    assert len({c['query']['plot_id'] for c in a['data_cases']})==2
    assert any(c['result']['outputs'].get('missing_days',0)>0 for c in a['data_cases'])
    assert a['status']=='ready'
    assert all(c['result']['status']=='success' for c in a['data_cases'])
    with get_connection() as conn:
        for case in a['data_cases']:
            rows=conn.execute(case['reproduce']['sql'],case['reproduce']['parameters']).fetchall()
            output=case['result']['outputs']
            if rows:
                assert output['n']==len(rows)
                assert abs(output['mean']-sum(r['value'] for r in rows)/len(rows))<1e-9
            else: assert output=={}
    raw.write_text('changed',encoding='utf-8')
    with pytest.raises(ValueError,match='哈希'): export(tmp_path/'bad.json',version='test-frozen')
    assert not (tmp_path/'bad.json').exists()


def test_export_separates_devices_units_and_rejects_failed_queries(client,tmp_path,monkeypatch):
    import tools.export_verifiable_cases as exporter
    raw=tmp_path/'sources.csv';raw.write_text('TEST ONLY MULTISOURCE',encoding='utf-8')
    with get_connection() as conn:
        conn.execute('INSERT INTO raw_files VALUES (?,?,?,?,?,?,?)',('multi',str(raw),sha256_file(raw),40,'now','multi-frozen','observation'))
        for device,unit,base in [('001','cm3/cm3',.1),('002','cm3/cm3',.3),('001','%',20)]:
            for i in range(1,11):
                day=f'2026-09-{i:02d}'
                conn.execute('INSERT INTO obs_long VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (device+unit+str(i),'p',device,day+('T01:00:00' if unit=='%' else 'T00:00:00'),day,'soil_moisture',40,str(base),base,unit,'multi',i,'ok','multi-frozen',1))
    freeze('multi-frozen')
    package=export(tmp_path/'multi.json',version='multi-frozen')
    assert len(package['data_cases'])==20
    assert len(package['coverage']['sources'])==3
    with get_connection() as conn:
        for case in package['data_cases']:
            args=case['query']
            assert args['device_id'] in ('001','002')
            rows=conn.execute(case['reproduce']['sql'],case['reproduce']['parameters']).fetchall()
            assert {r['device_id'] for r in rows}=={args['device_id']}
            assert {r['unit'] for r in rows}=={args['unit']}
            assert len(rows)==case['result']['outputs']['n']
            assert case['result']['outputs']['mean']==pytest.approx(sum(r['value'] for r in rows)/len(rows))
    monkeypatch.setattr(exporter,'query',lambda *a,**kw:{'status':'missing_input','source_type':'observation'})
    target=tmp_path/'refused.json'
    with pytest.raises(ValueError,match='拒绝标记就绪'): export(target,version='multi-frozen')
    assert not target.exists()
