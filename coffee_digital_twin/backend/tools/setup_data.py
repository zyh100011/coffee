"""Prepare an empty installation from a verified snapshot; never replace existing data."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contextlib import closing
import config
from database import init_db as db
from tools.seed_demo import import_frozen
from tools.selfcheck import inspect_database


def prepare(snapshot, raw_root=None, team_root=None):
    db.init_db()
    with closing(db.get_connection()) as conn:
        populated = any(conn.execute('SELECT 1 FROM '+name+' LIMIT 1').fetchone()
                        for name in ('plots', 'raw_files', 'obs_long'))
    if populated:
        if not inspect_database(db.DATABASE_PATH, 'data-v1.0')[1]:
            raise ValueError('已有数据库未通过冻结校验；保留原库，请核查，不自动覆盖')
        result = {'status': 'preserved_existing', 'data_version': 'data-v1.0'}
    else:
        result = import_frozen(snapshot, db.DATABASE_PATH, 'data-v1.0', raw_root, team_root)
    env = config.BASE_DIR / '.env'
    text = env.read_text(encoding='utf-8-sig')
    lines = text.splitlines()
    version_lines = [i for i, line in enumerate(lines) if line.strip().startswith('DATA_VERSION=')]
    if len(version_lines) > 1:
        raise ValueError('DATA_VERSION重复，请人工核查；未输出.env内容')
    if version_lines:
        index = version_lines[0]
        value = lines[index].split('=', 1)[1].strip().strip('\"\'')
        if value not in ('', 'data-v1.0'):
            raise ValueError('已有DATA_VERSION与安装快照不同；保留配置')
        lines[index] = 'DATA_VERSION=data-v1.0'
    else:
        lines.append('DATA_VERSION=data-v1.0')
    env.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--raw-root', type=Path)
    parser.add_argument('--team-root', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.snapshot, args.raw_root, args.team_root), ensure_ascii=False))
    except (ValueError, OSError) as error:
        print('安装数据未就绪：'+str(error)); sys.exit(1)
