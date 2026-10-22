"""All data here are isolated synthetic inputs for importer logic only."""
import gc
import json
import sqlite3
from contextlib import closing
import pytest
from database import init_db as db
from tools.seed_demo import import_frozen
from tools.material_paths import sha256_file

def snapshot(tmp_path,monkeypatch):
    source=tmp_path/'synthetic_snapshot.db'
    monkeypatch.setattr(db,'DATABASE_PATH',source);db.init_db()
    raw=tmp_path/'synthetic.csv';raw.write_text('EXPLICIT TEST FIXTURE',encoding='utf-8')
    profile={'plot_id':'p','plot_name':'构造的测试地块','crop':'coffee','field_sources':{'plot_name':'field_record'}}
    with closing(db.get_connection()) as conn:
        with conn:
            conn.execute('INSERT INTO plots(plot_id,plot_name,raw_json,created_at,updated_at) VALUES (?,?,?,?,?)',('p',profile['plot_name'],json.dumps(profile),'now','now'))
            conn.execute('INSERT INTO raw_files VALUES (?,?,?,?,?,?,?)',('f',str(raw),sha256_file(raw),1,'now','test-only','observation'))
            conn.execute('INSERT INTO obs_long VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('o','p','001','2026-09-01T00:00:00','2026-09-01','soil_moisture',40,'20',.2,'cm3/cm3','f',2,'ok','test-only',1))
            conn.execute('INSERT INTO data_versions VALUES (?,?,?,?,?)',('test-only','now',json.dumps({'f':sha256_file(raw)}),json.dumps({'obs_long':1}),'synthetic importer test only'))
    return source,raw

def test_missing_restricted_and_same_path(tmp_path):
    with pytest.raises(ValueError,match='缺少'): import_frozen(tmp_path/'missing.db',tmp_path/'out.db')
    with pytest.raises(ValueError,match='正式测试'): import_frozen(tmp_path/'06_正式测试资料'/'s.db',tmp_path/'out.db')
    with pytest.raises(ValueError,match='相同'): import_frozen(tmp_path/'s.db',tmp_path/'s.db')
    assert not (tmp_path/'out.db').exists()

def test_import_and_refuse_mutated_demo_or_unverified(tmp_path,monkeypatch):
    source,raw=snapshot(tmp_path,monkeypatch)
    out=tmp_path/'demo.db'
    result=import_frozen(source,out,'test-only')
    assert result['observations']==1 and result['plots']==1
    with closing(sqlite3.connect(out)) as conn:
        assert conn.execute('SELECT value FROM obs_long').fetchone()[0]==.2
        assert conn.execute('SELECT COUNT(*) FROM assistant_traces').fetchone()[0]==0
    with pytest.raises(ValueError,match='非空'): import_frozen(source,out,'test-only')
    raw.write_text('changed',encoding='utf-8')
    with pytest.raises(ValueError,match='哈希'): import_frozen(source,tmp_path/'bad.db','test-only')
    raw.write_text('EXPLICIT TEST FIXTURE',encoding='utf-8')
    with closing(sqlite3.connect(source)) as conn:
        with conn: conn.execute("UPDATE raw_files SET source_type='fixture'")
    with pytest.raises(ValueError,match='fixture'): import_frozen(source,tmp_path/'bad.db','test-only')
    with closing(sqlite3.connect(source)) as conn:
        with conn:
            conn.execute("UPDATE raw_files SET source_type='observation'")
            conn.execute("UPDATE plots SET raw_json=?",(json.dumps({'plot_name':'unverified','crop':'coffee'}),))
    with pytest.raises(ValueError,match='档案'): import_frozen(source,tmp_path/'bad.db','test-only')
