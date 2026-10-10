#requires -Version 7.4
<# Save only a new #364 road/shoulder material map and verify it in a fresh Editor. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string] $ExpectedHead,
    [Parameter(Mandatory)][ValidatePattern('^[1-9][0-9]{0,19}-[1-9][0-9]{0,5}$')][string] $RunToken,
    [string] $WorkspaceConfig = 'D:\yacs\workspace.json',
    [string] $RepoRoot = (Join-Path $PSScriptRoot '../..')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Saved road asphalt requires the trusted Windows host.' }
$PROFILE_DIAGNOSTIC = 'road-network-profile-diagnostic.json'
$root = $null
$evidence = $null
$editor = $null
$receipt = [ordered]@{
    schema_version = 1; issue = 364; exact_sha = $ExpectedHead
    run_token = $RunToken; status = 'PENDING'
    native_baseline_authenticated = $false
    transient_canary_authenticated = $false
    saved_derived_consumer = $false; fresh_reload_verified = $false
    shoulder_network_fresh_reload_verified = $false
    shoulder_support_count = 0; shoulder_material_target_count = 0
    shoulder_selected_triangle_count = 0
    road_profile_diagnostic_sha256 = $null
    original_map_saved = $false; original_landscape_mutated = $false
    gpu_shader_verified = $false; owner_visual_status = 'PENDING_FINAL_M3'
    performance_status = 'DEFERRED_AFTER_M3'; performance_pass = $false
    editor_processes = @(); proof_files = [ordered]@{}
    error = $null; secondary_errors = @()
}

function Assert-PlainPath {
    param([string] $Path)
    if (-not [IO.Path]::IsPathFullyQualified($Path) -or $Path -match '[\x00\r\n"]') {
        throw 'Saved road material paths must be absolute and plain.'
    }
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        try { $attrs = [IO.File]::GetAttributes($cursor) }
        catch [IO.FileNotFoundException] { $attrs = $null }
        catch [IO.DirectoryNotFoundException] { $attrs = $null }
        if ($null -ne $attrs -and ($attrs -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Saved road materials refuse symlinks and junctions.'
        }
        $next = [IO.Path]::GetDirectoryName($cursor)
        if ($next -eq $cursor) { break }
        $cursor = $next
    }
}
function Get-Identity {
    param([string] $Path, [long] $Limit = 64MB, [switch] $AllowEmpty)
    Assert-PlainPath $Path
    $before = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ($before.PSIsContainer -or $before.Length -gt $Limit -or
        ($before.Length -eq 0 -and -not $AllowEmpty)) {
        throw 'Saved road asphalt input is not a bounded regular file.'
    }
    $hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    $after = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ($after.Length -ne $before.Length -or
        $after.LastWriteTimeUtc.Ticks -ne $before.LastWriteTimeUtc.Ticks) {
        throw 'Saved road material input changed while hashing.'
    }
    return [ordered]@{ path = [IO.Path]::GetFullPath($Path)
        sha256 = $hash; size_bytes = $before.Length }
}
function Assert-Identity {
    param($Expected, [long] $Limit = 64MB)
    $actual = Get-Identity $Expected.path $Limit
    if ($actual.sha256 -cne $Expected.sha256 -or
        $actual.size_bytes -ne $Expected.size_bytes) {
        throw 'Authenticated input changed during saved asphalt authoring.'
    }
}
function Get-ClosedLog {
    param([string] $Path)
    for ($attempt = 1; $attempt -le 40; $attempt++) {
        try { return Get-Identity $Path 64MB -AllowEmpty }
        catch {
            $inner = $_.Exception
            $locked = $false
            while ($inner) {
                if ($inner -is [IO.IOException] -and
                    $inner.HResult -in @(-2147024864, -2147024863)) {
                    $locked = $true
                    break
                }
                $inner = $inner.InnerException
            }
            if (-not $locked -or $attempt -ge 40) { throw }
            Start-Sleep -Milliseconds 250
        }
    }
}
function Read-Json {
    param([string] $Path, [long] $Limit = 2MB)
    $id = Get-Identity $Path $Limit
    $data = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -AsHashtable -Depth 40
    Assert-Identity $id $Limit
    if ($data -isnot [Collections.IDictionary]) {
        throw 'Saved road material JSON must be an object.'
    }
    return [ordered]@{ identity = $id; value = $data }
}
function Write-ExclusiveReceipt {
    param([string] $Path, $Data)
    Assert-PlainPath $Path
    $raw = [Text.Encoding]::UTF8.GetBytes(($Data | ConvertTo-Json -Depth 40))
    if ($raw.Length -gt 2MB) { throw 'Saved road asphalt host receipt too large.' }
    $file = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $file.Write($raw, 0, $raw.Length) } finally { $file.Dispose() }
}
function Resolve-ProfileRetainedRoot {
    param($Workspace, [string] $ConfigPath, [string] $ExactHead,
          [string] $Token, [string] $RecordedRoot)
    if ($Workspace.schema_version -ne 1 -or $Workspace.work -isnot [string] -or
        [string]::IsNullOrWhiteSpace($Workspace.work) -or
        [IO.Path]::IsPathRooted($Workspace.work) -or
        $Workspace.work -match '[:\x00\r\n"]' -or
        ($Workspace.work -split '[\\/]') -contains '..') {
        throw 'Profile retained work root is not a bounded canonical workspace path.'
    }
    Assert-PlainPath $ConfigPath
    $configRoot = Split-Path -Parent ([IO.Path]::GetFullPath($ConfigPath))
    $work = [IO.Path]::GetFullPath((Join-Path $configRoot $Workspace.work))
    if (-not $work.StartsWith(($configRoot.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar),
                             [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Profile retained work root escaped the canonical workspace.'
    }
    $expected = [IO.Path]::GetFullPath((Join-Path $work ('road-materials/saved-consumers/' + $ExactHead + '/' + $Token)))
    Assert-PlainPath $expected
    Assert-PlainPath $RecordedRoot
    if (-not [string]::Equals([IO.Path]::GetFullPath($RecordedRoot), $expected,
                             [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Profile retained root differs from the exact prepared head and token.'
    }
    return $expected
}
function Get-ProfileCopies {
    param($Pin, [string] $ProofRoot, [string] $RetainedRoot)
    # This separate source/native diagnostic is only hashed, never parsed into
    # or embedded in the 4 MiB material manifest / 2 MiB process receipts.
    if ($Pin -isnot [Collections.IDictionary] -or $Pin.Count -ne 3 -or
        @($Pin.Keys) -cnotcontains 'file' -or @($Pin.Keys) -cnotcontains 'sha256' -or
        @($Pin.Keys) -cnotcontains 'size_bytes' -or
        $Pin.file -isnot [string] -or $Pin.file -cne $PROFILE_DIAGNOSTIC -or
        $Pin.sha256 -isnot [string] -or $Pin.sha256 -cnotmatch '^[0-9a-f]{64}$' -or
        ($Pin.size_bytes -isnot [long] -and $Pin.size_bytes -isnot [int]) -or
        $Pin.size_bytes -le 0 -or $Pin.size_bytes -gt 8MB) {
        throw 'Profile diagnostic pin is not the exact bounded sidecar identity.'
    }
    $proofCopy = Get-Identity (Join-Path $ProofRoot $PROFILE_DIAGNOSTIC) 8MB
    $retainedCopy = Get-Identity (Join-Path $RetainedRoot $PROFILE_DIAGNOSTIC) 8MB
    if ([string]::Equals($proofCopy.path, $retainedCopy.path, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Profile diagnostic requires distinct proof and retained copies.'
    }
    foreach ($copy in @($proofCopy, $retainedCopy)) {
        if ($copy.sha256 -cne $Pin.sha256 -or $copy.size_bytes -ne $Pin.size_bytes) {
            throw 'Profile diagnostic copy differs from the authenticated material manifest.'
        }
    }
    return [ordered]@{ proof = $proofCopy; retained = $retainedCopy }
}
function Require-IdleHost {
    $state = & (Join-Path $root 'scripts/runner/Get-YacsUnrealHostState.ps1')
    if ($state.status -cne 'IDLE') {
        throw 'Saved asphalt authoring must yield to a different active Unreal Editor.'
    }
}
function Require-ExactSource {
    param([string] $Relative)
    $committed = @(& git -C $root rev-parse ($ExpectedHead + ':' + $Relative))
    if ($LASTEXITCODE -ne 0 -or $committed.Count -ne 1) {
        throw 'Missing committed road save source: ' + $Relative
    }
    $working = @(& git -C $root hash-object --no-filters -- (Join-Path $root $Relative))
    if ($LASTEXITCODE -ne 0 -or $working.Count -ne 1 -or
        $working[0] -cne $committed[0]) {
        throw 'Saved asphalt executable differs from exact committed Git bytes: ' + $Relative
    }
}
function Assert-NetworkManifest {
    param($Manifest, [string] $ExactHead)
    if ($Manifest -isnot [Collections.IDictionary] -or
        $Manifest.schema_version -ne 1 -or $Manifest.issue -ne 364 -or
        $Manifest.status -cne 'SAVED_ROAD_ASPHALT_CONSUMER_PREPARED' -or
        $Manifest.exact_sha -cne $ExactHead -or
        $Manifest.material_changes -cne 'road_slot_zero_and_network_outer_shoulder_ids') {
        throw 'Saved material manifest is not the exact full-network schema.'
    }
    $flags = @{ map_saved = $true; landscape_1024_unchanged = $true
        canonical_saved = $false; source_scene_mutated = $false
        road_slot_zero_only = $false; support_186_unchanged = $false
        fresh_reload_verified = $false; performance_pass = $false }
    foreach ($name in $flags.Keys) {
        if ($Manifest[$name] -isnot [bool] -or $Manifest[$name] -ne $flags[$name]) {
            throw ('Saved network manifest changed protected flag: ' + $name)
        }
    }
    $network = $Manifest.shoulder_network
    if ($network -isnot [Collections.IDictionary] -or
        $network.schema_version -ne 2 -or $network.status -cne 'SHOULDER_NETWORK_PREPARED' -or
        $network.support_count -ne 186 -or $network.material_target_count -ne 185 -or
        $network.excluded_parapet_count -ne 1 -or
        $network.owners -isnot [Collections.IList] -or $network.owners.Count -ne 186) {
        throw 'Saved source-owned support coverage is incomplete.'
    }
    $flags = @{ rollback_verified = $true; source_vertices_topology_normals_uv_preserved = $true
        original_wall_material_preserved = $true; excluded_parapet_unchanged = $true
        whole_area_admitted = $false; performance_pass = $false }
    foreach ($name in $flags.Keys) {
        if ($network[$name] -isnot [bool] -or $network[$name] -ne $flags[$name]) {
            throw ('Saved network proof changed protected flag: ' + $name)
        }
    }
    $selected = $network.selected_triangle_count
    if (($selected -isnot [long] -and $selected -isnot [int]) -or
        $selected -le 0 -or $selected -gt $network.total_triangle_count) {
        throw 'Saved network selected-triangle inventory is invalid.'
    }
    return $selected
}
function Assert-FreshNetworkReceipt {
    param($Fresh, [string] $ExactHead, [string] $ManifestSha,
          [long] $SelectedTriangles, [string] $ProfileSha)
    if ($Fresh.status -cne 'ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_PASS' -or
        $Fresh.exact_sha -cne $ExactHead -or
        $Fresh.saved_manifest_sha256 -cne $ManifestSha -or
        $Fresh.evidence_manifest_sha256 -cne $ManifestSha -or
        $Fresh.road_profile_diagnostic_sha256 -cne $ProfileSha -or
        $Fresh.shoulder_support_count -ne 186 -or
        $Fresh.shoulder_material_target_count -ne 185 -or
        $Fresh.shoulder_selected_triangle_count -ne $SelectedTriangles -or
        $Fresh.owner_visual_status -cne 'PENDING_FINAL_M3') {
        throw 'Fresh reload differs from the exact saved network material inventory.'
    }
    $flags = @{ fresh_process = $true; shoulder_network_fresh_reload_verified = $true
        shoulder_positions_indices_normals_uv_unchanged = $true
        shoulder_wall_materials_unchanged = $true; road_full_buffers_unchanged = $true
        dry_asphalt_response_verified = $true; new_saved_asset_bytes_unchanged = $true
        road_material_reapplied = $false
        shoulder_material_reapplied = $false; source_scene_mutated = $false
        performance_pass = $false }
    foreach ($name in $flags.Keys) {
        if ($Fresh[$name] -isnot [bool] -or $Fresh[$name] -ne $flags[$name]) {
            throw ('Fresh reload changed protected network flag: ' + $name)
        }
    }
}
function Invoke-OwnedEditor {
    param([string] $Action)
    Require-IdleHost
    $script = Join-Path $root 'scripts/ue/road_asphalt_saved_consumer.py'
    $arguments = @(('"' + (Join-Path $root 'YetAnotherCyclingSim.uproject') + '"'),
        '/Engine/Maps/Entry', '-DisablePlugins=ModelContextProtocol,Wingman,AndroidFileServer',
        '-Unattended', '-NoPause', '-NoSplash', '-NoSound', '-NoLiveCoding', '-NoP4',
        '-NullRHI', '-ScriptErrorsAreFatal',
        '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
        ('-ExecutePythonScript="' + $script + '"'),
        ('-AbsLog="' + (Join-Path $evidence ('saved-road-' + $Action + '-editor.log')) + '"'))
    $streamOut = Join-Path $evidence ('saved-road-' + $Action + '-stdout.log')
    $streamErr = Join-Path $evidence ('saved-road-' + $Action + '-stderr.log')
    foreach ($path in @($streamOut, $streamErr)) {
        Assert-PlainPath $path
        if (Test-Path -LiteralPath $path) {
            throw 'An owned saved road material log already exists.'
        }
    }
    $script:editor = Start-Process -FilePath $engine.path -ArgumentList $arguments `
        -WorkingDirectory $root -PassThru -NoNewWindow `
        -RedirectStandardOutput $streamOut -RedirectStandardError $streamErr `
        -Environment @{
            YACS_ROAD_SAVED_ACTION = $Action
            YACS_ROAD_SAVED_RUN_TOKEN = $RunToken
            YACS_ROAD_MATERIAL_EXPECTED_HEAD = $ExpectedHead
            YACS_ROAD_MATERIAL_PREPARATION_SHA256 = [string] $baseline.value.proof_files.session_preparation.sha256
            YACS_WORKSPACE_CONFIG = $WorkspaceConfig
            YACS_OWNER_HANDOFF = ''; PYTHONPATH = ''; PYTHONHOME = ''
            YACS_MCP_BOB_PROJECT_ROOT = ''; YACS_MCP_BOB_EXPECTED_HEAD = ''
        }
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while (-not $script:editor.WaitForExit(200)) {
        if ($timer.Elapsed.TotalSeconds -ge 420) {
            throw ('Owned saved material Editor exceeded 420 seconds: ' + $Action)
        }
    }
    $script:editor.WaitForExit()
    $exitCode = $script:editor.ExitCode
    $editorPid = $script:editor.Id
    $script:editor.Dispose()
    $script:editor = $null
    $processRow = [ordered]@{ action = $Action; owned_pid = $editorPid
        exit_code = $exitCode; elapsed_seconds = $timer.Elapsed.TotalSeconds
        deadline_seconds = 420 }
    $receipt.editor_processes += $processRow
    foreach ($name in @(
        ('saved-road-' + $Action + '-editor.log'),
        ('saved-road-' + $Action + '-stdout.log'),
        ('saved-road-' + $Action + '-stderr.log')
    )) {
        $path = Join-Path $evidence $name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw 'Owned save/reload Editor log missing: ' + $name
        }
        $receipt.proof_files[$name] = Get-ClosedLog $path
    }
    if ($exitCode -ne 0) {
        throw ('Native saved asphalt ' + $Action + ' process failed; original logs retained.')
    }
}

try {
    $root = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\', '/')
    Assert-PlainPath $root
    Assert-PlainPath $WorkspaceConfig
    if (-not $env:GITHUB_WORKSPACE -or
        $RunToken -cne ($env:GITHUB_RUN_ID + '-' + $env:GITHUB_RUN_ATTEMPT) -or
        -not [string]::Equals(
            $root,
            (Join-Path ([IO.Path]::GetFullPath($env:GITHUB_WORKSPACE).TrimEnd('\', '/')) ('rm-' + $RunToken)),
            [StringComparison]::OrdinalIgnoreCase
        ) -or
        -not [string]::Equals($WorkspaceConfig, 'D:\yacs\workspace.json',
                             [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Native derived save requires the exact approved run checkout and workspace.'
    }
    $current = @(& git -C $root rev-parse HEAD)
    if ($LASTEXITCODE -ne 0 -or $current.Count -ne 1 -or $current[0] -cne $ExpectedHead) {
        throw 'Derived road consumer HEAD is not the exact approved revision.'
    }
    & git -C $root diff --quiet HEAD -- . ':(exclude)Content/**'
    if ($LASTEXITCODE -ne 0) { throw 'Native save code/config differs from Git HEAD.' }
    foreach ($relative in @(
        'scripts/ue/Invoke-YacsRoadSavedConsumer.ps1',
        'scripts/ue/road_asphalt_saved_consumer.py',
        'scripts/ue/road_asphalt_source_preflight.py',
        'scripts/ue/road_asphalt_slot_canary.py',
        'scripts/ue/import_material_forge_variant.py',
        'scripts/ue/road_shoulder_window.py',
        'scripts/ue/road_shoulder_sources.py',
        'scripts/ue/road_shoulder_network.py',
        'scripts/ue/road_material_views.py',
        'scripts/ue/road_shoulder_material.py',
        'Source/YetAnotherCyclingSimEditor/Public/Diagnostics/YacsRoadMaterialInspectionLibrary.h',
        'Source/YetAnotherCyclingSimEditor/Private/Diagnostics/YacsRoadMaterialInspectionLibrary.cpp',
        'scripts/ue/capture_sa_calobra_shoulder_contact.py',
        'scripts/proof/sa_calobra_shoulder_contact.py',
        'scripts/proof/sa_calobra_tpp_survey.py',
        'worldgen/materials/sa_calobra_texture_library_v2_20261005.json',
        'worldgen/terrain/benchmarks/sa_calobra/world_data/frozen_road_recipe_2026-10-04.json'
    )) { Require-ExactSource $relative }
    $evidence = Join-Path $root ('Saved/RuntimeProof/RoadMaterialBaseline/' + $RunToken)
    Assert-PlainPath $evidence
    $baseline = Read-Json (Join-Path $evidence 'host-receipt.json')
    $asphalt = Read-Json (Join-Path $evidence 'asphalt-host-receipt.json')
    $nativeRead = Read-Json (Join-Path $evidence 'road-material-baseline.json')
    $nativeAsphalt = Read-Json (Join-Path $evidence 'road-asphalt-canary.json')
    if ($baseline.value.status -cne 'ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE' -or
        $baseline.value.reader_pass -isnot [bool] -or -not $baseline.value.reader_pass -or
        $baseline.value.exact_sha -cne $ExpectedHead -or
        $baseline.value.proof_files.native_baseline.sha256 -cne $nativeRead.identity.sha256 -or
        $asphalt.value.status -cne 'ROAD_ASPHALT_TRANSIENT_HOST_PASS' -or
        $asphalt.value.native_material_bind_and_rollback_verified -isnot [bool] -or
        -not $asphalt.value.native_material_bind_and_rollback_verified -or
        $asphalt.value.exact_sha -cne $ExpectedHead -or
        $asphalt.value.native_canary.sha256 -cne $nativeAsphalt.identity.sha256 -or
        $nativeAsphalt.value.status -cne 'ROAD_ASPHALT_TRANSIENT_CANARY_ROLLED_BACK' -or
        $nativeAsphalt.value.result.consumer_snapshot_restored -isnot [bool] -or
        -not $nativeAsphalt.value.result.consumer_snapshot_restored) {
        throw 'Missing two independent exact-SHA road baseline and rolled-back canary proofs.'
    }
    $receipt.native_baseline_authenticated = $true
    $receipt.transient_canary_authenticated = $true
    $workspace = Read-Json $WorkspaceConfig
    if ($workspace.identity.sha256 -cne $baseline.value.proof_files.workspace_config.sha256 -or
        $workspace.identity.size_bytes -ne $baseline.value.proof_files.workspace_config.size_bytes) {
        throw 'Profile workspace configuration differs from the authenticated native baseline.'
    }
    $receipt.proof_files.workspace_config = $workspace.identity
    $engine = Get-Identity ([string] $baseline.value.proof_files.editor_executable.path) 1GB
    if ($engine.sha256 -cne $baseline.value.proof_files.editor_executable.sha256) {
        throw 'Unreal Editor executable differs from the original approved native baseline.'
    }
    foreach ($row in $baseline.value.binary_provenance) {
        Assert-Identity $row.copied_identity 512MB
        Assert-Identity $row.original_identity 512MB
    }
    Require-IdleHost
    $receipt.status = 'SAVED_CONSUMER_PREPARING'
    Invoke-OwnedEditor 'prepare'
    $saved = Read-Json (Join-Path $evidence 'road-asphalt-saved-prepared.json')
    if ($saved.value.status -cne 'ROAD_ASPHALT_SAVED_PREPARED' -or
        $saved.value.exact_sha -cne $ExpectedHead -or
        $saved.value.material_saved -isnot [bool] -or -not $saved.value.material_saved -or
        $saved.value.new_world_only -isnot [bool] -or -not $saved.value.new_world_only -or
        $saved.value.fresh_reload_verified -isnot [bool] -or
        $saved.value.fresh_reload_verified) {
        throw 'Saved road map preparation receipt is not an authentic first-stage candidate.'
    }
    $receipt.proof_files.saved_prepared = $saved.identity
    # A measured full-network upper bound is ~1.99 MB before material/API/assets.
    # Only this manifest grows to 4 MiB; host/prepared/fresh receipts stay at 2 MiB.
    $manifest = Read-Json (Join-Path $evidence 'road-asphalt-saved-manifest.json') 4MB
    if ($saved.value.evidence_manifest.file -cne 'road-asphalt-saved-manifest.json' -or
        $saved.value.evidence_manifest.sha256 -cne $manifest.identity.sha256 -or
        $saved.value.evidence_manifest.size_bytes -ne $manifest.identity.size_bytes -or
        $saved.value.manifest.sha256 -cne $manifest.identity.sha256 -or
        $saved.value.manifest.size_bytes -ne $manifest.identity.size_bytes) {
        throw 'Downloadable material manifest is not pinned to the native retained evidence.'
    }
    $selectedTriangles = Assert-NetworkManifest $manifest.value $ExpectedHead
    $receipt.proof_files.saved_manifest = $manifest.identity
    $retainedRoot = Resolve-ProfileRetainedRoot $workspace.value $WorkspaceConfig `
        $ExpectedHead $RunToken $saved.value.retained_root
    $profileCopies = Get-ProfileCopies $manifest.value.road_profile_diagnostic $evidence $retainedRoot
    $receipt.proof_files.road_profile_diagnostic = $profileCopies.proof
    $receipt.proof_files.retained_road_profile_diagnostic = $profileCopies.retained
    Assert-Identity $baseline.identity 2MB
    Assert-Identity $asphalt.identity 2MB
    Assert-Identity $nativeRead.identity 2MB
    Assert-Identity $nativeAsphalt.identity 2MB
    Require-IdleHost
    $receipt.status = 'SAVED_CONSUMER_FRESH_RELOADING'
    Invoke-OwnedEditor 'reload'
    $fresh = Read-Json (Join-Path $evidence 'road-asphalt-saved-reloaded.json')
    Assert-FreshNetworkReceipt $fresh.value $ExpectedHead $manifest.identity.sha256 `
        $selectedTriangles $profileCopies.proof.sha256
    $receipt.proof_files.fresh_reload = $fresh.identity
    Assert-Identity $saved.identity 2MB
    Assert-Identity $manifest.identity 4MB
    Assert-Identity $profileCopies.proof 8MB
    Assert-Identity $profileCopies.retained 8MB
    Assert-Identity $workspace.identity 2MB
    Assert-Identity $baseline.identity 2MB
    Assert-Identity $asphalt.identity 2MB
    Assert-Identity $engine 1GB
    foreach ($row in $baseline.value.binary_provenance) {
        Assert-Identity $row.copied_identity 512MB
    }
    Require-IdleHost
    $receipt.saved_derived_consumer = $true
    $receipt.fresh_reload_verified = $true
    $receipt.shoulder_network_fresh_reload_verified = $true
    $receipt.shoulder_support_count = 186
    $receipt.shoulder_material_target_count = 185
    $receipt.shoulder_selected_triangle_count = $selectedTriangles
    $receipt.road_profile_diagnostic_sha256 = $profileCopies.proof.sha256
    $receipt.status = 'ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_HOST_PASS'
}
catch {
    $receipt.status = 'FAILED'
    $receipt.error = $_.Exception.Message
    throw
}
finally {
    if ($null -ne $editor) {
        try {
            if (-not $editor.HasExited) {
                $editor.Kill()
                if (-not $editor.WaitForExit(10000)) {
                    throw 'Owned save/reload Editor did not stop within ten seconds.'
                }
            }
            $editor.WaitForExit()
        } catch { $receipt.secondary_errors += $_.Exception.Message }
        finally { $editor.Dispose() }
    }
    if ($receipt.secondary_errors.Count -ne 0) {
        $receipt.status = 'FAILED'
        $receipt.saved_derived_consumer = $false
        $receipt.fresh_reload_verified = $false
        $receipt.shoulder_network_fresh_reload_verified = $false
        $receipt.error = 'Owned saved consumer process teardown failed.'
    }
    if ($null -ne $evidence -and (Test-Path -LiteralPath $evidence -PathType Container)) {
        try { Write-ExclusiveReceipt (Join-Path $evidence 'saved-road-host-receipt.json') $receipt }
        catch {
            if ($null -eq $receipt.error) { throw }
            Write-Warning 'Failed to preserve host receipt after native save/reload failure.'
        }
    }
}
if ($receipt.status -cne 'ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_HOST_PASS' -or
    -not $receipt.saved_derived_consumer -or -not $receipt.fresh_reload_verified -or
    -not $receipt.shoulder_network_fresh_reload_verified) {
    throw 'Durable new-map asphalt save and fresh native reload were not both verified.'
}
Write-Host 'ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_HOST_PASS; owner visual/FPS/GPU rendering remain pending.'
