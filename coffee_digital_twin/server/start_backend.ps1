param(
    [string]$BindAddress = '127.0.0.1',
    [int]$Port = 5000
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Missing .venv. Run: py -3.11 -m venv .venv; then .\.venv\Scripts\python -m pip install -r backend\requirements.txt'
}

$env:FLASK_HOST = $BindAddress
$env:FLASK_PORT = [string]$Port
$env:PYTHONIOENCODING = 'utf-8'
Push-Location $projectRoot
try {
    & $pythonPath (Join-Path $projectRoot 'backend\app.py')
    if ($LASTEXITCODE -ne 0) { throw "Backend exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
}
