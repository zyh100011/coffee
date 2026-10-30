"""Read raw exports without changing them; report metadata and suspected overlap."""
import argparse
import codecs
import csv
from datetime import datetime
import itertools
import json
import os
from pathlib import Path
import re

from charset_normalizer import from_bytes
import pandas as pd

try:
    from tools.material_paths import MATERIAL_ROOT, allowed_path, sha256_file
except ModuleNotFoundError:
    from material_paths import MATERIAL_ROOT, allowed_path, sha256_file


FIELDS = ["filename", "relative_path", "size_bytes", "sha256", "extension", "encoding_guess",
          "rows", "columns", "preview", "date_ranges", "sheets", "status", "warnings"]


def guess_encoding(data):
    if data.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        best = from_bytes(data).best()
        if best is None:
            raise ValueError("不能识别文本编码，请人工确认")
        return best.encoding


def _parse_date(value):
    value = str(value).strip()
    # IDs, arbitrary numbers and scientific notation are not date evidence.
    if not re.match(r"^(?:19|20)\d{2}(?:[-/.年]|\d{4}(?:$|\s))", value):
        return None
    normalized = value.replace("年", "-").replace("月", "-").replace("日", "")
    normalized = normalized.replace("/", "-")
    if re.match(r"^\d{4}\.\d{1,2}\.\d{1,2}", normalized):
        normalized = normalized.replace(".", "-", 2)
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        for pattern in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y%m%d"):
            try:
                return datetime.strptime(normalized, pattern).date().isoformat()
            except ValueError:
                pass
    return None


def describe_table(frame):
    frame.columns = [str(column) for column in frame.columns]
    frame = frame.fillna("")
    date_ranges = {}
    for column in frame.columns:
        if not re.search(r"date|time|日期|时间", column, re.I):
            continue
        dates = [parsed for value in frame[column] if (parsed := _parse_date(value))]
        if dates:
            date_ranges[column] = {"min": min(dates), "max": max(dates), "parsed_rows": len(dates)}
    return {"rows": len(frame), "columns": list(frame.columns),
            "preview": frame.head(3).to_dict(orient="records"), "date_ranges": date_ranges}


def inspect_file(path, root):
    item = {"filename": path.name, "relative_path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size, "sha256": sha256_file(path),
            "extension": path.suffix.lower(), "encoding_guess": None, "rows": None,
            "columns": [], "preview": [], "date_ranges": {}, "sheets": {},
            "status": "metadata_only", "warnings": []}
    try:
        if item["extension"] == ".xlsx":
            item["encoding_guess"] = "xlsx/xml"
            tables = pd.read_excel(path, sheet_name=None, dtype=str, keep_default_na=False, engine="openpyxl")
            item["sheets"] = {name: describe_table(frame) for name, frame in tables.items()}
            item["rows"] = sum(table["rows"] for table in item["sheets"].values())
            if item["sheets"]:
                first = next(iter(item["sheets"].values()))
                item.update({key: first[key] for key in ("columns", "preview", "date_ranges")})
            item["warnings"].append("Excel 数值型设备 ID 可能已丢失精度；盘点不会恢复或修正它")
            item["status"] = "ok"
        elif item["extension"] in {".csv", ".txt"}:
            sample = path.read_bytes()
            item["encoding_guess"] = guess_encoding(sample)
            text = sample.decode(item["encoding_guess"])
            if not text.strip():
                item.update(rows=0, status="empty")
                return item
            try:
                dialect = csv.Sniffer().sniff(text[:8192], delimiters=",\t;|")
                separator = dialect.delimiter
            except csv.Error:
                separator = "," if path.suffix.lower() == ".csv" else None
            if separator is None:
                lines = path.read_text(encoding=item["encoding_guess"]).splitlines()
                item.update(rows=len(lines), preview=lines[:3], status="unstructured_text")
                item["warnings"].append("未识别表格分隔符；保留文本概览，后续人工确认格式")
            else:
                frame = pd.read_csv(path, sep=separator, dtype=str, keep_default_na=False,
                                    encoding=item["encoding_guess"], on_bad_lines="error")
                item.update(describe_table(frame), status="ok")
        else:
            # Metadata is enough for PDFs/other binary reports; never decode them.
            pass
    except Exception as error:
        item.update(status="read_error")
        item["warnings"].append(f"{type(error).__name__}: {error}")
    return item


def _tables(item):
    return list(item["sheets"].values()) if item["sheets"] else [item]


def suspected_duplicates(items):
    suspects = []
    for left, right in itertools.combinations(items, 2):
        pair = {"files": [left["relative_path"], right["relative_path"]]}
        if left["sha256"] == right["sha256"]:
            suspects.append(dict(pair, reason="same_sha256"))
            continue
        for first, second in itertools.product(_tables(left), _tables(right)):
            if not first["columns"] or sorted(first["columns"]) != sorted(second["columns"]):
                continue
            for column in first["date_ranges"].keys() & second["date_ranges"].keys():
                a, b = first["date_ranges"][column], second["date_ranges"][column]
                if max(a["min"], b["min"]) <= min(a["max"], b["max"]):
                    suspects.append(dict(pair, reason="same_columns_overlapping_dates", date_column=column))
                    break
            else:
                continue
            break
    return suspects


def inventory(raw_dir):
    root = allowed_path(raw_dir)
    if not root.exists():
        return [], []
    if not root.is_dir():
        raise ValueError("raw 必须是文件夹")
    items = []
    files = []
    for directory, subdirs, names in os.walk(root, followlinks=False):
        # Do not enter formal test directories, even if placed under raw.
        subdirs[:] = [name for name in subdirs if not name.casefold().startswith("06_正式测试资料")]
        for name in subdirs:
            if not allowed_path(Path(directory) / name).is_relative_to(root):
                raise ValueError("raw 子目录指向目录外；拒绝读取链接目标")
        files.extend(Path(directory) / name for name in names)
    for path in sorted(files):
        if path.name.casefold() == "readme.md" or not path.is_file():
            continue
        resolved = allowed_path(path)
        if not resolved.is_relative_to(root):
            raise ValueError("raw 文件指向目录外；拒绝读取链接目标")
        items.append(inspect_file(path, root))
    return items, suspected_duplicates(items)


def write_inventory(items, output):
    output = allowed_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for item in items:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict))
                             else value for key, value in item.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=MATERIAL_ROOT / "03_地块与监测数据" / "raw")
    parser.add_argument("--out", type=Path, default=MATERIAL_ROOT / "03_地块与监测数据" / "资产清单.csv")
    arguments = parser.parse_args()
    if allowed_path(arguments.out).is_relative_to(allowed_path(arguments.raw_dir)):
        raise ValueError("资产清单必须写到 raw 目录外，避免覆盖或混入原始导出")
    items, suspects = inventory(arguments.raw_dir)
    write_inventory(items, arguments.out)
    if not items:
        print("请把原始导出放入 raw/；当前没有数据文件（README 不计入资产）。")
    print(json.dumps({"files": len(items), "read_errors": sum(i["status"] == "read_error" for i in items),
                      "suspected_duplicates": suspects, "output": str(arguments.out)}, ensure_ascii=False))
    return 1 if any(item["status"] == "read_error" for item in items) else 0


if __name__ == "__main__":
    raise SystemExit(main())
