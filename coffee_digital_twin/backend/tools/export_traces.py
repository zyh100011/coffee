"""Export traces with path isolation and recursive credential redaction."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database.init_db import get_connection
from tools.material_paths import allowed_path

def redact(value):
    if isinstance(value,dict):
        return {k:('[REDACTED]' if re.search('key|secret|password|token|authorization',k,re.I) else redact(v)) for k,v in value.items()}
    if isinstance(value,list): return [redact(v) for v in value]
    if isinstance(value,str):
        for key,secret in os.environ.items():
            if re.search('key|secret|password|token',key,re.I) and len(secret)>=8: value=value.replace(secret,'[REDACTED]')
        value=re.sub(r'(Bearer[ ]+)[A-Za-z0-9._-]+',r'Bearer [REDACTED]',value,flags=re.I)
        value=re.sub(r'((?:api_key|password|secret|token)[ ]*[=:][ ]*)[^ ,;]+',r'[REDACTED]',value,flags=re.I)
    return value

def export(out):
    out=allowed_path(out); out.parent.mkdir(parents=True,exist_ok=True)
    with get_connection() as conn: rows=conn.execute('SELECT * FROM assistant_traces ORDER BY created_at,trace_id').fetchall()
    with out.open('w',encoding='utf-8') as stream:
        for row in rows:
            item=dict(row)
            for key in list(item):
                if key.endswith('_json'): item[key[:-5]]=json.loads(item.pop(key))
            stream.write(json.dumps(redact(item),ensure_ascii=False)+'\n')
    return len(rows)
if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--out',required=True); args=parser.parse_args(); print(export(args.out))
