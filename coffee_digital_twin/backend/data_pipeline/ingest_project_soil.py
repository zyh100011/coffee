"""Retain report sample identity and missing sampling date/depth separately."""
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database.init_db import get_connection, init_db, now_iso
from data_pipeline.ingest_project_raw import _digest
from tools.material_paths import MATERIAL_ROOT, allowed_path, sha256_file


def ingest_report(profile=None, material_root=None):
    profile = profile or json.loads(Path(__file__).with_name('soil_report_2026T108.json').read_text(encoding='utf-8'))
    path = allowed_path((material_root or MATERIAL_ROOT) / profile['source_path'])
    digest = sha256_file(path)
    fid = 'rf_' + _digest([digest, profile['data_version']])
    ids = [s['lab_sample_id'] for s in profile['samples']]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate_lab_sample_id')
    for sample in profile['samples']:
        if len(sample['values']) != len(profile['items']) or any(isinstance(v,bool) or not math.isfinite(float(v)) for v in sample['values']):
            raise ValueError('invalid_report_row')
    init_db()
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT 1 FROM plots WHERE plot_id=?', (profile['plot_id'],)).fetchone():
            raise ValueError('先导入项目档案')
        if conn.execute('SELECT 1 FROM raw_files WHERE file_id=?', (fid,)).fetchone():
            return {'status':'already_imported','samples':len(ids),'results':len(ids)*len(profile['items'])}
        if conn.execute('SELECT 1 FROM raw_files WHERE path=? AND data_version=?', (str(path),profile['data_version'])).fetchone():
            raise ValueError('报告原文件变化，请使用新版本')
        if conn.execute('SELECT 1 FROM data_versions WHERE data_version=?', (profile['data_version'],)).fetchone():
            raise ValueError('冻结版本不可修改')
        conn.execute('INSERT INTO raw_files VALUES (?,?,?,?,?,?,?)', (fid,str(path),digest,len(ids),now_iso(),profile['data_version'],'observation'))
        for sample in profile['samples']:
            for item,value in zip(profile['items'],sample['values']):
                rid = 'lab_' + _digest([fid,sample['lab_sample_id'],item['key']])
                conn.execute('INSERT INTO soil_lab_results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                             (rid,profile['plot_id'],sample['sample_label'],sample['lab_sample_id'],item['label'],value,item['unit'],item['method'],profile['sample_date'],profile['received_date'],profile['report_date'],profile['depth_top_cm'],profile['depth_bottom_cm'],fid,profile['source_page']))
    return {'status':'imported','samples':len(ids),'results':len(ids)*len(profile['items']), 'sha256':digest, 'missing_fields':profile['missing_fields']}


if __name__ == '__main__':
    print(json.dumps(ingest_report(),ensure_ascii=False))
