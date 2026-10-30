from pathlib import Path
from tools.audit_claims import scan,disposition,WORDS
from tools.material_paths import REPO_ROOT
import json
from tools.check_delivery import check
from tools.package_source import include

def test_contribution_coverage_and_original_headers():
    from tools.contribution_audit import verify
    result=verify()
    assert result['covered'] > 200
    assert result['missing_paths']==[]
    assert result['missing_markers']==[]

def test_claim_inventory_and_no_unresolved_positive_assertion():
    hits=scan()
    assert hits and not any(h['disposition'].startswith('人工复核必要') for h in hits)
    for hit in hits:
        path=REPO_ROOT/hit['file']
        assert path.read_text(encoding='utf-8-sig').splitlines()[hit['line']-1]==hit['text']
        assert any(w in hit['text'] for w in WORDS)
    assert disposition(Path('page.wxml'),'本系统精准增产').startswith('人工复核必要')

def test_delivery_paths_and_package_exclusions(tmp_path):
    rows=check()
    assert rows and all(r['path_check']=='PASS' for r in rows)
    assert any(r['status']=='pending' for r in rows)
    for path in ('coffee_digital_twin/server/hydrus_engine/H1D_CALC.EXE',
                 'coffee_digital_twin/backend/.env','coffee_digital_twin/backend/.env.production',
                 'coffee_digital_twin/miniprogram/project.config.json',
                 'coffee_digital_twin/miniprogram/utils/config.js',
                 '实验资料/06_正式测试资料/test.jsonl','coffee_digital_twin/backend/database/x.db'):
        assert not include(path)
    assert include('coffee_digital_twin/backend/.env.example')
    assert include('coffee_digital_twin/backend/tools/selfcheck.py')
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'items':[{'id':'bad','path':'实验资料/06_正式测试资料/unknown','status':'pending','note':'test'}]}),encoding='utf-8')
    assert check(manifest)[0]['path_check']=='FAIL'
