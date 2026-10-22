"""Validate source registration and accessible originals; do not download papers."""
import argparse
import csv
import json
from pathlib import Path

try:
    from tools.material_paths import MATERIAL_ROOT, REPO_ROOT, allowed_path, sha256_file
except ModuleNotFoundError:
    from material_paths import MATERIAL_ROOT, REPO_ROOT, allowed_path, sha256_file


REQUIRED_FIELDS = ["doc_id", "标题", "作者/机构", "发布年份/版本", "原始链接或内部来源", "保存路径",
                   "主题", "地区", "作物/品种", "生育期", "土壤/冠层条件", "有效状态", "使用权限", "审核状态", "采集人"]
EXTRA_FIELDS = ["参数类型(文献/推算/实测)", "页码定位", "交叉核查人"]


def check_ledger(ledger_path, repo_root=REPO_ROOT):
    ledger_path = allowed_path(ledger_path)
    root = allowed_path(repo_root)
    issues = []
    seen_ids, seen_hashes = {}, {}
    rows_checked = 0

    def issue(row, code, message, doc_id=""):
        issues.append({"row": row, "doc_id": doc_id, "code": code, "message": message})

    with ledger_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing_columns = set(REQUIRED_FIELDS) - set(reader.fieldnames or [])
        if missing_columns:
            issue(1, "missing_columns", "缺少必填表头：" + "、".join(sorted(missing_columns)))
            return {"rows_checked": 0, "issues": issues}
        for row_number, row in enumerate(reader, start=2):
            rows_checked += 1
            doc_id = (row.get("doc_id") or "").strip()
            if None in row or any(value is None for value in row.values()):
                issue(row_number, "column_count", "数据行列数与表头不一致", doc_id)
            missing = [field for field in REQUIRED_FIELDS if not (row.get(field) or "").strip()]
            if missing:
                issue(row_number, "empty_required", "必填字段为空（未知条件应填未知）：" + "、".join(missing), doc_id)
            if doc_id:
                if doc_id in seen_ids:
                    issue(row_number, "duplicate_doc_id", f"doc_id 重复，首次登记在第 {seen_ids[doc_id]} 行", doc_id)
                else:
                    seen_ids[doc_id] = row_number
            raw_path = (row.get("保存路径") or "").strip()
            if not raw_path:
                continue
            if raw_path == "未知":
                issue(row_number, "unresolved_path", "原文保存位置未知，尚不能回查", doc_id)
                continue
            source = Path(raw_path.replace("\\", "/"))
            try:
                source = allowed_path(source if source.is_absolute() else root / source)
                if not source.is_file():
                    issue(row_number, "file_missing", f"原文文件不存在或不是文件：{raw_path}", doc_id)
                    continue
                digest = sha256_file(source)
                if digest in seen_hashes:
                    first_row, first_doc = seen_hashes[digest]
                    issue(row_number, "duplicate_content", f"原文 SHA256 相同，首次登记第 {first_row} 行（{first_doc}）；同一原文只计一份", doc_id)
                else:
                    seen_hashes[digest] = (row_number, doc_id)
            except ValueError as error:
                issue(row_number, "restricted_path", str(error), doc_id)
            except OSError as error:
                issue(row_number, "file_unreadable", f"原文无法读取：{error}", doc_id)
    return {"rows_checked": rows_checked, "issues": issues}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=MATERIAL_ROOT / "01_原始知识资料" / "来源台账.csv")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    arguments = parser.parse_args()
    try:
        report = check_ledger(arguments.ledger, arguments.repo_root)
    except (OSError, ValueError, UnicodeError, csv.Error) as error:
        print(json.dumps({"issues": [{"code": "ledger_unreadable", "message": str(error)}]}, ensure_ascii=False))
        return 1
    if report["rows_checked"] == 0 and not report["issues"]:
        print("来源台账目前为空模板，请登记原文；空模板不代表资料已经齐全。")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
