"""Reproducible baseline ownership and per-file task coverage, without rewriting authors."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.material_paths import REPO_ROOT,allowed_path

BASELINE='221a26b'
DOC=REPO_ROOT/'coffee_digital_twin/docs/zyh/新旧贡献记录.md'
BEGIN='<!-- BEGIN GENERATED CONTRIBUTIONS -->'
END='<!-- END GENERATED CONTRIBUTIONS -->'
USER_CONFIGS={'coffee_digital_twin/miniprogram/project.config.json',
 'coffee_digital_twin/miniprogram/project.private.config.json','coffee_digital_twin/miniprogram/utils/config.js'}

def git(*args):
    return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=REPO_ROOT).decode('utf-8',errors='replace')

def paths(*args): return [p for p in git(*args).split('\0') if p]

def purpose(path):
    mapping={'apsim_adapter.py':'APSIM OilPalm代理适配，蔡负责原模型',
      'beps_adapter.py':'BEPS简化计算，简负责原模型',
      'hydrus_adapter.py':'张源皓原HYDRUS调用与输出解析、蔡集成；本届仅适配',
      'fusion_engine.py':'旧多模型融合业务逻辑',
      'llm_service.py':'旧GLM调用与建议业务逻辑',
      'H1D_CALC.EXE':'外部HYDRUS数值引擎；许可待确认，非本届原创',
      'model_api.py':'旧模型业务调度', 'app.py':'旧Flask入口',
      'request.js':'旧微信HTTP请求封装','app.wxss':'旧小程序配色与公共样式'}
    p=Path(path)
    if p.name in mapping: return mapping[p.name]
    if '/pages/' in path: return '旧原生小程序页面：'+p.parent.name
    if '/components/' in path: return '旧原生小程序组件：'+p.parent.name
    if '/templates/' in path: return '旧模型输入模板，许可与参数来源需独立确认'
    if '/demo_data/' in path: return '旧演示/预填数据，非本届实测或专家验证'
    if '/docs/' in path: return '旧设计/接口/模型说明'
    if '/runtime/' in path: return '旧运行目录占位/存档'
    if '/server/' in path: return '旧部署/引擎位置/备份占位'
    return '旧工程配置/辅助业务：'+p.name

def old_markers(content):
    return [line.strip() for line in content.splitlines() if re.search('AI辅助生成|原始实现|集成适配|原作者|作者[：:]',line)]

def build(working_task='T5.4'):
    baseline=paths('ls-tree','-r','--name-only','-z',BASELINE,'--','coffee_digital_twin')
    committed=set(paths('diff','--name-only','-z',BASELINE,'HEAD','--','.'))
    working=set(paths('diff','--name-only','-z','HEAD','--','.'))
    changes=set(committed)
    # Include current task's tracked/staged/untracked engineering sources, never raw material.
    for path in paths('ls-files','--others','--exclude-standard','-z','--','coffee_digital_twin'):
        if '/runtime/' not in path: changes.add(path)
    for path in paths('diff','--name-only','-z',BASELINE,'--','.'): changes.add(path)
    changes-=USER_CONFIGS
    safe=[]
    for path in sorted(changes):
        # Formal contents must never be read even if accidentally tracked by somebody else.
        if any(p.startswith('06_正式测试资料') for p in Path(path).parts): continue
        if Path(path).name.startswith('.env') and Path(path).name!='.env.example': continue
        safe.append(path)
    old=[];lost=[]
    for path in baseline:
        authors=git('log',BASELINE,'--format=%an','--',path).splitlines()
        authors=list(dict.fromkeys(authors))
        markers=[]
        if Path(path).suffix in ('.py','.js','.wxml','.wxss'):
            original=git('show',BASELINE+':'+path)
            markers=old_markers(original)
            current=REPO_ROOT/path
            if current.is_file():
                text=current.read_text(encoding='utf-8-sig')
                for marker in markers:
                    if marker not in text: lost.append({'file':path,'marker':marker})
        old.append({'file':path,'authors':authors,'header_markers':markers,'purpose':purpose(path)})
    current=[]
    for path in safe:
        entries=git('log',BASELINE+'..HEAD','--format=%h %s','--',path).splitlines()
        tasks=list(dict.fromkeys(t for e in entries for t in re.findall(r'\[(T[^\]]+)\]',e)))
        if path not in committed or path in working:
            tasks.append(working_task)
        kind='新增' if path not in baseline else '删除' if not (REPO_ROOT/path).exists() else '仅适配' if path.endswith('/models/hydrus_adapter.py') else '改造'
        description='本届业务/数据/界面/检查或文档实现；详见任务提交'
        if path.endswith('tool_registry.py') or path.endswith('model_api.py') or path.endswith('fusion_engine.py'):
            description='含旧模型外层仅适配/状态包装；不重建APSIM/BEPS数值核心'
        if path.endswith('hydrus_adapter.py'): description='HYDRUS输入/执行/解析/来源与回放适配，数值引擎保持原样'
        if kind=='删除': description='删除旧ec-canvas空占位，不含真实ECharts组件'
        current.append({'file':path,'type':kind,'tasks':list(dict.fromkeys(tasks)) or [working_task],'description':description})
    return {'baseline':BASELINE,'scope':'baseline..HEAD plus current task working changes; excludes 3 user local configs',
      'old_files':old,'current_files':current,'missing_markers':lost,
      'git_log':git('log','--format=%h %an %ad %s','--date=short'),
      'diff_stat':git('diff','--stat',BASELINE,'HEAD','--','coffee_digital_twin')}

def escape(text): return str(text).replace('|','/').replace('\n',' ')

def export(working_task='T5.4'):
    result=build(working_task);folder=DOC.parent
    (folder/'contribution_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'git_history_phase5.txt').write_text(result['git_log'],encoding='utf-8')
    (folder/'git_diff_stat_phase5.txt').write_text(result['diff_stat'],encoding='utf-8')
    section=BEGIN+'\n\n## 表一：基线旧工程逐文件归属\n\n基线221a26b。Git author是提交者，不能推定为唯一知识产权作者；原文件头署名和AI注释优先补充来源，外部引擎/模板仍须核实许可。\n\n| 文件 | Git提交者/文件头来源 | 原功能 |\n|---|---|---|\n'
    for row in result['old_files']:
        source='、'.join(row['authors'])+'；'+'；'.join(row['header_markers'])
        section+=f"| `{row['file']}` | {escape(source)} | {escape(row['purpose'])} |\n"
    section+='\n## 表二：本届逐文件改动与任务\n\n覆盖baseline到HEAD已提交改动及本次T5.4工作文件；三个用户本地配置不算本届提交。Git历史原文与diff stat另存git_history_phase5.txt/git_diff_stat_phase5.txt；生成器可复跑。文档无法记录包含自身提交的最终HEAD而不再产生新提交，因此验收按路径覆盖检查，不编造自引用哈希。\n\n| 文件 | 类型 | 任务号 | 简述 |\n|---|---|---|---|\n'
    for row in result['current_files']:
        section+=f"| `{row['file']}` | {row['type']} | {', '.join(row['tasks'])} | {row['description']} |\n"
    section+='\n原署名/AI注释缺失检查：'+('无缺失' if not result['missing_markers'] else '发现缺失，详见contribution_audit.json')+'。不把本机Git提交者改写为旧作者，不把适配、模板、演示数据或外部数值引擎记成本届原创。\n\n'+END
    text=DOC.read_text(encoding='utf-8-sig')
    if BEGIN in text: text=text[:text.index(BEGIN)]+section+text[text.index(END)+len(END):]
    else: text+='\n'+section+'\n'
    DOC.write_text(text,encoding='utf-8')
    return result

def verify():
    declared=json.loads((DOC.parent/'contribution_audit.json').read_text(encoding='utf-8'))
    actual=build()
    missing=sorted({r['file'] for r in actual['current_files']}-{r['file'] for r in declared['current_files']})
    return {'missing_paths':missing,'missing_markers':actual['missing_markers'],'covered':len(declared['current_files'])}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--working-task',default='T5.4');args=p.parse_args()
    if args.check:
        r=verify();print(json.dumps(r,ensure_ascii=False));sys.exit(1 if r['missing_paths'] or r['missing_markers'] else 0)
    r=export(args.working_task);print(json.dumps({'old':len(r['old_files']),'current':len(r['current_files']),'missing_markers':r['missing_markers']},ensure_ascii=False))
