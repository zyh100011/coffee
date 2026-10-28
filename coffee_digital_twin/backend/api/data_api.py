from flask import Blueprint,jsonify,request
from services.data_service import catalog,query
from database.init_db import get_connection
import json

data_bp=Blueprint('data_api',__name__,url_prefix='/api/data')

@data_bp.get('/team-materials')
def team_materials():
    from services.jgy_delivery import material_status
    return jsonify(material_status())

@data_bp.get('/historical-weather/catalog')
def historical_weather_catalog():
    from services.jgy_delivery import weather_catalog
    plot = request.args.get('plot_id')
    if not plot:
        return jsonify(status='missing_input', missing_fields=['plot_id']), 400
    return jsonify(weather_catalog(plot))

@data_bp.post('/historical-weather/query')
def historical_weather_query():
    from services.jgy_delivery import weather_query
    try:
        result = weather_query(request.get_json(silent=True))
    except (ValueError, TypeError, KeyError):
        return jsonify(status='missing_input', missing_fields=['valid_weather_query'],
                       message='请提供地块、有效日期和查询粒度；逐日最多366天、逐小时最多31天'), 400
    return jsonify(result), 200 if result['status'] == 'success' else 400

@data_bp.get('/catalog')
def get_catalog():
    plot=request.args.get('plot_id')
    if not plot: return jsonify(status='missing_input',missing_fields=['plot_id']),400
    return jsonify(status='success',plot_id=plot,items=catalog(plot))

@data_bp.get('/soil-reports')
def soil_reports():
    plot=request.args.get('plot_id')
    if not plot: return jsonify(status='missing_input',missing_fields=['plot_id']),400
    with get_connection() as conn:
        plot_row=conn.execute('SELECT raw_json FROM plots WHERE plot_id=?',(plot,)).fetchone()
        rows=conn.execute('''SELECT l.*,r.sha256,r.data_version FROM soil_lab_results l
            JOIN raw_files r ON r.file_id=l.source_file_id WHERE l.plot_id=?
            ORDER BY l.lab_sample_id,l.result_id''',(plot,)).fetchall()
    profile=json.loads(plot_row['raw_json']) if plot_row else {}
    selected=profile.get('representative_soil_sample',{})
    sampling=profile.get('soil_sampling_context',{})
    samples={}
    for row in rows:
        key=(row['source_file_id'],row['lab_sample_id'])
        sample=samples.setdefault(key,{'sample_label':row['sample_label'],'lab_sample_id':row['lab_sample_id'],
            'sample_date':row['sample_date'],'received_date':row['received_date'],'report_date':row['report_date'],
            'depth_top_cm':row['depth_top_cm'],'depth_bottom_cm':row['depth_bottom_cm'],
            'source_page':row['source_page'],'source_sha256':row['sha256'],'data_version':row['data_version'],
            'source_type':'observation','is_representative':row['lab_sample_id']==selected.get('lab_sample_id'),
            'measurements':[]})
        if sampling.get('depth_source')=='field_record':
            sample.update(depth_top_cm=sampling['depth_top_cm'],depth_bottom_cm=sampling['depth_bottom_cm'],
                          depth_source='field_record',sampling_label='表层 0–20cm')
        sample['measurements'].append({'item':row['item'],'value':row['value'],'unit':row['unit'],'method':row['method'],'result_id':row['result_id']})
    return jsonify(status='success',plot_id=plot,items=list(samples.values()),
                   representative_sample=selected if any(s['is_representative'] for s in samples.values()) else None,
                   sampling_context=sampling,
                   missing_fields=(['sample_date'] if sampling.get('depth_source')=='field_record' else ['sample_date','sample_depth','sample_to_station_mapping']) if rows else ['soil_reports'],
                   warnings=['检测报告按9个样品分别保存；收样日、报告日不作采样日；不与连续监测拼成同一时间序列'] if rows else [])

@data_bp.get('/import-status')
def import_status():
    plot=request.args.get('plot_id')
    if not plot: return jsonify(status='missing_input',missing_fields=['plot_id']),400
    with get_connection() as conn:
        row=conn.execute('SELECT raw_json FROM plots WHERE plot_id=?',(plot,)).fetchone()
        count=conn.execute('SELECT COUNT(*) n,MIN(date) start,MAX(date) end FROM obs_long WHERE plot_id=?',(plot,)).fetchone()
        flags=[dict(r) for r in conn.execute('SELECT qc_flag,COUNT(*) n FROM obs_long WHERE plot_id=? GROUP BY qc_flag',(plot,))]
    raw=json.loads(row['raw_json']) if row else {}
    return jsonify(status='success',plot_id=plot,observations=dict(count),qc_flags=flags,
                   missing_fields=raw.get('missing_fields',[]),data_scope=raw.get('data_scope'),
                   management={k:raw.get(k) for k in ('layer_intervals_cm','rain_source','irrigation_management','confirmation_source')},
                   warnings=['现有数据按用户确认归属同一卡蒂姆基地；按来源分别查询，历史数据不是当前实时监测'] if raw.get('data_scope') in ('project_group','single_base_user_confirmed') else [])

@data_bp.post('/query')
def data_query():
    args=request.get_json(silent=True)
    if not isinstance(args,dict): return jsonify(status='missing_input',missing_fields=['request_object']),400
    result=query(args)
    from services.trace_store import save_data_evidence
    save_data_evidence(result)
    return jsonify(result),200 if result['status']=='success' else 400

@data_bp.get('/source/<obs_id>')
def source(obs_id):
    with get_connection() as conn:
        row=conn.execute('SELECT o.obs_id,o.plot_id,o.value_raw,o.source_row,o.qc_flag,o.data_version,r.path,r.sha256,r.source_type,ds.source_version AS source_data_version FROM obs_long o JOIN raw_files r ON r.file_id=o.source_file_id LEFT JOIN data_release_sources ds ON ds.data_version=o.data_version AND ds.file_id=o.source_file_id WHERE o.obs_id=?',(obs_id,)).fetchone()
    if not row: return jsonify(status='not_found',code='E_EVIDENCE_NOT_FOUND'),404
    if request.args.get('plot_id') and row['plot_id']!=request.args['plot_id']: return jsonify(status='not_found'),404
    return jsonify(dict(row))


@data_bp.get('/evidence/<evidence_id>/sources')
def evidence_sources(evidence_id):
    """Paginate the original filter, without modifying saved query evidence."""
    from services.trace_store import lookup
    evidence=lookup(evidence_id,request.args.get('plot_id'))
    if not evidence or evidence.get('tool')!='data_query' or evidence.get('status')!='success':
        return jsonify(status='not_found',code='E_EVIDENCE_NOT_FOUND'),404
    try:
        offset=int(request.args.get('offset',0)); limit=int(request.args.get('limit',20))
        if offset<0 or not 1<=limit<=50: raise ValueError()
    except (ValueError,TypeError):
        return jsonify(status='missing_input',message='分页参数无效'),400
    args={key:value for key,value in evidence['inputs'].items() if key in
          ('plot_id','parameter','depth_cm','device_id','unit','data_version','start','end','include_flagged')}
    if args.get('parameter')=='rainfall_daily': args['parameter']='rainfall_raw'
    result=query(dict(args,agg='raw',offset=offset,limit=limit))
    if result['status']!='success': return jsonify(result),400
    ids=[row['obs_id'] for row in result['outputs']['series']]
    with get_connection() as conn:
        records={row['obs_id']:dict(row) for row in conn.execute(
            'SELECT o.obs_id,o.ts,o.value_raw,o.unit,o.source_row,o.qc_flag,o.data_version,r.path,r.sha256,r.source_type,ds.source_version AS source_data_version FROM obs_long o JOIN raw_files r ON r.file_id=o.source_file_id LEFT JOIN data_release_sources ds ON ds.data_version=o.data_version AND ds.file_id=o.source_file_id WHERE o.obs_id IN ('+','.join('?' for _ in ids)+')',ids)} if ids else {}
    return jsonify(status='success',evidence_id=evidence_id,items=[records[key] for key in ids],
        offset=offset,limit=limit,total=result['outputs']['series_total'],next_offset=result['outputs']['next_offset'])
