#requires -Version 7.4
<#
.SYNOPSIS
  Open the accepted saved Lesson07 once, from a limited interactive scheduled task.
.DESCRIPTION
  -PreflightOnly reads the host without starting or writing anything. The task
  retains its Editor on every failure and never retries, saves, builds or imports.
  The caller must hold the existing yacs-unreal-ci workflow reservation.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedHead,
    [switch]$PreflightOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = 'D:\yacs\lesson07-remote'
$release = Join-Path $root "releases\$ExpectedHead"
$stateRoot = Join-Path $root "state\$ExpectedHead"
$projectRoot = 'D:\yacs\project'
$project = Join-Path $projectRoot 'YetAnotherCyclingSim.uproject'
$engineRoot = 'D:\yacs\engine\UE_5.8'
$editorExe = Join-Path $engineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$mapPackage = '/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07'
$sourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$closure = @(
    'scripts/ue/Install-YacsLesson07RemoteEditor.ps1',
    'scripts/ue/Start-YacsLesson07RemoteEditor.ps1',
    'scripts/runner/Get-YacsUnrealHostState.ps1',
    'scripts/live_host/Assert-YacsLiveTaskPrincipal.ps1'
)
$report = [ordered]@{
    schema_version=1; source_sha=$ExpectedHead; status='PREFLIGHT_PENDING'; phase='HOST'
    checked_at_utc=[DateTime]::UtcNow.ToString('o'); subject=$null; error_type=$null;reason_code=$null
    project_file=$project; map_package=$mapPackage; editor=$null; host_status=$null
    checkpoint_bytes_verified=$false; module_build_ids_verified=$false
    native_world_verified=$false; native_module_load_verified=$false
    owner_sid_matches=$false; autosave_session_override=$false
    editor_stop_requested=$false; package_save_requested=$false; project_config_write_requested=$false
    performance_pass=$false; file_proofs=@(); module_proofs=@()
}
$editor = $null
$stateWritable = $false
$install = $null

function Stop-L07([string]$Reason) {
    $failure=[InvalidOperationException]::new('Lesson07 preflight blocked.')
    $failure.Data['l07_reason']=$Reason
    throw $failure
}
function Assert-L07PlainPath([string]$Path) {
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                Stop-L07 'REPARSE_PATH'
            }
        }
        $parent = Split-Path -Path $cursor -Parent
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}
function Get-L07FileProof([string]$Path, [long]$Limit=3GB) {
    $report.subject=$Path
    Assert-L07PlainPath $Path
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { Stop-L07 'FILE_NOT_FOUND' }
    $before=Get-Item -LiteralPath $Path -Force
    if ($before.PSIsContainer -or $before.Length -le 0 -or $before.Length -gt $Limit) { Stop-L07 'FILE_SIZE' }
    $hash=(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    $after=Get-Item -LiteralPath $Path -Force
    if ($before.Length -ne $after.Length -or $before.LastWriteTimeUtc -ne $after.LastWriteTimeUtc) { Stop-L07 'FILE_CHANGED_DURING_READ' }
    return [ordered]@{path=$Path;size_bytes=[long]$after.Length;sha256=$hash}
}
function Read-L07Json([string]$Path, [long]$Limit=256KB) {
    $null=Get-L07FileProof $Path $Limit
    return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -AsHashtable -Depth 32)
}
function Get-L07ReleaseEntry([Collections.IDictionary]$Install, [string]$Relative) {
    # Keep source-entry matching explicit for dictionary-backed JSON records.
    $rows=@($Install['files'] | Where-Object {
        $_ -is [Collections.IDictionary] -and $_['path'] -is [string] -and $_['path'] -ceq $Relative
    })
    if ($rows.Count -ne 1) { Stop-L07 'RELEASE_FILE_HASH' }
    return $rows[0]
}
function Assert-L07ProjectIdentity([Collections.IDictionary]$ProjectData, [string]$DescriptorSha256) {
    $association=$ProjectData['EngineAssociation']
    # Native read-only observation: run 39510504128, job 118930037564.
    # This is one saved descriptor, not admission for arbitrary custom engines.
    $knownGuid='{FEF18A3B-4D4B-15FD-E2E3-E5AA38A2AB75}'
    $knownDescriptorHash='f00d5117b63b3a6a5d200ff4ffab035a770712cd358b3e6f4cb50b6063c06c66'
    $associationBasis=if ($association -is [string] -and $association -ceq '5.8') { 'NUMERIC_5_8' }
        elseif ($association -is [string] -and $association -ceq $knownGuid -and $DescriptorSha256 -ceq $knownDescriptorHash) { 'OBSERVED_GUID_AND_DESCRIPTOR_SHA256' }
        else { 'NOT_ADMITTED' }
    $modules=@($ProjectData['Modules'])
    $runtimeCount=@($modules | Where-Object {
        $_ -is [Collections.IDictionary] -and $_['Name'] -is [string] -and $_['Name'] -ceq 'YetAnotherCyclingSim'
    }).Count
    $editorCount=@($modules | Where-Object {
        $_ -is [Collections.IDictionary] -and $_['Name'] -is [string] -and $_['Name'] -ceq 'YetAnotherCyclingSimEditor'
    }).Count
    $runtimeTypeCount=@($modules | Where-Object {
        $_ -is [Collections.IDictionary] -and $_['Name'] -is [string] -and $_['Type'] -is [string] -and
            $_['Name'] -ceq 'YetAnotherCyclingSim' -and $_['Type'] -ceq 'Runtime'
    }).Count
    $editorTypeCount=@($modules | Where-Object {
        $_ -is [Collections.IDictionary] -and $_['Name'] -is [string] -and $_['Type'] -is [string] -and
            $_['Name'] -ceq 'YetAnotherCyclingSimEditor' -and $_['Type'] -ceq 'Editor'
    }).Count
    $observedModules=@(foreach ($module in ($modules | Select-Object -First 32)) {
        $name=$null; $type=$null
        if ($module -is [Collections.IDictionary]) { $name=$module['Name']; $type=$module['Type'] }
        [ordered]@{
            name=if ($name -is [string] -and $name -cmatch '^[A-Za-z][A-Za-z0-9_]{0,127}$') { $name } else { 'INVALID' }
            type=if ($type -is [string] -and $type -cin @('Runtime','RuntimeNoCommandlet','RuntimeAndProgram','CookedOnly','UncookedOnly','Developer','DeveloperTool','Editor','EditorNoCommandlet','EditorAndProgram','Program','ServerOnly','ClientOnly','ClientOnlyNoCommandlet')) { $type } else { 'INVALID' }
        }
    })
    $report.project_observation=[ordered]@{
        engine_association=if ($association -is [string] -and $association -cmatch '^(?:[0-9]{1,3}(?:\.[0-9]{1,3}){1,2}|\{[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12}\})$') { $association } else { 'INVALID' }
        descriptor_sha256=if ($DescriptorSha256 -cmatch '^[a-f0-9]{64}$') { $DescriptorSha256 } else { 'INVALID' }
        admission_basis='NOT_ADMITTED'
        module_count=$modules.Count; modules=$observedModules; modules_truncated=($modules.Count -gt 32)
        required_runtime_matches=$runtimeCount; required_editor_matches=$editorCount
        required_runtime_type_matches=$runtimeTypeCount; required_editor_type_matches=$editorTypeCount
    }
    if ($associationBasis -ceq 'NOT_ADMITTED' -or $runtimeCount -ne 1 -or $editorCount -ne 1 -or
        $runtimeTypeCount -ne 1 -or $editorTypeCount -ne 1) {
        Stop-L07 'PROJECT_MODULES_OR_ENGINE'
    }
    $report.project_observation.admission_basis=$associationBasis
}
function Get-L07ConsoleSid {
    $user=[string](Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
    if (-not $user) { Stop-L07 'NO_CONSOLE_OWNER' }
    $sid=([Security.Principal.NTAccount]::new($user)).Translate([Security.Principal.SecurityIdentifier]).Value
    if ($sid -in @('S-1-5-18','S-1-5-19','S-1-5-20')) { Stop-L07 'SERVICE_IDENTITY' }
    return $sid
}
function Get-L07Host {
    $state=& (Join-Path $sourceRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
    $report.host_status=[string]$state.status
    if ($state.status -ceq 'IDLE') { return $null }
    if ($state.local_or_unknown_count -ne 1 -or $state.remote_ci_count -ne 0) { Stop-L07 'OTHER_UNREAL_OWNER' }
    $row=@($state.local_or_unknown_processes)[0]
    $exePattern=[regex]::Escape($editorExe.Replace('\','/'))
    $projectPattern=[regex]::Escape($project.Replace('\','/'))
    $prefix='\A(?:"'+$exePattern+'"|'+$exePattern+')\s+(?:"'+$projectPattern+'"|'+$projectPattern+')(?=\s|$)'
    if ($row.name -ine 'UnrealEditor.exe' -or $row.executable_path -ine $editorExe -or
        $row.session_id -le 0 -or ([string]$row.command_line).Replace('\','/') -notmatch $prefix) {
        Stop-L07 'OTHER_UNREAL_PROJECT'
    }
    # Inspect ownership in memory; never serialize a command line or account name.
    $native=Get-Process -Id $row.process_id -ErrorAction Stop
    $cim=Get-CimInstance Win32_Process -Filter "ProcessId=$($row.process_id)" -ErrorAction Stop
    $owner=Invoke-CimMethod -InputObject $cim -MethodName GetOwnerSid -ErrorAction Stop
    if ($native.HasExited -or $native.Path -ine $editorExe -or $owner.ReturnValue -ne 0 -or
        $owner.Sid -cne (Get-L07ConsoleSid) -or
        ([DateTime]$cim.CreationDate).ToUniversalTime().ToString('o') -cne $row.creation_date) {
        Stop-L07 'EDITOR_IDENTITY_OR_OWNER'
    }
    $report.owner_sid_matches=$true
    return [ordered]@{
        editor_pid=$native.Id; editor_start_filetime_utc=$native.StartTime.ToUniversalTime().ToFileTimeUtc().ToString()
        editor_started_utc=$native.StartTime.ToUniversalTime().ToString('o'); editor_executable_path=$editorExe
        interactive_session_id=$native.SessionId; canonical_project_matches=$true
    }
}
function Assert-L07OtherTaskIdle {
    $other=Get-ScheduledTask -TaskName 'YACS Live Host' -ErrorAction SilentlyContinue
    if ($other -and [string]$other.State -eq 'Running') { Stop-L07 'OTHER_STARTUP_TASK' }
}
function Get-L07ModuleProof([string]$Directory, [string[]]$Required, [string]$BuildId) {
    $path=Join-Path $Directory 'UnrealEditor.modules'
    $manifest=Read-L07Json $path 2MB
    if ($manifest.Modules -isnot [Collections.IDictionary] -or
        $manifest.Modules.Count -lt 1 -or $manifest.Modules.Count -gt 64) { Stop-L07 'MODULE_MANIFEST_SHAPE' }
    if ($manifest.BuildId -cne $BuildId) {
        $observed=[string]$manifest.BuildId
        $report.module_mismatch=[ordered]@{
            expected_build_id=$BuildId
            observed_build_id=if ($observed -cmatch '^[A-Za-z0-9-]{1,128}$') { $observed } else { 'INVALID' }
        }
        Stop-L07 'MODULE_BUILD_ID_MISMATCH'
    }
    foreach ($name in $Required) {
        if (-not $manifest.Modules.Contains($name)) { Stop-L07 'REQUIRED_MODULE_MISSING' }
    }
    $rows=@()
    foreach ($name in @($manifest.Modules.Keys | Sort-Object)) {
        $file=[string]$manifest.Modules[$name]
        if ($name -cnotmatch '^[A-Za-z][A-Za-z0-9_]{0,127}$' -or $file -cnotmatch '^UnrealEditor-[A-Za-z0-9_-]+\.dll$') {
            Stop-L07 'MODULE_FILENAME'
        }
        $proof=Get-L07FileProof (Join-Path $Directory $file) 1GB
        $rows+=,[ordered]@{module=$name;build_id=$BuildId;file=$proof}
    }
    return $rows
}
function Save-L07Session {
    if (-not $stateWritable) { return }
    $report.checked_at_utc=[DateTime]::UtcNow.ToString('o')
    $temporary=Join-Path $stateRoot 'session.tmp'
    $target=Join-Path $stateRoot 'session.json'
    Assert-L07PlainPath $temporary
    Assert-L07PlainPath $target
    $report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $temporary -Encoding utf8
    Move-Item -LiteralPath $temporary -Destination $target -Force
}

try {
    if (-not $IsWindows) { Stop-L07 'WINDOWS_REQUIRED' }
    if (-not $PreflightOnly) {
        $report.phase='RELEASE'
        if ($env:GITHUB_ACTIONS -eq 'true' -or $env:RUNNER_TRACKING_ID -or $sourceRoot -ine $release) {
            Stop-L07 'INDEPENDENT_TASK_REQUIRED'
        }
        $install=Read-L07Json (Join-Path $release 'installation.json')
        if ($install.source_sha -cne $ExpectedHead -or @($install.files).Count -ne $closure.Count) { Stop-L07 'RELEASE_IDENTITY' }
        foreach ($relative in $closure) {
            $entry=Get-L07ReleaseEntry $install $relative
            $proof=Get-L07FileProof (Join-Path $release $relative) 256KB
            if ($entry['sha256'] -cne $proof.sha256) { Stop-L07 'RELEASE_FILE_HASH' }
        }
        $report.phase='DESKTOP'
        $sid=(Get-L07ConsoleSid)
        if ($sid -cne $install.desktop_sid -or [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -cne $sid -or
            (Get-Process -Id $PID -ErrorAction Stop).SessionId -le 0) { Stop-L07 'TASK_CONSOLE_IDENTITY' }
        . (Join-Path $release 'scripts/live_host/Assert-YacsLiveTaskPrincipal.ps1')
        $task=Get-ScheduledTask -TaskName 'YACS Lesson07 Remote Editor' -ErrorAction Stop
        $null=Assert-YacsLiveTaskPrincipal -Task $task -ExpectedSid $sid
        if (@($task.Triggers | Where-Object { $null -ne $_ }).Count -ne 0 -or
            [Xml.XmlConvert]::ToTimeSpan([string]$task.Settings.ExecutionTimeLimit) -ne [TimeSpan]::Zero -or
            $task.Settings.RestartCount -ne 0 -or [string]$task.Settings.MultipleInstances -cnotin @('IgnoreNew','2') -or
            $task.Settings.AllowHardTerminate -ne $false -or $task.Settings.StopIfGoingOnBatteries -ne $false -or
            $task.Settings.DisallowStartIfOnBatteries -ne $false -or $task.Settings.IdleSettings.StopOnIdleEnd -ne $false) {
            Stop-L07 'TASK_SETTINGS_MISMATCH'
        }
        $report.owner_sid_matches=$true
        Assert-L07PlainPath $stateRoot
        if (Test-Path -LiteralPath $stateRoot) { Stop-L07 'PRIOR_SESSION_RETAINED' }
        [void][IO.Directory]::CreateDirectory($stateRoot)
        $stateWritable=$true
        $report.status='TASK_PREFLIGHT'
        Save-L07Session
    }
    $report.phase='HOST'
    $existing=Get-L07Host
    if ($null -ne $existing) {
        $report.editor=$existing; $report.status='ATTACH_EXISTING'; $report.subject=$null
        Save-L07Session
        if ($PreflightOnly) { return [pscustomobject]$report }
        return
    }
    Assert-L07OtherTaskIdle
    $report.phase='DESKTOP'
    $null=Get-L07ConsoleSid
    $report.phase='RESERVE'
    $report.free_d_bytes=[IO.DriveInfo]::new('D:\').AvailableFreeSpace
    if ($report.free_d_bytes -lt 5GB) { Stop-L07 'DISK_RESERVE' }
    $report.phase='PROJECT'
    $projectProof=Get-L07FileProof $project 256KB
    $report.file_proofs+=,$projectProof
    # Bind the parsed JSON to the exact bytes whose descriptor hash is admitted.
    $projectBytes=[IO.File]::ReadAllBytes($project)
    $readHash=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($projectBytes)).ToLowerInvariant()
    if ($projectBytes.Length -ne $projectProof.size_bytes -or $readHash -cne $projectProof.sha256) { Stop-L07 'PROJECT_CHANGED_DURING_READ' }
    $projectData=[Text.UTF8Encoding]::new($false,$true).GetString($projectBytes).TrimStart([char]0xFEFF) | ConvertFrom-Json -AsHashtable -Depth 32
    Assert-L07ProjectIdentity $projectData $projectProof.sha256
    $report.phase='CHECKPOINT'
    $materialRoot='Content/Generated/YACS/Lesson07_Unified/Materials/'
    $pins=@(
        @('Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap',1838638056,'d14a132cdfbb59f340a4c5ed503296153bb00700fa2a790cd3d5f900ebc5ac75'),
        @(($materialRoot+'MI_Landscape_Instance_YACS.uasset'),39740,'8c1dc875218a027a5ac83d88f8eedba49769fdd8494d287e7264807082eb11bf'),
        @(($materialRoot+'M_Landscape_YACS.uasset'),208956,'53a1d68a97a5205a25463dea5c6aaaec4a9bb1167a1ce9e131a84406327fad66'),
        @(($materialRoot+'TA_Colour_Unified.uasset'),24178947,'9efed079b6fba9f1c900c4348b9dceabab785a6eadcaf0ea21a6fe8b775568cf'),
        @(($materialRoot+'TA_Normal_Unified.uasset'),40441798,'838a513e1c725e4e69da26715e6dff3734bfa2e98ef7d91a31278c2a0dbaf0f1'),
        @(($materialRoot+'TA_Masks_Unified.uasset'),12124066,'e34fb9b1a51d4251058b6cf3da66951f3abc26ac4a6ab1c25f9d348c6923c9e8')
    )
    foreach ($pin in $pins) {
        $proof=Get-L07FileProof (Join-Path $projectRoot $pin[0])
        $report.file_proofs+=,$proof
        if ($proof.size_bytes -ne $pin[1] -or $proof.sha256 -cne $pin[2]) {
            $report.checkpoint_mismatch=[ordered]@{expected_size_bytes=$pin[1];expected_sha256=$pin[2];observed=$proof}
            Stop-L07 'CHECKPOINT_HASH_OR_SIZE'
        }
    }
    $report.checkpoint_bytes_verified=$true
    $report.phase='MODULES'
    $version=Read-L07Json (Join-Path $engineRoot 'Engine/Build/Build.version')
    if ($version.MajorVersion -ne 5 -or $version.MinorVersion -ne 8 -or $version.PatchVersion -ne 2 -or
        $version.Changelist -ne 56702186) { Stop-L07 'ENGINE_VERSION' }
    $report.file_proofs+=,(Get-L07FileProof $editorExe 1GB)
    $engineManifest=Read-L07Json (Join-Path $engineRoot 'Engine/Binaries/Win64/UnrealEditor.modules') 2MB
    $buildId=[string]$engineManifest.BuildId
    if ($buildId -cnotmatch '^[A-Za-z0-9-]{1,128}$') { Stop-L07 'ENGINE_BUILD_ID' }
    $wingman=Join-Path $engineRoot 'Engine/Plugins/Marketplace/Wingman'
    $descriptor=Get-L07FileProof (Join-Path $wingman 'Wingman.uplugin') 256KB
    $report.file_proofs+=,$descriptor
    if ($descriptor.size_bytes -ne 4580 -or $descriptor.sha256 -cne '54f34b9d3be93d951c3d1acd3ad37e04b391fd9b398f199c499d1f5dbd6b3b7e') { Stop-L07 'WINGMAN_DESCRIPTOR_HASH_OR_SIZE' }
    $plugin=Read-L07Json (Join-Path $wingman 'Wingman.uplugin')
    if ($plugin.VersionName -cne '0.20.5') { Stop-L07 'WINGMAN_VERSION' }
    $moduleInputs=@(
        @((Join-Path $projectRoot 'Binaries/Win64'),@('YetAnotherCyclingSim','YetAnotherCyclingSimEditor')),
        @((Join-Path $projectRoot 'Plugins/RoadForge/Binaries/Win64'),@('RoadForge')),
        @((Join-Path $wingman 'Binaries/Win64'),@('Wingman')),
        @((Join-Path $engineRoot 'Engine/Plugins/Experimental/PythonScriptPlugin/Binaries/Win64'),@('PythonScriptPlugin')),
        @((Join-Path $engineRoot 'Engine/Plugins/Editor/EditorScriptingUtilities/Binaries/Win64'),@('EditorScriptingUtilities'))
    )
    foreach ($moduleInput in $moduleInputs) { $report.module_proofs+=@(Get-L07ModuleProof $moduleInput[0] $moduleInput[1] $buildId) }
    $report.module_build_ids_verified=$true; $report.engine_build_id=$buildId
    $report.status='PREFLIGHT_PASS'; $report.subject=$null
    if ($PreflightOnly) { return [pscustomobject]$report }

    $report.phase='HANDOFF'
    $deadline=[DateTime]::Parse([string]$install.start_permitted_until_utc).ToUniversalTime()
    if ($deadline -lt [DateTime]::UtcNow -or $deadline -gt [DateTime]::UtcNow.AddMinutes(5)) { Stop-L07 'START_REQUEST_EXPIRED' }
    $existing=Get-L07Host
    if ($null -ne $existing) { $report.editor=$existing; $report.status='ATTACH_EXISTING'; Save-L07Session; return }
    Assert-L07OtherTaskIdle
    if ((Get-L07ConsoleSid) -cne $install.desktop_sid) { Stop-L07 'CONSOLE_OWNER_CHANGED' }
    if ([IO.DriveInfo]::new('D:\').AvailableFreeSpace -lt 5GB) { Stop-L07 'DISK_RESERVE_CHANGED' }
    $arguments=@(
        ('"'+$project+'"'), $mapPackage,
        '-NoP4','-NoLiveCoding','-EnablePlugins=Wingman,PythonScriptPlugin,EditorScriptingUtilities',
        '-ini:EditorPerProjectUserSettings:[/Script/UnrealEd.EditorLoadingSavingSettings]:bAutoSaveEnable=False',
        ('-AbsLog="'+(Join-Path $stateRoot 'editor.log')+'"')
    )
    $report.status='STARTING_NOT_NATIVE_PROOF'; $report.autosave_session_override=$true
    Save-L07Session
    if ([DateTime]::UtcNow -ge $deadline) { Stop-L07 'START_REQUEST_EXPIRED' }
    $editor=Start-Process -FilePath $editorExe -ArgumentList $arguments -WorkingDirectory $projectRoot -PassThru
    $report.editor=[ordered]@{
        editor_pid=$editor.Id; editor_start_filetime_utc=$editor.StartTime.ToUniversalTime().ToFileTimeUtc().ToString()
        editor_started_utc=$editor.StartTime.ToUniversalTime().ToString('o'); editor_executable_path=$editorExe
        interactive_session_id=$editor.SessionId; canonical_project_matches=$true
    }
    $report.status='EDITOR_RUNNING_NATIVE_NOT_VERIFIED'; $report.phase='SUPERVISING'
    Save-L07Session
} catch {
    $report.status='BLOCKED_'+$report.phase
    $report.error_type=$_.Exception.GetType().Name
    $reason=[string]$_.Exception.Data['l07_reason']
    $report.reason_code=if ($reason -cmatch '^[A-Z][A-Z0-9_]{0,79}$') { $reason } else { 'SYSTEM_EXCEPTION' }
    if ($null -ne $editor) { $report.status='EDITOR_RETAINED_AFTER_STARTUP_ERROR' }
    try { Save-L07Session } catch { }
    if ($PreflightOnly) { return [pscustomobject]$report }
    if ($null -eq $editor) { exit 1 }
}
# The scheduled action remains alive with its Editor. There is no timeout kill,
# retry, autorestart, native request, map load, save, or cleanup of owner work.
while ($null -ne $editor) {
    try {
        $editor.Refresh()
        if ($editor.HasExited) { $report.status='EDITOR_EXITED_NO_AUTORESTART'; Save-L07Session; break }
        Save-L07Session
    } catch { }
    Start-Sleep -Seconds 10
}
