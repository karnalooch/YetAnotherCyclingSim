<#
.SYNOPSIS
    Top-level unattended automation proof for YetAnotherCyclingSim Stage 2.

.DESCRIPTION
    Single-command orchestrator that:

      1. Runs Preflight-YacsProof.ps1 (deterministic environment check,
         branch/HEAD/dirty-state/UE install/GPU/artifact root);
      2. Builds the Development Editor (UBT) so Automation tests can run;
      3. Runs the existing Automation tests from the command line via
         RunUAT.bat RunUnreal / -ExecCmds="Automation RunTests <...>";
      4. Exports a machine-readable Automation report using
         -ReportExportPath;
      5. Parses discovered/passed/failed counts from the report;
      6. Exits non-zero when the proof genuinely failed (any test failure
         or any unverified prerequisite);
      7. Writes ONLY artifacts under <RepoRoot>/Saved/RuntimeProof/Issue49/Tranche4
         (the location is already covered by .gitignore via Saved/*).

    The script is PowerShell-first and does NOT require any new dependency
    beyond a Windows host with the Unreal Engine installed and Git on PATH.

    Default tests:
      CyclingPhysics.*
      CyclingSession.*
      CyclingInput.*
      CyclingRuntime.*
      CyclingDiagnostics.*
    Plus the frame-pacing test CyclingRuntime.FramePacing.

.PARAMETER RepoRoot
    Absolute path to the YetAnotherCyclingSim repository root.

.PARAMETER ProjectPath
    Absolute path to the .uproject file.

.PARAMETER ArtifactRoot
    Directory under which proof artifacts will be written.

.PARAMETER SkipBuild
    Skip the Development Editor build step (assume an existing build is
    already up to date).

.PARAMETER TestFilter
    Override the default test filter. The default matches the Stage 2
    suites and the frame-pacing test.

.PARAMETER ExpectedHead
    Override the expected HEAD SHA (default: a47d6e54...).

.PARAMETER ExpectedBranch
    Override the expected branch name.

.EXAMPLE
    pwsh ./scripts/ue/Invoke-YacsProof.ps1
    # Run the full Stage 2 proof with defaults.

.EXAMPLE
    pwsh ./scripts/ue/Invoke-YacsProof.ps1 -SkipBuild -TestFilter 'CyclingRuntime.PausePreservesMotionState+CyclingRuntime.ZeroPowerCoastsOnFlat+CyclingRuntime.ZeroPowerDownhillDoesNotMeanStop'
    # Re-run only the new regression coverage without rebuilding.

.NOTES
    The script never modifies any source tree file. It only writes to the
    Saved/RuntimeProof/Issue49/Tranche4 location.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [switch] $SkipBuild,
    [switch] $ConservativeBuild,
    [string] $TestFilter = 'CyclingPhysics+CyclingSession+CyclingInput+CyclingRuntime+CyclingDiagnostics',
    [string] $ExpectedBranch = 'test/stage2-integration-performance-proof',
    [string] $ExpectedHead   = 'a47d6e54ce2f4d72d774bcecc7c971b674b2ee53'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$ScriptDir = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue'
$PreflightScript = Join-Path -Path $ScriptDir -ChildPath 'Preflight-YacsProof.ps1'

if (-not $ProjectPath) {
    $ProjectPath = Join-Path -Path $RepoRoot -ChildPath 'YetAnotherCyclingSim.uproject'
}
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/Issue49/Tranche4'
}
if (-not (Test-Path -LiteralPath $ArtifactRoot)) {
    New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
}
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path
$PhaseStatusPath = Join-Path -Path $ArtifactRoot -ChildPath 'phase_status.json'

function Write-YacsPhaseStatus {
    param(
        [Parameter(Mandatory=$true)] [string] $Phase,
        [Parameter(Mandatory=$true)] [string] $Status,
        [string] $Detail = ''
    )

    $Payload = [ordered]@{
        TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
        Phase = $Phase
        Status = $Status
        Detail = $Detail
    }
    $Payload | ConvertTo-Json -Depth 3 |
        Set-Content -LiteralPath $PhaseStatusPath -Encoding UTF8
    Write-Host ("YACS PHASE: {0} -> {1}{2}" -f $Phase, $Status, $(if ($Detail) { " ($Detail)" } else { '' }))
}

function Wait-YacsProcessWithHeartbeat {
    param(
        [Parameter(Mandatory=$true)] [System.Diagnostics.Process] $Process,
        [Parameter(Mandatory=$true)] [string] $Label,
        [Parameter(Mandatory=$true)] [string] $LogPath,
        [int] $HeartbeatSeconds = 30
    )

    $Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $NextHeartbeat = [double]$HeartbeatSeconds

    while (-not $Process.HasExited) {
        Start-Sleep -Seconds 2
        if ($Stopwatch.Elapsed.TotalSeconds -lt $NextHeartbeat) {
            continue
        }

        $LogBytes = 0
        if (Test-Path -LiteralPath $LogPath -PathType Leaf) {
            try {
                $LogBytes = (Get-Item -LiteralPath $LogPath -ErrorAction Stop).Length
            } catch { }
        }

        Write-Host ("YACS HEARTBEAT [{0}] elapsed={1:N1}m logBytes={2}" -f $Label, $Stopwatch.Elapsed.TotalMinutes, $LogBytes)
        if ($LogBytes -gt 0) {
            Get-Content -LiteralPath $LogPath -Tail 5 -ErrorAction SilentlyContinue |
                ForEach-Object { Write-Host ("YACS LOGTAIL [{0}] {1}" -f $Label, $_) }
        }
        $NextHeartbeat += $HeartbeatSeconds
    }

    $Process.WaitForExit()
    $Stopwatch.Stop()
    Write-Host ("YACS PROCESS EXIT [{0}] elapsed={1:N1}m exitCode={2}" -f $Label, $Stopwatch.Elapsed.TotalMinutes, $Process.ExitCode)
    if (Test-Path -LiteralPath $LogPath -PathType Leaf) {
        Get-Content -LiteralPath $LogPath -Tail 10 -ErrorAction SilentlyContinue |
            ForEach-Object { Write-Host ("YACS LOGTAIL [{0}] {1}" -f $Label, $_) }
    }
}

Write-Host ("=== Invoke-YacsProof === RepoRoot={0}" -f $RepoRoot)
Write-Host ("ArtifactRoot={0}" -f $ArtifactRoot)

# --- (1) Preflight --------------------------------------------------------

Write-Host ""
Write-Host "[1/4] Running preflight..." -ForegroundColor Cyan
Write-YacsPhaseStatus -Phase 'preflight' -Status 'running'
$PreflightArgs = @{
    RepoRoot        = $RepoRoot
    ProjectPath     = $ProjectPath
    ArtifactRoot    = $ArtifactRoot
    ExpectedBranch  = $ExpectedBranch
    ExpectedHead    = $ExpectedHead
}
$Context = & $PreflightScript @PreflightArgs
if ($LASTEXITCODE -ne 0) {
    Write-YacsPhaseStatus -Phase 'preflight' -Status 'failed' -Detail ("exit={0}" -f $LASTEXITCODE)
    throw "Preflight failed with exit code $LASTEXITCODE"
}
Write-YacsPhaseStatus -Phase 'preflight' -Status 'passed'
Write-Host "Preflight OK." -ForegroundColor Green

# --- (2) Build ------------------------------------------------------------

if ($ConservativeBuild) {
    $UbtConfigDir = Join-Path -Path $RepoRoot -ChildPath 'Saved/UnrealBuildTool'
    New-Item -ItemType Directory -Path $UbtConfigDir -Force | Out-Null
    $UbtConfigPath = Join-Path -Path $UbtConfigDir -ChildPath 'BuildConfiguration.xml'
    @'
<?xml version="1.0" encoding="utf-8" ?>
<Configuration xmlns="https://www.unrealengine.com/BuildConfiguration">
  <BuildConfiguration>
    <bAllowUBAExecutor>false</bAllowUBAExecutor>
    <bAllowUBALocalExecutor>false</bAllowUBALocalExecutor>
    <MaxParallelActions>2</MaxParallelActions>
  </BuildConfiguration>
</Configuration>
'@ | Set-Content -LiteralPath $UbtConfigPath -Encoding UTF8
    Write-Host ("CI conservative UBT profile: UBA disabled; MaxParallelActions=2; config={0}" -f $UbtConfigPath) -ForegroundColor Yellow
}

if (-not $SkipBuild) {
    Write-Host ""
    Write-Host "[2/4] Building YetAnotherCyclingSimEditor (Development)..." -ForegroundColor Cyan
    Write-YacsPhaseStatus -Phase 'build' -Status 'running'
    $BuildLog = Join-Path -Path $ArtifactRoot -ChildPath 'build_editor.log'
    # Use UnrealBuildTool directly. The editor target name matches the
    # uproject module name "YetAnotherCyclingSim" with the "Editor"
    # suffix (per the existing *.Target.cs pair in Source/).
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
    Wait-YacsProcessWithHeartbeat -Process $BuildProc -Label 'build' -LogPath $BuildLog
    $BuildExit = $BuildProc.ExitCode
    # PowerShell 5.1 Start-Process -PassThru can return an empty/null
    # ExitCode on successful UBT runs even after WaitForExit(). Treat the
    # build as successful when the log explicitly reports Succeeded.
    if ($null -eq $BuildExit) {
        if (Test-Path -LiteralPath $BuildLog) {
            $BuildText = Get-Content -LiteralPath $BuildLog -Raw -ErrorAction SilentlyContinue
            if ($BuildText -and ($BuildText -match 'Result: Succeeded')) {
                $BuildExit = 0
            }
        }
    }
    if ($BuildExit -ne 0) {
        Write-YacsPhaseStatus -Phase 'build' -Status 'failed' -Detail ("exit={0}" -f $BuildExit)
        throw "Editor build failed with exit code $BuildExit; see $BuildLog"
    }
    Write-YacsPhaseStatus -Phase 'build' -Status 'passed'
    Write-Host "Editor build OK." -ForegroundColor Green
} else {
    Write-Host ""
    Write-YacsPhaseStatus -Phase 'build' -Status 'skipped'
    Write-Host "[2/4] Skipping editor build (-SkipBuild)." -ForegroundColor Yellow
}

# --- (3) Automation tests -------------------------------------------------

Write-Host ""
Write-Host "[3/4] Running Automation tests..." -ForegroundColor Cyan
Write-YacsPhaseStatus -Phase 'automation' -Status 'running'

$RunLog = Join-Path -Path $ArtifactRoot -ChildPath 'automation_run.log'
$ReportJson = Join-Path -Path $ArtifactRoot -ChildPath 'index.json'
$ReportExportPath = Join-Path -Path $ArtifactRoot -ChildPath 'AutomationReport'

# Drive headless Automation directly through UnrealEditor-Cmd.exe,
# matching the pattern already used by Invoke-YacsInsightsProof.ps1 for
# the Stage 2 PIE proof. RunUAT's RunUnreal entry point is a Gauntlet
# wrapper that requires -project/-build/-platform/-device setup which is
# heavier than this MVP needs. The Automation controller in the editor
# accepts "Automation RunTests <Filter>;Quit" via -execcmds= and writes
# the report to -ReportExportPath=<path>/index.json.

$EditorArgs = @(
    $ProjectPath
    '-Unattended'
    '-NoPause'
    '-NullRHI'
    '-NoSplash'
    '-log'
    '-ReportExportPath=' + $ReportExportPath
    # The execcmds value contains spaces; Windows CommandLineToArgvW
    # would otherwise split "-execcmds=Automation RunTests A+B;Quit" into
    # multiple tokens and the Automation handler would only receive the
    # first word ("Automation"), leaving RunTests unqueued. Wrap the
    # value in literal double-quotes so it stays a single argv element.
    ('-execcmds="' + ('Automation RunTests ' + $TestFilter + ';Quit' + '"'))
)
$UATProc = Start-Process -FilePath $Context.UnrealEditorCmdPath `
    -ArgumentList $EditorArgs -NoNewWindow -PassThru -RedirectStandardOutput $RunLog
Wait-YacsProcessWithHeartbeat -Process $UATProc -Label 'automation' -LogPath $RunLog

# Defer the PowerShell 5.1 Start-Process -PassThru null-ExitCode
# normalization to AFTER the tally block. Referencing $Failed/$Errors/
# $Discovered here would race against their initialization in the tally
# section and could wrongly classify an unknown exit as success before
# the report has been parsed.
$EditorExit = $UATProc.ExitCode

Write-Host ("Editor raw exit code: {0}" -f $EditorExit)

# --- (4) Tally ------------------------------------------------------------

Write-Host ""
Write-Host "[4/4] Tallying results..." -ForegroundColor Cyan
Write-YacsPhaseStatus -Phase 'tally' -Status 'running' -Detail ("editorExit={0}" -f $EditorExit)

$Discovered = 0
$Passed = 0
$Failed = 0
$Skipped = 0
$Errors = 0
$SucceededWithWarnings = 0
$WarningsTotal = 0

# The RunUAT export writes index.json with the report metadata and a
# per-test entry. We tolerate both "reportExportPath/index.json" and the
# older single-file layout.
$IndexCandidates = @(
    (Join-Path -Path $ReportExportPath -ChildPath 'index.json'),
    (Join-Path -Path $ArtifactRoot -ChildPath 'index.json'),
    (Join-Path -Path $ArtifactRoot -ChildPath 'AutomationReport/index.json')
)
$IndexPath = $null
foreach ($c in $IndexCandidates) {
    if (Test-Path -LiteralPath $c) { $IndexPath = $c; break }
}

if ($IndexPath) {
    try {
        $Index = Get-Content -LiteralPath $IndexPath -Raw -ErrorAction Stop | ConvertFrom-Json
        # Common shapes: { succeeded, failed, tests: [...] } OR
        # { results: { tests: [...] } }
        if ($Index.PSObject.Properties.Name -contains 'tests') {
            $Tests = $Index.tests
        } elseif ($Index.PSObject.Properties.Name -contains 'results' -and $Index.results.PSObject.Properties.Name -contains 'tests') {
            $Tests = $Index.results.tests
        } else {
            $Tests = @()
        }
        # The exporter splits the top-level counters between "succeeded"
        # (zero warnings) and "succeededWithWarnings" (state=Success but
        # warnings>0). The per-test entries are the source of truth: any
        # test with state=Success counts as a pass regardless of warnings.
        # We surface the warning breakdown separately instead of rolling
        # warning-bearing successes into a "failed" bucket.
        foreach ($t in $Tests) {
            $Discovered += 1
            $state = "$($t.state)"
            $warnCount = 0
            if ($t.PSObject.Properties.Name -contains 'warnings' -and ($t.warnings -is [int] -or $t.warnings -is [int64])) {
                $warnCount = [int] $t.warnings
            }
            $WarningsTotal += $warnCount
            switch -Regex ($state) {
                '^Success|^Pass'    {
                    $Passed += 1
                    if ($warnCount -gt 0) { $SucceededWithWarnings += 1 }
                }
                '^Fail'             { $Failed   += 1 }
                '^Skip'             { $Skipped  += 1 }
                default             { $Errors   += 1 }
            }
        }
        # Sanity-check the per-entry count against the explicit top-level
        # counters when both are present. If a real mismatch appears we
        # record it but keep the per-entry numbers as authoritative so
        # the proof never weakens failure detection.
        if ($Index.PSObject.Properties.Name -contains 'succeeded' -and $Index.succeeded -is [int] `
            -and $Index.PSObject.Properties.Name -contains 'succeededWithWarnings' -and $Index.succeededWithWarnings -is [int]) {
            $CounterTotal = ([int] $Index.succeeded) + ([int] $Index.succeededWithWarnings)
            if ($CounterTotal -ne $Passed) {
                Write-Warning ("index.json top-level succeeded+succeededWithWarnings={0} does not match per-entry Success count={1}; keeping per-entry numbers as authoritative." -f $CounterTotal, $Passed)
            }
        }
    } catch {
        Write-Warning "Could not parse index.json: $_"
    }
}

# --- PowerShell 5.1 Start-Process null-ExitCode fallback ------------------
#
# Only performed AFTER $Discovered/$Passed/$Failed/$Skipped/$Errors are
# known. Treat the editor as successful when:
#   - at least one test was actually discovered, AND
#   - no failures and no per-entry errors.
# Otherwise an unknown editor exit is conservatively treated as failure.
if ($null -eq $EditorExit) {
    if ($Discovered -gt 0 -and $Failed -eq 0 -and $Errors -eq 0) {
        Write-Host "Editor ExitCode unavailable under Windows PowerShell; Automation report is green, treating exit as 0." -ForegroundColor Yellow
        $EditorExit = 0
    }
    else {
        Write-Host "Editor ExitCode unavailable and Automation report is not demonstrably green." -ForegroundColor Red
        $EditorExit = 1
    }
}

$Summary = [ordered]@{
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
    RepoRoot     = $RepoRoot
    ProjectPath  = $ProjectPath
    Branch       = $Context.Branch
    Head         = $Context.Head
    UatExitCode  = $EditorExit
    IndexPath    = $IndexPath
    Discovered   = $Discovered
    Passed       = $Passed
    SucceededWithWarnings = $SucceededWithWarnings
    WarningsTotal = $WarningsTotal
    Failed       = $Failed
    Skipped      = $Skipped
    Errors       = $Errors
    RunLog       = $RunLog
    ReportPath   = $ReportExportPath
}
$Summary | ConvertTo-Json -Depth 4 |
    Set-Content -LiteralPath (Join-Path -Path $ArtifactRoot -ChildPath 'summary.json') -Encoding UTF8

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("=== YACS Stage 2 proof summary ===")
[void]$sb.AppendLine(("TimestampUtc : {0}" -f $Summary.TimestampUtc))
[void]$sb.AppendLine(("Branch       : {0}" -f $Summary.Branch))
[void]$sb.AppendLine(("Head         : {0}" -f $Summary.Head))
[void]$sb.AppendLine(("UAT exit     : {0}" -f $Summary.UatExitCode))

[void]$sb.AppendLine(("Index path   : {0}" -f $Summary.IndexPath))
[void]$sb.AppendLine(("Discovered   : {0}" -f $Summary.Discovered))
[void]$sb.AppendLine(("Passed       : {0}" -f $Summary.Passed))
[void]$sb.AppendLine(("  of which with warnings : {0}" -f $Summary.SucceededWithWarnings))
[void]$sb.AppendLine(("Total warnings           : {0}" -f $Summary.WarningsTotal))
[void]$sb.AppendLine(("Failed       : {0}" -f $Summary.Failed))
[void]$sb.AppendLine(("Skipped      : {0}" -f $Summary.Skipped))
[void]$sb.AppendLine(("Errors       : {0}" -f $Summary.Errors))
[void]$sb.AppendLine(("Run log      : {0}" -f $Summary.RunLog))
[void]$sb.AppendLine(("Report path  : {0}" -f $Summary.ReportPath))
$sb.ToString() | Set-Content -LiteralPath (Join-Path -Path $ArtifactRoot -ChildPath 'summary.txt') -Encoding UTF8

# --- Exit policy ----------------------------------------------------------

if ($EditorExit -ne 0 -or $Failed -gt 0 -or $Errors -gt 0) {
    Write-YacsPhaseStatus -Phase 'tally' -Status 'failed' -Detail ("discovered={0};passed={1};failed={2};errors={3};editorExit={4}" -f $Discovered, $Passed, $Failed, $Errors, $EditorExit)
    Write-Host ""
    Write-Host "PROOF FAILED." -ForegroundColor Red
    Write-Host ("Discovered={0} Passed={1} (withWarnings={2}) Failed={3} Skipped={4} Errors={5} UATExitCode={6}" -f `
        $Discovered, $Passed, $SucceededWithWarnings, $Failed, $Skipped, $Errors, $EditorExit)
    Write-Host ("See {0} for full log." -f $RunLog)
    exit 1
}

Write-YacsPhaseStatus -Phase 'tally' -Status 'passed' -Detail ("discovered={0};passed={1};failed={2};errors={3};editorExit={4}" -f $Discovered, $Passed, $Failed, $Errors, $EditorExit)
Write-Host ""
Write-Host "PROOF PASSED." -ForegroundColor Green
Write-Host ("Discovered={0} Passed={1} (withWarnings={2}) WarningsTotal={3} Failed={4} Skipped={5} Errors={6}" -f `
    $Discovered, $Passed, $SucceededWithWarnings, $WarningsTotal, $Failed, $Skipped, $Errors)
exit 0
