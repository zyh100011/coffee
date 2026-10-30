"""Explicit task/plot selection, never global latest."""
import json
from database.init_db import get_connection


class SelectionError(ValueError):
    pass


def select_result(task_id=None, plot_id=None):
    if not task_id and not plot_id:
        raise SelectionError('必须指定 task_id 或 plot_id')
    with get_connection() as conn:
        if task_id:
            row = conn.execute('SELECT * FROM model_results WHERE task_id=?', (task_id,)).fetchone()
            if row and plot_id and row['plot_id'] != plot_id:
                return None
        else:
            row = conn.execute('SELECT * FROM model_results WHERE plot_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1', (plot_id,)).fetchone()
    if not row:
        return None
    result = json.loads(row['result_json'])
    result.update(result_selected_by='task_id' if task_id else 'plot_latest', result_created_at=row['created_at'])
    return result
