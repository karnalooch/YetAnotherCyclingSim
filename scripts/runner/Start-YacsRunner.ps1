#requires -Version 7.4
[CmdletBinding()]
param([string]$WorkspaceConfig = (Join-Path $PSScriptRoot '../../../workspace.json'))
$ErrorActionPreference = 'Stop'
$WorkspaceConfig = (Resolve-Path -LiteralPath $WorkspaceConfig).Path
$config = Get-Content -LiteralPath $WorkspaceConfig -Raw | ConvertFrom-Json
$root = Split-Path -Parent $WorkspaceConfig
$relative = [string]$config.runner
if ([int]$config.schema_version -ne 1 -or [IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[\\/])\.\.([\\/]|$)') { throw 'Invalid configured runner path.' }
$runnerRoot = [IO.Path]::GetFullPath((Join-Path $root $relative))
if (-not $runnerRoot.StartsWith($root.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Runner must remain under workspace root.' }
if (-not (Test-Path -LiteralPath (Join-Path $runnerRoot '.runner'))) { throw 'Runner is not configured.' }
$identity = Get-Content -LiteralPath (Join-Path $runnerRoot '.runner') -Raw | ConvertFrom-Json
$listeners = @(Get-CimInstance Win32_Process -Filter "Name='Runner.Listener.exe'")
foreach ($listener in $listeners) {
    if (-not $listener.ExecutablePath) { throw 'Cannot identify an existing runner listener.' }
    $listenerRoot = Split-Path -Parent (Split-Path -Parent $listener.ExecutablePath)
    $identityPath = Join-Path $listenerRoot '.runner'
    if (-not (Test-Path -LiteralPath $identityPath)) { throw 'Cannot identify an existing runner registration.' }
    $existing = Get-Content -LiteralPath $identityPath -Raw | ConvertFrom-Json
    if ($existing.agentId -eq $identity.agentId -and $existing.serverUrl -eq $identity.serverUrl) {
        Write-Output 'Runner already active; reuse the current listener.'
        return
    }
}
if (Get-Process Runner.Worker -ErrorAction SilentlyContinue) { throw 'A runner worker is active.' }
$env:YACS_WORKSPACE_CONFIG = $WorkspaceConfig
$env:ACTIONS_RUNNER_HOOK_JOB_STARTED = Join-Path $PSScriptRoot 'Invoke-YacsJobStarted.ps1'
[Environment]::SetEnvironmentVariable('UE-ZenDataPath', (Join-Path $root 'cache/Zen'), 'Process')
$env:TEMP = Join-Path $root 'work/runner-temp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $root 'cache/pip'
$env:UV_CACHE_DIR = Join-Path $root 'cache/uv'
foreach ($path in @($env:TEMP, $env:PIP_CACHE_DIR, $env:UV_CACHE_DIR)) { [void][IO.Directory]::CreateDirectory($path) }
Start-Process -FilePath (Join-Path $runnerRoot 'run.cmd') -WorkingDirectory $runnerRoot -WindowStyle Hidden
Write-Output "Runner started from $runnerRoot in the interactive desktop session."
