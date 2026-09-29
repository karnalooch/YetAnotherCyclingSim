<#
.SYNOPSIS
    Render the cyclist-height real-SP638 road-first Landscape-conform proof.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [string] $PreparedWorkspaceStamp,
    [switch] $ValidateOnly,
    [int] $TimeoutSec = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) { $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject' }
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) { $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/CI/Stage3GR4_1/LocalCorridorVisual' }
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) { $ArtifactRoot = Join-Path $RepoRoot $ArtifactRoot }
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$SpikeMapRelative = 'Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap'
$SpikeMapPath = Join-Path $RepoRoot $SpikeMapRelative
$CaptureScript = Join-Path $RepoRoot 'scripts/ue/stage3g_capture_sp638_local_corridor.py'
$CaptureLog = Join-Path $ArtifactRoot 'local_corridor_visual.log'
$CaptureStdout = Join-Path $ArtifactRoot 'local_corridor_visual.stdout.log'
$CaptureErr = $CaptureLog + '.stderr'
$CapturePng = Join-Path $ArtifactRoot 'sp638_local_corridor_rider_3840x2160.png'
$CaptureProof = Join-Path $ArtifactRoot 'local_corridor_visual_proof.json'

if (-not $ValidateOnly) {
    foreach ($Path in @($CaptureLog,$CaptureStdout,$CaptureErr,$CapturePng,$CaptureProof)) {
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    }
}

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) { throw 'SP638 local-corridor visual preflight failed.' }

if (git -C $RepoRoot status --porcelain=v1 --untracked-files=no) {
    throw 'SP638 local-corridor visual checkout has tracked changes before proof.'
}

if ($ValidateOnly) {
    $CaptureExitCode = 0
    Write-Host '[validate-only] Reusing evidence from the single R4.1 editor session.' -ForegroundColor Cyan
}
else {
    $PreparedValidator = Join-Path $RepoRoot 'scripts/ue/Test-YacsR4_1PreparedWorkspace.ps1'
    if ($PreparedWorkspaceStamp) {
        & $PreparedValidator -StampPath $PreparedWorkspaceStamp -RepoRoot $RepoRoot -ExpectedHead $ExpectedHead -RequireMap | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Prepared R4.1 workspace validation failed before local-corridor visual proof.' }
        Write-Host '[1/3] Reusing materialized Passo Giau map from prepared R4.1 workspace.' -ForegroundColor Cyan
    }
    else {
        Write-Host '[1/3] Materializing only the persisted Passo Giau map...' -ForegroundColor Cyan
        git -C $RepoRoot lfs install --local
        if ($LASTEXITCODE -ne 0) { throw 'git lfs install failed.' }
        git -C $RepoRoot lfs pull --include=$SpikeMapRelative --exclude=''
        if ($LASTEXITCODE -ne 0) { throw 'git lfs pull for Passo Giau spike map failed.' }
        if (-not (Test-Path -LiteralPath $SpikeMapPath -PathType Leaf)) {
            throw "Passo Giau map is missing: $SpikeMapPath"
        }
        $MapBytes = (Get-Item -LiteralPath $SpikeMapPath).Length
        if ($MapBytes -lt 100000000) {
            throw "Passo Giau map was not materialized from LFS (bytes=$MapBytes)."
        }
    }
    
    Write-Host '[2/3] Rendering real-SP638 road-first Landscape-conform proof...' -ForegroundColor Cyan
    $UEditor = $Context.UnrealEditorPath
    if (-not $UEditor -or -not (Test-Path -LiteralPath $UEditor)) {
        throw 'UnrealEditor.exe GUI executable is unavailable.'
    }
    if (-not (Test-Path -LiteralPath $CaptureScript -PathType Leaf)) {
        throw "Local corridor visual script is missing: $CaptureScript"
    }
    
    $env:YACS_SP638_LOCAL_CORRIDOR_VISUAL_PNG = $CapturePng
    $env:YACS_SP638_LOCAL_CORRIDOR_VISUAL_PROOF = $CaptureProof
    try {
        $Args = @(
            $ProjectPath,
            ('-ExecutePythonScript="' + $CaptureScript + '"'),
            '-Unattended','-NoPause','-NoSplash','-NoP4',
            '-windowed','-ResX=1920','-ResY=1080','-NoVSync','-FixedSeed',
            '-ScriptErrorsAreFatal','-log','-stdout',('-AbsLog=' + $CaptureLog)
        )
        $Proc = Start-Process -FilePath $UEditor -ArgumentList $Args -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $CaptureStdout -RedirectStandardError $CaptureErr
        if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
            try { $Proc | Stop-Process -Force } catch { }
            throw 'SP638 local-corridor visual capture timed out.'
        }
        $CaptureExitCode = $Proc.ExitCode
    }
    finally {
        Remove-Item Env:YACS_SP638_LOCAL_CORRIDOR_VISUAL_PNG -ErrorAction SilentlyContinue
        Remove-Item Env:YACS_SP638_LOCAL_CORRIDOR_VISUAL_PROOF -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path -LiteralPath $CapturePng -PathType Leaf)) {
    throw "SP638 local-corridor PNG is missing (exit=$CaptureExitCode)."
}
if ((Get-Item -LiteralPath $CapturePng).Length -lt 100000) {
    throw 'SP638 local-corridor PNG is unexpectedly small.'
}
if (-not (Test-Path -LiteralPath $CaptureProof -PathType Leaf)) {
    throw "SP638 local-corridor proof JSON is missing (exit=$CaptureExitCode)."
}

$Proof = Get-Content -LiteralPath $CaptureProof -Raw | ConvertFrom-Json
if ($Proof.sp638_local_corridor_visual -ne 'PASS') {
    throw 'SP638 local-corridor visual proof did not report PASS.'
}
if ([int]$Proof.resolution[0] -ne 3840 -or [int]$Proof.resolution[1] -ne 2160) {
    throw 'SP638 local-corridor proof resolution is invalid.'
}
if ([bool]$Proof.saved_to_map -ne $false -or [bool]$Proof.authoritative_physics -ne $false) {
    throw 'SP638 local-corridor visual proof violated the presentation-only contract.'
}
if ([bool]$Proof.road_xy_snapped_to_terrain_grid -ne $false) {
    throw 'SP638 local-corridor visual proof snapped road XY to terrain.'
}
if ([bool]$Proof.local_geometry.continuous_dynamic_mesh_surfaces -ne $true) {
    throw 'SP638 local-corridor proof did not use continuous DynamicMesh surfaces.'
}
if ([bool]$Proof.local_geometry.box_strip_roadbed -ne $false) {
    throw 'SP638 local-corridor proof regressed to box-strip road geometry.'
}
if ([int]$Proof.station_count -lt 250) {
    throw "SP638 local-corridor proof sampled too few stations: $($Proof.station_count)"
}
if ([bool]$Proof.local_geometry.terrain_owned_by_landscape -ne $true) {
    throw 'SP638 road-first proof did not assign terrain ownership to Landscape.'
}
if ([bool]$Proof.local_geometry.custom_earthwork_mesh -ne $false) {
    throw 'SP638 road-first proof unexpectedly created a continuous custom earthwork mesh.'
}
if ([bool]$Proof.local_geometry.custom_meso_ground_mesh -ne $false) {
    throw 'SP638 road-first proof unexpectedly created a continuous custom meso-ground mesh.'
}
if ([int]$Proof.local_geometry.asphalt.triangles -lt 500) {
    throw 'SP638 road-first asphalt mesh is unexpectedly sparse.'
}
if ([int]$Proof.local_geometry.left_shoulder.triangles -lt 500 -or [int]$Proof.local_geometry.right_shoulder.triangles -lt 500) {
    throw 'SP638 road-first shoulder mesh is unexpectedly sparse.'
}
if ([bool]$Proof.spatial_grid_guardrail.canonical_road_xy_preserved -ne $true) {
    throw 'SP638 local-corridor proof did not preserve canonical road XY.'
}
if ([bool]$Proof.spatial_grid_guardrail.snapped_to_landscape_vertices -ne $false) {
    throw 'SP638 local-corridor proof snapped to Landscape vertices.'
}
if ([double]$Proof.source_geometry_analysis.half_window_m -lt 5.0) {
    throw "SP638 visual proof used a sub-source geometry window: $($Proof.source_geometry_analysis.half_window_m) m"
}
if ([bool]$Proof.source_geometry_analysis.canonical_centerline_xy_modified -ne $false) {
    throw 'SP638 visual proof modified canonical centerline XY.'
}
if ([string]$Proof.superelevation.mode -ne 'mase_lidar_seeded_crossfall') {
    throw "SP638 visual proof did not use MASE/LiDAR-seeded crossfall: '$($Proof.superelevation.mode)'."
}
if ([bool]$Proof.superelevation.measured_sp638_bank_data -ne $true) {
    throw 'SP638 visual proof did not use measured terrain crossfall as its primary bank source.'
}
if ([string]$Proof.superelevation.measurement_kind -ne 'LiDAR_DTM_adaptive_road_transect_fit') {
    throw "SP638 visual proof used unexpected bank measurement kind: '$($Proof.superelevation.measurement_kind)'."
}
if ([string]$Proof.superelevation.lidar_sampling.method -ne 'adaptive_transect_linear_road_fit') {
    throw "SP638 visual proof did not recover the road strip from a LiDAR transect: '$($Proof.superelevation.lidar_sampling.method)'."
}
if ([bool]$Proof.superelevation.instrument_survey_grade -ne $false) {
    throw 'SP638 LiDAR-derived bank proof incorrectly claims instrument-survey grade.'
}
if ([string]$Proof.superelevation.lidar_sampling.source -ne 'MASE_PST_1372858_LiDAR_DTM') {
    throw "SP638 visual proof used unexpected bank source: '$($Proof.superelevation.lidar_sampling.source)'."
}
if ([int]$Proof.superelevation.lidar_sampling.valid_station_count -lt 50) {
    throw "SP638 LiDAR bank sampling produced too few valid stations: $($Proof.superelevation.lidar_sampling.valid_station_count)."
}
if ([bool]$Proof.superelevation.authoritative_physics -ne $false) {
    throw 'SP638 presentation superelevation incorrectly claims physics authority.'
}
if ([bool]$Proof.superelevation.canonical_centerline_xy_modified -ne $false) {
    throw 'SP638 presentation superelevation modified canonical centerline XY.'
}
if ([double]$Proof.superelevation.peak_abs_bank_deg -lt 1.0) {
    throw "SP638 hairpin proof did not produce a visible bank: $($Proof.superelevation.peak_abs_bank_deg) deg."
}
if ([double]$Proof.superelevation.peak_abs_bank_deg -gt 4.01) {
    throw "SP638 LiDAR-regularized bank exceeded the 4-degree hard guard: $($Proof.superelevation.peak_abs_bank_deg) deg."
}
if ([double]$Proof.superelevation.maximum_adjacent_delta_deg -gt 0.351) {
    throw "SP638 presentation bank transition snapped between stations: $($Proof.superelevation.maximum_adjacent_delta_deg) deg."
}
if ([int]$Proof.superelevation.active_station_count -lt 5) {
    throw "SP638 hairpin proof banked too few stations: $($Proof.superelevation.active_station_count)."
}
if ([string]$Proof.proof_viewmode -ne 'lightingonly') {
    throw "SP638 visual proof must use Lighting Only geometry mode, got '$($Proof.proof_viewmode)'."
}
if ([bool]$Proof.material_independent_geometry_proof -ne $true) {
    throw 'SP638 visual proof did not declare material-independent geometry evidence.'
}
if ([string]$Proof.capture_source -ne 'primary_level_editor_viewport') {
    throw "SP638 visual proof did not use the primary Level Editor viewport: '$($Proof.capture_source)'."
}
if ([bool]$Proof.offscreen_camera_capture -ne $false) {
    throw 'SP638 visual proof regressed to an offscreen CameraActor capture.'
}
if ([bool]$Proof.viewport_game_view -ne $true) {
    throw 'SP638 visual proof did not keep the Level Editor viewport in Game View.'
}
if ([bool]$Proof.viewport_viewmode_verified -ne $true) {
    throw 'SP638 visual proof did not read back Lighting Only from the active editor viewport.'
}
if ([string]$Proof.viewmode_binding_api -ne 'AutomationLibrary.set_editor_active_viewport_view_mode') {
    throw "SP638 visual proof used an unexpected viewmode binding API: '$($Proof.viewmode_binding_api)'."
}
if ([double]$Proof.viewport_fov_deg -lt 75.9 -or [double]$Proof.viewport_fov_deg -gt 76.1) {
    throw "SP638 visual proof rider viewport FOV drifted: $($Proof.viewport_fov_deg)."
}
if ([string]::IsNullOrWhiteSpace([string]$Proof.viewport_config_key)) {
    throw 'SP638 visual proof did not record its Level Editor viewport key.'
}
if ([bool]$Proof.neutral_landscape_material -ne $true) {
    throw 'SP638 visual proof did not apply the required neutral Landscape proof material.'
}
if ([string]$Proof.capture_strategy -ne 'r4.1b.8-real-road-landscape-conform') {
    throw "SP638 visual proof used unexpected capture strategy: '$($Proof.capture_strategy)'."
}
if ([string]$Proof.landscape_cut_fill.mode -ne 'road_first_landscape_conform') {
    throw "SP638 terrain did not use road-first Landscape conform: '$($Proof.landscape_cut_fill.mode)'."
}
if ([string]$Proof.landscape_cut_fill.road_authority -ne 'official_sp638_gis') {
    throw "SP638 road-first proof used unexpected road authority: '$($Proof.landscape_cut_fill.road_authority)'."
}
if ([bool]$Proof.landscape_cut_fill.raise_heights -ne $true -or [bool]$Proof.landscape_cut_fill.lower_heights -ne $true) {
    throw 'SP638 road-first terrain conform must allow both cut and fill.'
}
if ([bool]$Proof.landscape_cut_fill.saved_to_map -ne $false) {
    throw 'SP638 road-first terrain conform unexpectedly persisted the Landscape edit.'
}
if ([double]$Proof.landscape_cut_fill.terrain_conform_half_width_m -lt 4.0 -or [double]$Proof.landscape_cut_fill.terrain_conform_half_width_m -gt 4.5) {
    throw "SP638 terrain conform width drifted from road/shoulder envelope: $($Proof.landscape_cut_fill.terrain_conform_half_width_m) m"
}
if ([double]$Proof.landscape_cut_fill.terrain_falloff_m -lt 8.0 -or [double]$Proof.landscape_cut_fill.terrain_falloff_m -gt 16.0) {
    throw "SP638 terrain conform falloff is outside the bounded blend range: $($Proof.landscape_cut_fill.terrain_falloff_m) m"
}
if ([double]$Proof.landscape_cut_fill.road_half_width_m -ne 3.0) {
    throw "SP638 asphalt half-width drifted: $($Proof.landscape_cut_fill.road_half_width_m) m"
}
if ([double]$Proof.landscape_cut_fill.shoulder_outer_half_width_m -ne 4.0) {
    throw "SP638 shoulder envelope drifted: $($Proof.landscape_cut_fill.shoulder_outer_half_width_m) m"
}

if (-not $ValidateOnly) {
    $CaptureLogText = Get-Content -LiteralPath $CaptureLog -Raw -ErrorAction Stop
    if ($CaptureExitCode -notin @(0,1)) {
        throw "SP638 local-corridor capture returned unexpected exit code $CaptureExitCode."
    }
    if ($CaptureLogText -match '(?i)Fatal error|Unhandled Exception|Critical error') {
        throw 'SP638 local-corridor capture log contains a crash/fatal marker.'
    }
    if ($CaptureLogText -notmatch '\[YacsSp638LocalCorridorVisual\] PASS:') {
        throw 'SP638 local-corridor log is missing the explicit PASS marker.'
    }
}

Write-Host '[3/3] Enforcing non-persistent proof contract...' -ForegroundColor Cyan
$TrackedChanges = @(git -C $RepoRoot status --porcelain=v1 --untracked-files=no)
if ($TrackedChanges.Count -gt 0) {
    throw ("SP638 local-corridor visual proof mutated tracked files: {0}" -f ($TrackedChanges -join '; '))
}

Write-Host 'R4.1B.8 real-SP638 road-first Landscape-conform visual proof: PASS.' -ForegroundColor Green
Write-Host ("Rendered proof: {0}" -f $CapturePng)
exit 0
