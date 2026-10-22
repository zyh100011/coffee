"""Normalized CSV contracts; never infer unknown instrument layouts."""
import csv
from datetime import date
from database.init_db import get_connection,init_db
from tools.material_paths import allowed_path
FIELDS={
 'lai_obs':['plot_id','date','quadrat','plant','repeat_no','lai','method','source_file_id','source_row'],
 'farm_events':['plot_id','date','op_type','amount','unit','source','source_ref','verified'],
 'soil_reports':['plot_id','sample_date','depth_top_cm','depth_bottom_cm','item','value','unit','method','report_ref','status']}

def ingest_form(table,path,confirmed=False):
    if not confirmed: raise ValueError('格式未确认；请按契约转换并保留原文件行号')
    if table not in FIELDS: raise ValueError('表不在白名单')
    with allowed_path(path).open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames!=FIELDS[table]: raise ValueError('字段需完全匹配：'+','.join(FIELDS[table]))
        rows=list(reader)
    if not rows: raise ValueError('空资料不入库')
    for row in rows:
        if not row['plot_id']: raise ValueError('plot_id缺失')
        if row.get('date') or row.get('sample_date'): date.fromisoformat(row.get('date') or row['sample_date'])
        elif table!='soil_reports' or row['status']!='pending': raise ValueError('日期缺失')
        if table=='lai_obs' and any(not row[k] for k in ('quadrat','plant','repeat_no','method','source_file_id','source_row')): raise ValueError('LAI层级/来源缺失')
        if table=='farm_events' and (row['verified']!='1' or not row['source_ref']): raise ValueError('事件须已核实且有来源')
        if table=='soil_reports' and row['status'] not in {'pending','verified'}: raise ValueError('报告状态未确认')
        if table=='soil_reports' and row['status']=='pending' and row['value']: raise ValueError('pending不能填数值')
        for key in ('lai','amount','value','depth_top_cm','depth_bottom_cm'):
            if key in row: row[key]=float(row[key]) if row[key] else None
        if table=='lai_obs': row['source_row']=int(row['source_row'])
        if table=='farm_events': row['verified']=1
    init_db()
    with get_connection() as conn:
        if table=='lai_obs':
            for row in rows:
                if not conn.execute('SELECT 1 FROM raw_files WHERE file_id=?',(row['source_file_id'],)).fetchone(): raise ValueError('先登记LAI原文件raw_files')
        fields=FIELDS[table]
        conn.executemany('INSERT INTO '+table+' ('+','.join(fields)+') VALUES ('+','.join('?' for _ in fields)+')',[[r[k] for k in fields] for r in rows])
    return len(rows)
