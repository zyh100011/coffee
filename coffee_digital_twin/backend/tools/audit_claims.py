"""Enumerate every matching line with an explicit review disposition; no scientific claims."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.material_paths import REPO_ROOT,allowed_path

WORDS=('增产','节水','精准','专家通过','已验证','success')
OUTPUTS={'措辞扫描明细.json','措辞核查.md'}
def disposition(path,line):
    if path.name in ('contribution_audit.json','git_history_phase5.txt','git_diff_stat_phase5.txt','新旧贡献记录.md'):
        return 'Git历史/原文件头与贡献归属存档；非本届农业效果或专家评价，原文保留用于追溯'
    if path.name=='CODEX_PLAN.md': return '执行规范/待验收要求，非已取得成果'
    if path.name=='baseline_snapshot_before.json': return '旧接口基线存档，含旧演示/预填评价；不得用作现行科学结论'
    if path.name in ('hydrus_phase0_verification.json','hydrus_phase3_stability.json','scenario_phase4_verification.json'):
        return '已运行工程/假设案例记录；success仅表示程序状态，不表示农业预测有效'
    if path.suffix in ('.js','.wxml'):
        if all(w not in line for w in WORDS[:-1]): return '协议状态/微信回调名称；仅表示代码或工具可用，不是科学验证'
    if any(x in line for x in ('不能','不推导','没有','无依据','非','待','移除','未校准','不支持','不声称','未冒称','禁止')):
        return '范围限制/缺项/历史诊断，保留警示语义'
    if 'success' in line: return '工程状态/可用性定义，须结合原文的来源与适用限制'
    return '人工复核必要：需要明确对应实验或调整表述'

def scan():
    hits=[]
    for root in (REPO_ROOT/'coffee_digital_twin/miniprogram',REPO_ROOT/'coffee_digital_twin/docs'):
        # Scope is fixed, outside all material folders; never traverse formal tests.
        for path in sorted(root.rglob('*')):
            if path.suffix not in ('.js','.wxml','.md','.json','.txt','.csv') or path.name in OUTPUTS: continue
            if root.name=='miniprogram' and path.suffix not in ('.js','.wxml'): continue
            for number,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
                terms=[w for w in WORDS if w in line]
                if terms: hits.append({'file':path.relative_to(REPO_ROOT).as_posix(),'line':number,'terms':terms,
                    'text':line,'disposition':disposition(path,line)})
    return hits

def export(out):
    hits=scan();out=allowed_path(out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'scope':'miniprogram/*.js/wxml + docs textual files; generated audit files excluded',
        'hits':hits,'unresolved':sum(h['disposition'].startswith('人工复核必要') for h in hits)},ensure_ascii=False,indent=2),encoding='utf-8')
    return hits

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=REPO_ROOT/'coffee_digital_twin/docs/zyh/措辞扫描明细.json')
    hits=export(p.parse_args().out);pending=sum(h['disposition'].startswith('人工复核必要') for h in hits)
    print(json.dumps({'matching_lines':len(hits),'requires_review':pending},ensure_ascii=False));sys.exit(1 if pending else 0)
