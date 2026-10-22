import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request

import pytest


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher requires Windows")
def test_powershell_launcher_from_another_directory(tmp_path):
    project = Path(__file__).resolve().parents[2]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    environment = dict(os.environ, COFFEE_DB_PATH=str(tmp_path / "database" / "launch.db"),
                       COFFEE_RUNTIME_DIR=str(tmp_path / "runtime"), FLASK_DEBUG="0")
    process = subprocess.Popen(
        [shutil.which("powershell.exe"), "-NoProfile", "-NonInteractive",
         "-ExecutionPolicy", "Bypass", "-File", str(project / "server" / "start_backend.ps1"),
         "-BindAddress", "127.0.0.1", "-Port", str(port)],
        cwd=tmp_path, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                pytest.fail(f"Launcher exited: {stdout!r} {stderr!r}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as response:
                    assert response.status == 200
                    assert json.load(response)["status"] == "ok"
                break
            except urllib.error.URLError:
                time.sleep(0.1)
        else:
            pytest.fail("Backend did not start within 20 seconds")
        assert (tmp_path / "database" / "launch.db").is_file()
        assert (tmp_path / "runtime" / "hydrus_runs").is_dir()
    finally:
        if process.poll() is None:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, check=False)
        process.communicate(timeout=10)
