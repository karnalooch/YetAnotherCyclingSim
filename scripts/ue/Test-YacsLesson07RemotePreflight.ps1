#requires -Version 7.4
<#
.SYNOPSIS
  Exercise the real Lesson07 JSON validators without Windows, UE or task actions.
#>
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot 'Start-YacsLesson07RemoteEditor.ps1'
$tokens=$null; $parseErrors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$parseErrors)
if (@($parseErrors).Count) { throw 'Lesson07 launcher did not parse.' }
# Load only these pure data validators, never the launcher's executable body.
foreach ($name in @('Stop-L07','Get-L07ReleaseEntry','Assert-L07ProjectIdentity','Get-L07StartDeadline')) {
    $nodes=@($ast.FindAll({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    },$false))
    if ($nodes.Count -ne 1) { throw 'Expected one production validator.' }
    . ([scriptblock]::Create($nodes[0].Extent.Text))
}
$installer=Join-Path $PSScriptRoot 'Install-YacsLesson07RemoteEditor.ps1'
$installerAst=[Management.Automation.Language.Parser]::ParseFile($installer,[ref]$tokens,[ref]$parseErrors)
if (@($parseErrors).Count) { throw 'Lesson07 installer did not parse.' }
foreach ($name in @('Stop-L07Install','Assert-L07TaskSettings','Get-L07FailedTaskPin','Assert-L07FailedTaskData',
    'Get-L07PriorTaskPin','Get-L07KnownTaskMigrationKind','Assert-L07PriorTaskData','Copy-L07SessionFailure')) {
    $nodes=@($installerAst.FindAll({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    },$false))
    if ($nodes.Count -ne 1) { throw 'Expected one production installer validator.' }
    . ([scriptblock]::Create($nodes[0].Extent.Text))
}
function Require([bool]$Condition,[string]$Message) {
    if (-not $Condition) { throw $Message }
}
function Expect-ProjectBlock([Collections.IDictionary]$Project, [string]$DescriptorSha256=('0'*64)) {
    $blocked=$false
    try { Assert-L07ProjectIdentity $Project $DescriptorSha256 } catch {
        Require ($_.Exception.Data['l07_reason'] -ceq 'PROJECT_MODULES_OR_ENGINE') 'Wrong project failure reason.'
        $blocked=$true
    }
    Require $blocked 'Invalid project was admitted.'
}
function Expect-ReleaseBlock([Collections.IDictionary]$Install,[string]$Relative) {
    $blocked=$false
    try { $null=Get-L07ReleaseEntry $Install $Relative } catch {
        Require ($_.Exception.Data['l07_reason'] -ceq 'RELEASE_FILE_HASH') 'Wrong release failure reason.'
        $blocked=$true
    }
    Require $blocked 'Invalid release entry was admitted.'
}
$json='{"EngineAssociation":"5.8","Modules":[{"Name":"YetAnotherCyclingSim","Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}],"Description":"PRIVATE_SENTINEL"}'
$report=[ordered]@{}
$valid=$json | ConvertFrom-Json -AsHashtable
Assert-L07ProjectIdentity $valid ('0'*64)
Require ($report.project_observation.required_runtime_matches -eq 1 -and $report.project_observation.required_editor_matches -eq 1) 'Valid JSON dictionary modules were not matched.'
Require ($report.project_observation.engine_association -ceq '5.8' -and $report.project_observation.modules.Count -eq 2) 'Safe project observation is incomplete.'
Require ($report.project_observation.admission_basis -ceq 'NUMERIC_5_8') 'Original numeric engine admission changed.'
Require (($report | ConvertTo-Json -Depth 8) -notmatch 'PRIVATE_SENTINEL|Description') 'Unselected project content leaked.'
$cases=1
foreach ($fixture in @(
    '{"EngineAssociation":"5.8","Modules":[{"Name":"YetAnotherCyclingSim","Type":"Runtime"}]}',
    '{"EngineAssociation":"5.8","Modules":[{"Name":"YetAnotherCyclingSim","Type":"Runtime"},{"Name":"YetAnotherCyclingSim","Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":"5.9","Modules":[{"Name":"YetAnotherCyclingSim","Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":"5.8","Modules":[{"Name":"yetanothercyclingsim","Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":"5.8","Modules":[{"Name":"YetAnotherCyclingSim","Type":"Editor"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":"5.8","Modules":[{"Name":"YetAnotherCyclingSim","Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Runtime"}]}',
    '{"EngineAssociation":["5.8","INVALID"],"Modules":[{"Name":"YetAnotherCyclingSim","Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":null,"Modules":[{"Name":"YetAnotherCyclingSim","Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":"5.8","Modules":[{"Name":["YetAnotherCyclingSim","INVALID"],"Type":"Runtime"},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":"5.8","Modules":[{"Name":"YetAnotherCyclingSim","Type":["Runtime","INVALID"]},{"Name":"YetAnotherCyclingSimEditor","Type":"Editor"}]}',
    '{"EngineAssociation":"5.8","Modules":["INVALID"]}',
    '{"EngineAssociation":"PRIVATE_SENTINEL","Modules":[{"Name":"INVALID/PRIVATE_SENTINEL","Type":"PRIVATE_SENTINEL"}]}'
)) {
    $report=[ordered]@{}
    Expect-ProjectBlock ($fixture | ConvertFrom-Json -AsHashtable)
    Require (($report | ConvertTo-Json -Depth 8) -notmatch 'PRIVATE_SENTINEL') 'Invalid project values were not sanitized.'
    $cases++
}
# Exercise the actual tracked .uproject through the same dictionary-producing API.
$tracked=Get-Content -LiteralPath (Join-Path $PSScriptRoot '../../YetAnotherCyclingSim.uproject') -Raw | ConvertFrom-Json -AsHashtable
$report=[ordered]@{}
Assert-L07ProjectIdentity $tracked ('0'*64)
$cases++
# Only the actual observed GUID together with the exact descriptor hash passes.
$knownGuid='{FEF18A3B-4D4B-15FD-E2E3-E5AA38A2AB75}'
$knownHash='f00d5117b63b3a6a5d200ff4ffab035a770712cd358b3e6f4cb50b6063c06c66'
$custom=$json | ConvertFrom-Json -AsHashtable
$custom['EngineAssociation']=$knownGuid
$report=[ordered]@{}
Assert-L07ProjectIdentity $custom $knownHash
Require ($report.project_observation.admission_basis -ceq 'OBSERVED_GUID_AND_DESCRIPTOR_SHA256' -and
    $report.project_observation.engine_association -ceq $knownGuid -and
    $report.project_observation.descriptor_sha256 -ceq $knownHash) 'Pinned custom engine observation did not pass.'
$cases++
Expect-ProjectBlock $custom ('0'*64)
$cases++
Expect-ProjectBlock $custom ''
$cases++
$custom['EngineAssociation']='{00000000-4D4B-15FD-E2E3-E5AA38A2AB75}'
Expect-ProjectBlock $custom $knownHash
$cases++
$custom['EngineAssociation']=$knownGuid
$custom['Modules'][1]['Type']='Runtime'
Expect-ProjectBlock $custom $knownHash
$cases++
$relative='scripts/ue/Start-YacsLesson07RemoteEditor.ps1'
$release='{"files":[{"path":"scripts/ue/Start-YacsLesson07RemoteEditor.ps1","sha256":"known"}]}' | ConvertFrom-Json -AsHashtable
Require ((Get-L07ReleaseEntry $release $relative)['sha256'] -ceq 'known') 'Valid release dictionary entry was not matched.'
$cases++
Expect-ReleaseBlock $release 'scripts/ue/Missing.ps1'
$cases++
$duplicate='{"files":[{"path":"scripts/ue/Start-YacsLesson07RemoteEditor.ps1"},{"path":"scripts/ue/Start-YacsLesson07RemoteEditor.ps1"}]}' | ConvertFrom-Json -AsHashtable
Expect-ReleaseBlock $duplicate $relative
$cases++
$wrongCase='{"files":[{"path":"scripts/ue/start-YacsLesson07RemoteEditor.ps1"}]}' | ConvertFrom-Json -AsHashtable
Expect-ReleaseBlock $wrongCase $relative
$cases++
$arrayPath='{"files":[{"path":["scripts/ue/Start-YacsLesson07RemoteEditor.ps1","INVALID"]}]}' | ConvertFrom-Json -AsHashtable
Expect-ReleaseBlock $arrayPath $relative
$cases++
# The actual installer JSON becomes DateTime(Utc); preserve its exact ticks under
# the owner's regional settings and other common cultures, including string input.
$now=[DateTime]::new(2026,10,20,23,0,0,[DateTimeKind]::Utc)
$timestamp='2026-10-20T23:04:00.1234567Z'
$parsedDeadline=('{"start_permitted_until_utc":"'+$timestamp+'"}' | ConvertFrom-Json -AsHashtable)['start_permitted_until_utc']
Require ($parsedDeadline -is [DateTime] -and $parsedDeadline.Kind -eq [DateTimeKind]::Utc) 'Fixture must exercise real default JSON date conversion.'
$originalCulture=[Threading.Thread]::CurrentThread.CurrentCulture
try {
    foreach ($culture in @('pl-PL','en-GB','en-US')) {
        [Threading.Thread]::CurrentThread.CurrentCulture=[Globalization.CultureInfo]::GetCultureInfo($culture)
        foreach ($value in @($parsedDeadline,$timestamp)) {
            $deadline=Get-L07StartDeadline -Value $value -NowUtc $now
            Require ($deadline.Kind -eq [DateTimeKind]::Utc -and $deadline.Ticks -eq $parsedDeadline.Ticks -and $deadline.ToString('o') -ceq $timestamp) 'Deadline changed UTC, precision or culture.'
            $cases++
        }
    }
} finally { [Threading.Thread]::CurrentThread.CurrentCulture=$originalCulture }
foreach ($value in @($null,'PRIVATE_SENTINEL','2026-10-20T23:04:00.1234567','2026-10-20T23:04:00.1234567+00:00',
    ([DateTime]::SpecifyKind($parsedDeadline,[DateTimeKind]::Local)),([DateTime]::SpecifyKind($parsedDeadline,[DateTimeKind]::Unspecified)),
    @($parsedDeadline,$parsedDeadline))) {
    $blocked=$false
    try { $null=Get-L07StartDeadline -Value $value -NowUtc $now } catch {
        Require ($_.Exception.Data['l07_reason'] -ceq 'START_DEADLINE_FORMAT') 'Wrong deadline format failure.'
        $blocked=$true
    }
    Require $blocked 'Malformed deadline was admitted.'
    $cases++
}
foreach ($value in @($now,$now.AddTicks(-1),$now.AddMinutes(5).AddTicks(1))) {
    $blocked=$false
    try { $null=Get-L07StartDeadline -Value $value -NowUtc $now } catch {
        Require ($_.Exception.Data['l07_reason'] -ceq 'START_REQUEST_EXPIRED') 'Wrong expired deadline failure.'
        $blocked=$true
    }
    Require $blocked 'Expired or excessive start permission was admitted.'
    $cases++
}
# Data-only migration admission; native SID resolution, file hashes and live
# Task Scheduler/host reads are performed by the wrapper before this validator.
function New-MigrationFixture {
    $pin=Get-L07FailedTaskPin
    $priorRelease='D:\yacs\lesson07-remote\releases\457dc899adb858abee69c8ec1c4174cb7bc8032d'
    $priorScript=if ($IsWindows) { Join-Path $priorRelease 'scripts/ue/Start-YacsLesson07RemoteEditor.ps1' }
        else { $priorRelease+'\scripts\ue\Start-YacsLesson07RemoteEditor.ps1' }
    $sid='S-1-5-21-100-200-300-1001'
    return @{
        Task=[pscustomobject]@{
            TaskName='YACS Lesson07 Remote Editor';TaskPath='\';State='Ready';Triggers=@()
            Principal=[pscustomobject]@{RunLevel='Limited';LogonType='Interactive'}
            Actions=@([pscustomobject]@{Execute='D:\yacs\tools\powershell-7.6.6-win-x64\pwsh.exe';WorkingDirectory=$priorRelease
                Arguments='-NoLogo -NoProfile -File "'+$priorScript+'" -ExpectedHead 457dc899adb858abee69c8ec1c4174cb7bc8032d'})
            Settings=[pscustomobject]@{ExecutionTimeLimit='PT0S';RestartCount=0;MultipleInstances='IgnoreNew';AllowHardTerminate=$false
                StopIfGoingOnBatteries=$false;DisallowStartIfOnBatteries=$false;IdleSettings=[pscustomobject]@{StopOnIdleEnd=$false}}
        }
        TaskInfo=[pscustomobject]@{LastTaskResult=1}
        PriorInstall=@{source_sha='457dc899adb858abee69c8ec1c4174cb7bc8032d';run_token='39510976391-1';desktop_sid=$sid
            start_permitted_until_utc=$now.AddMinutes(-1);files=@(foreach ($path in $pin.files.Keys) { @{path=$path;sha256=$pin.files[$path]} })}
        PriorSession=@{source_sha='457dc899adb858abee69c8ec1c4174cb7bc8032d';status='BLOCKED_HANDOFF';phase='HANDOFF'
            reason_code='SYSTEM_EXCEPTION';error_type='MethodInvocationException';host_status='IDLE';editor=$null
            owner_sid_matches=$true;checkpoint_bytes_verified=$true;module_build_ids_verified=$true;autosave_session_override=$false
            editor_stop_requested=$false;package_save_requested=$false;project_config_write_requested=$false}
        SessionSha256='57fa56edbd2d1eff4be7f3f765227457754f8dce298e2212a4ed5cff1e3ed1d9'
        ResolvedTaskSid=$sid;ExpectedSid=$sid;HostStatus='IDLE';NowUtc=$now
    }
}
$migration=New-MigrationFixture
Assert-L07FailedTaskData @migration
$cases++
# A valid AzureAD-style owner is not excluded by an invented account-family rule.
$migration=New-MigrationFixture
$migration.ExpectedSid='S-1-12-1-100-200-300-400';$migration.ResolvedTaskSid=$migration.ExpectedSid;$migration.PriorInstall.desktop_sid=$migration.ExpectedSid
Assert-L07FailedTaskData @migration
$cases++
$negativeMigrations=@(
    {param($x) $x.Task.State='Running'},
    {param($x) $x.Task.State='Queued'},
    {param($x) $x.TaskInfo.LastTaskResult=0},
    {param($x) $x.HostStatus='LOCAL_BUSY'},
    {param($x) $x.Task.TaskName='YACS Live Host'},
    {param($x) $x.Task.TaskPath='\Other\'},
    {param($x) $x.Task.Actions[0].Execute='D:\other\pwsh.exe'},
    {param($x) $x.Task.Actions[0].Arguments+=' -Other'},
    {param($x) $x.Task.Actions[0].WorkingDirectory='D:\other'},
    {param($x) $x.Task.Principal.RunLevel='Highest'},
    {param($x) $x.Task.Principal.LogonType='ServiceAccount'},
    {param($x) $x.ResolvedTaskSid='S-1-5-21-100-200-300-9999'},
    {param($x) $x.PriorInstall.desktop_sid='S-1-5-21-100-200-300-9999'},
    {param($x) $x.Task.Triggers=@([pscustomobject]@{Enabled=$true})},
    {param($x) $x.Task.Settings.RestartCount=1},
    {param($x) $x.Task.Settings.ExecutionTimeLimit='PT1H'},
    {param($x) $x.Task.Settings.AllowHardTerminate=$true},
    {param($x) $x.PriorInstall.source_sha='0'*40},
    {param($x) $x.PriorInstall.run_token='39510976391-2'},
    {param($x) $x.PriorInstall.files[0].sha256='0'*64},
    {param($x) $x.PriorInstall.start_permitted_until_utc=$x.NowUtc.AddMinutes(1)},
    {param($x) $x.PriorInstall.start_permitted_until_utc=$null},
    {param($x) $x.SessionSha256='0'*64},
    {param($x) $x.PriorSession.status='EDITOR_RUNNING_NATIVE_NOT_VERIFIED'},
    {param($x) $x.PriorSession.error_type='OtherException'},
    {param($x) $x.PriorSession.editor=@{editor_pid=123}},
    {param($x) $x.PriorSession.owner_sid_matches=$false},
    {param($x) $x.PriorSession.autosave_session_override=$true}
)
foreach ($mutate in $negativeMigrations) {
    $migration=New-MigrationFixture
    & $mutate $migration
    $blocked=$false
    try { Assert-L07FailedTaskData @migration } catch {
        Require ($_.Exception.Data['l07_reason'] -like 'MIGRATION_*' -or $_.Exception.Data['l07_reason'] -ceq 'TASK_SETTINGS_MISMATCH') 'Unexpected migration failure.'
        $blocked=$true
    }
    Require $blocked 'Unproven or active prior task was admitted for migration.'
    $cases++
}
# Each separately pinned prior session permits exactly one new release;
# none relaxes failed-457 admission or admits arbitrary completed tasks.
function New-PriorMigrationFixture([ValidateSet('CLOSED_602','CLOSED_DE903','INTERRUPTED_007')][string]$Kind='CLOSED_602') {
    $x=New-MigrationFixture
    $pin=Get-L07PriorTaskPin -Kind $Kind
    $x.Kind=$Kind
    $priorRelease='D:\yacs\lesson07-remote\releases\'+$pin.source_sha
    $priorScript=if ($IsWindows) { Join-Path $priorRelease 'scripts/ue/Start-YacsLesson07RemoteEditor.ps1' }
        else { $priorRelease+'\scripts\ue\Start-YacsLesson07RemoteEditor.ps1' }
    $x.Task.Actions[0].WorkingDirectory=$priorRelease
    $x.Task.Actions[0].Arguments='-NoLogo -NoProfile -File "'+$priorScript+'" -ExpectedHead '+$pin.source_sha
    $x.TaskInfo.LastTaskResult=[uint32]$pin.last_task_result
    $x.NowUtc=[DateTime]::new(2026,10,22,8,0,0,[DateTimeKind]::Utc)
    $deadline=if ($Kind -ceq 'INTERRUPTED_007') { '2026-10-21T16:11:22.0462628Z' }
        elseif ($Kind -ceq 'CLOSED_DE903') { '2026-10-21T15:35:55.6288295Z' } else { '2026-10-20T23:23:48.9836870Z' }
    $x.PriorInstall=@{source_sha=$pin.source_sha;run_token=$pin.run_token;desktop_sid=$x.ExpectedSid
        start_permitted_until_utc=(('{"utc":"'+$deadline+'"}') | ConvertFrom-Json -AsHashtable)['utc']
        files=@(foreach ($path in $pin.files.Keys) { @{path=$path;sha256=$pin.files[$path].sha256} })}
    $x.PriorSession=@{source_sha=$pin.source_sha;status=$pin.session_status;phase='SUPERVISING';host_status='IDLE';reason_code=$null
        checked_at_utc=(('{"utc":"'+$pin.checked_at_utc+'"}') | ConvertFrom-Json -AsHashtable)['utc']
        owner_sid_matches=$true;checkpoint_bytes_verified=$true;module_build_ids_verified=$true;autosave_session_override=$true
        editor_stop_requested=$false;package_save_requested=$false;project_config_write_requested=$false
        native_world_verified=$false;native_module_load_verified=$false;performance_pass=$false
        editor=@{editor_pid=$pin.editor_pid;editor_start_filetime_utc=$pin.editor_start_filetime_utc;interactive_session_id=$pin.interactive_session_id;canonical_project_matches=$true
            editor_executable_path='D:\yacs\engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'}}
    $x.InstallationSha256=$pin.installation_sha256;$x.InstallationBytes=$pin.installation_bytes
    $x.SessionSha256=$pin.session_sha256;$x.SessionBytes=$pin.session_bytes
    return $x
}
$closed=New-PriorMigrationFixture
[void]$closed.Remove('Kind')
Assert-L07PriorTaskData @closed
Require ((Get-L07KnownTaskMigrationKind $closed.Task) -ceq 'CLOSED_602') 'Closed602 dispatch did not match exact action.'
Require ((Get-L07KnownTaskMigrationKind (New-MigrationFixture).Task) -ceq 'FAILED_457') 'Failed457 dispatch changed.'
$cases++
$closed=New-PriorMigrationFixture -Kind 'CLOSED_DE903'
Assert-L07PriorTaskData @closed
Require ((Get-L07KnownTaskMigrationKind $closed.Task) -ceq 'CLOSED_DE903') 'ClosedDe903 dispatch did not match exact action.'
Require ($closed.PriorSession.editor.editor_pid -eq 24984 -and
    $closed.PriorSession.editor.editor_start_filetime_utc -ceq '134370703459789397' -and
    $closed.PriorSession.editor.interactive_session_id -eq 2) 'ClosedDe903 process identity differs from the diagnostic.'
$cases++
$interrupted=New-PriorMigrationFixture -Kind 'INTERRUPTED_007'
Assert-L07PriorTaskData @interrupted
Require ((Get-L07KnownTaskMigrationKind $interrupted.Task) -ceq 'INTERRUPTED_007') 'Interrupted007 dispatch did not match exact action.'
Require ($interrupted.TaskInfo.LastTaskResult -eq [uint32]3221225786 -and
    $interrupted.PriorSession.status -ceq 'EDITOR_RUNNING_NATIVE_NOT_VERIFIED' -and
    $interrupted.PriorSession.checked_at_utc.ToString('o') -ceq '2026-10-21T18:12:37.4610531Z' -and
    $interrupted.PriorSession.editor.editor_pid -eq 34848 -and
    $interrupted.PriorSession.editor.editor_start_filetime_utc -ceq '134370724521531735' -and
    $interrupted.PriorSession.editor.interactive_session_id -eq 2) 'Interrupted007 evidence differs from the diagnostic.'
$cases++
$negativePriorMigrations=@(
    {param($x) $x.InstallationSha256='0'*64},
    {param($x) $x.InstallationBytes=931},
    {param($x) $x.SessionSha256='0'*64},
    {param($x) $x.SessionBytes=6733},
    {param($x) $x.Task.State='Running'},
    {param($x) $x.Task.State='Queued'},
    {param($x) $x.TaskInfo.LastTaskResult=1},
    {param($x) $x.TaskInfo.LastTaskResult=if ($x.Kind -ceq 'INTERRUPTED_007') { [uint32]0 } else { [uint32]3221225786 }},
    {param($x) $x.TaskInfo.LastTaskResult=$false},
    {param($x) $x.HostStatus='LOCAL_BUSY'},
    {param($x) $x.Task.Actions[0].Arguments+=' -Other'},
    {param($x) $x.Task.Actions[0].Arguments=@($x.Task.Actions[0].Arguments)},
    {param($x) $x.Task.Actions[0].WorkingDirectory='D:\other'},
    {param($x) $x.ResolvedTaskSid='S-1-5-21-100-200-300-9999'},
    {param($x) $x.PriorInstall.desktop_sid='S-1-5-21-100-200-300-9999'},
    {param($x) $x.Task.Principal.RunLevel='Highest'},
    {param($x) $x.Task.Settings.RestartCount=1},
    {param($x) $x.PriorInstall.source_sha='0'*40},
    {param($x) $x.PriorInstall.run_token+='-changed'},
    {param($x) $x.PriorInstall.files[0].sha256='0'*64},
    {param($x) $x.PriorInstall.start_permitted_until_utc=$x.NowUtc.AddMinutes(1)},
    {param($x) $x.PriorSession.status=if ($x.Kind -ceq 'INTERRUPTED_007') { 'EDITOR_EXITED_NO_AUTORESTART' } else { 'EDITOR_RUNNING_NATIVE_NOT_VERIFIED' }},
    {param($x) $x.PriorSession.status=@('EDITOR_EXITED_NO_AUTORESTART')},
    {param($x) $x.PriorSession.phase='HANDOFF'},
    {param($x) $x.PriorSession.reason_code='SYSTEM_EXCEPTION'},
    {param($x) $x.PriorSession.checked_at_utc=$x.PriorSession.checked_at_utc.AddTicks(1)},
    {param($x) $x.PriorSession.owner_sid_matches=$false},
    {param($x) $x.PriorSession.owner_sid_matches=@($true)},
    {param($x) $x.PriorSession.owner_sid_matches=$null},
    {param($x) $x.PriorSession.editor_stop_requested=$true},
    {param($x) $x.PriorSession.editor_stop_requested=@($false)},
    {param($x) $x.PriorSession.editor_stop_requested=$null},
    {param($x) $x.PriorSession.editor.editor_pid++},
    {param($x) $x.PriorSession.editor.editor_start_filetime_utc='0'},
    {param($x) $x.PriorSession.editor.interactive_session_id++},
    {param($x) $x.PriorSession.editor.canonical_project_matches=@($true)},
    {param($x) $x.Kind=if ($x.Kind -ceq 'CLOSED_602') { 'CLOSED_DE903' } else { 'CLOSED_602' }}
)
foreach ($kind in @('CLOSED_602','CLOSED_DE903','INTERRUPTED_007')) {
    foreach ($mutate in $negativePriorMigrations) {
        $closed=New-PriorMigrationFixture -Kind $kind
        & $mutate $closed
        $blocked=$false
        try { Assert-L07PriorTaskData @closed } catch {
            Require ($_.Exception.Data['l07_reason'] -like 'MIGRATION_*' -or $_.Exception.Data['l07_reason'] -ceq 'TASK_SETTINGS_MISMATCH') 'Unexpected prior migration failure.'
            $blocked=$true
        }
        Require $blocked "Unproven $kind session was admitted for migration."
        $cases++
    }
}
$failure=@{reason_code='SYSTEM_EXCEPTION';error_type='MethodInvocationException';error_inner_type='FormatException';error_hresult=-2146233087;error_native_code=5;handoff_step='DEADLINE'}
$target=@{}
Copy-L07SessionFailure -Session $failure -Target $target
Require ($target.reason_code -ceq 'SYSTEM_EXCEPTION' -and $target.error_type -ceq 'MethodInvocationException' -and
    $target.error_inner_type -ceq 'FormatException' -and $target.error_native_code -eq 5 -and $target.handoff_step -ceq 'DEADLINE') 'Failure diagnostics were lost.'
$cases++
$failure=@{reason_code='private message';error_type='PRIVATE/SENTINEL';error_inner_type=@('private');error_hresult='secret';error_native_code='secret';handoff_step='PRIVATE_SENTINEL'}
Copy-L07SessionFailure -Session $failure -Target $target
Require (($target | ConvertTo-Json) -notmatch 'PRIVATE|SENTINEL|secret|private') 'Unbounded session failure content leaked.'
$cases++
[ordered]@{status='LESSON07_REMOTE_JSON_PREFLIGHT_PASS';cases=$cases;powershell_version=$PSVersionTable.PSVersion.ToString();native_host_actions=$false} | ConvertTo-Json -Compress
