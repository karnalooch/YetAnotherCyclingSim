<#
.SYNOPSIS
    Build, author and validate the Stage 3G R3 PCG_Valley and PCG_HighAlpine graphs.
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
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/CI/Stage3GR3/PCGBiomes'
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
    throw 'Stage 3G R3 biome PCG build/Automation canary failed.'
}

$Preflight = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) {
    throw 'Stage 3G R3 biome PCG preflight failed.'
}

$AuthorScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/stage3g_author_pcg_biomes.py'
$WorldSpec = Join-Path -Path $RepoRoot -ChildPath 'worldgen/specs/stage3g_alpine_reference.worldspec.yml'
$ProofJson = Join-Path -Path $ArtifactRoot -ChildPath 'pcg_biomes_graph_proof.json'
$AuthorLog = Join-Path -Path $ArtifactRoot -ChildPath 'pcg_biomes_authoring.log'
$ErrLog = $AuthorLog + '.stderr'

$ValleyRelativePath = 'Content/YACS/WorldGen/PCG/PCG_Valley.uasset'
$HighAlpineRelativePath = 'Content/YACS/WorldGen/PCG/PCG_HighAlpine.uasset'
$ExpectedAuthoredPaths = @($ValleyRelativePath, $HighAlpineRelativePath) | Sort-Object

foreach ($RelativePath in $ExpectedAuthoredPaths) {
    $AssetPath = Join-Path -Path $RepoRoot -ChildPath $RelativePath
    $AssetStem = [System.IO.Path]::ChangeExtension($AssetPath, $null)
    foreach ($Candidate in @($AssetPath, ($AssetStem + '.uexp'), ($AssetStem + '.ubulk'))) {
        Remove-Item -LiteralPath $Candidate -Force -ErrorAction SilentlyContinue
    }
}

Remove-Item -LiteralPath $ProofJson -Force -ErrorAction SilentlyContinue
$env:YACS_STAGE3G_WORLDSPEC = $WorldSpec
$env:YACS_STAGE3G_R3_PCG_BIOMES_PROOF = $ProofJson
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
    )
    $Proc = Start-Process -FilePath $Context.UnrealEditorCmdPath -ArgumentList $Arguments -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $AuthorLog -RedirectStandardError $ErrLog
    if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
        try { $Proc | Stop-Process -Force } catch { }
        throw "Stage 3G R3 biome PCG authoring timed out; see $AuthorLog"
    }
    if ($Proc.ExitCode -ne 0) {
        throw "Stage 3G R3 biome PCG authoring failed with exit code $($Proc.ExitCode); see $AuthorLog"
    }
}
finally {
    Remove-Item Env:YACS_STAGE3G_WORLDSPEC -ErrorAction SilentlyContinue
    Remove-Item Env:YACS_STAGE3G_R3_PCG_BIOMES_PROOF -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $ProofJson -PathType Leaf)) {
    throw 'Stage 3G R3 biome PCG proof JSON is missing.'
}

$Proof = Get-Content -LiteralPath $ProofJson -Raw -ErrorAction Stop | ConvertFrom-Json
if ($Proof.stage3g_r3_pcg_biomes_graphs -ne 'success') {
    throw 'Stage 3G R3 biome graph proof did not report success.'
}
if ([int]$Proof.generation_seed -ne 42017) {
    throw "Unexpected R3 biome generation seed: $($Proof.generation_seed)"
}
if ([math]::Abs([double]$Proof.route_clearance_m - 4.0) -gt 1e-9) {
    throw "Unexpected R3 route clearance: $($Proof.route_clearance_m)"
}

$Valley = $Proof.graphs.valley
if ($Valley.asset_path -ne '/Game/YACS/WorldGen/PCG/PCG_Valley') {
    throw "Unexpected PCG_Valley asset path: $($Valley.asset_path)"
}
if ($Valley.worldspec_biome -ne 'valley_meadow') {
    throw "Unexpected PCG_Valley biome: $($Valley.worldspec_biome)"
}
if ([math]::Abs([double]$Valley.start_m - 0.0) -gt 1e-9 -or [math]::Abs([double]$Valley.end_m - 3700.0) -gt 1e-9) {
    throw 'Unexpected PCG_Valley biome range.'
}
if ([math]::Abs([double]$Valley.rocks_density - 0.10) -gt 1e-9) {
    throw "Unexpected PCG_Valley rock density: $($Valley.rocks_density)"
}

$HighAlpine = $Proof.graphs.high_alpine
if ($HighAlpine.asset_path -ne '/Game/YACS/WorldGen/PCG/PCG_HighAlpine') {
    throw "Unexpected PCG_HighAlpine asset path: $($HighAlpine.asset_path)"
}
if ($HighAlpine.worldspec_biome -ne 'high_alpine') {
    throw "Unexpected PCG_HighAlpine biome: $($HighAlpine.worldspec_biome)"
}
if ([math]::Abs([double]$HighAlpine.start_m - 6200.0) -gt 1e-9 -or [math]::Abs([double]$HighAlpine.end_m - 10000.0) -gt 1e-9) {
    throw 'Unexpected PCG_HighAlpine biome range.'
}
if ([math]::Abs([double]$HighAlpine.rocks_density - 0.65) -gt 1e-9) {
    throw "Unexpected PCG_HighAlpine rock density: $($HighAlpine.rocks_density)"
}

foreach ($Graph in @($Valley, $HighAlpine)) {
    if ([int]$Graph.generation_seed -ne 42017) {
        throw "Unexpected graph seed for $($Graph.asset_path): $($Graph.generation_seed)"
    }
    if ([math]::Abs([double]$Graph.route_clearance_m - 4.0) -gt 1e-9) {
        throw "Unexpected graph route clearance for $($Graph.asset_path): $($Graph.route_clearance_m)"
    }
    if ($Graph.spawner_mesh -ne '/Game/Prototype/Environment/Stage3G/Imported/Meshes/SM_Stage3G_Boulder') {
        throw "Unexpected graph spawner mesh for $($Graph.asset_path): $($Graph.spawner_mesh)"
    }
    if ([int]$Graph.spawner_weight -ne 100) {
        throw "Unexpected graph spawner weight for $($Graph.asset_path): $($Graph.spawner_weight)"
    }
    if ($Graph.route_truth -ne 'FRouteGeometryProfile') {
        throw "Unexpected graph route truth for $($Graph.asset_path): $($Graph.route_truth)"
    }
}

foreach ($RelativePath in $ExpectedAuthoredPaths) {
    $DiskPath = Join-Path -Path $RepoRoot -ChildPath $RelativePath
    if (-not (Test-Path -LiteralPath $DiskPath -PathType Leaf)) {
        throw "Authored Stage 3G R3 graph is missing: $RelativePath"
    }
}

Push-Location -LiteralPath $RepoRoot
try {
    $Dirty = @(git status --porcelain=v1 --untracked-files=all)
}
finally {
    Pop-Location
}

$ChangedPaths = @(
    $Dirty | ForEach-Object {
        if ($_ -and $_.Length -ge 4) {
            $_.Substring(3).Trim()
        }
    } | Where-Object { $_ } | Sort-Object
)
if (($ChangedPaths -join [Environment]::NewLine) -ne ($ExpectedAuthoredPaths -join [Environment]::NewLine)) {
    throw ("R3 biome authoring changed unexpected paths: {0}" -f ($ChangedPaths -join '; '))
}

Write-Host 'PCG_VALLEY + PCG_HIGHALPINE GRAPH AUTHORING OK.' -ForegroundColor Green
exit 0
