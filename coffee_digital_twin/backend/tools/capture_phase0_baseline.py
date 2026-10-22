"""Run the unchanged legacy model route once, using temporary DB/runtime storage.

The supervisor bounds execution and stops only its own process tree on timeout.
The saved result is an engineering baseline containing legacy demo assumptions;
it is not a scientific validation record.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


BACKEND = Path(__file__).resolve().parents[1]
PROJECT = BACKEND.parent


def _worker(output):
    sys.path.insert(0, str(BACKEND))
    from app import create_app
    from config import APSIM_EXE, HYDRUS_EXE

    client = create_app().test_client()
    response = client.post("/api/model/run", json={"task_id": "phase0_legacy_baseline"})
    result = response.get_json()
    if response.status_code != 200:
        raise RuntimeError(f"Baseline HTTP status {response.status_code}: {result}")
    states = {tool: result.get(tool, {}).get("status") for tool in ("apsim", "hydrus", "beps")}
    result["_baseline_metadata"] = {
        "label": "旧工程改造前基线：使用旧 demo 气象、自动补地块和农事；不是实测或科学验证",
        "baseline_commit": "221a26b",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "http_status": response.status_code,
        "per_tool_status": states,
        "isolated_storage": True,
        "engines": {
            "apsim_exists": APSIM_EXE.is_file(),
            "hydrus_exists": HYDRUS_EXE.is_file(),
            "hydrus_sha256": hashlib.sha256(HYDRUS_EXE.read_bytes()).hexdigest()
            if HYDRUS_EXE.is_file() else None,
        },
        "limitations": [
            "HTTP 200 和融合 success 不代表三个引擎都运行成功",
            "BEPS 为简化计算，并可能使用 APSIM fallback 或旧 HYDRUS 输出",
            "HYDRUS 的时间、根系吸水比和建议文字保留旧实现，仅作工程对照",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"snapshot": str(output), "per_tool_status": states}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, default=PROJECT / "docs" / "zyh" / "baseline_snapshot_before.json")
    arguments = parser.parse_args()
    output = arguments.out.resolve()
    if arguments.worker:
        _worker(output)
        return
    with tempfile.TemporaryDirectory(prefix="coffee-baseline-") as directory:
        isolated = Path(directory)
        environment = dict(os.environ, COFFEE_DB_PATH=str(isolated / "baseline.db"),
                           COFFEE_RUNTIME_DIR=str(isolated / "runtime"),
                           FLASK_DEBUG="0", PYTHONIOENCODING="utf-8")
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--worker", "--out", str(output)],
            cwd=BACKEND, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        )
        try:
            stdout, stderr = process.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, check=False)
            process.communicate(timeout=10)
            raise RuntimeError("Legacy baseline exceeded 60 seconds; own process tree stopped") from None
        if process.returncode:
            raise RuntimeError(stderr or stdout)
        print(stdout.strip())


if __name__ == "__main__":
    main()
