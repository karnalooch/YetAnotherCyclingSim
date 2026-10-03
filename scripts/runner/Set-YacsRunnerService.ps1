#requires -Version 7.4
#requires -RunAsAdministrator
[CmdletBinding(SupportsShouldProcess)]
param([string]$RunnerRoot = 'D:\actions-runner-yacs')
$ErrorActionPreference = 'Stop'
$RunnerRoot = (Resolve-Path -LiteralPath $RunnerRoot).Path
$serviceFile = Join-Path $RunnerRoot '.service'
if (-not (Test-Path -LiteralPath $serviceFile)) {
    throw 'Runner has no registered service. Keep the interactive GPU runner unchanged. Native service registration requires config.cmd and a separate GPU/visual compatibility proof; this script does not re-register runners.'
}
$name = (Get-Content -LiteralPath $serviceFile -Raw).Trim()
if ($name -notmatch '^actions\.runner\.[A-Za-z0-9_.-]+$') { throw 'Unexpected runner service name.' }
$service = Get-Service -Name $name
if ($service.Status -ne 'Running') {
    $listenerPath = Join-Path $RunnerRoot 'bin/Runner.Listener.exe'
    $listeners = @(Get-CimInstance Win32_Process -Filter "Name='Runner.Listener.exe'" | Where-Object {
        $_.ExecutablePath -and [IO.Path]::GetFullPath($_.ExecutablePath) -ieq [IO.Path]::GetFullPath($listenerPath)
    })
    if ($listeners.Count -gt 0) { throw 'This runner is already active outside the stopped service. Refusing a duplicate listener; plan an idle, GPU-validated migration.' }
}
# Never change a running workload. This is conservative across all runners on the host.
if (Get-Process -Name 'Runner.Worker' -ErrorAction SilentlyContinue) { throw 'A runner job is active. Retry after it finishes.' }
if ($PSCmdlet.ShouldProcess($name, 'Configure automatic startup and service recovery without restart')) {
    Set-Service -Name $name -StartupType Automatic
    & sc.exe failure $name reset= 86400 actions= restart/60000/restart/120000/restart/300000
    if ($LASTEXITCODE -ne 0) { throw "sc.exe failure returned $LASTEXITCODE" }
    if ($service.Status -ne 'Running') { Start-Service -Name $name }
    Get-Service -Name $name | Select-Object Name, Status, StartType
}
