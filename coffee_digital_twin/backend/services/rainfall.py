"""Derive daily rain from one confirmed frozen daily counter; preserve raw rows."""
from datetime import date, timedelta
import math
from database.init_db import get_connection

SOURCES={f'环境监测点{i}':f'source:lujiangba:environment{i}' for i in (1,2,3)}
RULE='首个≤0.05mm归零点后取日最大值；归零前残留丢弃；日内零跳点不累加'


def daily_rainfall(plot_id, source=None, start=None, end=None):
    source=source or '环境监测点1'
    device=SOURCES.get(source,source)
    if device not in SOURCES.values(): raise ValueError('仅允许已确认的环境监测点1/2/3日累计计数器')
    begin,finish=date.fromisoformat(start),date.fromisoformat(end)
    if not 0<=(finish-begin).days<=365: raise ValueError('日雨量窗口须为1–366天')
    with get_connection() as conn:
        # Unfrozen rows and differently behaving weather stations cannot enter.
        rows=[dict(r) for r in conn.execute('''SELECT o.*,r.path,r.sha256,r.source_type
            FROM obs_long o JOIN raw_files r ON r.file_id=o.source_file_id
            JOIN data_versions v ON v.data_version=o.data_version
            WHERE o.plot_id=? AND o.device_id=? AND o.parameter='rainfall_raw'
              AND o.unit='mm' AND o.qc_flag='ok' AND o.value IS NOT NULL
              AND o.date BETWEEN ? AND ? ORDER BY o.ts,o.obs_id''',
            (plot_id,device,start,end))]
    versions={r['data_version'] for r in rows}
    if len(versions)>1: raise ValueError('多个冻结版本，不能合并日雨量')
    items=[];warnings=[]
    for offset in range((finish-begin).days+1):
        day=(begin+timedelta(days=offset)).isoformat()
        original=[r for r in rows if r['date']==day and math.isfinite(r['value']) and r['value']>=0]
        reset=next((i for i,r in enumerate(original) if r['value']<=.05),None)
        kept=original[reset:] if reset is not None else original
        note=[]
        value=None
        if kept:
            value=max(r['value'] for r in kept)
            if reset is None:
                if len(kept)==1 or all(r['value']==0 for r in kept):
                    value=0.0
                    note.append(day+' 无归零点且仅单条记录，按本轮指定口径记0mm；原读数保留')
                else:note.append(day+' 未发现归零点，取当天最大读数')
        else:note.append(day+' 无降雨记录，模型按0计；日雨量仍为缺失')
        source_type='demo' if any(r['source_type']=='fixture' for r in original) else 'observation'
        items.append({'date':day,'rain_mm':value,'value':value,'reset_ts':original[reset]['ts'] if reset is not None else None,
                      'discarded_before_reset':reset or 0,'source_count':len(original),
                      'obs_ids':[r['obs_id'] for r in original],'warnings':note,'source_type':source_type})
        warnings.extend(note)
    return {'plot_id':plot_id,'device_id':device,'display_source':next(k for k,v in SOURCES.items() if v==device),
            'time_range':{'start':start,'end':end},'unit':'mm','rule':RULE,
            'data_version':next(iter(versions),None),'items':items,'warnings':warnings}


def query_daily(args,ctx=None):
    from services.tool_result import make_tool_result
    result=make_tool_result(tool='data_query',plot_id=args.get('plot_id'),task_id=(ctx or {}).get('task_id'),inputs=dict(args))
    try:
        rain=daily_rainfall(args['plot_id'],args.get('device_id'),args['start'],args['end'])
        if args.get('unit','mm')!='mm' or args.get('data_version',rain['data_version'])!=rain['data_version']:
            raise ValueError('日降雨量来源单位或版本不匹配')
    except (ValueError,TypeError,KeyError) as error:
        result.update(status='missing_input',missing_fields=['daily_rainfall_parameters'],warnings=[str(error)]);return result
    points=rain['items'];values=[p['rain_mm'] for p in points if p['rain_mm'] is not None]
    result.update(time_range=rain['time_range'],units={'value':'mm'},parameter_version=rain['data_version'],
        source_type='demo' if any(p['source_type']=='demo' for p in points) else 'observation',warnings=rain['warnings'])
    result['inputs'].update(display_source=rain['display_source'],device_id=rain['device_id'],
                            data_version=rain['data_version'],derivation_rule=RULE)
    if not values:
        result.update(status='missing_input',missing_fields=['valid_observations']);return result
    result.update(status='success',outputs={'n':len(values),'mean':sum(values)/len(values),'min':min(values),'max':max(values),
        'total':sum(values),'missing_days':len(points)-len(values),'series':points,
        'source_obs_ids':[oid for p in points for oid in p['obs_ids']][:20],
        'series_total':len(points),'offset':0,'limit':366,'next_offset':None})
    return result
