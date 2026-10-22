"""Import confirmed profiles and an existing frozen snapshot; never generate demo rows."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from tools.material_paths import allowed_path,sha256_file


def import_frozen(source, destination, version='data-v1.0'):
    source,destination=allowed_path(source),allowed_path(destination)
    if source==destination: raise ValueError('源快照与目标不能相同')
    if not source.is_file(): raise ValueError('缺少真实冻结数据库快照；先完成H3/H4，不生成虚构数据')
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src:
        src.row_factory=sqlite3.Row
        tables={r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'plots','raw_files','obs_long','data_versions'}<=tables: raise ValueError('快照缺少地块/原文件/观测/冻结版本表')
        frozen=src.execute('SELECT * FROM data_versions WHERE data_version=?',(version,)).fetchone()
        files=src.execute('SELECT * FROM raw_files WHERE data_version=?',(version,)).fetchall()
        observations=src.execute('SELECT * FROM obs_long WHERE data_version=?',(version,)).fetchall()
        if not frozen or not files or not observations: raise ValueError('缺少非空冻结版本 '+version)
        if any(r['source_type']!='observation' for r in files): raise ValueError('拒绝fixture/demo来源，需确认的实测资料')
        if any(r['source_file_id'] not in {f['file_id'] for f in files} for r in observations): raise ValueError('观测来源不属于冻结文件清单')
        if {r['file_id']:r['sha256'] for r in files}!=json.loads(frozen['file_hashes_json']): raise ValueError('冻结文件清单不一致')
        if sum(r['value'] is not None and r['qc_flag'] in ('ok','rain_reset') for r in observations)!=json.loads(frozen['row_counts_json'])['obs_long']: raise ValueError('冻结有效行数不一致')
        for r in files:
            if sha256_file(r['path'])!=r['sha256']: raise ValueError('原文件哈希不一致')
        plots=[]
        for plot_id in sorted({r['plot_id'] for r in observations}):
            row=src.execute('SELECT * FROM plots WHERE plot_id=?',(plot_id,)).fetchone()
            raw=json.loads(row['raw_json']) if row else {}
            if not row or raw.get('crop')!='coffee' or not raw.get('plot_name') or raw.get('field_sources',{}).get('plot_name') not in ('field_record','现场记录'):
                raise ValueError('缺少已确认来源的真实地块档案：'+str(plot_id))
            if any(raw.get(k) not in (None,'') and raw.get('field_sources',{}).get(k) not in ('field_record','现场记录') for k in ('coffee_variety','tree_age','area_mu','latitude','longitude','elevation_m','soil_type','shade_level','plant_density','row_spacing_m','plant_spacing_m')):
                raise ValueError('地块含未核实字段，不能作为真实演示档案：'+plot_id)
            plots.append(row)
        payload={'plots':plots,'raw_files':files,'obs_long':observations,'data_versions':[frozen]}
        if 'device_plot_map' in tables:
            devices={r['device_id'] for r in observations}
            payload['device_plot_map']=[r for r in src.execute('SELECT * FROM device_plot_map') if r['device_id'] in devices]
        # Deliberately omit unversioned ancillary rows, traces and model results.
        # The existing ingestion tools import separately verified events/forms.
        from database.init_db import get_connection
        import database.init_db as db
        old=db.DATABASE_PATH
        try:
            db.DATABASE_PATH=destination
            # Existing nonempty targets are never overwritten or merged.
            if destination.exists():
                with closing(sqlite3.connect(destination)) as check:
                    names=[r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
                    if any(check.execute('SELECT 1 FROM "'+name.replace('"','""')+'" LIMIT 1').fetchone() for name in names): raise ValueError('目标数据库非空，请使用新路径；不会覆盖已有资料')
            destination.parent.mkdir(parents=True,exist_ok=True)
            db.init_db()
            with closing(get_connection()) as conn:
                with conn:
                    for table,rows in payload.items():
                        for row in rows:
                            columns=list(row.keys())
                            conn.execute('INSERT INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',tuple(row))
        finally: db.DATABASE_PATH=old
    return {'status':'success','data_version':version,'plots':len(plots),'observations':len(observations),
            'note':'仅复制确认地块、冻结观测及其来源映射；不生成假数据，不复制未分版本的农事/LAI/土壤记录'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path,help='确认后的冻结SQLite快照')
    parser.add_argument('--out',required=True,type=Path,help='新的演示数据库路径')
    parser.add_argument('--version',default='data-v1.0')
    args=parser.parse_args()
    try: print(json.dumps(import_frozen(args.source,args.out,args.version),ensure_ascii=False))
    except (ValueError,OSError,sqlite3.Error,KeyError) as error: print('缺项/拒绝导入：'+str(error));sys.exit(1)
