<#
.SYNOPSIS
    Final non-mutating Stage 3G proof for issue #80.

.DESCRIPTION
    Run this AFTER Stage 3G authoring assets/map have been generated and
    committed. It does not run the authoring pass. It verifies:
      1. Development Editor build + Stage 2/3 Automation including Stage3World;
      2. fresh-process Stage 3 route/world persistence verifier;
      3. Map Check;
      4. Git LFS integrity;
      5. comparable 1920x1080 captures at 1200/4900/8000 m.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [switch] $SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) { $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject' }
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) { $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/Issue80/Stage3G/FinalProof' }
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$TestFilter = 'CyclingPhysics+CyclingSession+CyclingInput+CyclingRuntime+CyclingDiagnostics+CyclingRouteContext+CyclingRouteProfile+CyclingRouteGeometry+CyclingStage3Runtime+CyclingStage3World+CyclingStage3FullRoute'

Write-Host '=== YACS Stage 3G final proof ===' -ForegroundColor Cyan
Write-Host ("Branch: {0}" -f $ExpectedBranch)
Write-Host ("Head  : {0}" -f $ExpectedHead)

# 1. Build + Automation, including the exact Stage3World test that owns the
# deterministic 3G instance-count assertions.
$BaseProof = Join-Path $RepoRoot 'scripts/ue/Invoke-YacsProof.ps1'
$AutomationRoot = Join-Path $ArtifactRoot 'Automation'
$BaseArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $AutomationRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
    TestFilter = $TestFilter
    ConservativeBuild = $true
    AdditionalAllowedDirtyPaths = @(
        'Content/Prototype/Environment/Stage3G/'
        'Content/Prototype/Maps/L_CyclingTest.umap'
    )
}
if ($SkipBuild) { $BaseArgs['SkipBuild'] = $true }
& $BaseProof @BaseArgs
if ($LASTEXITCODE -ne 0) { throw 'Stage 3G build/Automation proof failed.' }

# Resolve the exact editor path and provenance again for standalone commandlets.
$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$PreflightRoot = Join-Path $ArtifactRoot 'Preflight'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $PreflightRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead -AdditionalAllowedDirtyPaths @(
    'Content/Prototype/Environment/Stage3G/'
    'Content/Prototype/Maps/L_CyclingTest.umap'
)
if ($LASTEXITCODE -ne 0) { throw 'Stage 3G post-Automation preflight failed.' }
$EditorCmd = $Context.UnrealEditorCmdPath

function Invoke-Stage3GEditor {
    param(
        [Parameter(Mandatory=$true)] [string[]] $Arguments,
        [Parameter(Mandatory=$true)] [string] $LogPath,
        [int] $TimeoutSec = 180
    )
    $ErrPath = $LogPath + '.stderr'
    $Proc = Start-Process -FilePath $EditorCmd -ArgumentList $Arguments -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $LogPath -RedirectStandardError $ErrPath
    if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
        try { $Proc | Stop-Process -Force } catch { }
        throw "Unreal process timed out; see $LogPath"
    }
    $Code = $Proc.ExitCode
    if ($null -eq $Code) { if (Test-Path $LogPath) { $Code = 0 } else { $Code = 1 } }
    if ($Code -ne 0) { throw "Unreal process failed with exit code $Code; see $LogPath" }
}

function Invoke-Stage3GMapCheck {
    param(
        [Parameter(Mandatory=$true)] [string] $StdoutPath,
        [Parameter(Mandatory=$true)] [string] $EditorLogPath,
        [int] $TimeoutSec = 120,
        [int] $ExitGraceSec = 10
    )

    $ErrPath = $StdoutPath + '.stderr'
    Remove-Item -LiteralPath $StdoutPath, $ErrPath, $EditorLogPath -Force -ErrorAction SilentlyContinue

    $Arguments = @(
        $ProjectPath,
        '/Game/Prototype/Maps/L_CyclingTest',
        '-Unattended', '-NoPause', '-NullRHI', '-NoSplash', '-NoP4', '-log',
        ('-AbsLog=' + $EditorLogPath),
        '-execcmds="MAP CHECK;QUIT"'
    )

    $SummaryPattern = 'Map check complete:\s*(\d+)\s+Error\(s\),\s*(\d+)\s+Warning\(s\)'
    $Proc = Start-Process -FilePath $EditorCmd -ArgumentList $Arguments -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $StdoutPath -RedirectStandardError $ErrPath
    $Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $NextHeartbeatSec = 15
    $SummaryMatch = $null

    while ($Stopwatch.Elapsed.TotalSeconds -lt $TimeoutSec) {
        if (Test-Path -LiteralPath $EditorLogPath -PathType Leaf) {
            $MapText = Get-Content -LiteralPath $EditorLogPath -Raw -ErrorAction SilentlyContinue
            if ($MapText) {
                $Matches = [regex]::Matches($MapText, $SummaryPattern, 'IgnoreCase')
                if ($Matches.Count -gt 0) {
                    $SummaryMatch = $Matches[$Matches.Count - 1]
                    break
                }
            }
        }

        if ($Proc.HasExited) {
            break
        }

        if ($Stopwatch.Elapsed.TotalSeconds -ge $NextHeartbeatSec) {
            $LogBytes = if (Test-Path -LiteralPath $EditorLogPath -PathType Leaf) {
                (Get-Item -LiteralPath $EditorLogPath).Length
            } else { 0 }
            Write-Host ("YACS MAP CHECK heartbeat elapsed={0:N1}s logBytes={1}" -f $Stopwatch.Elapsed.TotalSeconds, $LogBytes)
            if ($LogBytes -gt 0) {
                Get-Content -LiteralPath $EditorLogPath -Tail 5 -ErrorAction SilentlyContinue |
                    ForEach-Object { Write-Host ("YACS MAP CHECK logtail {0}" -f $_) }
            }
            $NextHeartbeatSec += 15
        }

        Start-Sleep -Milliseconds 500
    }

    # One final read closes the race where the editor writes the summary just
    # before exiting or exactly as the timeout boundary is reached.
    if (-not $SummaryMatch -and (Test-Path -LiteralPath $EditorLogPath -PathType Leaf)) {
        $MapText = Get-Content -LiteralPath $EditorLogPath -Raw -ErrorAction SilentlyContinue
        if ($MapText) {
            $Matches = [regex]::Matches($MapText, $SummaryPattern, 'IgnoreCase')
            if ($Matches.Count -gt 0) {
                $SummaryMatch = $Matches[$Matches.Count - 1]
            }
        }
    }

    if (-not $SummaryMatch) {
        if (-not $Proc.HasExited) {
            try { $Proc | Stop-Process -Force } catch { }
            try { $Proc.WaitForExit() } catch { }
        }
        $Stopwatch.Stop()
        throw "Map Check did not emit a completion summary within $TimeoutSec seconds; see $EditorLogPath and $StdoutPath"
    }

    $MapErrors = [int]$SummaryMatch.Groups[1].Value
    $MapWarnings = [int]$SummaryMatch.Groups[2].Value
    Write-Host ("YACS MAP CHECK summary observed: errors={0} warnings={1}" -f $MapErrors, $MapWarnings)

    $ForcedExitAfterSummary = $false
    if (-not $Proc.HasExited) {
        Write-Host ("YACS MAP CHECK waiting up to {0}s for editor shutdown after summary..." -f $ExitGraceSec)
        if (-not $Proc.WaitForExit($ExitGraceSec * 1000)) {
            $ForcedExitAfterSummary = $true
            Write-Host 'YACS MAP CHECK editor did not exit after the completed check; terminating only after the proof marker was persisted.' -ForegroundColor Yellow
            try { $Proc | Stop-Process -Force } catch { }
            try { $Proc.WaitForExit() } catch { }
        }
    }

    if (-not $ForcedExitAfterSummary) {
        $Code = $Proc.ExitCode
        if ($null -eq $Code) { $Code = 0 }
        if ($Code -ne 0) {
            throw "Map Check editor exited with code $Code after writing its completion summary; see $EditorLogPath"
        }
    }

    $Stopwatch.Stop()
    $ProcessEvidence = [ordered]@{
        TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
        SummaryObserved = $true
        Errors = $MapErrors
        Warnings = $MapWarnings
        ForcedExitAfterSummary = $ForcedExitAfterSummary
        ElapsedSeconds = [math]::Round($Stopwatch.Elapsed.TotalSeconds, 2)
        TimeoutSeconds = $TimeoutSec
        ExitGraceSeconds = $ExitGraceSec
        EditorLog = $EditorLogPath
        StdoutLog = $StdoutPath
    }
    $ProcessEvidence |
        ConvertTo-Json -Depth 3 |
        Set-Content -LiteralPath (Join-Path $ArtifactRoot 'map_check_process.json') -Encoding UTF8

    return [pscustomobject]@{
        Errors = $MapErrors
        Warnings = $MapWarnings
        ForcedExitAfterSummary = $ForcedExitAfterSummary
    }
}

# 2. Fresh-process persisted-world verification.
$VerifyLog = Join-Path $ArtifactRoot 'route_world_verify.log'
Invoke-Stage3GEditor -LogPath $VerifyLog -Arguments @(
    $ProjectPath,
    '-run=CyclingStage3RouteVerify',
    '-Unattended', '-NoPause', '-NullRHI', '-NoSplash', '-NoP4', '-log'
)
$VerifyText = Get-Content -LiteralPath $VerifyLog -Raw
if ($VerifyText -notmatch 'CyclingStage3RouteVerifyCommandlet: PASS') {
    throw 'Fresh-process Stage 3 verifier PASS marker missing.'
}
if ($VerifyText -notmatch 'Stage 3 prototype world verified after reload') {
    throw 'Fresh-process Stage 3G world persistence marker missing.'
}

# 3. Map Check. UE 5.8 may persist the final Map Check result but keep the
# headless editor alive. Treat the persisted summary as the proof boundary:
# no summary is always a hard failure; after a summary, allow a short clean
# shutdown grace period before terminating the otherwise-idle editor.
$MapStdout = Join-Path $ArtifactRoot 'map_check.stdout.log'
$MapEditorLog = Join-Path $ArtifactRoot 'map_check.editor.log'
$MapResult = Invoke-Stage3GMapCheck -StdoutPath $MapStdout -EditorLogPath $MapEditorLog -TimeoutSec 120 -ExitGraceSec 10
$MapErrors = [int]$MapResult.Errors
$MapWarnings = [int]$MapResult.Warnings
if ($MapErrors -ne 0) { throw "Map Check failed: $MapErrors error(s), $MapWarnings warning(s)." }

# 4. Git LFS integrity. Stage 3G map/material binary sources must never fall
# back to normal Git blobs.
Push-Location -LiteralPath $RepoRoot
try {
    $LfsOutput = (& git lfs fsck 2>&1) -join "`n"
    $LfsExit = $LASTEXITCODE
} finally { Pop-Location }
$LfsLog = Join-Path $ArtifactRoot 'git_lfs_fsck.log'
$LfsOutput | Set-Content -LiteralPath $LfsLog -Encoding UTF8
if ($LfsExit -ne 0) { throw "git lfs fsck failed; see $LfsLog" }

# 5. Comparable rendered captures at the three canonical Stage 3 positions.
$Capture = Join-Path $RepoRoot 'scripts/ue/Invoke-YacsStage3GVisualCapture.ps1'
$CaptureRoot = Join-Path $ArtifactRoot 'Visual'
& $Capture -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $CaptureRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead -Suffix AFTER -SkipBuild
if ($LASTEXITCODE -ne 0) { throw 'Stage 3G rendered visual capture failed.' }

$ExpectedPngs = @(
    '01_meadow_valley_1200m_AFTER.png',
    '02_forest_sector_4900m_AFTER.png',
    '03_high_valley_mountains_8000m_AFTER.png'
)
foreach ($Name in $ExpectedPngs) {
    $Path = Join-Path $CaptureRoot $Name
    if (-not (Test-Path -LiteralPath $Path)) { throw "Missing Stage 3G proof image: $Path" }
    if ((Get-Item -LiteralPath $Path).Length -lt 50000) { throw "Stage 3G proof image is suspiciously small: $Path" }
}

$Summary = [ordered]@{
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
    Branch = $ExpectedBranch
    Head = $ExpectedHead
    Automation = 'passed'
    FreshLoadVerify = 'passed'
    MapCheckErrors = $MapErrors
    MapCheckWarnings = $MapWarnings
    GitLfsFsck = 'passed'
    VisualCapture = 'passed'
    ProofDistancesM = @(1200, 4900, 8000)
}
$SummaryPath = Join-Path $ArtifactRoot 'stage3g_final_summary.json'
$Summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8

Write-Host 'STAGE 3G FINAL PROOF PASSED.' -ForegroundColor Green
Write-Host ("Summary: {0}" -f $SummaryPath)
exit 0
