<#
.SYNOPSIS
    Render a bounded Passo Giau SP638 hairpin proof with one roadside alpine house.
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
if (-not $ArtifactRoot) { $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/CI/Stage3GR4_1/RoadsideHouse' }
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) { $ArtifactRoot = Join-Path $RepoRoot $ArtifactRoot }
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$SpikeMapRelative = 'Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap'
$SpikeMapPath = Join-Path $RepoRoot $SpikeMapRelative
$CaptureScript = Join-Path $RepoRoot 'scripts/ue/stage3g_capture_passo_giau_roadside_house.py'
$AssetLibrary = Join-Path $RepoRoot 'scripts/assets/yacs_asset_library.py'
$AssetCatalog = Join-Path $RepoRoot 'worldgen/assets/catalog.json'
$GrovePreset = Join-Path $RepoRoot 'worldgen/presets/alpine_roadside_grove_v1.json'
$AssetCache = Join-Path $RepoRoot 'ExternalAssets/WorldLibrary'
$SelectionPlan = Join-Path $ArtifactRoot 'world_asset_selection_plan.json'
$BuildLog = Join-Path $ArtifactRoot 'build_editor.log'
$CaptureLog = Join-Path $ArtifactRoot 'roadside_house_capture.log'
$CaptureStdout = Join-Path $ArtifactRoot 'roadside_house_capture.stdout.log'
$CaptureErr = $CaptureLog + '.stderr'
$CapturePng = Join-Path $ArtifactRoot 'passo_giau_sp638_roadside_house_3840x2160.png'
$CaptureProof = Join-Path $ArtifactRoot 'roadside_house_capture_proof.json'

foreach ($Path in @($BuildLog,$CaptureLog,$CaptureStdout,$CaptureErr,$CapturePng,$CaptureProof,$SelectionPlan)) {
    Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
}

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) { throw 'Roadside house preflight failed.' }

if (git -C $RepoRoot status --porcelain --untracked-files=all) {
    throw 'Roadside house checkout is dirty before LFS materialization.'
}

Write-Host '[1/5] Resolving and caching semantic world assets...' -ForegroundColor Cyan
foreach ($Path in @($AssetLibrary,$AssetCatalog,$GrovePreset)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "World Authoring Library input is missing: $Path"
    }
}

& python $AssetLibrary `
    --catalog $AssetCatalog `
    --preset $GrovePreset `
    --destination $AssetCache `
    --output $SelectionPlan `
    --live-discovery `
    --download
if ($LASTEXITCODE -ne 0) { throw 'YACS World Authoring Library asset resolution/download failed.' }
if (-not (Test-Path -LiteralPath $SelectionPlan -PathType Leaf)) {
    throw 'World Authoring Library did not emit selection-plan JSON.'
}

$Selection = Get-Content -LiteralPath $SelectionPlan -Raw | ConvertFrom-Json
if ($Selection.library -ne 'YACS World Authoring Library') { throw 'Unexpected asset-library proof identity.' }
if ($Selection.preset_id -ne 'alpine_roadside_grove_v1') { throw 'Unexpected world-authoring preset.' }
if ($Selection.generated_root -notlike '/Game/Generated/YACS*') { throw 'Generated root escaped YACS sandbox.' }
$MassConifer = @($Selection.selections | Where-Object { $_.slot -eq 'mass_conifer' })
if ($MassConifer.Count -ne 1) { throw 'Expected exactly one mass_conifer selection.' }
if ($MassConifer[0].provider -ne 'polyhaven') { throw 'Mass conifer provider is not Poly Haven.' }
if ($MassConifer[0].provider_asset_id -ne 'fir_sapling_medium') { throw 'Validated mass conifer selection changed unexpectedly.' }
if ($MassConifer[0].lifecycle_status -ne 'approved') { throw 'Mass conifer is not approved.' }
if (-not $MassConifer[0].ue_asset_path) { throw 'Mass conifer has no qualified Unreal asset path.' }
if (@($Selection.downloads).Count -lt 2) { throw 'Asset source-cache proof resolved too few files.' }
foreach ($Download in @($Selection.downloads)) {
    if ($Download.status -notin @('cached','downloaded')) {
        throw "Unexpected asset download status $($Download.status)."
    }
    if (-not $Download.md5) { throw 'Asset download entry is missing MD5 provenance.' }
}

Write-Host '[2/5] Materializing persisted Passo Giau map...' -ForegroundColor Cyan
git -C $RepoRoot lfs install --local
if ($LASTEXITCODE -ne 0) { throw 'git lfs install failed.' }
git -C $RepoRoot lfs pull --include=$SpikeMapRelative --exclude=''
if ($LASTEXITCODE -ne 0) { throw 'git lfs pull for Passo Giau spike map failed.' }
if (-not (Test-Path -LiteralPath $SpikeMapPath -PathType Leaf)) { throw "Passo Giau map is missing: $SpikeMapPath" }
$MapBytes = (Get-Item -LiteralPath $SpikeMapPath).Length
if ($MapBytes -lt 100000000) { throw "Passo Giau map was not materialized from LFS (bytes=$MapBytes)." }

Write-Host '[3/5] Building exact UE 5.8 editor revision...' -ForegroundColor Cyan
$BuildBat = Join-Path $Context.EngineRoot 'Engine/Build/BatchFiles/Build.bat'
$BuildArgs = @($ProjectPath,'YetAnotherCyclingSimEditor','Win64','Development','-WaitMutex','-FromMsBuild')
$BuildProc = Start-Process -FilePath $BuildBat -ArgumentList $BuildArgs -NoNewWindow -PassThru -RedirectStandardOutput $BuildLog -WorkingDirectory (Split-Path $BuildBat -Parent)
$BuildProc.WaitForExit()
if ($BuildProc.ExitCode -ne 0) { throw "Editor build failed with exit code $($BuildProc.ExitCode). See $BuildLog" }

Write-Host '[4/5] Rendering World Authoring Library proof...' -ForegroundColor Cyan
$UEditor = $Context.UnrealEditorPath
if (-not $UEditor -or -not (Test-Path -LiteralPath $UEditor)) { throw 'UnrealEditor.exe GUI executable is unavailable.' }
if (-not (Test-Path -LiteralPath $CaptureScript -PathType Leaf)) { throw "Roadside house capture script is missing: $CaptureScript" }

$env:YACS_PASSO_GIAU_HOUSE_CAPTURE_PNG = $CapturePng
$env:YACS_PASSO_GIAU_HOUSE_CAPTURE_PROOF = $CaptureProof
$env:YACS_WORLD_ASSET_SELECTION_PLAN = $SelectionPlan
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
        throw 'Roadside house visual capture timed out.'
    }
    $CaptureExitCode = $Proc.ExitCode
}
finally {
    Remove-Item Env:YACS_PASSO_GIAU_HOUSE_CAPTURE_PNG -ErrorAction SilentlyContinue
    Remove-Item Env:YACS_PASSO_GIAU_HOUSE_CAPTURE_PROOF -ErrorAction SilentlyContinue
    Remove-Item Env:YACS_WORLD_ASSET_SELECTION_PLAN -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $CapturePng -PathType Leaf)) { throw "Roadside house PNG is missing (exit=$CaptureExitCode)." }
if ((Get-Item -LiteralPath $CapturePng).Length -lt 100000) { throw 'Roadside house PNG is unexpectedly small.' }
if (-not (Test-Path -LiteralPath $CaptureProof -PathType Leaf)) { throw "Roadside house proof JSON is missing (exit=$CaptureExitCode)." }

$Proof = Get-Content -LiteralPath $CaptureProof -Raw | ConvertFrom-Json
if ($Proof.passo_giau_roadside_house_capture -ne 'PASS') { throw 'Roadside house proof did not report PASS.' }
if ($Proof.yacs_world_authoring_library -ne 'PASS') { throw 'World Authoring Library proof did not report PASS.' }
if ([int]$Proof.resolution[0] -ne 3840 -or [int]$Proof.resolution[1] -ne 2160) { throw 'Roadside house proof resolution is invalid.' }
if ([double]$Proof.slice_length_m -lt 500.0 -or [double]$Proof.slice_length_m -gt 900.0) { throw 'Roadside house proof slice length is outside the bounded proof contract.' }
if ([double]$Proof.curvature_score -le 0.0) { throw 'Roadside house proof did not select a curved segment.' }
if ([double]$Proof.house.road_offset_m -lt 10.0 -or [double]$Proof.house.road_offset_m -gt 15.0) { throw 'Roadside house offset is outside the safe proof band.' }
if ([int]$Proof.house.part_count -lt 8) { throw 'Roadside house proof has too few house parts.' }
if ([bool]$Proof.house.transient -ne $true) { throw 'Roadside house proof is not transient.' }
if ([bool]$Proof.house.saved_to_map -ne $false) { throw 'Roadside house proof unexpectedly claims a persistent save.' }
if ([double]$Proof.forest.forest_patch_size_m[0] -ne 10.0 -or [double]$Proof.forest.forest_patch_size_m[1] -ne 10.0) { throw 'Forest patch is not 10x10 m.' }
if ([int]$Proof.forest.tree_count -lt 12 -or [int]$Proof.forest.tree_count -gt 18) { throw 'Forest tree count is outside preset contract.' }
if ([bool]$Proof.forest.transient -ne $true) { throw 'Forest proof is not transient.' }
if ([bool]$Proof.forest.saved_to_map -ne $false) { throw 'Forest proof unexpectedly claims a persistent save.' }
if ($Proof.forest.mass_conifer.provider_asset_id -ne 'fir_sapling_medium') { throw 'Forest proof did not use the approved mass conifer.' }
if ($Proof.forest.mass_conifer.lifecycle_status -ne 'approved') { throw 'Forest proof used a non-approved asset.' }
if ([bool]$Proof.forest.pcg_contract.graphs_loaded -ne $true) { throw 'Forest proof did not validate existing PCG graphs.' }
if ($Proof.forest.pcg_contract.forest_graph -ne '/Game/YACS/WorldGen/PCG/PCG_Forest') { throw 'Forest proof used an unexpected PCG graph.' }
if ([bool]$Proof.landscape_cut_fill.saved_to_map -ne $false) { throw 'Roadside house proof unexpectedly claims persistent Landscape mutation.' }
if ([int]$Proof.proof_mesh.road_segments -lt 50 -or [int]$Proof.proof_mesh.shoulder_segments -lt 50) { throw 'Roadside house proof mesh is unexpectedly sparse.' }

$CaptureLogText = Get-Content -LiteralPath $CaptureLog -Raw -ErrorAction Stop
if ($CaptureExitCode -notin @(0,1)) { throw "Roadside house capture returned unexpected exit code $CaptureExitCode." }
if ($CaptureLogText -match '(?i)Fatal error|Unhandled Exception|Critical error') { throw 'Roadside house capture log contains a crash/fatal marker.' }
if ($CaptureLogText -notmatch '\[PassoGiauRoadsideHouse\] PASS:') { throw 'Roadside house capture log is missing the explicit PASS marker.' }

Write-Host '[5/5] Enforcing non-persistent visual-spike contract...' -ForegroundColor Cyan
$TrackedChanges = @(git -C $RepoRoot status --porcelain=v1 --untracked-files=no)
if ($TrackedChanges.Count -gt 0) {
    throw ("Roadside house proof mutated tracked files: {0}" -f ($TrackedChanges -join '; '))
}

Write-Host 'YACS World Authoring Library SP638 proof: PASS.' -ForegroundColor Green
Write-Host ("Rendered proof: {0}" -f $CapturePng)
Write-Host ("House offset: {0} m; side={1}; parts={2}" -f $Proof.house.road_offset_m,$Proof.house.outside_side,$Proof.house.part_count)
Write-Host ("Forest patch: {0}x{1} m; trees={2}; asset={3}" -f $Proof.forest.forest_patch_size_m[0],$Proof.forest.forest_patch_size_m[1],$Proof.forest.tree_count,$Proof.forest.mass_conifer.provider_asset_id)
exit 0
