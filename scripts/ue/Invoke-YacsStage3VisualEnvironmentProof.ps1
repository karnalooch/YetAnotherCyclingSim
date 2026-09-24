<#
.SYNOPSIS
    Stage 3E Visual Environment Proof for issue #67.

.DESCRIPTION
    Launches the editor with /Game/Prototype/Maps/L_CyclingTest in a
    real rendered PIE viewport at 1920x1080 and runs the dedicated
    CyclingRuntime.Stage3VisualEnvironmentProof automation test, which
    drives the placed ACyclingPrototypePawn to three deterministic
    route distances and emits one PNG per sector:

      01_meadow_valley_1200m.png        (meadow / valley sector)
      02_forest_sector_4900m.png        (forest sector)
      03_high_valley_mountains_8000m.png (high-valley / mountain sector)

    The visual environment is *already* persisted in L_CyclingTest by the
    CyclingStage3RouteSetup commandlet (24 forest cylinder props, 30
    mountain cone props, 1000 road tiles, 200 terrain tiles). This
    harness exists only to provide route-attributable PNG evidence that
    those props are visible from the standard chase camera at the
    documented target resolution.

    The script does NOT mutate the .umap. It launches the editor with the
    existing L_CyclingTest map URL and `-SkipBuild` so it can be re-run
    cheaply after a successful Stage 3E proof.

    Artifacts are written under
    Saved/RuntimeProof/Issue67/Stage3E/VisualEnvironmentProof/
    (gitignored) so they do not collide with the existing
    Performance1080p screenshot.

.PARAMETER RepoRoot
    Absolute path to the YetAnotherCyclingSim repository root.

.PARAMETER ProjectPath
    Absolute path to the .uproject file.

.PARAMETER ArtifactRoot
    Directory under which proof artifacts will be written.

.PARAMETER ExpectedBranch
    Exact branch expected by preflight.

.PARAMETER ExpectedHead
    Exact commit SHA expected by preflight.

.PARAMETER SkipBuild
    Skip the Development Editor build step (assume an existing build is
    already up to date). The default is $true so this script can be
    re-run quickly after a successful Stage 3E proof. Pass -SkipBuild:$false
    to force a rebuild.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [switch] $SkipBuild = [switch]::Present
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) {
    $ProjectPath = Join-Path -Path $RepoRoot -ChildPath 'YetAnotherCyclingSim.uproject'
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/Issue67/Stage3E/VisualEnvironmentProof'
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

Write-Host '=== YACS Stage 3E Visual Environment Proof ===' -ForegroundColor Cyan
Write-Host ('RepoRoot       : {0}' -f $RepoRoot)
Write-Host ('ProjectPath    : {0}' -f $ProjectPath)
Write-Host ('ArtifactRoot   : {0}' -f $ArtifactRoot)
Write-Host ('ExpectedBranch : {0}' -f $ExpectedBranch)
Write-Host ('ExpectedHead   : {0}' -f $ExpectedHead)

# Discover UE install + sanity-check branch/HEAD through the shared
# preflight helper.
$Preflight = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Preflight-YacsProof.ps1'
$PreflightArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $ArtifactRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
    AllowedDirtyPaths = @(
        # Pre-existing branch baseline.
        'Config/DefaultGame.ini',
        'Content/Prototype/Maps/L_CyclingTest.umap',
        '.kilo/',
        'YetAnotherCyclingSim/',
        # Stage 3E visual environment proof fixture:
        'Source/YetAnotherCyclingSim/Public/Cycling/CyclingPrototypePawn.h',
        'Source/YetAnotherCyclingSim/Private/Cycling/CyclingPrototypePawn.cpp',
        'Source/YetAnotherCyclingSim/Private/Tests/CyclingStage3VisualEnvironmentProof.spec.cpp',
        'scripts/ue/Invoke-YacsStage3VisualEnvironmentProof.ps1'
    )
}
$Context = & $Preflight @PreflightArgs
if ($LASTEXITCODE -ne 0) { throw 'Stage 3E visual environment preflight failed.' }

$UEditor = $Context.UnrealEditorPath
if (-not $UEditor) {
    throw 'UnrealEditor.exe (GUI) not resolved by preflight. Cannot launch a rendered PIE viewport.'
}
if (-not (Test-Path -LiteralPath $UEditor)) {
    throw "UnrealEditor.exe not found at '$UEditor'."
}

# --- (0) Optional editor build -------------------------------------------

if (-not $SkipBuild) {
    Write-Host ""
    Write-Host "[0/4] Building YetAnotherCyclingSimEditor (Development)..." -ForegroundColor Cyan
    $BuildLog = Join-Path -Path $ArtifactRoot -ChildPath 'build_editor.log'
    $BuildArgs = @(
        $ProjectPath,
        'YetAnotherCyclingSimEditor',
        'Win64',
        'Development',
        '-WaitMutex',
        '-FromMsBuild'
    )
    $BuildProc = Start-Process -FilePath (Join-Path -Path $Context.EngineRoot -ChildPath 'Engine/Build/BatchFiles/Build.bat') `
        -ArgumentList $BuildArgs -NoNewWindow -PassThru -RedirectStandardOutput $BuildLog `
        -WorkingDirectory (Join-Path -Path $Context.EngineRoot -ChildPath 'Engine/Build/BatchFiles')
    $BuildProc.WaitForExit()
    if ($BuildProc.ExitCode -ne 0) {
        throw "Editor build failed with exit code $($BuildProc.ExitCode); see $BuildLog"
    }
    Write-Host "Editor build OK." -ForegroundColor Green
}

# --- (1) Clean stale proof PNGs from previous runs ----------------------

foreach ($StaleName in @(
    '01_meadow_valley_1200m.png',
    '02_forest_sector_4900m.png',
    '03_high_valley_mountains_8000m.png',
    'visual_environment_report.txt'
)) {
    $StalePath = Join-Path -Path $ArtifactRoot -ChildPath $StaleName
    if (Test-Path -LiteralPath $StalePath) {
        Remove-Item -LiteralPath $StalePath -Force
    }
}

# --- (2) Launch rendered PIE and run the visual environment proof --------

Write-Host ""
Write-Host "[1/4] Launching rendered PIE for visual environment capture..." -ForegroundColor Cyan

$MapArg = '/Game/Prototype/Maps/L_CyclingTest.umap'

# The Stage3VisualEnvironmentProof test reads YACS_VISUAL_ENV_DIR to know
# where to write the PNGs. Set it on this process so the child editor
# inherits it (PowerShell 5.1 Start-Process does not support -Environment).
[System.Environment]::SetEnvironmentVariable('YACS_VISUAL_ENV_DIR', $ArtifactRoot, 'Process')

# Single deterministic execcmds string. The test itself is latent and
# ends with a `Quit` so the harness returns deterministically.
$ExeccmdsValue = 'Automation RunTests CyclingRuntime.Stage3VisualEnvironmentProof;Quit'

$AbsLog = Join-Path -Path $ArtifactRoot -ChildPath 'editor_session_visual_environment.log'
if (Test-Path -LiteralPath $AbsLog) { Remove-Item -LiteralPath $AbsLog -Force }

$EditorArgs = @(
    $ProjectPath,
    $MapArg,
    '-game',
    '-windowed',
    '-ResX=1920',
    '-ResY=1080',
    '-NoVSync',
    '-FixedSeed',
    '-NoSplash',
    '-log',
    '-unattended',
    '-stdout',
    ('-AbsLog=' + $AbsLog),
    ('-execcmds="' + $ExeccmdsValue + '"')
)

# Total wall-clock budget. The test sequences roughly:
#   Prepare + (Teleport + 1.5s wait + screenshot + 2.0s wait) x 3
# ~= 12s plus the editor startup. 180s is a generous safe cap.
$TimeoutSec = 180

$Proc = Start-Process -FilePath $UEditor -ArgumentList $EditorArgs `
    -NoNewWindow -PassThru -RedirectStandardOutput $AbsLog `
    -WorkingDirectory $RepoRoot
Write-Host ("Launched editor pid={0}; waiting up to {1} s..." -f $Proc.Id, $TimeoutSec)

if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
    try { $Proc | Stop-Process -Force } catch { }
    throw "Visual environment proof editor did not finish within $TimeoutSec seconds. See $AbsLog."
}
Write-Host ("Editor exit code: {0}" -f $Proc.ExitCode)

# --- (3) Validate launch evidence ---------------------------------------

$EditorLogText = if (Test-Path -LiteralPath $AbsLog) {
    Get-Content -LiteralPath $AbsLog -Raw -ErrorAction SilentlyContinue
} else { '' }
$LoadedExpected  = $EditorLogText -match 'L_CyclingTest'
$LoadedTemplate  = $EditorLogText -match 'Templates/OpenWorld' -or $EditorLogText -match 'OpenWorld'

# Count the deterministic teleport log lines so we know the test reached
# each proof sector.
$TeleportLines = ([regex]::Matches($EditorLogText, 'TeleportForProofCapture: requested=')).Count

$PngPaths = @(
    (Join-Path -Path $ArtifactRoot -ChildPath '01_meadow_valley_1200m.png'),
    (Join-Path -Path $ArtifactRoot -ChildPath '02_forest_sector_4900m.png'),
    (Join-Path -Path $ArtifactRoot -ChildPath '03_high_valley_mountains_8000m.png')
)
$PngInfo = foreach ($P in $PngPaths) {
    [ordered]@{
        Path = $P
        Exists = (Test-Path -LiteralPath $P)
        SizeBytes = if (Test-Path -LiteralPath $P) { (Get-Item -LiteralPath $P).Length } else { 0 }
    }
}

# --- (4) Write a human-readable report ----------------------------------

$ReportPath = Join-Path -Path $ArtifactRoot -ChildPath 'visual_environment_report.txt'
$ReportLines = @(
    ('TimestampUtc         : {0}' -f (Get-Date).ToUniversalTime().ToString('o')),
    ('RepoRoot             : {0}' -f $RepoRoot),
    ('ProjectPath          : {0}' -f $ProjectPath),
    ('Branch               : {0}' -f $Context.Branch),
    ('Head                 : {0}' -f $Context.Head),
    ('Editor               : {0}' -f $UEditor),
    ('EditorExitCode       : {0}' -f $Proc.ExitCode),
    ('EditorLogLoadedExpected : {0}' -f [bool]$LoadedExpected),
    ('EditorLogLoadedTemplate : {0}' -f [bool]$LoadedTemplate),
    ('TeleportForProofCapture lines observed : {0}' -f $TeleportLines),
    ''
)
foreach ($info in $PngInfo) {
    $ReportLines += ('PNG: {0} exists={1} size={2}' -f $info.Path, $info.Exists, $info.SizeBytes)
}
Set-Content -LiteralPath $ReportPath -Value $ReportLines -Encoding UTF8

Write-Host ""
Write-Host "[2/4] Editor session summary" -ForegroundColor Cyan
Write-Host ("Map loaded           : expected={0} template-fallback={1}" -f [bool]$LoadedExpected, [bool]$LoadedTemplate)
Write-Host ("Teleport lines       : {0}" -f $TeleportLines)
foreach ($info in $PngInfo) {
    Write-Host ("PNG: {0} (exists={1}, size={2})" -f $info.Path, $info.Exists, $info.SizeBytes)
}

# --- (5) Exit policy ----------------------------------------------------

Write-Host ""
Write-Host "[3/4] Visual environment proof exit policy..." -ForegroundColor Cyan

$HardFail = $false
$Reasons  = @()
if (-not $LoadedExpected) { $HardFail = $true; $Reasons += "editor log does not confirm L_CyclingTest was loaded" }
if ($LoadedTemplate)      { $HardFail = $true; $Reasons += "editor log shows OpenWorld template fallback" }
if ($TeleportLines -lt 3) { $HardFail = $true; $Reasons += ("expected at least 3 'TeleportForProofCapture:' log lines (one per sector); saw {0}" -f $TeleportLines) }
foreach ($info in $PngInfo) {
    if (-not $info.Exists) {
        $HardFail = $true
        $Reasons += ("missing PNG: {0}" -f $info.Path)
    }
    elseif ($info.SizeBytes -lt 4096) {
        $HardFail = $true
        $Reasons += ("PNG suspiciously small ({0} bytes): {1}" -f $info.SizeBytes, $info.Path)
    }
}

$Summary = [ordered]@{
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $ArtifactRoot
    EngineRoot = $Context.EngineRoot
    Branch = $Context.Branch
    Head = $Context.Head
    MapUrl = $MapArg
    Editor = $UEditor
    EditorExitCode = $Proc.ExitCode
    EditorLogLoadedExpected = [bool]$LoadedExpected
    EditorLogLoadedTemplate = [bool]$LoadedTemplate
    TeleportLineCount = $TeleportLines
    Screenshots = $PngInfo
}
$Summary | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path -Path $ArtifactRoot -ChildPath 'visual_environment_summary.json') -Encoding UTF8

Write-Host ""
Write-Host "[4/4] Summary written" -ForegroundColor Cyan
if ($HardFail) {
    Write-Host ""
    Write-Host "VISUAL ENVIRONMENT PROOF FAILED:" -ForegroundColor Red
    foreach ($r in $Reasons) { Write-Host ("  - {0}" -f $r) -ForegroundColor Red }
    Write-Host ("See {0} for full editor log." -f $AbsLog)
    exit 1
}

Write-Host ""
Write-Host "VISUAL ENVIRONMENT PROOF PASSED." -ForegroundColor Green
exit 0