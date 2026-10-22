"""Deterministic contract simulator; all replies explicitly MOCK."""
import argparse
from datetime import date,timedelta
import json
from pathlib import Path
import re
from flask import Flask,jsonify,request
def route_rules(payload):
    message=payload.get('message',''); supplement=payload.get('supplement') or {}
    if isinstance(supplement,str): message+=' '+supplement; supplement={}
    text=message+' '+str(supplement.get('text',''))
    plot=payload.get('plot_context',{}).get('plot_id'); args={'plot_id':plot}
    result={'intent':'knowledge','tool_calls':[],'missing_fields':[],'clarify_question':None,'need_retrieval':True,'mock':True}
    dates=re.findall(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',text)
    start=supplement.get('start') or (dates[0] if dates else None)
    end=supplement.get('end') or (dates[1] if len(dates)>1 else start)
    if '最近' in text:
        match=re.search(r'最近[ ]*([0-9]+)[ ]*[天日]',text); days=int(match[1]) if match else 7 if '一周' in text else 30 if '一个月' in text else None
        if days:
            today=date.fromisoformat(payload.get('today') or date.today().isoformat()); start=(today-timedelta(days=days-1)).isoformat(); end=today.isoformat()
    scenario=any(k in text for k in ('如果','多浇','额外灌溉')) or bool(re.search(r'灌溉.*?[0-9]+[ ]*(?:mm|毫米)',text,re.I))
    if scenario:
        amount=re.search(r'([0-9]+(?:[.][0-9]+)?)[ ]*(?:mm|毫米)',text,re.I)
        args.update(start_date=supplement.get('start_date') or start,extra_irrigation_mm=supplement.get('extra_irrigation_mm',float(amount[1]) if amount else None))
        if supplement.get('baseline_task_id'): args['baseline_task_id']=supplement['baseline_task_id']
        name='run_hydrus_scenario'; result.update(intent='scenario',need_retrieval=False)
    elif any(k in text for k in ('墒情','含水','湿度')):
        depth=re.search(r'([0-9]+(?:[.][0-9]+)?)[ ]*(?:cm|厘米)',text,re.I)
        depths={c['depth_cm'] for c in payload.get('plot_context',{}).get('observation_catalog',[]) if c['parameter']=='soil_moisture' and c['depth_cm'] is not None}
        unique=next(iter(depths)) if len(depths)==1 else None
        args.update(depth_cm=supplement.get('depth_cm',float(depth[1]) if depth else unique),start=start,end=end,agg='daily_mean')
        name='query_soil_moisture'; result.update(intent='data_query',need_retrieval=False)
    elif any(k in text for k in ('解释','为什么')) and (supplement.get('task_id') or re.search(r'task_[A-Za-z0-9_-]+',text)):
        task=re.search(r'task_[A-Za-z0-9_-]+',text)
        args={'task_id':supplement.get('task_id') or task[0],'tool':supplement.get('tool') or ('beps' if 'beps' in text.lower() else 'apsim' if 'apsim' in text.lower() else 'hydrus')}
        name='read_model_result'; result.update(intent='model_explain',need_retrieval=False)
    else: return result
    missing=[k for k,v in args.items() if v is None]
    result.update(tool_calls=[{'name':name,'arguments':{k:v for k,v in args.items() if v is not None}}],missing_fields=missing,clarify_question='请补充：'+'、'.join(missing) if missing else None)
    return result
def answer_rules(payload):
    claims=[]; citations=[]; limitations=['MOCK模板回答，不是蔡济远真实服务或真实文献检索']
    if payload.get('intent')=='knowledge':
        citations=json.loads(Path(__file__).with_name('mock_corpus.json').read_text(encoding='utf-8'))
        claims=[{'text':c['snippet'],'evidence_ids':[c['evidence_id']]} for c in citations]
    for r in payload.get('tool_results',[]):
        if r.get('status') not in {'success','replay'} or r.get('source_type')=='demo':
            limitations.append('工具不可用或演示，不生成数值解释'); continue
        numbers={k:v for k,v in r['outputs'].items() if isinstance(v,(int,float)) and not isinstance(v,bool)}
        text='MOCK 模板：'+r['tool']+'；'+json.dumps(numbers,ensure_ascii=False)+'；来源='+r['source_type']
        claims.append({'text':text,'evidence_ids':[r['evidence_id']]})
    return {'answer':'；'.join(c['text'] for c in claims) or 'MOCK：没有可解释的有效工具结果','claims':claims,'citations':citations,'limitations':limitations,'check_items':[],'clarify_question':None,'retrieval_trace':{'mode':'mock'},'mock':True}
app=Flask(__name__)
@app.get('/health')
def health(): return jsonify(status='ok',mock=True,service='deterministic_mock')
@app.post('/v1/route')
def route(): return jsonify(route_rules(request.get_json(silent=True) or {}))
@app.post('/v1/answer')
def answer(): return jsonify(answer_rules(request.get_json(silent=True) or {}))
if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8001); args=parser.parse_args()
    app.run(host='127.0.0.1',port=args.port,debug=False)
