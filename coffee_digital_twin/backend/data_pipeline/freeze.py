"""Freeze confirmed, nonempty observed versions; refuse fixtures and later mutation."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database.init_db import get_connection,now_iso
from tools.material_paths import sha256_file


def freeze(version):
    with get_connection() as conn:
        if conn.execute('SELECT 1 FROM data_versions WHERE data_version=?',(version,)).fetchone(): raise ValueError('版本已冻结')
        files=conn.execute('SELECT * FROM raw_files WHERE data_version=?',(version,)).fetchall()
        count=conn.execute("SELECT COUNT(*) FROM obs_long WHERE data_version=? AND value IS NOT NULL AND qc_flag IN ('ok','rain_reset')",(version,)).fetchone()[0]
        if not files or not count or any(r['source_type']!='observation' for r in files): raise ValueError('无非空已确认实测，不能冻结空版本或测试数据')
        for row in files:
            if sha256_file(row['path'])!=row['sha256']: raise ValueError('原文件哈希变化')
        conn.execute('INSERT INTO data_versions VALUES (?,?,?,?,?)',(version,now_iso(),json.dumps({r['file_id']:r['sha256'] for r in files}),json.dumps({'obs_long':count}),'冻结实测；后续修改需新版本'))
    return version

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--version',required=True); args=parser.parse_args()
    try: print(freeze(args.version))
    except ValueError as error: print(str(error)); sys.exit(1)
