"""Bounded observation queries with row-level lineage."""
from datetime import date, timedelta
from collections import defaultdict
import json
import re
from database.init_db import get_connection
from services.tool_result import make_tool_result
from data_pipeline.ingest_project_raw import load_profile

def display_source(device):
    match=re.search(r':(soil|environment)([123])$',device or '')
    if match:return ('土壤监测点' if match[1]=='soil' else '环境监测点')+match[2]
    return '基地气象站'


def catalog(plot_id):
    with get_connection() as conn:
        plot=conn.execute('SELECT raw_json FROM plots WHERE plot_id=?',(plot_id,)).fetchone()
        rows=conn.execute('''SELECT o.parameter,o.depth_cm,o.device_id,o.unit,o.data_version,
            MIN(o.date) start,MAX(o.date) end,COUNT(*) n,
            MIN(CASE WHEN o.qc_flag IN ('ok','rain_reset') AND o.value IS NOT NULL THEN o.date END) valid_start,
            MAX(CASE WHEN o.qc_flag IN ('ok','rain_reset') AND o.value IS NOT NULL THEN o.date END) valid_end,
            SUM(CASE WHEN o.qc_flag IN ('ok','rain_reset') AND o.value IS NOT NULL THEN 1 ELSE 0 END) usable_count,
            s.label source_label,s.location,s.identity_kind
            FROM obs_long o LEFT JOIN observation_sources s ON s.device_id=o.device_id
            WHERE o.plot_id=? GROUP BY o.parameter,o.depth_cm,o.device_id,o.unit,o.data_version
            ORDER BY o.parameter,o.device_id,o.unit,o.data_version''',(plot_id,)).fetchall()
    labels={v['parameter']:v['label'] for v in load_profile()['parameters'].values()}
    items=[{'parameter':r['parameter'],'parameter_label':labels.get(r['parameter'],r['parameter']),
             'depth_cm':r['depth_cm'],'start':r['start'],'end':r['end'],'valid_start':r['valid_start'],'valid_end':r['valid_end'],
             'device_id':r['device_id'],'devices':[r['device_id']], 'unit':r['unit'],
             'data_version':r['data_version'],'data_versions':[r['data_version']],
             'source_label':display_source(r['device_id']),'display_source':display_source(r['device_id']),
             'identity_kind':r['identity_kind'],'n':r['n'],'usable_count':r['usable_count']} for r in rows]
    profile=json.loads(plot['raw_json']) if plot else {}
    for item in items:
        item['hidden_reason']=('无有效记录' if not item['usable_count'] else '单位未注明' if not item['unit'] else '仅一条原始记录' if item['n']<=1 else None)
        match=re.search(r'_layer([123])',item['parameter'])
        layers=profile.get('layer_intervals_cm',[])
        if match and len(layers)==3:
            top,bottom=layers[int(match[1])-1]
            item.update(depth_top_cm=top,depth_bottom_cm=bottom)
            if item['parameter'].startswith('soil_humidity_layer') and profile.get('water_content_convention')=='volumetric_percent_user_requested':
                item['parameter_label']=f'{top}–{bottom}cm 土壤体积含水率'
                item['display_unit']='cm3/cm3'
            else:
                item['parameter_label']=item['parameter_label'].replace('（埋深未确认）','')+f'（{top}–{bottom}cm）'
    if profile.get('rainfall_counter_review',{}).get('model_daily_rain_enabled'):
        items += [dict(item,parameter='rainfall_daily',parameter_label='日降雨量',display_unit='mm',derived=True)
                  for item in items if item['parameter']=='rainfall_raw' and item['unit']=='mm'
                  and re.fullmatch(r'source:lujiangba:environment[123]',item['device_id']) and not item['hidden_reason']]
    return items


def query(args,ctx=None):
    if args.get('parameter')=='rainfall_daily':
        from services.rainfall import query_daily
        return query_daily(args,ctx)
    ctx=ctx or {}; result=make_tool_result(tool='data_query',task_id=ctx.get('task_id'),plot_id=args.get('plot_id'),inputs=dict(args))
    missing=[k for k in ('plot_id','parameter','start','end') if not args.get(k)]
    if missing:
        result.update(status='missing_input',missing_fields=missing); return result
    try:
        start=date.fromisoformat(args['start']); end=date.fromisoformat(args['end'])
        if not 0<=(end-start).days<=365: raise ValueError('日期范围必须1–366天')
        agg=args.get('agg','raw')
        if agg not in {'raw','daily_mean'}: raise ValueError('agg无效')
        if 'include_flagged' in args and not isinstance(args['include_flagged'],bool): raise ValueError('include_flagged须为布尔值')
        depth=args.get('depth_cm')
        if depth is not None and (isinstance(depth,bool) or not isinstance(depth,(int,float))): raise ValueError('depth_cm须数值')
        for key in ('device_id','data_version','unit'):
            if key in args and not isinstance(args[key],str): raise ValueError(key+'须为字符串')
        limit=args.get('limit',500); offset=args.get('offset',0)
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=1000: raise ValueError('limit须为1–1000整数')
        if isinstance(offset,bool) or not isinstance(offset,int) or offset<0: raise ValueError('offset须为非负整数')
    except (ValueError,TypeError) as error:
        result.update(status='missing_input',missing_fields=['query_parameters'],warnings=[str(error)]); return result
    result['time_range']={'start':start.isoformat(),'end':end.isoformat()}
    available=catalog(args['plot_id'])
    with get_connection() as conn:
        plot=conn.execute('SELECT raw_json FROM plots WHERE plot_id=?',(args['plot_id'],)).fetchone()
    profile=json.loads(plot['raw_json']) if plot else {}
    if not any(c['parameter']==args['parameter'] and (depth is None or c['depth_cm']==depth) for c in available):
        result.update(status='missing_input',missing_fields=['observations'],warnings=['该地块无已确认参数/深度']); return result
    sql='SELECT o.*,r.path,r.sha256,r.source_type FROM obs_long o JOIN raw_files r ON r.file_id=o.source_file_id WHERE o.plot_id=? AND o.parameter=? AND o.date BETWEEN ? AND ?'
    params=[args['plot_id'],args['parameter'],start.isoformat(),end.isoformat()]
    if depth is not None: sql+=' AND o.depth_cm=?'; params.append(depth)
    if args.get('data_version'): sql+=' AND o.data_version=?'; params.append(args['data_version'])
    if args.get('device_id'): sql+=' AND o.device_id=?'; params.append(args['device_id'])
    if 'unit' in args: sql+=' AND o.unit=?'; params.append(args['unit'])
    with get_connection() as conn:
        rows=[dict(r) for r in conn.execute(sql+' ORDER BY o.ts,o.obs_id',params)]
    if rows: result['inputs']['display_source']=display_source(rows[0]['device_id'])
    versions=sorted({r['data_version'] for r in rows})
    if len({r['device_id'] for r in rows})>1:
        result.update(status='missing_input',missing_fields=['device_id'],warnings=['有多个监测来源，请选择一个来源，避免混合地点或探头']); return result
    if len(versions)>1 and not args.get('data_version'):
        result.update(status='missing_input',missing_fields=['data_version'],warnings=['多版本记录，请明确查询版本']); return result
    excluded=sum(r['qc_flag'] not in {'ok','rain_reset'} for r in rows)
    valid=[r for r in rows if r['value'] is not None and (args.get('include_flagged',False) or r['qc_flag'] in {'ok','rain_reset'})]
    result['warnings']=[f'异常记录 {excluded} 条；'+('已包含' if args.get('include_flagged') else '默认排除')]
    parameter=args['parameter']
    if parameter.startswith('soil_humidity_layer'):
        if profile.get('water_content_convention')=='volumetric_percent_user_requested':
            for row in valid: row['value']/=100
            result['inputs']['conversion']={'operation':'raw_percent / 100','basis':'用户指定采用体积百分比口径','original_units':sorted({r['unit'] for r in valid})}
            result['missing_fields']=['sensor_calibration']
            result['warnings'].append('体积含水率按用户指定口径由原百分数÷100；原%RH/%和原值保留，传感器标定仍待核查')
        else:
            result['missing_fields']=['actual_probe_depths','soil_humidity_basis']
            result['warnings'].append('原始湿度百分数；埋深、百分比定义未确认，未换算体积含水率')
    elif parameter.startswith(('soil_temperature_layer','soil_ec_layer','soil_salt_layer')):
        if not profile.get('layer_intervals_cm'):
            result['missing_fields']=['actual_probe_depths']
            result['warnings'].append('层号来自原文件，实际埋深未确认')
    match=re.search(r'_layer([123])',parameter)
    if match and len(profile.get('layer_intervals_cm',[]))==3:
        top,bottom=profile['layer_intervals_cm'][int(match[1])-1]
        result['inputs']['layer_interval_cm']={'top':top,'bottom':bottom,'source':'用户确认'}
        result['missing_fields']=[f for f in result['missing_fields'] if f!='actual_probe_depths']
    if parameter=='rainfall_raw':
        enabled=profile.get('rainfall_counter_review',{}).get('model_daily_rain_enabled') and re.fullmatch(r'source:lujiangba:environment[123]',args.get('device_id',''))
        result['missing_fields']=[] if enabled else ['rainfall_accumulation_mode']
        result['warnings'].append('原始累计读数；日均读数不是日降雨量，日雨量另按归零后最大值计算' if enabled else '原始降雨读数，累计方式未知；日均读数不是日降雨量，不自动用于模型降雨输入')
    if args.get('include_flagged'):
        result['warnings'].append('已包含待核查记录，显示其原值不表示异常已修正')
    if not valid:
        result.update(status='missing_input',missing_fields=['valid_observations']); return result
    units={r['unit'] for r in valid}
    if parameter.startswith('soil_humidity_layer') and profile.get('water_content_convention')=='volumetric_percent_user_requested':
        units={'cm3/cm3'}
    if len(units)!=1:
        result.update(status='failed',warnings=['混合单位不可统计']); return result
    series=[{'date':r['date'],'ts':r['ts'],'value':r['value'],'obs_id':r['obs_id'],'qc_flag':r['qc_flag'],'depth_cm':r['depth_cm']} for r in valid]
    if agg=='daily_mean':
        groups=defaultdict(list)
        for r in valid: groups[(r['date'],r['depth_cm'])].append(r)
        series=[{'date':day,'value':sum(r['value'] for r in rs)/len(rs),'depth_cm':d,'obs_ids':[r['obs_id'] for r in rs]} for (day,d),rs in sorted(groups.items(),key=lambda x:(x[0][0],x[0][1] or -1))]
        # One representative source per day; other rows remain queryable in raw pages.
        for point in series:
            point['source_count']=len(point['obs_ids'])
            point['obs_ids']=point['obs_ids'][:1]
    total_points=len(series)
    series=series[offset:offset+limit]
    if offset or total_points>limit:
        result['warnings'].append(f'序列分页：显示第{offset+1}–{min(offset+limit,total_points)}条，共{total_points}条；统计量按完整筛选范围计算')
    values=[r['value'] for r in valid]
    source='demo' if any(r['source_type']=='fixture' for r in valid) else 'observation'
    if source=='demo': result['warnings'].append('构造测试数据，不是实测')
    result.update(status='success',source_type=source,parameter_version=','.join(versions),
        units={'value':next(iter(units)) or '单位未注明'},outputs={'n':len(valid),'mean':sum(values)/len(values),'min':min(values),'max':max(values),
        'first':values[0],'last':values[-1],'missing_days':(end-start).days+1-len({r['date'] for r in valid}),
        'series':series,'excluded_count':excluded,
        'source_obs_ids':[s.get('obs_id') or s['obs_ids'][0] for s in series][:20],
        'series_total':total_points,'offset':offset,'limit':limit,
        'next_offset':offset+limit if offset+limit<total_points else None})
    return result
