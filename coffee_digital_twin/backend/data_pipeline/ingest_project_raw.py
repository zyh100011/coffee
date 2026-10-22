"""Import the confirmed project classification, retaining unknown sensor semantics.

This reads the two known long-table exports; it never executes content in a row.
Missing depths stay NULL, percentages stay raw, rain is not a daily increment.
"""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data_pipeline.profile_raw import read_tables, precision_suspect
from data_pipeline.ingest_monitoring import _ts
from database.init_db import get_connection, init_db, now_iso
from tools.material_paths import MATERIAL_ROOT, allowed_path, sha256_file

PROFILE_PATH = Path(__file__).with_name('real_data_profile.json')


def load_profile():
    return json.loads(PROFILE_PATH.read_text(encoding='utf-8'))


def _digest(parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


def _register_plot(conn, profile):
    # A management group, not a claim that Pu'er and Lujiangba share coordinates.
    raw = dict(plot_id=profile['plot_id'], plot_name=profile['plot_name'], crop='coffee',
               coffee_variety=profile['cultivar'], data_scope=profile['scope'],
               classification_source=profile['classification_source'],
               field_sources={'coffee_variety': 'field_record'}, verified_fields=['coffee_variety'],
               missing_fields=profile['missing_fields'],
               **{k:profile[k] for k in ('layer_intervals_cm','water_content_convention','rain_source','irrigation_management','confirmation_source') if k in profile})
    conn.execute('INSERT OR IGNORE INTO plots (plot_id,plot_name,crop,coffee_variety,raw_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?)',
                 (profile['plot_id'], profile['plot_name'], 'coffee', profile['cultivar'], json.dumps(raw, ensure_ascii=False), now_iso(), now_iso()))
    sync_confirmed_profile(conn, profile)


def sync_confirmed_profile(conn, profile):
    """Merge only confirmed profile fields; leave observations and farm events intact."""
    row = conn.execute('SELECT raw_json FROM plots WHERE plot_id=?', (profile['plot_id'],)).fetchone()
    if not row:
        raise ValueError('卡蒂姆档案不存在')
    raw = json.loads(row['raw_json'])
    for key in ('plot_name','classification_source','missing_fields','layer_intervals_cm',
                'water_content_convention','rain_source','irrigation_management',
                'rainfall_input_policy','rainfall_input_note','irrigation_input_policy',
                'rainfall_counter_review','soil_sampling_context','representative_soil_sample',
                'soil_parameter_policy','soil_parameter_note',
                'fertilizer_management','lai_use','confirmation_source','area_mu','elevation_m',
                'planting_year','tree_age','tree_age_reference_year','tree_age_source',
                'shade_level','row_spacing_m','plant_spacing_m'):
        if key in profile:
            raw[key] = profile[key]
    raw.update(coffee_variety=profile['cultivar'], data_scope=profile['scope'])
    coordinates = profile.get('coordinates', {})
    for key in ('latitude', 'longitude'):
        if key in coordinates:
            raw[key] = coordinates[key]
    if coordinates:
        raw['coordinate_source'] = coordinates['source']
    sources = raw.setdefault('field_sources', {})
    confirmed = ['coffee_variety'] + [k for k in ('area_mu','elevation_m','planting_year',
                 'tree_age','shade_level','row_spacing_m','plant_spacing_m') if k in profile]
    confirmed += [k for k in ('latitude','longitude') if k in coordinates]
    for key in confirmed:
        sources[key] = 'field_record'
    if 'tree_age' in profile:
        sources['tree_age'] = 'estimated'
    raw['verified_fields'] = list(dict.fromkeys(raw.get('verified_fields', []) + confirmed))
    conn.execute('''UPDATE plots SET plot_name=?,coffee_variety=?,area_mu=?,elevation_m=?,
                    latitude=?,longitude=?,tree_age=?,shade_level=?,row_spacing_m=?,
                    plant_spacing_m=?,raw_json=?,updated_at=? WHERE plot_id=?''',
                 (raw['plot_name'],raw['coffee_variety'],raw.get('area_mu'),raw.get('elevation_m'),
                  raw.get('latitude'),raw.get('longitude'),raw.get('tree_age'),raw.get('shade_level'),
                  raw.get('row_spacing_m'),raw.get('plant_spacing_m'),json.dumps(raw,ensure_ascii=False),
                  now_iso(),profile['plot_id']))


def _source(kind, path, row):
    if kind == 'puer':
        device = str(row['设备编号']).strip()
        if not device or precision_suspect(device):
            raise ValueError('invalid_device_id')
        return device, '普洱爱伲庄园工作站 · ' + device, 'hardware_id'
    match = re.search(r'(土壤|环境)监测([123])历史数据\.csv$', path.name)
    if not match:
        raise ValueError('unrecognized_source_filename')
    category = 'soil' if match[1] == '土壤' else 'environment'
    return f'source:lujiangba:{category}{match[2]}', f'潞江坝{match[1]}监测{match[2]}（文件来源）', 'export_label_not_hardware_id'


def ingest_project(root=None, profile=None):
    root = allowed_path(root or MATERIAL_ROOT / '03_地块与监测数据/raw')
    profile = profile or load_profile()
    init_db()
    reports = []
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _register_plot(conn, profile)
        for spec in profile['sources']:
            version = spec['data_version']
            paths = sorted(root.glob(spec['file_glob']))
            if not paths:
                reports.append({'source': spec['kind'], 'missing_file': spec['file_glob']})
            for path in paths:
                path = allowed_path(path)
                if not path.is_relative_to(root):
                    raise ValueError('source_outside_raw')
                digest = sha256_file(path)
                fid = 'rf_' + _digest([digest, version])
                previous = conn.execute('SELECT sha256 FROM raw_files WHERE path=? AND data_version=?', (str(path), version)).fetchone()
                if previous and previous['sha256'] != digest:
                    raise ValueError('原文件已变化，请使用新数据版本：' + path.name)
                if conn.execute('SELECT 1 FROM raw_files WHERE file_id=?', (fid,)).fetchone():
                    reports.append({'file': path.name, 'status': 'already_imported', 'sha256': digest})
                    continue
                if conn.execute('SELECT 1 FROM data_versions WHERE data_version=?', (version,)).fetchone():
                    raise ValueError('冻结版本不可修改：' + version)
                frame = next(iter(read_tables(path).values()))
                required = {'参数名称', '参数数值', '参数单位'} | ({'日期','时间','设备编号','参数标识'} if spec['kind']=='puer' else {'记录时间'})
                if not required.issubset(frame.columns):
                    raise ValueError('未知列结构：' + path.name)
                if '参数标识' not in frame and '端口名称' not in frame:
                    raise ValueError('缺参数标识或已核对的端口名称列：'+path.name)
                conn.execute('INSERT INTO raw_files VALUES (?,?,?,?,?,?,?)', (fid, str(path), digest, len(frame), now_iso(), version, 'observation'))
                counts = Counter(read=len(frame), imported=0, duplicate=0, conflict=0, rejected=0, blank=0)
                flags = Counter()
                pending = {}
                rejections = []
                sources = {}
                # itertuples avoids expensive per-row dataframe allocations.
                for line, values in enumerate(frame.itertuples(index=False, name=None), 2):
                    row = dict(zip(frame.columns, values))
                    if not any(str(v).strip() for v in values):
                        counts['blank'] += 1
                        continue
                    try:
                        code = str(row.get('参数标识','')).strip()
                        if '参数标识' not in row:
                            code = profile['environment_name_codes'].get(str(row['参数名称']).strip(), '')
                        definition = profile['parameters'].get(code)
                        if definition is None:
                            raise ValueError('unknown_parameter_code')
                        device, label, identity = _source(spec['kind'], path, row)
                        text = str(row['日期'])+' '+str(row['时间']) if spec['kind']=='puer' else str(row['记录时间'])
                        pattern = '%Y/%m/%d %H:%M:%S' if spec['kind']=='puer' else '%Y/%m/%d %H:%M'
                        try:
                            dt = _ts(text, pattern)
                        except (ValueError, TypeError):
                            raise ValueError('invalid_timestamp')
                    except ValueError as error:
                        rejections.append((fid, line, str(error), json.dumps(row, ensure_ascii=False)))
                        counts['rejected'] += 1
                        continue
                    sources[device] = (label, identity)
                    raw = str(row['参数数值']).strip()
                    unit = str(row['参数单位']).strip()
                    flag = 'ok'
                    try:
                        value = float(raw) if raw else None
                        if value is not None and not math.isfinite(value):
                            value = None
                            flag = 'invalid_numeric'
                    except ValueError:
                        value = None
                        flag = 'invalid_numeric'
                    if value is None and flag == 'ok':
                        flag = 'missing'
                    if flag == 'ok' and not unit:
                        flag = 'missing_unit'
                    elif flag == 'ok' and unit not in definition['units']:
                        flag = 'unit_mismatch'
                    limits = definition.get('range')
                    if flag == 'ok' and limits and not limits[0] <= value <= limits[1]:
                        flag = 'out_of_range'
                    parameter = definition['parameter']
                    key = (device, dt.isoformat(), parameter)
                    oid = 'obs_' + _digest([fid, line, device, dt.isoformat(), parameter])
                    record = (oid, profile['plot_id'], device, dt.isoformat(), dt.date().isoformat(), parameter,
                              None, raw, value, unit, fid, line, flag, version, 0)
                    prior = pending.get(key)
                    if prior is None:
                        prior = conn.execute('SELECT * FROM obs_long WHERE device_id=? AND ts=? AND parameter=? AND depth_cm IS NULL AND data_version=?', (*key, version)).fetchone()
                    if prior is not None:
                        # Keep the first source row; retain all alternative rows in the audit table.
                        same = prior[8] == value and prior[9] == unit and prior[7] == raw
                        reason = 'exact_duplicate' if same else 'duplicate_conflict'
                        counts['duplicate' if same else 'conflict'] += 1
                        rejections.append((fid, line, reason, json.dumps(row, ensure_ascii=False)))
                        if not same:
                            if key in pending:
                                older = list(pending[key]); older[12] = 'duplicate_conflict'; pending[key] = tuple(older)
                            else:
                                conn.execute("UPDATE obs_long SET qc_flag='duplicate_conflict' WHERE obs_id=?", (prior[0],))
                        continue
                    pending[key] = record
                conn.executemany('INSERT INTO obs_long VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', pending.values())
                conn.executemany('INSERT INTO import_rejections VALUES (?,?,?,?)', rejections)
                for device, (label, identity) in sources.items():
                    conn.execute('INSERT OR IGNORE INTO observation_sources VALUES (?,?,?,?,?)', (device, label, spec['location'], identity, json.dumps(profile['missing_fields'], ensure_ascii=False)))
                    if not conn.execute('SELECT 1 FROM device_plot_map WHERE device_id=? AND plot_id=?', (device,profile['plot_id'])).fetchone():
                        conn.execute('INSERT INTO device_plot_map VALUES (?,?,NULL,NULL,NULL)', (device, profile['plot_id']))
                counts['imported'] = len(pending)
                flags.update(r[12] for r in pending.values())
                assert counts['read'] == sum(counts[k] for k in ('imported','duplicate','conflict','rejected','blank'))
                reports.append(dict(file=path.name, sha256=digest, data_version=version, status='imported', **counts, qc_flags=dict(flags)))
    return dict(plot_id=profile['plot_id'], frozen=False, profile_version=profile['profile_version'], missing_fields=profile['missing_fields'], files=reports)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = ingest_project(args.root)
    out = allowed_path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'plot_id':result['plot_id'], 'files':len(result['files']), 'counts':dict(sum((Counter({k:f.get(k,0) for k in ('read','imported','duplicate','conflict','rejected','blank')}) for f in result['files']),Counter()))},ensure_ascii=False))
