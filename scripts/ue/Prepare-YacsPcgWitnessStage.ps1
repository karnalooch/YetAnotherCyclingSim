#requires -Version 7.4
<#
.SYNOPSIS
  Audit or build/stage the #365 native point-count witness without deploying it.
.DESCRIPTION
  Inspect is strictly read-only. BuildStage compiles ONLY the D:\yacs\project
  worktree and copies the project modules plus the optional witness plugin
  into a fresh project-relative staging directory on D:. It never touches
  a running Editor's project, DLL, Live Host,
  saved levels or source checkpoint. It never restarts or hot-reloads UE.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedHead,
    [ValidateSet('Inspect', 'BuildStage')][string]$Action = 'Inspect'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$PinnedProjectRoot = 'D:\yacs\project'
$EngineRoot = 'D:\yacs\engine\UE_5.8'
$StageRoot = 'D:\yacs\work\pcg365-native-witness-stage'
$CanonicalRoot = 'D:\yacs\work\level-editor-review\b9fddea3f602-y473save01\Content\Generated\YACS\LiveCheckpoints\R2a00f7ebba40'
$ProjectFile = Join-Path $ProjectRoot 'YetAnotherCyclingSim.uproject'
# Opt-in only for PCG365 builds; the historical launcher remains byte-pinned.
$BuildTarget = 'YetAnotherCyclingSimPcg365Editor'
$BuildTargetFile = Join-Path $ProjectRoot 'Source/YetAnotherCyclingSimPcg365Editor.Target.cs'
$PinnedProjectSha256 = '09fbd6cd85fbdd299a3e37cfb65658e1210183878516599c90b783acc1d8099b'
$PinnedProjectBytes = 1152
$WitnessPluginName = 'YacsPcgWitness'
$WitnessPluginRelativeRoot = 'Plugins/YacsPcgWitness'
$WitnessPluginRoot = Join-Path $ProjectRoot $WitnessPluginRelativeRoot
$WitnessPluginDescriptor = Join-Path $WitnessPluginRoot 'YacsPcgWitness.uplugin'
$WitnessSourcePaths = @(
    'Source/YacsPcgWitness/YacsPcgWitness.Build.cs',
    'Source/YacsPcgWitness/Public/PCG/YacsPcgWitnessToolset.h',
    'Source/YacsPcgWitness/Private/PCG/YacsPcgWitnessToolset.cpp',
    'Source/YacsPcgWitness/Private/YacsPcgWitnessModule.cpp'
)
$CandidateDll = Join-Path $WitnessPluginRoot 'Binaries/Win64/UnrealEditor-YacsPcgWitness.dll'
$CandidateModules = Join-Path $WitnessPluginRoot 'Binaries/Win64/UnrealEditor.modules'
$ProjectModules = Join-Path $ProjectRoot 'Binaries/Win64/UnrealEditor.modules'
$ProjectModuleFiles = [ordered]@{
    YetAnotherCyclingSim = 'UnrealEditor-YetAnotherCyclingSim.dll'
    YetAnotherCyclingSimEditor = 'UnrealEditor-YetAnotherCyclingSimEditor.dll'
}
$BuildCandidateDlls = @($CandidateDll) + @($ProjectModuleFiles.Values | ForEach-Object {
    Join-Path $ProjectRoot "Binaries/Win64/$_"
})
$RuntimeEnableArgument = '-EnablePlugins=YacsPcgWitness'
$EngineModules = Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor.modules'
$BuildBat = Join-Path $EngineRoot 'Engine/Build/BatchFiles/Build.bat'
$StagePath = Join-Path $StageRoot $ExpectedHead

function Require-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file not found: $Path"
    }
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Refuse reparse-point input: $Path"
    }
    return $item
}

function File-Identity([string]$Path) {
    $item = Require-File $Path
    return [ordered]@{
        path = $item.FullName
        bytes = [long]$item.Length
        sha256 = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

function Check-HeadAndWorkspace {
    if ($ProjectRoot.TrimEnd('\') -ine $PinnedProjectRoot) {
        throw "Expected the dedicated D: source worktree, got: $ProjectRoot"
    }
    $projectIdentity = File-Identity $ProjectFile
    if ($projectIdentity.sha256 -cne $PinnedProjectSha256 -or
        $projectIdentity.bytes -ne $PinnedProjectBytes) {
        throw 'PINNED_LAUNCHER_PROJECT_CHANGED: original .uproject must retain historical SHA256 and 1152 bytes.'
    }
    [void](Require-File $BuildTargetFile)
    [void](Require-File (Join-Path $ProjectRoot 'scripts/ci/Assert-YacsBuildIsolation.ps1'))
    [void](Require-File $WitnessPluginDescriptor)
    foreach ($path in $WitnessSourcePaths) {
        [void](Require-File (Join-Path $WitnessPluginRoot $path))
    }
    $head = ((& git -C $ProjectRoot rev-parse HEAD) | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $head -cne $ExpectedHead) {
        throw "Exact HEAD mismatch: found $head, expected $ExpectedHead"
    }
    $branch = ((& git -C $ProjectRoot branch --show-current) | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $branch -cne 'codex/365-world-graph') {
        throw "Wrong worktree branch: $branch"
    }
    $dirty = @(& git -C $ProjectRoot status --porcelain --untracked-files=no)
    if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) {
        throw 'Tracked source changes detected. Do not overwrite or discard them.'
    }
}

function Check-CanonicalCheckpoint {
    $expected = [ordered]@{
        'L_RoadSurface.umap' = 'cf806999d73e6762ba6d91fab8b4e29d6c475a828ad9afcd525462054602ed1a'
        'M_Road.uasset' = 'd5bf7fdc7d34e70c30b29ec37d2f4c04afa01cd3dc9a9c12cec707be48078842'
        'M_Shoulder.uasset' = '94c40717a34d2b18f6d706abc7714cb6cbfb4ed0d631dda8bd1c624c38e7ae65'
        'MI_Road.uasset' = '7d96a2396bb8ef9e5d4d19d65b6c7e9d00e7b0e80ebd5ff5733dbab1a61e9a92'
        'MI_Shoulder.uasset' = '76425a2289c3907a8f3c831ad24fb1ba1f219e79204507efdce222c831c76cdf'
    }
    if (-not (Test-Path -LiteralPath $CanonicalRoot -PathType Container)) {
        throw "CANONICAL_CHECKPOINT_MISSING: $CanonicalRoot"
    }
    $results = @()
    foreach ($name in $expected.Keys) {
        $identity = File-Identity (Join-Path $CanonicalRoot $name)
        if ($identity.sha256 -cne $expected[$name]) {
            throw "CANONICAL_CHECKPOINT_MUTATED: $name"
        }
        $results += [pscustomobject]@{ name = $name; bytes = $identity.bytes; sha256 = $identity.sha256 }
    }
    return @($results)
}

function Check-EditorBuildIsolation {
    . (Join-Path $ProjectRoot 'scripts/ci/Assert-YacsBuildIsolation.ps1')
    Assert-YacsBuildIsolation -ProjectPath $ProjectFile
    $records = @()
    $processes = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        $_.Name -in @('UnrealEditor.exe', 'UnrealEditor-Cmd.exe')
    })
    foreach ($process in $processes) {
        $native = Get-Process -Id ([int]$process.ProcessId) -ErrorAction SilentlyContinue
        if ($null -eq $native) { continue }
        $candidateNames = @($BuildCandidateDlls | ForEach-Object { Split-Path $_ -Leaf })
        $modules = @($native.Modules | Where-Object { $_.ModuleName -iin $candidateNames })
        foreach ($module in $modules) {
            $loadedPath = [IO.Path]::GetFullPath([string]$module.FileName)
            if ($loadedPath -iin $BuildCandidateDlls) {
                throw "The build candidate DLL is already loaded by PID $($native.Id); refuse compilation."
            }
            $records += [pscustomobject]@{
                pid = [int]$native.Id
                start_time_utc = $native.StartTime.ToUniversalTime().ToString('o')
                loaded_module = (File-Identity $loadedPath)
            }
        }
    }
    return @($records)
}

function Assert-StageRoot {
    if (Test-Path -LiteralPath $StageRoot) {
        $rootItem = Get-Item -LiteralPath $StageRoot -Force
        if ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'Stage root is a reparse point.'
        }
    }
    if (Test-Path -LiteralPath $StagePath) {
        throw "Stage already exists, never overwrite it: $StagePath"
    }
}

function Check-ModuleManifest(
    [string]$Path,
    [string]$ExpectedBuildId,
    [System.Collections.IDictionary]$ExpectedModules
) {
    [void](Require-File $Path)
    $metadata = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -AsHashtable
    if (-not $metadata.BuildId -or $metadata.BuildId -cne $ExpectedBuildId) {
        throw "Editor and engine BuildId mismatch; block staging: $Path"
    }
    if ($metadata.Modules -isnot [System.Collections.IDictionary]) {
        throw "Missing module-to-DLL mapping: $Path"
    }
    foreach ($name in $ExpectedModules.Keys) {
        if (-not $metadata.Modules.Contains($name) -or
            $metadata.Modules[$name] -cne $ExpectedModules[$name]) {
            throw "Unexpected module-to-DLL mapping for ${name}: $Path"
        }
        [void](Require-File (Join-Path (Split-Path $Path -Parent) $ExpectedModules[$name]))
    }
    return [pscustomobject]@{
        identity = File-Identity $Path
        build_id = [string]$metadata.BuildId
        modules = $ExpectedModules
    }
}

Check-HeadAndWorkspace
$checkpoint = @(Check-CanonicalCheckpoint)
$loaded = @(Check-EditorBuildIsolation)
[void](Require-File $BuildBat)
[void](Require-File $EngineModules)

if ($Action -ceq 'Inspect') {
    [ordered]@{
        status = 'AUDITED_NOT_BUILT_OR_DEPLOYED'
        source_sha = $ExpectedHead
        source_project = $ProjectFile
        isolated_compilation_allowed = $true
        live_editor_modules = $loaded
        checkpoint_packages_verified = $checkpoint.Count
        stage_target = $StagePath
        witness_plugin = $WitnessPluginName
        required_runtime_enable_argument = $RuntimeEnableArgument
        warning = 'Does not validate unsaved in-editor state; native witness remains blocked until approved deployment and trusted in-process transport.'
    } | ConvertTo-Json -Depth 9
    exit 0
}

Assert-StageRoot
$drive = [IO.DriveInfo]::new('D:\')
if ($drive.AvailableFreeSpace -lt 5GB) {
    throw 'Insufficient D: reserve (<5 GiB); do not start UBT.'
}

$buildStartedUtc = [DateTime]::UtcNow
$log = Join-Path $env:TEMP ("yacs-pcg365-native-" + $ExpectedHead + "-" + [Guid]::NewGuid().ToString('N') + ".log")
$arguments = @(
    $BuildTarget,
    'Win64',
    'Development',
    "-Project=$ProjectFile",
    '-WaitMutex',
    '-NoHotReloadFromIDE'
)
& $BuildBat @arguments 2>&1 | Tee-Object -FilePath $log
$buildExit = $LASTEXITCODE
if ($buildExit -ne 0) {
    throw "UBT failed ($buildExit), see log: $log"
}

# An exit code of zero alone does not establish that this source produced a
# fresh DLL. Require a new link artifact for this explicitly requested build.
$dllItem = Require-File $CandidateDll
if ($dllItem.LastWriteTimeUtc -lt $buildStartedUtc.AddMinutes(-2)) {
    throw "No freshly linked DLL for requested exact HEAD. Preserve UBT log: $log"
}
$engineBuildId = (Get-Content -LiteralPath $EngineModules -Raw | ConvertFrom-Json).BuildId
if (-not $engineBuildId) {
    throw 'Editor and engine BuildId mismatch; block staging.'
}
$projectModuleIdentity = Check-ModuleManifest $ProjectModules $engineBuildId $ProjectModuleFiles
$pluginModuleIdentity = Check-ModuleManifest $CandidateModules $engineBuildId ([ordered]@{
    YacsPcgWitness = 'UnrealEditor-YacsPcgWitness.dll'
})
Check-HeadAndWorkspace
$checkpointAfter = @(Check-CanonicalCheckpoint)
$loadedAfter = @(Check-EditorBuildIsolation)

[void](New-Item -ItemType Directory -Path $StagePath -ErrorAction Stop)
$relativePaths = @(
    'YetAnotherCyclingSim.uproject',
    'Source/YetAnotherCyclingSimPcg365Editor.Target.cs',
    'Binaries/Win64/UnrealEditor.modules',
    "$WitnessPluginRelativeRoot/YacsPcgWitness.uplugin",
    "$WitnessPluginRelativeRoot/Binaries/Win64/UnrealEditor-YacsPcgWitness.dll",
    "$WitnessPluginRelativeRoot/Binaries/Win64/UnrealEditor.modules"
)
$relativePaths += @($WitnessSourcePaths | ForEach-Object { "$WitnessPluginRelativeRoot/$_" })
$relativePaths += @($ProjectModuleFiles.Values | ForEach-Object { "Binaries/Win64/$_" })
foreach ($dll in $BuildCandidateDlls) {
    $pdb = [IO.Path]::ChangeExtension($dll, '.pdb')
    if (Test-Path -LiteralPath $pdb -PathType Leaf) {
        $relativePaths += [IO.Path]::GetRelativePath($ProjectRoot, $pdb).Replace('\', '/')
    }
}
$files = @($relativePaths | ForEach-Object {
    [pscustomobject]@{ source = Join-Path $ProjectRoot $_; relative_path = $_ }
})
$files += [pscustomobject]@{ source = $log; relative_path = 'build.log' }
$artifacts = @()
foreach ($file in $files) {
    $original = File-Identity $file.source
    # Project-relative paths keep the project and plugin module manifests
    # separate. This stage is an overlay, never a deployed or standalone map.
    $destination = Join-Path $StagePath $file.relative_path
    if (Test-Path -LiteralPath $destination) { throw "Staging collision: $destination" }
    [void](New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force)
    Copy-Item -LiteralPath $file.source -Destination $destination -ErrorAction Stop
    $copied = File-Identity $destination
    if ($original.sha256 -cne $copied.sha256 -or $original.bytes -ne $copied.bytes) {
        throw "Staged byte identity drift: $destination"
    }
    $artifacts += [pscustomobject]@{
        relative_path = $file.relative_path
        filename = Split-Path $file.source -Leaf
        bytes = $copied.bytes
        sha256 = $copied.sha256
    }
}
$manifest = [ordered]@{
    schema_version = 2
    status = 'STAGED_NOT_DEPLOYED'
    source_sha = $ExpectedHead
    source_branch = 'codex/365-world-graph'
    created_at_utc = [DateTime]::UtcNow.ToString('o')
    build_exit_code = [int]$buildExit
    build_target = $BuildTarget
    witness_plugin = $WitnessPluginName
    witness_module = 'YacsPcgWitness'
    required_runtime_enable_argument = $RuntimeEnableArgument
    stage_layout = 'PROJECT_RELATIVE_OVERLAY_NOT_DEPLOYED'
    original_project_sha256 = $PinnedProjectSha256
    engine_build_id = $engineBuildId
    module_manifests = @($projectModuleIdentity, $pluginModuleIdentity)
    source_project = $ProjectFile
    stage_dir = $StagePath
    artifacts = $artifacts
    original_live_modules = $loaded
    post_build_live_modules = $loadedAfter
    canonical_source_checkpoint = $checkpointAfter
    project_world_unchanged = 'NOT_CHECKED_IN_EDITOR'
    native_reader_loaded = $false
    witness_admission = 'BLOCKED_PENDING_NATIVE_DEPLOYMENT'
    owner_restart_approved = $false
    source_world_saved = $false
    deployed_dll_mutated = $false
}
$manifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $StagePath 'staging-manifest.json') -Encoding utf8
$manifest | ConvertTo-Json -Depth 12
