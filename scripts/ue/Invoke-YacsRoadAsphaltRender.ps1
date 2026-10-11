#requires -Version 7.4
<# Technical GPU-only road review after exact-SHA saved/reloaded consumer PASS. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string] $ExpectedHead,
    [Parameter(Mandatory)][ValidatePattern('^[1-9][0-9]{0,19}-[1-9][0-9]{0,5}$')][string] $RunToken,
    [switch] $EdgeMarkings,
    [switch] $VisualControls,
    [switch] $CrackCanary,
    [string] $WorkspaceConfig = 'D:\yacs\workspace.json',
    [string] $RepoRoot = (Join-Path $PSScriptRoot '../..')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'GPU asphalt review requires an owned Windows runner.' }
if ($CrackCanary -and (-not $EdgeMarkings -or $VisualControls)) {
    throw 'The crack canary requires white markings and its own separate diagnostic sequence.'
}
$PROFILE_DIAGNOSTIC = 'road-network-profile-diagnostic.json'
$root = $null
$proof = $null
$renderProcess = $null
$expectedControls = $null
$expectedCrackControls = $null
$edgeMarkingSetting = if ($EdgeMarkings) { '1' } else { '0' }
$visualControlToken = if ($VisualControls) { $RunToken } else { $null }
$crackCanarySetting = if ($CrackCanary) { '1' } else { '0' }
$crackControlToken = if ($CrackCanary) { $RunToken } else { $null }
$expectedMaterialTextureCount = if ($CrackCanary) { 15 } else { 7 }
$receipt = [ordered]@{
    schema_version = 1; issue = 364; exact_sha = $ExpectedHead
    run_token = $RunToken; status = 'PREFLIGHT_PENDING'
    authenticated_saved_and_reloaded = $false
    original_map_mutated = $false; geometry_mutated = $false
    native_lit_frames_retained = $false; verified_frame_count = 0
    shoulder_network_material_ids_verified = $false
    shoulder_material_edge_uv_verified = $false
    shoulder_support_count = 0; shoulder_material_target_count = 0
    shoulder_selected_triangle_count = 0; expected_view_plan = $null
    edge_markings_requested = [bool]$EdgeMarkings
    edge_markings_verified = $false
    visual_controls_requested = [bool]$VisualControls
    visual_controls_frames_retained = $false
    visual_control_frame_count = 0
    crack_canary_requested = [bool]$CrackCanary
    crack_canary_verified = $false
    crack_control_frames_retained = $false
    crack_control_frame_count = 0
    crack_normal_space_verified = $false
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
        $Manifest.material_changes -cne 'road_slot_zero_network_outer_shoulder_ids_and_edge_uv') {
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
        $network.schema_version -ne 3 -or $network.status -cne 'SHOULDER_NETWORK_PREPARED' -or
        $network.support_count -ne 186 -or $network.material_target_count -ne 185 -or
        $network.excluded_parapet_count -ne 1 -or
        $network.owners -isnot [Collections.IList] -or $network.owners.Count -ne 186) {
        throw 'Saved source-owned support coverage is incomplete.'
    }
    if (($network.material_edge_uv_channel -isnot [long] -and $network.material_edge_uv_channel -isnot [int]) -or
        $network.material_edge_uv_channel -ne 0) {
        throw 'Saved material edge UV channel differs from the proved zero-UV source.'
    }
    $flags = @{ rollback_verified = $true; source_vertices_topology_normals_uv_prefix_preserved = $true
        material_edge_uv_appended = $true
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

function Assert-VisualControlObservation {
    param($Observed, [string] $Control, [string] $OriginalMaterial, [string] $UniformMaterial)
    $buffer = switch -CaseSensitive ($Control) {
        'current-basecolor' { 'BaseColor' }
        'current-worldnormal' { 'WorldNormal' }
        'current-lit' { $null }
        'uniform-lit' { $null }
        default { throw 'Unsupported visual control mode.' }
    }
    $mode = if ($null -eq $buffer) { 'VMI_LIT' } else { 'VMI_VISUALIZE_BUFFER' }
    $material = if ($Control -ceq 'uniform-lit') { $UniformMaterial } else { $OriginalMaterial }
    if ($Observed.control -cne $Control -or $Observed.active_viewmode_readback -cne $mode -or
        $Observed.road_material_readback -cne $material -or $Observed.requested_buffer -cne $buffer -or
        $Observed.buffer_name_readback_verified -isnot [bool] -or $Observed.buffer_name_readback_verified) {
        throw 'Native control observation differs from the exact material, viewmode or requested buffer.'
    }
}

function Assert-VisualControlContract {
    param($Data, $Expected, [string] $ViewPlanSha, [string] $ManifestSha,
          $LitIdentity, [string] $OriginalMaterial, [string] $ExactHead, [string] $Token)
    $plan = $Expected.control_plan
    if ($Data.schema_version -ne 1 -or $Data.issue -ne 364 -or
        $Data.status -cne 'ROAD_ASPHALT_VISUAL_CONTROLS_FRAMES_RETAINED' -or
        $Data.exact_sha -cne $ExactHead -or $Data.run_token -cne $Token -or
        $Data.map_package -cne '/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview' -or
        $Data.saved_manifest_sha256 -cne $ManifestSha -or $Data.view_plan_sha256 -cne $ViewPlanSha -or
        $Data.camera_csv_sha256 -cne $plan.survey_sha256 -or
        $Data.control_plan_sha256 -cne $Expected.sha256 -or
        $Data.lit_review_receipt.file -cne 'road-asphalt-lit-review.json' -or
        $Data.lit_review_receipt.sha256 -cne $LitIdentity.sha256 -or
        $Data.lit_review_receipt.size_bytes -ne $LitIdentity.size_bytes -or
        $Data.frame_count -ne 8 -or $Data.expected_frame_count -ne 8 -or
        $Data.frames -isnot [Collections.IList] -or $Data.frames.Count -ne 8 -or
        $plan.frame_count -ne 8 -or $plan.jobs.Count -ne 8 -or
        $Data.priming_frames_per_pose -ne 3 -or $Data.completed_priming_frames -ne 24 -or
        $Data.total_deadline_seconds_shared_with_lit -ne 1080 -or $Data.frame_deadline_seconds -ne 180 -or
        $Data.owner_visual_status -cne 'PENDING_FINAL_M3' -or
        $Data.performance_status -cne 'DEFERRED_AFTER_M3' -or $Data.errors.Count -ne 0) {
        throw 'Visual controls do not match the pre-Editor plan, current consumer and 68-frame receipt.'
    }
    Assert-JsonEqual $plan $Data.control_plan 'exact eight-condition plan'
    foreach ($name in @('control_restoration_verified', 'capture_readiness_verified',
                         'native_control_observations_verified', 'sources_and_saved_assets_unchanged')) {
        if ($Data[$name] -isnot [bool] -or -not $Data[$name]) { throw ('Visual control proof failed: ' + $name) }
    }
    foreach ($name in @('native_channel_images_reviewed', 'buffer_name_readback_verified',
                         'geometry_or_source_texture_change', 'map_saved', 'source_assets_saved',
                         'whole_area_visual_admitted', 'performance_pass')) {
        if ($Data[$name] -isnot [bool] -or $Data[$name]) { throw ('Visual controls changed authority: ' + $name) }
    }
    if ($Data.begin.status -cne 'READY' -or $Data.restore.status -cne 'RESTORED' -or
        $Data.begin.plan_sha256 -cne $Expected.sha256 -or $Data.restore.plan_sha256 -cne $Expected.sha256 -or
        $Data.begin.original_material -cne $OriginalMaterial -or
        $Data.begin.transient_material -cnotmatch '^/Engine/Transient\.[^/]+$' -or
        $Data.restore.applied_jobs.Count -ne 8 -or $Data.restore.cleanup_errors.Count -ne 0 -or
        $Data.begin.ownership.run_token -cne $Token -or
        $Data.begin.ownership.consumer_exact_sha -cne $ExactHead -or
        $Data.begin.ownership.owned_process_marker_verified -isnot [bool] -or
        -not $Data.begin.ownership.owned_process_marker_verified) {
        throw 'Visual control process ownership, transient material or restoration is incomplete.'
    }
    foreach ($name in @('ownership', 'native_api')) {
        Assert-JsonEqual $Data.preflight[$name] $Data.begin[$name] ('preflight control ' + $name)
    }
    if ($Data.begin.uniform_node_count -ne 6 -or
        $Data.begin.view_state_contract -cne 'owned_editor_establish_Lit_and_restore_Lit' -or
        $Data.begin.buffer_name_getter_available -isnot [bool] -or $Data.begin.buffer_name_getter_available -or
        $Data.begin.geometry_vertex_normals_preserved -isnot [bool] -or
        -not $Data.begin.geometry_vertex_normals_preserved) {
        throw 'Visual control material or viewport contract differs from the owned diagnostic.'
    }
    $uniform = @{ base_color_linear = @(0.075, 0.075, 0.075); roughness = 0.933
        specular = 0.20; metallic = 0.0; ambient_occlusion = 1.0
        emissive = 0.0; normal_tangent_space = @(0.0, 0.0, 1.0) }
    Assert-JsonEqual $uniform $Data.begin.uniform_material 'uniform control material'
    foreach ($name in @('original_material_restored', 'owned_viewports_returned_to_lit',
                         'saved_and_staged_package_bytes_unchanged')) {
        if ($Data.restore[$name] -isnot [bool] -or -not $Data.restore[$name]) {
            throw ('Visual control restoration failed: ' + $name)
        }
    }
    for ($i = 0; $i -lt 8; $i++) {
        $job = $plan.jobs[$i]
        $frame = $Data.frames[$i]
        $pose = $job.camera
        $actualPose = [ordered]@{}
        foreach ($key in $pose.Keys) {
            $actualPose[$key] = if ($key -ceq 'frame_id') { $frame.source_frame_id } else { $frame[$key] }
        }
        Assert-JsonEqual $pose $actualPose ('control camera metadata ' + $i)
        $renderMode = if ($job.control -cin @('current-basecolor', 'current-worldnormal')) {
            'buffer_visualization'
        } else { 'lit' }
        if ($frame.frame_id -cne $job.job_id -or $frame.source_frame_id -cne $pose.frame_id -or
            $frame.control_mode -cne $job.control -or
            $frame.file -cne ('road-asphalt-visual-controls/frames/' + $job.job_id + '.png') -or
            $frame.width -ne 1280 -or $frame.height -ne 720 -or $frame.unique_sampled_rgb -lt 12 -or
            $frame.render_mode -cne $renderMode -or
            $frame.visual_quality_reviewed -isnot [bool] -or $frame.visual_quality_reviewed -or
            $frame.priming_frames -isnot [Collections.IList] -or $frame.priming_frames.Count -ne 3 -or
            $Data.restore.applied_jobs[$i].job_id -cne $job.job_id) {
            throw 'Visual control frame, camera or mode order changed.'
        }
        Assert-NativeCameraObservation $pose $frame.native_camera_observation
        Assert-VisualControlObservation $Data.restore.applied_jobs[$i] $job.control `
            $OriginalMaterial $Data.begin.transient_material
        $ready = $frame.capture_readiness
        if ($ready.status -cne 'NATIVE_LOADING_AND_MIPS_READY' -or
            $ready.height_mip_lease_requested -isnot [bool] -or -not $ready.height_mip_lease_requested -or
            $ready.viewport_primed_at_rider_camera -isnot [bool] -or -not $ready.viewport_primed_at_rider_camera -or
            $ready.material_texture_count -ne 7) { throw 'Visual control camera lacks native mip readiness.' }
        $captures = @($frame) + @($frame.priming_frames)
        foreach ($capture in $captures) {
            $viewmode = if ($renderMode -ceq 'lit') { 'VMI_LIT' } else { 'VMI_VISUALIZE_BUFFER' }
            Assert-JsonEqual $viewmode $capture.native_viewmode_before 'native visual control viewmode before'
            Assert-JsonEqual $viewmode $capture.native_viewmode_after 'native visual control viewmode after'
            Assert-NativeCameraObservation $pose $capture.native_camera_observation
            Assert-VisualControlObservation $capture.native_control_observation_before $job.control `
                $OriginalMaterial $Data.begin.transient_material
            Assert-VisualControlObservation $capture.native_control_observation_after $job.control `
                $OriginalMaterial $Data.begin.transient_material
        }
        for ($prime = 0; $prime -lt 3; $prime++) {
            $expectedFile = 'road-asphalt-visual-controls/priming/' + $job.job_id + ('-{0:d2}.png' -f $prime)
            if ($frame.priming_frames[$prime].file -cne $expectedFile) {
                throw 'Visual control priming file differs from the fixed plan.'
            }
        }
    }
}

function Assert-SurfaceDetailLanes {
    param($HostReceipt, $Prepared, $Fresh, $Manifest, [bool] $Markings, [bool] $Cracks)
    if ($Cracks -and -not $Markings) { throw 'Crack diagnostics require the saved white marking lane.' }
    foreach ($lane in @(@{ name = 'edge_markings'; singular = 'edge_marking'; enabled = $Markings },
                        @{ name = 'crack_canary'; singular = 'crack'; enabled = $Cracks })) {
        foreach ($row in @($Manifest, $Prepared, $Fresh)) {
            Assert-JsonEqual $lane.enabled $row[($lane.name + '_enabled')] ('saved lane ' + $lane.name)
        }
        Assert-JsonEqual $lane.enabled $HostReceipt[($lane.name + '_requested')] ('requested lane ' + $lane.name)
        Assert-JsonEqual $lane.enabled $HostReceipt[($lane.name + '_fresh_reload_verified')] ('host fresh lane ' + $lane.name)
        Assert-JsonEqual $lane.enabled $Fresh[($lane.name + '_fresh_reload_verified')] ('native fresh lane ' + $lane.name)
        foreach ($suffix in @('_material_reapplied', '_geometry_reapplied')) {
            Assert-JsonEqual $false $Fresh[($lane.singular + $suffix)] ('fresh mutation ' + $lane.name)
        }
        $readback = $Fresh[($lane.singular + '_readback')]
        if (-not $lane.enabled) {
            if ($Manifest.Contains($lane.name) -or $null -ne $readback) {
                throw 'Disabled surface detail lane contains saved assets or a native readback.'
            }
        }
        else {
            if ($Manifest[$lane.name] -isnot [Collections.IDictionary] -or
                $readback -isnot [Collections.IDictionary]) { throw 'Surface detail has no saved and fresh native witness.' }
            Assert-JsonEqual $true $readback.read_only 'fresh read-only surface witness'
            Assert-JsonEqual $false $readback.owner_visual_pass 'surface owner admission'
            Assert-JsonEqual $false $readback.performance_pass 'surface performance admission'
        }
    }
    Assert-JsonEqual $false $HostReceipt.crack_normal_space_verified 'host pending normal review'
    if ($Markings) {
        Assert-JsonEqual 'EDGE_MARKINGS_FRESH_READBACK_VERIFIED' $Fresh.edge_marking_readback.status 'fresh white status'
        Assert-JsonEqual $true $Fresh.edge_marking_readback.all_marking_buffers_verified 'fresh white buffers'
        Assert-JsonEqual $true $Fresh.edge_marking_readback.full_source_buffers_preserved 'fresh original buffers'
    }
    if ($Cracks) {
        $created, $loaded = $Manifest.crack_canary, $Fresh.crack_readback
        if ($created.status -cne 'LOCAL_CRACKS_CREATED_NORMAL_REVIEW_PENDING' -or
            $created.plan_sha256 -cnotmatch '^[0-9a-f]{64}$' -or
            $loaded.status -cne 'LOCAL_CRACKS_FRESH_READBACK_VERIFIED_NORMAL_REVIEW_PENDING' -or
            $loaded.plan_sha256 -cne $created.plan_sha256 -or $loaded.actor_count -ne 2 -or
            $loaded.native_source_witness_sha256 -cnotmatch '^[0-9a-f]{64}$' -or
            $loaded.native_source_witness_sha256 -cne $created.source_correspondence.native_source_witness_sha256 -or
            $Fresh.edge_marking_readback.aggregate_owner -cne 'local_crack_canary') {
            throw 'Crack canary differs from the saved source/paint correspondence and fresh witness.'
        }
        foreach ($flag in @('all_crack_buffers_verified', 'full_source_and_existing_paint_buffers_preserved',
                            'caller_fresh_process_and_saved_bytes_required', 'world_normal_canary_required')) {
            Assert-JsonEqual $true $loaded[$flag] ('fresh crack ' + $flag)
        }
        Assert-JsonEqual $false $created.normal_space_verified 'saved pending normal review'
        Assert-JsonEqual $false $loaded.normal_space_verified 'fresh pending normal review'
    }
}

function Assert-SurfaceDetailGpuReadback {
    param($Data, $Fresh, [bool] $Markings, [bool] $Cracks)
    Assert-JsonEqual $Markings $Data.edge_markings_enabled 'GPU white lane'
    Assert-JsonEqual $Cracks $Data.crack_canary_enabled 'GPU crack lane'
    Assert-JsonEqual $false $Data.crack_normal_space_verified 'GPU pending normal review'
    Assert-JsonEqual $Fresh.edge_marking_readback $Data.edge_markings_before 'fresh paint before GPU'
    Assert-JsonEqual $Data.edge_markings_before $Data.edge_markings_after 'unchanged paint after GPU'
    Assert-JsonEqual $Fresh.crack_readback $Data.crack_before 'fresh cracks before GPU'
    Assert-JsonEqual $Data.crack_before $Data.crack_after 'unchanged cracks after GPU'
}

function Assert-CrackControlPlan {
    param($Expected, $NetworkPlan)
    if ($Expected.sha256 -cne 'f6f8a4fef0c10438fee2ee88827f797b9451ebf5d9e1f0b2334f754f593738d8') {
        throw 'Crack controls do not have the pinned sixteen-condition plan identity.'
    }
    $jobs = @()
    foreach ($id in @('window-0112-forward-00002', 'window-0082-forward-00002')) {
        $poses = @($NetworkPlan.frames | Where-Object { $_.frame_id -ceq $id })
        if ($poses.Count -ne 1) { throw 'Crack source camera is missing or repeated in the original view plan.' }
        foreach ($mode in @('base-basecolor', 'neutral-basecolor', 'base-roughness', 'neutral-roughness',
                            'base-worldnormal', 'neutral-worldnormal', 'cracks-lit', 'cracks-worldnormal')) {
            $jobs += @{ job_id = $id + '--' + $mode; control = $mode; camera = $poses[0] }
        }
    }
    $plan = @{ schema_version = 1
        network_plan_sha256 = '4bfb1aa75201863bf854a15d7bbc1691fc42765e694a22621b28f64fb9e72d75'
        survey_sha256 = $NetworkPlan.survey_sha256; resolution = @(1280, 720)
        priming_captures_per_condition = 3; frame_count = 16; jobs = $jobs
        owner_visual_pass = $false; performance_pass = $false }
    Assert-JsonEqual $plan $Expected.control_plan 'exact crack source cameras and condition order'
}

function Get-CrackControlTargets {
    param($Manifest)
    $map = '/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview'
    if ($Manifest.map_package -cne $map -or $Manifest.crack_canary.actors.Count -ne 2) {
        throw 'Crack control target world or actor inventory differs.'
    }
    $world = $map + '.L_SaCalobraRoadAsphaltReview'
    $targets = @()
    $motifs = @('drifting_interrupted', 'short_oblique')
    $labels = @('YACS_ROAD_CRACK_CANARY_ordinary_0112', 'YACS_ROAD_CRACK_CANARY_nudo_0082')
    for ($index = 0; $index -lt 2; $index++) {
        $motif = $motifs[$index]
        $row = $Manifest.crack_canary.actors[$index]
        $material = $Manifest.crack_canary.material.assets[$motif].instance
        $rotation = @(0.0, 90.0)[$index]
        if ($row.motif_id -cne $motif -or $row.label -cne $labels[$index] -or
            $row.actor.path -cnotmatch '^<scene>\.<world>:PersistentLevel\.[^:/]+$' -or
            -not $row.component.StartsWith(($row.actor.path + '.'), [StringComparison]::Ordinal) -or
            $row.material -cne $material -or
            $material -cnotmatch ('^/Game/Generated/YACS/RoadAsphaltConsumer/CrackLayer/[0-9a-f]{12}/MI_RoadCracks_' +
                                  $motif + '\.MI_RoadCracks_' + $motif + '$')) {
            throw 'Crack target is not one of the exact saved source-clipped components and MICs.'
        }
        Assert-JsonEqual $rotation $Manifest.crack_canary.geometry_contracts[$motif].uv_rotation_degrees 'saved crack UV frame'
        $targets += @{ motif_id = $motif; label = $row.label; material = $material; uv_rotation_degrees = $rotation
            actor = $row.actor.path.Replace('<scene>.<world>', $world)
            component = $row.component.Replace('<scene>.<world>', $world) }
    }
    if ($targets[0].actor -ceq $targets[1].actor -or $targets[0].component -ceq $targets[1].component) {
        throw 'Crack controls cannot share an actor or component.'
    }
    return ,$targets
}

function Assert-CrackVisualControlObservation {
    param($Observed, [string] $Control, $Targets, $Mids)
    $buffer = switch -CaseSensitive ($Control) {
        { $_ -cin @('base-basecolor', 'neutral-basecolor') } { 'BaseColor' }
        { $_ -cin @('base-roughness', 'neutral-roughness') } { 'Roughness' }
        { $_ -cin @('base-worldnormal', 'neutral-worldnormal', 'cracks-worldnormal') } { 'WorldNormal' }
        'cracks-lit' { $null }
        default { throw 'Unsupported crack visual condition.' }
    }
    $neutral = $Control.StartsWith('neutral-', [StringComparison]::Ordinal)
    $visible = -not $Control.StartsWith('base-', [StringComparison]::Ordinal)
    $actors = @()
    foreach ($target in $Targets) {
        $actors += @{ motif_id = $target.motif_id; label = $target.label; actor = $target.actor; component = $target.component
            material_readback = $(if ($neutral) { $Mids[$target.motif_id].path } else { $target.material })
            material_kind = $(if ($neutral) { 'transient_mid' } else { 'original_mic' })
            visible_readback = $visible; neutral_probe_readback = $(if ($neutral) { 1.0 } else { 0.0 })
            original_mic_probe_readback = 0.0; transient_mid_parent_readback = $target.material
            uv_rotation_degrees = $target.uv_rotation_degrees }
    }
    $expected = @{ control = $Control; requested_buffer = $buffer
        active_viewmode_readback = $(if ($null -eq $buffer) { 'VMI_LIT' } else { 'VMI_VISUALIZE_BUFFER' })
        buffer_name_readback_verified = $false; crack_actors = $actors
        dirty_content_count = 0; normal_space_verified = $false }
    $actual = [ordered]@{}
    foreach ($key in $Observed.Keys) { if ($key -cne 'job_id') { $actual[$key] = $Observed[$key] } }
    Assert-JsonEqual $expected $actual 'native crack condition, both components, probes and UV frames'
}

function Assert-CrackControlApi {
    param($Api)
    if ($Api.engine_version -cne '5.8.2-56702186+++UE5+Release-5.8' -or
        $Api.mid_creation_flags_argument -cne 'MIDCreationFlags.TRANSIENT' -or
        $Api.installed_sources.Count -ne 3 -or $Api.crack_sources.Count -ne 4 -or
        $Api.configured_buffers.Count -ne 2 -or $Api.transient_allocator.Count -ne 1) {
        throw 'Crack control engine/API inventory differs from the bounded native implementation.'
    }
    foreach ($name in @('engine_source_redistributed', 'buffer_name_getter_available',
                         'native_object_flags_readback_verified', 'normal_space_verified')) {
        Assert-JsonEqual $false $Api[$name] ('unclaimed native API capability ' + $name)
    }
    Assert-JsonEqual $true $Api.rf_transient_set_by_installed_allocator 'installed RF_Transient allocator'
    Assert-JsonEqual @('ChangeBufferVisualizationMode') $Api.buffer_argument_forwarding_calls 'installed buffer forwarding'
    foreach ($value in @($Api.buffer_setter_body_sha256, $Api.mid_allocator_body_sha256,
                          $Api.mid_scalar_getter_body_sha256, $Api.roughness_buffer.entry_sha256,
                          $Api.configured_buffers.BaseColor.entry_sha256, $Api.configured_buffers.WorldNormal.entry_sha256)) {
        if ($value -isnot [string] -or $value -cnotmatch '^[0-9a-f]{64}$') { throw 'Unpinned installed control function/configuration.' }
    }
    $installed = @('Source/Developer/FunctionalTesting/Private/AutomationBlueprintFunctionLibrary.cpp',
                   'Source/Developer/FunctionalTesting/Public/AutomationBlueprintFunctionLibrary.h', 'Config/BaseEngine.ini')
    foreach ($relative in $installed) {
        if (-not $Api.installed_sources.Contains($relative)) { throw 'Missing installed viewport source.' }
    }
    $crackSourceNames = @($Api.crack_sources.Keys)
    foreach ($relative in @('Source/Runtime/Engine/Private/KismetMaterialLibrary.cpp',
                            'Source/Runtime/Engine/Private/Materials/MaterialInstanceDynamic.cpp')) {
        if ($crackSourceNames -cnotcontains $relative) { throw 'Missing installed transient MID implementation.' }
    }
    foreach ($stem in @('Kismet/KismetMaterialLibrary', 'Materials/MaterialInstanceDynamic')) {
        if (@($crackSourceNames | Where-Object { $_ -cmatch ('^Source/Runtime/Engine/(Public|Classes)/' + $stem + '\.h$') }).Count -ne 1) {
            throw 'Installed MID header is missing, ambiguous or outside the bounded source roots.'
        }
    }
    Assert-JsonEqual $Api.installed_sources['Config/BaseEngine.ini'] $Api.roughness_buffer.config 'Roughness configuration bytes'
    $allocator = 'Source/YetAnotherCyclingSimEditor/Private/Diagnostics/YacsComponent230Detail.cpp'
    if (-not $Api.transient_allocator.Contains($allocator)) { throw 'Existing transient allocator identity is missing.' }
    foreach ($inventory in @($Api.installed_sources, $Api.crack_sources, $Api.transient_allocator)) {
        foreach ($row in $inventory.Values) {
            if ($row.sha256 -cnotmatch '^[0-9a-f]{64}$' -or $row.size_bytes -le 0 -or $row.size_bytes -gt 4MB) {
                throw 'Installed control source identity is unbounded or missing.'
            }
        }
    }
    $methods = @('MaterialLibrary.create_dynamic_material_instance',
        'MaterialInstanceDynamic.get_scalar_parameter_value', 'MaterialInstanceDynamic.set_scalar_parameter_value',
        'MaterialEditingLibrary.get_material_instance_scalar_parameter_value', 'DynamicMeshComponent.set_material',
        'DynamicMeshComponent.get_material', 'DynamicMeshComponent.get_num_materials', 'DynamicMeshComponent.set_visibility',
        'EditorLoadingAndSavingUtils.get_dirty_content_packages')
    if ($Api.crack_reflected_methods.Count -ne $methods.Count) { throw 'Crack reflected method inventory differs.' }
    foreach ($name in $methods) {
        $row = $Api.crack_reflected_methods[$name]
        if ($null -eq $row -or $row.signature -isnot [string] -or $row.signature.Length -eq 0 -or
            $row.signature.Length -gt 32768 -or $row.doc_sha256 -cnotmatch '^[0-9a-f]{64}$') {
            throw 'Crack native method signature/hash is missing.'
        }
    }
}

function Assert-CrackVisualControlContract {
    param($Data, $Expected, [string] $ViewPlanSha, [string] $ManifestSha, $LitIdentity,
          $Manifest, [long] $EditorPid, [string] $ProjectRoot, [string] $ExactHead, [string] $Token, $NetworkPlan)
    Assert-CrackControlPlan $Expected $NetworkPlan
    $plan = $Expected.control_plan
    if ($Data.schema_version -ne 1 -or $Data.issue -ne 364 -or
        $Data.status -cne 'ROAD_CRACK_VISUAL_CONTROLS_FRAMES_RETAINED' -or
        $Data.exact_sha -cne $ExactHead -or $Data.run_token -cne $Token -or
        $Data.map_package -cne $Manifest.map_package -or $Data.saved_manifest_sha256 -cne $ManifestSha -or
        $Data.view_plan_sha256 -cne $ViewPlanSha -or $Data.camera_csv_sha256 -cne $plan.survey_sha256 -or
        $Data.control_plan_sha256 -cne $Expected.sha256 -or
        $Data.lit_review_receipt.file -cne 'road-asphalt-lit-review.json' -or
        $Data.lit_review_receipt.sha256 -cne $LitIdentity.sha256 -or
        $Data.lit_review_receipt.size_bytes -ne $LitIdentity.size_bytes -or
        $Data.frame_count -ne 16 -or $Data.expected_frame_count -ne 16 -or
        $Data.frames -isnot [Collections.IList] -or $Data.frames.Count -ne 16 -or
        $Data.priming_frames_per_pose -ne 3 -or $Data.completed_priming_frames -ne 48 -or
        $Data.total_deadline_seconds_shared_with_lit -ne 1080 -or $Data.frame_deadline_seconds -ne 180 -or
        $Data.owner_visual_status -cne 'PENDING_FINAL_M3' -or $Data.performance_status -cne 'DEFERRED_AFTER_M3' -or
        $Data.errors -isnot [Collections.IList] -or $Data.errors.Count -ne 0) {
        throw 'Crack controls differ from the owned process, exact plan, saved consumer or original Lit receipt.'
    }
    Assert-JsonEqual $true $Manifest.crack_canary_enabled 'saved crack control lane'
    Assert-JsonEqual $true $Manifest.edge_markings_enabled 'saved white control lane'
    Assert-JsonEqual $plan $Data.control_plan 'retained exact sixteen-condition plan'
    foreach ($flag in @('control_restoration_verified', 'capture_readiness_verified', 'native_control_observations_verified',
                        'sources_and_saved_assets_unchanged', 'world_normal_canary_required')) {
        Assert-JsonEqual $true $Data[$flag] ('crack control evidence ' + $flag)
    }
    foreach ($flag in @('native_channel_images_reviewed', 'buffer_name_readback_verified', 'geometry_or_source_texture_change',
                        'map_saved', 'source_assets_saved', 'whole_area_visual_admitted', 'normal_space_verified', 'performance_pass')) {
        Assert-JsonEqual $false $Data[$flag] ('crack control authority ' + $flag)
    }
    $begin, $restored = $Data.begin, $Data.restore
    if ($begin.status -cne 'READY' -or $restored.status -cne 'RESTORED' -or
        $begin.applied_jobs.Count -ne 0 -or $restored.applied_jobs.Count -ne 16 -or
        $begin.cleanup_errors.Count -ne 0 -or $restored.cleanup_errors.Count -ne 0 -or
        $EditorPid -le 0 -or $begin.ownership.pid -ne $EditorPid -or
        $begin.ownership.run_token -cne $Token -or $begin.ownership.consumer_exact_sha -cne $ExactHead -or
        $begin.ownership.map_package -cne $Manifest.map_package -or
        -not [string]::Equals([IO.Path]::GetFullPath($begin.ownership.project), [IO.Path]::GetFullPath($ProjectRoot),
                             [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Crack process ownership, condition inventory or restoration is incomplete.'
    }
    Assert-JsonEqual $true $begin.ownership.owned_process_marker_verified 'owned crack process marker'
    Assert-JsonEqual $true $begin.ownership.host_idle_arbitration_required 'owned host arbitration'
    Assert-JsonEqual $EditorPid $begin.ownership.pid 'owned native crack PID'
    foreach ($key in @('ownership', 'native_api')) {
        Assert-JsonEqual $Data.preflight[$key] $begin[$key] ('crack preflight ' + $key)
        Assert-JsonEqual $begin[$key] $restored[$key] ('crack restoration ' + $key)
    }
    Assert-CrackControlApi $begin.native_api
    foreach ($report in @($begin, $restored)) {
        Assert-JsonEqual 1 $report.schema_version 'crack controller schema'
        Assert-JsonEqual 'road-crack' $report.family 'crack controller family'
        Assert-JsonEqual $Expected.sha256 $report.plan_sha256 'crack controller plan'
        Assert-JsonEqual 0 $report.dirty_content_count 'crack zero dirty content'
        Assert-JsonEqual 'owned_editor_establish_Lit_and_restore_Lit' $report.view_state_contract 'owned viewport contract'
        foreach ($flag in @('whole_native_scene_audit_owned_by_host', 'world_normal_canary_required')) {
            Assert-JsonEqual $true $report[$flag] ('crack controller requirement ' + $flag)
        }
        foreach ($flag in @('source_assets_saved', 'map_saved', 'saved_material_parameters_changed', 'geometry_buffers_modified',
                            'buffer_name_getter_available', 'capture_count_verified', 'normal_space_verified',
                            'owner_visual_pass', 'performance_pass')) {
            Assert-JsonEqual $false $report[$flag] ('crack controller authority ' + $flag)
        }
    }
    foreach ($flag in @('original_material_restored', 'original_visibility_restored', 'original_mic_probe_values_zero',
                        'transient_mids_detached', 'transient_mid_refs_released', 'owned_viewports_returned_to_lit',
                        'saved_and_staged_package_bytes_unchanged')) {
        Assert-JsonEqual $true $restored[$flag] ('crack restoration ' + $flag)
    }
    $targets = Get-CrackControlTargets $Manifest
    $originals, $visibility = @{}, @{}
    if ($begin.transient_mids.Count -ne 2) { throw 'Two transient crack MIDs are required.' }
    $midPaths = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    $calls = [Collections.Generic.List[object]]::new()
    $calls.Add(@{ function = 'AutomationLibrary.set_editor_viewport_view_mode'; argument = 'VMI_LIT' })
    foreach ($target in $targets) {
        $motif = $target.motif_id
        $originals[$motif], $visibility[$motif] = $target.material, $true
        $mid = $begin.transient_mids[$motif]
        if ($mid.path -isnot [string] -or $mid.path.Length -eq 0 -or $mid.path.Length -gt 2048 -or
            $mid.path -match '[\x00\r\n]' -or $mid.path -cin @($targets.material) -or -not $midPaths.Add($mid.path) -or
            $mid.parent -cne $target.material -or $mid.creation_flags -cne 'TRANSIENT') {
            throw 'Transient MID paths, parents or explicit creation flags differ.'
        }
        Assert-JsonEqual 1.0 $mid.probe_value 'transient MID probe'
        $calls.Add(@{ function = 'MaterialLibrary.create_dynamic_material_instance'; motif_id = $motif
                       parent = $target.material; creation_flags = 'MIDCreationFlags.TRANSIENT' })
        $calls.Add(@{ function = 'MaterialInstanceDynamic.set_scalar_parameter_value'; material = $mid.path
                       parameter = 'NeutralProbe'; value = 1.0 })
    }
    Assert-JsonEqual $originals $begin.original_materials 'saved crack MICs'
    Assert-JsonEqual $visibility $begin.original_visibility 'saved crack visibility'
    foreach ($key in @('original_materials', 'original_visibility', 'transient_mids')) {
        Assert-JsonEqual $begin[$key] $restored[$key] ('restored crack identity ' + $key)
    }
    Assert-JsonEqual $calls.ToArray() $begin.calls 'native crack begin calls'
    $maximumElapsed = 0.0
    for ($index = 0; $index -lt 16; $index++) {
        $job, $frame = $plan.jobs[$index], $Data.frames[$index]
        $pose = $job.camera
        $actualPose = [ordered]@{}
        foreach ($key in $pose.Keys) {
            $actualPose[$key] = if ($key -ceq 'frame_id') { $frame.source_frame_id } else { $frame[$key] }
        }
        Assert-JsonEqual $pose $actualPose ('crack camera metadata ' + $index)
        $renderMode = if ($job.control -ceq 'cracks-lit') { 'lit' } else { 'buffer_visualization' }
        if ($frame.frame_id -cne $job.job_id -or $frame.control_mode -cne $job.control -or
            $frame.file -cne ('road-crack-visual-controls/frames/' + $job.job_id + '.png') -or
            $frame.width -ne 1280 -or $frame.height -ne 720 -or $frame.unique_sampled_rgb -lt 12 -or
            $frame.render_mode -cne $renderMode -or $restored.applied_jobs[$index].job_id -cne $job.job_id -or
            $frame.priming_frames -isnot [Collections.IList] -or $frame.priming_frames.Count -ne 3) {
            throw 'Crack control frame order, content or mode differs.'
        }
        Assert-JsonEqual $false $frame.visual_quality_reviewed 'unreviewed crack image'
        Assert-CrackVisualControlObservation $restored.applied_jobs[$index] $job.control $targets $begin.transient_mids
        foreach ($capture in (@($frame) + @($frame.priming_frames))) {
            if ($capture.sha256 -cnotmatch '^[0-9a-f]{64}$' -or $capture.size_bytes -le 0 -or $capture.size_bytes -gt 16MB -or
                ($capture.screenshot_elapsed_seconds -isnot [double] -and $capture.screenshot_elapsed_seconds -isnot [long] -and
                 $capture.screenshot_elapsed_seconds -isnot [int]) -or
                -not [double]::IsFinite($capture.screenshot_elapsed_seconds) -or
                $capture.screenshot_elapsed_seconds -lt 0 -or $capture.screenshot_elapsed_seconds -gt 180) {
                throw 'Crack PNG identity or completed screenshot deadline is invalid.'
            }
            $maximumElapsed = [math]::Max($maximumElapsed, $capture.screenshot_elapsed_seconds)
            $viewmode = if ($renderMode -ceq 'lit') { 'VMI_LIT' } else { 'VMI_VISUALIZE_BUFFER' }
            Assert-JsonEqual $viewmode $capture.native_viewmode_before 'native crack viewmode before'
            Assert-JsonEqual $viewmode $capture.native_viewmode_after 'native crack viewmode after'
            Assert-NativeCameraObservation $pose $capture.native_camera_observation
            foreach ($phase in @('before', 'after')) {
                Assert-CrackVisualControlObservation $capture[('native_control_observation_' + $phase)] `
                    $job.control $targets $begin.transient_mids
            }
        }
        for ($prime = 0; $prime -lt 3; $prime++) {
            if ($frame.priming_frames[$prime].file -cne ('road-crack-visual-controls/priming/' + $job.job_id + ('-{0:d2}.png' -f $prime))) {
                throw 'Crack priming file differs from the exact sequence.'
            }
        }
        $ready = $frame.capture_readiness
        Assert-JsonEqual 'NATIVE_LOADING_AND_MIPS_READY' $ready.status 'crack loading barrier'
        Assert-JsonEqual $true $ready.height_mip_lease_requested 'crack height residency'
        Assert-JsonEqual $true $ready.viewport_primed_at_rider_camera 'crack rider viewport priming'
        Assert-JsonEqual 15 $ready.material_texture_count 'crack plus base/shoulder texture residency'
        $observed = $frame.native_control_observation_after
        foreach ($actor in $observed.crack_actors) {
            $calls.Add(@{ function = 'crack_component.set_material'; component = $actor.component
                           slot = 0; material = $actor.material_readback })
            $calls.Add(@{ function = 'crack_component.set_visibility'; component = $actor.component
                           visible = $actor.visible_readback; propagate_to_children = $false })
        }
        $calls.Add(@{ function = $(if ($renderMode -ceq 'lit') { 'AutomationLibrary.set_editor_viewport_view_mode' }
                                   else { 'AutomationLibrary.set_editor_viewport_visualize_buffer' })
                      argument = $(if ($renderMode -ceq 'lit') { 'VMI_LIT' } else { $observed.requested_buffer }) })
    }
    foreach ($target in $targets) {
        $calls.Add(@{ function = 'crack_component.set_material'; phase = 'restore'; component = $target.component
                       slot = 0; material = $target.material })
        $calls.Add(@{ function = 'crack_component.set_visibility'; phase = 'restore'; component = $target.component
                       visible = $true; propagate_to_children = $false })
    }
    $calls.Add(@{ function = 'AutomationLibrary.set_editor_viewport_view_mode'; argument = 'VMI_LIT' })
    Assert-JsonEqual $calls.ToArray() $restored.calls 'complete bounded native crack calls'
    Assert-JsonEqual $maximumElapsed $Data.max_completed_screenshot_seconds 'observed crack screenshot completion bound'
}

function Assert-CrackTextureReadiness {
    param($Data, $Manifest)
    $paths = @{}
    Assert-JsonEqual @('BaseColor', 'DetailMasks', 'Normal_DX', 'ORM') @($Manifest.texture_objects.Keys | Sort-Object) 'base channels'
    foreach ($channel in $Manifest.texture_objects.Keys) { $paths[$channel] = $Manifest.texture_objects[$channel] }
    $shoulder = $Manifest.shoulder_network.material.texture_objects
    Assert-JsonEqual @('BaseColor', 'Normal_DX', 'Roughness') @($shoulder.Keys | Sort-Object) 'shoulder channels'
    foreach ($channel in $shoulder.Keys) { $paths[('Shoulder_' + $channel)] = $shoulder[$channel] }
    $cracks = $Manifest.crack_canary.imports.assets.textures
    Assert-JsonEqual @('drifting_interrupted', 'short_oblique') @($cracks.Keys | Sort-Object) 'crack residency motifs'
    foreach ($motif in $cracks.Keys) {
        Assert-JsonEqual @('BaseColor', 'DetailMasks', 'Normal_DX', 'ORM') @($cracks[$motif].Keys | Sort-Object) 'crack residency channels'
        foreach ($channel in $cracks[$motif].Keys) { $paths[('Crack_' + $motif + '_' + $channel)] = $cracks[$motif][$channel] }
    }
    $names = [string[]]@($paths.Keys)
    [Array]::Sort($names, [StringComparer]::Ordinal)
    $unique = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    if ($Data.status -cne 'ROAD_TEXTURE_MIPS_READY' -or $Data.textures -isnot [Collections.IList] -or
        $Data.textures.Count -ne 15 -or $paths.Count -ne 15) { throw 'Crack captures require the exact fifteen material textures.' }
    Assert-JsonEqual $false $Data.material_parameters_changed 'texture readiness parameter changes'
    Assert-JsonEqual $false $Data.saved_to_map 'texture readiness map save'
    for ($index = 0; $index -lt $names.Count; $index++) {
        $row = $Data.textures[$index]
        if ($row.channel -cne $names[$index] -or $row.asset -cne $paths[$names[$index]] -or
            -not $unique.Add($row.asset)) { throw 'Native readiness changed, repeated or omitted a pinned crack/base texture.' }
        $native = $row.native_readback
        Assert-JsonEqual $false $native.is_default_texture 'native non-default texture'
        Assert-JsonEqual $false $native.is_compiling 'native completed texture compile'
        if (($native.mips -isnot [int] -and $native.mips -isnot [long]) -or $native.mips -le 0) {
            throw 'Native texture mip inventory is invalid.'
        }
        Assert-JsonEqual $native.mips $native.resident_mips 'native full material mip residency'
    }
}

function Get-CrackVisualControlArtifacts {
    param($Data, [string] $Proof, $Manifest, [string] $EngineRoot, [string] $ProjectRoot)
    $evidence = [ordered]@{}
    foreach ($frame in $Data.frames) {
        foreach ($capture in (@($frame) + @($frame.priming_frames))) {
            $file = File-Identity (Join-Path $Proof $capture.file) 16MB
            if ($file.sha256 -cne $capture.sha256 -or $file.size_bytes -ne $capture.size_bytes) {
                throw ('Crack control PNG changed: ' + $capture.file)
            }
            $evidence[('crack-control-' + $capture.file)] = $file
        }
        $directory = Join-Path $Proof ('road-crack-visual-controls/readiness/' + $frame.frame_id)
        $height = File-Identity (Join-Path $directory 'capture-readiness.json') 8MB
        $material = Read-PinnedJson (Join-Path $directory 'road-texture-readiness.json')
        if ($height.sha256 -cne $frame.capture_readiness.height_receipt.sha256 -or
            $height.size_bytes -ne $frame.capture_readiness.height_receipt.size_bytes -or
            $material.identity.sha256 -cne $frame.capture_readiness.material_receipt.sha256 -or
            $material.identity.size_bytes -ne $frame.capture_readiness.material_receipt.size_bytes) {
            throw 'Crack material/height readiness sidecar bytes changed.'
        }
        Assert-CrackTextureReadiness $material.value $Manifest
        $evidence[('crack-control-' + $frame.frame_id + '-height-readiness')] = $height
        $evidence[('crack-control-' + $frame.frame_id + '-material-readiness')] = $material.identity
    }
    Assert-CrackControlApi $Data.begin.native_api
    foreach ($key in @('installed_sources', 'crack_sources', 'transient_allocator')) {
        $sourceRoot = if ($key -ceq 'transient_allocator') { $ProjectRoot } else { $EngineRoot }
        foreach ($relative in $Data.begin.native_api[$key].Keys) {
            $pin = $Data.begin.native_api[$key][$relative]
            $actual = File-Identity (Join-Path $sourceRoot $relative) 4MB
            if ($actual.sha256 -cne $pin.sha256 -or $actual.size_bytes -ne $pin.size_bytes) {
                throw ('Installed crack control API/configuration changed: ' + $relative)
            }
            $evidence[('crack-control-api-' + $relative)] = $actual
        }
    }
    return $evidence
}

function Assert-GpuReviewContract {
    param($Data, $Plan, [string] $PlanSha, [string] $ManifestSha,
          [long] $SelectedTriangles, [string] $ExactHead, [string] $Token, [string] $ProfileSha,
          [ValidateSet(7, 15)][int] $ExpectedMaterialTextures = 7)
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
        shoulder_material_edge_uv_verified = $true
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
        foreach ($capture in (@($frame) + @($frame.priming_frames))) {
            Assert-JsonEqual 'VMI_LIT' $capture.native_viewmode_before 'native Lit viewmode before'
            Assert-JsonEqual 'VMI_LIT' $capture.native_viewmode_after 'native Lit viewmode after'
        }
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
            $ready.material_texture_count -ne $ExpectedMaterialTextures) {
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
        'scripts/ue/road_shoulder_edges.py',
        'scripts/ue/road_material_views.py',
        'scripts/ue/road_shoulder_material.py',
        'scripts/ue/road_edge_marking_geometry.py',
        'scripts/ue/road_edge_marking_material.py',
        'scripts/ue/road_edge_marking_consumer.py',
        'scripts/ue/road_pavement_source_bindings.py',
        'scripts/ue/road_asphalt_visual_controls.py',
        'scripts/ue/road_crack_sources.py',
        'scripts/ue/road_crack_material.py',
        'scripts/ue/road_crack_geometry.py',
        'scripts/ue/road_crack_consumer.py',
        'scripts/ue/road_crack_visual_controls.py',
        'Source/YetAnotherCyclingSimEditor/Public/Diagnostics/YacsRoadMaterialInspectionLibrary.h',
        'Source/YetAnotherCyclingSimEditor/Private/Diagnostics/YacsRoadMaterialInspectionLibrary.cpp',
        'Source/YetAnotherCyclingSimEditor/Private/Diagnostics/YacsComponent230Detail.cpp',
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
    Assert-SurfaceDetailLanes $savedHost.value $savedReceipt.value $reopenReceipt.value `
        $savedManifest.value ([bool]$EdgeMarkings) ([bool]$CrackCanary)
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
        $reopenReceipt.value.shoulder_positions_indices_normals_original_uv_prefix_unchanged -isnot [bool] -or
        -not $reopenReceipt.value.shoulder_positions_indices_normals_original_uv_prefix_unchanged -or
        $reopenReceipt.value.shoulder_material_edge_uv_fresh_reload_verified -isnot [bool] -or
        -not $reopenReceipt.value.shoulder_material_edge_uv_fresh_reload_verified -or
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
    if ($VisualControls) {
        $controlCode = @'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from scripts.ue.road_asphalt_visual_controls import control_plan, digest
plan = control_plan(Path(sys.argv[1]))
print(json.dumps({"control_plan": plan, "sha256": digest(plan)}, sort_keys=True, allow_nan=False))
'@
        $controlOutput = @(& $planPython.path -I -B -c $controlCode $root)
        if ($LASTEXITCODE -ne 0 -or $controlOutput.Count -ne 1) {
            throw 'Cannot derive the eight visual controls before starting the owned Editor.'
        }
        $controlValue = $controlOutput[0] | ConvertFrom-Json -AsHashtable -Depth 40
        if ($controlValue.sha256 -cnotmatch '^[0-9a-f]{64}$' -or
            $controlValue.control_plan.frame_count -ne 8 -or $controlValue.control_plan.jobs.Count -ne 8) {
            throw 'Visual control plan has an unexpected identity or scope.'
        }
        $controlPlanPath = Join-Path $proof 'road-asphalt-expected-visual-controls.json'
        Write-ExclusiveReceipt $controlPlanPath $controlValue
        $expectedControls = Read-PinnedJson $controlPlanPath
        Assert-JsonEqual $controlValue $expectedControls.value 'retained visual control plan'
        $receipt.expected_visual_control_plan = $expectedControls.identity
    }
    if ($CrackCanary) {
        $crackControlCode = @'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from scripts.ue.road_crack_visual_controls import control_plan, digest
plan = control_plan(Path(sys.argv[1]))
print(json.dumps({"control_plan": plan, "sha256": digest(plan)}, sort_keys=True, allow_nan=False))
'@
        $crackControlOutput = @(& $planPython.path -I -B -c $crackControlCode $root)
        if ($LASTEXITCODE -ne 0 -or $crackControlOutput.Count -ne 1) {
            throw 'Cannot derive the sixteen crack controls before starting the owned Editor.'
        }
        $crackControlValue = $crackControlOutput[0] | ConvertFrom-Json -AsHashtable -Depth 40
        Assert-CrackControlPlan $crackControlValue $expectedPlan.value
        $crackControlPlanPath = Join-Path $proof 'road-crack-expected-visual-controls.json'
        Write-ExclusiveReceipt $crackControlPlanPath $crackControlValue
        $expectedCrackControls = Read-PinnedJson $crackControlPlanPath
        Assert-JsonEqual $crackControlValue $expectedCrackControls.value 'retained crack control plan'
        $receipt.expected_crack_visual_control_plan = $expectedCrackControls.identity
    }
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
            YACS_ROAD_EDGE_MARKINGS = $edgeMarkingSetting
            YACS_ROAD_VISUAL_CONTROLS_OWNED = $visualControlToken
            YACS_ROAD_CRACK_CANARY = $crackCanarySetting
            YACS_ROAD_CRACK_CONTROLS_OWNED = $crackControlToken
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
        $savedManifest.identity.sha256 $selectedTriangles $ExpectedHead $RunToken $profileCopies.proof.sha256 `
        $expectedMaterialTextureCount
    Assert-SurfaceDetailGpuReadback $data $reopenReceipt.value ([bool]$EdgeMarkings) ([bool]$CrackCanary)
    $receipt.edge_markings_verified = [bool]$EdgeMarkings
    $receipt.crack_canary_verified = [bool]$CrackCanary
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
            $materialReady.value.textures.Count -ne $expectedMaterialTextureCount -or
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
        if ($CrackCanary) { Assert-CrackTextureReadiness $materialReady.value $savedManifest.value }
        $receipt.evidence[($expectedIds[$i] + '-height-readiness')] = $heightFile
        $receipt.evidence[($expectedIds[$i] + '-material-readiness')] = $materialReady.identity
    }
    $receipt.evidence.render_receipt = $review.identity
    if ($VisualControls) {
        $controlReceipt = Read-PinnedJson (Join-Path $proof 'road-asphalt-visual-controls.json')
        $controls = $controlReceipt.value
        Assert-VisualControlContract $controls $expectedControls.value $expectedPlan.identity.sha256 `
            $savedManifest.identity.sha256 $review.identity $savedManifest.value.material_instance $ExpectedHead $RunToken
        if ($controls.begin.ownership.pid -ne $receipt.editor_pid) {
            throw 'Visual controls ran in a different process from the owned GPU Editor.'
        }
        foreach ($frame in $controls.frames) {
            foreach ($capture in (@($frame) + @($frame.priming_frames))) {
                $file = File-Identity (Join-Path $proof $capture.file) 16MB
                if ($file.sha256 -cne $capture.sha256 -or $file.size_bytes -ne $capture.size_bytes) {
                    throw ('Visual control PNG changed: ' + $capture.file)
                }
                $receipt.evidence[('control-' + $capture.file)] = $file
            }
            $readinessRoot = Join-Path $proof ('road-asphalt-visual-controls/readiness/' + $frame.frame_id)
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
                throw ('Visual control texture/height readiness changed: ' + $frame.frame_id)
            }
            foreach ($texture in $materialReady.value.textures) {
                $native = $texture.native_readback
                if ($native.is_default_texture -isnot [bool] -or $native.is_default_texture -or
                    $native.is_compiling -isnot [bool] -or $native.is_compiling -or
                    $native.mips -le 0 -or $native.resident_mips -ne $native.mips) {
                    throw ('Visual control texture lacks full native residency: ' + $frame.frame_id)
                }
            }
            $receipt.evidence[('control-' + $frame.frame_id + '-height-readiness')] = $heightFile
            $receipt.evidence[('control-' + $frame.frame_id + '-material-readiness')] = $materialReady.identity
        }
        $engineRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $gui))
        $apiSources = $controls.begin.native_api.installed_sources
        $requiredSources = @(
            'Source/Developer/FunctionalTesting/Private/AutomationBlueprintFunctionLibrary.cpp',
            'Source/Developer/FunctionalTesting/Public/AutomationBlueprintFunctionLibrary.h',
            'Config/BaseEngine.ini'
        )
        if ($apiSources.Count -ne 3) { throw 'Unexpected installed visual control source inventory.' }
        foreach ($relative in $requiredSources) {
            $actual = File-Identity (Join-Path $engineRoot $relative) 4MB
            if ($actual.sha256 -cne $apiSources[$relative].sha256 -or
                $actual.size_bytes -ne $apiSources[$relative].size_bytes) {
                throw ('Installed visual control API/configuration changed: ' + $relative)
            }
            $receipt.evidence[('control-api-' + $relative)] = $actual
        }
        $allocatorPath = 'Source/YetAnotherCyclingSimEditor/Private/Diagnostics/YacsComponent230Detail.cpp'
        $allocator = File-Identity (Join-Path $root $allocatorPath) 4MB
        $allocatorPin = $controls.begin.native_api.transient_allocator[$allocatorPath]
        if ($allocator.sha256 -cne $allocatorPin.sha256 -or $allocator.size_bytes -ne $allocatorPin.size_bytes) {
            throw 'Transient visual-control allocator source changed.'
        }
        Assert-Identity $expectedControls.identity 2MB
        $receipt.evidence.visual_control_receipt = $controlReceipt.identity
        $receipt.evidence.visual_control_allocator = $allocator
        $receipt.visual_controls_frames_retained = $true
        $receipt.visual_control_frame_count = 8
    }
    if ($CrackCanary) {
        $crackControlReceipt = Read-PinnedJson (Join-Path $proof 'road-crack-visual-controls.json')
        $crackControls = $crackControlReceipt.value
        Assert-CrackVisualControlContract $crackControls $expectedCrackControls.value `
            $expectedPlan.identity.sha256 $savedManifest.identity.sha256 $review.identity `
            $savedManifest.value $receipt.editor_pid $root $ExpectedHead $RunToken $expectedPlan.value
        $engineRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $gui))
        $crackEvidence = Get-CrackVisualControlArtifacts $crackControls $proof $savedManifest.value $engineRoot $root
        foreach ($name in $crackEvidence.Keys) { $receipt.evidence[$name] = $crackEvidence[$name] }
        Assert-Identity $crackControlReceipt.identity 2MB
        Assert-Identity $expectedCrackControls.identity 2MB
        $receipt.evidence.crack_visual_control_receipt = $crackControlReceipt.identity
        $receipt.crack_control_frames_retained = $true
        $receipt.crack_control_frame_count = 16
    }
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
    $receipt.shoulder_material_edge_uv_verified = $true
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
            $receipt.shoulder_material_edge_uv_verified = $false
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
    -not $receipt.native_lit_frames_retained -or -not $receipt.shoulder_network_material_ids_verified -or
    -not $receipt.shoulder_material_edge_uv_verified) {
    throw 'Road GPU technical evidence failed the independent native host gate.'
}
if ($CrackCanary -and (-not $receipt.crack_canary_verified -or
    -not $receipt.crack_control_frames_retained -or $receipt.crack_control_frame_count -ne 16)) {
    throw 'Road crack canary lacks all sixteen independently verified control conditions.'
}
Write-Host ('ROAD_ASPHALT_GPU_LIT_REVIEW_HOST_PASS; ' + $receipt.verified_frame_count +
    ' pinned ordered lit road-facing frames, owner visual and FPS pending.')
