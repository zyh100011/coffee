import json
import os
from pathlib import Path
import subprocess
import sys


BACKEND = Path(__file__).resolve().parents[1]


def _read_config(environment):
    process = subprocess.run(
        [sys.executable, "-c", "import config,json; print(json.dumps({"
         "'db':str(config.DATABASE_PATH),'runtime':str(config.RUNTIME_DIR),"
         "'hydrus':str(config.HYDRUS_EXE),'debug':config.DEBUG}))"],
        cwd=BACKEND, env=environment, capture_output=True, text=True, check=True,
    )
    return json.loads(process.stdout)


def test_runtime_and_database_can_be_isolated(tmp_path):
    environment = dict(os.environ, COFFEE_DB_PATH=str(tmp_path / "db" / "test.db"),
                       COFFEE_RUNTIME_DIR=str(tmp_path / "runs"), FLASK_DEBUG="0")
    values = _read_config(environment)
    assert Path(values["db"]) == tmp_path / "db" / "test.db"
    assert Path(values["runtime"]) == tmp_path / "runs"
    assert values["debug"] is False
    assert not (tmp_path / "db").exists()
    assert not (tmp_path / "runs").exists()


def test_empty_hydrus_setting_uses_bundled_engine():
    values = _read_config(dict(os.environ, HYDRUS_EXE=""))
    assert Path(values["hydrus"]) == BACKEND.parent / "server" / "hydrus_engine" / "H1D_CALC.EXE"


def test_dotenv_does_not_override_environment(tmp_path, monkeypatch):
    from config import _load_env

    settings = tmp_path / "settings.env"
    settings.write_text('\ufeff# local settings\nPHASE0_CONFIG_OVERRIDE=file\n'
                        'PHASE0_CONFIG_QUOTED="value=with spaces"\n'
                        'PHASE0_CONFIG_EMPTY=\ninvalid-line\n', encoding="utf-8")
    monkeypatch.setenv("PHASE0_CONFIG_OVERRIDE", "process")
    monkeypatch.delenv("PHASE0_CONFIG_QUOTED", raising=False)
    monkeypatch.delenv("PHASE0_CONFIG_EMPTY", raising=False)
    _load_env(settings)
    assert os.environ["PHASE0_CONFIG_OVERRIDE"] == "process"
    assert os.environ["PHASE0_CONFIG_QUOTED"] == "value=with spaces"
    assert os.environ["PHASE0_CONFIG_EMPTY"] == ""
    os.environ.pop("PHASE0_CONFIG_QUOTED")
    os.environ.pop("PHASE0_CONFIG_EMPTY")
