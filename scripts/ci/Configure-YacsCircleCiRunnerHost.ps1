#requires -RunAsAdministrator
<#
.SYNOPSIS
Configure the YACS CircleCI machine-runner host so built-in workspace/cache steps use D: and can see gzip.

.DESCRIPTION
This is a one-time host bootstrap. It:
- keeps CircleCI runner working data on D:
- keeps task-agent downloads on D:
- exposes the existing Git for Windows gzip/tar binaries to the runner service through the machine PATH
- restarts the CircleCI service so the runner/task-agent inherit the updated host environment

No UE seed payload is copied to C:. The only C: path referenced is the already-installed Git for Windows toolchain.
#>

[CmdletBinding()]
param(
    [string]$RunnerRoot = 'D:\CircleCI\YACS-Runner',
    [switch]$NoRestart
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$workDir = Join-Path $RunnerRoot 'Workdir'
$taskAgentDir = Join-Path $RunnerRoot 'TaskAgent'
$tempDir = Join-Path $RunnerRoot 'Temp'
$gitUsrBin = 'C:\Program Files\Git\usr\bin'
$gzipPath = Join-Path $gitUsrBin 'gzip.exe'
$tarPath = Join-Path $gitUsrBin 'tar.exe'

foreach ($path in @($workDir, $taskAgentDir, $tempDir)) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}

if (-not (Test-Path -LiteralPath $gzipPath -PathType Leaf)) {
    throw "Git for Windows gzip is missing: $gzipPath"
}
if (-not (Test-Path -LiteralPath $tarPath -PathType Leaf)) {
    throw "Git for Windows tar is missing: $tarPath"
}

$machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
$entries = @($machinePath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if (-not ($entries | Where-Object { $_.TrimEnd('\') -ieq $gitUsrBin.TrimEnd('\') })) {
    [Environment]::SetEnvironmentVariable('Path', "$gitUsrBin;$machinePath", 'Machine')
    Write-Host "Added Git for Windows usr\bin to machine PATH: $gitUsrBin"
} else {
    Write-Host "Machine PATH already contains Git for Windows usr\bin."
}

[Environment]::SetEnvironmentVariable('CIRCLECI_RUNNER_WORK_DIR', $workDir, 'Machine')
[Environment]::SetEnvironmentVariable('CIRCLECI_RUNNER_TASK_AGENT_DIRECTORY', $taskAgentDir, 'Machine')

Write-Host "CIRCLECI_RUNNER_WORK_DIR=$workDir"
Write-Host "CIRCLECI_RUNNER_TASK_AGENT_DIRECTORY=$taskAgentDir"
Write-Host "gzip=$gzipPath"
Write-Host "tar=$tarPath"

$services = @(Get-Service | Where-Object {
    $_.Name -match 'circleci' -or $_.DisplayName -match 'circleci'
})

if ($services.Count -eq 0) {
    throw 'No CircleCI Windows service was found. Restart the machine-runner process manually after this script.'
}

Write-Host ('CircleCI service(s): ' + (($services | ForEach-Object Name) -join ', '))

if (-not $NoRestart) {
    foreach ($service in $services) {
        Write-Host "Restarting CircleCI service: $($service.Name)"
        Restart-Service -Name $service.Name -Force
        (Get-Service -Name $service.Name).WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
    }
    Write-Host 'YACS CircleCI host bootstrap: PASS'
} else {
    Write-Host 'Host settings updated. Restart the CircleCI service before the next pipeline.'
}
