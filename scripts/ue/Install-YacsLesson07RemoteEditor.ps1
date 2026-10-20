#requires -Version 7.4
<#
.SYNOPSIS
  Stage and request one owner-approved Lesson07 Editor through Task Scheduler.
.DESCRIPTION
  Requires the existing yacs-unreal-ci reservation and successful exact-SHA CI.
  -Apply is explicit. Without it, only read-only preflight runs. Existing tasks
  are never replaced, stopped or restarted. No canonical project files are written.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedHead,
    [Parameter(Mandatory)][ValidatePattern('^[1-9][0-9]{0,19}-[1-9][0-9]{0,5}$')][string]$RunToken,
    [string]$RepoRoot=(Join-Path $PSScriptRoot '../..'),
    [switch]$Apply
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root='D:\yacs\lesson07-remote'
$release=Join-Path $root "releases\$ExpectedHead"
$stateRoot=Join-Path $root "state\$ExpectedHead"
$reportRoot=Join-Path $root "reports\$RunToken"
$taskName='YACS Lesson07 Remote Editor'
$pwsh='D:\yacs\tools\powershell-7.6.6-win-x64\pwsh.exe'
$report=[ordered]@{
    schema_version=1;source_sha=$ExpectedHead;run_token=$RunToken;status='PREFLIGHT_PENDING'
    phase='SOURCE';error_type=$null;reason_code=$null;task=$taskName;task_registered=$false;task_start_requested=$false
    owner_sid_matches=$false;editor_stop_requested=$false;project_config_write_requested=$false
    package_save_requested=$false;native_world_verified=$false;post_job_survival_verified=$false
    session_report=(Join-Path $stateRoot 'session.json');preflight=$null;editor=$null
}
$failed=$false
function Stop-L07Install([string]$Reason) {
    $failure=[InvalidOperationException]::new('Lesson07 installation blocked.')
    $failure.Data['l07_reason']=$Reason
    throw $failure
}
function Assert-L07InstallPath([string]$Path) {
    $cursor=[IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if ((Test-Path -LiteralPath $cursor) -and
            ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { Stop-L07Install 'REPARSE_PATH' }
        $parent=Split-Path -Path $cursor -Parent
        if ($parent -eq $cursor) { break }
        $cursor=$parent
    }
}
function Assert-L07TaskSettings([object]$Task) {
    if (@($Task.Triggers | Where-Object { $null -ne $_ }).Count -ne 0 -or
        [Xml.XmlConvert]::ToTimeSpan([string]$Task.Settings.ExecutionTimeLimit) -ne [TimeSpan]::Zero -or
        $Task.Settings.RestartCount -ne 0 -or [string]$Task.Settings.MultipleInstances -cnotin @('IgnoreNew','2') -or
        $Task.Settings.AllowHardTerminate -ne $false -or $Task.Settings.StopIfGoingOnBatteries -ne $false -or
        $Task.Settings.DisallowStartIfOnBatteries -ne $false -or $Task.Settings.IdleSettings.StopOnIdleEnd -ne $false) {
        Stop-L07Install 'TASK_SETTINGS_MISMATCH'
    }
}
try {
    if (-not $IsWindows) { Stop-L07Install 'WINDOWS_REQUIRED' }
    $RepoRoot=[IO.Path]::GetFullPath((Resolve-Path -LiteralPath $RepoRoot).Path)
    Assert-L07InstallPath $RepoRoot
    if ([IO.Path]::GetFullPath($PSCommandPath) -ine (Join-Path $RepoRoot 'scripts/ue/Install-YacsLesson07RemoteEditor.ps1')) { Stop-L07Install 'EXECUTING_SOURCE_PATH' }
    $head=@(& git -C $RepoRoot rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1 -or $head[0] -cne $ExpectedHead) { Stop-L07Install 'SOURCE_HEAD' }
    $dirty=@(& git -C $RepoRoot status --porcelain --untracked-files=no 2>$null)
    if ($LASTEXITCODE -ne 0 -or $dirty.Count) { Stop-L07Install 'DIRTY_SOURCE' }
    $closure=@(
        'scripts/ue/Install-YacsLesson07RemoteEditor.ps1',
        'scripts/ue/Start-YacsLesson07RemoteEditor.ps1',
        'scripts/runner/Get-YacsUnrealHostState.ps1',
        'scripts/live_host/Assert-YacsLiveTaskPrincipal.ps1'
    )
    $proofs=@()
    foreach ($relative in $closure) {
        $tracked=@(& git -C $RepoRoot ls-files --error-unmatch -- $relative 2>$null)
        if ($LASTEXITCODE -ne 0 -or $tracked.Count -ne 1 -or $tracked[0] -cne $relative) { Stop-L07Install 'UNTRACKED_SOURCE' }
        $file=Join-Path $RepoRoot $relative
        Assert-L07InstallPath $file
        $item=Get-Item -LiteralPath $file -Force
        if ($item.PSIsContainer -or $item.Length -le 0 -or $item.Length -gt 256KB) { Stop-L07Install 'SOURCE_SIZE' }
        $proofs+=,[ordered]@{path=$relative;sha256=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()}
    }
    $report.phase='PREFLIGHT'
    $report.preflight=& (Join-Path $RepoRoot 'scripts/ue/Start-YacsLesson07RemoteEditor.ps1') -ExpectedHead $ExpectedHead -PreflightOnly
    if ($report.preflight.status -ceq 'ATTACH_EXISTING') {
        $report.status='ATTACH_EXISTING';$report.editor=$report.preflight.editor;$report.owner_sid_matches=$true
    } elseif ($report.preflight.status -cne 'PREFLIGHT_PASS') {
        $report.status=$report.preflight.status;$report.reason_code=$report.preflight.reason_code;$failed=$true
    } elseif (-not $Apply) {
        $report.status='DRY_RUN_PREFLIGHT_PASS'
    } else {
        $report.phase='TASK'
        Assert-L07InstallPath $root
        Assert-L07InstallPath $release
        Assert-L07InstallPath $stateRoot
        Assert-L07InstallPath $pwsh
        if (-not (Test-Path -LiteralPath $pwsh -PathType Leaf)) { Stop-L07Install 'POWERSHELL_MISSING' }
        . (Join-Path $RepoRoot 'scripts/live_host/Assert-YacsLiveTaskPrincipal.ps1')
        $user=[string](Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
        $sid=Resolve-YacsLiveWindowsSid -UserId $user
        if ($sid -in @('S-1-5-18','S-1-5-19','S-1-5-20')) { Stop-L07Install 'NO_CONSOLE_OWNER' }
        $actionArguments='-NoLogo -NoProfile -File "'+(Join-Path $release 'scripts/ue/Start-YacsLesson07RemoteEditor.ps1')+'" -ExpectedHead '+$ExpectedHead
        $existing=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($existing) {
            $null=Assert-YacsLiveTaskPrincipal -Task $existing -ExpectedSid $sid
            Assert-L07TaskSettings $existing
            # Even an identical completed task is one-shot; never repeat its launch.
            if (@($existing.Actions).Count -ne 1 -or $existing.Actions[0].Execute -ine $pwsh -or
                $existing.Actions[0].Arguments -cne $actionArguments -or $existing.Actions[0].WorkingDirectory -ine $release -or
                @($existing.Triggers | Where-Object { $null -ne $_ }).Count -ne 0) { Stop-L07Install 'TASK_DEFINITION_MISMATCH' }
            $report.status=if ([string]$existing.State -eq 'Running') { 'TASK_ALREADY_RUNNING' } else { 'BLOCKED_PRIOR_TASK' }
            $report.owner_sid_matches=$true
            $failed=$report.status -ceq 'BLOCKED_PRIOR_TASK'
        } else {
            if ((Test-Path -LiteralPath $release) -or (Test-Path -LiteralPath $stateRoot)) { Stop-L07Install 'PRIOR_RELEASE_RETAINED' }
            $pending=$release+'.incomplete'
            Assert-L07InstallPath $pending
            if (Test-Path -LiteralPath $pending) { Stop-L07Install 'INCOMPLETE_RELEASE_RETAINED' }
            [void][IO.Directory]::CreateDirectory($pending)
            foreach ($proof in $proofs) {
                $destination=Join-Path $pending $proof.path
                [void][IO.Directory]::CreateDirectory((Split-Path -Path $destination -Parent))
                Copy-Item -LiteralPath (Join-Path $RepoRoot $proof.path) -Destination $destination
                if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -cne $proof.sha256) { Stop-L07Install 'COPIED_SOURCE_HASH' }
            }
            $deadline=[DateTime]::UtcNow.AddMinutes(4)
            # The SID stays in this private installation record, never in reports.
            [ordered]@{
                schema_version=1;source_sha=$ExpectedHead;run_token=$RunToken;desktop_sid=$sid;files=$proofs
                start_permitted_until_utc=$deadline.ToString('o')
            } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $pending 'installation.json') -Encoding utf8
            Move-Item -LiteralPath $pending -Destination $release
            $action=New-ScheduledTaskAction -Execute $pwsh -Argument $actionArguments -WorkingDirectory $release
            $principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
            $settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 0 `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DisallowHardTerminate -DontStopOnIdleEnd
            # No trigger, password, elevation, task replacement or service change.
            Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -ErrorAction Stop | Out-Null
            $report.task_registered=$true
            $registered=Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
            $null=Assert-YacsLiveTaskPrincipal -Task $registered -ExpectedSid $sid
            Assert-L07TaskSettings $registered
            if (@($registered.Triggers | Where-Object { $null -ne $_ }).Count -ne 0 -or @($registered.Actions).Count -ne 1 -or
                $registered.Actions[0].Execute -ine $pwsh -or $registered.Actions[0].Arguments -cne $actionArguments -or
                $registered.Actions[0].WorkingDirectory -ine $release) { Stop-L07Install 'REGISTERED_TASK_MISMATCH' }
            $report.owner_sid_matches=$true
            $state=& (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
            if ($state.status -cne 'IDLE') { Stop-L07Install 'HOST_CHANGED_BEFORE_HANDOFF' }
            Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
            $report.task_start_requested=$true;$report.status='TASK_START_REQUESTED'
            # Hold the workflow reservation until the task started, blocked, or
            # its one-shot start permission expired. Timeout never stops its UE.
            while ([DateTime]::UtcNow -lt $deadline.AddSeconds(20)) {
                $statusFile=Join-Path $stateRoot 'session.json'
                if (Test-Path -LiteralPath $statusFile -PathType Leaf) {
                    Assert-L07InstallPath $statusFile
                    if ((Get-Item -LiteralPath $statusFile).Length -gt 256KB) { Stop-L07Install 'SESSION_REPORT_SIZE' }
                    $session=Get-Content -LiteralPath $statusFile -Raw | ConvertFrom-Json -Depth 16
                    if ($session.source_sha -cne $ExpectedHead) { Stop-L07Install 'SESSION_SOURCE' }
                    if ($session.editor) { $report.status=$session.status;$report.editor=$session.editor;break }
                    if ($session.status -like 'BLOCKED_*') { $report.status=$session.status;$failed=$true;break }
                }
                Start-Sleep -Seconds 2
            }
            if ($report.status -ceq 'TASK_START_REQUESTED') { $report.status='START_TIMEOUT_EDITOR_NOT_STOPPED';$failed=$true }
        }
    }
} catch {
    $report.status='BLOCKED_'+$report.phase;$report.error_type=$_.Exception.GetType().Name;$failed=$true
    $reason=[string]$_.Exception.Data['l07_reason']
    $report.reason_code=if ($reason -cmatch '^[A-Z][A-Z0-9_]{0,79}$') { $reason } else { 'SYSTEM_EXCEPTION' }
}
$report.completed_at_utc=[DateTime]::UtcNow.ToString('o')
if ($Apply -and $IsWindows) {
    try {
        Assert-L07InstallPath $reportRoot
        if (Test-Path -LiteralPath $reportRoot) { Stop-L07Install 'PRIOR_REPORT_RETAINED' }
        [void][IO.Directory]::CreateDirectory($reportRoot)
        $report | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath (Join-Path $reportRoot 'install.json') -Encoding utf8
    } catch { $report.report_write_failed=$true;$failed=$true }
}
$report | ConvertTo-Json -Depth 16 -Compress
if ($failed) { exit 1 }
