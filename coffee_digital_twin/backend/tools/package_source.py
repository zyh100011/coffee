"""Create a local source ZIP from tracked files, excluding engines, secrets and user configs."""
import argparse
from pathlib import Path,PurePosixPath
import subprocess
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.material_paths import REPO_ROOT,allowed_path

def include(path):
    p=PurePosixPath(path);parts=p.parts
    if not parts or '..' in parts or p.is_absolute(): return False
    if parts[0]!='coffee_digital_twin' and path not in ('AGENTS.md','README_从这里开始.md','.gitignore'): return False
    if any(x.startswith('06_正式测试资料') or x in ('.git','.venv','__pycache__','runtime','raw','logs','backup','node_modules') for x in parts): return False
    if (p.name.startswith('.env') and p.name!='.env.example') or p.name in ('project.config.json','project.private.config.json') or path=='coffee_digital_twin/miniprogram/utils/config.js': return False
    if p.suffix.lower() in ('.exe','.dll','.db','.sqlite','.sqlite3','.pyc','.zip','.docx','.pdf','.mp4','.png','.jpg'): return False
    return True

def package(destination):
    destination=allowed_path(destination)
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=REPO_ROOT).decode('utf-8').split('\0')
    selected=[p for p in paths if p and include(p) and (REPO_ROOT/p).is_file()]
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in selected:
            actual=allowed_path(REPO_ROOT/path)
            if not actual.is_relative_to(REPO_ROOT): raise ValueError('源码路径越出仓库')
            archive.write(actual,path)
    return len(selected)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=REPO_ROOT/'coffee_digital_twin/backend/runtime/delivery/source_phase5.zip')
    args=p.parse_args();print('本地源码包文件数：'+str(package(args.out)))
