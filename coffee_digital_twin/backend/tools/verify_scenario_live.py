"""Isolated localhost HTTP verification; fixture plot, real HYDRUS, no observed data."""
import argparse
import gc
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import sqlite3
from contextlib import closing
import threading
import requests
from werkzeug.serving import make_server

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))

def verify(out, snapshot=None, start_date='2026-09-01'):
    original_snapshot=Path(snapshot).resolve() if snapshot else None
    # Must run as its own process, before importing the application/config.
    with tempfile.TemporaryDirectory(prefix='coffee-scenario-') as temp:
        os.environ['COFFEE_DB_PATH']=str(Path(temp)/'verify.db')
        os.environ['COFFEE_RUNTIME_DIR']=str(Path(temp)/'runtime')
        os.environ['FLASK_DEBUG']='0'
        os.environ['SINGLE_PLOT_ID']=''
        if original_snapshot:
            from tools.material_paths import allowed_path
            original_snapshot=allowed_path(original_snapshot)
            with closing(sqlite3.connect(original_snapshot.as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(Path(temp)/'verify.db')) as dst:src.backup(dst)
        from app import create_app
        from tools.material_paths import allowed_path
        server=make_server('127.0.0.1',0,create_app())
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        root=f'http://127.0.0.1:{server.server_port}'
        try:
            def post(path,payload):
                response=requests.post(root+path,json=payload,timeout=70);response.raise_for_status();return response.json()
            if not original_snapshot:post('/api/plot/init',{'plot_id':'verification_fixture','plot_name':'明确构造的引擎核验地块'})
            payload={'plot_id':'plot_catimor_project' if original_snapshot else 'verification_fixture','start_date':start_date,'change':{'extra_irrigation_mm':20},'mode':'live'}
            preview=post('/api/scenario/compare',{**payload,'confirm':False})
            result=post('/api/scenario/compare',{**payload,'confirm':True})
            reference=json.loads((BACKEND/'data/hydrus_cases/case_compare_0_vs_20.json').read_text(encoding='utf-8'))
            passed=(preview['status']=='confirmation_required' and result['status']=='success'
                    and result['parameter_verified'] and all(abs(x-y)<.001 for x,y in zip(result['input_diff'],[2,0,0,0,0,0,0]))
                    and (all(abs(x-y)<.001 for x,y in zip(result['baseline']['inputs']['daily_prec_cm'],[.28,2.5,2.18,.7,.02,.14,.08])) if original_snapshot else result['output_diff']==reference['output_diff']))
            report={'checked_at':datetime.now(timezone.utc).isoformat(),'passed':passed,
                'decision':'live' if passed else 'replay','deadline_rule':'按10/21规则于10/18提前核验',
                'label':'实际库副本、冻结计数器派生日雨量、真实Windows引擎；非田间校准' if original_snapshot else '隔离构造地块、真实Windows引擎、假设输入、非田间校准',
                'comparison':result,'reference_match':passed,
                'note':'临时数据库和运行目录在退出后清理；本文件保留实际HTTP响应与证据ID'}
            target=allowed_path(out);target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            return report
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3)
            gc.collect()  # Release sqlite connection cycles before Windows temp cleanup.

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=BACKEND.parent/'docs/zyh/scenario_phase4_verification.json')
    parser.add_argument('--snapshot',type=Path);parser.add_argument('--start-date',default='2026-09-01')
    args=parser.parse_args()
    r=verify(args.out,args.snapshot,args.start_date);print(json.dumps({k:r[k] for k in ('checked_at','passed','decision')},ensure_ascii=False))
    sys.exit(0 if r['passed'] else 1)
