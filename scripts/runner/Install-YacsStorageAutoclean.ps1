#requires -Version 7.4
<#
.SYNOPSIS
  Deploy limited, owner-scheduled YACS auto-clean independent of GitHub Actions.
.DESCRIPTION
  Preview by default. -Install registers a daily audit; -EnableDeletion is
  additionally required for actual scheduled cleanup. Never restarts runner/UE.
#>
[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$EnableDeletion,
    [switch]$Uninstall
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Windows Task Scheduler is required.' }
if ($Install -and $Uninstall) { throw 'Choose one of -Install or -Uninstall.' }
if ($EnableDeletion -and -not $Install) { throw '-EnableDeletion requires -Install.' }
$user = [Security.Principal.WindowsIdentity]::GetCurrent()
$sid = $user.User.Value
if ($sid -in @('S-1-5-18','S-1-5-19','S-1-5-20')) {
    throw 'Do not schedule automatic deletion under a service identity.'
}
$name = "YACS Safe Autoclean-$sid"
if ($Uninstall) {
    $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($existing -and $existing.State -eq 'Running') {
        throw 'The maintenance task is running. Uninstall refused.'
    }
    if ($existing) { Unregister-ScheduledTask -TaskName $name -Confirm:$false }
    Write-Host 'Removed the current user task only. Source assets and receipts preserved.'
    return
}
$root = 'D:\yacs'
$dest = Join-Path $root 'maintenance'
$files = @('Invoke-YacsStorageAutoclean.ps1','Clear-YacsRunnerWorkspace.ps1')
$hashes = [ordered]@{}
foreach ($file in $files) {
    $src = Join-Path $PSScriptRoot $file
    if (-not (Test-Path -LiteralPath $src -PathType Leaf)) {
        throw "Missing source: $src"
    }
    $hashes[$file] = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
}
$pwsh = (Get-Command pwsh.exe -ErrorAction Stop).Source
$command = '-NoLogo -NoProfile -NonInteractive -File "{0}"{1} -WriteReceipt -Json' -f (Join-Path $dest $files[0]), $(if ($EnableDeletion) { ' -Apply' } else { '' })
Write-Host "Scheduled task: $name"
Write-Host "Scheduled: logon and daily at 12:00"
Write-Host "Command: $pwsh $command"
Write-Host ('Mode: ' + $(if ($EnableDeletion) { 'bounded Apply' } else { 'audit only' }))
Write-Host ('Source SHA256: ' + ($hashes | ConvertTo-Json -Compress))
if (-not $Install) {
    Write-Host 'PREVIEW ONLY: no task, file, or disk was modified.'
    return
}
if (-not (Test-Path -LiteralPath (Join-Path $root 'workspace.json') -PathType Leaf)) {
    throw 'Canonical workspace is missing.'
}
$existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
if ($existing -and $existing.State -eq 'Running') {
    throw 'The currently installed cleanup task is running.'
}
foreach ($path in @($root,$dest)) {
    if (Test-Path -LiteralPath $path) {
        $item = Get-Item -LiteralPath $path -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Junction/symlink installation prohibited: $path"
        }
    }
}
New-Item -Path $dest -ItemType Directory -Force | Out-Null
foreach ($file in $files) {
    $src = Join-Path $PSScriptRoot $file
    $dst = Join-Path $dest $file
    $temporary = "$dst.installing"
    Copy-Item -LiteralPath $src -Destination $temporary -Force
    if ((Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash -ne $hashes[$file]) {
        throw "Installed script failed SHA256 verification: $file"
    }
    Move-Item -LiteralPath $temporary -Destination $dst -Force
}
$action = New-ScheduledTaskAction -Execute $pwsh -Argument $command -WorkingDirectory $dest
$triggers = @((New-ScheduledTaskTrigger -AtLogOn -User $user.Name), (New-ScheduledTaskTrigger -Daily -At '12:00'))
$principal = New-ScheduledTaskPrincipal -UserId $user.Name -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 45) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $name -Action $action -Trigger $triggers -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "Installed $name. No runner restart or immediate disk deletion."
Write-Host "Manual audit: & '$dest\Invoke-YacsStorageAutoclean.ps1' -Json"
