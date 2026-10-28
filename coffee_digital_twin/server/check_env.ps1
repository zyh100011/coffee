$ErrorActionPreference = 'Stop'
$python = Join-Path (Split-Path -Parent $PSScriptRoot) '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run setup_windows.ps1 first.' }
$env:PYTHONIOENCODING = 'utf-8'
& $python (Join-Path (Split-Path -Parent $PSScriptRoot) 'backend\tools\selfcheck.py')
exit $LASTEXITCODE
