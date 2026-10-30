import pytest

from tools.verify_hydrus_baseline import inspect_run


@pytest.mark.parametrize("status,error,final_time,expected", [
    ("success", False, 7, True),
    ("success_with_fallback", False, 7, False),
    ("success", True, 7, False),
    ("success", False, 3, False),
])
def test_verification_requires_real_success_and_complete_outputs(tmp_path, status, error, final_time, expected):
    # Synthetic artifacts test the verifier, never the scientific engine.
    (tmp_path / "T_Level.out").write_text("test fixture only", encoding="utf-8")
    (tmp_path / "Nod_Inf.out").write_text(
        f"Date: 14.10.2026    Time: 16: 9:48\n Time: 0.0\n Time: {final_time}.0\n",
        encoding="utf-8")
    if error:
        (tmp_path / "Error.msg").write_text("test error", encoding="utf-8")
    record = inspect_run(tmp_path, {"status": status})
    assert record["passed"] is expected
    assert record["output_times"] == [0, final_time]


def test_missing_outputs_do_not_pass(tmp_path):
    record = inspect_run(tmp_path, {"status": "success"})
    assert record["passed"] is False
    assert record["checks"]["t_level_exists"] is False
    assert record["checks"]["nod_inf_exists"] is False
