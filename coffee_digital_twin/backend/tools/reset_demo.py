"""Reversible demo reset. Preview by default; archive data and runtime before replacement."""
import argparse
from contextlib import closing
from datetime import datetime
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.material_paths import allowed_path, REPO_ROOT
from tools.seed_demo import import_frozen
from tools.export_traces import redact


def reset(snapshot, database, runtime, archive_root, workspace, apply=False,
          raw_root=None, team_root=None, service_port=5000):
    workspace = allowed_path(workspace)
    snapshot, database, runtime, archive_root = [allowed_path(p) for p in
                                               (snapshot, database, runtime, archive_root)]
    for path in (snapshot, database, runtime, archive_root):
        if path == workspace or not path.is_relative_to(workspace):
            raise ValueError('重置目标必须位于指定工作区内，不能是工作区本身')
    if (snapshot == database or snapshot.is_relative_to(runtime) or database.is_relative_to(runtime)
            or archive_root.is_relative_to(runtime) or runtime.is_relative_to(archive_root)
            or archive_root == database or runtime == database):
        raise ValueError('快照、数据库、运行目录和归档路径不能重叠')
    if not snapshot.is_file() or not database.is_file():
        raise ValueError('冻结快照或当前数据库不存在')
    archive = archive_root / ('reset_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    plan = {'applied': False, 'snapshot': str(snapshot), 'database': str(database),
            'runtime': str(runtime), 'archive': str(archive),
            'note': '预览；-Apply前停止后端。先备份和导出轨迹，再归档runtime并恢复冻结快照，不删除旧数据'}
    if not apply:
        return plan
    try:
        with socket.create_connection(('127.0.0.1', service_port), timeout=.5):
            raise ValueError('后端端口仍在使用；请先停止服务再重置')
    except OSError:
        pass
    # Explicitly check write locks before opening archive files.
    with closing(sqlite3.connect(database, timeout=1)) as current:
        current.execute('BEGIN EXCLUSIVE'); current.rollback()
    archive.mkdir(parents=True, exist_ok=False)
    with closing(sqlite3.connect(database)) as current, closing(sqlite3.connect(archive/'before_reset.db')) as backup:
        current.backup(backup)
        current.row_factory = sqlite3.Row
        tables = {r[0] for r in current.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        with (archive/'assistant_traces.jsonl').open('w', encoding='utf-8') as out:
            if 'assistant_traces' in tables:
                for row in current.execute('SELECT * FROM assistant_traces ORDER BY created_at,trace_id'):
                    out.write(json.dumps(redact(dict(row)), ensure_ascii=False)+'\n')
    staged = archive/'restored.db'
    imported = import_frozen(snapshot, staged, 'data-v1.0', raw_root, team_root)
    runtime_archive = archive/'runtime'
    moved_runtime = False
    moved_database = False
    try:
        if runtime.exists():
            runtime.rename(runtime_archive); moved_runtime = True
        # Preserve SQLite sidecars as well, after a checkpoint and closure.
        with closing(sqlite3.connect(database)) as current:
            current.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        database.rename(archive/'original.db'); moved_database = True
        for suffix in ('-wal', '-shm', '-journal'):
            sidecar = Path(str(database)+suffix)
            if sidecar.exists(): sidecar.rename(archive/('original.db'+suffix))
        os.replace(staged, database)
    except Exception:
        if moved_database and not database.exists():
            (archive/'original.db').rename(database)
            for suffix in ('-wal', '-shm', '-journal'):
                sidecar = archive/('original.db'+suffix)
                if sidecar.exists(): sidecar.rename(Path(str(database)+suffix))
        if moved_runtime and not runtime.exists(): runtime_archive.rename(runtime)
        raise
    plan.update(applied=True, imported=imported,
                note='重置完成；旧数据库、轨迹和runtime全部归档。启动时重建空runtime；需重新运行selfcheck')
    (archive/'reset_manifest.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--service-port', type=int, default=5000)
    args = parser.parse_args()
    import config
    try:
        print(json.dumps(reset(config.SERVER_DIR/'backup/frozen/data-v1.0.db', config.DATABASE_PATH,
            config.RUNTIME_DIR, REPO_ROOT/'实验资料/07_实验结果/demo_reset', REPO_ROOT, args.apply,
            team_root=REPO_ROOT/'JGY内容' if (REPO_ROOT/'JGY内容').is_dir() else None,
            service_port=args.service_port), ensure_ascii=False, indent=2))
    except (ValueError, OSError, sqlite3.Error) as error:
        print('拒绝或未完成重置：'+str(error)); sys.exit(1)
