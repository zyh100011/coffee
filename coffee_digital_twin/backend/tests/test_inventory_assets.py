import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from tools.inventory_assets import inventory, write_inventory


def test_overlapping_exports_and_string_device_ids():
    root = Path(__file__).parent / "fixtures" / "raw_sample"
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in root.iterdir()}
    items, duplicates = inventory(root)
    assert len(items) == 2
    assert duplicates[0]["reason"] == "same_columns_overlapping_dates"
    assert items[0]["preview"][0]["device_id"] == "000123"
    assert items[0]["date_ranges"]["date"] == {"min": "2026-09-01", "max": "2026-09-03", "parsed_rows": 3}
    assert before == {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in root.iterdir()}


def test_identical_files_and_non_overlapping_exports(tmp_path):
    content = "date,value\n2026-09-01,2\n"
    (tmp_path / "a.csv").write_text(content, encoding="utf-8")
    (tmp_path / "b.csv").write_text(content, encoding="utf-8")
    (tmp_path / "c.csv").write_text("date,value\n2026-10-01,3\n", encoding="utf-8")
    _, duplicates = inventory(tmp_path)
    assert duplicates == [{"files": ["a.csv", "b.csv"], "reason": "same_sha256"}]


def test_empty_folder_readme_and_machine_readable_report(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "README.md").write_text("place exports here", encoding="utf-8")
    assert inventory(raw) == ([], [])
    output = tmp_path / "inventory.csv"
    write_inventory([], output)
    with output.open(encoding="utf-8-sig") as stream:
        assert list(csv.DictReader(stream)) == []


def test_utf16_text_and_multisheet_excel(tmp_path):
    (tmp_path / "sensor.txt").write_text("日期\t设备\t水分\n2026/09/01\t0001\t20\n", encoding="utf-16")
    with pd.ExcelWriter(tmp_path / "sensors.xlsx", engine="openpyxl") as writer:
        pd.DataFrame({"date": ["2026-09-01"], "device_id": ["0001"]}).to_excel(writer, sheet_name="first", index=False)
        pd.DataFrame({"date": ["2026-09-02", "2026-09-03"], "device_id": ["0002", "0002"]}).to_excel(writer, sheet_name="second", index=False)
    items, _ = inventory(tmp_path)
    text, excel = items
    assert text["encoding_guess"] == "utf-16"
    assert text["preview"][0]["设备"] == "0001"
    assert excel["rows"] == 3
    assert set(excel["sheets"]) == {"first", "second"}
    assert excel["preview"][0]["device_id"] == "0001"


def test_corrupt_excel_is_reported_without_losing_inventory(tmp_path):
    (tmp_path / "broken.xlsx").write_bytes(b"not a workbook")
    items, _ = inventory(tmp_path)
    assert items[0]["status"] == "read_error"
    assert items[0]["sha256"]
    output = tmp_path / "report.csv"
    write_inventory(items, output)
    with output.open(encoding="utf-8-sig") as stream:
        saved = next(csv.DictReader(stream))
    assert json.loads(saved["warnings"])


def test_formal_test_directory_is_rejected_before_access(tmp_path):
    with pytest.raises(ValueError, match="正式测试"):
        inventory(tmp_path / "06_正式测试资料")
