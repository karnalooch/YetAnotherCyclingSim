#requires -Version 7.4
[CmdletBinding()]
param([Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedHead)
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Deployment requires the trusted Windows host.' }
if ($env:RUNNER_NAME -ne 'yacs-home-ue58') { throw 'Unexpected runner identity.' }
$head = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $head -ne $ExpectedHead) { throw 'Checkout does not match the authorized exact SHA.' }
$desktopUser = (Get-CimInstance Win32_ComputerSystem).UserName
if (-not $desktopUser) { throw 'No console user is logged in. Installation cannot verify the desktop tray monitor.' }
$workRoot = Split-Path $env:RUNNER_TEMP -Parent
$runnerRoot = Split-Path $workRoot -Parent
if (-not (Test-Path (Join-Path $runnerRoot '.runner'))) { throw 'Unable to identify the installed runner root.' }
& (Join-Path $PSScriptRoot 'Test-YacsRunnerMonitor.ps1')
$priorLog = Join-Path (Split-Path $runnerRoot -Parent) 'runner-monitor/logs/monitor.jsonl'
$priorHealth = $null; $priorCompleted = $null; $priorAlive = $false
if (Test-Path $priorLog) {
    $records = @(Get-Content $priorLog -Tail 200 | ForEach-Object {
        try { $_ | ConvertFrom-Json } catch { }
    })
    $priorHealth = $records | Where-Object kind -eq 'health' | Select-Object -Last 1
    $priorCompleted = $records | Where-Object kind -eq 'completed' | Select-Object -Last 1
    $priorStart = $records | Where-Object kind -eq 'monitor_started' | Select-Object -Last 1
    if ($priorHealth -and $priorStart -and ([DateTime]::UtcNow - [DateTime]$priorHealth.utc).TotalSeconds -lt 120) {
        $priorProcess = Get-Process -Id $priorStart.processId -ErrorAction SilentlyContinue
        $priorAlive = $null -ne $priorProcess -and $priorProcess.SessionId -gt 0
    }
}
$installation = & (Join-Path $PSScriptRoot 'Install-YacsRunnerMonitor.ps1') -RunnerRoot $runnerRoot -DesktopUser $desktopUser -Verify
if (-not $installation -or $installation.health -ne 'fresh') { throw 'No verified installation receipt.' }
$serviceState = 'not registered'
$serviceFile = Join-Path $runnerRoot '.service'
if (Test-Path $serviceFile) { $serviceState = [string](Get-Service -Name (Get-Content $serviceFile -Raw).Trim()).Status }
$receipt = [ordered]@{
    schema = 1
    sha = $ExpectedHead
    utc = [DateTime]::UtcNow.ToString('o')
    installed = $true
    taskState = $installation.state
    sessionId = $installation.sessionId
    processId = $installation.processId
    health = $installation.health
    notification = $installation.notification
    serviceState = $serviceState
    serviceChanged = $false
    rebootProof = 'not performed'
    previousMonitorAlive = $priorAlive
    previousCompletion = if ($priorCompleted) { [string]$priorCompleted.result } else { 'not observed' }
    files = @(Get-ChildItem $installation.installRoot -File | Where-Object Extension -in @('.ps1', '.psm1') | ForEach-Object {
        @{ name = $_.Name; sha256 = (Get-FileHash $_.FullName -Algorithm SHA256).Hash }
    })
}
[void][IO.Directory]::CreateDirectory('monitor-proof')
$receipt | ConvertTo-Json -Depth 5 | Set-Content 'monitor-proof/installation.json' -Encoding utf8
$receipt | ConvertTo-Json -Depth 5 | Write-Host
Write-Host 'PASS: desktop task, interactive process, fresh health and silent mode verified.'
