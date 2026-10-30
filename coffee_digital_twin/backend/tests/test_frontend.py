from pathlib import Path
import shutil
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[2]/'miniprogram'
NODE=shutil.which('node') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
WCC=Path('E:/wechat tools/微信web开发者工具/code/package.nw/node_modules/wcc-exec/wcc.exe')
@pytest.mark.skipif(not WCC.is_file(),reason='WeChat WXML compiler unavailable')
def test_native_wxml_compilation(tmp_path):
    for index,path in enumerate(ROOT.rglob('*.wxml')):
        result=subprocess.run([str(WCC),'-o',str(tmp_path/f'{index}.js'),str(path)],capture_output=True,timeout=10)
        assert result.returncode==0,str(path)+result.stderr.decode('utf-8',errors='replace')
def test_frontend_behavior_contract():
    result=subprocess.run([NODE,str(Path(__file__).with_name('frontend_contract.cjs'))],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
def test_frontend_js_syntax():
    for path in ROOT.rglob('*.js'):
        result=subprocess.run([NODE,'--check',str(path)],capture_output=True,text=True,timeout=10)
        assert result.returncode==0,str(path)+result.stderr
