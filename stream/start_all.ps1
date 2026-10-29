# Start the live pipeline: reset state -> stream job -> replay -> dashboard.
# Logs: stream\logs\stream.log, replay.log, dashboard_server.log
# This file is ASCII-only on purpose: Windows PowerShell 5.1 reads .ps1 as ANSI.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$logs = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

Write-Host "[1/6] stopping previous replay / stream / dashboard processes ..."
Get-CimInstance Win32_Process -Filter "name='python.exe'" |
    Where-Object {
        $_.CommandLine -like "*stream\10_replay.py*" -or
        $_.CommandLine -like "*stream\20_stream_job.py*" -or
        $_.CommandLine -like "*dashboard\server.py*" -or
        $_.CommandLine -like "*streamlit*app\main.py*"
    } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 3

Write-Host "[2/6] clearing spark temp and old hot layer ..."
$tmp = Join-Path $root "spark-tmp"
if (Test-Path $tmp) {
    Get-ChildItem $tmp | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}
foreach ($d in @("checkpoint", "spool", "hot")) {
    $p = Join-Path $PSScriptRoot $d
    if (Test-Path $p) { Remove-Item -Recurse -Force $p }
}
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "hot") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "spool\tmp") | Out-Null

Write-Host "[3/6] resetting run state ..."
& $py (Join-Path $PSScriptRoot "reset_run.py")
$control = Get-Content -Raw (Join-Path $PSScriptRoot "control.json") | ConvertFrom-Json

# WMI keeps the children alive after this window closes: their parent becomes
# WmiPrvSE, so closing the terminal does not send Ctrl+C to them.
function Start-Detached([string]$arguments, [string]$logName) {
    $log = Join-Path $logs ($logName + ".log")
    $line = 'cmd.exe /c ""' + $py + '" ' + $arguments + ' > "' + $log + '" 2>&1"'
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine = $line
        CurrentDirectory = $root
    } | Out-Null
}

Write-Host "[4/6] starting stream job and waiting for ack ..."
Start-Detached ('-u "' + (Join-Path $PSScriptRoot "20_stream_job.py") + '"') "stream"
$ackPath = Join-Path $PSScriptRoot "ack.json"
$acked = $false
for ($i = 0; $i -lt 180; $i++) {
    if (Test-Path $ackPath) {
        try {
            $ack = Get-Content -Raw $ackPath | ConvertFrom-Json
            if ([int]$ack.run_id -eq [int]$control.run_id) { $acked = $true; break }
        } catch {}
    }
    Start-Sleep -Milliseconds 500
}
if (-not $acked) {
    Write-Host "WARN: stream job did not acknowledge run $($control.run_id); check stream\logs\stream.log"
}

Write-Host "[5/6] starting replay and dashboard ..."
Start-Detached ('-u "' + (Join-Path $PSScriptRoot "10_replay.py") + '"') "replay"
Start-Detached ('-u "' + (Join-Path $root "dashboard\server.py") + '"') "dashboard_server"

Write-Host "[6/6] waiting for the dashboard ..."
$health = $false
for ($i = 0; $i -lt 45; $i++) {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:8601/api/health" -TimeoutSec 2 | Out-Null
        $health = $true
        break
    } catch {}
    Start-Sleep -Seconds 1
}

Write-Host ""
if ($health) {
    Write-Host "OK: dashboard is running."
    Write-Host "  Dashboard: http://127.0.0.1:8601/"
    Write-Host "  Pages:     /live /overview /geo /topics /cascade /influence /profile /relations /simulate"
} else {
    Write-Host "WARN: dashboard did not answer on http://127.0.0.1:8601/"
}
Write-Host "Logs: $logs"
Write-Host "Keep this window open; closing it is safe, the pipeline keeps running."
