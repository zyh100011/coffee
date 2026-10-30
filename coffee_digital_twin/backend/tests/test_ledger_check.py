import csv

import pytest

from tools.ledger_check import REQUIRED_FIELDS, EXTRA_FIELDS, check_ledger


def _write_ledger(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REQUIRED_FIELDS + EXTRA_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _record(doc_id, filename):
    row = {field: "未知" for field in REQUIRED_FIELDS + EXTRA_FIELDS}
    row.update(doc_id=doc_id, 保存路径=filename, 标题="构造测试文件，非真实文献")
    return row


def test_reports_empty_fields_duplicate_id_and_duplicate_content(tmp_path):
    (tmp_path / "a.txt").write_text("synthetic source only", encoding="utf-8")
    (tmp_path / "b.txt").write_text("synthetic source only", encoding="utf-8")
    first = _record("A3-TEST", "a.txt")
    second = _record("A3-TEST", "b.txt")
    second["标题"] = ""
    ledger = tmp_path / "ledger.csv"
    _write_ledger(ledger, [first, second])
    before = ledger.read_bytes()
    report = check_ledger(ledger, tmp_path)
    assert report["rows_checked"] == 2
    assert {issue["code"] for issue in report["issues"]} == {"empty_required", "duplicate_doc_id", "duplicate_content"}
    assert ledger.read_bytes() == before


def test_existing_file_and_unknown_conditions_are_accepted(tmp_path):
    (tmp_path / "source.txt").write_text("synthetic source only", encoding="utf-8")
    ledger = tmp_path / "ledger.csv"
    _write_ledger(ledger, [_record("A3-TEST", "source.txt")])
    assert check_ledger(ledger, tmp_path) == {"rows_checked": 1, "issues": []}


def test_missing_original_and_formal_test_reference_are_reported(tmp_path):
    ledger = tmp_path / "ledger.csv"
    _write_ledger(ledger, [_record("A3-TEST1", "missing.pdf"),
                           _record("A3-TEST2", "06_正式测试资料/secret.jsonl")])
    report = check_ledger(ledger, tmp_path)
    assert [issue["code"] for issue in report["issues"]] == ["file_missing", "restricted_path"]


def test_invalid_header_and_empty_template(tmp_path):
    ledger = tmp_path / "ledger.csv"
    ledger.write_text("doc_id,标题\n", encoding="utf-8")
    assert check_ledger(ledger, tmp_path)["issues"][0]["code"] == "missing_columns"
    _write_ledger(ledger, [])
    assert check_ledger(ledger, tmp_path) == {"rows_checked": 0, "issues": []}


def test_checker_cannot_open_formal_test_ledger(tmp_path):
    with pytest.raises(ValueError, match="正式测试"):
        check_ledger(tmp_path / "06_正式测试资料" / "ledger.csv", tmp_path)
