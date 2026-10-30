from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database.init_db import get_connection,init_db
from tools.material_paths import allowed_path

def generate(out):
    init_db(); lines=['# 数据字典','根据SQLite结构和column_mapping.yaml自动生成。当前缺资料，未冻结data-v1.0。',
      'n/mean/min/max/first/last统计原始有效记录；daily_mean仅聚合series；默认排除异常。缺测按有效值日期计。累计雨首条未知为null；复位以当前计数作增量。']
    with get_connection() as conn:
        for table in ('raw_files','obs_long','device_plot_map','lai_obs','farm_events','soil_reports','data_versions'):
            lines.append('\n## '+table)
            lines.extend('- '+r['name']+'：'+r['type'] for r in conn.execute('PRAGMA table_info('+table+')'))
    lines += ['\n## 映射草稿','```yaml',Path(__file__).with_name('column_mapping.yaml').read_text(encoding='utf-8'),'```',
      'IN-G10原TXT格式未提供；ingest_lai仅接受已确认规范CSV，保留样方/植株/测次。事件须核实；报告pending时数值为空。']
    allowed_path(out).write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__': generate(Path(__file__).resolve().parents[2]/'docs'/'zyh'/'数据字典.md')
