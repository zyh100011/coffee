"""Import confirmed profiles and an existing frozen snapshot; never generate demo rows."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from tools.material_paths import allowed_path,sha256_file


def import_frozen(source, destination, version='data-v1.0', raw_root=None, team_root=None):
    source,destination=allowed_path(source),allowed_path(destination)
    if source==destination: raise ValueError('源快照与目标不能相同')
    if not source.is_file(): raise ValueError('缺少真实冻结数据库快照；先完成H3/H4，不生成虚构数据')
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src:
        src.row_factory=sqlite3.Row
        tables={r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'plots','raw_files','obs_long','data_versions'}<=tables: raise ValueError('快照缺少地块/原文件/观测/冻结版本表')
        frozen=src.execute('SELECT * FROM data_versions WHERE data_version=?',(version,)).fetchone()
        files=[dict(r) for r in src.execute('SELECT * FROM raw_files WHERE data_version=?',(version,))]
        observations=src.execute('SELECT * FROM obs_long WHERE data_version=?',(version,)).fetchall()
        if not frozen or not files or not observations: raise ValueError('缺少非空冻结版本 '+version)
        if any(r['source_type']!='observation' for r in files): raise ValueError('拒绝fixture/demo来源，需确认的实测资料')
        if any(r['source_file_id'] not in {f['file_id'] for f in files} for r in observations): raise ValueError('观测来源不属于冻结文件清单')
        if {r['file_id']:r['sha256'] for r in files}!=json.loads(frozen['file_hashes_json']): raise ValueError('冻结文件清单不一致')
        if sum(r['value'] is not None and r['qc_flag'] in ('ok','rain_reset') for r in observations)!=json.loads(frozen['row_counts_json'])['obs_long']: raise ValueError('冻结有效行数不一致')
        if raw_root:
            root=allowed_path(raw_root); candidates={}
            if not root.is_dir(): raise ValueError('原始资料目录不存在')
            for current,dirs,names in os.walk(root,followlinks=False):
                dirs[:]=[d for d in dirs if not d.casefold().startswith('06_正式测试资料')]
                for name in names:
                    path=allowed_path(Path(current)/name)
                    if not path.is_relative_to(root): raise ValueError('原始资料路径越界')
                    digest=sha256_file(path);candidates.setdefault(digest,[]).append(path)
            for row in files:
                matches=candidates.get(row['sha256'],[])
                if len(matches)!=1: raise ValueError('原文件哈希未唯一匹配')
                row['path']=str(matches[0])
        for r in files:
            if sha256_file(r['path'])!=r['sha256']: raise ValueError('原文件哈希不一致')
        plots=[]
        for plot_id in sorted({r['plot_id'] for r in observations}):
            row=src.execute('SELECT * FROM plots WHERE plot_id=?',(plot_id,)).fetchone()
            raw=json.loads(row['raw_json']) if row else {}
            if not row or raw.get('crop')!='coffee' or not raw.get('plot_name') or not (raw.get('field_sources',{}).get('plot_name') in ('field_record','现场记录') or (raw.get('data_scope')=='single_base_user_confirmed' and raw.get('confirmation_source') and raw.get('plot_id')==plot_id)):
                raise ValueError('缺少已确认来源的真实地块档案：'+str(plot_id))
            sources=raw.get('field_sources',{})
            from data_pipeline.ingest_project_raw import load_profile
            confirmed_profile=load_profile()
            for key in ('coffee_variety','tree_age','area_mu','latitude','longitude','elevation_m','soil_type','shade_level','plant_density','row_spacing_m','plant_spacing_m','soil_bulk_density','soil_texture'):
                if raw.get(key) in (None,'') or sources.get(key) in ('field_record','现场记录'): continue
                derived_age=(key=='tree_age' and sources.get(key)=='estimated' and sources.get('planting_year')=='field_record'
                    and type(raw.get('planting_year')) is int and type(raw.get('tree_age_reference_year')) is int
                    and raw.get('tree_age')==raw['tree_age_reference_year']-raw['planting_year'] and bool(raw.get('tree_age_source')))
                reference=(plot_id==confirmed_profile['plot_id'] and key in ('soil_type','plant_density','soil_bulk_density','soil_texture')
                    and raw.get(key)==confirmed_profile.get(key) and raw.get('auto_apply_to_hydrus') is False
                    and sources.get(key)==confirmed_profile.get('field_sources',{}).get(key)
                    and raw.get('field_notes',{}).get(key)==confirmed_profile.get('field_notes',{}).get(key))
                if not (derived_age or reference): raise ValueError('地块含未核实字段，不能作为真实演示档案：'+plot_id)
            plots.append(row)
        payload={'plots':plots,'raw_files':files,'obs_long':observations,'data_versions':[frozen]}
        if 'device_plot_map' in tables:
            devices={r['device_id'] for r in observations}
            payload['device_plot_map']=[r for r in src.execute('SELECT * FROM device_plot_map') if r['device_id'] in devices]
        file_ids={f['file_id'] for f in files};plot_ids={r['plot_id'] for r in plots}
        if 'data_release_sources' in tables: payload['data_release_sources']=src.execute('SELECT * FROM data_release_sources WHERE data_version=?',(version,)).fetchall()
        if 'observation_sources' in tables: payload['observation_sources']=[r for r in src.execute('SELECT * FROM observation_sources') if r['device_id'] in {o['device_id'] for o in observations}]
        if 'soil_lab_results' in tables: payload['soil_lab_results']=[r for r in src.execute('SELECT * FROM soil_lab_results') if r['source_file_id'] in file_ids and r['plot_id'] in plot_ids]
        if 'soil_reports' in tables: payload['soil_reports']=[r for r in src.execute('SELECT * FROM soil_reports') if r['plot_id'] in plot_ids]
        if 'import_rejections' in tables: payload['import_rejections']=[r for r in src.execute('SELECT * FROM import_rejections') if r['file_id'] in file_ids]
        # Gridded weather remains a separate product, only copied with matching source assets.
        if team_root and 'gridded_weather' in tables:
            team=allowed_path(team_root);weather=[r for r in src.execute('SELECT * FROM gridded_weather') if r['plot_id'] in plot_ids]
            for path,digest in {(r['source_path'],r['source_sha256']) for r in weather}:
                resolved=allowed_path(team/path)
                if not resolved.is_relative_to(team) or sha256_file(resolved)!=digest: raise ValueError('历史网格气象来源哈希不一致')
            payload['gridded_weather']=weather
            for table in ('team_materials','team_imports'):
                if table in tables:payload[table]=src.execute('SELECT * FROM '+table).fetchall()
        # Never import mutable conversations, model tasks, reports or farm-event guesses.

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
                            conn.execute('INSERT INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',tuple(row[column] for column in columns))
                    # New destination only: current confirmed profile metadata is
                    # independent of the unchanged frozen observation release.
                    # Keep the source snapshot read-only, also during demo reset.
                    if version=='data-v1.0' and confirmed_profile['plot_id'] in plot_ids:
                        from data_pipeline.ingest_project_raw import sync_confirmed_profile
                        sync_confirmed_profile(conn,confirmed_profile)
        finally: db.DATABASE_PATH=old
    return {'status':'success','data_version':version,'plots':len(plots),'observations':len(observations),
            'soil_measurements':len(payload.get('soil_lab_results',[])),'weather_rows':len(payload.get('gridded_weather',[])),
            'note':'保留来源及树龄估算标签；网格气象须显式提供team_root；不复制会话/模型/报告或未核验农事'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path,help='确认后的冻结SQLite快照')
    parser.add_argument('--out',required=True,type=Path,help='新的演示数据库路径')
    parser.add_argument('--version',default='data-v1.0')
    parser.add_argument('--raw-root',type=Path,help='迁移电脑时按哈希重新定位原始文件；不能含正式题集')
    parser.add_argument('--team-root',type=Path,help='可选：简交付目录，校验来源后复制历史网格气象')
    args=parser.parse_args()
    try: print(json.dumps(import_frozen(args.source,args.out,args.version,args.raw_root,args.team_root),ensure_ascii=False))
    except (ValueError,OSError,sqlite3.Error,KeyError) as error: print('缺项/拒绝导入：'+str(error));sys.exit(1)
