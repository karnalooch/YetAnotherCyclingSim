<#
.SYNOPSIS
    Top-level Stage 3E completion proof for YetAnotherCyclingSim.

.DESCRIPTION
    Runs the complete Stage 3 validation chain on a dedicated worktree:

      1. Development Editor build + Automation, including Stage 3 route,
         runtime, prototype-world and 200 W full-route regression suites.
      2. Stage 3 route/world setup commandlet twice, proving idempotent
         deterministic generation and persisting L_CyclingTest.
      3. Fresh-process route/world verifier, proving save/reopen persistence.
      4. Editor Map Check for L_CyclingTest.
      5. Rendered 1920x1080 performance/PIE sanity using the existing
         Unreal Insights harness.

    The setup step intentionally modifies Content/Prototype/Maps/
    L_CyclingTest.umap in the dedicated Stage 3E worktree. All other proof
    artifacts live below Saved/RuntimeProof/Issue67/Stage3E.

.PARAMETER ExpectedBranch
    Exact branch expected by preflight.

.PARAMETER ExpectedHead
    Exact commit SHA expected by preflight before the generated map is saved.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [switch] $SkipBuild,
    [switch] $SkipPerformance
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) {
    $ProjectPath = Join-Path -Path $RepoRoot -ChildPath 'YetAnotherCyclingSim.uproject'
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/Issue67/Stage3E'
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$AutomationRoot = Join-Path -Path $ArtifactRoot -ChildPath 'Automation'
$Setup1Log = Join-Path -Path $ArtifactRoot -ChildPath 'route_world_setup_1.log'
$Setup2Log = Join-Path -Path $ArtifactRoot -ChildPath 'route_world_setup_2.log'
$VerifyLog = Join-Path -Path $ArtifactRoot -ChildPath 'route_world_verify.log'
$MapCheckLog = Join-Path -Path $ArtifactRoot -ChildPath 'map_check.log'
$PerformanceRoot = Join-Path -Path $ArtifactRoot -ChildPath 'Performance1080p'
New-Item -ItemType Directory -Path $AutomationRoot -Force | Out-Null

Write-Host '=== YACS Stage 3E proof ===' -ForegroundColor Cyan
Write-Host ('RepoRoot       : {0}' -f $RepoRoot)
Write-Host ('ExpectedBranch : {0}' -f $ExpectedBranch)
Write-Host ('ExpectedHead   : {0}' -f $ExpectedHead)
Write-Host ('ArtifactRoot   : {0}' -f $ArtifactRoot)

# ----------------------------------------------------------------------
# 1. Build + complete Automation before touching the binary map.
# ----------------------------------------------------------------------

$BaseProof = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Invoke-YacsProof.ps1'
$TestFilter = 'CyclingPhysics+CyclingSession+CyclingInput+CyclingRuntime+CyclingDiagnostics+CyclingRouteContext+CyclingRouteProfile+CyclingRouteGeometry+CyclingStage3Runtime+CyclingStage3World+CyclingStage3FullRoute'

Write-Host ''
Write-Host '[1/5] Build + Automation...' -ForegroundColor Cyan
$BaseProofArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $AutomationRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
    TestFilter = $TestFilter
}
if ($SkipBuild) { $BaseProofArgs['SkipBuild'] = $true }
& $BaseProof @BaseProofArgs
if ($LASTEXITCODE -ne 0) {
    throw "Stage 3E build/Automation proof failed with exit code $LASTEXITCODE"
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
    throw 'Stage 3E preflight failed after Automation.'
}
$EditorCmd = $Context.UnrealEditorCmdPath

function Invoke-YacsCommandlet {
    param(
        [Parameter(Mandatory=$true)] [string] $RunName,
        [Parameter(Mandatory=$true)] [string] $LogPath
    )

    $ErrPath = $LogPath + '.stderr'
    $Args = @(
        $ProjectPath
        ('-run={0}' -f $RunName)
        '-Unattended'
        '-NoPause'
        '-NullRHI'
        '-NoSplash'
        '-NoP4'
        '-log'
    )
    $Proc = Start-Process -FilePath $EditorCmd -ArgumentList $Args -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $LogPath -RedirectStandardError $ErrPath
    $Proc.WaitForExit()
    if ($Proc.ExitCode -ne 0) {
        throw ('Commandlet {0} failed with exit code {1}; see {2}' -f $RunName, $Proc.ExitCode, $LogPath)
    }
}

# ----------------------------------------------------------------------
# 2. Generate route + minimal prototype terrain twice.
# ----------------------------------------------------------------------

Write-Host ''
Write-Host '[2/5] Stage 3 route/world setup + idempotency...' -ForegroundColor Cyan
Invoke-YacsCommandlet -RunName 'CyclingStage3RouteSetup' -LogPath $Setup1Log
Invoke-YacsCommandlet -RunName 'CyclingStage3RouteSetup' -LogPath $Setup2Log

# ----------------------------------------------------------------------
# 3. Fresh-process persistence verification.
# ----------------------------------------------------------------------

Write-Host ''
Write-Host '[3/5] Fresh-load route/world verification...' -ForegroundColor Cyan
Invoke-YacsCommandlet -RunName 'CyclingStage3RouteVerify' -LogPath $VerifyLog

$VerifyText = Get-Content -LiteralPath $VerifyLog -Raw -ErrorAction Stop
if ($VerifyText -notmatch 'CyclingStage3RouteVerifyCommandlet: PASS') {
    throw 'Fresh-load verifier exited 0 but PASS marker is missing.'
}
if ($VerifyText -notmatch 'Stage 3 prototype world verified after reload') {
    throw 'Fresh-load verifier did not prove persisted prototype-world instances.'
}

# ----------------------------------------------------------------------
# 4. Map Check on the persisted map.
# ----------------------------------------------------------------------

Write-Host ''
Write-Host '[4/5] Map Check...' -ForegroundColor Cyan
# UE 5.8 writes the main editor log to <RepoRoot>/Saved/Logs/
# regardless of stdout redirection. Use -AbsLog to redirect the engine
# log to a path we control so the summary parser sees the result.
$MapEditorLog = Join-Path -Path $ArtifactRoot -ChildPath 'map_check_editor.log'
if (Test-Path -LiteralPath $MapEditorLog) { Remove-Item -LiteralPath $MapEditorLog -Force }
$MapCheckErr = $MapCheckLog + '.stderr'
$MapArgs = @(
    $ProjectPath
    '/Game/Prototype/Maps/L_CyclingTest'
    '-Unattended'
    '-NoPause'
    '-NullRHI'
    '-NoSplash'
    '-NoP4'
    '-log'
    ('-AbsLog=' + $MapEditorLog)
    '-execcmds="MAP CHECK;QUIT"'
)
$MapProc = Start-Process -FilePath $EditorCmd -ArgumentList $MapArgs -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $MapCheckLog -RedirectStandardError $MapCheckErr
$MapProc.WaitForExit()
# PowerShell 5.1 Start-Process can return a null ExitCode for UE editor
# even on success; defer to the report-based check below.
$MapExit = $MapProc.ExitCode
if ($null -eq $MapExit) {
    if (Test-Path -LiteralPath $MapEditorLog) { $MapExit = 0 }
    else { $MapExit = 1 }
}
if ($MapExit -ne 0) {
    throw "Map Check editor process failed with exit code $MapExit; see $MapEditorLog"
}

if (-not (Test-Path -LiteralPath $MapEditorLog)) {
    throw "Map Check editor log was not produced at $MapEditorLog"
}
$MapText = Get-Content -LiteralPath $MapEditorLog -Raw -ErrorAction Stop
$MapMatches = [regex]::Matches(
    $MapText,
    'Map check complete:\s*(\d+)\s+Error\(s\),\s*(\d+)\s+Warning\(s\)',
    [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
)
if ($MapMatches.Count -eq 0) {
    throw 'Map Check summary was not found in the editor log.'
}
$MapSummary = $MapMatches[$MapMatches.Count - 1]
$MapErrors = [int]$MapSummary.Groups[1].Value
$MapWarnings = [int]$MapSummary.Groups[2].Value
if ($MapErrors -ne 0) {
    throw ('Map Check reported {0} error(s), {1} warning(s).' -f $MapErrors, $MapWarnings)
}
Write-Host ('Map Check: 0 errors, {0} warning(s).' -f $MapWarnings) -ForegroundColor Green

# ----------------------------------------------------------------------
# 5. Rendered 1080p / PIE sanity.
# ----------------------------------------------------------------------

$PerformanceStatus = 'skipped'
if (-not $SkipPerformance) {
    Write-Host ''
    Write-Host '[5/5] Rendered 1920x1080 performance sanity...' -ForegroundColor Cyan
    $InsightsProof = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Invoke-YacsInsightsProof.ps1'
    $InsightsArgs = @{
        RepoRoot = $RepoRoot
        ProjectPath = $ProjectPath
        ArtifactRoot = $PerformanceRoot
        ExpectedBranch = $ExpectedBranch
        ExpectedHead = $ExpectedHead
        SkipBuild = $true
    }
    & $InsightsProof @InsightsArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Rendered 1080p/Insights proof failed with exit code $LASTEXITCODE"
    }
    $PerformanceStatus = 'passed'
}
else {
    Write-Host ''
    Write-Host '[5/5] Rendered performance proof skipped by caller.' -ForegroundColor Yellow
}

$Summary = [ordered]@{
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
    RepoRoot = $RepoRoot
    Branch = $ExpectedBranch
    Head = $ExpectedHead
    TestFilter = $TestFilter
    SetupRun1 = 'passed'
    SetupRun2Idempotency = 'passed'
    FreshLoadVerify = 'passed'
    MapCheckErrors = $MapErrors
    MapCheckWarnings = $MapWarnings
    Performance1080p = $PerformanceStatus
}
$SummaryPath = Join-Path -Path $ArtifactRoot -ChildPath 'stage3e_summary.json'
$Summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8

Write-Host ''
Write-Host 'STAGE 3E PROOF PASSED.' -ForegroundColor Green
Write-Host ('Summary: {0}' -f $SummaryPath)
exit 0
