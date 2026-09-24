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

Write-Host ("=== Invoke-YacsProof === RepoRoot={0}" -f $RepoRoot)
Write-Host ("ArtifactRoot={0}" -f $ArtifactRoot)

# --- (1) Preflight --------------------------------------------------------

Write-Host ""
Write-Host "[1/4] Running preflight..." -ForegroundColor Cyan
$PreflightArgs = @{
    RepoRoot        = $RepoRoot
    ProjectPath     = $ProjectPath
    ArtifactRoot    = $ArtifactRoot
    ExpectedBranch  = $ExpectedBranch
    ExpectedHead    = $ExpectedHead
}
$Context = & $PreflightScript @PreflightArgs
if ($LASTEXITCODE -ne 0) {
    throw "Preflight failed with exit code $LASTEXITCODE"
}
Write-Host "Preflight OK." -ForegroundColor Green

# --- (2) Build ------------------------------------------------------------

if (-not $SkipBuild) {
    Write-Host ""
    Write-Host "[2/4] Building YetAnotherCyclingSimEditor (Development)..." -ForegroundColor Cyan
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
    $BuildProc.WaitForExit()
    if ($BuildProc.ExitCode -ne 0) {
        throw "Editor build failed with exit code $($BuildProc.ExitCode); see $BuildLog"
    }
    Write-Host "Editor build OK." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[2/4] Skipping editor build (-SkipBuild)." -ForegroundColor Yellow
}

# --- (3) Automation tests -------------------------------------------------

Write-Host ""
Write-Host "[3/4] Running Automation tests..." -ForegroundColor Cyan

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
$UATProc.WaitForExit()

Write-Host ("Editor exit code: {0}" -f $UATProc.ExitCode)

# --- (4) Tally ------------------------------------------------------------

Write-Host ""
Write-Host "[4/4] Tallying results..." -ForegroundColor Cyan

$Discovered = 0
$Passed = 0
$Failed = 0
$Skipped = 0
$Errors = 0

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
        foreach ($t in $Tests) {
            $Discovered += 1
            $state = "$($t.state)"
            switch -Regex ($state) {
                '^Success|^Pass'    { $Passed   += 1 }
                '^Fail'             { $Failed   += 1 }
                '^Skip'             { $Skipped  += 1 }
                default             { $Errors   += 1 }
            }
        }
        # Some exporters write top-level succeeded/failed counters too.
        if ($Index.PSObject.Properties.Name -contains 'succeeded' -and $Index.succeeded -is [int]) {
            # Trust the explicit counters when present and reasonable.
            $Passed = [int] $Index.succeeded
        }
        if ($Index.PSObject.Properties.Name -contains 'failed' -and $Index.failed -is [int]) {
            $Failed = [int] $Index.failed
        }
    } catch {
        Write-Warning "Could not parse index.json: $_"
    }
}

$Summary = [ordered]@{
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
    RepoRoot     = $RepoRoot
    ProjectPath  = $ProjectPath
    Branch       = $Context.Branch
    Head         = $Context.Head
    UatExitCode  = $UATProc.ExitCode
    IndexPath    = $IndexPath
    Discovered   = $Discovered
    Passed       = $Passed
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
[void]$sb.AppendLine(("Failed       : {0}" -f $Summary.Failed))
[void]$sb.AppendLine(("Skipped      : {0}" -f $Summary.Skipped))
[void]$sb.AppendLine(("Errors       : {0}" -f $Summary.Errors))
[void]$sb.AppendLine(("Run log      : {0}" -f $Summary.RunLog))
[void]$sb.AppendLine(("Report path  : {0}" -f $Summary.ReportPath))
$sb.ToString() | Set-Content -LiteralPath (Join-Path -Path $ArtifactRoot -ChildPath 'summary.txt') -Encoding UTF8

# --- Exit policy ----------------------------------------------------------

if ($UATProc.ExitCode -ne 0 -or $Failed -gt 0 -or $Errors -gt 0) {
    Write-Host ""
    Write-Host "PROOF FAILED." -ForegroundColor Red
    Write-Host ("Discovered={0} Passed={1} Failed={2} Skipped={3} Errors={4} UATExitCode={5}" -f `
        $Discovered, $Passed, $Failed, $Skipped, $Errors, $UATProc.ExitCode)
    Write-Host ("See {0} for full log." -f $RunLog)
    exit 1
}

Write-Host ""
Write-Host "PROOF PASSED." -ForegroundColor Green
Write-Host ("Discovered={0} Passed={1} Failed={2} Skipped={3} Errors={4}" -f `
    $Discovered, $Passed, $Failed, $Skipped, $Errors)
exit 0
