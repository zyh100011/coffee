"""Generate documented hypothetical cases, not observed agronomic evidence."""
import copy
import json
from pathlib import Path
import shutil
import sys
import uuid

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from models import hydrus_adapter as hydrus
from services.tool_result import validate_tool_result


def generate():
    destination = BACKEND / "data" / "hydrus_cases"
    materials = BACKEND.parents[1] / "实验资料" / "04_三模型工具资料" / "HYDRUS" / "cases"
    destination.mkdir(parents=True, exist_ok=True)
    materials.mkdir(parents=True, exist_ok=True)
    previous = hydrus.HYDRUS_MODE, hydrus.ALLOW_DEMO_FALLBACK, hydrus.HYDRUS_EXE
    results = {}
    try:
        hydrus.HYDRUS_MODE, hydrus.ALLOW_DEMO_FALLBACK = "live", False
        for filename, extra in [("case_baseline_0mm.json", 0), ("case_irrig_20mm.json", 20)]:
            results[filename] = hydrus.run_hydrus_model({"task_id": "case_" + uuid.uuid4().hex,
                "plot_id": None, "start_date": "2026-09-01", "scenario": {"extra_irrigation_mm": extra}})
        results["case_missing_input.json"] = hydrus.run_hydrus_model({})
        hydrus.HYDRUS_EXE = BACKEND / "not_provided_hydrus_engine.exe"
        results["case_engine_failed.json"] = hydrus.run_hydrus_model({"start_date": "2026-09-01"})
    finally:
        hydrus.HYDRUS_MODE, hydrus.ALLOW_DEMO_FALLBACK, hydrus.HYDRUS_EXE = previous
    baseline, variant = results["case_baseline_0mm.json"], results["case_irrig_20mm.json"]
    assert baseline["status"] == variant["status"] == "success"
    assert baseline["parameter_version"] == variant["parameter_version"]
    assert abs(variant["inputs"]["daily_prec_cm"][0] - baseline["inputs"]["daily_prec_cm"][0] - 2) < .001
    profiles = [{point["depth_cm"]: point["theta"] for point in result["outputs"]["soil_profile_current"]}
                for result in (baseline, variant)]
    diff = {str(depth): profiles[1][depth] - value for depth,value in profiles[0].items()}
    assert diff["40"] != 0
    compare = {"input_label": "假设输入", "mode": "live", "status": "success",
               "note": "同一参数版本、同一窗口；不是地块校准或田间节水验证",
               "baseline_evidence_id": baseline["evidence_id"], "variant_evidence_id": variant["evidence_id"],
               "parameter_version": baseline["parameter_version"], "time_range": baseline["time_range"],
               "input_diff": [b-a for a,b in zip(baseline["inputs"]["daily_prec_cm"], variant["inputs"]["daily_prec_cm"])],
               "output_diff": {"theta_day7_by_depth": diff,
                   **{key: variant["outputs"][key] - baseline["outputs"][key]
                      for key in ("infiltration_depth_cm", "root_uptake_ratio")}}}
    for filename, result in results.items():
        assert not validate_tool_result(result), validate_tool_result(result)
        result["input_label"] = "假设输入"
        (destination / filename).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.copyfile(destination / filename, materials / filename)
    (destination / "case_compare_0_vs_20.json").write_text(json.dumps(compare, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copyfile(destination / "case_compare_0_vs_20.json", materials / "case_compare_0_vs_20.json")
    historic = BACKEND.parents[1] / "zyh" / "runtime" / "hydrus_runs" / "test_001" / "Error.msg"
    for directory in (destination, materials):
        shutil.copyfile(historic, directory / "historic_nonconverge_Error.msg")
    print(json.dumps({"cases": len(results), "parameter_version": baseline["parameter_version"],
                      "theta_40cm_difference": diff["40"]}, ensure_ascii=False))


if __name__ == "__main__":
    generate()
