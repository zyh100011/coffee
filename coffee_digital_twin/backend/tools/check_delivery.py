"""Check only declared delivery paths. Pending items point to instructions, not fake artifacts."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.material_paths import REPO_ROOT,allowed_path

MANIFEST=REPO_ROOT/'coffee_digital_twin/docs/zyh/delivery_manifest.json'

def check(manifest=MANIFEST):
    manifest=allowed_path(manifest)
    content=json.loads(manifest.read_text(encoding='utf-8-sig'));rows=[]
    for entry in content['items']:
        try:
            target=allowed_path(REPO_ROOT/entry['path'])
            if not target.is_relative_to(REPO_ROOT): raise ValueError('交付路径越出仓库')
            exists=target.exists()
            rows.append({'id':entry['id'],'path':entry['path'],'status':entry['status'],
                'path_check':'PASS' if exists else 'FAIL','note':entry['note']})
        except (ValueError,OSError): rows.append({'id':entry['id'],'path_check':'FAIL','note':'受限或无效路径'})
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,default=MANIFEST);args=p.parse_args()
    rows=check(args.manifest)
    for r in rows: print(f"{r['id']} | {r['path_check']} | {r.get('status','invalid')} | {r['note']}")
    print('路径存在不等于所有交付已齐全；pending项仍需真实材料')
    sys.exit(1 if any(r['path_check']!='PASS' for r in rows) else 0)
