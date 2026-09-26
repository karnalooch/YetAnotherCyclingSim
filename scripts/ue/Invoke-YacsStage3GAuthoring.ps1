<#
.SYNOPSIS
    Author Stage 3G materials and persist the regenerated reference environment.

.DESCRIPTION
    Runs the Stage 3G Unreal Python material authoring script and then the
    existing CyclingStage3RouteSetup commandlet, which rebuilds the deterministic
    presentation actor and saves L_CyclingTest.umap.

    This intentionally runs only on a machine with the real Unreal Editor.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [int] $TimeoutSec = 240
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) {
    $ProjectPath = Join-Path -Path $RepoRoot -ChildPath 'YetAnotherCyclingSim.uproject'
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/Issue80/Stage3G/Authoring'
}
# Caller-supplied proof roots are repo-relative by contract. Do not let the
# current PowerShell cwd leak into Unreal authoring provenance.
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath $ArtifactRoot
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
# Unreal Python commandlets do not guarantee the repository as their process cwd.
# Canonicalize the proof root before passing any paths through the environment.
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$Preflight = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) { throw 'Stage 3G preflight failed.' }

# A clean self-hosted workspace intentionally has no trusted Binaries/Intermediate
# state after cleanup. Prove the exact Stage 3G revision can build before any
# authoring mutation occurs, using the hardened conservative UBT profile.
$CiEntry = Join-Path -Path $RepoRoot -ChildPath 'scripts/ci/Invoke-YacsUnrealCi.ps1'
$PreAuthoringCanary = Join-Path -Path $ArtifactRoot -ChildPath 'PreAuthoringCanary'
& $CiEntry -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $PreAuthoringCanary -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) {
    throw 'Stage 3G pre-authoring build/Automation canary failed.'
}

$EditorCmd = $Context.UnrealEditorCmdPath
$DownloadScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/assets/download_stage3g_assets.py'
$ImportScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/stage3g_import_source_assets.py'
$PythonScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/stage3g_author_materials.py'
$AssetCache = Join-Path -Path $RepoRoot -ChildPath 'ExternalAssets/Stage3G/PolyHaven'
$ImportLog = Join-Path -Path $ArtifactRoot -ChildPath 'stage3g_asset_import.log'
$ImportProof = Join-Path -Path $ArtifactRoot -ChildPath 'stage3g_asset_import_proof.json'
$MaterialLog = Join-Path -Path $ArtifactRoot -ChildPath 'stage3g_material_authoring.log'
$WorldLog = Join-Path -Path $ArtifactRoot -ChildPath 'stage3g_world_authoring.log'
$SetupLog = Join-Path -Path $ArtifactRoot -ChildPath 'stage3g_route_world_setup.log'

function Invoke-UEProcess {
    param(
        [Parameter(Mandatory=$true)] [string[]] $Arguments,
        [Parameter(Mandatory=$true)] [string] $LogPath
    )
    $ErrPath = $LogPath + '.stderr'
    $Proc = Start-Process -FilePath $EditorCmd -ArgumentList $Arguments -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $LogPath -RedirectStandardError $ErrPath
    if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
        try { $Proc | Stop-Process -Force } catch { }
        throw "Unreal process timed out; see $LogPath"
    }
    $ExitCode = $Proc.ExitCode
    if ($null -eq $ExitCode) {
        if (Test-Path -LiteralPath $LogPath) { $ExitCode = 0 } else { $ExitCode = 1 }
    }
    if ($ExitCode -ne 0) {
        throw "Unreal process failed with exit code $ExitCode; see $LogPath"
    }
}

Write-Host '[1/5] Downloading curated Stage 3G R1 source assets...' -ForegroundColor Cyan
$DownloadArgs = @(
    $DownloadScript
    '--destination'
    $AssetCache
    '--asset'
    'sparse_grass'
    '--asset'
    'forrest_ground_03'
    '--asset'
    'rocky_terrain'
    '--asset'
    'boulder_01'
    '--max-total-mib'
    '1536'
)
& python @DownloadArgs
if ($LASTEXITCODE -ne 0) {
    throw 'Stage 3G source-asset download failed.'
}
$DownloadIndex = Join-Path -Path $AssetCache -ChildPath 'download-index.json'
if (-not (Test-Path -LiteralPath $DownloadIndex -PathType Leaf)) {
    throw 'Stage 3G source-asset download index is missing.'
}

Write-Host '[2/5] Importing canonical Stage 3G R1 assets into Unreal...' -ForegroundColor Cyan
Remove-Item -LiteralPath $ImportProof -Force -ErrorAction SilentlyContinue
$env:YACS_STAGE3G_ASSET_CACHE = $AssetCache
$env:YACS_STAGE3G_IMPORT_PROOF = $ImportProof
try {
    Invoke-UEProcess -LogPath $ImportLog -Arguments @(
        $ProjectPath
        '-run=PythonScript'
        ('-script="' + $ImportScript + '"')
        '-Unattended'
        '-NoPause'
        '-NullRHI'
        '-NoSplash'
        '-NoP4'
        '-log'
    )
}
finally {
    Remove-Item Env:YACS_STAGE3G_ASSET_CACHE -ErrorAction SilentlyContinue
    Remove-Item Env:YACS_STAGE3G_IMPORT_PROOF -ErrorAction SilentlyContinue
}
if (-not (Test-Path -LiteralPath $ImportProof -PathType Leaf)) {
    throw 'Stage 3G source-asset import proof is missing.'
}
$ImportEvidence = Get-Content -LiteralPath $ImportProof -Raw -ErrorAction Stop | ConvertFrom-Json
if ($ImportEvidence.stage3g_asset_import -ne 'success' -or [int]$ImportEvidence.imported_count -ne 13) {
    throw 'Stage 3G source-asset import proof is incomplete.'
}

$ExpectedImportedAssets = @(
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_Meadow_BaseColor.uasset'
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_Meadow_Normal.uasset'
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_Meadow_Roughness.uasset'
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_ForestGround_BaseColor.uasset'
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_ForestGround_Normal.uasset'
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_ForestGround_Roughness.uasset'
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_HighAlpine_BaseColor.uasset'
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_HighAlpine_Normal.uasset'
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_HighAlpine_Roughness.uasset'
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_Boulder_BaseColor.uasset'
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_Boulder_Normal.uasset'
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_Boulder_Roughness.uasset'
    'Content/Prototype/Environment/Stage3G/Imported/Meshes/SM_Stage3G_Boulder.uasset'
)
$MissingImportedAssets = @(
    $ExpectedImportedAssets | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path -Path $RepoRoot -ChildPath $_) -PathType Leaf)
    }
)
if ($MissingImportedAssets.Count -gt 0) {
    throw ("Stage 3G import did not produce expected canonical assets: {0}" -f ($MissingImportedAssets -join ', '))
}
Write-Host ("Stage 3G R1 source asset import: PASS ({0} assets)." -f $ExpectedImportedAssets.Count) -ForegroundColor Green

Write-Host '[3/5] Authoring Stage 3G texture-backed materials...' -ForegroundColor Cyan
Invoke-UEProcess -LogPath $MaterialLog -Arguments @(
    $ProjectPath
    '-run=PythonScript'
    ('-script="' + $PythonScript + '"')
    '-Unattended'
    '-NoPause'
    '-NullRHI'
    '-NoSplash'
    '-NoP4'
    '-log'
)

$ExpectedMaterialAssets = @(
    'M_Stage3G_Grass.uasset',
    'MI_Stage3G_Grass.uasset',
    'M_Stage3G_Forest.uasset',
    'MI_Stage3G_Forest.uasset',
    'M_Stage3G_Rock.uasset',
    'MI_Stage3G_Rock.uasset',
    'M_Stage3G_DistantRock.uasset',
    'MI_Stage3G_DistantRock.uasset',
    'M_Stage3G_Foliage.uasset',
    'MI_Stage3G_Foliage.uasset',
    'M_Stage3G_Water.uasset',
    'MI_Stage3G_Water.uasset'
)
$MaterialDir = Join-Path -Path $RepoRoot -ChildPath 'Content/Prototype/Environment/Stage3G/Materials'
$MissingMaterialAssets = @(
    $ExpectedMaterialAssets | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path -Path $MaterialDir -ChildPath $_) -PathType Leaf)
    }
)
if ($MissingMaterialAssets.Count -gt 0) {
    throw ("Stage 3G material authoring did not produce expected assets: {0}" -f ($MissingMaterialAssets -join ', '))
}
Write-Host ("Stage 3G material authoring outputs: PASS ({0} assets)." -f $ExpectedMaterialAssets.Count) -ForegroundColor Green

Write-Host '[4/5] Authoring Stage 3G lighting / atmosphere...' -ForegroundColor Cyan
$WorldScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/stage3g_author_world.py'
$WorldProof = Join-Path -Path $ArtifactRoot -ChildPath 'stage3g_world_authoring_proof.txt'
Remove-Item -LiteralPath $WorldProof -Force -ErrorAction SilentlyContinue
$env:YACS_STAGE3G_WORLD_PROOF = $WorldProof
try {
    Invoke-UEProcess -LogPath $WorldLog -Arguments @(
        $ProjectPath
        '-run=PythonScript'
        ('-script="' + $WorldScript + '"')
        '-Unattended'
        '-NoPause'
        '-NullRHI'
        '-NoSplash'
        '-NoP4'
        '-log'
    )
}
finally {
    Remove-Item Env:YACS_STAGE3G_WORLD_PROOF -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $WorldProof -PathType Leaf)) {
    throw 'Stage 3G world authoring proof file is missing.'
}
$WorldProofLines = @(Get-Content -LiteralPath $WorldProof -ErrorAction Stop)
$ExpectedWorldProofLines = @(
    'stage3g_world_authoring=success',
    'sun_intensity=8.0',
    'sky_intensity=0.75',
    'fog_density=0.0065',
    'fog_height_falloff=0.18',
    'fog_max_opacity=0.55'
)
$MissingWorldProofLines = @(
    $ExpectedWorldProofLines | Where-Object { $WorldProofLines -notcontains $_ }
)
if ($MissingWorldProofLines.Count -gt 0) {
    throw ("Stage 3G world authoring proof is incomplete: {0}" -f ($MissingWorldProofLines -join ', '))
}
Write-Host 'Stage 3G world authoring proof: PASS.' -ForegroundColor Green

Write-Host '[5/5] Rebuilding and saving Stage 3 reference environment...' -ForegroundColor Cyan
Invoke-UEProcess -LogPath $SetupLog -Arguments @(
    $ProjectPath
    '-run=CyclingStage3RouteSetup'
    '-Unattended'
    '-NoPause'
    '-NullRHI'
    '-NoSplash'
    '-NoP4'
    '-log'
)

$SetupText = Get-Content -LiteralPath $SetupLog -Raw -ErrorAction Stop
if ($SetupText -notmatch 'CyclingStage3RouteSetupCommandlet: done') {
    throw 'Stage 3 route/world setup completion marker missing.'
}
if ($SetupText -notmatch 'valley_ridges=32 forest_canopy=100 distant_mountains=28 rock_props=40 water_tiles=26') {
    throw 'Stage 3G deterministic instance-count marker missing.'
}

# Fail closed on source-tree mutations. The authoring pass may only create the
# Stage 3G environment assets and update the canonical Stage 3 map.
Push-Location -LiteralPath $RepoRoot
try {
    $StatusLines = @(git status --porcelain=v1 --untracked-files=all)
}
finally {
    Pop-Location
}

$ChangedPaths = [System.Collections.Generic.List[string]]::new()
foreach ($Line in $StatusLines) {
    if (-not $Line -or $Line.Length -lt 4) { continue }
    $Path = $Line.Substring(3).Trim()
    if ($Path -match ' -> ') {
        $Path = ($Path -split ' -> ')[-1].Trim()
    }
    [void]$ChangedPaths.Add($Path)
}

$AllowedAssetPrefix = 'Content/Prototype/Environment/Stage3G/'
$AllowedMap = 'Content/Prototype/Maps/L_CyclingTest.umap'
$Unexpected = @(
    $ChangedPaths | Where-Object {
        $_ -ne $AllowedMap -and -not $_.StartsWith($AllowedAssetPrefix)
    }
)
if ($Unexpected.Count -gt 0) {
    throw ("Stage 3G authoring changed unexpected source paths: {0}" -f ($Unexpected -join ', '))
}

$AuthoredAssetDir = Join-Path -Path $RepoRoot -ChildPath 'Content/Prototype/Environment/Stage3G/Materials'
$AuthoredAssets = @(
    Get-ChildItem -LiteralPath $AuthoredAssetDir -Filter '*.uasset' -File -ErrorAction SilentlyContinue
)
if ($AuthoredAssets.Count -lt 12) {
    throw "Stage 3G authoring expected at least 12 authored material .uasset files on disk; found $($AuthoredAssets.Count)."
}
$AuthoredMapPath = Join-Path -Path $RepoRoot -ChildPath $AllowedMap
if (-not (Test-Path -LiteralPath $AuthoredMapPath -PathType Leaf)) {
    throw "Stage 3G authoring required map is missing: $AllowedMap"
}

$ChangesManifest = Join-Path -Path $ArtifactRoot -ChildPath 'stage3g_authored_changes.txt'
$ChangedPaths | Sort-Object | Set-Content -LiteralPath $ChangesManifest -Encoding UTF8
Write-Host ("Stage 3G source mutation guard: PASS ({0} paths)." -f $ChangedPaths.Count) -ForegroundColor Green

Write-Host 'STAGE 3G AUTHORING OK.' -ForegroundColor Green
exit 0
