<#
.SYNOPSIS
    Profile the curated Stage 3G R2 Fir Tree 01 candidate on the trusted UE runner.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [string] $ExpectedBranch = 'HEAD',
    [int] $TimeoutSec = 1200
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) {
    $ProjectPath = Join-Path -Path $RepoRoot -ChildPath 'YetAnotherCyclingSim.uproject'
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/CI/Stage3GR2/FirProfile'
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
    throw 'Stage 3G R2 fir profiling build/Automation canary failed.'
}

$Preflight = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) {
    throw 'Stage 3G R2 fir profiling preflight failed.'
}

$DownloadScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/assets/download_stage3g_assets.py'
$ProfileScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/stage3g_profile_fir_tree.py'
$AssetCache = Join-Path -Path $RepoRoot -ChildPath 'ExternalAssets/Stage3G/PolyHaven'
$ProfileJson = Join-Path -Path $ArtifactRoot -ChildPath 'fir_tree_01_profile.json'
$ProfileLog = Join-Path -Path $ArtifactRoot -ChildPath 'fir_tree_01_profile.log'

Write-Host '[1/2] Downloading curated fir_tree_01 source set...' -ForegroundColor Cyan
& python $DownloadScript --destination $AssetCache --asset fir_tree_01 --max-total-mib 3072
if ($LASTEXITCODE -ne 0) {
    throw 'Fir Tree 01 source download failed.'
}

$IndexPath = Join-Path -Path $AssetCache -ChildPath 'download-index.json'
if (-not (Test-Path -LiteralPath $IndexPath -PathType Leaf)) {
    throw 'Fir Tree 01 download index is missing.'
}
$Index = Get-Content -LiteralPath $IndexPath -Raw -ErrorAction Stop | ConvertFrom-Json
$FirRows = @($Index.files | Where-Object { $_.asset_id -eq 'fir_tree_01' })
$FirGeometry = @($FirRows | Where-Object { $null -eq $_.map_type -and $_.relative_path -match '(?i)\.fbx$' })
if ($FirGeometry.Count -le 0) {
    throw 'Fir Tree 01 download index contains no FBX geometry.'
}

Write-Host '[2/2] Profiling Fir Tree 01 meshes in Unreal...' -ForegroundColor Cyan
$env:YACS_STAGE3G_ASSET_CACHE = $AssetCache
$env:YACS_STAGE3G_FIR_PROFILE = $ProfileJson
try {
    $Arguments = @(
        $ProjectPath
        '-run=PythonScript'
        ('-script="' + $ProfileScript + '"')
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
        throw "Fir Tree 01 profiling timed out; see $ProfileLog"
    }
    if ($Proc.ExitCode -ne 0) {
        throw "Fir Tree 01 profiling failed with exit code $($Proc.ExitCode); see $ProfileLog"
    }
}
finally {
    Remove-Item Env:YACS_STAGE3G_ASSET_CACHE -ErrorAction SilentlyContinue
    Remove-Item Env:YACS_STAGE3G_FIR_PROFILE -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $ProfileJson -PathType Leaf)) {
    throw 'Fir Tree 01 profiling proof JSON is missing.'
}
$Profile = Get-Content -LiteralPath $ProfileJson -Raw -ErrorAction Stop | ConvertFrom-Json
if ($Profile.stage3g_r2_fir_profile -ne 'success') {
    throw 'Fir Tree 01 profiling did not report success.'
}
if ([int]$Profile.source_fbx_count -le 0 -or [int]$Profile.mesh_count -le 0) {
    throw 'Fir Tree 01 profiling returned no source FBX or mesh records.'
}
$TotalTriangles = 0
foreach ($Mesh in @($Profile.meshes)) {
    if (@($Mesh.lods).Count -le 0) {
        throw "Profiled mesh '$($Mesh.mesh_name)' has no LOD records."
    }
    $TotalTriangles += [int]$Mesh.lods[0].triangles
}
if ($TotalTriangles -le 0) {
    throw 'Fir Tree 01 profiling returned zero total LOD0 triangles.'
}

Push-Location -LiteralPath $RepoRoot
try {
    $Dirty = @(git status --porcelain=v1 --untracked-files=all)
}
finally {
    Pop-Location
}
if ($Dirty.Count -gt 0) {
    throw ("Fir Tree profiling mutated repository source paths: {0}" -f ($Dirty -join '; '))
}

Write-Host ("FIR TREE PROFILE OK: sources={0} meshes={1} total_lod0_triangles={2}" -f $Profile.source_fbx_count, $Profile.mesh_count, $TotalTriangles) -ForegroundColor Green
exit 0
