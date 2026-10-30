# Compatibility entry: use the portable Python 3.11 launcher.
param([string]$BindAddress = '127.0.0.1', [int]$Port = 5000)
& (Join-Path $PSScriptRoot '..\server\start_demo.ps1') -BindAddress $BindAddress -Port $Port
