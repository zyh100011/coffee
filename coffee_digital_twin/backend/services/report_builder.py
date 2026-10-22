"""Evidence-bound report snapshots; HTML escapes all untrusted content."""
import html
import json
from database.init_db import get_connection
from services.trace_store import lookup

ORDER=['事实','依据','情景差异','建议/核查','缺项与限制']
def build_report(source_id,kind='trace',plot_id=None):
    with get_connection() as conn:
        if kind=='trace':
            row=conn.execute('SELECT * FROM assistant_traces WHERE trace_id=?',(source_id,)).fetchone()
            if not row or (plot_id and row['plot_id']!=plot_id): raise LookupError('调用轨迹未找到')
            results=json.loads(row['tool_results_json']); answer=json.loads(row['answer_json']); blocks=json.loads(row['blocks_json'])
            report={'plot_id':row['plot_id'],'source_id':source_id,'source_type':'trace','service_mode':row['service_mode'],'question':row['message']}
            citations=answer.get('citations',[])
            facts=[b for b in blocks if b['type'] in ('fact','chart')]
            available={r['evidence_id'] for r in results if r['status'] in ('success','replay') and r['source_type']!='demo'}
            claims=[]
            forbidden={r['evidence_id'] for r in results}-available
            allowed=available|{c['evidence_id'] for c in citations if c['evidence_id'] not in forbidden}
            for c in answer.get('claims',[]):
                valid=bool(c.get('evidence_ids')) and set(c['evidence_ids'])<=allowed
                claims.append({'text':c['text'] if valid else '[未核验] '+c['text'],'evidence_ids':c['evidence_ids'] if valid else []})
            checks=answer.get('check_items',[])+[x for b in blocks if b['type']=='check_items' for x in b['items']]
            limits=[b['text'] for b in blocks if b['type']=='warning']+[b.get('question','缺项：'+','.join(b.get('fields',[]))) for b in blocks if b['type']=='missing']
            evidence=[{'evidence_id':r['evidence_id'],'source_type':r['source_type'],'status':r['status'],'mode':r['mode'],'text':r['tool']+' · '+r['parameter_version']} for r in results]
            evidence += [{'evidence_id':c['evidence_id'],'source_type':'demo' if row['service_mode']=='mock' else 'literature','status':'success','mode':'live','text':c['title']+' · '+c['locator']} for c in citations]
            items=[facts,evidence,[],claims+[{'text':x,'evidence_ids':[]} for x in checks],[{'text':x,'evidence_ids':[]} for x in limits]]
        else:
            exists=conn.execute("SELECT 1 FROM sqlite_master WHERE name='scenario_compares'").fetchone()
            if not exists: raise LookupError('情景比较记录将在Phase4接入')
            row=conn.execute('SELECT * FROM scenario_compares WHERE compare_id=?',(source_id,)).fetchone()
            if not row or (plot_id and row['plot_id']!=plot_id): raise LookupError('情景比较记录未找到')
            raw=json.loads(row['compare_json'])
            report={'plot_id':row['plot_id'],'source_id':source_id,'source_type':'compare','service_mode':raw.get('service_mode','live'),'question':'情景比较'}
            evidence=[{'evidence_id':r['evidence_id'],'source_type':r['source_type'],'status':r['status'],'mode':r['mode'],'text':r['tool']} for r in (raw.get('baseline'),raw.get('variant')) if isinstance(r,dict)]
            ids=[e['evidence_id'] for e in evidence if e['status'] in ('success','replay')] if raw.get('parameter_verified') else []
            facts=[{'type':'chart','series':raw['series'],'source_type':'simulation_uncalibrated','evidence_ids':ids,'mode':raw['mode']}] if ids else []
            items=[facts,evidence,[{'text':json.dumps(raw.get('output_diff',{}),ensure_ascii=False),'evidence_ids':ids}] if ids else [],[],[{'text':x,'evidence_ids':[]} for x in raw.get('undetermined',[])+raw.get('assumptions',[])+raw.get('warnings',[])]]
            if raw.get('mode')=='replay': items[4].insert(0,{'text':'历史结果回放，仅解释历史假设案例，非当前地块新计算','evidence_ids':[]})
    sections=[]
    for title,content in zip(ORDER,items):
        ids=[]
        for item in content:
            ids += item.get('evidence_ids',[])
            if item.get('evidence_id'): ids.append(item['evidence_id'])
        sections.append({'title':title,'items':content,'evidence_ids':list(dict.fromkeys(ids)),'note':'无可用证据' if not ids else ''})
    report['sections']=sections; report['evidence']=evidence
    return report

def render_html(report):
    esc=lambda x:html.escape(str(x),quote=True)
    labels={'observation':'实测','literature':'文献','simulation_uncalibrated':'模拟·未校准','proxy_model':'代理模型','simplified_model':'简化模型','demo':'演示数据'}
    evidence={e['evidence_id']:e for e in report.get('evidence',[])}
    def provenance(item):
        source=item.get('source_type') or evidence.get(item.get('evidence_id'),{}).get('source_type')
        mode=item.get('mode') or evidence.get(item.get('evidence_id'),{}).get('mode')
        label=labels.get(source,'来源未核验')+('·历史回放' if mode=='replay' else '')
        return '<p><strong>'+esc(label)+'</strong></p>'
    parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>咖啡农事循证决策报告</title><style>body{font:16px/1.7 sans-serif;color:#1d2a22;background:#f4f7f3;max-width:900px;margin:24px auto;padding:24px;}section{background:white;padding:24px;margin:20px 0;border:1px solid #dfe7df;break-inside:avoid;}h1{color:#1f5a3a;}pre{white-space:pre-wrap;overflow-wrap:anywhere;}small{color:#5f6b63;}table{width:100%;border-collapse:collapse;}td,th{padding:8px;border:1px solid #dfe7df;}@media print{body{background:white;margin:0;padding:0;}button{display:none;}section{break-inside:auto;}}</style><body><h1>咖啡农事循证决策报告</h1>']
    parts.append('<p>'+esc(report.get('question',''))+'</p><p>服务模式：'+esc(report.get('service_mode',''))+'</p>')
    for section in report['sections']:
        parts.append('<section><h2>'+esc(section['title'])+'</h2>')
        if section['note']:parts.append('<p>'+esc(section['note'])+'</p>')
        for item in section['items']:
            if item.get('type') in ('fact','chart') or item.get('source_type'): parts.append(provenance(item))
            if item.get('type')=='chart':
                parts.append('<table><tr><th>序列</th><th>时间</th><th>数值</th></tr>')
                for line in item.get('series',[]):
                    for x,y in line['data']: parts.append('<tr><td>'+esc(line['name'])+'</td><td>'+esc(x)+'</td><td>'+esc(y)+'</td></tr>')
                parts.append('</table>')
            elif item.get('type')=='fact': parts.append('<p>'+esc(item['label'])+'：'+esc(item['value'])+' '+esc(item.get('unit',''))+'</p>')
            else: parts.append('<pre>'+esc(item.get('text',json.dumps(item,ensure_ascii=False)))+'</pre>')
        parts.append('<small>依据：'+esc('、'.join(section['evidence_ids']) or '无可用证据')+'</small></section>')
    parts.append('<button onclick="window.print()">打印 / 保存为PDF</button></body></html>')
    return ''.join(parts)
