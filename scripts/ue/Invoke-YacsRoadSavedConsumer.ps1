#requires -Version 7.4
<# Save only a new #364 road/shoulder material map and verify it in a fresh Editor. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string] $ExpectedHead,
    [Parameter(Mandatory)][ValidatePattern('^[1-9][0-9]{0,19}-[1-9][0-9]{0,5}$')][string] $RunToken,
    [switch] $EdgeMarkings,
    [switch] $CrackCanary,
    [switch] $OuterTerrainCanary,
    [string] $WorkspaceConfig = 'D:\yacs\workspace.json',
    [string] $RepoRoot = (Join-Path $PSScriptRoot '../..')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Saved road asphalt requires the trusted Windows host.' }
if ($CrackCanary -and -not $EdgeMarkings) { throw 'The local crack canary requires the authenticated white edge markings.' }
$PROFILE_DIAGNOSTIC = 'road-network-profile-diagnostic.json'
$root = $null
$evidence = $null
$editor = $null
$edgeMarkingSetting = if ($EdgeMarkings) { '1' } else { '0' }
$crackCanarySetting = if ($CrackCanary) { '1' } else { '0' }
$outerTerrainSetting = if ($OuterTerrainCanary) { '1' } else { '0' }
$receipt = [ordered]@{
    schema_version = 1; issue = 364; exact_sha = $ExpectedHead
    run_token = $RunToken; status = 'PENDING'
    native_baseline_authenticated = $false
    transient_canary_authenticated = $false
    saved_derived_consumer = $false; fresh_reload_verified = $false
    shoulder_network_fresh_reload_verified = $false
    shoulder_support_count = 0; shoulder_material_target_count = 0
    shoulder_selected_triangle_count = 0
    edge_markings_requested = [bool]$EdgeMarkings
    edge_markings_fresh_reload_verified = $false
    crack_canary_requested = [bool]$CrackCanary
    crack_canary_fresh_reload_verified = $false
    crack_normal_space_verified = $false
    outer_terrain_requested = [bool]$OuterTerrainCanary
    outer_terrain_fresh_reload_verified = $false
    outer_terrain_owner_labels = @()
    outer_terrain_physical_contact_verified = $false
    outer_terrain_normal_response_verified = $false
    rendering_mode_requested = $null
    rendering_arguments_requested = @()
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
function Get-SavedEditorLaunch {
    param($Commandlet, [bool] $OuterTerrain)
    if ($Commandlet.path -isnot [string] -or
        -not $Commandlet.path.EndsWith('UnrealEditor-Cmd.exe', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Saved material rendering must derive from the authenticated commandline Editor.'
    }
    if ($OuterTerrain) {
        # The frozen whole-map verifier reads platform texture data. Reuse
        # its proven rendered Editor context, including the existing RHI flag.
        $gui = Join-Path (Split-Path -Parent $Commandlet.path) 'UnrealEditor.exe'
        return [ordered]@{ mode = 'RENDER_OFFSCREEN'; program = (Get-Identity $gui 1GB)
            arguments = @('-RenderOffscreen', '-norhithread', '-NoVSync') }
    }
    return [ordered]@{ mode = 'NULL_RHI'; program = $Commandlet
        arguments = @('-NullRHI') }
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
    param($Manifest, [string] $ExactHead, [bool] $OuterTerrain = $false)
    if ($Manifest -isnot [Collections.IDictionary] -or
        $Manifest.schema_version -ne 1 -or $Manifest.issue -ne 364 -or
        $Manifest.status -cne 'SAVED_ROAD_ASPHALT_CONSUMER_PREPARED' -or
        $Manifest.exact_sha -cne $ExactHead -or
        $Manifest.material_changes -cne 'road_slot_zero_network_outer_shoulder_ids_and_edge_uv' -or
        $Manifest.outer_terrain_enabled -isnot [bool] -or
        $Manifest.outer_terrain_enabled -ne $OuterTerrain) {
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
    $expectedSchema = if ($OuterTerrain) { 4 } else { 3 }
    if ($network -isnot [Collections.IDictionary] -or
        $network.schema_version -ne $expectedSchema -or $network.status -cne 'SHOULDER_NETWORK_PREPARED' -or
        $network.support_count -ne 186 -or $network.material_target_count -ne 185 -or
        $network.excluded_parapet_count -ne 1 -or
        $network.owners -isnot [Collections.IList] -or $network.owners.Count -ne 186) {
        throw 'Saved source-owned support coverage is incomplete.'
    }
    if (-not $OuterTerrain -and $network.Contains('outer_terrain')) {
        throw 'Disabled outer terrain mode contains an unexpected material variant.'
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
        shoulder_positions_indices_normals_original_uv_prefix_unchanged = $true
        shoulder_material_edge_uv_fresh_reload_verified = $true
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
function Assert-OuterTerrainReceipt {
    param($Manifest, $Prepared, $Fresh, [bool] $Requested)
    foreach ($row in @($Manifest, $Prepared, $Fresh)) {
        if ($row.outer_terrain_enabled -isnot [bool] -or $row.outer_terrain_enabled -ne $Requested) {
            throw 'Saved outer terrain variant differs from the explicit host request.'
        }
    }
    foreach ($name in @('outer_material_reapplied', 'outer_geometry_reapplied')) {
        if ($Fresh[$name] -isnot [bool] -or $Fresh[$name]) {
            throw 'Fresh outer terrain verification changed its saved scene.'
        }
    }
    if ($Fresh.outer_terrain_fresh_reload_verified -isnot [bool] -or
        $Fresh.outer_terrain_fresh_reload_verified -ne $Requested) {
        throw 'Fresh outer terrain verification differs from the requested variant.'
    }
    $network = $Manifest.shoulder_network
    if (-not $Requested) {
        if ($network.schema_version -ne 3 -or $network.Contains('outer_terrain') -or
            $null -ne $Fresh.outer_terrain_readback) {
            throw 'Disabled outer terrain mode contains unexpected material or readback evidence.'
        }
        return
    }
    # Retained 4258 camera windows 0013/0071/0097/0112/0082, resolved by
    # window_id and material_target. Camera ordinals are not support indices.
    $labels = @('018', '073', '093', '112', '182' | ForEach-Object { 'YACS_PERSIST_SUPPORT_' + $_ })
    $outer = $network.outer_terrain
    if ($network.schema_version -ne 4 -or $outer -isnot [Collections.IDictionary] -or
        $outer.owner_labels -isnot [Collections.IList] -or
        ($outer.owner_labels -join ',') -cne ($labels -join ',') -or
        $outer.selection -cne 'source_owned_outer_top_faces' -or $outer.uv_channel -ne 1 -or
        $outer.uv0_stage_witness_required -isnot [bool] -or -not $outer.uv0_stage_witness_required -or
        $outer.physical_contact_verified -isnot [bool] -or $outer.physical_contact_verified) {
        throw 'Outer terrain variant escaped the five selected source-owned top surfaces.'
    }
    $material = $outer.material
    $source = $material.terrain_source
    $loaded = $Fresh.outer_terrain_readback
    $prefix = '/Game/Generated/YACS/RoadAsphaltConsumer/ShoulderNetwork/TerrainBlend/'
    $master = $prefix + 'M_ShoulderNetworkTerrain.M_ShoulderNetworkTerrain'
    $instance = $prefix + 'MI_ShoulderNetworkTerrain.MI_ShoulderNetworkTerrain'
    if ($material.schema_version -ne 3 -or
        $material.status -cne 'SHOULDER_MATERIAL_CREATED_REVIEW_PENDING' -or
        $material.outer_terrain_enabled -isnot [bool] -or -not $material.outer_terrain_enabled -or
        $material.assets.master -cne $master -or $material.assets.instance -cne $instance -or
        $source -isnot [Collections.IDictionary] -or $source.landscape_component_count -ne 1024 -or
        $source.texture_objects -isnot [Collections.IDictionary] -or $source.texture_objects.Count -ne 11 -or
        $loaded -isnot [Collections.IDictionary] -or
        $loaded.status -cne 'SHOULDER_MATERIALS_NATIVE_READBACK_VERIFIED' -or
        $loaded.outer_terrain_enabled -isnot [bool] -or -not $loaded.outer_terrain_enabled -or
        $loaded.read_only -isnot [bool] -or -not $loaded.read_only -or
        $loaded.base_instance -cne $network.material.assets.instance -or
        $loaded.outer_instance -cne $instance -or
        $loaded.outer_owner_labels -isnot [Collections.IList] -or
        ($loaded.outer_owner_labels -join ',') -cne ($labels -join ',') -or
        $loaded.landscape_instance -cne $source.instance -or $loaded.landscape_component_count -ne 1024 -or
        $loaded.outer_texture_objects -isnot [Collections.IDictionary] -or
        $loaded.outer_texture_objects.Count -ne 11) {
        throw 'Outer material readback does not match both saved instances and the frozen Landscape.'
    }
    foreach ($name in @('outer_material_reapplied', 'outer_geometry_reapplied', 'outer_gpu_compile_verified', 'physical_contact_verified',
                         'normal_response_visual_verified', 'owner_visual_pass', 'performance_pass')) {
        if ($loaded[$name] -isnot [bool] -or $loaded[$name]) {
            throw ('Outer material readback changed protected authority: ' + $name)
        }
    }
    foreach ($name in $source.texture_objects.Keys) {
        if (-not $loaded.outer_texture_objects.Contains($name) -or
            $source.texture_objects[$name] -isnot [string] -or
            $source.texture_objects[$name] -cnotmatch '^/Game/Generated/YACS/.+\.[^/]+$' -or
            $loaded.outer_texture_objects[$name] -cne $source.texture_objects[$name]) {
            throw 'Fresh outer material changed a frozen Landscape texture binding.'
        }
    }
    $statistics = @('num_samplers', 'num_pixel_shader_instructions', 'num_pixel_texture_samples',
                    'num_vertex_shader_instructions', 'num_vertex_texture_samples', 'num_virtual_texture_samples',
                    'num_uv_scalars', 'num_interpolator_scalars')
    # Save/reload counters remain observations, including zero. Their RHI
    # context is not the separate cold GPU capture/compile proof below.
    foreach ($row in @($material.native_statistics, $loaded.outer_native_statistics)) {
        if ($row -isnot [Collections.IDictionary] -or $row.Count -ne $statistics.Count -or
            $row.num_virtual_texture_samples -ne 0) {
            throw 'Outer material native statistics are incomplete.'
        }
        foreach ($name in $statistics) {
            if (-not $row.Contains($name) -or ($row[$name] -isnot [long] -and $row[$name] -isnot [int]) -or
                $row[$name] -lt 0 -or $row[$name] -gt 1000000) {
                throw 'Outer material native statistics are not bounded integer observations.'
            }
        }
    }
    if ($material.native_compile_errors -isnot [Collections.IList] -or $material.native_compile_errors.Count -ne 0 -or
        $material.unique_texture_objects -ne 17 -or
        $material.gpu_compile_verified -isnot [bool] -or $material.gpu_compile_verified) {
        throw 'Outer material has native compilation errors or a changed texture inventory.'
    }
    if ($network.owners -isnot [Collections.IList] -or $network.owners.Count -ne 186) {
        throw 'Outer material lacks the complete support inventory.'
    }
    for ($index = 0; $index -lt 186; $index++) {
        $owner = $network.owners[$index]
        $label = 'YACS_PERSIST_SUPPORT_' + $index.ToString('D3')
        if ($owner.support_label -cne $label) { throw 'Outer material support inventory is reordered.' }
        $attribute = $owner.edge_attribute
        if ($labels -cnotcontains $label) {
            if ($attribute -is [Collections.IDictionary] -and
                ($attribute.Contains('outer_attribute') -or $attribute.Contains('inner_stage_mesh'))) {
                throw 'Outer UV evidence escaped the five selected owners.'
            }
            continue
        }
        $before = $owner.before_mesh
        $inner = $attribute.inner_stage_mesh
        $after = $owner.after_mesh
        $field = $attribute.outer_attribute
        if ($owner.material_target -isnot [bool] -or -not $owner.material_target -or
            $before.uv_set_count -ne 0 -or $inner.uv_set_count -ne 1 -or $after.uv_set_count -ne 2 -or
            $attribute.channel -ne 0 -or $field.channel -ne 1 -or
            $attribute.uv0_preserved -isnot [bool] -or -not $attribute.uv0_preserved -or
            $attribute.original_normals_uv_prefix_blake3 -cne $before.triangle_corner_normals_uv_blake3 -or
            $field.original_normals_uv_prefix_blake3 -cne $inner.triangle_corner_normals_uv_blake3 -or
            $attribute.set_triangle_count -ne $owner.selected_triangle_count -or
            $field.set_triangle_count -ne $owner.selected_triangle_count -or
            $field.unset_nonselected_triangles -isnot [bool] -or -not $field.unset_nonselected_triangles) {
            throw 'Outer UV source selection or complete original normal/UV prefix chain changed.'
        }
        foreach ($name in @('vertex_count', 'triangle_count', 'positions_indices_blake3')) {
            if ($before[$name] -cne $inner[$name] -or $before[$name] -cne $after[$name]) {
                throw 'Outer material UV creation changed the source positions or topology.'
            }
        }
        foreach ($hash in @($attribute.uv_blake3, $field.uv_blake3,
                             $before.triangle_corner_normals_uv_blake3, $inner.triangle_corner_normals_uv_blake3,
                             $after.triangle_corner_normals_uv_blake3)) {
            if ($hash -isnot [string] -or $hash -cnotmatch '^[0-9a-f]{64}$') {
                throw 'Outer UV proof lacks a complete native buffer hash.'
            }
        }
    }
}
function Assert-EdgeMarkingReceipt {
    param($Manifest, $Prepared, $Fresh, [bool] $Requested)
    foreach ($row in @($Manifest, $Prepared, $Fresh)) {
        if ($row.edge_markings_enabled -isnot [bool] -or
            $row.edge_markings_enabled -ne $Requested) {
            throw 'Saved edge marking lane differs from the explicit host request.'
        }
    }
    foreach ($name in @('edge_marking_material_reapplied', 'edge_marking_geometry_reapplied')) {
        if ($Fresh[$name] -isnot [bool] -or $Fresh[$name]) {
            throw 'Fresh edge marking readback reapplied a material or geometry.'
        }
    }
    if ($Fresh.edge_markings_fresh_reload_verified -isnot [bool] -or
        $Fresh.edge_markings_fresh_reload_verified -ne $Requested) {
        throw 'Fresh edge marking verification differs from the explicit lane.'
    }
    if (-not $Requested) {
        if ($Manifest.Contains('edge_markings') -or $null -ne $Fresh.edge_marking_readback) {
            throw 'Disabled edge marking lane contains unexpected geometry or evidence.'
        }
        return
    }
    $paint = $Manifest.edge_markings
    $loaded = $Fresh.edge_marking_readback
    if ($paint.schema_version -ne 1 -or $paint.status -cne 'EDGE_MARKINGS_CREATED_REVIEW_PENDING' -or
        $paint.plan_sha256 -cnotmatch '^[0-9a-f]{64}$' -or
        $paint.actors -isnot [Collections.IList] -or $paint.actors.Count -ne 370 -or
        $paint.geometry.counts.source_owner_count -ne 186 -or
        $paint.geometry.counts.pavement_owner_count -ne 185 -or
        $paint.geometry.counts.excluded_parapet_count -ne 1 -or
        $paint.geometry.counts.mesh_count -ne 370 -or
        $loaded.schema_version -ne 1 -or $loaded.status -cne 'EDGE_MARKINGS_FRESH_READBACK_VERIFIED' -or
        $loaded.plan_sha256 -cne $paint.plan_sha256 -or $loaded.actor_count -ne 370 -or
        $loaded.normal_contract -cne 'normalized_barycentric_native_road_split_corner_normals' -or
        $loaded.native_source_witness_sha256 -cne $paint.source_correspondence.native_source_witness_sha256) {
        throw 'Saved edge markings lack complete native source and fresh actor correspondence.'
    }
    foreach ($name in @('material_packages_saved', 'render_flags_verified_before_append',
                         'full_source_buffers_preserved', 'native_surface_correspondence_verified',
                         'all_marking_buffers_verified')) {
        if ($paint[$name] -isnot [bool] -or -not $paint[$name]) {
            throw ('Saved edge markings failed native protection: ' + $name)
        }
    }
    foreach ($name in @('source_geometry_changed', 'source_materials_changed', 'collision_enabled',
                         'cast_shadow', 'affects_navigation', 'physics_authored', 'map_saved',
                         'owner_visual_pass', 'performance_pass')) {
        if ($paint[$name] -isnot [bool] -or $paint[$name]) {
            throw ('Saved edge markings changed protected authority: ' + $name)
        }
    }
    foreach ($name in @('all_marking_buffers_verified', 'full_source_buffers_preserved', 'read_only',
                         'caller_fresh_process_and_saved_bytes_required')) {
        if ($loaded[$name] -isnot [bool] -or -not $loaded[$name]) {
            throw ('Fresh edge marking buffer proof failed: ' + $name)
        }
    }
    foreach ($name in @('owner_visual_pass', 'performance_pass')) {
        if ($loaded[$name] -isnot [bool] -or $loaded[$name]) {
            throw 'Native edge marking readback cannot grant owner or performance acceptance.'
        }
    }
}
function Assert-CrackCanaryReceipt {
    param($Manifest, $Prepared, $Fresh, [bool] $Requested)
    foreach ($row in @($Manifest, $Prepared, $Fresh)) {
        if ($row.crack_canary_enabled -isnot [bool] -or $row.crack_canary_enabled -ne $Requested) {
            throw 'Saved crack canary differs from the explicit host request.'
        }
    }
    foreach ($name in @('crack_material_reapplied', 'crack_geometry_reapplied')) {
        if ($Fresh[$name] -isnot [bool] -or $Fresh[$name]) { throw 'Fresh crack readback modified its saved scene.' }
    }
    if ($Fresh.crack_canary_fresh_reload_verified -isnot [bool] -or
        $Fresh.crack_canary_fresh_reload_verified -ne $Requested) { throw 'Fresh crack canary verification differs.' }
    if (-not $Requested) {
        if ($Manifest.Contains('crack_canary') -or $null -ne $Fresh.crack_readback) {
            throw 'Disabled crack canary contains unexpected geometry or evidence.'
        }
        return
    }
    $crack = $Manifest.crack_canary
    $loaded = $Fresh.crack_readback
    if ($crack.schema_version -ne 1 -or $crack.status -cne 'LOCAL_CRACKS_CREATED_NORMAL_REVIEW_PENDING' -or
        $crack.plan_sha256 -cnotmatch '^[0-9a-f]{64}$' -or
        $crack.actors -isnot [Collections.IList] -or $crack.actors.Count -ne 2 -or
        $crack.owned_asset_paths -isnot [Collections.IList] -or $crack.owned_asset_paths.Count -ne 11 -or
        @($crack.owned_asset_paths | Sort-Object -Unique).Count -ne 11 -or
        $crack.imports.texture_count -ne 8 -or
        $crack.imports.sources.status -cne 'ROAD_CRACK_SOURCE_BYTES_AUTHENTICATED' -or
        $crack.imports.sources.verified_map_count -ne 80 -or $crack.imports.sources.verified_process_count -ne 16 -or
        $crack.imports.sources.pins.exact_sha -cne '07ebafad08bce8bc227089901cb46785079fefda' -or
        $crack.imports.sources.pins.run -cne '38102423216' -or $crack.imports.sources.pins.attempt -cne '1' -or
        $crack.imports.sources.pins.source_proof.sha256 -cne 'bdfb2b889a8c8ed48960518909f497d822b5c34e7d4631a890368de984310afb' -or
        $loaded.schema_version -ne 1 -or $loaded.status -cne 'LOCAL_CRACKS_FRESH_READBACK_VERIFIED_NORMAL_REVIEW_PENDING' -or
        $loaded.plan_sha256 -cne $crack.plan_sha256 -or $loaded.actor_count -ne 2 -or
        $loaded.native_source_witness_sha256 -cne $crack.source_correspondence.native_source_witness_sha256 -or
        $Fresh.edge_marking_readback.aggregate_owner -cne 'local_crack_canary') {
        throw 'Crack canary lacks the exact source, native actors, package inventory or aggregate white readback.'
    }
    foreach ($name in @('asset_packages_saved', 'full_source_and_existing_paint_buffers_preserved',
                         'all_crack_buffers_verified', 'native_surface_correspondence_verified',
                         'render_flags_verified_before_append', 'world_normal_canary_required')) {
        if ($crack[$name] -isnot [bool] -or -not $crack[$name]) { throw ('Crack native proof failed: ' + $name) }
    }
    foreach ($name in @('full_source_and_existing_paint_buffers_preserved', 'all_crack_buffers_verified',
                         'read_only', 'caller_fresh_process_and_saved_bytes_required', 'world_normal_canary_required')) {
        if ($loaded[$name] -isnot [bool] -or -not $loaded[$name]) { throw ('Crack fresh proof failed: ' + $name) }
    }
    foreach ($name in @('source_geometry_changed', 'source_materials_changed', 'existing_paint_changed',
                         'collision_enabled', 'cast_shadow', 'affects_navigation', 'physics_authored', 'map_saved',
                         'normal_space_verified', 'owner_visual_pass', 'performance_pass')) {
        if ($crack[$name] -isnot [bool] -or $crack[$name]) { throw ('Crack canary changed protected authority: ' + $name) }
    }
    foreach ($name in @('normal_space_verified', 'owner_visual_pass', 'performance_pass')) {
        if ($loaded[$name] -isnot [bool] -or $loaded[$name]) { throw 'Crack readback cannot grant visual/normal/performance admission.' }
    }
}
function Invoke-OwnedEditor {
    param([string] $Action)
    Require-IdleHost
    Assert-Identity $engine 1GB
    Assert-Identity $launch.program 1GB
    $script = Join-Path $root 'scripts/ue/road_asphalt_saved_consumer.py'
    $arguments = @(('"' + (Join-Path $root 'YetAnotherCyclingSim.uproject') + '"'),
        '/Engine/Maps/Entry', '-DisablePlugins=ModelContextProtocol,Wingman,AndroidFileServer',
        '-Unattended', '-NoPause', '-NoSplash', '-NoSound', '-NoLiveCoding', '-NoP4',
        '-ScriptErrorsAreFatal',
        '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
        ('-ExecutePythonScript="' + $script + '"'),
        ('-AbsLog="' + (Join-Path $evidence ('saved-road-' + $Action + '-editor.log')) + '"')) + @($launch.arguments)
    $streamOut = Join-Path $evidence ('saved-road-' + $Action + '-stdout.log')
    $streamErr = Join-Path $evidence ('saved-road-' + $Action + '-stderr.log')
    foreach ($path in @($streamOut, $streamErr)) {
        Assert-PlainPath $path
        if (Test-Path -LiteralPath $path) {
            throw 'An owned saved road material log already exists.'
        }
    }
    $script:editor = Start-Process -FilePath $launch.program.path -ArgumentList $arguments `
        -WorkingDirectory $root -PassThru -NoNewWindow `
        -RedirectStandardOutput $streamOut -RedirectStandardError $streamErr `
        -Environment @{
            YACS_ROAD_SAVED_ACTION = $Action
            YACS_ROAD_SAVED_RUN_TOKEN = $RunToken
            YACS_ROAD_EDGE_MARKINGS = $edgeMarkingSetting
            YACS_ROAD_CRACK_CANARY = $crackCanarySetting
            YACS_ROAD_OUTER_TERRAIN_CANARY = $outerTerrainSetting
            YACS_ROAD_CRACK_CONTROLS_OWNED = $null
            YACS_ROAD_VISUAL_CONTROLS_OWNED = $null
            YACS_ROAD_PAINT_COVERAGE_OWNED = $null
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
        deadline_seconds = 420; rendering_mode_requested = $launch.mode
        editor_executable_sha256 = $launch.program.sha256 }
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
    Assert-Identity $engine 1GB
    Assert-Identity $launch.program 1GB
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
        'scripts/ue/road_shoulder_edges.py',
        'scripts/ue/road_material_views.py',
        'scripts/ue/road_shoulder_material.py',
        'scripts/ue/build_sa_calobra_whole_map_master.py',
        'scripts/ue/sa_calobra_whole_map_prep.py',
        'scripts/ue/road_edge_marking_geometry.py',
        'scripts/ue/road_edge_marking_material.py',
        'scripts/ue/road_edge_marking_consumer.py',
        'scripts/ue/road_pavement_source_bindings.py',
        'scripts/ue/road_crack_sources.py',
        'scripts/ue/road_crack_material.py',
        'scripts/ue/road_crack_geometry.py',
        'scripts/ue/road_crack_consumer.py',
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
    $launch = Get-SavedEditorLaunch $engine ([bool]$OuterTerrainCanary)
    $receipt.rendering_mode_requested = $launch.mode
    $receipt.rendering_arguments_requested = @($launch.arguments)
    $receipt.proof_files.save_reload_editor_executable = $launch.program
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
    $selectedTriangles = Assert-NetworkManifest $manifest.value $ExpectedHead ([bool]$OuterTerrainCanary)
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
    Assert-EdgeMarkingReceipt $manifest.value $saved.value $fresh.value ([bool]$EdgeMarkings)
    Assert-CrackCanaryReceipt $manifest.value $saved.value $fresh.value ([bool]$CrackCanary)
    Assert-OuterTerrainReceipt $manifest.value $saved.value $fresh.value ([bool]$OuterTerrainCanary)
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
    $receipt.edge_markings_fresh_reload_verified = [bool]$EdgeMarkings
    $receipt.crack_canary_fresh_reload_verified = [bool]$CrackCanary
    $receipt.outer_terrain_fresh_reload_verified = [bool]$OuterTerrainCanary
    if ($OuterTerrainCanary) {
        $receipt.outer_terrain_owner_labels = @($manifest.value.shoulder_network.outer_terrain.owner_labels)
    }
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
        $receipt.outer_terrain_fresh_reload_verified = $false
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
