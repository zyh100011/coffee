"""Exercise destructive-path guards using isolated synthetic snapshots only."""
from contextlib import closing
import json
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import pytest
from tests.test_seed_demo import snapshot
from tools.reset_demo import reset


def test_reset_preview_archive_and_restore(tmp_path, monkeypatch):
    source, _ = snapshot(tmp_path, monkeypatch)
    with closing(sqlite3.connect(source)) as conn:
        with conn:
            for table in ('data_versions', 'raw_files', 'obs_long'):
                conn.execute('UPDATE '+table+" SET data_version='data-v1.0'")
    current = tmp_path/'current.db'; shutil.copy2(source, current)
    with closing(sqlite3.connect(current)) as conn:
        with conn:
            conn.execute("INSERT INTO assistant_traces(trace_id,message,created_at) VALUES ('test-trace','TEST ONLY','now')")
    runtime = tmp_path/'runtime'; runtime.mkdir(); (runtime/'keep.txt').write_text('saved')
    archives = tmp_path/'results'
    preview = reset(source, current, runtime, archives, tmp_path)
    assert not preview['applied'] and not archives.exists()
    assert (runtime/'keep.txt').read_text() == 'saved'
    result = reset(source, current, runtime, archives, tmp_path, apply=True, service_port=0)
    archived = Path(result['archive'])
    assert (archived/'runtime/keep.txt').read_text() == 'saved'
    assert 'test-trace' in (archived/'assistant_traces.jsonl').read_text()
    with closing(sqlite3.connect(current)) as conn:
        assert conn.execute('SELECT COUNT(*) FROM assistant_traces').fetchone()[0] == 0
        assert conn.execute('SELECT value FROM obs_long').fetchone()[0] == .2
    with closing(sqlite3.connect(archived/'before_reset.db')) as conn:
        assert conn.execute('SELECT COUNT(*) FROM assistant_traces').fetchone()[0] == 1


def test_reset_rejects_paths_and_running_service(tmp_path, monkeypatch):
    source, _ = snapshot(tmp_path, monkeypatch)
    current = tmp_path/'current.db'; shutil.copy2(source, current)
    with pytest.raises(ValueError, match='重叠'):
        reset(source, current, tmp_path/'runtime', tmp_path/'runtime/archive', tmp_path)
    with pytest.raises(ValueError, match='工作区'):
        reset(source, current, tmp_path.parent, tmp_path/'archive', tmp_path)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); listener.listen()
        with pytest.raises(ValueError, match='停止服务'):
            reset(source, current, tmp_path/'runtime', tmp_path/'archive', tmp_path,
                  apply=True, service_port=listener.getsockname()[1])
    assert not (tmp_path/'archive').exists()


def test_powershell_scripts_parse():
    app = Path(__file__).resolve().parents[2]
    scripts = [app/'server/setup_windows.ps1', app/'server/start_demo.ps1', app/'backend/tools/reset_demo.ps1']
    literals=','.join("'"+str(path).replace("'","''")+"'" for path in scripts)
    command = '$bad=$false; foreach($file in @('+literals+')){$tokens=$null;$errors=$null;[System.Management.Automation.Language.Parser]::ParseFile($file,[ref]$tokens,[ref]$errors) | Out-Null;if($errors){$errors | Out-String | Write-Output;$bad=$true}};if($bad){exit 1}'
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout+result.stderr


def test_mock_launch_configuration():
    from tools.startup_config import local_mock_target
    assert local_mock_target('http://127.0.0.1:8001')
    assert local_mock_target('http://localhost:8001/')
    for url in ('http://192.168.1.2:8001','http://127.0.0.1:8001/api','http://user:secret@127.0.0.1:8001','https://127.0.0.1:8001'):
        assert not local_mock_target(url)


def test_standalone_mock_route_from_another_directory(tmp_path):
    import os,time,sys
    import requests
    script=Path(__file__).resolve().parents[1]/'tools/mock_evidence_service.py'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    environment=dict(os.environ);environment.pop('PYTHONPATH',None)
    process=subprocess.Popen([sys.executable,str(script),'--port',str(port)],cwd=tmp_path,
        env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    try:
        url=f'http://127.0.0.1:{port}'
        for attempt in range(40):
            try:
                if requests.get(url+'/health',timeout=.5).ok:break
            except requests.RequestException:pass
            time.sleep(.1)
        response=requests.post(url+'/v1/route',json={'message':'40cm最近7天墒情怎么样？','plot_context':{'plot_id':'test'}},timeout=3)
        assert response.status_code==200 and response.json()['mock']
        assert response.json()['tool_calls'][0]['arguments']['depth_cm']==40
    finally:
        process.terminate();process.wait(timeout=5)
