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
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null

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
$PythonScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/stage3g_author_materials.py'
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

Write-Host '[1/3] Authoring Stage 3G materials...' -ForegroundColor Cyan
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

$MaterialText = Get-Content -LiteralPath $MaterialLog -Raw -ErrorAction Stop
if ($MaterialText -notmatch 'SUCCESS: authored 5 Stage 3G material pairs') {
    throw 'Stage 3G material success marker missing.'
}

Write-Host '[2/3] Authoring Stage 3G lighting / atmosphere...' -ForegroundColor Cyan
$WorldScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/stage3g_author_world.py'
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
$WorldText = Get-Content -LiteralPath $WorldLog -Raw -ErrorAction Stop
if ($WorldText -notmatch 'Stage3GWorld.*SUCCESS') {
    throw 'Stage 3G world-authoring success marker missing.'
}

Write-Host '[3/3] Rebuilding and saving Stage 3 reference environment...' -ForegroundColor Cyan
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
if ($SetupText -notmatch 'valley_ridges=32 forest_canopy=100 distant_mountains=28 water_tiles=26') {
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
if ($AuthoredAssets.Count -lt 10) {
    throw "Stage 3G authoring expected at least 10 authored .uasset files on disk; found $($AuthoredAssets.Count)."
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
