"""Legacy adapter provenance wrappers; executable whitelist added in T2.8."""
import hashlib
import copy
import json
import time
import uuid
from jsonschema import Draft202012Validator
from datetime import date, timedelta
from pathlib import Path
from services.tool_result import make_tool_result, validate_tool_result

AVAILABLE = {'success','replay'}


def wrap_legacy_result(tool, raw, ctx):
    if 'evidence_id' in raw:
        if validate_tool_result(raw):
            return make_tool_result(tool=tool,task_id=ctx.get('task_id'),plot_id=ctx.get('plot_id'),
                                    warnings=['invalid_tool_result'])
        return raw
    status = {'apsim':{'success':'success','fallback':'fallback'},
              'beps':{'ok':'success','fallback':'fallback'}}[tool].get(raw.get('status'),'failed')
    assumptions = ['OilPalm 代理映射咖啡指标，无咖啡产量验证'] if tool=='apsim' else ['BEPS-Lite 简化模型，无田间生产力验证']
    warnings = []
    if status=='failed':
        warnings.append('未知旧状态：'+str(raw.get('status')))
    if tool=='beps':
        assumptions += ['遮阴未映射时使用0.3；NDVI缺省；LAI缺省2.5；水分因子来自可用HYDRUS，否则不可用',
                        'BEPS依赖APSIM的LAI与HYDRUS吸水比，不是独立互证']
        weather = ctx.get('weather_series') or []
        if status=='success' and (not weather or any(w.get('source')=='demo' or
            any(w.get(k) is None for k in ('tmin','tmax','radiation_mj')) for w in weather)):
            status='fallback'
            warnings.append('旧BEPS补用演示或默认气象，不能作为模型证据')
    start=ctx.get('start_date')
    model_path=Path(__file__).resolve().parents[1]/'models'/f'{tool}_adapter.py'
    result=make_tool_result(tool=tool,task_id=ctx.get('task_id'),plot_id=ctx.get('plot_id'),
        time_range={'start':start,'end':(date.fromisoformat(start)+timedelta(days=7)).isoformat() if start else None},
        status=status,source_type='demo' if status=='fallback' else ('proxy_model' if tool=='apsim' else 'simplified_model'),
        model_version=tool+'-adapter-sha256:'+hashlib.sha256(model_path.read_bytes()).hexdigest()[:12],
        parameter_version=tool+'-defaults-unverified', inputs={'data_sources':ctx.get('data_sources',{}),
        'input_summary':raw.get('input_summary',{}),'upstream':ctx.get('upstream',{})},
        assumptions=assumptions,outputs=raw if status in AVAILABLE|{'fallback'} else {},warnings=warnings)
    if status=='fallback':
        result['warnings'].append('工程演示数据，不是可用科学证据')
    return result


def legacy_inputs(result):
    return result.get('outputs',{}) if result.get('status') in AVAILABLE else {}


STR={'type':'string','minLength':1,'maxLength':100}
DATE={'type':'string','pattern':'^[0-9]{4}-[0-9]{2}-[0-9]{2}$'}
def _schema(properties,required):
    return {'type':'object','properties':properties,'required':required,'additionalProperties':False}
QUERY={'plot_id':STR,'start':DATE,'end':DATE,'agg':{'enum':['raw','daily_mean']},
       'depth_cm':{'type':'number','minimum':0,'maximum':500},'data_version':STR,'device_id':STR,
       'unit':{'type':'string','maxLength':40},'limit':{'type':'integer','minimum':1,'maximum':1000},
       'offset':{'type':'integer','minimum':0}}
SCHEMAS={
 'get_plot_profile':_schema({'plot_id':STR},['plot_id']),
 'query_soil_moisture':_schema(QUERY,['plot_id','depth_cm','start','end']),
 'query_observation':_schema({**QUERY,'parameter':STR},['plot_id','parameter','start','end']),
 'run_hydrus_scenario':_schema({'plot_id':STR,'start_date':DATE,'extra_irrigation_mm':{'type':'number','minimum':0,'maximum':100},'baseline_task_id':STR},['plot_id','start_date','extra_irrigation_mm']),
 'read_model_result':_schema({'task_id':STR,'tool':{'enum':['apsim','hydrus','beps']}},['task_id','tool'])}

def available_tools(): return [{'name':name,'schema':schema} for name,schema in SCHEMAS.items()]

def prepare_calls(calls,ctx):
    prepared=[]; missing=[]; errors=[]
    if not isinstance(calls,list) or len(calls)>3:
        return [],[],['E_TOOL_LIMIT']
    if sum(isinstance(c,dict) and c.get('name')=='run_hydrus_scenario' for c in calls)>1:
        return [],[],['E_HYDRUS_LIMIT']
    for call in calls:
        if not isinstance(call,dict) or call.get('name') not in SCHEMAS:
            errors.append('E_TOOL_NOT_ALLOWED'); continue
        name=call['name']; args=call.get('arguments')
        if not isinstance(args,dict): errors.append('E_PARAM_INVALID'); continue
        args=dict(args)
        if 'plot_id' in SCHEMAS[name]['properties'] and not args.get('plot_id') and ctx.get('plot_id'):
            args['plot_id']=ctx['plot_id']
        if args.get('plot_id') and args['plot_id']!=ctx.get('plot_id'):
            errors.append('E_PLOT_MISMATCH'); continue
        # Only verified fields could fill arguments; current schema has no implicit numeric defaults.
        required=[k for k in SCHEMAS[name]['required'] if k not in args]
        missing.extend(required)
        failures=list(Draft202012Validator(SCHEMAS[name]).iter_errors(args))
        if any(e.validator!='required' for e in failures): errors.append('E_PARAM_INVALID'); continue
        if not required:
            try:
                for k in ('start','end','start_date'):
                    if k in args: date.fromisoformat(args[k])
                if 'start' in args and not 0<=(date.fromisoformat(args['end'])-date.fromisoformat(args['start'])).days<=365:
                    raise ValueError('date window')
            except (ValueError,TypeError): errors.append('E_PARAM_INVALID'); continue
        prepared.append({'name':name,'arguments':args})
    return prepared,sorted(set(missing)),errors

def _profile(args,ctx):
    from services.plot_context import load_plot_context
    profile=load_plot_context(args['plot_id'])
    return make_tool_result(tool='plot_profile',task_id=ctx.get('task_id'),plot_id=args['plot_id'],
        status='success' if profile['exists'] else 'missing_input',inputs=args,
        outputs={'known':profile['known'],'unknown':profile['unknown']} if profile['exists'] else {},
        missing_fields=profile['unknown'] if profile['exists'] else ['plot_profile'],warnings=['仅已核实且有来源的字段进入known'])

def _query(args,ctx):
    from services.data_service import query
    return query(args,ctx)

def _hydrus(args,ctx):
    from api.model_api import build_model_input
    from models.hydrus_adapter import run_hydrus_model
    from database.init_db import get_connection,now_iso
    if ctx.get('model_input') is not None:
        data=copy.deepcopy(ctx['model_input'])
        data.update(task_id='task_'+uuid.uuid4().hex,scenario={'start_date':args['start_date'],'extra_irrigation_mm':args['extra_irrigation_mm']})
    elif args.get('baseline_task_id'):
        from services.result_store import select_result
        baseline=select_result(args['baseline_task_id'],args['plot_id'])
        if not baseline: return make_tool_result(tool='hydrus',status='missing_input',plot_id=args['plot_id'],missing_fields=['baseline_task_id'])
        # Reuse baseline actual inputs and weather, never silently change the comparison setup.
        data=dict(baseline.get('model_input',{}))
        if not data or data.get('start_date')!=args['start_date']:
            return make_tool_result(tool='hydrus',status='missing_input',plot_id=args['plot_id'],missing_fields=['baseline_same_window'])
        data.update(task_id='task_'+uuid.uuid4().hex,scenario={'start_date':args['start_date'],'extra_irrigation_mm':args['extra_irrigation_mm']})
    else:
        data=build_model_input('task_'+uuid.uuid4().hex,args['plot_id'],args,args['start_date'])
    if ctx.get('mode') in {'live','replay'}: data['_mode']=ctx['mode']
    data['_timeout_s']=max(.01,min(60,ctx.get('deadline',time.monotonic()+60)-time.monotonic()-1))
    result=run_hydrus_model(data)
    with get_connection() as conn:
        conn.execute('INSERT INTO model_results VALUES (?,?,?,?)',(result['task_id'],args['plot_id'],json.dumps({'task_id':result['task_id'],'plot_id':args['plot_id'],'hydrus':result,'model_input':data},ensure_ascii=False),now_iso()))
    return result

def _read(args,ctx):
    from services.result_store import select_result
    result=select_result(args['task_id'],ctx.get('plot_id'))
    if not result or args['tool'] not in result:
        return make_tool_result(tool=args['tool'],plot_id=ctx.get('plot_id'),status='missing_input',missing_fields=['model_result'])
    raw=result[args['tool']]
    if args['tool']=='hydrus':
        if validate_tool_result(raw): return make_tool_result(tool='hydrus',warnings=['历史结果协议未核验'])
        return raw
    return wrap_legacy_result(args['tool'],raw,result.get('model_input',{}))

FUNCTIONS={'get_plot_profile':_profile,'query_observation':_query,'query_soil_moisture':_query,
           'run_hydrus_scenario':_hydrus,'read_model_result':_read}

def execute(calls,ctx):
    prepared,missing,errors=prepare_calls(calls,ctx)
    if missing or errors:
        return [make_tool_result(tool='data_query',task_id=ctx.get('task_id'),plot_id=ctx.get('plot_id'),
                                status='missing_input',missing_fields=missing,warnings=errors)]
    results=[]
    tool_deadline=min(ctx.get('deadline',time.monotonic()+60),time.monotonic()+60)
    for call in prepared:
        name=call['name']; args=dict(call['arguments'])
        if time.monotonic()>=tool_deadline-1:
            results.append(make_tool_result(tool='data_query',status='timeout',warnings=['工具时间预算耗尽'])); break
        try:
            if name=='query_soil_moisture' and FUNCTIONS[name] is _query:
                from services.moisture_query import run
                result=run(args,{**ctx,'deadline':tool_deadline})
            else:
                if name=='query_soil_moisture':args['parameter']='soil_moisture'
                result=FUNCTIONS[name](args,{**ctx,'deadline':tool_deadline})
        except (ValueError,TypeError) as error:
            result=make_tool_result(tool='hydrus' if name=='run_hydrus_scenario' else 'data_query',status='missing_input',missing_fields=['tool_inputs'],warnings=[str(error)])
        except Exception:
            result=make_tool_result(tool='hydrus' if name=='run_hydrus_scenario' else 'data_query',status='failed',warnings=['工具执行失败'])
        if validate_tool_result(result): result=make_tool_result(tool=result.get('tool','data_query'),warnings=['工具返回协议不合法'])
        results.append(result)
    return results
