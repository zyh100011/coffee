param([switch]$Apply, [int]$ServicePort = 5000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$env:FLASK_DEBUG = '0'
$env:PYTHONIOENCODING = 'utf-8'
$arguments = @((Join-Path $PSScriptRoot 'reset_demo.py'), '--service-port', [string]$ServicePort)
if ($Apply) { $arguments += '--apply' }
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Reset did not complete. Original data and backups must be preserved.' }
