from services.trace_store import save
from services.tool_result import make_tool_result
def test_report_bound_order_html_escape_and_plot(client):
    r=make_tool_result(tool='data_query',plot_id='p',status='success',outputs={'mean':.21},units={'value':'cm3/cm3'})
    trace={'trace_id':'tr_report','session_id':'s','turn_id':'t','plot_id':'p','message':'<script>alert(1)</script>',
        'tool_results':[r],'answer':{'citations':[],'claims':[{'text':'均值0.21','evidence_ids':[r['evidence_id']]},{'text':'错误999','evidence_ids':['bad']}],'check_items':['核对探头']},
        'blocks':[{'type':'fact','label':'mean','value':.21,'unit':'cm3/cm3','evidence_id':r['evidence_id']}, {'type':'warning','text':'待校验'}],
        'service_mode':'mock'}
    save(trace)
    response=client.post('/api/report/create',json={'trace_id':'tr_report','plot_id':'p'})
    assert response.status_code==200
    rid=response.get_json()['report_id']
    report=client.get('/api/report/'+rid+'?plot_id=p').get_json()
    assert [s['title'] for s in report['sections']]==['事实','依据','情景差异','建议/核查','缺项与限制']
    assert report['sections'][0]['evidence_ids']==[r['evidence_id']]
    assert report['sections'][2]['note']=='无可用证据'
    assert report['sections'][3]['items'][1]['text'].startswith('[未核验]')
    text=client.get('/api/report/'+rid+'.html').get_data(as_text=True)
    assert '<script>' not in text and '&lt;script&gt;' in text and '@media print' in text
    assert '<strong>实测</strong>' in text
    assert client.get('/api/report/'+rid+'?plot_id=q').status_code==404
    assert client.get('/api/report/list?plot_id=q').get_json()['items']==[]
    assert client.post('/api/report/create',json={'trace_id':'tr_report','plot_id':'q'}).status_code==404
    assert client.post('/api/report/create',json={'compare_id':'not_available'}).status_code==404
