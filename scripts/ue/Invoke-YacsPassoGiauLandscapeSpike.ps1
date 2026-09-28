<# 
.SYNOPSIS
    Author and prove the isolated Stage 3G R4.1B Passo Giau Landscape spike.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
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
$FinalProof = Join-Path $ArtifactRoot 'passo_giau_landscape_spike_proof.json'

foreach ($Path in @($BuildLog,$MapPrepLog,$MapPrepErr,$MapPrepProof,$ImportLog,$ImportErr,$ImportProof,$CaptureLog,$CaptureStdout,$CaptureErr,$CapturePng,$CaptureProof,$FinalProof)) {
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
    & $VenvPython -m pip install --disable-pip-version-check 'numpy==2.2.6' 'Pillow==11.3.0' 'rasterio==1.4.3'
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install terrain preparation dependencies.' }
    & $VenvPython $DownloadScript
    if ($LASTEXITCODE -ne 0) { throw 'Pinned MASE PST Passo Giau LiDAR DTM download failed.' }
    & $VenvPython $FallbackDownloadScript
    if ($LASTEXITCODE -ne 0) { throw 'Veneto 5 m fallback download failed.' }
    & $VenvPython $PrepareScript
    if ($LASTEXITCODE -ne 0) { throw 'MASE PST Passo Giau LiDAR heightmap preparation failed.' }
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
if ([int]$Terrain.tile_count -ne 89 -or [double]$Terrain.target_aoi.native_cell_m -ne 1.0) { throw 'Hybrid terrain report does not prove the expected 89-tile MASE / 1 m metric working grid.' }
if ($Terrain.primary_source.source_crs -ne 'EPSG:4326' -or $Terrain.fallback_source.source_crs -ne 'EPSG:7795' -or $Terrain.target_crs -ne 'EPSG:32632') { throw 'Hybrid terrain report does not prove the expected CRS chain.' }
if ($SourceDownload.archive.sha256 -ne '0e2a133fcc80f225aee2b61aa04bc7a858aa3754c6b80a7c640b8a6ab7d14b8c' -or [int64]$SourceDownload.archive.bytes -ne 356503497) { throw 'MASE source checkpoint digest/size does not match the pinned release asset.' }
if ([int]$FallbackDownload.tile_count -lt 1) { throw 'Veneto fallback report does not prove any downloaded fallback tiles.' }
if ([double]$Terrain.coverage.mase_share -lt 0.50) { throw 'MASE primary coverage share dropped below the accepted hybrid threshold.' }
if (-not [bool]$Terrain.coverage.passo_giau.mase_1m_at_reference_point) { throw 'Passo Giau reference point is not covered by MASE primary terrain.' }
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
$ImportArgs = @($ProjectPath,'-run=CyclingPassoGiauLandscapeSpike',('-Heightmap="' + $HeightmapR16 + '"'),('-Proof="' + $ImportProof + '"'),('-ScaleZ=' + $ScaleZ.ToString([System.Globalization.CultureInfo]::InvariantCulture)),('-LocationZCm=' + $LocationZCm.ToString([System.Globalization.CultureInfo]::InvariantCulture)),'-Unattended','-NoPause','-NullRHI','-NoSplash','-NoP4','-log',('-AbsLog=' + $ImportLog))
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

$ImportLogText = Get-Content -LiteralPath $ImportLog -Raw -ErrorAction Stop
if ($ImportExitCode -notin @(0, 1)) {
    throw "Passo Giau Landscape import returned unexpected exit code $ImportExitCode."
}
if ($ImportLogText -match '(?i)Fatal error|Unhandled Exception|Critical error') {
    throw 'Passo Giau Landscape import log contains a crash/fatal marker.'
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
$Final = [ordered]@{
    schema_version = 1
    passo_giau_r4_1b_landscape_spike = 'PASS'
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

Write-Host 'Passo Giau R4.1B isolated Landscape spike: PASS.' -ForegroundColor Green
Write-Host ("Only tracked mutation: {0}" -f $SpikeMapRelative)
Write-Host ("Rendered proof: {0}" -f $CapturePng)
exit 0
