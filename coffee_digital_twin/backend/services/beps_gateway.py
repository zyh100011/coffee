"""Preflight the protected legacy adapter; never supply its hidden input defaults."""
import math
from datetime import date, timedelta

from services.tool_registry import legacy_inputs, wrap_legacy_result
from services.tool_result import make_tool_result, validate_tool_result


def _number(value, low, high):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and low <= value <= high


def run_beps_checked(model_input, apsim, hydrus):
    a, h = legacy_inputs(apsim), legacy_inputs(hydrus)
    missing, warnings = [], []
    lai_policy = model_input.get('plot_info', {}).get('lai_use', '')
    lai_disabled = '本期' in lai_policy and any(x in lai_policy for x in ('不作为', '不使用'))
    if lai_disabled or not _number(a.get('lai'), .01, 20):
        missing.append('supported_canopy_input')
        warnings.append('现有BEPS实现仍需要LAI；本期不导入LAI实测，也不以2.5补缺。需简光耀提供不依赖LAI的有效输入方案')
    water = h.get('root_uptake_ratio')
    if water is None:
        water = h.get('root_uptake_efficiency')
    if not _number(water, .2, 1):
        missing.append('water_factor_supported_range')
        warnings.append('旧BEPS仅支持0.2至1的吸水因子，不把0或缺失值改为默认值')
    shades = {'无遮挡': '无遮阴', '无遮阴': '无遮阴', '轻度遮阴': '轻度遮阴',
              '中等遮阴': '中等遮阴', '重度遮阴': '重度遮阴'}
    shade = model_input.get('plot_info', {}).get('shade_level')
    if shade not in shades:
        missing.append('shade_level')
    start = model_input.get('start_date')
    window = {'start': start, 'end': (date.fromisoformat(start)+timedelta(days=7)).isoformat() if start else None}
    for name, upstream in [('apsim', apsim), ('hydrus', hydrus)]:
        if (validate_tool_result(upstream) or upstream.get('source_type') == 'demo'
                or upstream.get('plot_id') != model_input.get('plot_id')
                or upstream.get('time_range') != window
                or not upstream.get('model_version') or not upstream.get('parameter_version')):
            missing.append(name + '_same_plot_window_provenance')
    weather = model_input.get('weather_series') or []
    expected = [(date.fromisoformat(start)+timedelta(days=i)).isoformat() for i in range(7)] if start else []
    if not expected or [w.get('date') for w in weather] != expected:
        missing.append('complete_seven_day_weather')
    for row in weather:
        if row.get('source') not in {'observation', 'gridded_reanalysis'} or not all(
            _number(row.get(k), lo, hi) for k,lo,hi in [('tmin',-90,65),('tmax',-90,65),
                ('radiation_mj',0,60),('wind_ms',0,100)]):
            missing.append('verified_weather_fields')
            break
        if row['tmin'] > row['tmax']:
            missing.append('valid_temperature_range')
    if missing:
        return make_tool_result(tool='beps', task_id=model_input.get('task_id'), plot_id=model_input.get('plot_id'),
            status='missing_input', source_type='simplified_model',
            time_range=window,
            missing_fields=sorted(set(missing)), warnings=warnings,
            inputs={'data_sources': model_input.get('data_sources', {})})
    from models.beps_adapter import run_beps_model
    prepared = {**model_input, 'plot_info': {**model_input['plot_info'], 'shade_level': shades[shade]}}
    raw = run_beps_model(prepared, apsim_result=a, hydrus_result={'root_uptake_ratio': water})
    upstream = {'lai': apsim.get('evidence_id'), 'water_factor': hydrus.get('evidence_id')}
    result = wrap_legacy_result('beps', raw, {**prepared, 'upstream': upstream})
    result['assumptions'] = ['BEPS-Lite简化模型，无田间生产力验证',
        '冠层输入来自可用APSIM，吸水因子来自可用HYDRUS，不是三模型独立互证',
        'NDVI未输入；遮阴来自地块档案；气象和上游因子经外层检查后运行',
        'ET为简化估算；NPP换算量不等同于生态系统净碳汇']
    return result
