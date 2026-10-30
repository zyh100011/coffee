"""Export reproducible tool facts, never reference answers or formal test material."""
import argparse
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from database.init_db import get_connection
from services.data_service import query
from tools.material_paths import MATERIAL_ROOT, allowed_path, sha256_file

CASE_FILES = ('case_baseline_0mm.json', 'case_irrig_20mm.json',
              'case_missing_input.json', 'case_engine_failed.json')


def hydrus_cases(directory):
    cases = []
    for name, expected in zip(CASE_FILES, ('success', 'success', 'missing_input', 'failed')):
        path = allowed_path(Path(directory) / name)
        result = json.loads(path.read_text(encoding='utf-8-sig'))
        if result['status'] != expected or result['source_type'] != 'simulation_uncalibrated':
            raise ValueError('HYDRUS 案例状态或来源不符合契约：' + name)
        cases.append({'case_id': name[:-5], 'input_label': '假设输入，未校准',
                      'file_sha256': sha256_file(path), 'result': result})
    return cases


def frozen_snapshot(version):
    with get_connection() as conn:
        frozen = conn.execute('SELECT * FROM data_versions WHERE data_version=?', (version,)).fetchone()
        files = conn.execute('SELECT * FROM raw_files WHERE data_version=?', (version,)).fetchall()
        if not frozen or not files or any(r['source_type'] != 'observation' for r in files):
            raise ValueError('缺少非空冻结实测版本 ' + version + '；请先完成 H3/H4，禁止导出虚构正式案例')
        hashes = {r['file_id']: r['sha256'] for r in files}
        if hashes != json.loads(frozen['file_hashes_json']):
            raise ValueError('冻结文件清单发生变化')
        for row in files:
            if sha256_file(row['path']) != row['sha256']:
                raise ValueError('原文件哈希发生变化')
        count = conn.execute("SELECT COUNT(*) FROM obs_long WHERE data_version=? AND value IS NOT NULL AND qc_flag IN ('ok','rain_reset')", (version,)).fetchone()[0]
        if not count or count != json.loads(frozen['row_counts_json'])['obs_long']:
            raise ValueError('冻结有效行数发生变化')
        groups = [dict(r) for r in conn.execute('''SELECT plot_id,parameter,depth_cm,device_id,unit,
            MIN(date) start,MAX(date) end FROM obs_long
            WHERE data_version=? AND value IS NOT NULL AND qc_flag IN ('ok','rain_reset')
            AND device_id IS NOT NULL AND device_id!='' AND unit IS NOT NULL
            GROUP BY plot_id,parameter,depth_cm,device_id,unit
            ORDER BY plot_id,parameter,depth_cm,device_id,unit''', (version,))]
    return dict(frozen), groups


def select_queries(groups, version):
    # Round-robin groups first so plots/depths are represented before more windows.
    candidates = []
    for g in groups:
        first, last = date.fromisoformat(g['start']), date.fromisoformat(g['end'])
        windows = [(max(first, last-timedelta(days=365)), last), (first, first),
                   (last, last), (max(first,last-timedelta(days=6)),last),
                   (max(first,last-timedelta(days=29)),last),
                   (first, min(last,first+timedelta(days=6))),
                   (max(first,last-timedelta(days=365)),last+timedelta(days=1))]
        # Keep real gaps inside populated windows; empty queries are not positive cases.
        with get_connection() as conn:
            valid = {r[0] for r in conn.execute("SELECT DISTINCT date FROM obs_long WHERE plot_id=? AND parameter=? AND depth_cm IS ? AND device_id=? AND unit=? AND data_version=? AND value IS NOT NULL AND qc_flag IN ('ok','rain_reset')", (g['plot_id'],g['parameter'],g['depth_cm'],g['device_id'],g['unit'],version))}
        windows.extend((date.fromisoformat(day),date.fromisoformat(day)) for day in sorted(valid))
        items = []
        for start,end in windows:
            if (end-start).days > 365: continue
            if not any(start.isoformat() <= day <= end.isoformat() for day in valid): continue
            for agg in ('raw','daily_mean'):
                args = {k:g[k] for k in ('plot_id','parameter','depth_cm','device_id','unit')}
                args.update(start=start.isoformat(),end=end.isoformat(),agg=agg,data_version=version)
                if args not in items: items.append(args)
        candidates.append(items)
    selected = []
    for i in range(max((len(x) for x in candidates),default=0)):
        for items in candidates:
            if i < len(items) and items[i] not in selected: selected.append(items[i])
            if len(selected) == 20: return selected
    raise ValueError(f'真实数据可选独立查询只有 {len(selected)} 条，不足 20 条；请补充真实覆盖范围')


def export(destination, version='data-v1.0', hydrus_only=False, case_dir=None):
    destination = allowed_path(destination)
    package = {'schema_version':'verifiable-zyh-v1','status':'partial' if hydrus_only else 'ready',
               'note':'工具数值与查询条件，非参考答案；HYDRUS 为未校准假设情景',
               'data_version':None if hydrus_only else version,
               'missing_fields':['frozen_observations_20_cases'] if hydrus_only else [],
               'data_cases':[], 'hydrus_cases':hydrus_cases(case_dir or BACKEND/'data'/'hydrus_cases')}
    if not hydrus_only:
        snapshot,groups = frozen_snapshot(version)
        package['freeze_manifest'] = snapshot
        package['coverage'] = {'plots':sorted({g['plot_id'] for g in groups}),
            'parameter_depth_pairs':[{'parameter':g['parameter'],'depth_cm':g['depth_cm']} for g in groups],
            'sources':[{k:g[k] for k in ('plot_id','parameter','depth_cm','device_id','unit')} for g in groups]}
        for args in select_queries(groups,version):
            digest = hashlib.sha256(json.dumps(args,sort_keys=True).encode()).hexdigest()[:20]
            result = query(args, {'task_id':'verify_'+digest})
            result['evidence_id'] = 'ev_data_query_verify_'+digest
            result['created_at'] = snapshot['created_at']
            if result['status'] != 'success' or result['source_type'] != 'observation' or result.get('outputs',{}).get('n',0) <= 0:
                raise ValueError('实测案例查询未成功，拒绝标记就绪：' + digest)
            repeated = query(args, {'task_id':'verify_'+digest})
            if any(result[k] != repeated[k] for k in ('status','source_type','parameter_version','inputs','outputs','units','missing_fields','warnings')):
                raise ValueError('案例重复执行不一致：' + digest)
            sql = 'SELECT o.* FROM obs_long o WHERE o.plot_id=? AND o.parameter=? AND o.date BETWEEN ? AND ? AND o.data_version=?'
            params = [args[k] for k in ('plot_id','parameter','start','end','data_version')]
            if args['depth_cm'] is not None: sql += ' AND o.depth_cm=?'; params.append(args['depth_cm'])
            sql += ' AND o.device_id=? AND o.unit=?'
            params.extend([args['device_id'],args['unit']])
            sql += " AND o.value IS NOT NULL AND o.qc_flag IN ('ok','rain_reset') ORDER BY o.ts,o.obs_id"
            package['data_cases'].append({'case_id':'data_'+digest,'query':args,
                'reproduce':{'call':'services.data_service.query(query)','sql':sql,'parameters':params,
                    'value_transform':result['inputs'].get('conversion')},'result':result})
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(package,ensure_ascii=False,indent=2),encoding='utf-8')
    return package


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=MATERIAL_ROOT/'04_三模型工具资料'/'可核验案例_zyh.json')
    parser.add_argument('--version',default='data-v1.0')
    parser.add_argument('--hydrus-only',action='store_true',help='明确的部分包；不声称有20条正式数据案例')
    args = parser.parse_args()
    try:
        p = export(args.out,args.version,args.hydrus_only)
        print(json.dumps({'status':p['status'],'data_cases':len(p['data_cases']),'hydrus_cases':len(p['hydrus_cases']),'missing_fields':p['missing_fields']},ensure_ascii=False))
    except (ValueError,KeyError,OSError) as error:
        print(str(error)); sys.exit(1)
