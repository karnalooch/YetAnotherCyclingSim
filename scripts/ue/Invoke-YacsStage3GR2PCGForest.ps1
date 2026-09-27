<#
.SYNOPSIS
    Build, author and validate the Stage 3G R2 PCG_Forest prototype graph.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [string] $ExpectedBranch = 'HEAD',
    [int] $TimeoutSec = 1800
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

if (-not $ProjectPath) {
    $ProjectPath = Join-Path -Path $RepoRoot -ChildPath 'YetAnotherCyclingSim.uproject'
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path

if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/CI/Stage3GR2/PCGForest'
}
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath $ArtifactRoot
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$CiEntry = Join-Path -Path $RepoRoot -ChildPath 'scripts/ci/Invoke-YacsUnrealCi.ps1'
$CanaryRoot = Join-Path -Path $ArtifactRoot -ChildPath 'Canary'
& $CiEntry -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $CanaryRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead -TestFilter 'CyclingStage3World'
if ($LASTEXITCODE -ne 0) {
    throw 'Stage 3G R2 PCG forest build/Automation canary failed.'
}

$Preflight = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) {
    throw 'Stage 3G R2 PCG forest preflight failed.'
}

$AuthorScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/stage3g_author_pcg_forest.py'
$WorldSpec = Join-Path -Path $RepoRoot -ChildPath 'worldgen/specs/stage3g_alpine_reference.worldspec.yml'
$ProofJson = Join-Path -Path $ArtifactRoot -ChildPath 'pcg_forest_graph_proof.json'
$AuthorLog = Join-Path -Path $ArtifactRoot -ChildPath 'pcg_forest_authoring.log'
$EditorLog = $AuthorLog + '.editor.log'
$ErrLog = $AuthorLog + '.stderr'
$AssetRelativePath = 'Content/YACS/WorldGen/PCG/PCG_Forest.uasset'
$AssetDiskPath = Join-Path -Path $RepoRoot -ChildPath $AssetRelativePath

Remove-Item -LiteralPath $ProofJson -Force -ErrorAction SilentlyContinue
$env:YACS_STAGE3G_WORLDSPEC = $WorldSpec
$env:YACS_STAGE3G_R2_PCG_FOREST_PROOF = $ProofJson
try {
    $Arguments = @(
        $ProjectPath
        '-run=PythonScript'
        ('-script="' + $AuthorScript + '"')
        '-Unattended'
        '-NoPause'
        '-NullRHI'
        '-NoSplash'
        '-NoP4'
        '-log'
        ('-AbsLog=' + $EditorLog)
    )
    $Proc = Start-Process -FilePath $Context.UnrealEditorCmdPath -ArgumentList $Arguments -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $AuthorLog -RedirectStandardError $ErrLog
    if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
        try { $Proc | Stop-Process -Force } catch { }
        throw "PCG_Forest authoring timed out; see $AuthorLog"
    }
    if ($Proc.ExitCode -ne 0) {
        throw "PCG_Forest authoring failed with exit code $($Proc.ExitCode); see $AuthorLog"
    }
}
finally {
    Remove-Item Env:YACS_STAGE3G_WORLDSPEC -ErrorAction SilentlyContinue
    Remove-Item Env:YACS_STAGE3G_R2_PCG_FOREST_PROOF -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $ProofJson -PathType Leaf)) {
    throw 'PCG_Forest proof JSON is missing.'
}
$Proof = Get-Content -LiteralPath $ProofJson -Raw -ErrorAction Stop | ConvertFrom-Json
if ($Proof.stage3g_r2_pcg_forest_graph -ne 'success') {
    throw 'PCG_Forest graph proof did not report success.'
}
if ($Proof.asset_path -ne '/Game/YACS/WorldGen/PCG/PCG_Forest') {
    throw "Unexpected PCG_Forest asset path: $($Proof.asset_path)"
}
if ([int]$Proof.generation_seed -ne 42017) {
    throw "Unexpected PCG_Forest seed: $($Proof.generation_seed)"
}
if ([math]::Abs([double]$Proof.forest_start_m - 3700.0) -gt 1e-9 -or [math]::Abs([double]$Proof.forest_end_m - 6200.0) -gt 1e-9) {
    throw 'Unexpected PCG_Forest biome range.'
}
if ([math]::Abs([double]$Proof.forest_density - 0.84) -gt 1e-9) {
    throw "Unexpected PCG_Forest density: $($Proof.forest_density)"
}
if ([math]::Abs([double]$Proof.route_clearance_m - 4.0) -gt 1e-9) {
    throw "Unexpected PCG_Forest route clearance: $($Proof.route_clearance_m)"
}
if ($Proof.spawner_status -ne 'validated_mass_forest_asset') {
    throw "Unexpected PCG_Forest spawner status: $($Proof.spawner_status)"
}
if ($Proof.spawner_mesh -ne '/Game/Prototype/Environment/Stage3G/Imported/Meshes/SM_Stage3G_FirSaplingMedium') {
    throw "Unexpected PCG_Forest spawner mesh: $($Proof.spawner_mesh)"
}
if ($Proof.forest_lod_profile -ne 'aggressive') {
    throw "Unexpected PCG_Forest LOD profile: $($Proof.forest_lod_profile)"
}
if ($Proof.forest_layer_profile -ne 'target_density_v2') {
    throw "Unexpected PCG_Forest layer profile: $($Proof.forest_layer_profile)"
}
if ([int]$Proof.layer_profile_version -ne 2) {
    throw "Unexpected PCG_Forest layer profile version: $($Proof.layer_profile_version)"
}
$ExpectedMean = [double]$Proof.configured_expected_candidate_mean
if ($ExpectedMean -lt 1850.0 -or $ExpectedMean -gt 2150.0) {
    throw ("PCG_Forest target-density expected candidate mean {0:F2} is outside [1850, 2150]." -f $ExpectedMean)
}
if ([math]::Abs([double]$Proof.station_spacing_m - 20.0) -gt 1e-9 -or [int]$Proof.points_per_side_per_station -ne 4) {
    throw 'Unexpected PCG_Forest primary-layer station profile.'
}
if ([math]::Abs([double]$Proof.min_lateral_offset_m - 10.0) -gt 1e-9 -or [math]::Abs([double]$Proof.max_lateral_offset_m - 36.0) -gt 1e-9) {
    throw 'Unexpected PCG_Forest primary-layer lateral profile.'
}
if ([math]::Abs([double]$Proof.min_uniform_scale - 0.95) -gt 1e-9 -or [math]::Abs([double]$Proof.max_uniform_scale - 1.35) -gt 1e-9) {
    throw 'Unexpected PCG_Forest primary-layer scale profile.'
}
if ([int]$Proof.spawner_weight -ne 100) {
    throw "Unexpected PCG_Forest spawner weight: $($Proof.spawner_weight)"
}
if (-not (Test-Path -LiteralPath $AssetDiskPath -PathType Leaf)) {
    throw "Authored PCG_Forest asset is missing: $AssetRelativePath"
}

Push-Location -LiteralPath $RepoRoot
try {
    $Dirty = @(git status --porcelain=v1 --untracked-files=all)
}
finally {
    Pop-Location
}
$Unexpected = @(
    $Dirty | Where-Object {
        $_ -and $_.Length -ge 4 -and $_.Substring(3).Trim() -ne $AssetRelativePath
    }
)
if ($Unexpected.Count -gt 0) {
    throw ("PCG forest authoring changed unexpected paths: {0}" -f ($Unexpected -join '; '))
}

Write-Host 'PCG_FOREST GRAPH AUTHORING OK.' -ForegroundColor Green
exit 0
