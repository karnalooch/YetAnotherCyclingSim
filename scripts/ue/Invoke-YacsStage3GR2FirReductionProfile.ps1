<#
.SYNOPSIS
    Measure transient Fir Tree 01 LOD reduction chains on the trusted UE 5.8 runner.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [string] $ExpectedBranch = 'HEAD',
    [int] $TimeoutSec = 2400
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

if (-not $ProjectPath) {
    $ProjectPath = Join-Path -Path $RepoRoot -ChildPath 'YetAnotherCyclingSim.uproject'
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path

if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/CI/Stage3GR2/FirReduction'
}
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath $ArtifactRoot
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$CiEntry = Join-Path -Path $RepoRoot -ChildPath 'scripts/ci/Invoke-YacsUnrealCi.ps1'
$CanaryRoot = Join-Path -Path $ArtifactRoot -ChildPath 'Canary'
$CiArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $CanaryRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
    TestFilter = 'CyclingStage3World'
}
& $CiEntry @CiArgs
if ($LASTEXITCODE -ne 0) {
    throw 'Stage 3G R2 reduction profiling build/Automation canary failed.'
}

$Preflight = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Preflight-YacsProof.ps1'
$PreflightArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $ArtifactRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
}
$Context = & $Preflight @PreflightArgs
if ($LASTEXITCODE -ne 0) {
    throw 'Stage 3G R2 reduction profiling preflight failed.'
}

$DownloadScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/assets/download_stage3g_assets.py'
$ReductionScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/stage3g_profile_fir_reduction.py'
$AssetCache = Join-Path -Path $RepoRoot -ChildPath 'ExternalAssets/Stage3G/PolyHaven'
$ProofJson = Join-Path -Path $ArtifactRoot -ChildPath 'fir_tree_01_reduction_profile.json'
$ProfileLog = Join-Path -Path $ArtifactRoot -ChildPath 'fir_tree_01_reduction_profile.log'

Write-Host '[1/2] Downloading curated Fir Tree 01 source...' -ForegroundColor Cyan
$DownloadArgs = @(
    $DownloadScript,
    '--destination',
    $AssetCache,
    '--asset',
    'fir_tree_01',
    '--max-total-mib',
    '3072'
)
& python @DownloadArgs
if ($LASTEXITCODE -ne 0) {
    throw 'Fir Tree 01 source download failed.'
}

$IndexPath = Join-Path -Path $AssetCache -ChildPath 'download-index.json'
if (-not (Test-Path -LiteralPath $IndexPath -PathType Leaf)) {
    throw 'Fir Tree 01 download index is missing.'
}

Write-Host '[2/2] Generating and measuring transient LOD chains in UE 5.8...' -ForegroundColor Cyan
Remove-Item -LiteralPath $ProofJson -Force -ErrorAction SilentlyContinue
$env:YACS_STAGE3G_ASSET_CACHE = $AssetCache
$env:YACS_STAGE3G_FIR_REDUCTION = $ProofJson
try {
    $Arguments = @(
        $ProjectPath
        '-run=PythonScript'
        ('-script="' + $ReductionScript + '"')
        '-Unattended'
        '-NoPause'
        '-NullRHI'
        '-NoSplash'
        '-NoP4'
        '-log'
    )
    $ErrPath = $ProfileLog + '.stderr'
    $Proc = Start-Process -FilePath $Context.UnrealEditorCmdPath -ArgumentList $Arguments -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $ProfileLog -RedirectStandardError $ErrPath

    if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
        try { $Proc | Stop-Process -Force } catch { }
        throw "Fir Tree reduction profiling timed out; see $ProfileLog"
    }
    if ($Proc.ExitCode -ne 0) {
        Write-Host ''
        Write-Host '===== FIR TREE REDUCTION UE LOG TAIL =====' -ForegroundColor Red
        if (Test-Path -LiteralPath $ProfileLog -PathType Leaf) {
            Get-Content -LiteralPath $ProfileLog -Tail 180 -ErrorAction SilentlyContinue |
                ForEach-Object { Write-Host $_ }
        }
        if (Test-Path -LiteralPath $ErrPath -PathType Leaf) {
            Write-Host ''
            Write-Host '===== FIR TREE REDUCTION STDERR TAIL =====' -ForegroundColor Red
            Get-Content -LiteralPath $ErrPath -Tail 80 -ErrorAction SilentlyContinue |
                ForEach-Object { Write-Host $_ }
        }
        throw "Fir Tree reduction profiling failed with exit code $($Proc.ExitCode); see $ProfileLog"
    }
}
finally {
    Remove-Item Env:YACS_STAGE3G_ASSET_CACHE -ErrorAction SilentlyContinue
    Remove-Item Env:YACS_STAGE3G_FIR_REDUCTION -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $ProofJson -PathType Leaf)) {
    throw 'Fir Tree reduction proof JSON is missing.'
}
$Proof = Get-Content -LiteralPath $ProofJson -Raw -ErrorAction Stop | ConvertFrom-Json

if ($Proof.stage3g_r2_fir_reduction_profile -ne 'success') {
    throw 'Fir Tree reduction profile did not report success.'
}
if ($Proof.source_mesh -ne 'fir_tree_01_c_LOD0') {
    throw "Unexpected selected Fir Tree source mesh: $($Proof.source_mesh)"
}

$ExpectedProfiles = @('conservative', 'balanced', 'aggressive')
foreach ($ProfileName in $ExpectedProfiles) {
    $Candidate = $Proof.profiles.$ProfileName
    if ($null -eq $Candidate) {
        throw "Missing Fir Tree reduction candidate: $ProfileName"
    }

    $Actual = @($Candidate.actual)
    if ($Actual.Count -ne 4) {
        throw "$ProfileName produced $($Actual.Count) LODs; expected 4."
    }

    for ($Index = 1; $Index -lt $Actual.Count; ++$Index) {
        if ([int]$Actual[$Index].triangles -ge [int]$Actual[$Index - 1].triangles) {
            throw "$ProfileName triangles are not strictly decreasing at LOD $Index."
        }
    }
}

if ([int]$Proof.source_lod0_triangles -le 100000) {
    throw 'Fir Tree source LOD0 unexpectedly falls below the profiling floor.'
}

Push-Location -LiteralPath $RepoRoot
try {
    $Dirty = @(git status --porcelain=v1 --untracked-files=all)
}
finally {
    Pop-Location
}
if ($Dirty.Count -gt 0) {
    throw ("Fir Tree reduction profiling mutated repository source paths: {0}" -f ($Dirty -join '; '))
}

foreach ($ProfileName in $ExpectedProfiles) {
    $Actual = @($Proof.profiles.$ProfileName.actual)
    $Summary = $Actual | ForEach-Object { "LOD$($_.lod)=$($_.triangles)" }
    Write-Host ("{0}: {1}" -f $ProfileName, ($Summary -join ', ')) -ForegroundColor Green
}

Write-Host 'FIR TREE REDUCTION PROFILE OK.' -ForegroundColor Green
exit 0
