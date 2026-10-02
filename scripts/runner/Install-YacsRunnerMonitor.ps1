#requires -Version 7.4
[CmdletBinding()]
param(
    [string]$RunnerRoot = 'D:\actions-runner-yacs',
    [string]$InstallRoot,
    [string]$DesktopUser,
    [switch]$Verify,
    [switch]$Uninstall
)
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Windows is required.' }
$user = if ($DesktopUser) { $DesktopUser } else { [Security.Principal.WindowsIdentity]::GetCurrent().Name }
$sid = ([Security.Principal.NTAccount]::new($user)).Translate([Security.Principal.SecurityIdentifier]).Value
if ($sid -in @('S-1-5-18', 'S-1-5-19', 'S-1-5-20')) { throw 'A service identity cannot own the desktop monitor.' }
if ($DesktopUser -and -not $Uninstall) {
    $consoleUser = (Get-CimInstance Win32_ComputerSystem).UserName
    if (-not $consoleUser -or $consoleUser -ine $DesktopUser) { throw 'DesktopUser must match the currently logged-in console user.' }
}
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
[void][IO.Directory]::CreateDirectory($InstallRoot)
# This directory contains only this companion; do not rewrite an unrelated ACL.
$allowedNames = @('RunnerMonitor.psm1', 'Start-YacsRunnerMonitor.ps1', 'Show-YacsRunnerLog.ps1', 'logs')
if (@(Get-ChildItem -LiteralPath $InstallRoot -Force | Where-Object Name -notin $allowedNames).Count -gt 0) {
    throw 'InstallRoot contains unrelated files; choose a dedicated companion directory.'
}
$acl = [Security.AccessControl.DirectorySecurity]::new()
$acl.SetAccessRuleProtection($true, $false)
foreach ($entry in @(@($sid, 'Modify'), @('S-1-5-18', 'FullControl'), @('S-1-5-32-544', 'FullControl'))) {
    $rule = [Security.AccessControl.FileSystemAccessRule]::new(
        [Security.Principal.SecurityIdentifier]::new($entry[0]), $entry[1],
        'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.AddAccessRule($rule)
}
# Persist only DACL changes. Set-Acl with a fresh descriptor can request SACL
# privileges on an existing directory; no audit-policy change is intended here.
$directory = [IO.DirectoryInfo]::new($InstallRoot)
$currentAcl = [IO.FileSystemAclExtensions]::GetAccessControl($directory, [Security.AccessControl.AccessControlSections]::Access)
$desiredSddl = $acl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access)
$currentSddl = $currentAcl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access)
if ($currentSddl -ne $desiredSddl) {
    $currentAcl.SetSecurityDescriptorSddlForm($desiredSddl, [Security.AccessControl.AccessControlSections]::Access)
    [IO.FileSystemAclExtensions]::SetAccessControl($directory, $currentAcl)
}
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Stop-ScheduledTask -TaskName $taskName
    for ($i = 0; $i -lt 20 -and (Get-ScheduledTask -TaskName $taskName).State -eq 'Running'; $i++) { Start-Sleep -Milliseconds 250 }
    if ((Get-ScheduledTask -TaskName $taskName).State -eq 'Running') { throw 'Previous monitor did not stop; installation aborted.' }
}

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
$startedAfter = [DateTime]::UtcNow
Start-ScheduledTask -TaskName $taskName
Write-Host "Monitor installed for $user at $InstallRoot. Silent tray mode is active; automatic popups are disabled."
Write-Host 'No runner restart, hook, credential, debug setting or workload change was made.'

if ($Verify) {
    $log = Join-Path $InstallRoot 'logs/monitor.jsonl'
    $verified = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        if (-not (Test-Path -LiteralPath $log)) { continue }
        $records = @(Get-Content -LiteralPath $log -Tail 100 | ForEach-Object {
            try { $r = $_ | ConvertFrom-Json; if ([DateTime]$r.utc -ge $startedAfter) { $r } } catch { }
        })
        $started = $records | Where-Object kind -eq 'monitor_started' | Select-Object -Last 1
        $health = $records | Where-Object kind -eq 'health' | Select-Object -Last 1
        $errorRecord = $records | Where-Object kind -eq 'monitor_error' | Select-Object -Last 1
        if ($errorRecord) { throw "Monitor reported an error: $($errorRecord.type). Inspect the local monitor Status menu." }
        if ($started -and $health) {
            if ($started.popupsEnabled -ne $false) { throw 'Silent mode was not confirmed by the running monitor.' }
            $process = Get-Process -Id $started.processId -ErrorAction Stop
            if ($process.SessionId -le 0) { throw 'Monitor started outside an interactive session.' }
            $task = Get-ScheduledTask -TaskName $taskName
            if ($task.State -ne 'Running') { throw 'Monitor task is not running.' }
            if ($task.Principal.LogonType -ne 'Interactive' -or $task.Principal.RunLevel -ne 'Limited') { throw 'Unexpected monitor task security context.' }
            $verified = $true
            [pscustomobject]@{ task = $taskName; state = [string]$task.State; processId = $process.Id; sessionId = $process.SessionId; health = 'fresh'; notification = 'disabled-by-owner'; installRoot = $InstallRoot }
            break
        }
    }
    if (-not $verified) {
        $info = Get-ScheduledTaskInfo -TaskName $taskName
        throw "Monitor startup could not be verified within 60 seconds. Task result: $($info.LastTaskResult). Inspect task history and local logs."
    }
}
