"""Check declared delivery links and paths. Remote checks use HEAD only."""
import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin,urlsplit,urlunsplit,unquote
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import requests
from tools.material_paths import REPO_ROOT,allowed_path

DEFAULT=REPO_ROOT/'coffee_digital_twin/docs/zyh/交付目录.md'

def safe_url(url):
    u=urlsplit(url)
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:
        raise ValueError('拒绝含凭据或无效URL')
    return url

def display_url(url):
    u=urlsplit(url)
    return urlunsplit((u.scheme,u.hostname or '',u.path,'',''))

def head(url,timeout=8):
    current=safe_url(url)
    for _ in range(5):
        response=requests.head(current,allow_redirects=False,timeout=timeout)
        status=response.status_code
        if status in (301,302,303,307,308) and response.headers.get('Location'):
            current=safe_url(urljoin(current,response.headers['Location']));continue
        return 200<=status<400,'HTTP '+str(status)
    return False,'重定向次数过多'

def check(document=DEFAULT,repo=REPO_ROOT):
    repo=allowed_path(repo);document=allowed_path(document)
    text=document.read_text(encoding='utf-8-sig')
    targets=[]
    for target in re.findall(r'`([^`\n]+)`',text):
        if target.startswith(('coffee_digital_twin/','实验资料/','https://','http://')):targets.append((target,repo))
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
        targets.append((target.strip('<>'),document.parent))
    targets.extend((url,repo) for url in re.findall(r'https?://[^\s<>`)|]+',text))
    rows=[];seen=set()
    for target,base in targets:
        if target in seen:continue
        seen.add(target)
        if target.startswith(('https://','http://')):
            try:passed,detail=head(target)
            except (ValueError,requests.RequestException):passed,detail=False,'URL无效、不可访问或包含凭据；不输出URL参数'
            rows.append({'kind':'url','target':display_url(target),'status':'PASS' if passed else 'FAIL','detail':detail})
        elif target.startswith('#'):
            continue
        else:
            try:
                local=unquote(target.split('#',1)[0]);path=allowed_path(base/local)
                if not path.is_relative_to(repo):raise ValueError('路径越出仓库')
                exists=path.exists()
                rows.append({'kind':'path','target':local,'status':'PASS' if exists else 'FAIL','detail':'存在' if exists else '缺失'})
            except (OSError,ValueError):rows.append({'kind':'path','target':'受限路径','status':'FAIL','detail':'越界、无效或正式测试目录，不访问'})
    return rows

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--document',type=Path,default=DEFAULT);parser.add_argument('--out',type=Path)
    args=parser.parse_args();rows=check(args.document)
    if args.out:allowed_path(args.out).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    for row in rows:print(row['status']+' | '+row['kind']+' | '+row['target']+' | '+row['detail'])
    print('路径/HEAD可达不等于真实服务、成果或人工验收完成')
    sys.exit(0 if rows and all(r['status']=='PASS' for r in rows) else 1)
