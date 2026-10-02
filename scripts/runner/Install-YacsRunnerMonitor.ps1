#requires -Version 7.4
[CmdletBinding()]
param(
    [string]$RunnerRoot = 'D:\actions-runner-yacs',
    [string]$InstallRoot,
    [switch]$Uninstall
)
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Windows is required.' }
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$taskName = "YACS Runner Monitor-$sid"
if ($Uninstall) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        Stop-ScheduledTask -TaskName $taskName
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    Write-Host 'Monitor task removed. Runner configuration and logs were preserved.'
    return
}
$RunnerRoot = (Resolve-Path -LiteralPath $RunnerRoot).Path
if (-not (Test-Path -LiteralPath (Join-Path $RunnerRoot '_diag'))) { throw 'Runner _diag directory is missing.' }
if (-not $InstallRoot) { $InstallRoot = Join-Path (Split-Path $RunnerRoot -Parent) 'yacs-runner-monitor' }
$InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
foreach ($path in @($RunnerRoot, $InstallRoot)) {
    if ($path -match '["\r\n]') { throw 'Unsupported quote/newline in installation path.' }
}
# Keep installed code outside job workspaces and runner self-update directories.
if ($InstallRoot.StartsWith($RunnerRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase) -or $InstallRoot -eq $RunnerRoot) {
    throw 'InstallRoot must be outside RunnerRoot.'
}
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) { Stop-ScheduledTask -TaskName $taskName }
[void][IO.Directory]::CreateDirectory($InstallRoot)
foreach ($name in @('RunnerMonitor.psm1', 'Start-YacsRunnerMonitor.ps1', 'Show-YacsRunnerLog.ps1')) {
    $source = Join-Path $PSScriptRoot $name
    $target = Join-Path $InstallRoot $name
    if ([IO.Path]::GetFullPath($source) -ne [IO.Path]::GetFullPath($target)) { Copy-Item -LiteralPath $source -Destination $target -Force }
}
$pwsh = (Get-Command pwsh.exe -ErrorAction Stop).Source
$script = Join-Path $InstallRoot 'Start-YacsRunnerMonitor.ps1'
$arguments = '-NoLogo -NoProfile -STA -WindowStyle Hidden -File "{0}" -RunnerRoot "{1}"' -f $script, $RunnerRoot
$action = New-ScheduledTaskAction -Execute $pwsh -Argument $arguments -WorkingDirectory $InstallRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Host "Monitor installed for $user at $InstallRoot. Select Test notification from its tray menu."
Write-Host 'No runner restart, hook, credential, debug setting or workload change was made.'
