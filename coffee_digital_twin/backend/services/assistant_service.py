"""Route -> validate -> tools -> answer -> blocks -> trace, bounded and explicit."""
from datetime import date
import time
import uuid
import re
import json
from threading import Lock
from services import evidence_client
from services.plot_context import load_plot_context
from services.tool_registry import available_tools,prepare_calls,execute,AVAILABLE
from services.trace_store import save
from services.evidence_transport import answer_results,citation_source,ANSWER_LABELS,REJECTED_ANSWERS
from tools.mock_evidence_service import route_rules
SESSIONS={}
LOCK=Lock()
LABELS={'observation':'实测','literature':'文献','simulation_uncalibrated':'未校准模拟','proxy_model':'代理模型','simplified_model':'简化模型','demo':'演示','internal_tool_description':'工具说明'}

def service_context(context):
    """Compact copy sent to the model service (8k context); full context stays in the business layer."""
    compact={k:v for k,v in context.items() if k!='observation_catalog'}
    summary={}
    for c in context.get('observation_catalog',[]):
        if not c.get('usable_count') or c.get('hidden_reason'): continue
        start=c.get('valid_start') or c['start']; end=c.get('valid_end') or c['end']
        e=summary.setdefault(c['parameter'],{'parameter':c['parameter'],'label':c.get('parameter_label'),'end':end})
        e['end']=max(e['end'],end)
        if c.get('depth_cm') is not None: e['depth_cm']=c['depth_cm']
        if c.get('depth_top_cm') is not None: e['layer_cm']=[c['depth_top_cm'],c['depth_bottom_cm']]
    compact['observation_catalog']=list(summary.values())
    return compact


def service_history(history):
    return [dict(h,content=str(h.get('content',''))[:300]) if isinstance(h,dict) else h for h in (history or [])[-6:]]


def service_route_payload(route_payload):
    return dict(route_payload,plot_context=service_context(route_payload['plot_context']),history=service_history(route_payload.get('history')))


def _blocks(results):
    blocks=[]; evidence=[]
    for r in results:
        evidence.append({'evidence_id':r['evidence_id'],'label':LABELS[r['source_type']],
            'detail':{'status':r['status'],'plot_id':r['plot_id'],'time_range':r['time_range'],'version':r['parameter_version'],'mode':r['mode']},
            'display_source':r['inputs'].get('display_source',''),
            'layer_label': ('{top}–{bottom}cm'.format(**r['inputs']['layer_interval_cm']) if r['inputs'].get('layer_interval_cm') else '')})
        if r['status'] not in AVAILABLE:
            blocks.append({'type':'warning','text':{'missing_input':'缺少查询条件或可用数据','failed':'工具运行失败','timeout':'工具运行超时','fallback':'当前仅有演示结果'}.get(r['status'],'工具暂不可用')+('：'+'；'.join(r['warnings']) if r['warnings'] else '')})
        else:
            for key,value in r['outputs'].items():
                if r['tool']=='data_query' and key not in ('n','mean','min','max','missing_days'): continue
                if isinstance(value,(int,float)) and not isinstance(value,bool):
                    blocks.append({'type':'fact','label':key,'value':value,'unit':('' if key in ('n','missing_days','excluded_count','series_total','offset','limit') else r['units'].get(key,r['units'].get('value',''))),'evidence_id':r['evidence_id'],'source_type':r['source_type']})
            series=r['outputs'].get('series') or r['outputs'].get('soil_moisture_series')
            if series:
                if 'value' in series[0]: data=[[s['date'],s['value']] for s in series]; name='含水率' if 'soil' in r['inputs'].get('parameter','') else '查询结果'
                else: data=[[s['date'],s.get('d40')] for s in series]; name='40cm'
                blocks.append({'type':'chart','chart':'line','series':[{'name':name,'data':data}], 'unit':r['units'].get('value','cm3/cm3'),'evidence_id':r['evidence_id'],'source_type':r['source_type']})
        # Complete warnings/assumptions stay in saved evidence and reports.
        if r['tool']=='data_query' and r['status'] in AVAILABLE:
            blocks.append({'type':'text','text':f"历史观测：{r['time_range']['start']} 至 {r['time_range']['end']}；{r['inputs'].get('display_source','所选监测点')}"})
        for text in ([] if r['tool']=='data_query' else r.get('warnings',[])+r.get('assumptions',[])):
            blocks.append({'type':'warning','text':text})
    if evidence: blocks.append({'type':'evidence','items':evidence})
    return blocks

def chat(payload):
    begin=time.monotonic(); deadline=begin+120
    entry_mode=payload.get('entry_mode','auto')
    session=payload.get('session_id') or 's_'+uuid.uuid4().hex
    trace={'trace_id':'tr_'+uuid.uuid4().hex,'turn_id':'t_'+uuid.uuid4().hex,'session_id':session,
        'plot_id':payload.get('plot_id'),'message':payload['message'],'route':{},'tool_calls':[],
        'tool_results':[],'answer':{},'blocks':[],'latency_ms':{},'errors':[],'service_mode':'live'}
    context=load_plot_context(payload.get('plot_id'))
    compare_match=re.fullmatch(r'解释情景对比 (cmp_[a-f0-9]{32})',payload['message'].strip()) if entry_mode=='auto' else None
    compare_record=None
    if compare_match:
        from database.init_db import get_connection
        with get_connection() as conn:
            row=conn.execute('SELECT compare_json FROM scenario_compares WHERE compare_id=? AND plot_id=?',(compare_match[1],payload.get('plot_id'))).fetchone()
        if row: compare_record=json.loads(row['compare_json'])
        context['scenario_compare']=compare_record or {'status':'missing_input','missing_fields':['compare_id']}
    from services.data_service import catalog
    context['observation_catalog']=catalog(context['plot_id']) if context['plot_id'] else []
    context['data_end']=max((c.get('valid_end') or c['end'] for c in context['observation_catalog'] if c['usable_count']),default=None)
    with LOCK:
        old=SESSIONS.get((session,payload.get('plot_id')),{})
    continuing=bool(payload.get('supplement') and old.get('pending') and old.get('entry_mode','auto')==entry_mode)
    question=old.get('message',payload['message']) if continuing else payload['message']
    clarify_count=old.get('clarify_count',0) if continuing else 0
    route_payload={'session_id':session,'message':question,'history':payload.get('history',[]),
        'supplement':payload.get('supplement'),'plot_context':context,'available_tools':available_tools(),'today':date.today().isoformat()}
    blocks=[]; status='success'; route_start=time.monotonic()
    try:
        if entry_mode=='knowledge':
            route={'intent':'knowledge','tool_calls':[],'missing_fields':[],'clarify_question':None,
                   'need_retrieval':True,'guard_trace':['explicit_knowledge_entry']}
        elif compare_match:
            route={'intent':'model_explain','tool_calls':[{'name':'read_model_result','arguments':{'task_id':r['task_id'],'tool':'hydrus'}} for r in (compare_record['baseline'],compare_record['variant'])] if compare_record and compare_record.get('parameter_verified') else [],
                   'missing_fields':[] if compare_record and compare_record.get('parameter_verified') else ['verified_compare'], 'clarify_question':None}
        else:
            route=evidence_client.route(service_route_payload(route_payload),timeout=min(20,deadline-time.monotonic()-2))
        evidence_client.validate('route',route)
        if route.get('mock'): trace['service_mode']='mock'
    except (evidence_client.EvidenceServiceError,ValueError) as error:
        trace['errors'].append(getattr(error,'code','E_EVIDENCE_INVALID')); trace['service_mode']='degraded'
        if getattr(error,'detail',''): trace['errors'].append('detail:'+error.detail)
        candidate=route_rules(route_payload)
        route=candidate if candidate['intent']=='data_query' else {'intent':'other','tool_calls':[],'missing_fields':[],'clarify_question':None}
        blocks.append({'type':'warning','text':'智能解释暂不可用；仅执行明确的数据查询'})
    trace['latency_ms']['route']=round((time.monotonic()-route_start)*1000)
    from services.moisture_query import normalize_route
    route=normalize_route(route,route_payload)
    route['request_context']={'history':payload.get('history',[]),'supplement':payload.get('supplement'),'original_message':question,'entry_mode':entry_mode}
    trace['route']=route
    calls,missing,errors=prepare_calls(route.get('tool_calls',[]),{'plot_id':context['plot_id']})
    missing=sorted(set(missing+route.get('missing_fields',[])))
    if any(c['name']!='read_model_result' for c in calls) and not context['exists']:
        missing=sorted(set(missing+['plot_id']))
    trace['tool_calls']=calls; trace['errors']+=errors
    pending=False
    if errors:
        status='error'; blocks.append({'type':'warning','text':'工具或参数校验失败：'+','.join(errors)})
    elif missing:
        status='missing_input'
        if clarify_count<1:
            names={'plot_id':'基地','depth_cm':'深度','start':'开始日期','end':'结束日期','start_date':'起始日期','task_id':'模型任务','tool':'模型工具','device_id':'监测点','parameter':'参数'}
            fields=[names.get(k,'查询条件') for k in missing]
            quick=['0–15cm 最近7天','15–30cm 最近7天','30–45cm 最近7天'] if 'depth_cm' in missing else ['最近7天','最近30天']
            blocks.append({'type':'missing','fields':fields,'question':'请补充：'+'、'.join(fields),'quick_replies':quick})
            clarify_count=1; pending=True
        else:
            blocks.append({'type':'check_items','items':['现场核对缺项：'+k for k in missing]})
    else:
        stage=time.monotonic()
        results=execute(calls,{'plot_id':context['plot_id'],'task_id':'task_'+uuid.uuid4().hex,'deadline':deadline-2})
        trace['tool_results']=results; trace['latency_ms']['tools']=round((time.monotonic()-stage)*1000)
        blocks+=_blocks(results)
        if trace['service_mode']!='degraded':
            stage=time.monotonic()
            usable=[r for r in results if r['status'] in AVAILABLE and r['source_type']!='demo']
            transported,annotations=answer_results(usable)
            trace['route']['answer_transport']=annotations
            try:
                answer=evidence_client.answer({'session_id':session,'message':question,'intent':route['intent'],
                    'tool_results':transported,'tool_status':[{k:r[k] for k in ('tool','status','source_type')} for r in results],
                    'plot_context':service_context(context)},timeout=min(60,deadline-time.monotonic()-2))
                evidence_client.validate('answer',answer); trace['answer']=answer
                if answer.get('mock'): trace['service_mode']='mock'
                allowed={r['evidence_id'] for r in usable}
                forbidden={r['evidence_id'] for r in results}-allowed
                citations=[c for c in answer['citations'] if c['evidence_id'] not in forbidden]
                citations=[dict(c,source_type=citation_source(c,usable,answer.get('mock',False))) for c in citations]
                answer['citations']=citations
                allowed.update(c['evidence_id'] for c in citations)
                new_citations=[c for c in citations if c['evidence_id'] not in {r['evidence_id'] for r in usable}]
                if new_citations:
                    blocks.append({'type':'evidence','items':[{'evidence_id':c['evidence_id'],'label':LABELS[c['source_type']],'detail':c} for c in new_citations]})
                answer_status=answer.get('retrieval_trace',{}).get('status')
                if answer_status:
                    blocks.append({'type':'warning','answer_status':answer_status,'text':ANSWER_LABELS.get(answer_status,'服务解释状态待核查，请以原始证据为准。')})
                if answer_status in REJECTED_ANSWERS:
                    status='partial'
                # Claims are rendered individually; unbound free-form answer is withheld.
                for claim in ([] if answer_status in REJECTED_ANSWERS else answer['claims']):
                    supported=bool(claim['evidence_ids']) and set(claim['evidence_ids'])<=allowed
                    blocks.append({'type':'text','text':claim['text'] if supported else '[未核验] '+claim['text'],'verified':supported})
                    if not supported: trace['errors'].append('unsupported_claim')
                if not answer['claims']:
                    blocks.append({'type':'text','text':'暂无绑定可核验证据的解释，请查看事实与缺项。'})
                blocks.extend({'type':'warning','text':text} for text in answer['limitations'])
                if answer['check_items']: blocks.append({'type':'check_items','items':answer['check_items']})
            except (evidence_client.EvidenceServiceError,ValueError) as error:
                trace['errors'].append(getattr(error,'code','E_EVIDENCE_INVALID')); trace['service_mode']='degraded'
                if getattr(error,'detail',''): trace['errors'].append('detail:'+error.detail)
                blocks.append({'type':'warning','text':'智能解释暂不可用；已保留工具事实和来源'})
            trace['latency_ms']['answer']=round((time.monotonic()-stage)*1000)
    with LOCK:
        SESSIONS[(session,payload.get('plot_id'))]={'message':question,'pending':pending,'clarify_count':clarify_count,'entry_mode':entry_mode,'updated':time.time()}
        for key in list(SESSIONS):
            if SESSIONS[key]['updated']<time.time()-3600: del SESSIONS[key]
    if trace['service_mode']=='mock': blocks.insert(0,{'type':'warning','text':'MOCK 联调：不是正式大模型或文献检索结果'})
    steps=[('接收问题','done'),('识别意图','degraded' if trace['service_mode']=='degraded' else 'done'),
           ('校验条件','failed' if errors else 'missing' if missing else 'done'),
           ('执行工具','done' if trace['tool_results'] else 'skipped'),
           ('生成解释','done' if trace['answer'] else 'skipped'),('绑定证据','done' if any(b['type']=='evidence' for b in blocks) else 'skipped'),('记录轨迹','saved')]
    blocks.append({'type':'trace','trace_id':trace['trace_id'],'steps':[{'step':name,'status':state} for name,state in steps]})
    trace['latency_ms']['total']=round((time.monotonic()-begin)*1000); trace['blocks']=blocks
    save(trace)
    response={'status':status,'session_id':session,'turn_id':trace['turn_id'],'trace_id':trace['trace_id'],
            'blocks':blocks,'service_mode':trace['service_mode'],'mock':trace['service_mode']=='mock',
            'answer_status':trace['answer'].get('retrieval_trace',{}).get('status'),
            # 仅供前端显示问题类别，不参与路由。
            'intent':(trace.get('route') or {}).get('intent'),'tools':[c.get('name') for c in trace.get('tool_calls',[])]}
    from services.errors import envelope,ERRORS
    response['errors']=[envelope(code,trace_id=trace['trace_id']) for code in trace['errors'] if code in ERRORS]
    if status=='error':
        failure=envelope(next((c for c in trace['errors'] if c in ERRORS),'E_PARAM_INVALID'),trace_id=trace['trace_id'])
        response.update(failure)
    return response
