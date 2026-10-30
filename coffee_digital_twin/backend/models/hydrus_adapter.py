"""
HYDRUS-1D 适配器（集成版）
原始实现：张源皓（zyh）
集成适配：蔡济远
本届改造：张源皓任务 T2.1；仅适配、参数核验与输出解析，数值引擎不改。
"""
import copy
from datetime import date, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

from config import HYDRUS_EXE, HYDRUS_RUN_DIR, DEMO_DATA_DIR, HYDRUS_TIMEOUT_S, HYDRUS_MODE, ALLOW_DEMO_FALLBACK
from services.tool_result import make_tool_result
from services.unit_convert import normalize_irrigation_mm

_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / 'templates' / 'hydrus'
_CASE_DIR = Path(__file__).resolve().parents[1] / 'data' / 'hydrus_cases'
ASSUMPTIONS = ['土壤水力参数为模板通用值，非地块实测', '初始压力水头剖面为模板值',
               '下边界自由排水', '模拟窗口 7 天', '结果未经田间校准']
CLASSIFICATION = '工程默认阈值，未依据本地块田间持水量/凋萎点'


def _number(value, label, minimum=0, maximum=None):
    if isinstance(value, bool):
        raise ValueError(label + ' 不能为布尔值')
    value = float(value)
    if not math.isfinite(value) or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(label + ' 超出允许范围')
    return value


def _build_hydrus_input(data):
    scenario = data.get('scenario') or {}
    start = scenario.get('start_date') or data.get('start_date')
    if not start:
        return None, ['start_date']
    start = date.fromisoformat(start)
    days = [(start + timedelta(days=i)).isoformat() for i in range(7)]
    extra = _number(scenario.get('extra_irrigation_mm', 0), 'extra_irrigation_mm', maximum=100)
    rain, known = [0.0]*7, set()
    derived=None
    enabled=data.get('plot_info',{}).get('rainfall_counter_review',{}).get('model_daily_rain_enabled')
    if enabled and data.get('plot_id'):
        from services.rainfall import daily_rainfall
        derived=daily_rainfall(data['plot_id'],data.get('rainfall_source'),days[0],days[-1])
        weather=[{'date':p['date'],'rain_mm':p['rain_mm'],'source':p['source_type']} for p in derived['items']]
    else:
        weather=data.get('weather_series') or []
    for item in weather:
        if item.get('date') not in days or item.get('source') not in {'observation', 'observed'}:
            continue
        index = days.index(item['date'])
        value = item.get('rain_mm', item.get('rain'))
        if value is not None:
            rain[index] += _number(value, 'rain_mm')
            known.add(index)
    irrigation = [0.0]*7
    operations = []
    for item in data.get('farm_operations') or []:
        if item.get('op_type') != 'irrigation':
            continue
        op_date = item.get('date') or item.get('op_date')
        if op_date not in days:
            continue
        if item.get('amount') is None or not item.get('unit'):
            raise ValueError('窗口内灌溉缺 amount/unit')
        if item['unit'].lower() not in {'mm', '吨/亩', 't/mu', 'ton/mu', 'tons/mu'}:
            raise ValueError('未知灌溉单位')
        amount = _number(normalize_irrigation_mm(item['amount'], item['unit']), 'irrigation_mm')
        irrigation[days.index(op_date)] += amount
        operations.append(dict(item, normalized_mm=amount))
    irrigation[0] += extra
    assumptions = list(ASSUMPTIONS)
    if derived:
        assumptions.append('日降雨按'+derived['display_source']+'累计读数派生：'+derived['rule'])
        assumptions.extend(derived['warnings'])
    absent = [str(i+1) for i in range(7) if i not in known]
    if absent:
        assumptions.append('无实测降雨，第 ' + '/'.join(absent) + ' 天降雨按 0 mm 假设')
    if not operations:
        assumptions.append('窗口内无已记录灌溉；记录缺失不证明实际未灌溉')
    assumptions.append(f'第 1 天额外灌溉 {extra:g} mm，为假设情景，非灌溉指令')
    fluxes = {}
    for key, default in [('rsoil_cm_d', 0.15), ('rroot_cm_d', 0.22)]:
        supplied = scenario.get(key, data.get(key))
        source = scenario.get(key + '_source', data.get(key + '_source'))
        if supplied is not None and not source:
            raise ValueError(key + ' 缺少来源说明')
        fluxes[key] = default if supplied is None else _number(supplied, key)
        assumptions.append(f'{key}={fluxes[key]:g} cm/d，' + ('模板固定值' if supplied is None else '显式覆盖，来源：' + str(source)))
    return {'start_date': start.isoformat(), 'extra_irrigation_mm': extra, 'dates': days,
            **({'rainfall_derivation':derived} if derived else {}),
            'daily_prec_cm': [(a+b)/10 for a,b in zip(rain, irrigation)], 'farm_operations': operations,
            'assumptions': assumptions, **fluxes}, []


def _prepare_input_files(model_input, run_dir):
    for name in ('SELECTOR.IN', 'PROFILE.DAT'):
        shutil.copyfile(_TEMPLATE_DIR / name, run_dir / name)
    selector = (run_dir / 'SELECTOR.IN').read_text(encoding='utf-8').splitlines()
    for i, line in enumerate(selector):
        if re.search(r'\bMPL\s*$', line):
            parts = selector[i+1].split()
            parts[-1] = '7'
            selector[i+1] = ' '.join(parts)
        if line.startswith('TPrint(1)'):
            selector[i+1] = '          1 2 3 4 5 6 7'
    (run_dir / 'SELECTOR.IN').write_text('\n'.join(selector)+'\n', encoding='utf-8')
    atmosphere = (_TEMPLATE_DIR / 'ATMOSPH.IN').read_text(encoding='utf-8').splitlines()
    first = next(i for i,line in enumerate(atmosphere) if 'tAtm' in line) + 1
    rows = [f'{i+1:11d}{prec:12.3f}{model_input["rsoil_cm_d"]:12.6f}{model_input["rroot_cm_d"]:12.6f}'
            f'{100000:12d}{0:12d}{0:12d}{0:12d} ' for i,prec in enumerate(model_input['daily_prec_cm'])]
    atmosphere[first:first+7] = rows
    (run_dir / 'ATMOSPH.IN').write_text('\n'.join(atmosphere)+'\n', encoding='utf-8')
    (run_dir / 'LEVEL_01.DIR').write_text(str(run_dir.resolve())+'\n', encoding='utf-8')
    # Values below are read back from the files that the engine actually sees.
    written = (run_dir / 'ATMOSPH.IN').read_text(encoding='utf-8').splitlines()[first:first+7]
    inputs = {key:value for key,value in model_input.items() if key not in {'assumptions','daily_prec_cm'}}
    inputs['daily_prec_cm'] = [float(line.split()[1]) for line in written]
    inputs['rsoil_cm_d'] = [float(line.split()[2]) for line in written]
    inputs['rroot_cm_d'] = [float(line.split()[3]) for line in written]
    inputs['run_directory'] = str(run_dir)
    return inputs


def _execute_engine(run_dir, timeout=None):
    if not HYDRUS_EXE.is_file():
        raise FileNotFoundError('HYDRUS 引擎不存在')
    if os.name != 'nt' and HYDRUS_EXE.suffix != '.sh':
        raise RuntimeError('engine_unavailable_non_windows')
    command = [str(HYDRUS_EXE)] if os.name == 'nt' else ['sh', str(HYDRUS_EXE)]
    try:
        process = subprocess.run(command, cwd=run_dir, capture_output=True, text=True, input='\n',
                                 errors='replace', timeout=min(HYDRUS_TIMEOUT_S, timeout or HYDRUS_TIMEOUT_S))
    except subprocess.TimeoutExpired as error:
        content = (error.stdout or b'')
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        (run_dir / 'engine_stdout.txt').write_text(content + '\n[timeout]', encoding='utf-8')
        raise
    (run_dir / 'engine_stdout.txt').write_text(process.stdout+'\n'+process.stderr, encoding='utf-8')
    if (run_dir / 'Error.msg').exists():
        raise RuntimeError((run_dir / 'Error.msg').read_text(encoding='utf-8', errors='replace'))
    if process.returncode != 0:
        raise RuntimeError(f'HYDRUS exit code {process.returncode}')
    for name in ('T_Level.out','Nod_Inf.out'):
        if not (run_dir / name).is_file():
            raise RuntimeError('模型未生成 ' + name)


def _parse_output(run_dir, start_date):
    blocks, current = {}, None
    for line in (run_dir / 'Nod_Inf.out').read_text(encoding='utf-8').splitlines():
        match = re.fullmatch(r'\s*Time:\s*([-+\d.eE]+)\s*', line)
        if match:
            current = int(round(float(match[1])))
            blocks[current] = {}
        parts = line.split()
        if current is not None and len(parts) >= 4 and parts[0].isdigit():
            blocks[current][abs(float(parts[1]))] = float(parts[3])
    if set(blocks) != set(range(8)) or any(not values for values in blocks.values()):
        raise RuntimeError('缺少完整第 0–7 天剖面输出')
    targets = [10,20,40,60,100]
    def theta(day, depth):
        key = min(blocks[day], key=lambda value: abs(value-depth))
        if abs(key-depth) > 0.01:
            raise RuntimeError('模板不包含目标深度')
        return blocks[day][key]
    start = date.fromisoformat(start_date)
    series = [{'date': (start+timedelta(days=day)).isoformat(), 'model_day':day,
               **{f'd{depth}':theta(day,depth) for depth in targets}} for day in range(8)]
    def classification(value):
        return '适宜' if value > .24 else '略低' if value > .20 else '偏低' if value > .16 else '干旱'
    profile = [{'depth_cm':depth, 'theta':theta(7,depth), 'status':classification(theta(7,depth))} for depth in targets]
    lines = (run_dir / 'T_Level.out').read_text(encoding='utf-8').splitlines()
    header = next(line.split() for line in lines if 'sum(rRoot)' in line and 'sum(vRoot)' in line)
    values = [line.split() for line in lines if re.match(r'^\s*\d+\.\d+', line)]
    final = values[-1]
    potential = float(final[header.index('sum(rRoot)')])
    actual = float(final[header.index('sum(vRoot)')])
    ratio = actual/potential if potential else None
    front = max([depth for depth,value in blocks[7].items() if value-blocks[0][depth] > .01], default=0)
    d40 = theta(7,40)
    state = '水分适宜' if d40 > .24 else '轻度偏干' if d40 > .20 else '中度干旱' if d40 > .16 else '重度干旱'
    return {'soil_profile_current':profile, 'soil_moisture_series':series, 'root_uptake_ratio':ratio,
            'infiltration_depth_cm':front, 'water_status':state, 'classification_basis':CLASSIFICATION,
            'hydrus_explain':{'what':f'第7天40cm含水率 {d40:.4f}，较初始 {d40-theta(0,40):+.4f}',
                              'why':'未校准假设情景，不能由此给出实际灌溉处方'},
            'root_uptake_totals':{'actual_cm':actual,'potential_cm':potential}}


def _replay(data, result, extra):
    for path in sorted(_CASE_DIR.glob('case_*.json')):
        stored = json.loads(path.read_text(encoding='utf-8'))
        if stored.get('status') == 'success' and stored.get('inputs',{}).get('extra_irrigation_mm') == extra:
            original = copy.deepcopy(stored)
            # Never relabel the historical date or plot as a fresh simulation.
            result.update({key:original[key] for key in ('plot_id','time_range','inputs','outputs','assumptions','model_version','parameter_version','units')})
            result.update(status='replay',mode='replay',warnings=original['warnings'] +
                          ['历史结果回放，生成于 ' + original['created_at'], '仅解释该历史假设案例，不代表当前地块的新计算结果'])
            result['inputs']['replay_origin_evidence_id'] = original['evidence_id']
            result['inputs']['requested_plot_id'] = data.get('plot_id')
            return
    result['warnings'].append('找不到对应历史假设案例')


def run_hydrus_model(model_input_json):
    # AI辅助生成-DeepSeek-V3 - 2026年4月26日 09:22:15 - HYDRUS-1D模型调用与土壤水分状态解析
    task_id = model_input_json.get('task_id') or 'hydrus_' + uuid.uuid4().hex
    result = make_tool_result(tool='hydrus', task_id=task_id, plot_id=model_input_json.get('plot_id'),
                              source_type='simulation_uncalibrated', assumptions=list(ASSUMPTIONS),
                              units={'theta':'cm3/cm3','depth':'cm','prec':'cm/d','root_uptake_ratio':'dimensionless'})
    if not isinstance(task_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', task_id):
        result.update(status='missing_input', missing_fields=['task_id'], warnings=['task_id 格式无效'])
        return result
    run_dir = HYDRUS_RUN_DIR / (task_id + '_' + uuid.uuid4().hex[:8])
    run_dir.mkdir(parents=True, exist_ok=False)
    input_ready = False
    try:
        data, missing = _build_hydrus_input(model_input_json)
        if missing:
            result.update(status='missing_input',missing_fields=missing)
        else:
            input_ready = True
            result.update(time_range={'start':data['start_date'], 'end':(date.fromisoformat(data['start_date'])+timedelta(days=7)).isoformat()},
                          assumptions=data['assumptions'])
            mode = model_input_json.get('_mode', HYDRUS_MODE)
            if mode == 'replay':
                _replay(model_input_json,result,data['extra_irrigation_mm'])
            elif mode != 'live':
                raise ValueError('HYDRUS_MODE 必须为 live 或 replay')
            else:
                result['inputs'] = _prepare_input_files(data,run_dir)
                parameter_bytes = (run_dir/'SELECTOR.IN').read_bytes()+(run_dir/'PROFILE.DAT').read_bytes()
                result['parameter_version'] = 'hydrus-params-' + hashlib.sha256(parameter_bytes).hexdigest()[:12]
                result['model_version'] = 'HYDRUS-1D H1D_CALC.EXE sha256:' + (hashlib.sha256(HYDRUS_EXE.read_bytes()).hexdigest()[:12] if HYDRUS_EXE.is_file() else 'unavailable')
                _execute_engine(run_dir, model_input_json.get('_timeout_s'))
                result.update(status='success',outputs=_parse_output(run_dir,data['start_date']),warnings=[CLASSIFICATION])
    except (ValueError,TypeError) as error:
        result.update(status='failed' if input_ready else 'missing_input',
                      missing_fields=[] if input_ready else ['hydrus_inputs'],warnings=[str(error)])
    except subprocess.TimeoutExpired:
        result.update(status='timeout',warnings=['HYDRUS 计算超时'])
    except Exception as error:
        result.update(status='failed',warnings=[str(error)])
        if ALLOW_DEMO_FALLBACK:
            result.update(status='fallback',source_type='demo',outputs=json.loads((DEMO_DATA_DIR/'hydrus_result_demo.json').read_text(encoding='utf-8')))
            result['warnings'].append('工程演示数据，不是模拟结果')
    (run_dir/'hydrus_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
