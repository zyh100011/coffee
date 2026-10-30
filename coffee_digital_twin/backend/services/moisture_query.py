"""Resolve user-selected depths against confirmed sensor intervals, not point probes."""
from datetime import date,timedelta
import re
from services.data_service import catalog,query
from services.tool_result import make_tool_result

def selected(args,items):
    depth=args.get('depth_cm')
    candidates=[c for c in items if c.get('usable_count',0)>0 and (
        (c['parameter']=='soil_moisture' and c.get('depth_cm')==depth) or
        (c['parameter'].startswith('soil_humidity_layer') and depth is not None and
         c.get('depth_top_cm',999)<=depth<=c.get('depth_bottom_cm',-1)))]
    if args.get('device_id'):candidates=[c for c in candidates if c['device_id']==args['device_id']]
    if args.get('data_version'):candidates=[c for c in candidates if c['data_version']==args['data_version']]
    if 'unit' in args:candidates=[c for c in candidates if c['unit']==args['unit']]
    return next(iter(sorted(candidates,key=lambda c:(0 if c['device_id'].endswith(':soil1') else 1,c.get('depth_top_cm',-1),c['device_id'],c['data_version'],c['unit']))),None)

def depth_from_text(text):
    match=re.search(r'(\d+)\s*[–—~-]\s*(\d+)\s*(?:cm|厘米)',text,re.I)
    if match:return (float(match[1])+float(match[2]))/2
    match=re.search(r'第\s*([123一二三])\s*层',text)
    if match:return {'1':7.5,'一':7.5,'2':22.5,'二':22.5,'3':37.5,'三':37.5}[match[1]]
    if '表层' in text:return 7.5
    match=re.search(r'(\d+(?:\.\d+)?)\s*(?:cm|厘米)',text,re.I)
    return float(match[1]) if match else None

def recent_days(text):
    match=re.search(r'(?:最近|近)\s*(\d+)\s*[天日]',text)
    if match:return int(match[1]) if 1<=int(match[1])<=366 else None
    return 7 if re.search(r'(?:最近|近)一周',text) else 30 if re.search(r'(?:最近|近)一个月',text) else None

def normalize_route(route,payload):
    """Bind only explicit query terms, after service routing and before schema checks."""
    extra=payload.get('supplement') or {}
    text=payload['message']+' '+(extra if isinstance(extra,str) else str(extra.get('text','')))
    context=payload.get('plot_context',{});notes=[]
    for call in route.get('tool_calls',[]):
        if call.get('name')!='query_soil_moisture':continue
        args=call['arguments'];depth=depth_from_text(text)
        if depth is not None:args['depth_cm']=depth
        choice=selected(args,context.get('observation_catalog',[]))
        days=recent_days(text)
        explicit_dates=bool(re.search(r'\d{4}-\d{2}-\d{2}',text)) or (isinstance(extra,dict) and bool(extra.get('start') or extra.get('end')))
        if choice and days and not explicit_dates:
            end=choice.get('valid_end') or choice['end']
            args.update(start=max(choice.get('valid_start') or choice['start'],(date.fromisoformat(end)-timedelta(days=days-1)).isoformat()),end=end)
            notes.append({'kind':'relative_to_data_end','data_end':end,'start':args['start'],'end':args['end']})
        route['missing_fields']=[k for k in route.get('missing_fields',[]) if not (k in ('depth_cm','start','end') and args.get(k) is not None)]
    if notes:route['business_bindings']=notes
    return route

def run(args,ctx):
    choice=selected(args,catalog(args['plot_id']))
    if not choice:return make_tool_result(tool='data_query',plot_id=args['plot_id'],status='missing_input',missing_fields=['observations'],warnings=['该深度暂无可用监测数据，请选择已入库监测层'])
    actual={**args,'parameter':choice['parameter'],'device_id':choice['device_id'],'data_version':choice['data_version'],'unit':choice['unit']}
    requested=actual.pop('depth_cm',None)
    if choice['depth_cm'] is not None:actual['depth_cm']=choice['depth_cm']
    result=query(actual,ctx)
    result['inputs'].update(requested_depth_cm=requested,display_source=choice['display_source'])
    if choice.get('depth_top_cm') is not None:
        interval=f"{choice['depth_top_cm']}–{choice['depth_bottom_cm']}cm"
        result['warnings'].append(f'{requested:g}cm 按 {interval} 探头层回答；监测点：{choice["display_source"]}')
    result['warnings'].append(f"数据截至 {choice.get('valid_end') or choice['end']}，本次查询 {args['start']} 至 {args['end']}")
    return result
