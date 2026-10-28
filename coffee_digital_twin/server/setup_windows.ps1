param(
    [string]$Snapshot,
    [string]$RawRoot,
    [string]$TeamRoot,
    [switch]$SkipDependencyInstall
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $projectRoot
$backend = Join-Path $projectRoot 'backend'
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    & py -3.11 -m venv (Join-Path $projectRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 is required.' }
}
& $python -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3,11) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Use a Python 3.11 virtual environment.' }
if (-not $SkipDependencyInstall) {
    & $python -m pip install -r (Join-Path $backend 'requirements.lock.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
if (-not (Test-Path -LiteralPath (Join-Path $backend '.env'))) {
    Copy-Item -LiteralPath (Join-Path $backend '.env.example') -Destination (Join-Path $backend '.env')
}
if (-not $Snapshot) { $Snapshot = Join-Path $PSScriptRoot 'backup\frozen\data-v1.0.db' }
if (-not $RawRoot) { $RawRoot = Join-Path $repoRoot '实验资料\03_地块与监测数据\raw' }
if (-not $TeamRoot -and (Test-Path -LiteralPath (Join-Path $repoRoot 'JGY内容'))) { $TeamRoot = Join-Path $repoRoot 'JGY内容' }
$arguments = @((Join-Path $backend 'tools\setup_data.py'), '--snapshot', $Snapshot, '--raw-root', $RawRoot)
if ($TeamRoot) { $arguments += @('--team-root', $TeamRoot) }
$env:FLASK_DEBUG = '0'
$env:PYTHONIOENCODING = 'utf-8'
Push-Location $backend
try {
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Data setup failed; existing database was not replaced.' }
    Write-Host 'Configure the reachable evidence service and token in backend/.env. Do not share the token.'
    & $python (Join-Path $backend 'tools\selfcheck.py')
    if ($LASTEXITCODE -ne 0) { throw 'Selfcheck has pending items. Read the report; do not claim release readiness.' }
} finally { Pop-Location }
