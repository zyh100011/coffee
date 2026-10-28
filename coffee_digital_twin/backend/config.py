from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

def _load_env(path):
    """Load simple KEY=VALUE lines without overriding the process environment."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if key.isidentifier():
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)


_load_env(BASE_DIR / ".env")


def _env_path(name, default):
    # Empty .env entries use bundled defaults, rather than Path('').
    return Path(os.environ.get(name) or default).expanduser().resolve()


DATABASE_PATH = _env_path("COFFEE_DB_PATH", BASE_DIR / "database" / "coffee_demo.db")
DATABASE_DIR = DATABASE_PATH.parent

RUNTIME_DIR = _env_path("COFFEE_RUNTIME_DIR", BASE_DIR / "runtime")
APSIM_RUN_DIR = RUNTIME_DIR / "apsim_runs"
HYDRUS_RUN_DIR = RUNTIME_DIR / "hydrus_runs"
BEPS_RUN_DIR = RUNTIME_DIR / "beps_runs"
RESULT_JSON_DIR = RUNTIME_DIR / "result_json"

DEMO_DATA_DIR = BASE_DIR / "demo_data"

SERVER_DIR = PROJECT_DIR / "server"
APSIM_EXE = _env_path("APSIM_EXE", SERVER_DIR / "apsim_engine" / "Models.exe")
HYDRUS_EXE = _env_path("HYDRUS_EXE", SERVER_DIR / "hydrus_engine" / "H1D_CALC.EXE")
HYDRUS_TIMEOUT_S = int(os.getenv("HYDRUS_TIMEOUT_S") or "60")
HYDRUS_MODE = os.getenv("HYDRUS_MODE") or "live"
ALLOW_DEMO_FALLBACK = os.getenv("ALLOW_DEMO_FALLBACK", "0") == "1"
EVIDENCE_SERVICE_URL = os.getenv("EVIDENCE_SERVICE_URL") or "http://127.0.0.1:8001"
DATA_VERSION = os.getenv("DATA_VERSION", "")
SINGLE_PLOT_ID = os.getenv('SINGLE_PLOT_ID', 'plot_catimor_project')

HOST = os.getenv("FLASK_HOST") or "0.0.0.0"
PORT = int(os.getenv("FLASK_PORT") or "5000")
DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"


def ensure_dirs():
    for path in [
        DATABASE_DIR,
        APSIM_RUN_DIR,
        HYDRUS_RUN_DIR,
        BEPS_RUN_DIR,
        RESULT_JSON_DIR,
        DEMO_DATA_DIR,
        SERVER_DIR / "logs",
        SERVER_DIR / "backup" / "final_result_json",
    ]:
        path.mkdir(parents=True, exist_ok=True)
