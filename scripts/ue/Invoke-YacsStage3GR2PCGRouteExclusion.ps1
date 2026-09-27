<#
.SYNOPSIS
    Build, author and validate the Stage 3G R2 PCG_RouteExclusion asset.
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
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/CI/Stage3GR2/PCGRouteExclusion'
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
    throw 'Stage 3G R2 PCG route-exclusion build/Automation canary failed.'
}

$Preflight = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) {
    throw 'Stage 3G R2 PCG route-exclusion preflight failed.'
}

$AuthorScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/stage3g_author_pcg_route_exclusion.py'
$ProofJson = Join-Path -Path $ArtifactRoot -ChildPath 'pcg_route_exclusion_proof.json'
$AuthorLog = Join-Path -Path $ArtifactRoot -ChildPath 'pcg_route_exclusion_authoring.log'
$ErrLog = $AuthorLog + '.stderr'
$AssetRelativePath = 'Content/YACS/WorldGen/PCG/PCG_RouteExclusion.uasset'
$AssetDiskPath = Join-Path -Path $RepoRoot -ChildPath $AssetRelativePath

Remove-Item -LiteralPath $ProofJson -Force -ErrorAction SilentlyContinue
$env:YACS_STAGE3G_R2_PCG_ROUTE_EXCLUSION_PROOF = $ProofJson
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
        throw "PCG_RouteExclusion authoring timed out; see $AuthorLog"
    }
    if ($Proc.ExitCode -ne 0) {
        throw "PCG_RouteExclusion authoring failed with exit code $($Proc.ExitCode); see $AuthorLog"
    }
}
finally {
    Remove-Item Env:YACS_STAGE3G_R2_PCG_ROUTE_EXCLUSION_PROOF -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $ProofJson -PathType Leaf)) {
    throw 'PCG_RouteExclusion proof JSON is missing.'
}
$Proof = Get-Content -LiteralPath $ProofJson -Raw -ErrorAction Stop | ConvertFrom-Json
if ($Proof.stage3g_r2_pcg_route_exclusion -ne 'success') {
    throw 'PCG_RouteExclusion proof did not report success.'
}
if ($Proof.asset_path -ne '/Game/YACS/WorldGen/PCG/PCG_RouteExclusion') {
    throw "Unexpected PCG_RouteExclusion asset path: $($Proof.asset_path)"
}
if ([math]::Abs([double]$Proof.protected_half_width_m - 4.0) -gt 1e-9) {
    throw "Unexpected route exclusion half-width: $($Proof.protected_half_width_m)"
}
if ($Proof.route_truth -ne 'FRouteGeometryProfile') {
    throw "Unexpected route truth in proof: $($Proof.route_truth)"
}
if (-not (Test-Path -LiteralPath $AssetDiskPath -PathType Leaf)) {
    throw "Authored PCG_RouteExclusion asset is missing: $AssetRelativePath"
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
    throw ("PCG route-exclusion authoring changed unexpected paths: {0}" -f ($Unexpected -join '; '))
}

Write-Host 'PCG_ROUTE_EXCLUSION AUTHORING OK.' -ForegroundColor Green
exit 0
