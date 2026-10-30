"""Phase 0: inspect a real legacy HYDRUS run without changing the adapter."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid


BACKEND = Path(__file__).resolve().parents[1]
PROJECT = BACKEND.parent


def inspect_run(run_dir, result):
    files = []
    for path in sorted(run_dir.iterdir()) if run_dir.is_dir() else []:
        if path.is_file():
            files.append({"name": path.name, "bytes": path.stat().st_size,
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    nod = run_dir / "Nod_Inf.out"
    times = [float(value) for value in re.findall(
        r"^\s*Time:[ \t]*([-+\d.eE]+)[ \t]*$",
        nod.read_text(encoding="utf-8", errors="replace"), re.MULTILINE
    )] if nod.is_file() else []
    checks = {
        "adapter_success": result.get("status") == "success",
        "t_level_exists": (run_dir / "T_Level.out").is_file(),
        "nod_inf_exists": nod.is_file(),
        "no_error_msg": not (run_dir / "Error.msg").exists(),
        "initial_and_final_time": bool(times) and times[0] == 0 and times[-1] == 7,
    }
    return {"passed": all(checks.values()), "checks": checks,
            "output_times": times, "file_inventory": files}


def _worker(output):
    sys.path.insert(0, str(BACKEND))
    from config import HYDRUS_EXE, HYDRUS_RUN_DIR
    from models.hydrus_adapter import run_hydrus_model

    model_input = {"task_id": "t0_4", "plot_id": "phase0_inspection_only",
                   "farm_operations": [{"op_type": "irrigation", "amount": 25, "unit": "mm"}]}
    started = datetime.now(timezone.utc)
    result = run_hydrus_model(model_input)
    run_dir = HYDRUS_RUN_DIR / model_input["task_id"]
    record = inspect_run(run_dir, result)
    record.update({
        "label": "旧 HYDRUS adapter 本机运行核验；25mm 假设输入，非真实地块或田间验证",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": (datetime.now(timezone.utc) - started).total_seconds(),
        "run_directory": str(run_dir),
        "engine_sha256": hashlib.sha256(HYDRUS_EXE.read_bytes()).hexdigest()
        if HYDRUS_EXE.is_file() else None,
        "input": model_input,
        "legacy_adapter_status": result.get("status"),
        "legacy_error": result.get("hydrus_error"),
        "inspection_timeout_seconds": 60,
        "limitations": [
            "未修改数值引擎、模板或 adapter；日期、吸水比解析和建议文字的修正留到 T2.1",
            "当前模板只输出第 0 和第 7 天；逐日输出尚未改造",
            "模型使用通用模板参数，未经地块实测校准",
        ],
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": record["passed"], "checks": record["checks"],
                      "elapsed_seconds": record["elapsed_seconds"],
                      "output_times": record["output_times"], "record": str(output)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, default=PROJECT / "docs" / "zyh" / "hydrus_phase0_verification.json")
    arguments = parser.parse_args()
    output = arguments.out.resolve()
    if arguments.worker:
        _worker(output)
        return
    # Every inspection gets a fresh directory, so the old adapter's rmtree
    # cannot remove a previous run or a user's dataset.
    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    isolated = BACKEND / "runtime" / "phase0_verification" / run_stamp
    isolated.mkdir(parents=True)
    environment = dict(os.environ, COFFEE_RUNTIME_DIR=str(isolated),
                       PYTHONIOENCODING="utf-8", FLASK_DEBUG="0")
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
        stdout, stderr = process.communicate(timeout=10)
        output.write_text(json.dumps({"passed": False, "status": "timeout",
                                     "run_directory": str(isolated),
                                     "inspection_timeout_seconds": 60}, indent=2), encoding="utf-8")
        (isolated / "supervisor_stdout.txt").write_text(stdout, encoding="utf-8")
        (isolated / "supervisor_stderr.txt").write_text(stderr, encoding="utf-8")
        raise RuntimeError("HYDRUS inspection exceeded 60 seconds; own process tree stopped") from None
    (isolated / "supervisor_stdout.txt").write_text(stdout, encoding="utf-8")
    (isolated / "supervisor_stderr.txt").write_text(stderr, encoding="utf-8")
    if process.returncode:
        raise RuntimeError(stderr or stdout)
    print(stdout.strip())
    if not json.loads(output.read_text(encoding="utf-8"))["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
