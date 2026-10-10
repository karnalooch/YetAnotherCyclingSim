#requires -Version 7.4
<# Technical GPU-only road review after exact-SHA saved/reloaded consumer PASS. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string] $ExpectedHead,
    [Parameter(Mandatory)][ValidatePattern('^[1-9][0-9]{0,19}-[1-9][0-9]{0,5}$')][string] $RunToken,
    [string] $WorkspaceConfig = 'D:\yacs\workspace.json',
    [string] $RepoRoot = (Join-Path $PSScriptRoot '../..')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'GPU asphalt review requires an owned Windows runner.' }
$PROFILE_DIAGNOSTIC = 'road-network-profile-diagnostic.json'
$root = $null
$proof = $null
$renderProcess = $null
$receipt = [ordered]@{
    schema_version = 1; issue = 364; exact_sha = $ExpectedHead
    run_token = $RunToken; status = 'PREFLIGHT_PENDING'
    authenticated_saved_and_reloaded = $false
    original_map_mutated = $false; geometry_mutated = $false
    native_lit_frames_retained = $false; verified_frame_count = 0
    shoulder_network_material_ids_verified = $false
    shoulder_support_count = 0; shoulder_material_target_count = 0
    shoulder_selected_triangle_count = 0; expected_view_plan = $null
    road_profile_diagnostic_sha256 = $null
    gpu_shader_compilation_admitted = $false
    road_pixel_visibility_admitted = $false
    owner_visual_status = 'PENDING_FINAL_M3'
    performance_status = 'DEFERRED_AFTER_M3'; performance_pass = $false
    editor_pid = $null; editor_exit_code = $null
    editor_exit_observed = $false; stopped_on_failure = $false
    max_editor_seconds = 1200
    program_executable = $null; source_receipts = [ordered]@{}
    evidence = [ordered]@{}; error = $null; secondary_errors = @()
}

function Assert-PlainPath {
    param([string] $Path)
    if (-not [IO.Path]::IsPathFullyQualified($Path) -or $Path -match '[\x00\r\n"]') {
        throw 'Road review paths must be absolute and plain.'
    }
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        try { $attrs = [IO.File]::GetAttributes($cursor) }
        catch [IO.FileNotFoundException] { $attrs = $null }
        catch [IO.DirectoryNotFoundException] { $attrs = $null }
        if ($null -ne $attrs -and ($attrs -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Road visual review cannot traverse symbolic/reparse paths.'
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}

function File-Identity {
    param([string] $Path, [long] $Limit = 64MB, [switch] $AllowEmpty)
    Assert-PlainPath $Path
    $before = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ($before.PSIsContainer -or $before.Length -gt $Limit -or
        ($before.Length -eq 0 -and -not $AllowEmpty)) {
        throw 'Road review expected a bounded regular file.'
    }
    $hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    $after = Get-Item -LiteralPath $Path -Force
    if ($before.Length -ne $after.Length -or
        $before.LastWriteTimeUtc.Ticks -ne $after.LastWriteTimeUtc.Ticks) {
        throw 'Road review source changed during hash read.'
    }
    return [ordered]@{ path = [IO.Path]::GetFullPath($Path)
        sha256 = $hash; size_bytes = $before.Length }
}

function Assert-Identity {
    param($Original, [long] $Limit = 64MB)
    $actual = File-Identity $Original.path $Limit
    if ($Original.sha256 -cne $actual.sha256 -or
        $Original.size_bytes -ne $actual.size_bytes) {
        throw 'Authenticated road evidence changed after GPU process.'
    }
}

function Log-Identity {
    param([string] $Path)
    for ($i = 1; $i -le 40; $i++) {
        try { return File-Identity $Path 64MB -AllowEmpty }
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
            if (-not $locked -or $i -eq 40) { throw }
            Start-Sleep -Milliseconds 250
        }
    }
}

function Read-PinnedJson {
    param([string] $Path, [long] $Limit = 2MB)
    $identity = File-Identity $Path $Limit
    $value = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -AsHashtable -Depth 40
    Assert-Identity $identity $Limit
    if ($value -isnot [Collections.IDictionary]) {
        throw 'Road review pinned receipt is not a JSON object.'
    }
    return [ordered]@{ identity = $identity; value = $value }
}

function Write-ExclusiveReceipt {
    param([string] $Path, $Value)
    Assert-PlainPath $Path
    $raw = [Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 35))
    if ($raw.Length -gt 2MB) { throw 'GPU road host receipt exceeds fixed bound.' }
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
    $proofCopy = File-Identity (Join-Path $ProofRoot $PROFILE_DIAGNOSTIC) 8MB
    $retainedCopy = File-Identity (Join-Path $RetainedRoot $PROFILE_DIAGNOSTIC) 8MB
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
        throw ('GPU road preview must yield to existing local Editor: ' + $state.status)
    }
}

function Require-ExactSource {
    param([string] $Relative)
    $committed = @(& git -C $root rev-parse ($ExpectedHead + ':' + $Relative))
    $working = @(& git -C $root hash-object --no-filters -- (Join-Path $root $Relative))
    if ($LASTEXITCODE -ne 0 -or $committed.Count -ne 1 -or
        $working.Count -ne 1 -or $committed[0] -cne $working[0]) {
        throw ('Road GPU executable differs from committed exact SHA: ' + $Relative)
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

function Assert-JsonEqual {
    param($Expected, $Actual, [string] $At = 'view plan')
    if ($null -eq $Expected) {
        if ($null -ne $Actual) { throw ('Unexpected value at ' + $At) }
    }
    elseif ($Expected -is [Collections.IDictionary]) {
        if ($Actual -isnot [Collections.IDictionary] -or $Expected.Count -ne $Actual.Count) {
            throw ('JSON object differs at ' + $At)
        }
        foreach ($key in $Expected.Keys) {
            if (@($Actual.Keys) -cnotcontains $key) { throw ('Missing exact JSON key at ' + $At) }
            Assert-JsonEqual $Expected[$key] $Actual[$key] ($At + '.' + $key)
        }
    }
    elseif ($Expected -is [Collections.IList]) {
        if ($Actual -isnot [Collections.IList] -or $Expected.Count -ne $Actual.Count) {
            throw ('Ordered JSON inventory differs at ' + $At)
        }
        for ($index = 0; $index -lt $Expected.Count; $index++) {
            Assert-JsonEqual $Expected[$index] $Actual[$index] ($At + '[' + $index + ']')
        }
    }
    elseif ($Expected -is [bool]) {
        if ($Actual -isnot [bool] -or $Actual -ne $Expected) { throw ('Boolean differs at ' + $At) }
    }
    elseif ($Expected -is [string]) {
        if ($Actual -isnot [string] -or $Actual -cne $Expected) { throw ('String differs at ' + $At) }
    }
    else {
        if (($Actual -isnot [long] -and $Actual -isnot [int] -and $Actual -isnot [double]) -or
            -not [double]::IsFinite([double]$Actual) -or [double]$Actual -ne [double]$Expected) {
            throw ('Number differs at ' + $At)
        }
    }
}

function Assert-ViewPlan {
    param($Plan)
    if ($Plan -isnot [Collections.IDictionary] -or $Plan.schema_version -ne 1 -or
        $Plan.survey_sha256 -cne '15e0a2350c613bf52bfb1354192043ca0c6cd785493c59e7721305b67de099a3' -or
        $Plan.sampling -cne 'all_occupied_250m_road_cells_both_directions_plus_exceptions' -or
        $Plan.source_window_count -ne 185 -or $Plan.cell_size_m -ne 250 -or
        $Plan.occupied_road_cells.Count -ne 24 -or
        $Plan.frames -isnot [Collections.IList] -or
        $Plan.frame_count -ne $Plan.frames.Count -or
        $Plan.frame_count -lt 48 -or $Plan.frame_count -gt 80) {
        throw 'Expected view plan is not the bounded authenticated full-area sample.'
    }
    foreach ($name in @('exhaustive_road_pixel_visibility', 'whole_area_owner_accepted', 'performance_pass')) {
        if ($Plan[$name] -isnot [bool] -or $Plan[$name]) {
            throw ('Expected view plan overstates admission: ' + $name)
        }
    }
    $names = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($frame in $Plan.frames) {
        if ($frame.frame_id -cnotmatch '^window-[0-9]{4}-(forward|reverse)-[0-9]{5}$' -or
            -not $names.Add($frame.frame_id)) { throw 'Expected view inventory has invalid or repeated IDs.' }
    }
}

function Assert-NativeCameraObservation {
    param($Pose, $Observed)
    if ($Observed -isnot [Collections.IDictionary] -or
        $Observed.rotation_setter_accepted -isnot [bool] -or -not $Observed.rotation_setter_accepted -or
        $Observed.location_cm -isnot [Collections.IList] -or $Observed.location_cm.Count -ne 3 -or
        $Observed.forward_unit -isnot [Collections.IList] -or $Observed.forward_unit.Count -ne 3) {
        throw 'Native camera observation is missing a successful pose readback.'
    }
    foreach ($number in (@($Observed.fov_deg, $Observed.forward_error) +
                         @($Observed.location_cm) + @($Observed.forward_unit))) {
        if (($number -isnot [double] -and $number -isnot [int] -and $number -isnot [long]) -or
            -not [double]::IsFinite([double]$number)) {
            throw 'Native camera readback contains a non-finite or non-numeric value.'
        }
    }
    $delta = @()
    $distanceSquared = 0.0
    $forwardSquared = 0.0
    for ($axis = 0; $axis -lt 3; $axis++) {
        if ([math]::Abs([double]$Observed.location_cm[$axis] - $Pose.camera_location_cm[$axis]) -gt 0.1) {
            throw 'Native camera location differs from the pinned source pose.'
        }
        $component = $Pose.target_cm[$axis] - $Pose.camera_location_cm[$axis]
        $delta += $component
        $distanceSquared += $component * $component
        $forwardSquared += [double]$Observed.forward_unit[$axis] * $Observed.forward_unit[$axis]
    }
    if ($distanceSquared -le 0 -or -not [double]::IsFinite($distanceSquared) -or
        [math]::Abs([math]::Sqrt($forwardSquared) - 1.0) -gt 0.00001 -or
        [math]::Abs([double]$Observed.fov_deg - $Pose.fov_deg) -gt 0.001) {
        throw 'Native camera direction or FOV differs from the pinned source pose.'
    }
    $errorSquared = 0.0
    $distance = [math]::Sqrt($distanceSquared)
    for ($axis = 0; $axis -lt 3; $axis++) {
        $component = [double]$Observed.forward_unit[$axis] - $delta[$axis] / $distance
        $errorSquared += $component * $component
    }
    $error = [math]::Sqrt($errorSquared)
    if ($error -gt 0.00001 -or $Observed.forward_error -lt 0 -or
        $Observed.forward_error -gt 0.00001 -or
        [math]::Abs([double]$Observed.forward_error - $error) -gt 0.000000000001) {
        throw 'Native camera forward readback differs from the independently recomputed target direction.'
    }
}

function Assert-GpuReviewContract {
    param($Data, $Plan, [string] $PlanSha, [string] $ManifestSha,
          [long] $SelectedTriangles, [string] $ExactHead, [string] $Token, [string] $ProfileSha)
    Assert-ViewPlan $Plan
    if ($Data.status -cne 'ROAD_ASPHALT_LIT_REVIEW_FRAMES_RETAINED' -or
        $Data.schema_version -ne 1 -or $Data.issue -ne 364 -or
        $Data.exact_sha -cne $ExactHead -or $Data.run_token -cne $Token -or
        $Data.saved_manifest_sha256 -cne $ManifestSha -or
        $Data.road_profile_diagnostic_sha256 -cne $ProfileSha -or
        $Data.view_plan_sha256 -cne $PlanSha -or
        $Data.camera_csv_sha256 -cne $Plan.survey_sha256 -or
        $Data.frame_count -ne $Plan.frame_count -or $Data.expected_frame_count -ne $Plan.frame_count -or
        $Data.frames -isnot [Collections.IList] -or $Data.frames.Count -ne $Plan.frames.Count -or
        $Data.shoulder_support_count -ne 186 -or $Data.shoulder_material_target_count -ne 185 -or
        $Data.shoulder_selected_triangle_count -ne $SelectedTriangles -or
        $Data.priming_frames_per_pose -ne 3 -or $Data.completed_priming_frames -ne (3 * $Plan.frame_count) -or
        $Data.gpu_shutdown_quiescence_seconds -ne 10.0 -or
        $Data.owner_visual_status -cne 'PENDING_FINAL_M3' -or
        $Data.performance_status -cne 'DEFERRED_AFTER_M3' -or $Data.errors.Count -ne 0) {
        throw 'Native lit receipt differs from the pinned network, plan or priming inventory.'
    }
    $flags = @{ native_lit_frames_retained = $true; shoulder_network_material_ids_verified = $true
        shoulder_wall_materials_unchanged = $true; road_full_buffers_unchanged = $true
        dry_asphalt_response_verified = $true; sources_and_saved_assets_unchanged = $true
        capture_readiness_verified = $true; residency_requests_released = $true
        transient_camera_destroyed = $true; gpu_shader_compilation_admitted = $false
        road_pixel_visibility_admitted = $false; whole_area_visual_admitted = $false
        shoulder_wall_materials_admitted = $false; exhaustive_road_pixel_visibility = $false
        whole_area_owner_accepted = $false; terrain_geometry_repaired = $false; performance_pass = $false }
    foreach ($name in $flags.Keys) {
        if ($Data[$name] -isnot [bool] -or $Data[$name] -ne $flags[$name]) {
            throw ('Native lit receipt changed protected flag: ' + $name)
        }
    }
    $audit = $Data.transient_dirty_package_audit
    if ($audit.no_original_or_content_package_dirty -isnot [bool] -or
        -not $audit.no_original_or_content_package_dirty -or
        $audit.dirty_derived_package_saved -isnot [bool] -or $audit.dirty_derived_package_saved -or
        $audit.dirty_content_count -ne 0) { throw 'GPU capture dirtied original/content packages.' }
    $sampling = [ordered]@{}
    foreach ($key in $Plan.Keys) { if ($key -cne 'frames') { $sampling[$key] = $Plan[$key] } }
    Assert-JsonEqual $sampling $Data.material_view_sampling 'material_view_sampling'
    for ($i = 0; $i -lt $Plan.frames.Count; $i++) {
        $expected = $Plan.frames[$i]
        $frame = $Data.frames[$i]
        $actualPose = [ordered]@{}
        foreach ($key in $expected.Keys) { $actualPose[$key] = $frame[$key] }
        Assert-JsonEqual $expected $actualPose ('ordered frame ' + $i)
        Assert-NativeCameraObservation $expected $frame.native_camera_observation
        if ($frame.file -cne ('road-asphalt-lit-review/frames/' + $expected.frame_id + '.png') -or
            $frame.width -ne 1280 -or $frame.height -ne 720 -or $frame.unique_sampled_rgb -lt 12 -or
            $frame.visual_quality_reviewed -isnot [bool] -or $frame.visual_quality_reviewed -or
            $frame.render_mode -cne 'lit' -or
            $frame.priming_frames -isnot [Collections.IList] -or $frame.priming_frames.Count -ne 3) {
            throw ('Road screenshot content/phase differs: ' + $expected.frame_id)
        }
        $ready = $frame.capture_readiness
        if ($ready.status -cne 'NATIVE_LOADING_AND_MIPS_READY' -or
            $ready.height_mip_lease_requested -isnot [bool] -or -not $ready.height_mip_lease_requested -or
            $ready.viewport_primed_at_rider_camera -isnot [bool] -or -not $ready.viewport_primed_at_rider_camera -or
            $ready.material_texture_count -ne 7) {
            throw ('Road pose lacks native height/material mip readiness: ' + $expected.frame_id)
        }
        for ($prime = 0; $prime -lt 3; $prime++) {
            $expectedFile = 'road-asphalt-lit-review/priming/' + $expected.frame_id + ('-{0:d2}.png' -f $prime)
            if ($frame.priming_frames[$prime].file -cne $expectedFile) {
                throw ('Road pose priming inventory differs: ' + $expected.frame_id)
            }
            Assert-NativeCameraObservation $expected $frame.priming_frames[$prime].native_camera_observation
        }
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
        throw 'GPU road review must use exact shared-host isolated run checkout.'
    }
    $head = @(& git -C $root rev-parse HEAD)
    if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1 -or $head[0] -cne $ExpectedHead) {
        throw 'GPU road review exact Git HEAD differs.'
    }
    & git -C $root diff --quiet HEAD -- . ':(exclude)Content/**'
    if ($LASTEXITCODE -ne 0) { throw 'GPU road review tracked source is modified.' }
    foreach ($relative in @(
        'scripts/ue/Invoke-YacsRoadAsphaltRender.ps1',
        'scripts/ue/road_asphalt_gpu_review.py',
        'scripts/ue/road_asphalt_saved_consumer.py',
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
        'worldgen/terrain/benchmarks/sa_calobra/world_data/frozen_road_recipe_2026-10-04.json',
        'docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv'
    )) { Require-ExactSource $relative }
    $proof = Join-Path $root ('Saved/RuntimeProof/RoadMaterialBaseline/' + $RunToken)
    Assert-PlainPath $proof
    $readHost = Read-PinnedJson (Join-Path $proof 'host-receipt.json')
    $savedHost = Read-PinnedJson (Join-Path $proof 'saved-road-host-receipt.json')
    $savedReceipt = Read-PinnedJson (Join-Path $proof 'road-asphalt-saved-prepared.json')
    $reopenReceipt = Read-PinnedJson (Join-Path $proof 'road-asphalt-saved-reloaded.json')
    # Full-network selected IDs require 4 MiB; other JSON receipts retain 2 MiB.
    $savedManifest = Read-PinnedJson (Join-Path $proof 'road-asphalt-saved-manifest.json') 4MB
    $selectedTriangles = Assert-NetworkManifest $savedManifest.value $ExpectedHead
    if ($readHost.value.status -cne 'ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE' -or
        $readHost.value.exact_sha -cne $ExpectedHead -or
        $savedHost.value.status -cne 'ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_HOST_PASS' -or
        $savedHost.value.exact_sha -cne $ExpectedHead -or
        $savedHost.value.saved_derived_consumer -isnot [bool] -or
        -not $savedHost.value.saved_derived_consumer -or
        $savedHost.value.fresh_reload_verified -isnot [bool] -or
        -not $savedHost.value.fresh_reload_verified -or
        $savedHost.value.shoulder_network_fresh_reload_verified -isnot [bool] -or
        -not $savedHost.value.shoulder_network_fresh_reload_verified -or
        $savedHost.value.shoulder_support_count -ne 186 -or
        $savedHost.value.shoulder_material_target_count -ne 185 -or
        $savedHost.value.shoulder_selected_triangle_count -ne $selectedTriangles -or
        $savedHost.value.original_map_saved -isnot [bool] -or $savedHost.value.original_map_saved -or
        $savedHost.value.original_landscape_mutated -isnot [bool] -or
        $savedHost.value.original_landscape_mutated -or
        $savedHost.value.proof_files.saved_prepared.sha256 -cne $savedReceipt.identity.sha256 -or
        $savedHost.value.proof_files.fresh_reload.sha256 -cne $reopenReceipt.identity.sha256 -or
        $savedHost.value.proof_files.saved_manifest.sha256 -cne $savedManifest.identity.sha256 -or
        $savedHost.value.proof_files.saved_manifest.size_bytes -ne $savedManifest.identity.size_bytes -or
        $savedReceipt.value.manifest.sha256 -cne $savedManifest.identity.sha256 -or
        $savedReceipt.value.manifest.size_bytes -ne $savedManifest.identity.size_bytes -or
        $savedReceipt.value.evidence_manifest.file -cne 'road-asphalt-saved-manifest.json' -or
        $savedReceipt.value.evidence_manifest.sha256 -cne $savedManifest.identity.sha256 -or
        $savedReceipt.value.evidence_manifest.size_bytes -ne $savedManifest.identity.size_bytes -or
        $reopenReceipt.value.status -cne 'ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_PASS' -or
        $reopenReceipt.value.exact_sha -cne $ExpectedHead -or
        $reopenReceipt.value.saved_manifest_sha256 -cne $savedManifest.identity.sha256 -or
        $reopenReceipt.value.evidence_manifest_sha256 -cne $savedManifest.identity.sha256 -or
        $reopenReceipt.value.shoulder_network_fresh_reload_verified -isnot [bool] -or
        -not $reopenReceipt.value.shoulder_network_fresh_reload_verified -or
        $reopenReceipt.value.shoulder_support_count -ne 186 -or
        $reopenReceipt.value.shoulder_material_target_count -ne 185 -or
        $reopenReceipt.value.shoulder_selected_triangle_count -ne $selectedTriangles -or
        $reopenReceipt.value.road_material_reapplied -isnot [bool] -or
        $reopenReceipt.value.road_material_reapplied -or
        $reopenReceipt.value.shoulder_material_reapplied -isnot [bool] -or
        $reopenReceipt.value.shoulder_material_reapplied -or
        $reopenReceipt.value.performance_pass -isnot [bool] -or
        $reopenReceipt.value.performance_pass) {
        throw 'Native road source and saved/reloaded materials are not admitted.'
    }
    $workspace = Read-PinnedJson $WorkspaceConfig
    if ($workspace.identity.sha256 -cne $readHost.value.proof_files.workspace_config.sha256 -or
        $workspace.identity.size_bytes -ne $readHost.value.proof_files.workspace_config.size_bytes) {
        throw 'Profile workspace configuration differs from the authenticated native baseline.'
    }
    $retainedRoot = Resolve-ProfileRetainedRoot $workspace.value $WorkspaceConfig `
        $ExpectedHead $RunToken $savedReceipt.value.retained_root
    $profileCopies = Get-ProfileCopies $savedManifest.value.road_profile_diagnostic $proof $retainedRoot
    if ($reopenReceipt.value.road_profile_diagnostic_sha256 -cne $profileCopies.proof.sha256 -or
        $savedHost.value.road_profile_diagnostic_sha256 -cne $profileCopies.proof.sha256 -or
        $savedHost.value.proof_files.road_profile_diagnostic.sha256 -cne $profileCopies.proof.sha256 -or
        $savedHost.value.proof_files.road_profile_diagnostic.size_bytes -ne $profileCopies.proof.size_bytes -or
        $savedHost.value.proof_files.retained_road_profile_diagnostic.sha256 -cne $profileCopies.retained.sha256 -or
        $savedHost.value.proof_files.retained_road_profile_diagnostic.size_bytes -ne $profileCopies.retained.size_bytes) {
        throw 'Fresh native profile diagnostic proof differs from its two pinned copies.'
    }
    $receipt.source_receipts.baseline = $readHost.identity
    $receipt.source_receipts.saved_host = $savedHost.identity
    $receipt.source_receipts.saved_prepared = $savedReceipt.identity
    $receipt.source_receipts.fresh_reload = $reopenReceipt.identity
    $receipt.source_receipts.saved_manifest = $savedManifest.identity
    $receipt.source_receipts.workspace_config = $workspace.identity
    $receipt.source_receipts.road_profile_diagnostic = $profileCopies.proof
    $receipt.source_receipts.retained_road_profile_diagnostic = $profileCopies.retained
    $receipt.authenticated_saved_and_reloaded = $true
    $cmdPath = [string] $readHost.value.proof_files.editor_executable.path
    $cmdIdentity = File-Identity $cmdPath 1GB
    if ($cmdIdentity.sha256 -cne $readHost.value.proof_files.editor_executable.sha256 -or
        -not $cmdPath.EndsWith('UnrealEditor-Cmd.exe', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Cannot bind GPU Editor to the approved Unreal commandline engine.'
    }
    $gui = Join-Path (Split-Path -Parent $cmdPath) 'UnrealEditor.exe'
    $program = File-Identity $gui 1GB
    $receipt.program_executable = $program
    foreach ($row in $readHost.value.binary_provenance) {
        Assert-Identity $row.copied_identity 512MB
    }
    # Generate and pin the exact ordered survey plan before opening Unreal.
    # Reuse the already installed proof Python with isolated import state.
    $planPython = File-Identity 'D:\yacs\tool-cache\material-forge\python\Scripts\python.exe' 1GB
    $planCode = @'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from scripts.ue.road_material_views import current_view_plan
print(json.dumps(current_view_plan(Path(sys.argv[1])), sort_keys=True, allow_nan=False))
'@
    $planOutput = @(& $planPython.path -I -B -c $planCode $root)
    if ($LASTEXITCODE -ne 0 -or $planOutput.Count -ne 1) {
        throw 'Cannot derive the current authenticated ordered road view plan.'
    }
    $plan = $planOutput[0] | ConvertFrom-Json -AsHashtable -Depth 40
    Assert-ViewPlan $plan
    $cameraSource = File-Identity (Join-Path $root 'docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv') 1MB
    if ($cameraSource.sha256 -cne $plan.survey_sha256) { throw 'View plan CSV source differs.' }
    $planPath = Join-Path $proof 'road-asphalt-expected-view-plan.json'
    Write-ExclusiveReceipt $planPath $plan
    $expectedPlan = Read-PinnedJson $planPath
    Assert-JsonEqual $plan $expectedPlan.value 'retained expected view plan'
    $receipt.expected_view_plan = $expectedPlan.identity
    $receipt.view_plan_sha256 = $expectedPlan.identity.sha256
    $receipt.expected_frame_count = $expectedPlan.value.frame_count
    $receipt.source_receipts.view_plan_python = $planPython
    $receipt.source_receipts.camera_csv = $cameraSource
    Require-IdleHost
    $script = Join-Path $root 'scripts/ue/road_asphalt_gpu_review.py'
    $arguments = @(
        ('"' + (Join-Path $root 'YetAnotherCyclingSim.uproject') + '"'),
        '/Engine/Maps/Entry',
        '-DisablePlugins=ModelContextProtocol,Wingman,AndroidFileServer',
        '-RenderOffscreen', '-norhithread',
        '-Unattended', '-NoPause', '-NoSplash', '-NoSound',
        '-NoLiveCoding', '-NoVSync', '-NoP4', '-ScriptErrorsAreFatal',
        '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
        ('-ExecutePythonScript="' + $script + '"'),
        ('-AbsLog="' + (Join-Path $proof 'road-asphalt-gpu-editor.log') + '"')
    )
    $stdout = Join-Path $proof 'road-asphalt-gpu-stdout.log'
    $stderr = Join-Path $proof 'road-asphalt-gpu-stderr.log'
    foreach ($path in @($stdout, $stderr)) {
        Assert-PlainPath $path
        if (Test-Path -LiteralPath $path) {
            throw 'GPU road review cannot overwrite existing process log.'
        }
    }
    $receipt.status = 'GPU_RENDER_RUNNING'
    $renderProcess = Start-Process -FilePath $gui -ArgumentList $arguments `
        -WorkingDirectory $root -PassThru -NoNewWindow `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
        -Environment @{
            YACS_ROAD_SAVED_RUN_TOKEN = $RunToken
            YACS_ROAD_MATERIAL_EXPECTED_HEAD = $ExpectedHead
            YACS_ROAD_MATERIAL_PREPARATION_SHA256 = [string] $readHost.value.proof_files.session_preparation.sha256
            YACS_ROAD_MATERIAL_VIEW_PLAN_SHA256 = [string] $expectedPlan.identity.sha256
            YACS_WORKSPACE_CONFIG = $WorkspaceConfig
            YACS_OWNER_HANDOFF = ''; PYTHONPATH = ''; PYTHONHOME = ''
            YACS_MCP_BOB_PROJECT_ROOT = ''; YACS_MCP_BOB_EXPECTED_HEAD = ''
        }
    $receipt.editor_pid = $renderProcess.Id
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while (-not $renderProcess.WaitForExit(200)) {
        if ($watch.Elapsed.TotalSeconds -gt 1200) {
            throw 'Owned GPU road review exceeded strict 1200 second full-network host deadline.'
        }
    }
    $renderProcess.WaitForExit()
    $receipt.editor_exit_observed = $true
    $receipt.editor_exit_code = $renderProcess.ExitCode
    $receipt.editor_seconds = $watch.Elapsed.TotalSeconds
    if ($renderProcess.ExitCode -ne 0) {
        throw 'GPU Unreal review exited nonzero; no render acceptance.'
    }
    $review = Read-PinnedJson (Join-Path $proof 'road-asphalt-lit-review.json')
    $data = $review.value
    Assert-GpuReviewContract $data $expectedPlan.value $expectedPlan.identity.sha256 `
        $savedManifest.identity.sha256 $selectedTriangles $ExpectedHead $RunToken $profileCopies.proof.sha256
    $expectedIds = @($expectedPlan.value.frames | ForEach-Object { $_.frame_id })
    for ($i = 0; $i -lt $expectedIds.Count; $i++) {
        $frame = $data.frames[$i]
        $file = File-Identity (Join-Path $proof ($frame.file.Replace('/', '\'))) 16MB
        if ($file.sha256 -cne $frame.sha256 -or
            $file.size_bytes -ne $frame.size_bytes) {
            throw ('Native road screenshot hash changed: ' + $expectedIds[$i])
        }
        $receipt.evidence[$expectedIds[$i]] = $file
        for ($prime = 0; $prime -lt 3; $prime++) {
            $priming = $frame.priming_frames[$prime]
            $primingFile = File-Identity (Join-Path $proof ($priming.file.Replace('/', '\'))) 16MB
            if ($primingFile.sha256 -cne $priming.sha256 -or $primingFile.size_bytes -ne $priming.size_bytes) {
                throw ('Native road priming PNG changed: ' + $expectedIds[$i])
            }
            $receipt.evidence[($expectedIds[$i] + '-priming-' + $prime)] = $primingFile
        }
        $readinessRoot = Join-Path $proof ('road-asphalt-lit-review/readiness/' + $expectedIds[$i])
        $heightFile = File-Identity (Join-Path $readinessRoot 'capture-readiness.json') 8MB
        $materialReady = Read-PinnedJson (Join-Path $readinessRoot 'road-texture-readiness.json')
        if ($heightFile.sha256 -cne $frame.capture_readiness.height_receipt.sha256 -or
            $heightFile.size_bytes -ne $frame.capture_readiness.height_receipt.size_bytes -or
            $materialReady.identity.sha256 -cne $frame.capture_readiness.material_receipt.sha256 -or
            $materialReady.identity.size_bytes -ne $frame.capture_readiness.material_receipt.size_bytes -or
            $materialReady.value.status -cne 'ROAD_TEXTURE_MIPS_READY' -or
            $materialReady.value.textures.Count -ne 7 -or
            $materialReady.value.material_parameters_changed -isnot [bool] -or
            $materialReady.value.material_parameters_changed -or
            $materialReady.value.saved_to_map -isnot [bool] -or $materialReady.value.saved_to_map) {
            throw ('Pinned road height/material readiness changed: ' + $expectedIds[$i])
        }
        foreach ($texture in $materialReady.value.textures) {
            $native = $texture.native_readback
            if ($native.is_default_texture -isnot [bool] -or $native.is_default_texture -or
                $native.is_compiling -isnot [bool] -or $native.is_compiling -or
                $native.mips -le 0 -or $native.resident_mips -ne $native.mips) {
                throw ('Native material texture lacks full mip residency: ' + $expectedIds[$i])
            }
        }
        $receipt.evidence[($expectedIds[$i] + '-height-readiness')] = $heightFile
        $receipt.evidence[($expectedIds[$i] + '-material-readiness')] = $materialReady.identity
    }
    $receipt.evidence.render_receipt = $review.identity
    foreach ($original in @($readHost.identity, $savedHost.identity, $savedReceipt.identity,
                            $reopenReceipt.identity)) { Assert-Identity $original 2MB }
    Assert-Identity $savedManifest.identity 4MB
    Assert-Identity $profileCopies.proof 8MB
    Assert-Identity $profileCopies.retained 8MB
    Assert-Identity $workspace.identity 2MB
    Assert-Identity $expectedPlan.identity 2MB
    Assert-Identity $cameraSource 1MB
    Assert-Identity $planPython 1GB
    Assert-Identity $program 1GB
    Require-IdleHost
    $receipt.verified_frame_count = $expectedIds.Count
    $receipt.verified_frame_ids = $expectedIds
    $receipt.material_view_sampling = $data.material_view_sampling
    $receipt.shoulder_network_material_ids_verified = $true
    $receipt.shoulder_support_count = 186
    $receipt.shoulder_material_target_count = 185
    $receipt.shoulder_selected_triangle_count = $selectedTriangles
    $receipt.road_profile_diagnostic_sha256 = $profileCopies.proof.sha256
    $receipt.native_lit_frames_retained = $true
    $receipt.status = 'ROAD_ASPHALT_GPU_LIT_REVIEW_HOST_PASS'
}
catch {
    $receipt.status = 'FAILED'
    $receipt.error = $_.Exception.Message
    throw
}
finally {
    if ($null -ne $renderProcess) {
        try {
            if (-not $renderProcess.HasExited) {
                $renderProcess.Kill()
                if (-not $renderProcess.WaitForExit(10000)) {
                    throw 'Owned Unreal GPU review process failed to stop.'
                }
                $receipt.stopped_on_failure = $true
            }
            $receipt.editor_exit_observed = $true
            $receipt.editor_exit_code = $renderProcess.ExitCode
        }
        catch { $receipt.secondary_errors += $_.Exception.Message }
        finally { $renderProcess.Dispose() }
    }
    if ($proof -and (Test-Path -LiteralPath $proof -PathType Container)) {
        foreach ($name in @(
            'road-asphalt-gpu-editor.log',
            'road-asphalt-gpu-stdout.log',
            'road-asphalt-gpu-stderr.log'
        )) {
            $path = Join-Path $proof $name
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                try { $receipt.evidence[$name] = Log-Identity $path }
                catch { $receipt.secondary_errors += $_.Exception.Message }
            }
            elseif ($receipt.editor_pid) {
                $receipt.secondary_errors += ('Missing GPU Editor output log: ' + $name)
            }
        }
        if ($receipt.secondary_errors.Count -gt 0) {
            $receipt.status = 'FAILED'
            $receipt.native_lit_frames_retained = $false
            $receipt.shoulder_network_material_ids_verified = $false
            $receipt.error = 'GPU review process/log teardown did not complete.'
        }
        try {
            Write-ExclusiveReceipt (Join-Path $proof 'road-asphalt-gpu-host-receipt.json') $receipt
        }
        catch {
            if ($null -eq $receipt.error) { throw }
            Write-Warning 'Unable to retain GPU host receipt after a prior failure.'
        }
    }
}
if ($receipt.status -cne 'ROAD_ASPHALT_GPU_LIT_REVIEW_HOST_PASS' -or
    -not $receipt.native_lit_frames_retained -or -not $receipt.shoulder_network_material_ids_verified) {
    throw 'Road GPU technical evidence failed the independent native host gate.'
}
Write-Host ('ROAD_ASPHALT_GPU_LIT_REVIEW_HOST_PASS; ' + $receipt.verified_frame_count +
    ' pinned ordered lit road-facing frames, owner visual and FPS pending.')
