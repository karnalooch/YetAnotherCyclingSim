#requires -Version 7.4
<#
.SYNOPSIS
  Stage and request one owner-approved Lesson07 Editor through Task Scheduler.
.DESCRIPTION
  Requires the existing yacs-unreal-ci reservation and successful exact-SHA CI.
  -Apply is explicit. Without it, only read-only preflight runs. Only the pinned
  failed 457 or closed 602/de903 task may have its action migrated; no task is stopped
  or unregistered. Existing releases/state and canonical files are retained.
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
    handoff_step=$null;error_inner_type=$null;error_hresult=$null;error_native_code=$null
    task_migrated=$false;task_migration=$null
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
function Get-L07FailedTaskPin {
    # Original bytes from run 39510976391/job 118934957954; never a generic retry.
    return @{
        source_sha='457dc899adb858abee69c8ec1c4174cb7bc8032d'
        run_token='39510976391-1'
        session_sha256='57fa56edbd2d1eff4be7f3f765227457754f8dce298e2212a4ed5cff1e3ed1d9'
        files=@{
            'scripts/ue/Install-YacsLesson07RemoteEditor.ps1'='da93a7dbe2818af78af21fe44b853177bd240a2c8c37b251c4e5f038450d4271'
            'scripts/ue/Start-YacsLesson07RemoteEditor.ps1'='c7d2f4c400dec3324be53b4ce0c7098b2c03f793820da01c94ec0c6a68ead75f'
            'scripts/runner/Get-YacsUnrealHostState.ps1'='73506d6f1707faa33c97797f6e57d1d22e381eb72787377c3bdbb66fe0d2c346'
            'scripts/live_host/Assert-YacsLiveTaskPrincipal.ps1'='2bd54cda4f1a1aa3ca3af3d3a94d7013317bfe570910701fc7c17d946d0af0b2'
        }
    }
}
function Assert-L07FailedTaskData(
    [object]$Task, [object]$TaskInfo, [Collections.IDictionary]$PriorInstall,
    [Collections.IDictionary]$PriorSession, [string]$SessionSha256,
    [string]$ResolvedTaskSid, [string]$ExpectedSid, [string]$HostStatus,
    [DateTime]$NowUtc=[DateTime]::UtcNow
) {
    $pin=Get-L07FailedTaskPin
    $priorRelease='D:\yacs\lesson07-remote\releases\'+$pin.source_sha
    # Reproduce the original Windows Join-Path expression exactly. The literal
    # fallback is only for data-only fixtures on hosts without a D: provider.
    $priorScript=if ($IsWindows) { Join-Path $priorRelease 'scripts/ue/Start-YacsLesson07RemoteEditor.ps1' }
        else { $priorRelease+'\scripts\ue\Start-YacsLesson07RemoteEditor.ps1' }
    $arguments='-NoLogo -NoProfile -File "'+$priorScript+'" -ExpectedHead '+$pin.source_sha
    if ($HostStatus -cne 'IDLE' -or [string]$Task.State -cne 'Ready' -or $TaskInfo.LastTaskResult -ne 1) { Stop-L07Install 'MIGRATION_NOT_IDLE_FAILED' }
    if ($Task.TaskName -cne 'YACS Lesson07 Remote Editor' -or $Task.TaskPath -cne '\' -or
        @($Task.Actions).Count -ne 1 -or $Task.Actions[0].Execute -ine 'D:\yacs\tools\powershell-7.6.6-win-x64\pwsh.exe' -or
        $Task.Actions[0].Arguments -cne $arguments -or $Task.Actions[0].WorkingDirectory -ine $priorRelease) { Stop-L07Install 'MIGRATION_TASK_DEFINITION' }
    Assert-L07TaskSettings $Task
    if ($ResolvedTaskSid -cne $ExpectedSid -or $ExpectedSid -cnotmatch '^S-1-\d+-' -or
        $ExpectedSid -cin @('S-1-5-18','S-1-5-19','S-1-5-20') -or
        [string]$Task.Principal.RunLevel -cne 'Limited' -or [string]$Task.Principal.LogonType -cnotin @('Interactive','InteractiveToken') -or
        $PriorInstall['desktop_sid'] -isnot [string] -or $PriorInstall['desktop_sid'] -cne $ExpectedSid) { Stop-L07Install 'MIGRATION_OWNER' }
    if ($PriorInstall['source_sha'] -isnot [string] -or $PriorInstall['source_sha'] -cne $pin.source_sha -or
        $PriorInstall['run_token'] -isnot [string] -or $PriorInstall['run_token'] -cne $pin.run_token -or
        @($PriorInstall['files']).Count -ne $pin.files.Count) { Stop-L07Install 'MIGRATION_RELEASE_IDENTITY' }
    $oldDeadline=$PriorInstall['start_permitted_until_utc']
    if ($oldDeadline -isnot [DateTime] -or $oldDeadline.Kind -ne [DateTimeKind]::Utc -or
        $NowUtc.Kind -ne [DateTimeKind]::Utc -or $oldDeadline -ge $NowUtc) { Stop-L07Install 'MIGRATION_PERMISSION_NOT_EXPIRED' }
    foreach ($relative in $pin.files.Keys) {
        $entries=@($PriorInstall['files'] | Where-Object { $_ -is [Collections.IDictionary] -and $_['path'] -is [string] -and $_['path'] -ceq $relative })
        if ($entries.Count -ne 1 -or $entries[0]['sha256'] -isnot [string] -or $entries[0]['sha256'] -cne $pin.files[$relative]) { Stop-L07Install 'MIGRATION_SOURCE_HASH' }
    }
    if ($SessionSha256 -cne $pin.session_sha256 -or $PriorSession['source_sha'] -cne $pin.source_sha -or
        $PriorSession['status'] -cne 'BLOCKED_HANDOFF' -or $PriorSession['phase'] -cne 'HANDOFF' -or
        $PriorSession['reason_code'] -cne 'SYSTEM_EXCEPTION' -or $PriorSession['error_type'] -cne 'MethodInvocationException' -or
        $PriorSession['host_status'] -cne 'IDLE' -or $null -ne $PriorSession['editor']) { Stop-L07Install 'MIGRATION_FAILED_SESSION' }
    foreach ($field in @('owner_sid_matches','checkpoint_bytes_verified','module_build_ids_verified')) {
        if ($PriorSession[$field] -isnot [bool] -or $PriorSession[$field] -ne $true) { Stop-L07Install 'MIGRATION_FAILED_SESSION' }
    }
    foreach ($field in @('autosave_session_override','editor_stop_requested','package_save_requested','project_config_write_requested')) {
        if ($PriorSession[$field] -isnot [bool] -or $PriorSession[$field] -ne $false) { Stop-L07Install 'MIGRATION_FAILED_SESSION' }
    }
}
function Get-L07ClosedTaskPin([ValidateSet('CLOSED_602','CLOSED_DE903')][string]$Kind='CLOSED_602') {
    if ($Kind -ceq 'CLOSED_DE903') {
        # Exact closed-session bytes from diagnostic run 39629865244/job 119324891844.
        # The owner closed this Editor; this permits one new release, not a retry.
        return @{
            source_sha='de903a85e67540f451ea86743ea981fb7eb79f18';run_token='39625318792-1'
            installation_bytes=930;installation_sha256='48c0a9a2548888a375baf3eda9db6541936900da453d3e052225ab66071e5c44'
            session_bytes=6732;session_sha256='cc69b0b48a54b5ebeeef6cad95d66b17096a13337a3bbad8cb2b072e735a940e'
            checked_at_utc='2026-10-21T15:44:07.6634944Z'
            editor_pid=24984;editor_start_filetime_utc='134370703459789397';interactive_session_id=2
            files=@{
                'scripts/ue/Install-YacsLesson07RemoteEditor.ps1'=@{bytes=31842;sha256='1ae41ae62ead55bb24d2119f7b89d926ec3f2dad011d26cade5aeb6f7aa7059a'}
                'scripts/ue/Start-YacsLesson07RemoteEditor.ps1'=@{bytes=22916;sha256='8dfd047027ac874ea550868f020997e0df731e26e7d8ba8deb8bcb2518931e91'}
                'scripts/runner/Get-YacsUnrealHostState.ps1'=@{bytes=3374;sha256='73506d6f1707faa33c97797f6e57d1d22e381eb72787377c3bdbb66fe0d2c346'}
                'scripts/live_host/Assert-YacsLiveTaskPrincipal.ps1'=@{bytes=2304;sha256='2bd54cda4f1a1aa3ca3af3d3a94d7013317bfe570910701fc7c17d946d0af0b2'}
            }
        }
    }
    # Observed original bytes: diagnostic run 39579824031/job 119154379466.
    # Task result 0 is a completed supervisor, not proof of a clean UE exit.
    return @{
        source_sha='602f8d0136d8f930adab1cda0c5006de8bf2d9d3';run_token='39513355021-1'
        installation_bytes=930;installation_sha256='8b78fa1df99f91897dbc301467743dd13ea5d6239e62d2c9ed5d4e5cff146ff5'
        session_bytes=6732;session_sha256='8e2b1cd9c108d9ef1f6244ccdfc8d13bcd59ba30be06f3bea23e96e94b3c69eb'
        checked_at_utc='2026-10-21T07:37:58.9575712Z'
        editor_pid=17896;editor_start_filetime_utc='134370120000674689';interactive_session_id=1
        files=@{
            'scripts/ue/Install-YacsLesson07RemoteEditor.ps1'=@{bytes=22040;sha256='bf7d9314cadaa6aa04432eb5615795fad671978da97ebf43ab045ff5fe1ce247'}
            'scripts/ue/Start-YacsLesson07RemoteEditor.ps1'=@{bytes=22830;sha256='215c4cd1ed651d229706e2570dc19b8d57f586677284af29e78f1c90d09eb6ad'}
            'scripts/runner/Get-YacsUnrealHostState.ps1'=@{bytes=3374;sha256='73506d6f1707faa33c97797f6e57d1d22e381eb72787377c3bdbb66fe0d2c346'}
            'scripts/live_host/Assert-YacsLiveTaskPrincipal.ps1'=@{bytes=2304;sha256='2bd54cda4f1a1aa3ca3af3d3a94d7013317bfe570910701fc7c17d946d0af0b2'}
        }
    }
}
function Get-L07KnownTaskMigrationKind([object]$Task) {
    if ($Task.TaskName -isnot [string] -or $Task.TaskName -cne 'YACS Lesson07 Remote Editor' -or
        $Task.TaskPath -isnot [string] -or $Task.TaskPath -cne '\' -or @($Task.Actions).Count -ne 1) { Stop-L07Install 'MIGRATION_TASK_DEFINITION' }
    $action=$Task.Actions[0]
    if ($action.Execute -isnot [string] -or $action.Execute -ine 'D:\yacs\tools\powershell-7.6.6-win-x64\pwsh.exe' -or
        $action.Arguments -isnot [string] -or $action.WorkingDirectory -isnot [string]) { Stop-L07Install 'MIGRATION_TASK_DEFINITION' }
    foreach ($kind in @('FAILED_457','CLOSED_602','CLOSED_DE903')) {
        $pin=if ($kind -ceq 'FAILED_457') { Get-L07FailedTaskPin } else { Get-L07ClosedTaskPin -Kind $kind }
        $priorRelease='D:\yacs\lesson07-remote\releases\'+$pin.source_sha
        $priorScript=if ($IsWindows) { Join-Path $priorRelease 'scripts/ue/Start-YacsLesson07RemoteEditor.ps1' }
            else { $priorRelease+'\scripts\ue\Start-YacsLesson07RemoteEditor.ps1' }
        $arguments='-NoLogo -NoProfile -File "'+$priorScript+'" -ExpectedHead '+$pin.source_sha
        if ($action.Arguments -ceq $arguments -and $action.WorkingDirectory -ieq $priorRelease) { return $kind }
    }
    Stop-L07Install 'MIGRATION_TASK_DEFINITION'
}
function Assert-L07ClosedTaskData(
    [object]$Task, [object]$TaskInfo, [Collections.IDictionary]$PriorInstall,
    [Collections.IDictionary]$PriorSession, [string]$InstallationSha256, [long]$InstallationBytes,
    [string]$SessionSha256, [long]$SessionBytes,
    [string]$ResolvedTaskSid, [string]$ExpectedSid, [string]$HostStatus,
    [DateTime]$NowUtc=[DateTime]::UtcNow,
    [ValidateSet('CLOSED_602','CLOSED_DE903')][string]$Kind='CLOSED_602'
) {
    $pin=Get-L07ClosedTaskPin -Kind $Kind
    if ($HostStatus -cne 'IDLE' -or $Task.State -is [Array] -or [string]$Task.State -cne 'Ready' -or
        ($TaskInfo.LastTaskResult -isnot [int] -and $TaskInfo.LastTaskResult -isnot [long] -and $TaskInfo.LastTaskResult -isnot [uint32]) -or
        $TaskInfo.LastTaskResult -ne 0) { Stop-L07Install 'MIGRATION_NOT_IDLE_CLOSED' }
    if ((Get-L07KnownTaskMigrationKind $Task) -cne $Kind) { Stop-L07Install 'MIGRATION_TASK_DEFINITION' }
    Assert-L07TaskSettings $Task
    if ($ResolvedTaskSid -cne $ExpectedSid -or $ExpectedSid -cnotmatch '^S-1-\d+-' -or
        $ExpectedSid -cin @('S-1-5-18','S-1-5-19','S-1-5-20') -or
        $Task.Principal.RunLevel -is [Array] -or [string]$Task.Principal.RunLevel -cne 'Limited' -or
        $Task.Principal.LogonType -is [Array] -or [string]$Task.Principal.LogonType -cnotin @('Interactive','InteractiveToken') -or
        $PriorInstall['desktop_sid'] -isnot [string] -or $PriorInstall['desktop_sid'] -cne $ExpectedSid) { Stop-L07Install 'MIGRATION_OWNER' }
    if ($InstallationBytes -ne $pin.installation_bytes -or $InstallationSha256 -cne $pin.installation_sha256 -or
        $PriorInstall['source_sha'] -isnot [string] -or $PriorInstall['source_sha'] -cne $pin.source_sha -or
        $PriorInstall['run_token'] -isnot [string] -or $PriorInstall['run_token'] -cne $pin.run_token -or
        @($PriorInstall['files']).Count -ne $pin.files.Count) { Stop-L07Install 'MIGRATION_CLOSED_INSTALLATION' }
    $oldDeadline=$PriorInstall['start_permitted_until_utc']
    if ($oldDeadline -isnot [DateTime] -or $oldDeadline.Kind -ne [DateTimeKind]::Utc -or
        $NowUtc.Kind -ne [DateTimeKind]::Utc -or $oldDeadline -ge $NowUtc) { Stop-L07Install 'MIGRATION_PERMISSION_NOT_EXPIRED' }
    foreach ($relative in $pin.files.Keys) {
        $entries=@($PriorInstall['files'] | Where-Object { $_ -is [Collections.IDictionary] -and $_['path'] -is [string] -and $_['path'] -ceq $relative })
        if ($entries.Count -ne 1 -or $entries[0]['sha256'] -isnot [string] -or $entries[0]['sha256'] -cne $pin.files[$relative].sha256) { Stop-L07Install 'MIGRATION_SOURCE_HASH' }
    }
    if ($SessionBytes -ne $pin.session_bytes -or $SessionSha256 -cne $pin.session_sha256 -or $null -ne $PriorSession['reason_code']) { Stop-L07Install 'MIGRATION_CLOSED_SESSION' }
    $expectedFields=@{source_sha=$pin.source_sha;status='EDITOR_EXITED_NO_AUTORESTART';phase='SUPERVISING';host_status='IDLE'}
    foreach ($field in $expectedFields.Keys) {
        if ($PriorSession[$field] -isnot [string] -or $PriorSession[$field] -cne $expectedFields[$field]) { Stop-L07Install 'MIGRATION_CLOSED_SESSION' }
    }
    $checked=$PriorSession['checked_at_utc']
    if ($checked -isnot [DateTime] -or $checked.Kind -ne [DateTimeKind]::Utc -or $checked.ToString('o') -cne $pin.checked_at_utc) { Stop-L07Install 'MIGRATION_CLOSED_SESSION' }
    foreach ($field in @('owner_sid_matches','checkpoint_bytes_verified','module_build_ids_verified','autosave_session_override')) {
        if ($PriorSession[$field] -isnot [bool] -or $PriorSession[$field] -ne $true) { Stop-L07Install 'MIGRATION_CLOSED_SESSION' }
    }
    foreach ($field in @('editor_stop_requested','package_save_requested','project_config_write_requested','native_world_verified','native_module_load_verified','performance_pass')) {
        if ($PriorSession[$field] -isnot [bool] -or $PriorSession[$field] -ne $false) { Stop-L07Install 'MIGRATION_CLOSED_SESSION' }
    }
    $priorEditor=$PriorSession['editor']
    if ($priorEditor -isnot [Collections.IDictionary] -or
        ($priorEditor['editor_pid'] -isnot [int] -and $priorEditor['editor_pid'] -isnot [long]) -or $priorEditor['editor_pid'] -ne $pin.editor_pid -or
        $priorEditor['editor_start_filetime_utc'] -isnot [string] -or $priorEditor['editor_start_filetime_utc'] -cne $pin.editor_start_filetime_utc -or
        $priorEditor['editor_executable_path'] -isnot [string] -or $priorEditor['editor_executable_path'] -ine 'D:\yacs\engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe' -or
        ($priorEditor['interactive_session_id'] -isnot [int] -and $priorEditor['interactive_session_id'] -isnot [long]) -or $priorEditor['interactive_session_id'] -ne $pin.interactive_session_id -or
        $priorEditor['canonical_project_matches'] -isnot [bool] -or $priorEditor['canonical_project_matches'] -ne $true) { Stop-L07Install 'MIGRATION_CLOSED_EDITOR_IDENTITY' }
}
function Read-L07MigrationJson([string]$Path) {
    Assert-L07InstallPath $Path
    $item=Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer -or $item.Length -le 0 -or $item.Length -gt 256KB) { Stop-L07Install 'MIGRATION_FILE_SIZE' }
    $bytes=[IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -ne $item.Length) { Stop-L07Install 'MIGRATION_FILE_CHANGED' }
    return @{
        size_bytes=[long]$bytes.Length
        sha256=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
        data=([Text.UTF8Encoding]::new($false,$true).GetString($bytes).TrimStart([char]0xFEFF) | ConvertFrom-Json -AsHashtable -Depth 16)
    }
}
function Get-L07FailedTaskMigration([object]$Task, [string]$ExpectedSid) {
    $pin=Get-L07FailedTaskPin
    $priorRelease=Join-Path $root ('releases\'+$pin.source_sha)
    $priorInstall=Read-L07MigrationJson (Join-Path $priorRelease 'installation.json')
    $priorSession=Read-L07MigrationJson (Join-Path $root ('state\'+$pin.source_sha+'\session.json'))
    $currentUser=[string](Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
    if (-not $currentUser -or (Resolve-YacsLiveWindowsSid -UserId $currentUser) -cne $ExpectedSid) { Stop-L07Install 'MIGRATION_OWNER_CHANGED' }
    $principalProof=Assert-YacsLiveTaskPrincipal -Task $Task -ExpectedSid $ExpectedSid
    $taskInfo=Get-ScheduledTaskInfo -TaskName $taskName -TaskPath '\' -ErrorAction Stop
    $hostState=& (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
    Assert-L07FailedTaskData -Task $Task -TaskInfo $taskInfo -PriorInstall $priorInstall.data -PriorSession $priorSession.data `
        -SessionSha256 $priorSession.sha256 -ResolvedTaskSid $principalProof.sid -ExpectedSid $ExpectedSid -HostStatus $hostState.status
    foreach ($relative in $pin.files.Keys) {
        $path=Join-Path $priorRelease $relative
        Assert-L07InstallPath $path
        $item=Get-Item -LiteralPath $path -Force
        if ($item.PSIsContainer -or $item.Length -le 0 -or $item.Length -gt 256KB -or
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $pin.files[$relative]) { Stop-L07Install 'MIGRATION_SOURCE_HASH' }
    }
    return [ordered]@{prior_source_sha=$pin.source_sha;prior_session_sha256=$priorSession.sha256;prior_release_retained=$true;prior_state_retained=$true;owner_sid_matches=$true;prior_task_result=1}
}
function Get-L07ClosedTaskMigration([object]$Task, [string]$ExpectedSid,
    [ValidateSet('CLOSED_602','CLOSED_DE903')][string]$Kind='CLOSED_602') {
    $pin=Get-L07ClosedTaskPin -Kind $Kind
    $priorRelease=Join-Path $root ('releases\'+$pin.source_sha)
    $priorInstall=Read-L07MigrationJson (Join-Path $priorRelease 'installation.json')
    $priorSession=Read-L07MigrationJson (Join-Path $root ('state\'+$pin.source_sha+'\session.json'))
    foreach ($relative in $pin.files.Keys) {
        $path=Join-Path $priorRelease $relative
        Assert-L07InstallPath $path
        $item=Get-Item -LiteralPath $path -Force
        if ($item.PSIsContainer -or $item.Length -ne $pin.files[$relative].bytes -or
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $pin.files[$relative].sha256) { Stop-L07Install 'MIGRATION_SOURCE_HASH' }
    }
    $currentUser=[string](Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
    if (-not $currentUser -or (Resolve-YacsLiveWindowsSid -UserId $currentUser) -cne $ExpectedSid) { Stop-L07Install 'MIGRATION_OWNER_CHANGED' }
    $principalProof=Assert-YacsLiveTaskPrincipal -Task $Task -ExpectedSid $ExpectedSid
    $taskInfo=Get-ScheduledTaskInfo -TaskName $taskName -TaskPath '\' -ErrorAction Stop
    $hostState=& (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
    Assert-L07ClosedTaskData -Kind $Kind -Task $Task -TaskInfo $taskInfo -PriorInstall $priorInstall.data -PriorSession $priorSession.data `
        -InstallationSha256 $priorInstall.sha256 -InstallationBytes $priorInstall.size_bytes `
        -SessionSha256 $priorSession.sha256 -SessionBytes $priorSession.size_bytes `
        -ResolvedTaskSid $principalProof.sid -ExpectedSid $ExpectedSid -HostStatus $hostState.status
    return [ordered]@{kind=$Kind;prior_source_sha=$pin.source_sha;prior_installation_sha256=$priorInstall.sha256;prior_session_sha256=$priorSession.sha256
        prior_release_retained=$true;prior_state_retained=$true;owner_sid_matches=$true;prior_task_result=0;prior_ue_clean_exit_verified=$false}
}
function Get-L07KnownTaskMigration([object]$Task, [string]$ExpectedSid) {
    $kind=Get-L07KnownTaskMigrationKind $Task
    if ($kind -ceq 'FAILED_457') { return Get-L07FailedTaskMigration -Task $Task -ExpectedSid $ExpectedSid }
    if ($kind -cin @('CLOSED_602','CLOSED_DE903')) { return Get-L07ClosedTaskMigration -Kind $kind -Task $Task -ExpectedSid $ExpectedSid }
    Stop-L07Install 'MIGRATION_TASK_DEFINITION'
}
function Copy-L07SessionFailure([Collections.IDictionary]$Session, [Collections.IDictionary]$Target) {
    $Target['reason_code']=if ($Session['reason_code'] -is [string] -and $Session['reason_code'] -cmatch '^[A-Z][A-Z0-9_]{0,79}$') { $Session['reason_code'] } else { 'SYSTEM_EXCEPTION' }
    foreach ($field in @('error_type','error_inner_type')) {
        $Target[$field]=if ($Session[$field] -is [string] -and $Session[$field] -cmatch '^[A-Za-z][A-Za-z0-9]{0,79}$') { $Session[$field] } else { $null }
    }
    foreach ($field in @('error_hresult','error_native_code')) {
        $value=$Session[$field]
        $Target[$field]=if (($value -is [int] -or $value -is [long]) -and $value -ge [int]::MinValue -and $value -le [int]::MaxValue) { $value } else { $null }
    }
    $Target['handoff_step']=if ($Session['handoff_step'] -is [string] -and $Session['handoff_step'] -cin @('DEADLINE','HOST','OTHER_TASK','CONSOLE_OWNER','DISK_RESERVE','SAVE_STARTING','FINAL_DEADLINE','START_PROCESS','PROCESS_IDENTITY','SAVE_RUNNING')) { $Session['handoff_step'] } else { $null }
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
        $existing=Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction SilentlyContinue
        $migration=$null
        $stageRelease=$true
        if ($existing) {
            $null=Assert-YacsLiveTaskPrincipal -Task $existing -ExpectedSid $sid
            Assert-L07TaskSettings $existing
            if (@($existing.Actions).Count -eq 1 -and $existing.Actions[0].Execute -ieq $pwsh -and
                $existing.Actions[0].Arguments -ceq $actionArguments -and $existing.Actions[0].WorkingDirectory -ieq $release) {
                # An identical completed task remains one-shot; never repeat it.
                $report.status=if ([string]$existing.State -eq 'Running') { 'TASK_ALREADY_RUNNING' } else { 'BLOCKED_PRIOR_TASK' }
                $report.owner_sid_matches=$true
                $failed=$report.status -ceq 'BLOCKED_PRIOR_TASK'
                $stageRelease=$false
            } else {
                $report.phase='MIGRATION'
                $migration=Get-L07KnownTaskMigration -Task $existing -ExpectedSid $sid
            }
        }
        if ($stageRelease) {
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
            if ($null -ne $migration) {
                # Retain the prior definition privately; it contains account data.
                Export-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction Stop |
                    Set-Content -LiteralPath (Join-Path $pending 'previous-task.xml') -Encoding utf8
            }
            Move-Item -LiteralPath $pending -Destination $release
            $action=New-ScheduledTaskAction -Execute $pwsh -Argument $actionArguments -WorkingDirectory $release
            if ($null -ne $migration) {
                # Re-read every admission immediately before changing only action.
                $existing=Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction Stop
                $report.task_migration=Get-L07KnownTaskMigration -Task $existing -ExpectedSid $sid
                if ($report.task_migration.prior_source_sha -cne $migration.prior_source_sha) { Stop-L07Install 'MIGRATION_TASK_CHANGED' }
                Set-ScheduledTask -TaskName $taskName -TaskPath '\' -Action $action -ErrorAction Stop | Out-Null
                $report.task_migrated=$true
            } else {
                $principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
                $settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 0 `
                    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DisallowHardTerminate -DontStopOnIdleEnd
                Register-ScheduledTask -TaskName $taskName -TaskPath '\' -Action $action -Principal $principal -Settings $settings -ErrorAction Stop | Out-Null
                $report.task_registered=$true
            }
            $report.phase='TASK'
            $registered=Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction Stop
            $null=Assert-YacsLiveTaskPrincipal -Task $registered -ExpectedSid $sid
            Assert-L07TaskSettings $registered
            if (@($registered.Triggers | Where-Object { $null -ne $_ }).Count -ne 0 -or @($registered.Actions).Count -ne 1 -or
                $registered.Actions[0].Execute -ine $pwsh -or $registered.Actions[0].Arguments -cne $actionArguments -or
                $registered.Actions[0].WorkingDirectory -ine $release) { Stop-L07Install 'REGISTERED_TASK_MISMATCH' }
            $report.owner_sid_matches=$true
            $state=& (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
            if ($state.status -cne 'IDLE') { Stop-L07Install 'HOST_CHANGED_BEFORE_HANDOFF' }
            Start-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction Stop
            $report.task_start_requested=$true;$report.status='TASK_START_REQUESTED'
            # Hold the workflow reservation until the task started, blocked, or
            # its one-shot start permission expired. Timeout never stops its UE.
            while ([DateTime]::UtcNow -lt $deadline.AddSeconds(20)) {
                $statusFile=Join-Path $stateRoot 'session.json'
                if (Test-Path -LiteralPath $statusFile -PathType Leaf) {
                    Assert-L07InstallPath $statusFile
                    if ((Get-Item -LiteralPath $statusFile).Length -gt 256KB) { Stop-L07Install 'SESSION_REPORT_SIZE' }
                    $session=Get-Content -LiteralPath $statusFile -Raw | ConvertFrom-Json -AsHashtable -Depth 16
                    if ($session['source_sha'] -cne $ExpectedHead) { Stop-L07Install 'SESSION_SOURCE' }
                    if ($session['editor']) {
                        $report.status=$session['status'];$report.editor=$session['editor']
                        if ($session['error_type']) { Copy-L07SessionFailure -Session $session -Target $report;$failed=$true }
                        break
                    }
                    if ($session['status'] -like 'BLOCKED_*' -or $session['status'] -ceq 'EDITOR_RETAINED_AFTER_STARTUP_ERROR') {
                        $report.status=$session['status'];$failed=$true
                        Copy-L07SessionFailure -Session $session -Target $report
                        break
                    }
                }
                Start-Sleep -Seconds 2
            }
            if ($report.status -ceq 'TASK_START_REQUESTED') { $report.status='START_TIMEOUT_EDITOR_NOT_STOPPED';$failed=$true }
        }
    }
} catch {
    $report.status='BLOCKED_'+$report.phase;$report.error_type=$_.Exception.GetType().Name;$failed=$true
    $report.error_hresult=[int]$_.Exception.HResult
    if ($_.Exception.InnerException) { $report.error_inner_type=$_.Exception.InnerException.GetType().Name }
    $nativeError=if ($_.Exception -is [ComponentModel.Win32Exception]) { $_.Exception }
        elseif ($_.Exception.InnerException -is [ComponentModel.Win32Exception]) { $_.Exception.InnerException }
        else { $null }
    if ($null -ne $nativeError) { $report.error_native_code=[int]$nativeError.NativeErrorCode }
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
