"""Confirmed mapping only; atomic import with source/QC lineage."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import yaml
from data_pipeline.profile_raw import read_tables, precision_suspect
from data_pipeline.schema import version_frozen
from database.init_db import get_connection, init_db, now_iso
from tools.material_paths import allowed_path, sha256_file, MATERIAL_ROOT

DOCS=Path(__file__).resolve().parents[2]/'docs'/'zyh'


def unresolved(value,path='mapping'):
    if isinstance(value,dict):
        return [item for k,v in value.items() for item in unresolved(v,path+'.'+str(k))]
    if isinstance(value,list):
        return [item for i,v in enumerate(value) for item in unresolved(v,path+f'[{i}]')]
    return [path] if value=='TODO_HUMAN' else []


def read_devices(path):
    with allowed_path(path).open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))
    for row in rows:
        if not row.get('device_id') or not row.get('plot_id') or precision_suspect(row['device_id']):
            raise ValueError('设备映射缺失或 precision_loss_suspect')
    return rows


def _ts(value,pattern):
    dt=datetime.fromisoformat(value.replace('Z','+00:00')) if pattern=='ISO8601' else datetime.strptime(value,pattern)
    return (dt.replace(tzinfo=ZoneInfo('Asia/Shanghai')) if dt.tzinfo is None else dt.astimezone(ZoneInfo('Asia/Shanghai')))


def ingest(root,mapping,device_map,log_path=None):
    root=allowed_path(root)
    pending=unresolved(mapping)
    if pending or mapping.get('confirmed') is not True:
        raise ValueError('映射未确认：'+','.join(pending or ['confirmed']))
    if mapping.get('source_type') not in {'observation','fixture'}:
        raise ValueError('source_type必须为observation或fixture')
    files=mapping.get('files') or []
    if not files or not device_map:
        raise ValueError('文件映射和设备地块映射不能为空')
    for item in files:
        if item.get('rain_mode') not in {'increment','cumulative'}:
            raise ValueError('rain_mode待人工确认')
        if not item.get('data_version') or not item.get('value_cols'):
            raise ValueError('data_version/value_cols缺失')
        if item.get('crop') not in {'coffee','茶','tea','水稻','rice'}:
            raise ValueError('crop待确认')
    init_db(); counters=[]
    with get_connection() as conn:
        conn.execute('BEGIN')
        for item in files:
            version=item['data_version']
            if version_frozen(conn, version):
                raise ValueError('冻结版本不可修改：'+version)
            pattern=item['file_glob']
            if Path(pattern).is_absolute() or '..' in Path(pattern).parts:
                raise ValueError('file_glob必须位于raw内')
            for path in sorted(root.glob(pattern)):
                path=allowed_path(path)
                if not path.is_relative_to(root):
                    raise ValueError('文件越出raw目录')
                count={'file':path.name,'data_version':version,'read':0,'dedup':0,'abnormal':0,'skip':0}
                if item['crop']!='coffee' or any(x in path.name.casefold() for x in ('茶','水稻','rice','tea')):
                    count['skip']='non_coffee'; counters.append(count); continue
                tables=read_tables(path)
                if len(tables)>1 and 'sheet' not in item:
                    raise ValueError('多工作表必须确认sheet')
                frame=tables[item['sheet']] if 'sheet' in item else next(iter(tables.values()))
                if any(str(v).strip().lower() in {'tea','rice','茶','水稻'} for v in frame.to_numpy().flatten()):
                    count['skip']='non_coffee_content'; counters.append(count); continue
                columns=[item['time_col'],item['device_col']]+[v['col'] for v in item['value_cols']]
                if any(c not in frame for c in columns):
                    raise ValueError('映射列不存在：'+path.name)
                if any(precision_suspect(v) for v in frame[item['device_col']]):
                    raise ValueError('precision_loss_suspect：'+path.name)
                digest=sha256_file(path); fid='rf_'+hashlib.sha256((digest+version).encode()).hexdigest()
                conn.execute('INSERT OR IGNORE INTO raw_files VALUES (?,?,?,?,?,?,?)',
                    (fid,str(path),digest,len(frame),now_iso(),version,mapping['source_type']))
                records=[]
                for index,row in frame.iterrows():
                    dt=_ts(str(row[item['time_col']]),item['time_format']); day=dt.date().isoformat()
                    device=str(row[item['device_col']]).strip()
                    matches=[d for d in device_map if d['device_id']==device and
                        (not d.get('valid_from') or day>=d['valid_from']) and (not d.get('valid_to') or day<=d['valid_to'])]
                    if len(matches)!=1:
                        raise ValueError('设备日期映射不唯一或未确认：'+device)
                    dm=matches[0]
                    for v in item['value_cols']:
                        depth=v.get('depth_cm',dm.get('depth_cm'))
                        depth=float(depth) if depth not in (None,'') else None
                        raw=str(row[v['col']]).strip(); value=None; flag='missing'
                        if raw:
                            try:
                                value=float(raw); flag='ok'
                                if not math.isfinite(value): value=None; flag='invalid_numeric'
                            except ValueError: flag='invalid_numeric'
                        parameter=v['parameter']; unit=v['unit']
                        if parameter=='soil_moisture':
                            if unit=='%' and value is not None: value/=100
                            elif unit not in {'%','cm3/cm3'}: raise ValueError('含水量单位未确认')
                            unit='cm3/cm3'
                        if parameter in {'rain','rainfall'} and unit!='mm': raise ValueError('降雨须为mm')
                        records.append({'device':device,'ts':dt.isoformat(),'day':day,'parameter':parameter,
                            'depth':depth,'raw':raw,'value':value,'unit':unit,'flag':flag,'row':int(index)+2,'plot':dm['plot_id']})
                previous={}
                for r in sorted(records,key=lambda r:(r['device'],r['parameter'],r['depth'] or -1,r['ts'])):
                    key=(r['device'],r['parameter'],r['depth'])
                    if r['parameter'] in {'rain','rainfall'} and item['rain_mode']=='cumulative':
                        current=r['value']; old=previous.get(key)
                        if current is None or old is None:
                            r['value']=None; r['flag']='rain_initial_unknown' if current is not None else 'missing'
                        elif current<old:
                            r['value']=current; r['flag']='rain_reset'
                        else: r['value']=current-old
                        previous[key]=current
                    limits={'soil_moisture':(0,.6),'soil_temperature':(-5,50),'air_temperature':(-5,50),'rain':(0,300),'rainfall':(0,300)}
                    if r['value'] is not None and r['parameter'] in limits and not limits[r['parameter']][0]<=r['value']<=limits[r['parameter']][1]: r['flag']='out_of_range'
                    count['read']+=1; count['abnormal']+=r['flag'] not in {'ok','rain_reset'}
                    prior=conn.execute('SELECT obs_id,priority FROM obs_long WHERE device_id=? AND ts=? AND parameter=? AND depth_cm IS ? AND data_version=?',
                        (r['device'],r['ts'],r['parameter'],r['depth'],version)).fetchone()
                    if prior:
                        count['dedup']+=1
                        if prior['priority']>=item['priority']: continue
                        conn.execute('DELETE FROM obs_long WHERE obs_id=?',(prior['obs_id'],))
                    oid='obs_'+hashlib.sha256(json.dumps([fid,r['row'],r['device'],r['ts'],r['parameter'],r['depth']],ensure_ascii=False).encode()).hexdigest()
                    conn.execute('INSERT INTO obs_long VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (oid,r['plot'],r['device'],r['ts'],r['day'],r['parameter'],r['depth'],r['raw'],r['value'],r['unit'],fid,r['row'],r['flag'],version,item['priority']))
                counters.append(count)
        daily_bad=conn.execute("SELECT device_id,date,parameter,data_version FROM obs_long WHERE parameter IN ('rain','rainfall') GROUP BY device_id,date,parameter,data_version HAVING SUM(value)>300").fetchall()
        for bad in daily_bad:
            affected=conn.execute("UPDATE obs_long SET qc_flag='out_of_range' WHERE device_id=? AND date=? AND parameter=? AND data_version=?",tuple(bad)).rowcount
            counters.append({'daily_rain_exceeds_300':dict(bad),'flagged':affected})
        if not counters:
            raise ValueError('未匹配任何原始文件，不生成观测')
        conn.execute('DELETE FROM device_plot_map')
        conn.executemany('INSERT INTO device_plot_map VALUES (?,?,?,?,?)',[(d['device_id'],d['plot_id'],float(d['depth_cm']) if d.get('depth_cm') else None,d.get('valid_from'),d.get('valid_to')) for d in device_map])
    log=allowed_path(log_path or DOCS/'清洗日志.md'); log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('a',encoding='utf-8') as stream:
        stream.write('\n## '+now_iso()+'\n'+json.dumps(counters,ensure_ascii=False,indent=2)+'\n规则：优先级去重；%/100；累计雨差分/复位；范围标记；null不插值；上海时区；非咖啡隔离；版本区分。\n')
    return counters


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--root',type=Path,default=MATERIAL_ROOT/'03_地块与监测数据'/'raw'); parser.add_argument('--mapping',type=Path,default=Path(__file__).with_name('column_mapping.yaml')); parser.add_argument('--devices',type=Path,default=Path(__file__).with_name('device_plot_map.csv'))
    args=parser.parse_args()
    try: print(json.dumps(ingest(args.root,yaml.safe_load(allowed_path(args.mapping).read_text(encoding='utf-8-sig')),read_devices(args.devices)),ensure_ascii=False))
    except (ValueError,KeyError) as error: print(str(error)); sys.exit(1)
