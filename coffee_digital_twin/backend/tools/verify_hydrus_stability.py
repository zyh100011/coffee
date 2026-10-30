"""Five paired baseline/+20mm runs; does not overwrite historical case packages."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import uuid

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from models import hydrus_adapter as hydrus
from services.tool_result import validate_tool_result
from tools.material_paths import allowed_path, sha256_file


def decision(runs):
    passed = (len(runs)==10 and all(r['status']=='success' and r['duration_s']<=30
              and r['contract_ok'] and r['input_verified'] for r in runs)
              and len({r['parameter_version'] for r in runs})==1)
    return 'live' if passed else 'replay'


def verify(destination):
    destination=allowed_path(destination)
    original=hydrus.HYDRUS_MODE,hydrus.ALLOW_DEMO_FALLBACK,hydrus.HYDRUS_RUN_DIR
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
    hydrus.HYDRUS_RUN_DIR=original[2].parent/'phase3_stability'/stamp
    runs=[]
    try:
        hydrus.HYDRUS_MODE,hydrus.ALLOW_DEMO_FALLBACK='live',False
        for round_no in range(1,6):
            for extra in (0,20):
                started=time.perf_counter()
                result=hydrus.run_hydrus_model({'task_id':f'stability_{round_no}_{extra}_{uuid.uuid4().hex[:8]}',
                    'start_date':'2026-09-01','scenario':{'extra_irrigation_mm':extra}})
                elapsed=time.perf_counter()-started
                result_path=Path(result.get('inputs',{}).get('run_directory',''))/'hydrus_result.json'
                runs.append({'round':round_no,'extra_irrigation_mm':extra,'duration_s':round(elapsed,6),
                    'status':result['status'],'evidence_id':result['evidence_id'],
                    'model_version':result['model_version'],'parameter_version':result['parameter_version'],
                    'inputs':result['inputs'],'warnings':result['warnings'],
                    'contract_ok':not validate_tool_result(result),
                    'input_verified':result['inputs'].get('daily_prec_cm')==[extra/10,0,0,0,0,0,0],
                    'theta_day7_40cm':next((p['theta'] for p in result['outputs'].get('soil_profile_current',[]) if p['depth_cm']==40),None),
                    'result_file':str(result_path) if result_path.is_file() else None,
                    'result_sha256':sha256_file(result_path) if result_path.is_file() else None})
    finally:
        hydrus.HYDRUS_MODE,hydrus.ALLOW_DEMO_FALLBACK,hydrus.HYDRUS_RUN_DIR=original
    report={'checked_at':datetime.now(timezone.utc).isoformat(),
        'note':'提前执行10/18规则；仅Windows引擎工程稳定性，假设输入/模板参数，非田间校准',
        'configured_mode_before':original[0],'recommended_mode':decision(runs),
        'success_count':sum(r['status']=='success' for r in runs),'total':len(runs),
        'max_duration_s':max(r['duration_s'] for r in runs),'runs':runs}
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--out',type=Path,default=BACKEND.parent/'docs'/'zyh'/'hydrus_phase3_stability.json')
    args=parser.parse_args(); r=verify(args.out)
    print(json.dumps({k:v for k,v in r.items() if k!='runs'},ensure_ascii=False))
    sys.exit(0 if r['recommended_mode']=='live' else 1)
