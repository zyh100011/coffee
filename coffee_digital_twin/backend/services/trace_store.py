"""Complete structured traces; no credential-bearing request headers."""
import json
from database.init_db import get_connection,now_iso
SQL='''CREATE TABLE IF NOT EXISTS assistant_traces(trace_id TEXT PRIMARY KEY,session_id TEXT,turn_id TEXT,plot_id TEXT,message TEXT,route_json TEXT,tool_calls_json TEXT,tool_results_json TEXT,answer_json TEXT,blocks_json TEXT,latency_ms_json TEXT,errors_json TEXT,service_mode TEXT,created_at TEXT);'''
def init_traces(conn):
    conn.executescript(SQL)
    conn.execute('CREATE TABLE IF NOT EXISTS data_query_evidence(evidence_id TEXT PRIMARY KEY,plot_id TEXT,result_json TEXT,created_at TEXT)')
def save_data_evidence(result):
    with get_connection() as conn:
        conn.execute('INSERT INTO data_query_evidence VALUES (?,?,?,?)',(result['evidence_id'],result['plot_id'],json.dumps(result,ensure_ascii=False),now_iso()))
def save(trace):
    keys=('route','tool_calls','tool_results','answer','blocks','latency_ms','errors')
    with get_connection() as conn:
        conn.execute('INSERT INTO assistant_traces VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
          (trace['trace_id'],trace['session_id'],trace['turn_id'],trace.get('plot_id'),trace['message'],
           *(json.dumps(trace.get(k,{}),ensure_ascii=False) for k in keys),trace['service_mode'],now_iso()))
def lookup(evidence_id,plot_id=None):
    with get_connection() as conn:
        row=conn.execute('SELECT * FROM data_query_evidence WHERE evidence_id=?',(evidence_id,)).fetchone()
        if row and (not plot_id or row['plot_id']==plot_id): return json.loads(row['result_json'])
        rows=conn.execute('SELECT plot_id,tool_results_json,answer_json,service_mode FROM assistant_traces ORDER BY created_at DESC').fetchall()
        for row in rows:
            if plot_id and row['plot_id']!=plot_id: continue
            for item in json.loads(row['tool_results_json'])+json.loads(row['answer_json']).get('citations',[]):
                if item.get('evidence_id')==evidence_id:
                    if 'tool' not in item:
                        item=dict(item,source_type='demo' if row['service_mode']=='mock' else item.get('source_type','literature'))
                    return item
        results=conn.execute('SELECT plot_id,result_json FROM model_results').fetchall()
        for row in results:
            if plot_id and row['plot_id']!=plot_id: continue
            result=json.loads(row['result_json'])
            for item in [result]+[result.get(k,{}) for k in ('apsim','hydrus','beps')]:
                if item.get('evidence_id')==evidence_id: return item
        exists=conn.execute("SELECT 1 FROM sqlite_master WHERE name='scenario_compares'").fetchone()
        if exists:
            for row in conn.execute('SELECT * FROM scenario_compares'):
                if plot_id and 'plot_id' in row.keys() and row['plot_id']!=plot_id: continue
                for key in row.keys():
                    if key.endswith('_json') and row[key]:
                        try: value=json.loads(row[key])
                        except (ValueError,TypeError): continue
                        stack=[value]
                        while stack:
                            item=stack.pop()
                            if isinstance(item,dict):
                                if item.get('evidence_id')==evidence_id: return item
                                stack.extend(item.values())
                            elif isinstance(item,list): stack.extend(item)
    return None
