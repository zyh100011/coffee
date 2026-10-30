"""Read complete columns as strings; profile, never repair identifiers."""
import argparse
import csv
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from tools.inventory_assets import guess_encoding
from tools.material_paths import allowed_path, MATERIAL_ROOT


def read_tables(path):
    path=allowed_path(path)
    if path.suffix.lower()=='.xlsx':
        return pd.read_excel(path,sheet_name=None,dtype=str,keep_default_na=False,engine='openpyxl')
    if path.suffix.lower() not in {'.csv','.txt'}:
        return {}
    raw=path.read_bytes(); encoding=guess_encoding(raw)
    if not raw:
        return {}
    content=raw.decode(encoding)
    try:
        sep=csv.Sniffer().sniff(content[:8192],delimiters=',\t;|').delimiter
    except csv.Error:
        if path.suffix.lower()=='.txt':
            raise ValueError('TXT格式未确认，不能猜测IN-G10层级')
        sep=','
    return {'':pd.read_csv(path,sep=sep,dtype=str,keep_default_na=False,encoding=encoding)}


def precision_suspect(value):
    text=str(value).strip()
    return bool(re.search(r'\d[Ee][+-]?\d',text) or re.fullmatch(r'\d{15,}0{3,}(?:\.0)?',text))


def profile(root,out):
    root=allowed_path(root); out=allowed_path(out)
    lines=['# 字段画像','所有字段按字符串读取；示例值仅为原文件预览，不代表已确认观测。']
    for path in sorted(root.rglob('*')):
        allowed_path(path)
        if not path.is_file() or path.suffix.lower() not in {'.csv','.txt','.xlsx'}:
            continue
        lines.append('\n## '+path.relative_to(root).as_posix())
        try:
            for sheet,table in read_tables(path).items():
                lines.append('工作表：'+sheet+'；行数：'+str(len(table)))
                for col in table:
                    values=table[col].astype(str).str.strip(); nonempty=values[values!='']
                    kind='设备ID' if re.search('device|设备|编号',col,re.I) else '时间' if re.search('time|date|时间|日期',col,re.I) else '数值' if len(nonempty) and pd.to_numeric(nonempty,errors='coerce').notna().all() else '文本/单位'
                    warning=' precision_loss_suspect' if kind=='设备ID' and any(precision_suspect(v) for v in nonempty) else ''
                    lines.append(f'- {col}：非空率 {len(nonempty)/max(len(values),1):.3f}；疑似{kind}；示例 '+json.dumps(nonempty.head(3).tolist(),ensure_ascii=False)+warning)
        except Exception as error:
            lines.append('未解析：'+str(error))
    out.parent.mkdir(parents=True,exist_ok=True); out.write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--root',type=Path,default=MATERIAL_ROOT/'03_地块与监测数据'/'raw'); parser.add_argument('--out',type=Path,default=MATERIAL_ROOT/'03_地块与监测数据'/'字段画像.md')
    args=parser.parse_args(); profile(args.root,args.out)
