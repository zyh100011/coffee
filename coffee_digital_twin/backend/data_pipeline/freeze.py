"""Freeze a release from existing observed versions, preserving original lineage."""
import argparse
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database import init_db as db
from database.init_db import get_connection,now_iso
from tools.material_paths import allowed_path,sha256_file


def freeze(version, source_versions=None, backup=None):
    if not version or not version.strip(): raise ValueError('版本不能为空')
    sources=list(dict.fromkeys(source_versions or [version]))
    if source_versions:
        if version in sources: raise ValueError('发布版本不能同时作为源版本')
        backup=allowed_path(backup or Path(db.DATABASE_PATH).parent/'freeze_backups'/('before_freeze_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.db'))
        if backup.exists() or backup==allowed_path(db.DATABASE_PATH): raise ValueError('备份路径已经存在或与源库相同')
        backup.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(allowed_path(db.DATABASE_PATH).as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(backup)) as dst:src.backup(dst)
    with closing(get_connection()) as conn:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('SELECT 1 FROM data_versions WHERE data_version=?',(version,)).fetchone(): raise ValueError('版本已冻结')
            files=[]
            for source in sources:
                if source_versions and conn.execute('SELECT 1 FROM data_versions WHERE data_version=?',(source,)).fetchone(): raise ValueError('源版本已冻结，不重标冻结来源')
                current=conn.execute('SELECT * FROM raw_files WHERE data_version=?',(source,)).fetchall()
                if not current: raise ValueError('源版本不存在：'+source)
                files.extend(current)
            if source_versions and (conn.execute('SELECT 1 FROM raw_files WHERE data_version=?',(version,)).fetchone() or conn.execute('SELECT 1 FROM obs_long WHERE data_version=?',(version,)).fetchone()): raise ValueError('目标版本已存在，拒绝合并')
            marks=','.join('?' for _ in sources)
            count=conn.execute("SELECT COUNT(*) FROM obs_long WHERE data_version IN ("+marks+") AND value IS NOT NULL AND qc_flag IN ('ok','rain_reset')",sources).fetchone()[0]
            if not files or not count or any(r['source_type']!='observation' for r in files): raise ValueError('无非空已确认实测，不能冻结空版本或测试数据')
            for row in files:
                if sha256_file(row['path'])!=row['sha256']: raise ValueError('原文件哈希变化')
            if source_versions:
                conn.executemany('INSERT INTO data_release_sources VALUES (?,?,?,?)',[(version,r['file_id'],r['data_version'],r['sha256']) for r in files])
                conn.execute('UPDATE obs_long SET data_version=? WHERE data_version IN ('+marks+')',[version,*sources])
                conn.execute('UPDATE raw_files SET data_version=? WHERE data_version IN ('+marks+')',[version,*sources])
            conn.execute('INSERT INTO data_versions VALUES (?,?,?,?,?)',(version,now_iso(),json.dumps({r['file_id']:r['sha256'] for r in files}),json.dumps({'obs_long':count}),'冻结实测；源版本保存在data_release_sources；后续修改需新版本'))
    return version

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--version',required=True)
    parser.add_argument('--source-version',action='append',help='已有未冻结版本，可重复指定；先备份，再登记发布版本')
    parser.add_argument('--backup',type=Path)
    args=parser.parse_args()
    try: print(freeze(args.version,args.source_version,args.backup))
    except (ValueError,OSError,sqlite3.Error) as error:print(str(error));sys.exit(1)
