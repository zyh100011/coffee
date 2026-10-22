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
from tools.mock_evidence_service import route_rules
SESSIONS={}
LOCK=Lock()
LABELS={'observation':'实测','literature':'文献','simulation_uncalibrated':'未校准模拟','proxy_model':'代理模型','simplified_model':'简化模型','demo':'演示'}

def _blocks(results):
    blocks=[]; evidence=[]
    for r in results:
        evidence.append({'evidence_id':r['evidence_id'],'label':LABELS[r['source_type']],
            'detail':{'status':r['status'],'plot_id':r['plot_id'],'time_range':r['time_range'],'version':r['parameter_version'],'mode':r['mode']}})
        if r['status'] not in AVAILABLE:
            blocks.append({'type':'warning','text':r['tool']+'：'+r['status']+'；'+'；'.join(r['warnings'])})
        else:
            for key,value in r['outputs'].items():
                if isinstance(value,(int,float)) and not isinstance(value,bool):
                    blocks.append({'type':'fact','label':key,'value':value,'unit':r['units'].get(key,r['units'].get('value','')),'evidence_id':r['evidence_id'],'source_type':r['source_type']})
            series=r['outputs'].get('series') or r['outputs'].get('soil_moisture_series')
            if series:
                if 'value' in series[0]: data=[[s['date'],s['value']] for s in series]; name='value'
                else: data=[[s['date'],s.get('d40')] for s in series]; name='40cm'
                blocks.append({'type':'chart','chart':'line','series':[{'name':name,'data':data}], 'evidence_id':r['evidence_id'],'source_type':r['source_type']})
        for text in r.get('warnings',[])+r.get('assumptions',[]):
            blocks.append({'type':'warning','text':text})
    if evidence: blocks.append({'type':'evidence','items':evidence})
    return blocks

def chat(payload):
    begin=time.monotonic(); deadline=begin+120
    session=payload.get('session_id') or 's_'+uuid.uuid4().hex
    trace={'trace_id':'tr_'+uuid.uuid4().hex,'turn_id':'t_'+uuid.uuid4().hex,'session_id':session,
        'plot_id':payload.get('plot_id'),'message':payload['message'],'route':{},'tool_calls':[],
        'tool_results':[],'answer':{},'blocks':[],'latency_ms':{},'errors':[],'service_mode':'live'}
    context=load_plot_context(payload.get('plot_id'))
    compare_match=re.fullmatch(r'解释情景对比 (cmp_[a-f0-9]{32})',payload['message'].strip())
    compare_record=None
    if compare_match:
        from database.init_db import get_connection
        with get_connection() as conn:
            row=conn.execute('SELECT compare_json FROM scenario_compares WHERE compare_id=? AND plot_id=?',(compare_match[1],payload.get('plot_id'))).fetchone()
        if row: compare_record=json.loads(row['compare_json'])
        context['scenario_compare']=compare_record or {'status':'missing_input','missing_fields':['compare_id']}
    from services.data_service import catalog
    context['observation_catalog']=catalog(context['plot_id']) if context['plot_id'] else []
    with LOCK:
        old=SESSIONS.get((session,payload.get('plot_id')),{})
    continuing=bool(payload.get('supplement') and old.get('pending'))
    question=old.get('message',payload['message']) if continuing else payload['message']
    clarify_count=old.get('clarify_count',0) if continuing else 0
    route_payload={'session_id':session,'message':question,'history':payload.get('history',[]),
        'supplement':payload.get('supplement'),'plot_context':context,'available_tools':available_tools(),'today':date.today().isoformat()}
    blocks=[]; status='success'; route_start=time.monotonic()
    try:
        if compare_match:
            route={'intent':'model_explain','tool_calls':[{'name':'read_model_result','arguments':{'task_id':r['task_id'],'tool':'hydrus'}} for r in (compare_record['baseline'],compare_record['variant'])] if compare_record and compare_record.get('parameter_verified') else [],
                   'missing_fields':[] if compare_record and compare_record.get('parameter_verified') else ['verified_compare'], 'clarify_question':None}
        else:
            route=evidence_client.route(route_payload,timeout=min(20,deadline-time.monotonic()-2))
        evidence_client.validate('route',route)
        if route.get('mock'): trace['service_mode']='mock'
    except (evidence_client.EvidenceServiceError,ValueError) as error:
        trace['errors'].append(getattr(error,'code','E_EVIDENCE_INVALID')); trace['service_mode']='degraded'
        candidate=route_rules(route_payload)
        route=candidate if candidate['intent']=='data_query' else {'intent':'other','tool_calls':[],'missing_fields':[],'clarify_question':None}
        blocks.append({'type':'warning','text':'智能解释暂不可用；仅执行明确的数据查询'})
    trace['latency_ms']['route']=round((time.monotonic()-route_start)*1000)
    route['request_context']={'history':payload.get('history',[]),'supplement':payload.get('supplement'),'original_message':question}
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
            blocks.append({'type':'missing','fields':missing,'question':route.get('clarify_question') or '请补充：'+'、'.join(missing),'quick_replies':['最近7天','最近30天']})
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
            try:
                answer=evidence_client.answer({'session_id':session,'message':question,'intent':route['intent'],
                    'tool_results':usable,'tool_status':[{k:r[k] for k in ('tool','status','source_type')} for r in results],
                    'plot_context':context},timeout=min(60,deadline-time.monotonic()-2))
                evidence_client.validate('answer',answer); trace['answer']=answer
                if answer.get('mock'): trace['service_mode']='mock'
                allowed={r['evidence_id'] for r in usable}
                forbidden={r['evidence_id'] for r in results}-allowed
                citations=[c for c in answer['citations'] if c['evidence_id'] not in forbidden]
                allowed.update(c['evidence_id'] for c in citations)
                if citations:
                    blocks.append({'type':'evidence','items':[{'evidence_id':c['evidence_id'],'label':'演示' if answer.get('mock') else '文献','detail':c} for c in citations]})
                # Claims are rendered individually; unbound free-form answer is withheld.
                for claim in answer['claims']:
                    supported=bool(claim['evidence_ids']) and set(claim['evidence_ids'])<=allowed
                    blocks.append({'type':'text','text':claim['text'] if supported else '[未核验] '+claim['text'],'verified':supported})
                    if not supported: trace['errors'].append('unsupported_claim')
                if not answer['claims']:
                    blocks.append({'type':'text','text':'暂无绑定可核验证据的解释，请查看事实与缺项。'})
                blocks.extend({'type':'warning','text':text} for text in answer['limitations'])
                if answer['check_items']: blocks.append({'type':'check_items','items':answer['check_items']})
            except (evidence_client.EvidenceServiceError,ValueError) as error:
                trace['errors'].append(getattr(error,'code','E_EVIDENCE_INVALID')); trace['service_mode']='degraded'
                blocks.append({'type':'warning','text':'智能解释暂不可用；已保留工具事实和来源'})
            trace['latency_ms']['answer']=round((time.monotonic()-stage)*1000)
    with LOCK:
        SESSIONS[(session,payload.get('plot_id'))]={'message':question,'pending':pending,'clarify_count':clarify_count,'updated':time.time()}
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
            'blocks':blocks,'service_mode':trace['service_mode'],'mock':trace['service_mode']=='mock'}
    from services.errors import envelope,ERRORS
    response['errors']=[envelope(code,trace_id=trace['trace_id']) for code in trace['errors'] if code in ERRORS]
    if status=='error':
        failure=envelope(next((c for c in trace['errors'] if c in ERRORS),'E_PARAM_INVALID'),trace_id=trace['trace_id'])
        response.update(failure)
    return response
