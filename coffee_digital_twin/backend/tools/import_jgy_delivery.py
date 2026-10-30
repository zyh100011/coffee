"""Import fixed, reviewed delivery paths; keep the original files and site observations intact."""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATABASE_PATH, RUNTIME_DIR
from database.init_db import init_db
from services.jgy_delivery import ingest

if __name__ == '__main__':
    backup = None
    if DATABASE_PATH.is_file():
        backup = RUNTIME_DIR / 'backups' / ('before_jgy_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.db')
        backup.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DATABASE_PATH) as source, sqlite3.connect(backup) as target:
            source.backup(target)
    init_db()
    result = ingest()
    result['backup'] = str(backup) if backup else None
    print(json.dumps(result, ensure_ascii=False, indent=2))
