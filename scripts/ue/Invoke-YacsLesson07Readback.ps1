#requires -Version 7.4
<#
.SYNOPSIS
    Read the existing pinned L07 map with ordinary verified CI DLLs in a new project.
.DESCRIPTION
    No build, cache selection/publication, source save, Houdini cook, asset import,
    repair or deployment. Known asset roots are bounded copies, not an assumed
    dependency closure. Missing native packages/fields block completeness.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string] $ExpectedHead,
    [Parameter(Mandatory)][ValidatePattern('^[1-9][0-9]{0,19}-[1-9][0-9]{0,5}$')][string] $RunToken,
    [Parameter(Mandatory)][ValidatePattern('^[1-9][0-9]{0,19}$')][string] $ProtectedCiRunId,
    [string] $WorkspaceConfig = 'D:\yacs\workspace.json',
    [string] $RepoRoot = (Join-Path $PSScriptRoot '../..')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'The isolated L07 reader requires the trusted Windows host.' }
$MapRelative = 'Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap'
$OriginalMapPin = @{ sha256 = '61aa69146ce6822b20d0d2ffe93e6840ce238b941fea3f5ae955c0e15a7814f7'; size_bytes = [long]1842190204 }
$MapPin = @{ sha256 = 'd14a132cdfbb59f340a4c5ed503296153bb00700fa2a790cd3d5f900ebc5ac75'; size_bytes = [long]1838638056 }
$MaterialPins = @{
    'Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset' = @{
        sha256 = 'dcd34f9381414c0d63bbd234072ef1b4ac7dd62cf04a4ecc1fe2c48a029d3d2d'; size_bytes = [long]40154
    }
    'Content/Generated/YACS/Lesson07_Unified/Materials/M_Landscape_YACS.uasset' = @{
        sha256 = '53a1d68a97a5205a25463dea5c6aaaec4a9bb1167a1ce9e131a84406327fad66'; size_bytes = [long]208956
    }
}
$LevelPackage = '/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07'
$SourceRoot = 'D:\yacs\project'
$AssetRoots = @('Content/Generated/YACS/Lesson07_Unified', 'Content/PegasusDemo/Materials')
$FileLimit = 3GB
$AssetByteLimit = 8GB
$AssetFileLimit = 2048
$ownedEditor = $null
$ownedHelper = $null
$EvidenceRoot = $null
$EvidenceOwned = $false
$CandidateRoot = $null
$sourceMap = $null
$candidateMap = $null
$protectedInputs = [Collections.Generic.List[object]]::new()
$originalEnvironment = @{}
foreach ($name in @('YACS_WORKSPACE_CONFIG', 'GIT_OPTIONAL_LOCKS', 'PYTHONDONTWRITEBYTECODE')) {
    $originalEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$receipt = [ordered]@{
    schema_version = 1; source_head = $ExpectedHead; run_token = $RunToken
    protected_ci_run_id = $ProtectedCiRunId; protected_ci_head = $ExpectedHead
    status = 'PREPARATION_PENDING'; started_at_utc = [DateTime]::UtcNow.ToString('o'); ended_at_utc = $null
    canonical_source_root = $SourceRoot; candidate_root = $null; level = $LevelPackage
    expected_map = $MapPin; original_map = $OriginalMapPin; expected_materials = $MaterialPins
    source_map_before = $null; source_map_after = $null
    candidate_map_before = $null; candidate_map_after = $null
    source_map_unchanged = $null; candidate_map_unchanged = $null
    source_fingerprints = $null; cache_provenance = $null; binary_provenance = @()
    known_asset_roots = $AssetRoots; asset_inventory = @(); staged_assets = @()
    dependency_closure_complete = $false; houdini_engine_staged = $false
    host_checks = @(); helper_processes = @(); protected_inputs_after = @()
    protected_inputs_unchanged = $null; proof_files = [ordered]@{}
    owned_editor_pid = $null; owned_editor_exit_code = $null; owned_editor_stopped_on_failure = $false
    native_log_findings = $null; structural_readback_complete = $false; geometry_accepted = $false
    source_height_interpolation_proved = $false; visibility_layer_proved_in_ue = $false
    material_render_verified = $false; owner_visual_pass = $false; performance_pass = $false
    native_reopen_after_repair = 'NOT_RUN'; error = $null; secondary_errors = @()
}

function Assert-L07PlainPath {
    param([Parameter(Mandatory)][string] $Path)
    if ($Path -match '[\x00\r\n"]' -or -not [IO.Path]::IsPathFullyQualified($Path) -or
        ($Path -split '[\\/]') -contains '..') { throw 'An absolute plain L07 path is required.' }
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        try { $attributes = [IO.File]::GetAttributes($cursor) }
        catch [IO.FileNotFoundException] { $attributes = $null }
        catch [IO.DirectoryNotFoundException] { $attributes = $null }
        if ($null -ne $attributes -and ($attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'L07 refuses symlinks and junctions.'
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}

function Get-L07Identity {
    param([string] $Path, [long] $Limit = 3GB, [switch] $AllowEmpty)
    Assert-L07PlainPath $Path
    $before = Get-Item -LiteralPath $Path -Force
    if ($before.PSIsContainer -or $before.Length -gt $Limit -or ($before.Length -eq 0 -and -not $AllowEmpty)) {
        throw 'L07 input is not a bounded regular file.'
    }
    $length = $before.Length
    $ticks = $before.LastWriteTimeUtc.Ticks
    $stream = [IO.File]::OpenRead($Path)
    $hash = [Security.Cryptography.SHA256]::Create()
    try { $digest = [Convert]::ToHexString($hash.ComputeHash($stream)).ToLowerInvariant() }
    finally { $hash.Dispose(); $stream.Dispose() }
    $after = Get-Item -LiteralPath $Path -Force
    if ($after.Length -ne $length -or $after.LastWriteTimeUtc.Ticks -ne $ticks) { throw 'L07 input changed during hashing.' }
    return [ordered]@{ path = [IO.Path]::GetFullPath($Path); size_bytes = $length; sha256 = $digest }
}

function Assert-L07Identity {
    param($Identity, [long] $Limit = 3GB, [switch] $AllowEmpty)
    $actual = Get-L07Identity $Identity.path $Limit -AllowEmpty:$AllowEmpty
    if ($actual.sha256 -cne $Identity.sha256 -or $actual.size_bytes -ne $Identity.size_bytes) {
        throw ('Authenticated L07 input changed: ' + $Identity.path)
    }
}

function Assert-L07Pin {
    param($Identity, $Pin)
    if ($Identity.sha256 -cne $Pin.sha256 -or $Identity.size_bytes -ne $Pin.size_bytes) {
        throw ('L07 asset differs from its exact current pin: ' + $Identity.path)
    }
}

function Protect-L07Identity {
    param($Identity, [string] $Role, [long] $Limit = 3GB, [switch] $AllowEmpty)
    $protectedInputs.Add([ordered]@{ identity = $Identity; role = $Role; limit = $Limit; allow_empty = [bool]$AllowEmpty })
}

function Read-L07Json {
    param([string] $Path, [long] $Limit = 2MB)
    $identity = Get-L07Identity $Path $Limit
    $value = [IO.File]::ReadAllText($Path) | ConvertFrom-Json -AsHashtable -Depth 50
    Assert-L07Identity $identity $Limit
    if ($value -isnot [Collections.IDictionary]) { throw 'L07 JSON must be an object.' }
    return @{ identity = $identity; value = $value }
}

function Write-L07JsonExclusive {
    param([string] $Path, $Value)
    Assert-L07PlainPath $Path
    $bytes = [Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 50))
    if ($bytes.Length -gt 8MB) { throw 'L07 evidence exceeds its fixed bound.' }
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
}

function Copy-L07Exclusive {
    param($Identity, [string] $Target, [long] $Limit = 3GB, [switch] $AllowEmpty)
    Assert-L07Identity $Identity $Limit -AllowEmpty:$AllowEmpty
    Assert-L07PlainPath $Target
    if (Test-Path -LiteralPath $Target) { throw 'L07 cannot overwrite an existing output.' }
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Target))
    $inputStream = [IO.File]::OpenRead($Identity.path)
    try {
        $outputStream = [IO.File]::Open($Target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $inputStream.CopyTo($outputStream) } finally { $outputStream.Dispose() }
    } finally { $inputStream.Dispose() }
    $copied = Get-L07Identity $Target $Limit -AllowEmpty:$AllowEmpty
    if ($copied.sha256 -cne $Identity.sha256 -or $copied.size_bytes -ne $Identity.size_bytes) {
        throw 'Physical L07 copy differs from its source.'
    }
    Assert-L07Identity $Identity $Limit -AllowEmpty:$AllowEmpty
    return $copied
}

function Assert-L07Materialized {
    param([string] $Path)
    $stream = [IO.File]::OpenRead($Path)
    try {
        $prefix = [byte[]]::new(64)
        $count = $stream.Read($prefix, 0, $prefix.Length)
        if ([Text.Encoding]::ASCII.GetString($prefix, 0, $count).StartsWith('version https://git-lfs.github.com/spec/v1')) {
            throw 'A required L07 asset is only an LFS pointer; no download is permitted.'
        }
    } finally { $stream.Dispose() }
}

function Copy-L07InventoriedAsset {
    param($Asset, [string] $TargetRoot)
    $identity = Get-L07Identity $Asset.path 3GB
    if ($identity.size_bytes -ne $Asset.size_bytes) {
        throw 'L07 asset changed size after inventory; preserve the planned disk reserve.'
    }
    $copied = Copy-L07Exclusive $identity (Join-Path $TargetRoot $Asset.relative) 3GB
    return @{ relative = $Asset.relative; source_identity = $identity; copied_identity = $copied }
}

function Get-L07AssetInventory {
    param([string] $Root, [string[]] $RelativeRoots, [long] $MaxBytes = 8GB, [int] $MaxFiles = 2048)
    $queue = [Collections.Generic.Queue[string]]::new()
    $rows = [Collections.Generic.List[object]]::new()
    $bytes = [long]0
    $entries = 0
    foreach ($relative in $RelativeRoots) {
        if ($relative -notmatch '^Content(?:/[A-Za-z0-9_/]+)?$' -or $relative.Contains('..')) { throw 'Invalid fixed L07 asset root.' }
        $path = Join-Path $Root $relative
        Assert-L07PlainPath $path
        if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw ('Known L07 asset root is absent: ' + $relative) }
        $queue.Enqueue($path)
    }
    while ($queue.Count) {
        foreach ($item in @(Get-ChildItem -LiteralPath $queue.Dequeue() -Force)) {
            if (++$entries -gt 8192) { throw 'L07 directory inventory exceeds its bounded entry count.' }
            Assert-L07PlainPath $item.FullName
            if ($item.PSIsContainer) { $queue.Enqueue($item.FullName); continue }
            if ($item.Extension.ToLowerInvariant() -notin @('.uasset', '.umap', '.uexp', '.ubulk')) { continue }
            $relative = [IO.Path]::GetRelativePath($Root, $item.FullName).Replace('\', '/')
            if ($item.Extension -ieq '.umap' -and $relative -cne $MapRelative) { throw 'Only the pinned L07 map may be staged.' }
            $bytes += [long]$item.Length
            if ($item.Length -le 0 -or $item.Length -gt 3GB -or $rows.Count -ge $MaxFiles -or $bytes -gt $MaxBytes) {
                throw 'L07 asset inventory exceeds its file/count/byte bound.'
            }
            Assert-L07Materialized $item.FullName
            $rows.Add([ordered]@{ relative = $relative; path = $item.FullName; size_bytes = [long]$item.Length })
        }
    }
    if ($rows.Count -eq 0) { throw 'Known L07 roots contain no materialized Unreal assets.' }
    return @($rows | Sort-Object relative)
}

function Assert-L07Reserve {
    param([long] $PlannedBytes = 0)
    $free = ([IO.DriveInfo]::new('D:\')).AvailableFreeSpace
    if ($PlannedBytes -lt 0 -or $free - $PlannedBytes -lt 30GB) { throw 'L07 must retain at least 30 GiB after all planned physical copies.' }
    return $free
}

function Assert-L07IdleHost {
    $state = & (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
    $houdini = @(Get-Process -Name hython,houdini,hbatch -ErrorAction SilentlyContinue)
    $receipt.host_checks += [ordered]@{ status = $state.status; checked_at_utc = $state.checked_at_utc
        remote_ci_count = $state.remote_ci_count; local_or_unknown_count = $state.local_or_unknown_count
        houdini_process_ids = @($houdini | ForEach-Object Id) }
    if ($state.status -cne 'IDLE' -or $houdini.Count) { throw 'L07 yields to the current Unreal/Houdini host owner.' }
}

function Assert-L07Source {
    param([string] $Root, [string] $Head)
    $actual = @(& git -C $Root rev-parse HEAD)
    if ($LASTEXITCODE -ne 0 -or $actual.Count -ne 1 -or $actual[0] -cne $Head) { throw 'L07 source HEAD differs.' }
    & git -C $Root diff --quiet HEAD -- . ':(exclude)Content/**'
    if ($LASTEXITCODE -ne 0) { throw 'Tracked source/config bytes differ from HEAD.' }
    $extra = @(& git -C $Root ls-files --others -- Source ':(glob)Plugins/*/Source/**' ':(glob)Plugins/*/*.uplugin' Config Build '*.uproject')
    if ($LASTEXITCODE -ne 0 -or $extra.Count) { throw 'Untracked native/config inputs cannot be certified.' }
    $scripts = @(& git -C $Root ls-files --others --exclude-standard -- scripts)
    if ($LASTEXITCODE -ne 0 -or $scripts.Count) { throw 'Untracked script inputs cannot be certified.' }
}

function Invoke-L07Helper {
    param([string] $Code, [string] $Argument, [string] $Name)
    $stdout = Join-Path $EvidenceRoot ($Name + '-stdout.json')
    $stderr = Join-Path $EvidenceRoot ($Name + '-stderr.log')
    foreach ($path in @($stdout, $stderr)) { if (Test-Path -LiteralPath $path) { throw 'Owned helper evidence already exists.' } }
    $script:ownedHelper = Start-Process -FilePath $python -ArgumentList @('-B', '-c', ('"' + $Code + '"'), ('"' + $Argument + '"')) `
        -WorkingDirectory $RepoRoot -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
        -Environment @{ PYTHONDONTWRITEBYTECODE = '1'; GIT_OPTIONAL_LOCKS = '0'; PYTHONPATH = ''; PYTHONHOME = ''; GITHUB_OUTPUT = '' }
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while (-not $script:ownedHelper.WaitForExit(200)) {
        if ($timer.Elapsed.TotalSeconds -ge 60) { throw 'Owned L07 read-only helper exceeded 60 seconds.' }
    }
    $script:ownedHelper.WaitForExit()
    $exitCode = $script:ownedHelper.ExitCode
    $receipt.helper_processes += @{ name = $Name; pid = $script:ownedHelper.Id; exit_code = $exitCode }
    $script:ownedHelper.Dispose()
    $script:ownedHelper = $null
    if ($exitCode -ne 0) { throw ('Read-only L07 helper failed: ' + $Name) }
    return (Read-L07Json $stdout 64KB).value
}

function Get-L07Fingerprints {
    param([string] $Root, [string] $Name)
    $code = 'import json,sys; from scripts.ci.classify_changes import unreal_compile_fingerprint,unreal_proof_fingerprint; print(json.dumps(dict(compile=unreal_compile_fingerprint(sys.argv[1]),proof=unreal_proof_fingerprint(sys.argv[1]))))'
    $value = Invoke-L07Helper $code $Root $Name
    if ($value.compile -cnotmatch '^[0-9a-f]{64}$' -or $value.proof -cnotmatch '^[0-9a-f]{64}$') { throw 'Malformed source fingerprints.' }
    return $value
}

function Assert-L07CacheProvenance {
    param($State, $Fingerprints, $Environment)
    if ($State.SchemaVersion -ne 3 -or $State.CompilePassed -isnot [bool] -or -not $State.CompilePassed -or
        $State.ProofPassed -isnot [bool] -or -not $State.ProofPassed -or $State.CompileHead -cnotmatch '^[0-9a-f]{40}$' -or
        $State.ProofHead -cnotmatch '^[0-9a-f]{40}$' -or $State.CompileFingerprint -cne $Fingerprints.compile -or
        $State.ProofFingerprint -cne $Fingerprints.proof -or $State.EnvironmentIdentity -cne $Environment.Identity -or
        $State.EngineIdentity -cne $Environment.Engine.Identity -or $State.ToolchainIdentity -cne $Environment.Toolchain.Identity -or
        -not [string]::Equals($State.EngineRoot, $Environment.Engine.Root, [StringComparison]::OrdinalIgnoreCase) -or
        $State.BuildCachePolicy -cne 'ubt-native-incremental-v1') {
        throw 'Active ordinary CI cache does not match current source/proof/environment; no build or invalidation is permitted.'
    }
}

function Get-L07ModuleClosure {
    param([string] $Root, [string] $Relative, [hashtable] $ExpectedModules, [string] $BuildId)
    $manifest = Read-L07Json (Join-Path $Root $Relative) 64KB
    $value = $manifest.value
    if ($value.BuildId -cne $BuildId -or $value.Modules -isnot [Collections.IDictionary] -or $value.Modules.Count -ne $ExpectedModules.Count) {
        throw 'Ordinary CI module manifest differs from the installed engine or fixed module set.'
    }
    $rows = @(@{ relative = $Relative; source_identity = $manifest.identity })
    foreach ($name in @($ExpectedModules.Keys | Sort-Object)) {
        if ($value.Modules[$name] -cne $ExpectedModules[$name]) { throw 'Unexpected module/DLL mapping.' }
        $relativeDll = [IO.Path]::GetDirectoryName($Relative).Replace('\', '/') + '/' + $ExpectedModules[$name]
        $rows += @{ relative = $relativeDll; source_identity = Get-L07Identity (Join-Path $Root $relativeDll) 512MB }
    }
    return $rows
}

function Get-L07LogFindings {
    param([string] $Path)
    [void](Get-L07Identity $Path 128MB -AllowEmpty)
    $findings = [Collections.Generic.List[string]]::new()
    $count = 0
    $pattern = "(?i)(Can't find file|Couldn't find file|Unable to find package|Failed to (load|find) (package|object|class|module)|Failed to load.*(/Game/|/Script/|/Engine/)|CreateExport.*Failed to load Outer|Log(Linker|UObjectGlobals|ModuleManager):\s*(Warning|Error)|Failed to compile Material|:\s*(Error|Fatal):|Fatal error:|Missing.*modules|module.*could not be loaded)"
    foreach ($line in [IO.File]::ReadLines($Path)) {
        if ($line -match $pattern) {
            $count++
            if ($findings.Count -lt 200) { $findings.Add($line.Substring(0, [Math]::Min(1600, $line.Length))) }
        }
    }
    return @{ total = $count; lines = @($findings); truncated = $count -gt $findings.Count }
}

function Assert-L07NativeReport {
    param($Report, [string] $Head, [string] $Project, [string] $PreparationSha)
    if ($Report.schema_version -ne 2 -or $Report.source_head -cne $Head -or
        -not [string]::Equals($Report.project_root.TrimEnd('\', '/'), $Project.TrimEnd('\', '/'), [StringComparison]::OrdinalIgnoreCase) -or
        $Report.preparation_identity.sha256 -cne $PreparationSha -or $Report.level -cne $LevelPackage -or
        -not $Report.engine_version.StartsWith('5.8.2-56702186') -or
        $Report.status -cne 'STRUCTURE_READBACK_COMPLETE_GEOMETRY_PENDING') { throw 'Native report does not authenticate this completed structural read.' }
    foreach ($name in @('structural_readback_complete', 'candidate_map_unchanged', 'native_component_properties_complete', 'components_pass')) {
        if ($Report[$name] -isnot [bool] -or -not $Report[$name]) { throw ('Native readback is incomplete: ' + $name) }
    }
    foreach ($name in @('geometry_accepted', 'source_height_interpolation_proved', 'visibility_layer_proved_in_ue', 'material_render_verified', 'dependency_closure_complete')) {
        if ($Report[$name] -isnot [bool] -or $Report[$name]) { throw ('Structural readback exceeded its proof scope: ' + $name) }
    }
    if ($Report.total_landscape_actors -ne 4 -or $Report.total_components -ne 4096 -or $Report.reasons.Count -ne 0 -or
        $Report.native_dependencies.observed -isnot [bool] -or -not $Report.native_dependencies.observed -or
        $Report.native_dependencies.value.queries_complete -isnot [bool] -or -not $Report.native_dependencies.value.queries_complete) {
        throw 'Native inventory or package queries are incomplete.'
    }
}

try {
    $RepoRoot = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\', '/')
    $WorkspaceConfig = [IO.Path]::GetFullPath($WorkspaceConfig)
    Assert-L07PlainPath $RepoRoot
    Assert-L07PlainPath $WorkspaceConfig
    if (-not [string]::Equals($WorkspaceConfig, 'D:\yacs\workspace.json', [StringComparison]::OrdinalIgnoreCase) -or
        -not $env:GITHUB_WORKSPACE -or $ExpectedHead -cne $env:GITHUB_SHA -or
        $RunToken -cne ($env:GITHUB_RUN_ID + '-' + $env:GITHUB_RUN_ATTEMPT)) { throw 'Exact owned Actions context and canonical workspace configuration are required.' }
    $workspace = [IO.Path]::GetFullPath($env:GITHUB_WORKSPACE).TrimEnd('\', '/')
    Assert-L07PlainPath $workspace
    if (-not $workspace.StartsWith('D:\yacs\runner\_work\', [StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals($RepoRoot, (Join-Path $workspace ('l07-' + $RunToken)), [StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals($RepoRoot, [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..')).TrimEnd('\', '/'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'L07 requires its own exact source checkout, separate from the accepted project and CI cache.'
    }
    [Environment]::SetEnvironmentVariable('YACS_WORKSPACE_CONFIG', $WorkspaceConfig, 'Process')
    [Environment]::SetEnvironmentVariable('GIT_OPTIONAL_LOCKS', '0', 'Process')
    [Environment]::SetEnvironmentVariable('PYTHONDONTWRITEBYTECODE', '1', 'Process')
    Assert-L07Source $RepoRoot $ExpectedHead
    & (Join-Path $RepoRoot 'scripts/ci/Test-YacsCodeOnlyCheckout.ps1') -RepoRoot $RepoRoot
    $EvidenceRoot = Join-Path $RepoRoot ('Saved/RuntimeProof/Lesson07Readback/' + $RunToken)
    Assert-L07PlainPath $EvidenceRoot
    if (Test-Path -LiteralPath $EvidenceRoot) { throw 'L07 evidence already exists; preserve it.' }
    [void][IO.Directory]::CreateDirectory($EvidenceRoot)
    $EvidenceOwned = $true
    if ($env:GITHUB_ENV) { ('YACS_L07_READBACK_EVIDENCE=' + $EvidenceRoot) | Out-File -LiteralPath $env:GITHUB_ENV -Append -Encoding utf8 }
    Assert-L07IdleHost
    $receipt.free_before_bytes = Assert-L07Reserve
    $sourceMap = Join-Path $SourceRoot $MapRelative
    Assert-L07PlainPath $sourceMap
    # Preserve measured metadata even when a file is too large to hash safely.
    $mapItem = Get-Item -LiteralPath $sourceMap
    $receipt.source_map_before = @{ path = $sourceMap; size_bytes = [long]$mapItem.Length; sha256 = $null }
    $receipt.source_map_before = Get-L07Identity $sourceMap $FileLimit
    if ($receipt.source_map_before.sha256 -cne $MapPin.sha256 -or $receipt.source_map_before.size_bytes -ne $MapPin.size_bytes) {
        throw 'Current saved L07 differs from its pinned receipt; measured identity retained, no candidate/native launch.'
    }
    $reader = Join-Path $RepoRoot 'scripts/ue/readback_lesson07_geometry.py'
    $receipt.proof_files.reader = Get-L07Identity $reader 256KB
    $receipt.proof_files.wrapper = Get-L07Identity $PSCommandPath 256KB
    $receipt.proof_files.workspace_config = Get-L07Identity $WorkspaceConfig 2MB
    foreach ($id in $receipt.proof_files.Values) { Protect-L07Identity $id 'reviewed-input' 2MB }
    foreach ($relative in @('scripts/ue/readback_lesson07_geometry.py', 'scripts/ue/Invoke-YacsLesson07Readback.ps1')) {
        $committed = @(& git -C $RepoRoot rev-parse ($ExpectedHead + ':' + $relative))
        if ($LASTEXITCODE -ne 0 -or $committed.Count -ne 1) { throw 'Executed L07 source is absent from HEAD.' }
        $actual = @(& git -C $RepoRoot hash-object --no-filters -- (Join-Path $RepoRoot $relative))
        if ($LASTEXITCODE -ne 0 -or $actual.Count -ne 1 -or $actual[0] -cne $committed[0]) { throw 'Executed L07 source differs from committed raw bytes.' }
    }
    $python = 'D:\yacs\tool-cache\material-forge\python\Scripts\python.exe'
    Protect-L07Identity (Get-L07Identity $python 128MB) 'read-only-python' 128MB
    $fingerprints = Get-L07Fingerprints $RepoRoot 'current-fingerprints'
    $receipt.source_fingerprints = $fingerprints
    . (Join-Path $RepoRoot 'scripts/ci/Resolve-YacsUnrealBuildEnvironment.ps1')
    $environment = Resolve-YacsUnrealBuildEnvironment -ProjectPath (Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject')
    if (-not $environment -or $environment.Engine.Version -cne '5.8.2-56702186' -or $environment.Identity -cnotmatch '^[0-9a-f]{64}$') {
        throw 'Canonical Unreal 5.8.2 CL56702186/toolchain identity is required.'
    }
    $engine = $environment.Engine
    $receipt.environment = $environment
    $engineManifest = Read-L07Json (Join-Path $engine.Root 'Engine/Binaries/Win64/UnrealEditor.modules') 2MB
    if ($engineManifest.value.BuildId -isnot [string] -or -not $engineManifest.value.BuildId) { throw 'Installed engine BuildId is missing.' }
    Protect-L07Identity $engineManifest.identity 'engine-modules' 2MB
    Protect-L07Identity (Get-L07Identity $engine.UnrealEditorCmdPath 1GB) 'editor-executable' 1GB
    $pointer = Read-L07Json (Join-Path $workspace '_yacs-unreal-ci/active.json') 64KB
    if ($pointer.value.Count -ne 2 -or $pointer.value.schema_version -ne 1 -or
        $pointer.value.worktree -isnot [string] -or $pointer.value.worktree -cnotmatch '^(_unreal-ci-warm|_unreal-build-[0-9]+-[0-9]+)$') {
        throw 'Existing ordinary CI pointer is unavailable/malformed; preserve all caches.'
    }
    $cacheRoot = Join-Path $workspace $pointer.value.worktree
    Assert-L07PlainPath $cacheRoot
    $cacheHeadOutput = @(& git -C $cacheRoot rev-parse HEAD)
    if ($LASTEXITCODE -ne 0 -or $cacheHeadOutput.Count -ne 1 -or $cacheHeadOutput[0] -cnotmatch '^[0-9a-f]{40}$') { throw 'Cache HEAD is unavailable.' }
    $cacheHead = $cacheHeadOutput[0]
    Assert-L07Source $cacheRoot $cacheHead
    $state = Read-L07Json (Join-Path $cacheRoot 'Saved/BuildCache/UnrealCi/state.json') 64KB
    $receipt.cache_provenance = @{ root = $cacheRoot; actual_head = $cacheHead; original_state = $state.value
        pointer_identity = $pointer.identity; state_identity = $state.identity }
    Protect-L07Identity $pointer.identity 'cache-pointer' 64KB
    Protect-L07Identity $state.identity 'cache-state' 64KB
    # Only read helpers: select() may write active.json, Resolve writes cache_resolution.json.
    $verifyCode = 'import json,sys; from pathlib import Path; from scripts.ci.unreal_ci_workspace import safe_path,verified; p=Path(sys.argv[1]); print(json.dumps(verified(safe_path(p.parent,p.name))))'
    [void](Invoke-L07Helper $verifyCode $cacheRoot 'verify-existing-cache')
    Assert-L07Identity $state.identity 64KB
    Assert-L07CacheProvenance $state.value $fingerprints $environment
    $cacheFingerprints = Get-L07Fingerprints $cacheRoot 'cache-fingerprints'
    if ($cacheFingerprints.compile -cne $fingerprints.compile -or $cacheFingerprints.proof -cne $fingerprints.proof) {
        throw 'Cache source differs from its state or current compile/proof inputs.'
    }
    $s = $state.value
    $summary = Read-L07Json (Join-Path $cacheRoot ('Saved/BuildCache/UnrealCi/proof-summary-' + $s.ProofSummarySha256 + '.json')) 2MB
    if ($summary.identity.sha256 -cne $s.ProofSummarySha256 -or $summary.identity.size_bytes -ne $s.ProofSummarySizeBytes) {
        throw 'Original normal Automation proof bytes differ from cache state.'
    }
    Protect-L07Identity $summary.identity 'cache-original-proof' 2MB
    $receipt.proof_files.original_ci_summary = Copy-L07Exclusive $summary.identity (Join-Path $EvidenceRoot 'original-ci-proof-summary.json') 2MB
    $moduleRows = @(Get-L07ModuleClosure $cacheRoot 'Binaries/Win64/UnrealEditor.modules' @{
        YetAnotherCyclingSim = 'UnrealEditor-YetAnotherCyclingSim.dll'; YetAnotherCyclingSimEditor = 'UnrealEditor-YetAnotherCyclingSimEditor.dll'
    } $engineManifest.value.BuildId)
    $moduleRows += @(Get-L07ModuleClosure $cacheRoot 'Plugins/RoadForge/Binaries/Win64/UnrealEditor.modules' @{
        RoadForge = 'UnrealEditor-RoadForge.dll'
    } $engineManifest.value.BuildId)
    $assets = @(Get-L07AssetInventory $SourceRoot $AssetRoots $AssetByteLimit $AssetFileLimit)
    $receipt.asset_inventory = $assets
    foreach ($required in @($MapRelative,
        'Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset',
        'Content/Generated/YACS/Lesson07_Unified/Materials/M_Landscape_YACS.uasset',
        'Content/Generated/YACS/Lesson07_Unified/Textures/T_PE_Terrain_IDMap.uasset',
        'Content/Generated/YACS/Lesson07_Unified/Textures/T_PE_Terrain_Color.uasset',
        'Content/Generated/YACS/Lesson07_Unified/Materials/TA_Colour_Unified.uasset',
        'Content/Generated/YACS/Lesson07_Unified/Materials/TA_Normal_Unified.uasset',
        'Content/Generated/YACS/Lesson07_Unified/Materials/TA_Masks_Unified.uasset')) {
        if ($required -cnotin @($assets.relative)) { throw ('Known L07 package is absent: ' + $required) }
    }
    foreach ($relative in $MaterialPins.Keys) {
        $identity = Get-L07Identity (Join-Path $SourceRoot $relative) 3GB
        Assert-L07Pin $identity $MaterialPins[$relative]
        Protect-L07Identity $identity 'pinned-current-material'
    }
    $metadataNames = @(& git -C $RepoRoot ls-files -- YetAnotherCyclingSim.uproject Config Plugins/RoadForge)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot enumerate committed project/config inputs.' }
    $metadata = @($metadataNames | Where-Object { $_ -cmatch '^(YetAnotherCyclingSim\.uproject|Config/.+\.ini|Plugins/RoadForge/RoadForge\.uplugin|Plugins/RoadForge/Config/.+\.ini)$' })
    if ('YetAnotherCyclingSim.uproject' -cnotin $metadata -or 'Plugins/RoadForge/RoadForge.uplugin' -cnotin $metadata -or $metadata.Count -gt 128) {
        throw 'Bounded committed project/RoadForge metadata is incomplete.'
    }
    $metadataRows = @($metadata | ForEach-Object {
        # Empty committed .ini files are valid configuration, not missing inputs.
        $allowEmptyConfig = $_ -cmatch '^(Config/.+\.ini|Plugins/RoadForge/Config/.+\.ini)$'
        @{ relative = $_; source_identity = Get-L07Identity (Join-Path $RepoRoot $_) 8MB -AllowEmpty:$allowEmptyConfig }
    })
    # Identities are OrderedDictionary values; read their keys explicitly.
    $plannedBytes = [long](($assets | Measure-Object -Property { $_.size_bytes } -Sum).Sum)
    $plannedBytes += [long](($moduleRows.source_identity | Measure-Object -Property { $_.size_bytes } -Sum).Sum)
    $plannedBytes += [long](($metadataRows.source_identity | Measure-Object -Property { $_.size_bytes } -Sum).Sum)
    $receipt.planned_copy_bytes = $plannedBytes
    [void](Assert-L07Reserve $plannedBytes)
    Assert-L07IdleHost
    $CandidateRoot = Join-Path 'D:\yacs\work' ('lesson07-readback-' + $RunToken)
    Assert-L07PlainPath $CandidateRoot
    if (Test-Path -LiteralPath $CandidateRoot) { throw 'Candidate already exists; never reuse or overwrite it.' }
    [void][IO.Directory]::CreateDirectory($CandidateRoot)
    $receipt.candidate_root = $CandidateRoot
    $remainingBytes = $plannedBytes
    foreach ($row in (@($metadataRows) + @($moduleRows))) {
        [void](Assert-L07Reserve $remainingBytes)
        $allowEmptyConfig = $row.relative -cmatch '^(Config/.+\.ini|Plugins/RoadForge/Config/.+\.ini)$'
        $copied = Copy-L07Exclusive $row.source_identity (Join-Path $CandidateRoot $row.relative) -AllowEmpty:$allowEmptyConfig
        $remainingBytes -= [long]$copied.size_bytes
        Protect-L07Identity $row.source_identity 'original-config-or-binary' -AllowEmpty:$allowEmptyConfig
        Protect-L07Identity $copied 'copied-config-or-binary' -AllowEmpty:$allowEmptyConfig
        if ($row.relative.EndsWith('.dll') -or $row.relative.EndsWith('.modules')) {
            $receipt.binary_provenance += @{ relative = $row.relative; original_identity = $row.source_identity; copied_identity = $copied
                original_compile_head = $s.CompileHead; original_proof_head = $s.ProofHead; engine_build_id = $engineManifest.value.BuildId }
        }
    }
    foreach ($asset in $assets) {
        [void](Assert-L07Reserve $remainingBytes)
        $copy = Copy-L07InventoriedAsset $asset $CandidateRoot
        if ($MaterialPins.ContainsKey($asset.relative)) {
            Assert-L07Pin $copy.copied_identity $MaterialPins[$asset.relative]
        }
        $remainingBytes -= [long]$copy.copied_identity.size_bytes
        Protect-L07Identity $copy.source_identity 'original-asset'
        Protect-L07Identity $copy.copied_identity 'copied-asset'
        $receipt.staged_assets += $copy
    }
    $candidateMap = Join-Path $CandidateRoot $MapRelative
    $receipt.candidate_map_before = Get-L07Identity $candidateMap $FileLimit
    if ($receipt.candidate_map_before.sha256 -cne $MapPin.sha256 -or $receipt.candidate_map_before.size_bytes -ne $MapPin.size_bytes) { throw 'Copied map differs from its pin.' }
    $reportPath = Join-Path $EvidenceRoot 'l07-native-geometry.json'
    $preparationPath = Join-Path $EvidenceRoot 'staging.json'
    $preparation = [ordered]@{
        schema_version = 1; status = 'L07_COPIED_BYTES_NATIVE_READ_PENDING'; source_head = $ExpectedHead
        candidate_root = $CandidateRoot; level = $LevelPackage; report_path = $reportPath
        reader_identity = $receipt.proof_files.reader
        map = @{ relative = $MapRelative; source_identity = $receipt.source_map_before; original_identity = $OriginalMapPin }
        assets = $receipt.staged_assets; known_asset_roots = $AssetRoots; binary_provenance = $receipt.binary_provenance
        geometry_accepted = $false; dependency_closure_complete = $false; houdini_engine_staged = $false
    }
    Write-L07JsonExclusive $preparationPath $preparation
    $preparationIdentity = Get-L07Identity $preparationPath 8MB
    Protect-L07Identity $preparationIdentity 'owned-staging-receipt' 8MB
    Assert-L07Source $RepoRoot $ExpectedHead
    Assert-L07Source $cacheRoot $cacheHead
    Assert-L07Identity $pointer.identity 64KB
    Assert-L07Identity $state.identity 64KB
    Assert-L07IdleHost
    $receipt.free_before_editor_bytes = Assert-L07Reserve
    $log = Join-Path $EvidenceRoot 'owned-editor.log'
    $project = Join-Path $CandidateRoot 'YetAnotherCyclingSim.uproject'
    $editorArguments = @(('"' + $project + '"'), '/Engine/Maps/Entry',
        '-DisablePlugins=ModelContextProtocol,Wingman,AndroidFileServer,HoudiniEngine,PCGExtendedToolkit,YacsPcgWitness',
        # UE 5.8 editor session analytics reads shader-compiler statistics at startup.
        # NullRHI is sufficient for this read; NoShaderCompile removes that manager.
        '-NullRHI', '-Unattended', '-NoSplash', '-NoSound', '-NoLiveCoding', '-ScriptErrorsAreFatal', '-NoPause', '-NoP4',
        '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
        ('-ExecutePythonScript="' + $reader + '"'), ('-AbsLog="' + $log + '"'))
    $receipt.editor_arguments = $editorArguments
    $receipt.status = 'OWNED_EDITOR_READING'
    $ownedEditor = Start-Process -FilePath $engine.UnrealEditorCmdPath -ArgumentList $editorArguments -WorkingDirectory $CandidateRoot `
        -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $EvidenceRoot 'owned-editor-stdout.log') `
        -RedirectStandardError (Join-Path $EvidenceRoot 'owned-editor-stderr.log') -Environment @{
            YACS_L07_EXPECTED_HEAD = $ExpectedHead; YACS_L07_PREPARATION_FILE = $preparationPath
            YACS_L07_PREPARATION_SHA256 = $preparationIdentity.sha256; YACS_LESSON07_READBACK_PATH = $reportPath
            YACS_WORKSPACE_CONFIG = $WorkspaceConfig; PYTHONDONTWRITEBYTECODE = '1'; PYTHONPATH = ''; PYTHONHOME = ''; YACS_OWNER_HANDOFF = ''
        }
    $receipt.owned_editor_pid = $ownedEditor.Id
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $heartbeat = 30
    while (-not $ownedEditor.WaitForExit(200)) {
        if ($timer.Elapsed.TotalSeconds -ge 660) { throw 'Owned L07 Editor exceeded its 660 second deadline.' }
        if ($timer.Elapsed.TotalSeconds -ge $heartbeat) {
            Write-Host ('L07 readback heartbeat: ownedPID={0}, elapsed={1:N0}s.' -f $ownedEditor.Id, $timer.Elapsed.TotalSeconds)
            $heartbeat += 30
        }
    }
    $ownedEditor.WaitForExit()
    $receipt.owned_editor_exit_code = $ownedEditor.ExitCode
    $receipt.native_log_findings = Get-L07LogFindings $log
    if ($ownedEditor.ExitCode -ne 0) {
        throw ('Owned L07 Editor failed with exit code {0}; see {1}.' -f $ownedEditor.ExitCode, $log)
    }
    $native = Read-L07Json $reportPath 8MB
    $receipt.proof_files.native_readback = $native.identity
    if ($receipt.native_log_findings.total -gt 0) { throw 'Native missing-package/class/module or error diagnostics block completeness.' }
    Assert-L07NativeReport $native.value $ExpectedHead $CandidateRoot $preparationIdentity.sha256
    Assert-L07Source $RepoRoot $ExpectedHead
    Assert-L07Source $cacheRoot $cacheHead
    $finalCurrent = Get-L07Fingerprints $RepoRoot 'final-current-fingerprints'
    $finalCache = Get-L07Fingerprints $cacheRoot 'final-cache-fingerprints'
    if ($finalCurrent.compile -cne $fingerprints.compile -or $finalCurrent.proof -cne $fingerprints.proof -or
        $finalCache.compile -cne $fingerprints.compile -or $finalCache.proof -cne $fingerprints.proof) {
        throw 'Current/cache compile or proof inputs changed during the read.'
    }
    $finalSourceAssets = @(Get-L07AssetInventory $SourceRoot $AssetRoots $AssetByteLimit $AssetFileLimit)
    $finalCandidateAssets = @(Get-L07AssetInventory $CandidateRoot @('Content') $AssetByteLimit $AssetFileLimit)
    $initialNames = (@($assets.relative) | Sort-Object) -join "`n"
    if (((@($finalSourceAssets.relative) | Sort-Object) -join "`n") -cne $initialNames -or
        ((@($finalCandidateAssets.relative) | Sort-Object) -join "`n") -cne $initialNames) {
        throw 'Source/candidate Unreal asset inventory changed during the read.'
    }
    $receipt.free_after_editor_bytes = Assert-L07Reserve
    $receipt.structural_readback_complete = $true
    $receipt.status = 'STRUCTURE_READBACK_COMPLETE_GEOMETRY_PENDING'
} catch {
    $receipt.status = 'INCOMPLETE'
    $receipt.structural_readback_complete = $false
    $receipt.error = $_.Exception.Message
} finally {
    foreach ($process in @($ownedEditor, $ownedHelper)) {
        if ($null -eq $process) { continue }
        try {
            if (-not $process.HasExited) {
                $process.Kill()
                [void]$process.WaitForExit(10000)
                if ($process -eq $ownedEditor) { $receipt.owned_editor_stopped_on_failure = $true }
            }
            if ($process -eq $ownedEditor -and $process.HasExited) { $receipt.owned_editor_exit_code = $process.ExitCode }
        } catch { $receipt.secondary_errors += ('Owned process cleanup: ' + $_.Exception.Message) }
        finally { $process.Dispose() }
    }
    # Conservation measurements run on failure and timeout, not only on success.
    foreach ($entry in @(@('source', $sourceMap), @('candidate', $candidateMap))) {
        if (-not $entry[1]) { continue }
        try {
            $after = Get-L07Identity $entry[1] $FileLimit
            $before = $receipt[$entry[0] + '_map_before']
            $receipt[$entry[0] + '_map_after'] = $after
            $receipt[$entry[0] + '_map_unchanged'] = $null -ne $before -and $after.sha256 -ceq $before.sha256 -and $after.size_bytes -eq $before.size_bytes
            if (-not $receipt[$entry[0] + '_map_unchanged']) { throw ($entry[0] + ' map changed or initial hash unavailable.') }
        } catch { $receipt.secondary_errors += ($entry[0] + ' final map identity: ' + $_.Exception.Message) }
    }
    $unchanged = $protectedInputs.Count -gt 0
    foreach ($entry in $protectedInputs) {
        try {
            $after = Get-L07Identity $entry.identity.path $entry.limit -AllowEmpty:$entry.allow_empty
            $equal = $after.sha256 -ceq $entry.identity.sha256 -and $after.size_bytes -eq $entry.identity.size_bytes
            $receipt.protected_inputs_after += @{ role = $entry.role; actual = $after; unchanged = $equal }
            if (-not $equal) { throw ('Protected input changed: ' + $entry.identity.path) }
        } catch { $unchanged = $false; $receipt.secondary_errors += $_.Exception.Message }
    }
    $receipt.protected_inputs_unchanged = $unchanged
    if ($receipt.secondary_errors.Count -gt 0 -or $receipt.source_map_unchanged -ne $true -or
        $receipt.candidate_map_unchanged -ne $true -or -not $unchanged) {
        $receipt.status = 'INCOMPLETE'
        $receipt.structural_readback_complete = $false
    }
    $receipt.ended_at_utc = [DateTime]::UtcNow.ToString('o')
    try {
        if ($EvidenceOwned -and $EvidenceRoot -and (Test-Path -LiteralPath $EvidenceRoot -PathType Container)) {
            Write-L07JsonExclusive (Join-Path $EvidenceRoot 'host-receipt.json') $receipt
        }
    } finally {
        foreach ($name in $originalEnvironment.Keys) { [Environment]::SetEnvironmentVariable($name, $originalEnvironment[$name], 'Process') }
    }
}
if ($receipt.status -cne 'STRUCTURE_READBACK_COMPLETE_GEOMETRY_PENDING') { throw ('L07 readback incomplete: ' + $receipt.error) }
Write-Host 'L07 structural readback complete; geometry, height seams, visibility, material rendering and repair reopen remain unproved.'
