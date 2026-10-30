"""Release-readiness checks. Default HTTP run uses an isolated copy of the local DB."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import uuid
import requests

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from tools.material_paths import allowed_path

TABLES={'plots','farm_operations','model_tasks','model_results','advice_logs','raw_files','obs_long',
        'device_plot_map','lai_obs','farm_events','soil_reports','data_versions','assistant_traces',
        'data_query_evidence','reports','scenario_compares'}


def observation_query(conn, version):
    """Choose one real source; a diagnostic query does not certify a frozen release."""
    sql="""SELECT o.plot_id,o.parameter,o.depth_cm,o.device_id,o.unit,o.data_version,
        MIN(o.date) start,MAX(o.date) end FROM obs_long o
        JOIN plots p ON p.plot_id=o.plot_id JOIN raw_files f ON f.file_id=o.source_file_id
        WHERE f.data_version=o.data_version AND f.source_type='observation'
        AND o.value IS NOT NULL AND o.qc_flag IN ('ok','rain_reset')
        AND o.device_id IS NOT NULL AND o.device_id!='' AND o.unit IS NOT NULL"""
    params=[]
    if version:
        sql+=' AND o.data_version=?';params.append(version)
    sql+=''' GROUP BY o.plot_id,o.parameter,o.depth_cm,o.device_id,o.unit,o.data_version
        ORDER BY CASE WHEN o.parameter='soil_moisture' THEN 0 ELSE 1 END,
        o.plot_id,o.parameter,o.depth_cm,o.device_id,o.unit,o.data_version LIMIT 1'''
    group=conn.execute(sql,params).fetchone()
    if not group: return None
    query=dict(group);query['agg']='daily_mean'
    from datetime import date,timedelta
    query['start']=max(query['start'],(date.fromisoformat(query['end'])-timedelta(days=365)).isoformat())
    return query


def inspect_database(path, version):
    from tools.material_paths import sha256_file
    path=allowed_path(path)
    if not path.is_file(): return False,False,None,'数据库不存在'
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as conn:
        conn.row_factory=sqlite3.Row
        names={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing=TABLES-names
        if missing: return False,False,None,'缺表：'+','.join(sorted(missing))
        frozen=conn.execute('SELECT * FROM data_versions WHERE data_version=?',(version,)).fetchone()
        files=conn.execute('SELECT * FROM raw_files WHERE data_version=?',(version,)).fetchall()
        query=observation_query(conn,version) or observation_query(conn,None)
        if not version or not frozen or not files or any(r['source_type']!='observation' for r in files):
            return True,False,query,'缺少已冻结非空实测版本；现有实测仅用于接口诊断，不表示冻结验收通过'
        if json.loads(frozen['file_hashes_json'])!={r['file_id']:r['sha256'] for r in files}: return True,False,query,'冻结清单不一致'
        for row in files:
            if sha256_file(row['path'])!=row['sha256']: return True,False,query,'冻结原文件哈希改变'
        count=conn.execute("SELECT COUNT(*) FROM obs_long WHERE data_version=? AND value IS NOT NULL AND qc_flag IN ('ok','rain_reset')",(version,)).fetchone()[0]
        if count<=0 or count!=json.loads(frozen['row_counts_json']).get('obs_long'): return True,False,query,'冻结有效行数不一致'
        query=observation_query(conn,version)
        if not query: return True,False,None,'冻结观测无有效地块档案/来源关联'
        return True,True,query,f'非空冻结实测，{count}条有效观测；原文件哈希一致'


def run_checks(base_url, settings, db_state=None):
    """Each core endpoint gets an actual HTTP call, even when prerequisites are absent."""
    rows=[]
    def add(name,passed,detail): rows.append({'check':name,'status':'PASS' if passed else 'FAIL','detail':detail})
    add('python',sys.version_info[:2]==(3,11),f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}；要求3.11')
    failures=[]
    for line in (BACKEND/'requirements.txt').read_text(encoding='utf-8-sig').splitlines():
        if '==' not in line: continue
        name,expected=line.split('==',1)
        try: actual=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: actual='missing'
        if actual!=expected: failures.append(name+'版本不符')
    add('dependencies',not failures,'；'.join(failures) or '固定依赖版本全部匹配')
    env_ok=(settings['mode'] in ('live','replay') and not settings['fallback'] and not settings['debug']
            and 0<settings['timeout']<=60 and bool(settings['version']) and settings['evidence_url_valid'])
    add('environment',env_ok,'检查HYDRUS_MODE/超时/禁用fallback/关闭debug/DATA_VERSION/服务URL；不输出.env值或凭据')
    try: schema,frozen,query,detail=db_state or inspect_database(settings['database'],settings['version'])
    except (ValueError,OSError,sqlite3.Error,KeyError): schema,frozen,query,detail=False,False,None,'数据库/来源校验失败，请核查资料与路径'
    add('database_tables',schema,detail if not schema else '所需业务与来源表齐全')
    add('frozen_data',frozen,detail)
    engine=allowed_path(settings['engine']).is_file()
    cases=[];historical=[]
    for name in ('case_baseline_0mm.json','case_irrig_20mm.json'):
        try:
            item=json.loads((BACKEND/'data/hydrus_cases'/name).read_text(encoding='utf-8'))
            cases.append(item['status']=='success' and item['source_type']=='simulation_uncalibrated')
            historical.append(item)
        except (OSError,ValueError,KeyError): cases.append(False)
    add('hydrus',settings['mode'] in ('live','replay') and (engine if settings['mode']=='live' else all(cases)),
        f"模式{settings['mode']}；引擎{'存在' if engine else '缺失'}；0/20mm历史案例{'齐全' if all(cases) else '不齐'}；未校准")
    def http(name,method,path,payload,predicate):
        try:
            r=requests.request(method,base_url.rstrip('/')+path,json=payload if method=='POST' else None,
                               params=payload if method=='GET' else None,timeout=125 if 'assistant/chat' in path else 70)
            body=r.json();good=r.ok and isinstance(body,dict) and predicate(body)
            add(name,good,f'HTTP {r.status_code}；'+('契约与来源通过' if good else '未满足数据/服务/响应契约条件'))
            return body if isinstance(body,dict) else {}
        except (requests.RequestException,ValueError,TypeError,KeyError):
            add(name,False,'HTTP不可用或响应无效；未记录URL/响应正文以免泄露凭据');return {}
    health=http('evidence_health','GET','/api/assistant/health',{},lambda b:b.get('evidence_service',{}).get('status')=='ok' and b.get('evidence_service',{}).get('mock') is False)
    http('http_ping','GET','/api/ping',{},lambda b:b.get('status')=='ok')
    args=query or {}
    plot=args.get('plot_id')
    query_version=args.get('data_version')
    http('http_catalog','GET','/api/data/catalog',{'plot_id':plot} if plot else {},lambda b:bool(query) and any(query_version in c.get('data_versions',[]) and c.get('device_id')==args.get('device_id') and c.get('unit')==args.get('unit') and c.get('parameter')==args.get('parameter') for c in b.get('items',[])))
    http('http_query','POST','/api/data/query',args,lambda b:bool(query) and b.get('status')=='success' and b.get('source_type')=='observation' and b.get('parameter_version')==query_version and b.get('outputs',{}).get('n',0)>0)
    if not frozen:
        for row in rows:
            if row['check'] in ('http_catalog','http_query'):
                row['detail']+='；现有数据诊断，冻结验收仍未通过'
    message=(f"{args['depth_cm']:g}cm " if args.get('depth_cm') is not None else '')+(f"{args['start']}到{args['end']}"+('含水率' if args.get('parameter')=='soil_moisture' else '观测数据')+f"，参数{args['parameter']}，来源{args['device_id']}，单位{args['unit']}，版本{query_version}" if query else '请说明当前地块有哪些可核验数据')
    answer=http('http_assistant','POST','/api/assistant/chat',{'plot_id':plot,'session_id':'selfcheck_'+uuid.uuid4().hex,'message':message},lambda b:b.get('status')=='success' and b.get('service_mode')=='live' and not b.get('mock') and not b.get('errors') and bool(b.get('trace_id')))
    historical_start=historical[0]['time_range']['start'] if historical and all(cases) else None
    def valid_replay(body):
        return (len(historical)==2 and all(cases) and body.get('status')=='replay'
            and body.get('mode')=='replay' and body.get('parameter_verified') is True
            and all(body.get(key,{}).get('time_range')==original['time_range']
                and body.get(key,{}).get('plot_id')==original['plot_id']
                and body.get(key,{}).get('parameter_version')==original['parameter_version']
                for key,original in zip(('baseline','variant'),historical)))
    comparison=http('http_compare_replay','POST','/api/scenario/compare',{'plot_id':plot,'start_date':historical_start,'change':{'extra_irrigation_mm':20},'confirm':True,'mode':'replay'},valid_replay)
    report_args={'plot_id':plot}
    if comparison.get('compare_id'): report_args['compare_id']=comparison['compare_id']
    elif answer.get('trace_id'): report_args['trace_id']=answer['trace_id']
    report=http('http_report','POST','/api/report/create',report_args,lambda b:b.get('status')=='success' and bool(b.get('report_id')))
    if report.get('report_id'):
        http('http_report_detail','GET','/api/report/'+report['report_id'],{'plot_id':plot},lambda b:[s.get('title') for s in b.get('sections',[])]==['事实','依据','情景差异','建议/核查','缺项与限制'])
    return rows


def write_report(rows,out):
    out=allowed_path(out);out.parent.mkdir(parents=True,exist_ok=True)
    text='自检时间：'+datetime.now(timezone.utc).isoformat()+'\n检查 | 状态 | 说明\n'
    text+='\n'.join(f"{r['check']} | {r['status']} | {r['detail']}" for r in rows)
    text+='\n结果：'+('PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL：仍有缺项，不是正式交付就绪')+'\n'
    out.write_text(text,encoding='utf-8');return text


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',help='可选：检查已启动的本机/可信局域网服务，会新增自检trace/比较/报告')
    args=parser.parse_args()
    import config
    from urllib.parse import urlsplit
    service=urlsplit(config.EVIDENCE_SERVICE_URL)
    settings={'database':config.DATABASE_PATH,'version':config.DATA_VERSION,'mode':config.HYDRUS_MODE,
        'engine':config.HYDRUS_EXE,'fallback':config.ALLOW_DEMO_FALLBACK,'debug':config.DEBUG,
        'timeout':config.HYDRUS_TIMEOUT_S,'evidence_url_valid':service.scheme in ('http','https') and bool(service.hostname)}
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
    out=config.SERVER_DIR/'logs'/('selfcheck_'+stamp+'.txt')
    if args.base_url:
        url=urlsplit(args.base_url)
        if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment: parser.error('base-url须为无凭据的HTTP(S)服务根地址')
        rows=run_checks(args.base_url,settings)
    else:
        # Preserve source DB; inspect original schema before app compatibility migrations.
        try: state=inspect_database(settings['database'],settings['version'])
        except (ValueError,OSError,sqlite3.Error,KeyError): state=(False,False,None,'数据库或来源校验失败')
        with tempfile.TemporaryDirectory(prefix='coffee-selfcheck-') as temp:
            target=Path(temp)/'selfcheck.db'
            if allowed_path(settings['database']).is_file():
                with closing(sqlite3.connect(allowed_path(settings['database']).as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(target)) as dst: src.backup(dst)
            # All imports happen after temporary runtime/database paths are set.
            config.DATABASE_PATH=target;config.DATABASE_DIR=target.parent
            config.RUNTIME_DIR=Path(temp)/'runtime'
            for key,folder in [('APSIM_RUN_DIR','apsim_runs'),('HYDRUS_RUN_DIR','hydrus_runs'),('BEPS_RUN_DIR','beps_runs'),('RESULT_JSON_DIR','result_json')]: setattr(config,key,config.RUNTIME_DIR/folder)
            from app import create_app
            from werkzeug.serving import make_server
            server=make_server('127.0.0.1',0,create_app());thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try: rows=run_checks(f'http://127.0.0.1:{server.server_port}',settings,state)
            finally:
                server.shutdown();server.server_close();thread.join(timeout=3)
                import gc
                gc.collect()
    print(write_report(rows,out));print('日志：'+str(out))
    return 0 if all(r['status']=='PASS' for r in rows) else 1


if __name__=='__main__': sys.exit(main())
