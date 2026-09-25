<#
.SYNOPSIS
Configure a foreground/manual YACS CircleCI machine runner without administrator rights.

.DESCRIPTION
Persists runner settings for the current Windows user and updates the current PowerShell
process so a subsequently launched circleci-runner inherits:
- Git for Windows gzip/tar on PATH
- runner work directory on D:
- task-agent directory on D:

No service installation or machine-level registry writes are required.
#>

[CmdletBinding()]
param(
    [string]$RunnerRoot = 'D:\CircleCI\YACS-Runner'
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

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$userEntries = @($userPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if (-not ($userEntries | Where-Object { $_.TrimEnd('\') -ieq $gitUsrBin.TrimEnd('\') })) {
    $newUserPath = if ([string]::IsNullOrWhiteSpace($userPath)) { $gitUsrBin } else { "$gitUsrBin;$userPath" }
    [Environment]::SetEnvironmentVariable('Path', $newUserPath, 'User')
    Write-Host "Added Git for Windows usr\bin to USER PATH: $gitUsrBin"
} else {
    Write-Host "USER PATH already contains Git for Windows usr\bin."
}

[Environment]::SetEnvironmentVariable('CIRCLECI_RUNNER_WORK_DIR', $workDir, 'User')
[Environment]::SetEnvironmentVariable('CIRCLECI_RUNNER_TASK_AGENT_DIRECTORY', $taskAgentDir, 'User')

$env:PATH = "$gitUsrBin;$env:PATH"
$env:CIRCLECI_RUNNER_WORK_DIR = $workDir
$env:CIRCLECI_RUNNER_TASK_AGENT_DIRECTORY = $taskAgentDir
$env:TEMP = $tempDir
$env:TMP = $tempDir

$gzipCommand = Get-Command gzip.exe -ErrorAction Stop
$tarCommand = Get-Command tar.exe -ErrorAction Stop

Write-Host ''
Write-Host 'YACS CircleCI foreground-runner bootstrap: PASS'
Write-Host "  WORKDIR   = $env:CIRCLECI_RUNNER_WORK_DIR"
Write-Host "  TASKAGENT = $env:CIRCLECI_RUNNER_TASK_AGENT_DIRECTORY"
Write-Host "  TEMP      = $env:TEMP"
Write-Host "  gzip      = $($gzipCommand.Source)"
Write-Host "  tar       = $($tarCommand.Source)"
Write-Host ''
Write-Host 'IMPORTANT: launch/relaunch circleci-runner from THIS PowerShell window (or a new window after sign-in) before triggering the next pipeline.'
