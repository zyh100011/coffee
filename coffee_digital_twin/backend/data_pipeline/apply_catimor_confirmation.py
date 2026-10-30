"""Apply the user's 2026-10-20 corrections; back up before removing named plots."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config import DATABASE_PATH, RUNTIME_DIR
from database.init_db import get_connection, init_db, now_iso
from data_pipeline.ingest_project_raw import load_profile, sync_confirmed_profile

REMOVED_IDS=('plot_3db2190d','plot_955456c8','plot_f896d8da')


def apply_confirmation(profile_only=False):
    init_db()
    backup=RUNTIME_DIR/'raw_review'/('before_catimor_confirmation_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.db')
    backup.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as source,sqlite3.connect(backup) as target:
        source.backup(target)
    profile=load_profile()
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT raw_json FROM plots WHERE plot_id=?',(profile['plot_id'],)).fetchone()
        if not row: raise ValueError('卡蒂姆档案不存在，不能删除其他档案')
        sync_confirmed_profile(conn, profile)
        removed=[]
        for pid in (() if profile_only else REMOVED_IDS):
            row=conn.execute('SELECT plot_name FROM plots WHERE plot_id=?',(pid,)).fetchone()
            if not row: continue
            if row['plot_name']!='潞江坝咖啡示范园': raise ValueError('目标档案名称变化，停止删除：'+pid)
            # Their historical demo results/logs remain under their old IDs, never
            # reclassified as this base's observed events or current model results.
            conn.execute('DELETE FROM plots WHERE plot_id=?',(pid,))
            removed.append(pid)
    return {'removed_plot_ids':removed,'remaining_plot_id':profile['plot_id'],'backup':str(backup),
            'history_policy':'旧档案农事/模型记录保留原ID存档，不合并为卡蒂姆实测',
            'raw_observations_modified':False,'layer_intervals_cm':profile['layer_intervals_cm']}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--profile-only',action='store_true',help='仅同步确认的档案信息，不删除任何地块')
    args=parser.parse_args()
    print(json.dumps(apply_confirmation(profile_only=args.profile_only),ensure_ascii=False,indent=2))
