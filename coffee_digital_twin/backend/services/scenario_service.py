"""Confirmed single-variable comparisons using the existing whitelisted tool."""
import json
import math
import time
import uuid
from datetime import date
from database.init_db import get_connection, now_iso
from models import hydrus_adapter as hydrus
from services import tool_registry
from services.trace_store import save


def init_compares(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS scenario_compares(compare_id TEXT PRIMARY KEY,plot_id TEXT,compare_json TEXT,created_at TEXT)')


class ScenarioInputError(ValueError):
    def __init__(self, message, code='E_PARAM_INVALID'):
        super().__init__(message); self.code=code


def validate(payload):
    if not isinstance(payload,dict): raise ScenarioInputError('请求必须为对象')
    if set(payload)-{'plot_id','start_date','change','confirm','tool','mode'}: raise ScenarioInputError('包含未允许的字段')
    if not isinstance(payload.get('plot_id'),str) or not payload['plot_id'].strip():
        raise ScenarioInputError('请选择当前地块','E_PLOT_REQUIRED')
    if payload.get('tool','hydrus')!='hydrus': raise ScenarioInputError('当前仅支持灌溉情景')
    try: date.fromisoformat(payload['start_date'])
    except (ValueError,TypeError,KeyError): raise ScenarioInputError('请提供有效起始日期')
    change=payload.get('change')
    if not isinstance(change,dict) or set(change)!={'extra_irrigation_mm'}: raise ScenarioInputError('仅允许单一变化 extra_irrigation_mm')
    amount=change['extra_irrigation_mm']
    if isinstance(amount,bool) or not isinstance(amount,(int,float)) or not math.isfinite(amount) or not 0<=amount<=100:
        raise ScenarioInputError('额外灌溉须为0–100mm的有限数值')
    if 'confirm' in payload and not isinstance(payload['confirm'],bool): raise ScenarioInputError('confirm须为布尔值')
    if payload.get('mode',hydrus.HYDRUS_MODE) not in {'live','replay'}: raise ScenarioInputError('mode须为live或replay')


def compare(payload):
    validate(payload)
    from api.model_api import build_model_input
    try: snapshot=build_model_input('preview',payload['plot_id'],{},payload['start_date'])
    except ValueError: raise ScenarioInputError('地块不存在，请选择有效地块','E_PLOT_REQUIRED')
    amount=payload['change']['extra_irrigation_mm']
    mode=payload.get('mode',hydrus.HYDRUS_MODE)
    base_input,_=hydrus._build_hydrus_input({**snapshot,'scenario':{'extra_irrigation_mm':0}})
    var_input,_=hydrus._build_hydrus_input({**snapshot,'scenario':{'extra_irrigation_mm':amount}})
    assumptions=list(dict.fromkeys(base_input['assumptions']+var_input['assumptions']))
    confirmation={'baseline':'窗口内已记录灌溉与已有实测降雨；未知降雨按0假设，记录缺失不证明未发生',
        'change':f'第1天额外灌溉 {amount:g} mm', 'start_date':payload['start_date'],'window_days':7,
        'recorded_irrigation':base_input['farm_operations'],'baseline_daily_prec_cm':base_input['daily_prec_cm']}
    if mode=='replay':
        historical=[]
        for path in sorted(hydrus._CASE_DIR.glob('case_*.json')):
            item=json.loads(path.read_text(encoding='utf-8'))
            if item.get('status')=='success' and item.get('inputs',{}).get('extra_irrigation_mm') in (0,amount): historical.append(item)
        assumptions=list(dict.fromkeys(x for item in historical for x in item['assumptions']))
        assumptions.append('回放只解释历史假设案例；保留历史日期和地块，不代表当前地块的新计算')
        confirmation['baseline']='历史0mm假设案例，与相同历史窗口的变化案例比较；不使用当前地块记录'
        confirmation['recorded_irrigation']=[]
        confirmation['baseline_daily_prec_cm']=None
        confirmation['historical_cases']=[{'time_range':r['time_range'],'created_at':r['created_at'],'evidence_id':r['evidence_id']} for r in historical]
    if payload.get('confirm') is not True:
        return {'status':'confirmation_required','mode':mode,'confirmation':confirmation,
            'assumptions':assumptions,'undetermined':snapshot['missing_fields']}
    begin=time.monotonic(); deadline=begin+60
    compare_id='cmp_'+uuid.uuid4().hex
    results=[]; calls=[]
    for extra in (0,amount):
        call={'name':'run_hydrus_scenario','arguments':{'plot_id':payload['plot_id'],
            'start_date':payload['start_date'],'extra_irrigation_mm':extra}}
        calls.append(call)
        results.append(tool_registry.execute([call],{'plot_id':payload['plot_id'],'mode':mode,
            'model_input':snapshot,'deadline':deadline})[0])
    baseline,variant=results
    warnings=[]; input_diff=[]; output_diff={}; rows=[]; series=[]; verified=False
    available=all(r['status'] in tool_registry.AVAILABLE and r['source_type']=='simulation_uncalibrated' for r in results)
    if available:
        try:
            a,b=(r['inputs']['daily_prec_cm'] for r in results)
            if len(a)!=7 or len(b)!=7: raise ValueError('逐日输入不完整')
            input_diff=[y-x for x,y in zip(a,b)]
            if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in a+b): raise ValueError('输入数值无效')
            if not abs(input_diff[0]-amount/10)<.001 or any(abs(x)>=.001 for x in input_diff[1:]): raise ValueError('参数未进入模型')
            if not baseline['parameter_version'] or baseline['parameter_version']!=variant['parameter_version'] or baseline['model_version']!=variant['model_version'] or baseline['time_range']!=variant['time_range'] or baseline['plot_id']!=variant['plot_id']:
                raise ValueError('参数版本、引擎版本、地块或窗口不一致')
            for key in ('rsoil_cm_d','rroot_cm_d'):
                if baseline['inputs'].get(key)!=variant['inputs'].get(key): raise ValueError('非目标输入发生变化')
            profiles=[{p['depth_cm']:p['theta'] for p in r['outputs']['soil_profile_current']} for r in results]
            if set(profiles[0])!={10,20,40,60,100} or set(profiles[0])!=set(profiles[1]): raise ValueError('深度输出不完整')
            rows=[{'depth_cm':d,'baseline':profiles[0][d],'variant':profiles[1][d],'difference':profiles[1][d]-profiles[0][d]} for d in sorted(profiles[0])]
            output_diff={'theta_day7_by_depth':{str(r['depth_cm']):r['difference'] for r in rows}}
            for key in ('infiltration_depth_cm','root_uptake_ratio'):
                x,y=(r['outputs'].get(key) for r in results)
                output_diff[key]=None if x is None or y is None else y-x
            dates=[[p['date'] for p in r['outputs']['soil_moisture_series']] for r in results]
            if dates[0]!=dates[1] or len(dates[0])!=8: raise ValueError('序列窗口不一致')
            series=[{'name':label,'color':color,'data':[[p['date'],p['d40']] for p in r['outputs']['soil_moisture_series']]} for r,label,color in zip(results,('基线40cm','变化组40cm'),('#5f6b63','#1f5a3a'))]
            verified=True
        except (ValueError,KeyError,TypeError) as error:
            warnings.append(str(error))
    if not verified:
        input_diff=[]; output_diff={}; rows=[]; series=[]
        warnings+= [w for r in results for w in r.get('warnings',[])]
    actual_mode='replay' if any(r['mode']=='replay' for r in results) else mode
    result={'compare_id':compare_id,'plot_id':payload['plot_id'],'baseline':baseline,'variant':variant,
        'input_diff':input_diff,'output_diff':output_diff,'rows':rows,'series':series,'parameter_verified':verified,
        'assumptions':list(dict.fromkeys(assumptions+[x for r in results for x in r['assumptions']])),
        'undetermined':list(dict.fromkeys(snapshot['missing_fields']+['本地块土壤/初始剖面尚未校准','现场实际灌溉条件需核查'])),
        'warnings':warnings,'mode':actual_mode,'status':('replay' if actual_mode=='replay' else 'success') if verified else 'failed',
        'confirmation':confirmation,'requested_start_date':payload['start_date'],'time_range':baseline['time_range'],
        'trace_id':'tr_'+uuid.uuid4().hex}
    if not verified:
        from services.errors import envelope,hydrus_code
        failure=envelope(hydrus_code(results),trace_id=result['trace_id'])
        result.update({k:v for k,v in failure.items() if k!='status'})
    with get_connection() as conn:
        conn.execute('INSERT INTO scenario_compares VALUES (?,?,?,?)',(compare_id,payload['plot_id'],json.dumps(result,ensure_ascii=False),now_iso()))
    save({'trace_id':result['trace_id'],'session_id':compare_id,'turn_id':compare_id,'plot_id':payload['plot_id'],
        'message':'灌溉假设A/B比较','route':{'intent':'scenario','request':payload},'tool_calls':calls,'tool_results':results,
        'answer':{},'blocks':[],'latency_ms':{'total':round((time.monotonic()-begin)*1000)},'errors':warnings,'service_mode':'live'})
    return result
