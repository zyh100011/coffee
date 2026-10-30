"""Import reviewed team materials without mixing gridded weather into observations."""
import csv
import hashlib
import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path

from database.init_db import get_connection, now_iso
from tools.material_paths import REPO_ROOT, allowed_path, sha256_file

DELIVERY = REPO_ROOT / 'JGY内容'
GROUPS = ('01-A4-LAI冠层与遮阴', '02-A5-气候与气象驱动',
          '03-B1-咖啡基地条件卡', '05-BEPS-Lite工具说明')
PLOT = 'plot_catimor_project'
DAILY = '02-A5-气候与气象驱动/04_标准化数据与质控/A5-06_白沙坡_标准化逐日气象数据_2006-2025.csv'
HOURLY = '02-A5-气候与气象驱动/04_标准化数据与质控/A5-06_白沙坡_标准化逐小时气象数据_2024.csv'
FIELDS = {
    'daily': {'tavg': ('Tmean_C', '°C'), 'tmin': ('Tmin_C', '°C'), 'tmax': ('Tmax_C', '°C'),
              'rain_mm': ('precipitation_mm_day', 'mm/day'),
              'radiation_mj': ('solar_radiation_MJ_m2_day', 'MJ/m²/day'),
              'wind_10m_ms': ('wind_speed_10m_m_s', 'm/s'), 'rh': ('RHmean_pct', '%')},
    'hourly': {'tavg': ('Tair_C', '°C'), 'rain_mm': ('precipitation_mm_hour', 'mm/hour'),
               'radiation_mj': ('solar_radiation_MJ_m2_hour', 'MJ/m²/hour'),
               'wind_10m_ms': ('wind_speed_10m_m_s', 'm/s'), 'rh': ('RH_pct', '%')},
}
WARNINGS = ['NASA POWER网格气象产品，不是基地现场实测；LST不是北京时间',
            '历史数据仅按原日期查询，不替代当前天气，不自动补入HYDRUS降雨',
            '1225.24米为来源网格高程，不替换基地1050米；10米风速不冒充2米风速']


def init_schema(conn):
    conn.executescript('''
      CREATE TABLE IF NOT EXISTS team_materials(
        path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, size INTEGER NOT NULL, category TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS gridded_weather(
        plot_id TEXT NOT NULL, resolution TEXT NOT NULL, ts TEXT NOT NULL, date TEXT NOT NULL,
        source_path TEXT NOT NULL, source_sha256 TEXT NOT NULL, source_row INTEGER NOT NULL,
        data_json TEXT NOT NULL, PRIMARY KEY(plot_id,resolution,ts));
      CREATE TABLE IF NOT EXISTS team_imports(
        import_id TEXT PRIMARY KEY, imported_at TEXT NOT NULL, report_json TEXT NOT NULL);
    ''')


def parse_weather(path, resolution, source_path):
    """Validate the whole file before replacing its previous import, preserving raw rows."""
    digest = sha256_file(path)
    records, seen = [], set()
    with path.open(encoding='utf-8-sig', newline='') as stream:
        for line, raw in enumerate(csv.DictReader(stream), 2):
            dt = datetime.strptime(raw['date_LST'], '%Y/%m/%d')
            if resolution == 'hourly':
                hour = int(raw['hour_LST'])
                if not 0 <= hour <= 23:
                    raise ValueError('invalid hour')
                dt = dt.replace(hour=hour)
            ts = dt.isoformat(timespec='seconds')
            if ts in seen or (records and dt - previous != timedelta(days=1) / (24 if resolution == 'hourly' else 1)):
                raise ValueError('duplicate or discontinuous weather timestamps')
            seen.add(ts); previous = dt
            values = {}
            for key, (field, unit) in FIELDS[resolution].items():
                value = float(raw[field])
                if not math.isfinite(value) or value == -999:
                    raise ValueError('missing/nonfinite weather value: ' + field)
                values[key] = value
            if values['rain_mm'] < 0 or values['radiation_mj'] < 0 or values['wind_10m_ms'] < 0 or not 0 <= values['rh'] <= 100:
                raise ValueError('out-of-range weather value')
            if resolution == 'daily' and not values['tmin'] <= values['tmax']:
                raise ValueError('invalid temperature range')
            if raw['time_standard'] != 'LST' or abs(float(raw['latitude_deg'])-22.6347) > .0001 or abs(float(raw['longitude_deg'])-101.0027) > .0001:
                raise ValueError('unexpected weather location/time standard')
            payload = {'values': values, 'raw': raw, 'time_standard': 'LST',
                       'timestamp_processing': 'date_LST+hour_LST' if resolution == 'hourly' else 'date_LST'}
            records.append((PLOT, resolution, ts, dt.date().isoformat(), source_path, digest, line,
                            json.dumps(payload, ensure_ascii=False)))
    if not records:
        raise ValueError('empty weather file')
    return records


def ingest(root=DELIVERY):
    root = allowed_path(root)
    materials = []
    # Explicit directory allowlist: question sets and expert reference answers are excluded.
    for group in GROUPS:
        folder = allowed_path(root / group)
        for p in sorted(folder.rglob('*')):
            if not p.is_file():
                continue
            p = allowed_path(p)
            if not p.is_relative_to(folder):
                raise ValueError('material outside allowed directory')
            relative = str(p.relative_to(root)).replace('\\', '/')
            materials.append((relative, sha256_file(p), p.stat().st_size, group))
    datasets = {res: parse_weather(allowed_path(root / name), res, name)
                for res, name in [('daily', DAILY), ('hourly', HOURLY)]}
    version = 'jgy-' + hashlib.sha256(json.dumps(materials, ensure_ascii=False).encode()).hexdigest()[:16]
    report = {'import_id': version, 'materials': len(materials),
              'weather_rows': {res: len(records) for res, records in datasets.items()},
              'knowledge_ingested': False, 'expert_evaluation_completed': False,
              'lai_used': False, 'warnings': WARNINGS}
    with get_connection() as conn:
        if not conn.execute('SELECT 1 FROM plots WHERE plot_id=?', (PLOT,)).fetchone():
            raise ValueError('target plot does not exist; import confirmed base profile first')
        conn.execute('DELETE FROM team_materials')
        conn.executemany('INSERT INTO team_materials VALUES (?,?,?,?)', materials)
        for res, records in datasets.items():
            conn.execute('DELETE FROM gridded_weather WHERE plot_id=? AND resolution=?', (PLOT, res))
            conn.executemany('INSERT INTO gridded_weather VALUES (?,?,?,?,?,?,?,?)', records)
        conn.execute('INSERT OR REPLACE INTO team_imports VALUES (?,?,?)', (version, now_iso(), json.dumps(report, ensure_ascii=False)))
    return report


def material_status():
    with get_connection() as conn:
        items = [dict(r) for r in conn.execute('SELECT * FROM team_materials ORDER BY path')]
        imports = [json.loads(r['report_json']) for r in conn.execute('SELECT report_json FROM team_imports ORDER BY imported_at DESC LIMIT 1')]
    return {'status': 'success', 'items': items, 'latest_import': imports[0] if imports else None,
            'knowledge_ingested': False, 'note': '资料可交蔡济远入库；清单不代表已完成RAG检索或人工证据复核'}


def weather_catalog(plot_id):
    with get_connection() as conn:
        rows = conn.execute('''SELECT resolution,COUNT(*) n,MIN(date) start,MAX(date) end,
            MIN(source_sha256) source_sha256 FROM gridded_weather WHERE plot_id=? GROUP BY resolution''', (plot_id,)).fetchall()
    return {'status': 'success', 'plot_id': plot_id, 'source_type': 'gridded_reanalysis',
            'items': [{**dict(r), 'parameters': [{'key': k, 'unit': v[1]} for k,v in FIELDS[r['resolution']].items()]} for r in rows],
            'warnings': WARNINGS}


def weather_query(args):
    if not isinstance(args, dict) or not isinstance(args.get('plot_id'), str) or not args['plot_id']:
        raise ValueError('plot_id required')
    resolution = args.get('resolution', 'daily')
    if resolution not in FIELDS:
        raise ValueError('invalid resolution')
    start, end = date.fromisoformat(args['start']), date.fromisoformat(args['end'])
    if not 0 <= (end-start).days <= (30 if resolution == 'hourly' else 365):
        raise ValueError('invalid date window')
    with get_connection() as conn:
        rows = conn.execute('''SELECT * FROM gridded_weather WHERE plot_id=? AND resolution=?
            AND date BETWEEN ? AND ? ORDER BY ts''', (args['plot_id'],resolution,start.isoformat(),end.isoformat())).fetchall()
    items = []
    for r in rows:
        payload = json.loads(r['data_json'])
        items.append({'ts': r['ts'], 'date': r['date'], **payload['values'], 'source_path': r['source_path'],
                      'source_sha256': r['source_sha256'], 'source_row': r['source_row']})
    return {'status': 'success' if items else 'missing_input', 'plot_id': args['plot_id'],
            'source_type': 'gridded_reanalysis', 'source_label': 'NASA POWER历史网格气象',
            'resolution': resolution, 'time_standard': 'LST', 'items': items,
            'units': {k: v[1] for k,v in FIELDS[resolution].items()},
            'missing_fields': [] if items else ['historical_weather_in_requested_window'], 'warnings': WARNINGS}
