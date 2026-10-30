"""Relink moved raw files by exact SHA256, without changing observations or versions."""
import argparse
from collections import defaultdict
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database import init_db as db
from config import RUNTIME_DIR
from tools.material_paths import MATERIAL_ROOT,allowed_path,sha256_file


def relink(root=None, apply=False):
    root=allowed_path(root or MATERIAL_ROOT/'03_地块与监测数据/raw')
    if not root.is_dir(): raise ValueError('原始资料目录不存在')
    with closing(sqlite3.connect(allowed_path(db.DATABASE_PATH).as_uri()+'?mode=ro',uri=True)) as conn:
        conn.row_factory=sqlite3.Row
        registered=[dict(r) for r in conn.execute('SELECT file_id,path,sha256 FROM raw_files')]
    candidates=defaultdict(list)
    for path in sorted(root.rglob('*')):
        if not path.is_file(): continue
        resolved=allowed_path(path)
        if not resolved.is_relative_to(root): raise ValueError('原始资料路径越出指定目录')
        candidates[sha256_file(resolved)].append(str(resolved))
    changes=[]
    for row in registered:
        original=allowed_path(row['path'])
        if original.is_file():
            if sha256_file(original)!=row['sha256']: raise ValueError('已登记原文件内容变化，拒绝替换')
            continue
        matches=candidates.get(row['sha256'],[])
        if len(matches)!=1: raise ValueError('原文件哈希未唯一匹配：'+row['file_id'])
        changes.append({**row,'new_path':matches[0]})
    backup=None
    if apply and changes:
        backup=RUNTIME_DIR/'raw_review'/('before_source_relink_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.db')
        backup.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(db.DATABASE_PATH)) as src,closing(sqlite3.connect(backup)) as dst:
            src.backup(dst)
        with closing(db.get_connection()) as conn:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                for row in changes:
                    if sha256_file(row['new_path'])!=row['sha256']: raise ValueError('匹配后原文件内容变化')
                    updated=conn.execute('UPDATE raw_files SET path=? WHERE file_id=? AND path=? AND sha256=?',
                        (row['new_path'],row['file_id'],row['path'],row['sha256']))
                    if updated.rowcount!=1: raise ValueError('来源登记已变化，事务回滚')
    return {'applied':apply,'changes':changes,'backup':str(backup) if backup else None,
            'observations_modified':False,'versions_modified':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path)
    parser.add_argument('--apply',action='store_true',help='默认仅预览；指定后备份并更新来源路径')
    args=parser.parse_args()
    print(json.dumps(relink(args.root,args.apply),ensure_ascii=False,indent=2))
