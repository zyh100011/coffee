"""Isolated localhost HTTP verification; fixture plot, real HYDRUS, no observed data."""
import argparse
import gc
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import requests
from werkzeug.serving import make_server

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))

def verify(out):
    # Must run as its own process, before importing the application/config.
    with tempfile.TemporaryDirectory(prefix='coffee-scenario-') as temp:
        os.environ['COFFEE_DB_PATH']=str(Path(temp)/'verify.db')
        os.environ['COFFEE_RUNTIME_DIR']=str(Path(temp)/'runtime')
        os.environ['FLASK_DEBUG']='0'
        from app import create_app
        from tools.material_paths import allowed_path
        server=make_server('127.0.0.1',0,create_app())
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        root=f'http://127.0.0.1:{server.server_port}'
        try:
            def post(path,payload):
                response=requests.post(root+path,json=payload,timeout=70);response.raise_for_status();return response.json()
            post('/api/plot/init',{'plot_id':'verification_fixture','plot_name':'明确构造的引擎核验地块'})
            payload={'plot_id':'verification_fixture','start_date':'2026-09-01','change':{'extra_irrigation_mm':20},'mode':'live'}
            preview=post('/api/scenario/compare',{**payload,'confirm':False})
            result=post('/api/scenario/compare',{**payload,'confirm':True})
            reference=json.loads((BACKEND/'data/hydrus_cases/case_compare_0_vs_20.json').read_text(encoding='utf-8'))
            passed=(preview['status']=='confirmation_required' and result['status']=='success'
                    and result['parameter_verified'] and result['input_diff']==reference['input_diff']
                    and result['output_diff']==reference['output_diff'])
            report={'checked_at':datetime.now(timezone.utc).isoformat(),'passed':passed,
                'decision':'live' if passed else 'replay','deadline_rule':'按10/21规则于10/18提前核验',
                'label':'隔离构造地块、真实Windows引擎、假设输入、非田间校准',
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
    r=verify(parser.parse_args().out);print(json.dumps({k:r[k] for k in ('checked_at','passed','decision')},ensure_ascii=False))
    sys.exit(0 if r['passed'] else 1)
