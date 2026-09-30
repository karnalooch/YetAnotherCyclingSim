<# 
.SYNOPSIS
    Author and prove the isolated Passo Giau M3 Landscape / Road & Earthworks slice.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [switch] $IncludeRoad,
    [int] $TimeoutSec = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) { $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject' }
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) { $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/CI/Stage3GR4_1/PassoGiauLandscape' }
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) { $ArtifactRoot = Join-Path $RepoRoot $ArtifactRoot }
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$SpikeMapRelative = 'Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap'
$CanonicalMapRelative = 'Content/Prototype/Maps/L_CyclingTest.umap'
$PreparedRoot = Join-Path $RepoRoot 'ExternalAssets/Terrain/PassoGiau/PreparedMasePstLidar1x1'
$HeightmapR16 = Join-Path $PreparedRoot 'passo_giau_mase_pst_ue_landscape_4033.r16'
$TerrainReport = Join-Path $PreparedRoot 'terrain-report.json'
$SourceDownloadReport = Join-Path $RepoRoot 'ExternalAssets/Terrain/PassoGiau/MASE_PST_Lidar1x1/mase-pst-download-report.json'
$FallbackDownloadReport = Join-Path $RepoRoot 'ExternalAssets/Terrain/PassoGiau/Veneto_Lidar5m/veneto-lidar-download-report.json'
$MapPrepScript = Join-Path $RepoRoot 'scripts/ue/stage3g_prepare_passo_giau_landscape_map.py'
$CaptureScript = Join-Path $RepoRoot 'scripts/ue/stage3g_capture_passo_giau_landscape.py'
$DownloadScript = Join-Path $RepoRoot 'scripts/assets/download_passo_giau_mase_pst.py'
$FallbackDownloadScript = Join-Path $RepoRoot 'scripts/assets/download_passo_giau_veneto_lidar.py'
$PrepareScript = Join-Path $RepoRoot 'scripts/assets/prepare_passo_giau_mase_pst.py'

$RoadDownloadScript = Join-Path $RepoRoot 'scripts/assets/download_passo_giau_road_network.py'
$RoadPrepareScript = Join-Path $RepoRoot 'scripts/assets/prepare_passo_giau_road.py'
$RoadCaptureScript = Join-Path $RepoRoot 'scripts/ue/stage3g_capture_passo_giau_road.py'
$RoadSourceRoot = Join-Path $RepoRoot 'ExternalAssets/Terrain/PassoGiau/RoadNetwork'
$RoadPreparedRoot = Join-Path $RepoRoot 'ExternalAssets/Terrain/PassoGiau/PreparedRoad'
$RoadDownloadReport = Join-Path $RoadSourceRoot 'road-download-report.json'
$RoadPreparationReport = Join-Path $RoadPreparedRoot 'road-preparation-report.json'
$RoadJson = Join-Path $RoadPreparedRoot 'passo_giau_sp638_ue_centerline.json'
$RoadOverlay = Join-Path $RoadPreparedRoot 'passo_giau_sp638_hillshade_overlay.png'

$BuildLog = Join-Path $ArtifactRoot 'build_editor.log'
$MapPrepLog = Join-Path $ArtifactRoot 'map_prep.log'
$MapPrepErr = $MapPrepLog + '.stderr'
$MapPrepProof = Join-Path $ArtifactRoot 'map_prep_proof.json'
$ImportLog = Join-Path $ArtifactRoot 'landscape_import.log'
$ImportErr = $ImportLog + '.stderr'
$ImportProof = Join-Path $ArtifactRoot 'landscape_import_proof.json'
$CaptureLog = Join-Path $ArtifactRoot 'capture.log'
$CaptureStdout = Join-Path $ArtifactRoot 'capture.stdout.log'
$CaptureErr = $CaptureLog + '.stderr'
$CapturePng = Join-Path $ArtifactRoot 'passo_giau_landscape_3840x2160_fxaa.png'
$CaptureProof = Join-Path $ArtifactRoot 'capture_proof.json'
$RoadCaptureLog = Join-Path $ArtifactRoot 'road_capture.log'
$RoadCaptureStdout = Join-Path $ArtifactRoot 'road_capture.stdout.log'
$RoadCaptureErr = $RoadCaptureLog + '.stderr'
$RoadCapturePng = Join-Path $ArtifactRoot 'passo_giau_sp638_rider_3840x2160.png'
$RoadTerrainOnlyPng = Join-Path $ArtifactRoot 'passo_giau_sp638_rider_terrain_only_3840x2160.png'
$RoadCaptureProof = Join-Path $ArtifactRoot 'road_capture_proof.json'
$FinalProof = Join-Path $ArtifactRoot 'passo_giau_landscape_spike_proof.json'

foreach ($Path in @($BuildLog,$MapPrepLog,$MapPrepErr,$MapPrepProof,$ImportLog,$ImportErr,$ImportProof,$CaptureLog,$CaptureStdout,$CaptureErr,$CapturePng,$CaptureProof,$RoadCaptureLog,$RoadCaptureStdout,$RoadCaptureErr,$RoadCapturePng,$RoadTerrainOnlyPng,$RoadCaptureProof,$FinalProof)) {
    Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
}

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$PreflightArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $ArtifactRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
}
$Context = & $Preflight @PreflightArgs
if ($LASTEXITCODE -ne 0) { throw 'Passo Giau Landscape preflight failed.' }

if (git -C $RepoRoot status --porcelain) { throw 'Passo Giau Landscape checkout is dirty before authoring.' }

# A previous successful authoring pass persists this generated map as an LFS
# pointer on the branch. Re-authoring must be idempotent: after proving the
# checkout is clean, remove only the isolated spike target so new_level() can
# recreate it from scratch. The final mutation guard still permits only this
# exact path, and workflow cleanup resets it on failure.
$SpikeMapPath = Join-Path $RepoRoot $SpikeMapRelative
if (Test-Path -LiteralPath $SpikeMapPath -PathType Leaf) {
    Remove-Item -LiteralPath $SpikeMapPath -Force
}
if (Test-Path -LiteralPath $SpikeMapPath) {
    throw 'Failed to remove the existing isolated Passo Giau spike map before re-authoring.'
}

$CanonicalHashBefore = (git -C $RepoRoot hash-object -- $CanonicalMapRelative).Trim()
if (-not $CanonicalHashBefore) { throw 'Failed to hash canonical L_CyclingTest before spike authoring.' }

Write-Host '[1/7] Building exact UE 5.8 editor revision...' -ForegroundColor Cyan
$BuildBat = Join-Path $Context.EngineRoot 'Engine/Build/BatchFiles/Build.bat'
$BuildArgs = @($ProjectPath,'YetAnotherCyclingSimEditor','Win64','Development','-WaitMutex','-FromMsBuild')
$BuildProc = Start-Process -FilePath $BuildBat -ArgumentList $BuildArgs -NoNewWindow -PassThru -RedirectStandardOutput $BuildLog -WorkingDirectory (Split-Path $BuildBat -Parent)
$BuildProc.WaitForExit()
if ($BuildProc.ExitCode -ne 0) { throw "Editor build failed with exit code $($BuildProc.ExitCode). See $BuildLog" }

Write-Host '[2/7] Preparing immutable MASE PST LiDAR DTM 1x1 terrain source...' -ForegroundColor Cyan
$VenvRoot = Join-Path $env:RUNNER_TEMP ('yacs-passo-giau-' + [Guid]::NewGuid().ToString('N'))
try {
    & python -m venv $VenvRoot
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create terrain preparation virtualenv.' }
    $VenvPython = Join-Path $VenvRoot 'Scripts/python.exe'
    $PythonPackages = @('numpy==2.2.6','Pillow==11.3.0','rasterio==1.4.3')
    if ($IncludeRoad) { $PythonPackages += 'shapely==2.1.1' }
    & $VenvPython -m pip install --disable-pip-version-check @PythonPackages
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install terrain preparation dependencies.' }
    & $VenvPython $DownloadScript
    if ($LASTEXITCODE -ne 0) { throw 'Pinned MASE PST Passo Giau LiDAR DTM download failed.' }
    & $VenvPython $FallbackDownloadScript
    if ($LASTEXITCODE -ne 0) { throw 'Veneto 5 m fallback download failed.' }
    & $VenvPython $PrepareScript
    if ($LASTEXITCODE -ne 0) { throw 'MASE PST Passo Giau LiDAR heightmap preparation failed.' }
    if ($IncludeRoad) {
        & $VenvPython $RoadDownloadScript
        if ($LASTEXITCODE -ne 0) { throw 'Official Veneto Passo Giau road download failed.' }
        & $VenvPython $RoadPrepareScript
        if ($LASTEXITCODE -ne 0) { throw 'Passo Giau SP638 road preparation failed.' }
    }
}
finally {
    if (Test-Path -LiteralPath $VenvRoot) { Remove-Item -LiteralPath $VenvRoot -Recurse -Force -ErrorAction SilentlyContinue }
}

if (-not (Test-Path -LiteralPath $HeightmapR16 -PathType Leaf)) { throw "Prepared R16 is missing: $HeightmapR16" }
if (-not (Test-Path -LiteralPath $TerrainReport -PathType Leaf)) { throw "Terrain report is missing: $TerrainReport" }
if (-not (Test-Path -LiteralPath $SourceDownloadReport -PathType Leaf)) { throw "MASE PST source download report is missing: $SourceDownloadReport" }
if (-not (Test-Path -LiteralPath $FallbackDownloadReport -PathType Leaf)) { throw "Veneto fallback download report is missing: $FallbackDownloadReport" }
$Terrain = Get-Content -LiteralPath $TerrainReport -Raw | ConvertFrom-Json
$SourceDownload = Get-Content -LiteralPath $SourceDownloadReport -Raw | ConvertFrom-Json
$FallbackDownload = Get-Content -LiteralPath $FallbackDownloadReport -Raw | ConvertFrom-Json
$Candidate = $Terrain.unreal_landscape_candidate
if ([int]$Candidate.landscape_size_vertices -ne 4033) { throw 'Terrain report did not produce a 4033-vertex Landscape candidate.' }
$Transform = $Candidate.recommended_transform
if ([math]::Abs([double]$Transform.scale_x_cm_per_vertex - 198.412698) -gt 0.001) { throw 'Unexpected Passo Giau XY scale in terrain report.' }
$ScaleZ = [double]$Transform.scale_z
$LocationZCm = [double]$Transform.location_z_cm_for_sea_level_preservation
if ($ScaleZ -lt 250.0 -or $ScaleZ -gt 350.0) { throw 'Unexpected Passo Giau Z scale in MASE terrain report.' }
if ($LocationZCm -lt 150000.0 -or $LocationZCm -gt 250000.0) { throw 'Unexpected Passo Giau Z midpoint in MASE terrain report.' }
if ([int]$Terrain.tile_count -ne 204 -or [double]$Terrain.target_aoi.native_cell_m -ne 1.0) { throw 'Hybrid terrain report does not prove the expected 204-tile MASE / 1 m metric working grid.' }
if ($Terrain.primary_source.source_crs -ne 'EPSG:4326' -or $Terrain.fallback_source.source_crs -ne 'EPSG:7795' -or $Terrain.target_crs -ne 'EPSG:32632') { throw 'Hybrid terrain report does not prove the expected CRS chain.' }
if ($SourceDownload.archive.sha256 -ne '4215d1d37fb8540c44442aedd164b6cda3f1845f3552413a975a6b7b1461e93c' -or [int64]$SourceDownload.archive.bytes -ne 853162557) { throw 'MASE source checkpoint digest/size does not match the pinned release asset.' }
if ([int]$SourceDownload.source_contract.tile_count -ne 204 -or [int]$SourceDownload.source_contract.dsm_tile_count -ne 0) { throw 'MASE source checkpoint must contain exactly 204 DTM GeoTIFFs and zero DSM tiles.' }
if ([int]$FallbackDownload.tile_count -lt 1) { throw 'Veneto fallback report does not prove any downloaded fallback tiles.' }
if ([double]$Terrain.coverage.mase_share -lt 0.50) { throw 'MASE primary coverage share dropped below the accepted hybrid threshold.' }
if ([double]$Terrain.coverage.passo_giau.nearest_mase_sample_distance_m -gt 500.0) { throw 'No MASE primary terrain exists within 500 m of the Passo Giau reference point.' }
if ([int]$Terrain.coverage.remaining_missing_samples -ne 0) { throw 'Hybrid terrain still contains uncovered samples after fallback fill.' }
$ExpectedElevationMinM = [double]$Terrain.elevation_m.minimum
$ExpectedElevationMaxM = [double]$Terrain.elevation_m.maximum

# Fail closed on diagnostics from the actual active hybrid preparation path.
$Diagnostics = $Terrain.landscape_diagnostics
if ($null -eq $Diagnostics) { throw 'MASE terrain report is missing Landscape diagnostics.' }
if ([int]$Diagnostics.unique_u16_count -lt 50000) {
    throw 'MASE prepared R16 lost too much encoded height diversity.'
}
$QuantizationStepM = [double]$Diagnostics.vertical_quantization_step_m
if ($QuantizationStepM -le 0.0 -or $QuantizationStepM -gt 0.05) {
    throw 'MASE prepared R16 quantization step is outside the expected terrain range.'
}
$RoundTrip = $Diagnostics.r16_roundtrip_error_m
if ($null -eq $RoundTrip) { throw 'MASE terrain report is missing R16 round-trip diagnostics.' }
$RoundTripLimitM = ($QuantizationStepM * 0.51) + 0.000001
if ([double]$RoundTrip.max_abs -gt $RoundTripLimitM) {
    throw 'Hybrid R16 round-trip error exceeds half-step quantization tolerance.'
}
$SubsectionSeam = $Diagnostics.seams.subsection_63_quads
$ComponentSeam = $Diagnostics.seams.component_126_quads
if ($null -eq $SubsectionSeam -or [int]$SubsectionSeam.sample_count -lt 1) {
    throw 'MASE terrain report is missing 63-quad subsection seam diagnostics.'
}
if ($null -eq $ComponentSeam -or [int]$ComponentSeam.sample_count -lt 1) {
    throw 'MASE terrain report is missing 126-quad component seam diagnostics.'
}
if ($null -eq $Diagnostics.slope_degrees -or @($Diagnostics.slope_degrees.histogram).Count -lt 1) {
    throw 'MASE terrain report is missing prepared slope diagnostics.'
}
if ($null -eq $Diagnostics.scanlines -or @($Diagnostics.scanlines.center_row_elevation_m).Count -lt 2 -or @($Diagnostics.scanlines.center_column_elevation_m).Count -lt 2) {
    throw 'MASE terrain report is missing deterministic center scanline diagnostics.'
}
if ($null -eq $Terrain.native_diagnostics -or [int]$Terrain.native_diagnostics.sampled_unique_elevation_count -lt 10000) {
    throw 'MASE native ~1 m source diagnostics are incomplete or implausibly low-diversity.'
}

$RoadDownload = $null
$RoadPreparation = $null
if ($IncludeRoad) {
    foreach ($RoadPath in @($RoadDownloadReport,$RoadPreparationReport,$RoadJson,$RoadOverlay)) {
        if (-not (Test-Path -LiteralPath $RoadPath -PathType Leaf)) {
            throw "Prepared SP638 road evidence is missing: $RoadPath"
        }
    }
    $RoadDownload = Get-Content -LiteralPath $RoadDownloadReport -Raw | ConvertFrom-Json
    $RoadPreparation = Get-Content -LiteralPath $RoadPreparationReport -Raw | ConvertFrom-Json
    if ($RoadDownload.road.route_id -ne '000000027157') { throw 'Road source report does not identify canonical SP638 route id.' }
    if ($RoadPreparation.route_id -ne '000000027157') { throw 'Road preparation report does not identify canonical SP638 route id.' }
    if ([int]$RoadPreparation.spline_control_point_count -lt 50 -or [int]$RoadPreparation.spline_control_point_count -gt 1000) {
        throw 'SP638 spline control count is outside the bounded authoring contract.'
    }
    if ([double]$RoadPreparation.centerline_length_m -lt 10000.0 -or [double]$RoadPreparation.centerline_length_m -gt 25000.0) {
        throw 'SP638 centerline length is outside the expected Passo Giau AOI range.'
    }
}

Write-Host '[3/7] Creating isolated spike map...' -ForegroundColor Cyan
$env:YACS_PASSO_GIAU_MAP_PREP_PROOF = $MapPrepProof
try {
    $MapPrepArgs = @($ProjectPath,('-ExecutePythonScript="' + $MapPrepScript + '"'),'-Unattended','-NoPause','-NullRHI','-NoSplash','-NoP4','-ScriptErrorsAreFatal','-log',('-AbsLog=' + $MapPrepLog))
    $Proc = Start-Process -FilePath $Context.UnrealEditorCmdPath -ArgumentList $MapPrepArgs -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $MapPrepLog -RedirectStandardError $MapPrepErr
    if (-not $Proc.WaitForExit($TimeoutSec * 1000)) { try { $Proc | Stop-Process -Force } catch { }; throw 'Passo Giau isolated map preparation timed out.' }
    if ($Proc.ExitCode -ne 0) { throw "Passo Giau map preparation failed with exit code $($Proc.ExitCode)." }
}
finally { Remove-Item Env:YACS_PASSO_GIAU_MAP_PREP_PROOF -ErrorAction SilentlyContinue }

if (-not (Test-Path -LiteralPath $MapPrepProof -PathType Leaf)) { throw 'Passo Giau map preparation proof is missing.' }
$MapPrep = Get-Content -LiteralPath $MapPrepProof -Raw | ConvertFrom-Json
if ($MapPrep.passo_giau_map_prep -ne 'PASS' -or $MapPrep.canonical_map_mutated -ne $false) { throw 'Passo Giau isolated map preparation proof is invalid.' }

Write-Host '[4/7] Importing 4033x4033 Landscape with C++ commandlet...' -ForegroundColor Cyan
$ImportArgs = @($ProjectPath,'-run=CyclingPassoGiauLandscapeSpike',('-Heightmap="' + $HeightmapR16 + '"'),('-Proof="' + $ImportProof + '"'),('-ScaleZ=' + $ScaleZ.ToString([System.Globalization.CultureInfo]::InvariantCulture)),('-LocationZCm=' + $LocationZCm.ToString([System.Globalization.CultureInfo]::InvariantCulture)))
if ($IncludeRoad) { $ImportArgs += ('-RoadJson="' + $RoadJson + '"') }
$ImportArgs += @('-Unattended','-NoPause','-NullRHI','-NoSplash','-NoP4','-log',('-AbsLog=' + $ImportLog))
$Proc = Start-Process -FilePath $Context.UnrealEditorCmdPath -ArgumentList $ImportArgs -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $ImportLog -RedirectStandardError $ImportErr
if (-not $Proc.WaitForExit($TimeoutSec * 1000)) { try { $Proc | Stop-Process -Force } catch { }; throw 'Passo Giau Landscape import commandlet timed out.' }
$ImportExitCode = $Proc.ExitCode
if (-not (Test-Path -LiteralPath $ImportProof -PathType Leaf)) { throw "Passo Giau Landscape import proof is missing (exit=$ImportExitCode)." }
$Import = Get-Content -LiteralPath $ImportProof -Raw | ConvertFrom-Json
if ($Import.passo_giau_landscape_import -ne 'PASS') { throw "Passo Giau Landscape import proof did not report PASS (exit=$ImportExitCode)." }
if ($Import.unreal_native_import_reader_parity -ne 'PASS') { throw 'Passo Giau Unreal-native R16 import-reader parity proof is missing or failed.' }
if ([int]$Import.component_count -ne 1024 -or [int]$Import.num_subsections -ne 2 -or [int]$Import.subsection_size_quads -ne 63) { throw 'Passo Giau Landscape topology proof is invalid.' }
if ([int]$Import.encoded_min -gt 512 -or [int]$Import.encoded_max -lt 65023) { throw 'Passo Giau encoded height-domain proof is invalid.' }
if ([math]::Abs([double]$Import.sampled_elevation_min_m - $ExpectedElevationMinM) -gt 10.0 -or [math]::Abs([double]$Import.sampled_elevation_max_m - $ExpectedElevationMaxM) -gt 10.0) { throw 'Passo Giau sampled elevation range drifted too far from the MASE PST LiDAR source DEM.' }
if ([math]::Abs([double]$Import.scale_z - $ScaleZ) -gt 0.001 -or [math]::Abs([double]$Import.location_z_cm - $LocationZCm) -gt 0.01) { throw 'Passo Giau import proof did not preserve the MASE vertical transform.' }

if ([math]::Abs([double]$Import.scale_z - $ScaleZ) -gt 0.001 -or [math]::Abs([double]$Import.location_z_cm - $LocationZCm) -gt 0.01) { throw 'Passo Giau import proof did not preserve the Veneto vertical transform.' }
if ([bool]$Import.edit_layers_enabled -ne $true) { throw 'Passo Giau Landscape edit layers are not enabled.' }
if ([int]$Import.edit_layer_count -ne 2) { throw 'Passo Giau Landscape must contain exactly Base_DTM + Road_Earthworks edit layers.' }
if ($Import.base_edit_layer -ne 'Base_DTM') { throw 'Passo Giau base edit layer is not Base_DTM.' }
if ($Import.road_edit_layer -ne 'Road_Earthworks') { throw 'Passo Giau road edit layer is not Road_Earthworks.' }
if ($IncludeRoad) {
    if ([bool]$Import.road_imported -ne $true) { throw 'Passo Giau import proof did not persist the requested SP638 road.' }
    if ([int]$Import.road_control_points -ne [int]$RoadPreparation.spline_control_point_count) { throw 'SP638 commandlet control-point count differs from prepared road evidence.' }
    if ([int]$Import.road_spline_mesh_segments -ne ([int]$Import.road_control_points - 1)) { throw 'SP638 spline-mesh segment count is invalid.' }
    if ([math]::Abs([double]$Import.road_width_cm - 600.0) -gt 0.01) { throw 'SP638 proof road width drifted from the bounded 6 m visual contract.' }
    if ([bool]$Import.road_earthworks_applied -ne $true) { throw 'SP638 road was imported without applying Road_Earthworks deformation.' }
    if ([bool]$Import.road_earthworks_raise_heights -ne $true -or [bool]$Import.road_earthworks_lower_heights -ne $true) { throw 'SP638 Road_Earthworks must allow both cut and fill.' }
    if ([math]::Abs([double]$Import.road_earthworks_half_width_cm - 450.0) -gt 0.01) { throw 'SP638 Road_Earthworks half-width drifted from 4.5 m.' }
    if ([math]::Abs([double]$Import.road_earthworks_side_falloff_cm - 650.0) -gt 0.01) { throw 'SP638 Road_Earthworks side falloff drifted from 6.5 m.' }
    if ([int]$Import.road_earthworks_subdivisions -lt 256 -or [int]$Import.road_earthworks_subdivisions -gt 4096) { throw 'SP638 Road_Earthworks subdivision count is outside the bounded contract.' }
} elseif ([bool]$Import.road_imported -eq $true) {
    throw 'Base Landscape authoring unexpectedly imported a road without -IncludeRoad.'
}

$ImportLogText = Get-Content -LiteralPath $ImportLog -Raw -ErrorAction Stop
if ($ImportExitCode -notin @(0, 1)) {
    throw "Passo Giau Landscape import returned unexpected exit code $ImportExitCode."
}
if ($ImportLogText -match '(?i)Fatal error|Unhandled Exception|Critical error') {
    throw 'Passo Giau Landscape import log contains a crash/fatal marker.'
}
if ($ImportLogText -match '(?i)Attempting to ConvertNonEditLayerLandscape on a landscape with edit-layer data') {
    throw 'Passo Giau Landscape import attempted a redundant edit-layer conversion.'
}
if ($IncludeRoad -and $ImportLogText -match '(?i)AttachTo:.*SP638Spline.*is not static.*SP638Segment_') {
    throw 'SP638 road persistence log contains spline-mesh mobility attachment failures.'
}
if ($ImportLogText -notmatch 'CyclingPassoGiauLandscapeSpikeCommandlet: done\.') {
    throw 'Passo Giau Landscape import log is missing the commandlet completion marker.'
}
if ($ImportExitCode -eq 1) {
    Write-Warning 'UE returned exit 1 after a proven-successful Passo Giau commandlet because code-only LFS pointer assets generated unrelated Asset Registry errors.'
}

Write-Host '[5/7] Rendering deterministic visual proof...' -ForegroundColor Cyan
$UEditor = $Context.UnrealEditorPath
if (-not $UEditor -or -not (Test-Path -LiteralPath $UEditor)) { throw 'UnrealEditor.exe GUI executable is unavailable for visual proof.' }
$env:YACS_PASSO_GIAU_CAPTURE_PNG = $CapturePng
$env:YACS_PASSO_GIAU_CAPTURE_PROOF = $CaptureProof
try {
    $CaptureArgs = @($ProjectPath,('-ExecutePythonScript="' + $CaptureScript + '"'),'-Unattended','-NoPause','-NoSplash','-NoP4','-windowed','-ResX=1920','-ResY=1080','-NoVSync','-FixedSeed','-ScriptErrorsAreFatal','-log','-stdout',('-AbsLog=' + $CaptureLog))
    # Keep UE's -AbsLog file separate from redirected stdout. Pointing both
    # streams at capture.log makes UE rotate its real log to capture_2.log,
    # which hides the Python PASS marker from the fail-closed gate.
    $Proc = Start-Process -FilePath $UEditor -ArgumentList $CaptureArgs -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $CaptureStdout -RedirectStandardError $CaptureErr
    if (-not $Proc.WaitForExit(180000)) { try { $Proc | Stop-Process -Force } catch { }; throw 'Passo Giau visual capture timed out.' }
    $CaptureExitCode = $Proc.ExitCode
}
finally {
    Remove-Item Env:YACS_PASSO_GIAU_CAPTURE_PNG -ErrorAction SilentlyContinue
    Remove-Item Env:YACS_PASSO_GIAU_CAPTURE_PROOF -ErrorAction SilentlyContinue
}
if (-not (Test-Path -LiteralPath $CapturePng -PathType Leaf)) { throw "Passo Giau rendered PNG is missing (exit=$CaptureExitCode)." }
if ((Get-Item -LiteralPath $CapturePng).Length -lt 100000) { throw 'Passo Giau rendered PNG is unexpectedly small.' }
if (-not (Test-Path -LiteralPath $CaptureProof -PathType Leaf)) { throw "Passo Giau capture proof is missing (exit=$CaptureExitCode)." }
$Capture = Get-Content -LiteralPath $CaptureProof -Raw | ConvertFrom-Json
if ($Capture.passo_giau_landscape_capture -ne 'PASS') { throw "Passo Giau visual capture proof did not report PASS (exit=$CaptureExitCode)." }
if ([int]$Capture.resolution[0] -ne 3840 -or [int]$Capture.resolution[1] -ne 2160) { throw 'Passo Giau supersampled capture proof resolution is invalid.' }
if ($Capture.capture_strategy -ne '2x-spatial-proof-with-fxaa') { throw 'Passo Giau capture proof strategy is invalid.' }
if ($Capture.proof_aa_method -ne 'FXAA' -or [int]$Capture.post_process_aa_quality -ne 6) { throw 'Passo Giau capture proof anti-aliasing contract is invalid.' }
if ([int]$Capture.forced_landscape_lod -ne 0 -or [int]$Capture.ray_tracing_landscape_lod_bias -ne -1) { throw 'Passo Giau capture proof LOD stabilization is invalid.' }
if ([bool]$Capture.proof_sun_cast_shadows -ne $false) { throw 'Passo Giau geometry proof sun unexpectedly casts shadows.' }
if ($Capture.proof_viewmode -ne 'lightingonly') { throw 'Passo Giau diagnostic proof view mode is invalid.' }
if ([int]$Capture.landscape_component_count -ne 1024) { throw 'Passo Giau capture proof Landscape component count is invalid.' }
if ([int64]$Capture.screenshot_bytes -ne (Get-Item -LiteralPath $CapturePng).Length) { throw 'Passo Giau capture proof PNG byte count does not match the rendered file.' }

$CaptureLogText = Get-Content -LiteralPath $CaptureLog -Raw -ErrorAction Stop
if ($CaptureExitCode -notin @(0, 1)) {
    throw "Passo Giau visual capture returned unexpected exit code $CaptureExitCode."
}
if ($CaptureLogText -match '(?i)Fatal error|Unhandled Exception|Critical error') {
    throw 'Passo Giau visual capture log contains a crash/fatal marker.'
}
if ($CaptureLogText -notmatch '\[PassoGiauCapture\] PASS:') {
    throw 'Passo Giau visual capture log is missing the explicit PASS marker.'
}
if ($CaptureExitCode -eq 1) {
    Write-Warning 'UE returned exit 1 after a proven-successful Passo Giau capture because code-only LFS pointer assets generated unrelated Asset Registry errors.'
}

$RoadCapture = $null
if ($IncludeRoad) {
    Write-Host '[5b/7] Rendering cyclist-height SP638 hairpin proof...' -ForegroundColor Cyan
    if (-not (Test-Path -LiteralPath $RoadCaptureScript -PathType Leaf)) {
        throw "SP638 road capture script is missing: $RoadCaptureScript"
    }
    $env:YACS_PASSO_GIAU_ROAD_CAPTURE_PNG = $RoadCapturePng
    $env:YACS_PASSO_GIAU_ROAD_TERRAIN_ONLY_PNG = $RoadTerrainOnlyPng
    $env:YACS_PASSO_GIAU_ROAD_CAPTURE_PROOF = $RoadCaptureProof
    try {
        $RoadCaptureArgs = @($ProjectPath,('-ExecutePythonScript="' + $RoadCaptureScript + '"'),'-Unattended','-NoPause','-NoSplash','-NoP4','-windowed','-ResX=1920','-ResY=1080','-NoVSync','-FixedSeed','-ScriptErrorsAreFatal','-log','-stdout',('-AbsLog=' + $RoadCaptureLog))
        $RoadProc = Start-Process -FilePath $UEditor -ArgumentList $RoadCaptureArgs -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $RoadCaptureStdout -RedirectStandardError $RoadCaptureErr
        if (-not $RoadProc.WaitForExit(180000)) { try { $RoadProc | Stop-Process -Force } catch { }; throw 'SP638 rider visual capture timed out.' }
        $RoadCaptureExitCode = $RoadProc.ExitCode
    }
    finally {
        Remove-Item Env:YACS_PASSO_GIAU_ROAD_CAPTURE_PNG -ErrorAction SilentlyContinue
        Remove-Item Env:YACS_PASSO_GIAU_ROAD_TERRAIN_ONLY_PNG -ErrorAction SilentlyContinue
        Remove-Item Env:YACS_PASSO_GIAU_ROAD_CAPTURE_PROOF -ErrorAction SilentlyContinue
    }

    if (-not (Test-Path -LiteralPath $RoadCapturePng -PathType Leaf)) { throw "SP638 rider PNG is missing (exit=$RoadCaptureExitCode)." }
    if ((Get-Item -LiteralPath $RoadCapturePng).Length -lt 100000) { throw 'SP638 rider PNG is unexpectedly small.' }
    if (-not (Test-Path -LiteralPath $RoadTerrainOnlyPng -PathType Leaf)) { throw "SP638 terrain-only comparison PNG is missing (exit=$RoadCaptureExitCode)." }
    if ((Get-Item -LiteralPath $RoadTerrainOnlyPng).Length -lt 100000) { throw 'SP638 terrain-only comparison PNG is unexpectedly small.' }
    if (-not (Test-Path -LiteralPath $RoadCaptureProof -PathType Leaf)) { throw "SP638 rider capture proof is missing (exit=$RoadCaptureExitCode)." }
    $RoadCapture = Get-Content -LiteralPath $RoadCaptureProof -Raw | ConvertFrom-Json
    if ($RoadCapture.passo_giau_sp638_rider_capture -ne 'PASS') { throw "SP638 rider capture proof did not report PASS (exit=$RoadCaptureExitCode)." }
    if ([int]$RoadCapture.resolution[0] -ne 3840 -or [int]$RoadCapture.resolution[1] -ne 2160) { throw 'SP638 rider proof resolution is invalid.' }
    if ([int]$RoadCapture.road_control_points -ne [int]$Import.road_control_points) { throw 'SP638 rider proof control count differs from import proof.' }
    if ([int]$RoadCapture.road_spline_mesh_segments -ne [int]$Import.road_spline_mesh_segments) { throw 'SP638 rider proof spline-mesh count differs from import proof.' }
    if ([double]$RoadCapture.road_spline_length_m -lt 10000.0 -or [double]$RoadCapture.road_spline_length_m -gt 25000.0) { throw 'SP638 rider proof spline length is outside the expected AOI range.' }
    if ([double]$RoadCapture.curvature_score -le 0.0) { throw 'SP638 rider proof did not select a curved road segment.' }
    if ($RoadCapture.comparison_strategy -ne 'same-camera-combined-vs-terrain-only') { throw 'SP638 rider proof comparison strategy is invalid.' }
    if ([int64]$RoadCapture.terrain_only_screenshot_bytes -ne (Get-Item -LiteralPath $RoadTerrainOnlyPng).Length) { throw 'SP638 terrain-only proof PNG byte count does not match the rendered file.' }

    $RoadCaptureLogText = Get-Content -LiteralPath $RoadCaptureLog -Raw -ErrorAction Stop
    if ($RoadCaptureExitCode -notin @(0, 1)) { throw "SP638 rider capture returned unexpected exit code $RoadCaptureExitCode." }
    if ($RoadCaptureLogText -match '(?i)Fatal error|Unhandled Exception|Critical error') { throw 'SP638 rider capture log contains a crash/fatal marker.' }
    if ($RoadCaptureLogText -notmatch '\[PassoGiauRoadCapture\] PASS:') { throw 'SP638 rider capture log is missing the explicit PASS marker.' }
    if ($RoadCaptureExitCode -eq 1) {
        Write-Warning 'UE returned exit 1 after a proven-successful SP638 rider capture because code-only LFS pointer assets generated unrelated Asset Registry errors.'
    }
}

Write-Host '[6/7] Enforcing canonical-map and mutation guards...' -ForegroundColor Cyan
$CanonicalHashAfter = (git -C $RepoRoot hash-object -- $CanonicalMapRelative).Trim()
if ($CanonicalHashBefore -ne $CanonicalHashAfter) { throw 'L_CyclingTest changed during isolated Passo Giau authoring.' }
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $SpikeMapRelative) -PathType Leaf)) { throw "Isolated spike map was not persisted: $SpikeMapRelative" }

$TrackedChanges = @(
    git -C $RepoRoot status --porcelain=v1 --untracked-files=all |
        ForEach-Object {
            if ($_ -and $_.Length -ge 4) {
                $P = $_.Substring(3).Trim()
                if ($P -match ' -> ') { $P = ($P -split ' -> ')[-1].Trim() }
                $P
            }
        } |
        Where-Object { $_ }
)
$Unexpected = @($TrackedChanges | Where-Object { $_ -ne $SpikeMapRelative })
if ($Unexpected.Count -gt 0) { throw ("Unexpected tracked mutations: {0}" -f ($Unexpected -join ', ')) }
if ($TrackedChanges -notcontains $SpikeMapRelative) { throw 'Passo Giau authoring produced no isolated spike-map mutation.' }

Write-Host '[7/7] Writing consolidated evidence...' -ForegroundColor Cyan
$RoadEvidence = $null
if ($IncludeRoad) {
    $RoadEvidence = [ordered]@{
        download_report = $RoadDownload
        preparation_report = $RoadPreparation
        ue_centerline_json = $RoadJson
        hillshade_overlay = $RoadOverlay
        imported_control_points = [int]$Import.road_control_points
        imported_spline_mesh_segments = [int]$Import.road_spline_mesh_segments
        rider_capture = $RoadCapture
        visual_acceptance = 'PENDING_HUMAN_REVIEW'
        presentation_only = $true
        authoritative_route_geometry = $false
        authoritative_physics = $false
    }
}

$Final = [ordered]@{
    schema_version = 1
    passo_giau_r4_1b_landscape_spike = 'PASS'
    passo_giau_m3_road_earthworks = $(if ($IncludeRoad) { 'PASS' } else { 'NOT_REQUESTED' })
    expected_head = $ExpectedHead
    source = [ordered]@{
        provider = 'Ministero dell''Ambiente e della Sicurezza Energetica (MASE)'
        dataset = 'PST LiDAR DTM grigliato 1x1'
        license = 'CC BY 4.0'
        release_tag = 'data-mase-pst-passo-giau-dtm-2026-09-28'
        tile_count = [int]$Terrain.tile_count
        native_cell_m = [double]$Terrain.target_aoi.native_cell_m
        source_download_report = $SourceDownload
        terrain_report = $Terrain
    }
    isolated_map = $SpikeMapRelative
    canonical_map = $CanonicalMapRelative
    canonical_map_hash_before = $CanonicalHashBefore
    canonical_map_hash_after = $CanonicalHashAfter
    road = $RoadEvidence
    import = $Import
    import_process_exit_code = [int]$ImportExitCode
    capture = $Capture
    capture_process_exit_code = [int]$CaptureExitCode
    code_only_lfs_asset_registry_exit_tolerance_used = ([int]$ImportExitCode -eq 1 -or [int]$CaptureExitCode -eq 1)
    tracked_mutations = @($TrackedChanges)
    visual_acceptance = 'PENDING_HUMAN_REVIEW'
    presentation_only = $true
    authoritative_route_geometry = $false
    authoritative_physics = $false
}
$Final | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $FinalProof -Encoding UTF8

if ($IncludeRoad) {
    Write-Host ("SP638 road proof: {0} controls / {1} spline meshes." -f $Import.road_control_points,$Import.road_spline_mesh_segments) -ForegroundColor Green
    Write-Host ("SP638 rider proof: {0}" -f $RoadCapturePng) -ForegroundColor Green
}
Write-Host 'Passo Giau M3 isolated Landscape / Road & Earthworks proof: PASS.' -ForegroundColor Green
Write-Host ("Only tracked mutation: {0}" -f $SpikeMapRelative)
Write-Host ("Rendered proof: {0}" -f $CapturePng)
exit 0
