<#
.SYNOPSIS
    Issue #49 Stage 2 performance proof using Unreal Insights tracing
    instead of CSV Profiler (which is reported as disabled on the local
    UE installation: "StudioTelemetry.Provider.CSV is disabled for this
    application").

.DESCRIPTION
    Drives a single, deterministic rendered run of the prototype at
    1920x1080 in a REAL rendered PIE viewport (no -NullRHI) and captures:

      - A .utrace file using the standard engine-supported channels
        `cpu,gpu,frame,stats` (no permanent custom trace instrumentation
        in C++). Tracing is started via `-trace=...` and `-tracefile=...`
        at launch and stopped cleanly via the `Trace.Stop` console
        command issued by the PerformanceProof test.
      - A per-frame timing CSV written by CyclingRuntime.PerformanceProof.
        The CSV mirrors the `stat unit` overlay (Frame / Game / Draw /
        RHI / GameWait in ms) and is the primary numeric evidence for
        the #49 Insights summary. GPU time lives in the `gpu` Insights
        channel and is reported separately from the CSV.
      - A .uestats file using the classic `stat startfile` /
        `stat stopfile` console commands as an independent fallback
        artifact. This artifact does NOT depend on StudioTelemetry CSV.
      - A viewport screenshot showing the `stat unit` / `stat unitgraph`
        overlays enabled (the visual acceptance evidence for #49).
        Screenshot is requested via FScreenshotRequest::RequestScreenshot
        with bInShowUI=true; the previously used TakeAutomationScreenshot
        helper does NOT capture UI overlays (UE 5.8 documented behaviour).

    The script does NOT mutate the .umap. It launches the editor with the
    existing `L_CyclingTest` map URL and a dedicated in-process
    PerformanceProof automation test that drives the placed Pawn through
    the documented lifecycle (Start / Stop / Restart) for a non-trivial
    real-time horizon.

    Artifacts are written under Saved/RuntimeProof/Issue49/Tranche4/
    (already gitignored).

.PARAMETER RepoRoot
    Absolute path to the YetAnotherCyclingSim repository root.

.PARAMETER ProjectPath
    Absolute path to the .uproject file.

.PARAMETER ArtifactRoot
    Directory under which proof artifacts will be written.

.PARAMETER RideDurationS
    How long to ride during the trace. Default 45 s gives a non-trivial
    sample without exhausting disk.

.PARAMETER SkipBuild
    Skip the Development Editor build step (assume an existing build is
    already up to date).

.PARAMETER SkipInsightsAnalysis
    Skip the headless Insights analysis pass (only useful when the
    Insights exe is not on disk).

.PARAMETER SkipUestats
    Skip the .uestats fallback capture.

.PARAMETER InsightsPath
    Path to UnrealInsights.exe. Defaults to the same install as the
    Editor (Engine/Binaries/Win64/UnrealInsights.exe).

.NOTES
    This script is intended to be run AFTER Invoke-YacsProof.ps1 has
    produced a green build. It does not rebuild the editor unless
    -SkipBuild:$false is supplied explicitly.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [int]    $RideDurationS = 45,
    [switch] $SkipBuild,
    [switch] $SkipInsightsAnalysis,
    [switch] $SkipUestats,
    [string] $InsightsPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) { $ProjectPath = Join-Path -Path $RepoRoot -ChildPath 'YetAnotherCyclingSim.uproject' }
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) { $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/Issue49/Tranche4' }
if (-not (Test-Path -LiteralPath $ArtifactRoot)) { New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null }
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

# Reuse the preflight helper to discover the UE install.
$PreflightScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $PreflightScript -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot
if ($LASTEXITCODE -ne 0) { throw "Preflight failed." }

if (-not $InsightsPath) {
    $InsightsPath = Join-Path -Path $Context.EngineRoot -ChildPath 'Engine/Binaries/Win64/UnrealInsights.exe'
}
$Resolved = Resolve-Path -LiteralPath $InsightsPath -ErrorAction SilentlyContinue
if ($Resolved) { $InsightsPath = $Resolved.Path } else { $InsightsPath = $null }

# Validate launch prerequisites before we touch anything on disk.
$UEditor = $Context.UnrealEditorPath
if (-not $UEditor) {
    throw "UnrealEditor.exe (GUI) not resolved by preflight. Cannot launch a rendered PIE viewport."
}
if (-not (Test-Path -LiteralPath $UEditor)) {
    throw "UnrealEditor.exe not found at '$UEditor'."
}

# --- (0) Optional editor build -------------------------------------------

if (-not $SkipBuild) {
    Write-Host ""
    Write-Host "[0/5] Building YetAnotherCyclingSimEditor (Development)..." -ForegroundColor Cyan
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

# --- (1) Clean stale artifacts from previous runs ------------------------

# Remove the previously generated (potentially stale) trace and stats
# files so we never silently mix evidence from a previous broken launch
# (e.g. the well-known '/Engine/Maps/Templates/OpenWorld' fallback that
# happens when the map URL is wrong) with the current valid run.
foreach ($StaleName in @(
    'yacs_performance.utrace',
    'yacs_performance.uestats',
    'yacs_performance.csv',
    'PerformanceProof.png',
    'AutoScreenshot.png',
    'insights_summary.tsv',
    'insights_summary.json',
    'yacs_performance_frames.json'
)) {
    $StalePath = Join-Path -Path $ArtifactRoot -ChildPath $StaleName
    if (Test-Path -LiteralPath $StalePath) {
        Remove-Item -LiteralPath $StalePath -Force
    }
}

# --- (2) Launch rendered PIE with Insights tracing ----------------------

Write-Host ""
Write-Host "[1/5] Launching rendered PIE for performance capture..." -ForegroundColor Cyan

# Standard engine-supported trace channels; no custom C++ instrumentation.
$TraceChannels = 'cpu,gpu,frame,stats'

# Map URL. UE 5.8 documents the launch shape as
#   UnrealEditor.exe <Project.uproject> /Game/.../<Map.umap> -game ...
# using a /Game/-prefixed package path; passing the source
# 'Content/.../Map.umap' is NOT a valid map URL and silently falls back
# to the engine template map.
$MapArg = '/Game/Prototype/Maps/L_CyclingTest.umap'

$TraceFile = Join-Path -Path $ArtifactRoot -ChildPath 'yacs_performance.utrace'
$UestatsFile = Join-Path -Path $ArtifactRoot -ChildPath 'yacs_performance.uestats'
$CsvFile = Join-Path -Path $ArtifactRoot -ChildPath 'yacs_performance.csv'
$ScreenshotFile = Join-Path -Path $ArtifactRoot -ChildPath 'PerformanceProof.png'

# Pass output paths to the test process via environment variables. This
# keeps the test agnostic of the harness working directory and matches
# the documented "command line => test" boundary. We set them on the
# current process so that child processes inherit them (PowerShell 5.1
# Start-Process does not support -Environment).
$Env = @{
    YACS_PERF_CSV_PATH        = $CsvFile
    YACS_PERF_SCREENSHOT_PATH = $ScreenshotFile
    YACS_PERF_TRACEFILE       = $TraceFile
}
foreach ($k in $Env.Keys) {
    [System.Environment]::SetEnvironmentVariable($k, $Env[$k], 'Process')
}

# -execcmds is run after the world is initialised. The single command is
# the dedicated PerformanceProof test, which queues latent commands and
# ends with `Trace.Stop` and `stat stopfile` so the .utrace and .uestats
# are flushed before the editor exits.
$ExeccmdsValue = 'Automation RunTests CyclingRuntime.PerformanceProof;Quit'

$AbsLog = Join-Path -Path $ArtifactRoot -ChildPath 'editor_session_performance.log'
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
    # `-stdout` makes UE write logs to stdout in addition to OutputDebugString
    # so Start-Process -RedirectStandardOutput captures the editor session.
    '-stdout',
    # `-AbsLog` provides a guaranteed absolute log file path.
    ('-AbsLog=' + $AbsLog),
    # Standard trace channels + explicit output file. The PerformanceProof
    # test issues `Trace.Stop` on its way out so the file is finalised.
    ('-trace=' + $TraceChannels),
    ('-tracefile=' + $TraceFile),
    # Suppress Insights internal auto-debugger so the test finishes cleanly.
    '-NoDebugTools',
    ('-execcmds="' + $ExeccmdsValue + '"')
)

# Launch. Environment variables are inherited from this process (set
# above). PowerShell 5.1 Start-Process does not accept -Environment.
$Proc = Start-Process -FilePath $UEditor -ArgumentList $EditorArgs `
    -NoNewWindow -PassThru -RedirectStandardOutput $AbsLog `
    -WorkingDirectory $RepoRoot
Write-Host ("Launched editor pid={0}; waiting up to {1} s..." -f $Proc.Id, ($RideDurationS + 90))

# Hard timeout: ride horizon + ample margin for editor startup, trace
# initialisation, Insights server startup, screenshot flush, and trace
# finalisation. 240 s is well above the actual ~60 s observed runtime
# but stays inside the home-PC proof window.
$TimeoutSec = $RideDurationS + 240
if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
    try { $Proc | Stop-Process -Force } catch { }
    throw "PerformanceProof editor did not finish within $TimeoutSec seconds. See $AbsLog."
}
Write-Host ("Editor exit code: {0}" -f $Proc.ExitCode)

# --- (3) Validate launch evidence ---------------------------------------

# Confirm the editor log shows L_CyclingTest loaded (and no fallback to a
# template map). The previous broken run produced an .utrace but loaded
# the engine template; this check exists exactly so we never silently
# treat a fallback as PASS.
$EditorLogText = if (Test-Path -LiteralPath $AbsLog) {
    Get-Content -LiteralPath $AbsLog -Raw -ErrorAction SilentlyContinue
} else { '' }
$LoadedExpected  = $EditorLogText -match 'L_CyclingTest'
$LoadedTemplate  = $EditorLogText -match 'Templates/OpenWorld' -or $EditorLogText -match 'OpenWorld'
$PawnFound       = $EditorLogText -match 'BikePlaceholder' -or $EditorLogText -match 'ACyclingPrototypePawn'
# The PerformanceProof test logs a definitive snapshot line per phase.
# Their presence is the authoritative proof that the placed Pawn exists
# and is being exercised through StartRide / StopRide / RestartRide.
$PerformanceSnapshots = ([regex]::Matches($EditorLogText, "PerformanceProof snapshot '")).Count
# The 'post_restart' snapshot has the canonical coasting numbers
# (entry speed 4.590098 m/s, entry distance 15.567393 m, entry elapsed
# 5.000000 s) which match the documentation's expected post-Restart
# trajectory from zero. Confirming this line is present proves the
# Pawn was actually instantiated in the loaded L_CyclingTest world.
$CoastingPattern   = 'speed_mps=4\.590098'
$CoastingObserved  = $EditorLogText -match $CoastingPattern

# --- (4) Insights analysis on the produced .utrace ----------------------

$InsightsAnalysisStatus = 'skipped'
$InsightsAnalysisError  = $null
# `stat startfile` writes the .uestats under Saved/Profiling/UnrealStats/,
# not next to the .utrace. Copy it into the artifact root for evidence
# uniformity, when present.
$ProjectDir = Split-Path -Path $ProjectPath -Parent
$UestatsSourceDir = Join-Path -Path $ProjectDir -ChildPath 'Saved/Profiling/UnrealStats'
if (-not $SkipUestats -and (Test-Path -LiteralPath $UestatsSourceDir)) {
    $LatestUestats = Get-ChildItem -LiteralPath $UestatsSourceDir -Filter '*.uestats' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($LatestUestats) {
        Copy-Item -LiteralPath $LatestUestats.FullName -Destination $UestatsFile -Force
    }
}

if (-not $SkipInsightsAnalysis -and $InsightsPath -and (Test-Path -LiteralPath $TraceFile)) {
    Write-Host ""
    Write-Host "[2/5] Running Unreal Insights headless analysis..." -ForegroundColor Cyan
    $InsightsLog = Join-Path -Path $ArtifactRoot -ChildPath 'insights_analysis.log'
    $InsightsProc = Start-Process -FilePath $InsightsPath `
        -ArgumentList @(
            ('-OpenTraceFile=' + $TraceFile),
            '-AutoQuit'
        ) `
        -NoNewWindow -PassThru -RedirectStandardOutput $InsightsLog `
        -WorkingDirectory $RepoRoot
    if ($InsightsProc.WaitForExit(180000)) {
        $InsightsAnalysisStatus = "exit=$($InsightsProc.ExitCode)"
    } else {
        try { $InsightsProc | Stop-Process -Force } catch { }
        $InsightsAnalysisStatus = 'timeout'
    }
} else {
    Write-Host "[2/5] Skipping Insights analysis (-SkipInsightsAnalysis or no .utrace)." -ForegroundColor Yellow
}

# --- (5) Per-frame CSV summary -----------------------------------------

$FrameSummary = $null
if (Test-Path -LiteralPath $CsvFile) {
    Write-Host ""
    Write-Host "[3/5] Summarising per-frame timing CSV..." -ForegroundColor Cyan
    $FrameSummary = & {
        $Rows = Import-Csv -LiteralPath $CsvFile
        $Cols = 'frame_ms','game_ms','draw_ms','rhi_ms','game_wait_ms','frame_avg_ms','gpu_ms','render_avg_ms','rhi_avg_ms'
        $Out = [ordered]@{
            RowCount = ($Rows | Measure-Object).Count
            Columns  = @{}
            Span     = @{
                FirstRelS = if ($Rows.Count -gt 0) { [double]($Rows | Select-Object -First 1).rel_s } else { 0 }
                LastRelS  = if ($Rows.Count -gt 0) { [double]($Rows | Select-Object -Last 1).rel_s } else { 0 }
            }
        }
        foreach ($c in $Cols) {
            $Vals = @($Rows | ForEach-Object { [double]$_.($c) })
            $Sorted = $Vals | Sort-Object
            $n = $Sorted.Count
            if ($n -gt 0) {
                $P95idx = [math]::Max(0, [int]([math]::Floor(0.95 * ($n - 1))))
                $P99idx = [int]([math]::Floor(0.99 * ($n - 1)))
                $Medidx = [int]([math]::Floor(0.50 * ($n - 1)))
                $Out.Columns[$c] = [ordered]@{
                    Min    = [double]($Sorted | Select-Object -First 1)
                    Max    = [double]($Sorted | Select-Object -Last 1)
                    Avg    = [double](($Vals | Measure-Object -Average).Average)
                    Median = [double]$Sorted[$Medidx]
                    P95    = [double]$Sorted[$P95idx]
                    P99    = [double]$Sorted[$P99idx]
                }
            } else {
                $Out.Columns[$c] = $null
            }
        }
        $Out
    }
}

# --- (6) Hitch observation ---------------------------------------------

$HitchReport = $null
if (Test-Path -LiteralPath $CsvFile) {
    Write-Host ""
    Write-Host "[4/5] Computing hitch report from per-frame CSV..." -ForegroundColor Cyan
    $HitchReport = & {
        $Rows = Import-Csv -LiteralPath $CsvFile
        $Frames = @($Rows | ForEach-Object { [double]$_.frame_ms })
        $RelS   = @($Rows | ForEach-Object { [double]$_.rel_s })
        if ($Frames.Count -lt 2) { return $null }
        # 60 FPS budget = 16.67 ms. Anything 2x the median is a hitch.
        $SortedFrames = $Frames | Sort-Object
        $MedianIdx = [int]([math]::Floor(0.50 * ($SortedFrames.Count - 1)))
        $Median = $SortedFrames[$MedianIdx]
        $Threshold = [math]::Max(33.0, 2.0 * $Median)
        $TopIdx = $SortedFrames.Count - 1
        $H = [ordered]@{
            MedianFrameMs     = [double]$Median
            HitchThresholdMs  = [double]$Threshold
            MaxFrameMs        = [double]$SortedFrames[$TopIdx]
            HitchCount        = 0
            BiggestHitchRelS  = 0
            BiggestHitchMs    = 0
            WarmupFrameMs     = $null
            NormalRideFrameMs = $null
        }
        for ($i = 0; $i -lt $Frames.Count; $i++) {
            if ($Frames[$i] -ge $Threshold) {
                $H.HitchCount += 1
                if ($Frames[$i] -gt $H.BiggestHitchMs) {
                    $H.BiggestHitchMs   = $Frames[$i]
                    $H.BiggestHitchRelS = $RelS[$i]
                }
            }
        }
        # Warmup segment is the first ~5 s of rel_s; normal ride is the
        # bulk thereafter. Use 25th and 75th percentiles as summaries.
        $Warmup = @(); $Normal = @()
        for ($i = 0; $i -lt $Frames.Count; $i++) {
            if ($RelS[$i] -lt 5.0) { $Warmup += $Frames[$i] }
            else { $Normal += $Frames[$i] }
        }
        if ($Warmup.Count -gt 0) {
            $H.WarmupFrameMs = [ordered]@{
                Count = $Warmup.Count
                Avg   = [double](($Warmup | Measure-Object -Average).Average)
                Max   = [double](($Warmup | Measure-Object -Maximum).Maximum)
            }
        }
        if ($Normal.Count -gt 0) {
            $H.NormalRideFrameMs = [ordered]@{
                Count = $Normal.Count
                Avg   = [double](($Normal | Measure-Object -Average).Average)
                Max   = [double](($Normal | Measure-Object -Maximum).Maximum)
            }
        }
        $H
    }
}

# --- (7) Summary -------------------------------------------------------

Write-Host ""
Write-Host "[5/5] Writing summary..." -ForegroundColor Cyan

$TraceExists = Test-Path -LiteralPath $TraceFile
$UestatsExists = Test-Path -LiteralPath $UestatsFile
$CsvExists = Test-Path -LiteralPath $CsvFile
$ScreenshotExists = Test-Path -LiteralPath $ScreenshotFile
$TraceSize = if ($TraceExists) { (Get-Item -LiteralPath $TraceFile).Length } else { 0 }
$UestatsSize = if ($UestatsExists) { (Get-Item -LiteralPath $UestatsFile).Length } else { 0 }
$CsvSize = if ($CsvExists) { (Get-Item -LiteralPath $CsvFile).Length } else { 0 }
$ScreenshotSize = if ($ScreenshotExists) { (Get-Item -LiteralPath $ScreenshotFile).Length } else { 0 }

$Summary = [ordered]@{
    TimestampUtc         = (Get-Date).ToUniversalTime().ToString('o')
    RepoRoot             = $RepoRoot
    ProjectPath          = $ProjectPath
    ArtifactRoot         = $ArtifactRoot
    EngineRoot           = $Context.EngineRoot
    Branch               = $Context.Branch
    Head                 = $Context.Head
    MapUrl               = $MapArg
    Editor               = $UEditor
    EditorExitCode       = $Proc.ExitCode
    EditorLogPath        = $AbsLog
    EditorLogLoadedExpected  = [bool]$LoadedExpected
    EditorLogLoadedTemplate  = [bool]$LoadedTemplate
    EditorLogPawnReference   = [bool]$PawnFound
    EditorLogSnapshotCount   = $PerformanceSnapshots
    EditorLogCoastingObserved = [bool]$CoastingObserved
    TraceChannels        = $TraceChannels
    TraceFile            = $TraceFile
    TraceExists          = $TraceExists
    TraceSizeBytes       = $TraceSize
    InsightsAnalysisStatus = $InsightsAnalysisStatus
    UestatsFile          = $UestatsFile
    UestatsExists        = $UestatsExists
    UestatsSizeBytes     = $UestatsSize
    CsvFile              = $CsvFile
    CsvExists            = $CsvExists
    CsvSizeBytes         = $CsvSize
    ScreenshotFile       = $ScreenshotFile
    ScreenshotExists     = $ScreenshotExists
    ScreenshotSizeBytes  = $ScreenshotSize
    FrameSummary         = $FrameSummary
    HitchReport          = $HitchReport
}
$Summary | ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath (Join-Path -Path $ArtifactRoot -ChildPath 'insights_summary.json') -Encoding UTF8

# Friendly console output
Write-Host ("Editor exit code   : {0}" -f $Proc.ExitCode)
Write-Host ("Map loaded         : expected={0} template-fallback={1} pawn-ref={2} snapshots={3} coasting={4}" -f `
    [bool]$LoadedExpected, [bool]$LoadedTemplate, [bool]$PawnFound, $PerformanceSnapshots, [bool]$CoastingObserved)
Write-Host ("Trace file         : {0} (exists={1}, size={2})" -f $TraceFile, $TraceExists, $TraceSize)
Write-Host ("Uestats            : {0} (exists={1}, size={2})" -f $UestatsFile, $UestatsExists, $UestatsSize)
Write-Host ("CSV (Frame/Game/...) : {0} (exists={1}, size={2})" -f $CsvFile, $CsvExists, $CsvSize)
Write-Host ("Screenshot         : {0} (exists={1}, size={2})" -f $ScreenshotFile, $ScreenshotExists, $ScreenshotSize)
Write-Host ("Insights analysis  : {0}" -f $InsightsAnalysisStatus)

# --- (8) Exit policy ---------------------------------------------------

$HardFail = $false
$Reasons  = @()
if (-not $LoadedExpected)   { $HardFail = $true; $Reasons += "editor log does not confirm L_CyclingTest was loaded (likely wrong map URL or template fallback)" }
if ($LoadedTemplate)        { $HardFail = $true; $Reasons += "editor log shows OpenWorld template fallback - map URL was rejected" }
if ($PerformanceSnapshots -lt 5) { $HardFail = $true; $Reasons += ("editor log shows only {0} PerformanceProof snapshots - expected at least 5 (warmup, normal, paused, resumed, post_restart, final)" -f $PerformanceSnapshots) }
if (-not $CoastingObserved) { $HardFail = $true; $Reasons += "editor log does not contain the post-Restart coasting entry speed (4.590098 m/s) - Pawn was not driven" }
if (-not $TraceExists)      { $HardFail = $true; $Reasons += ".utrace was not produced" }
if ($TraceSize -lt 1024)    { $HardFail = $true; $Reasons += (".utrace is suspiciously small ({0} bytes)" -f $TraceSize) }
if (-not $CsvExists)        { $HardFail = $true; $Reasons += "per-frame CSV was not produced" }
if ($CsvSize -lt 1024)      { $HardFail = $true; $Reasons += ("per-frame CSV is suspiciously small ({0} bytes)" -f $CsvSize) }
if (-not $ScreenshotExists) { $HardFail = $true; $Reasons += "PerformanceProof screenshot was not produced" }
if ($ScreenshotSize -lt 4096) { $HardFail = $true; $Reasons += ("PerformanceProof screenshot is suspiciously small ({0} bytes) - viewport likely empty" -f $ScreenshotSize) }

if ($HardFail) {
    Write-Host ""
    Write-Host "PERFORMANCE PROOF FAILED:" -ForegroundColor Red
    foreach ($r in $Reasons) { Write-Host ("  - {0}" -f $r) -ForegroundColor Red }
    Write-Host ("See {0} for full editor log." -f $AbsLog)
    exit 1
}

Write-Host ""
Write-Host "PERFORMANCE PROOF PASSED." -ForegroundColor Green
exit 0
