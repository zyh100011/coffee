param(
    [string]$BindAddress = '127.0.0.1',
    [int]$Port = 5000,
    [switch]$StartMock,
    [switch]$NonInteractive
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $projectRoot 'backend'
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run server/setup_windows.ps1 first.' }
$mockProcess = $null
$env:FLASK_DEBUG = '0'
$env:PYTHONIOENCODING = 'utf-8'
Push-Location $backend
try {
    # Read only a boolean decision; never emit configuration URLs or credentials.
    $localMockTarget = & $python (Join-Path $backend 'tools\startup_config.py')
    if ($LASTEXITCODE -ne 0) { throw 'Invalid evidence-service configuration.' }
    $tcp = [System.Net.Sockets.TcpClient]::new()
    try { $active = $tcp.ConnectAsync('127.0.0.1', 8001).Wait(800) -and $tcp.Connected } catch { $active = $false } finally { $tcp.Dispose() }
    if ($localMockTarget.Trim() -eq '1' -and -not $active) {
        $allowMock = $StartMock.IsPresent
        if (-not $allowMock -and -not $NonInteractive) { $allowMock = (Read-Host 'Local evidence service is unavailable. Start MOCK for integration only? [y/N]') -eq 'y' }
        if ($allowMock) {
            $mockScript = Join-Path $backend 'tools\mock_evidence_service.py'
            $mockProcess = Start-Process -FilePath $python -ArgumentList @(('"' + $mockScript + '"'), '--port', '8001') -WorkingDirectory $backend -WindowStyle Hidden -PassThru
            Write-Host 'MOCK: rule-based integration replies, not the real model or literature retrieval.' -ForegroundColor Red
        }
    } elseif ($StartMock -and $localMockTarget.Trim() -ne '1') {
        throw 'Refusing to override a remote evidence service with MOCK.'
    }
    Write-Host 'No authentication: trusted local network only. Close the service after the demo.'
    Write-Host "Developer tools URL: http://127.0.0.1:$Port"
    if ($BindAddress -eq '0.0.0.0') {
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' } |
            ForEach-Object { Write-Host "Phone preview: http://$($_.IPAddress):$Port" }
    }
    & (Join-Path $PSScriptRoot 'start_backend.ps1') -BindAddress $BindAddress -Port $Port
} finally {
    if ($mockProcess -and -not $mockProcess.HasExited) { Stop-Process -Id $mockProcess.Id }
    Pop-Location
}
