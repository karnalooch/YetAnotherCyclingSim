
<# Stage 3G fail-closed environment performance gate. #>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [double] $TargetFps = 60.0,
    [double] $AllowedOverBudgetRatio = 0.05,
    [int] $MinimumSamplesPerSector = 120,
    [int] $MinimumPositiveGpuSamplesPerSector = 30,
    [switch] $SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) { $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject' }
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) { $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/Issue80/Stage3G/EnvironmentPerformance' }
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

if ($TargetFps -le 0.0) { throw 'TargetFps must be positive.' }
if ($AllowedOverBudgetRatio -lt 0.0 -or $AllowedOverBudgetRatio -gt 1.0) { throw 'AllowedOverBudgetRatio must be inside [0,1].' }

$FrameBudgetMs = 1000.0 / $TargetFps
$CsvPath = Join-Path $ArtifactRoot 'stage3g_environment_performance.csv'
$SummaryPath = Join-Path $ArtifactRoot 'stage3g_environment_performance_summary.json'
$LogPath = Join-Path $ArtifactRoot 'editor_session_stage3g_environment_performance.log'
foreach ($Path in @($CsvPath, $SummaryPath, $LogPath)) {
    if (Test-Path -LiteralPath $Path) { Remove-Item -LiteralPath $Path -Force }
}

Write-Host '=== YACS Stage 3G environment performance gate ===' -ForegroundColor Cyan
Write-Host ("Target: {0:F2} FPS / {1:F4} ms p95 per sector" -f $TargetFps, $FrameBudgetMs)
Write-Host ("Over-budget allowance: {0:P1}" -f $AllowedOverBudgetRatio)
Write-Host ("Branch / HEAD: {0} / {1}" -f $ExpectedBranch, $ExpectedHead)

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$PreflightArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $ArtifactRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
}
$Context = & $Preflight @PreflightArgs
if ($LASTEXITCODE -ne 0) { throw 'Stage 3G performance preflight failed.' }

$UEditor = $Context.UnrealEditorPath
if (-not $UEditor -or -not (Test-Path -LiteralPath $UEditor)) { throw 'UnrealEditor.exe GUI binary is unavailable.' }

$GpuNames = @(Get-CimInstance Win32_VideoController -ErrorAction Stop | ForEach-Object { [string]$_.Name } | Where-Object { $_ })
$CpuNames = @(Get-CimInstance Win32_Processor -ErrorAction Stop | ForEach-Object { [string]$_.Name } | Where-Object { $_ })
$ReferenceGpuMatched = [bool]($GpuNames | Where-Object { $_ -match '(?i)RTX\s*2070.*SUPER' })
if (-not $ReferenceGpuMatched) { throw ("Reference GPU mismatch. Expected RTX 2070 Super class hardware; detected: {0}" -f ($GpuNames -join '; ')) }

if (-not $SkipBuild) {
    Write-Host '[1/5] Building YetAnotherCyclingSimEditor Development...' -ForegroundColor Cyan
    $BuildLog = Join-Path $ArtifactRoot 'build_editor.log'
    $BuildBat = Join-Path $Context.EngineRoot 'Engine/Build/BatchFiles/Build.bat'
    $BuildArgs = @($ProjectPath, 'YetAnotherCyclingSimEditor', 'Win64', 'Development', '-WaitMutex', '-FromMsBuild')
    $BuildProc = Start-Process -FilePath $BuildBat -ArgumentList $BuildArgs -NoNewWindow -PassThru -RedirectStandardOutput $BuildLog -WorkingDirectory (Split-Path $BuildBat -Parent)
    $BuildProc.WaitForExit()
    if ($BuildProc.ExitCode -ne 0) { throw "Editor build failed with exit code $($BuildProc.ExitCode). See $BuildLog" }
}

Write-Host '[2/5] Running rendered 1920x1080 sector sampler...' -ForegroundColor Cyan
[System.Environment]::SetEnvironmentVariable('YACS_STAGE3G_PERF_CSV', $CsvPath, 'Process')

$MapArg = '/Game/Prototype/Maps/L_CyclingTest.umap'
$ExeccmdsValue = 'Automation RunTests CyclingRuntime.Stage3GEnvironmentPerformanceProof;Quit'
$EditorArgs = @(
    $ProjectPath, $MapArg, '-game', '-windowed', '-ResX=1920', '-ResY=1080',
    '-NoVSync', '-FixedSeed', '-NoSplash', '-unattended', '-stdout',
    ('-AbsLog=' + $LogPath), ('-execcmds="' + $ExeccmdsValue + '"')
)
$Proc = Start-Process -FilePath $UEditor -ArgumentList $EditorArgs -NoNewWindow -PassThru -RedirectStandardOutput $LogPath -WorkingDirectory $RepoRoot
$TimeoutSec = 240
if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
    try { $Proc | Stop-Process -Force } catch { }
    throw "Stage 3G environment performance editor timed out after $TimeoutSec s."
}

if (-not (Test-Path -LiteralPath $CsvPath)) { throw 'Stage 3G environment performance CSV was not produced.' }

$LogText = if (Test-Path -LiteralPath $LogPath) { Get-Content -LiteralPath $LogPath -Raw -ErrorAction SilentlyContinue } else { '' }
if ($LogText -notmatch 'L_CyclingTest') { throw 'Performance proof log does not confirm L_CyclingTest was loaded.' }
if ($LogText -match 'Templates/OpenWorld') { throw 'Performance proof fell back to the OpenWorld template map.' }
$SectorReadyCount = ([regex]::Matches($LogText, 'Stage3GEnvironmentPerformanceProof: sector=')).Count
if ($SectorReadyCount -lt 3) { throw "Performance proof did not reach all three sectors; observed $SectorReadyCount sector-ready lines." }

Write-Host '[3/5] Evaluating per-sector 60 FPS budget...' -ForegroundColor Cyan
$Rows = @(Import-Csv -LiteralPath $CsvPath)
if ($Rows.Count -lt ($MinimumSamplesPerSector * 3)) { throw "Performance CSV has only $($Rows.Count) total rows." }

function Get-Percentile {
    param([Parameter(Mandatory=$true)] [double[]] $Values, [Parameter(Mandatory=$true)] [double] $Percentile)
    if ($Values.Count -eq 0) { return $null }
    $Sorted = @($Values | Sort-Object)
    $Index = [int][math]::Floor($Percentile * ($Sorted.Count - 1))
    return [double]$Sorted[$Index]
}

$ExpectedSectors = [ordered]@{ valley = 1200.0; forest = 4900.0; high_alpine = 8000.0 }
$Results = @()
$Reasons = @()
if ($Proc.ExitCode -ne 0) { $Reasons += "UnrealEditor exited with code $($Proc.ExitCode)." }

foreach ($Entry in $ExpectedSectors.GetEnumerator()) {
    $Sector = [string]$Entry.Key
    $DistanceM = [double]$Entry.Value
    $SectorRows = @($Rows | Where-Object { $_.sector -eq $Sector })

    if ($SectorRows.Count -lt $MinimumSamplesPerSector) {
        $Reasons += "$Sector has $($SectorRows.Count) samples; minimum is $MinimumSamplesPerSector."
        continue
    }

    $Frames = [double[]]@($SectorRows | ForEach-Object { [double]$_.frame_ms })
    $GpuPositive = [double[]]@($SectorRows | ForEach-Object { [double]$_.gpu_ms } | Where-Object { $_ -gt 0.01 })

    if ($GpuPositive.Count -lt $MinimumPositiveGpuSamplesPerSector) {
        $Reasons += "$Sector has only $($GpuPositive.Count) positive GPU samples; minimum is $MinimumPositiveGpuSamplesPerSector."
    }

    $FrameP50 = Get-Percentile -Values $Frames -Percentile 0.50
    $FrameP95 = Get-Percentile -Values $Frames -Percentile 0.95
    $FrameP99 = Get-Percentile -Values $Frames -Percentile 0.99
    $GpuP95 = if ($GpuPositive.Count -gt 0) { Get-Percentile -Values $GpuPositive -Percentile 0.95 } else { $null }
    $OverBudget = @($Frames | Where-Object { $_ -gt $FrameBudgetMs }).Count
    $OverBudgetRatio = [double]$OverBudget / [double]$Frames.Count
    $AverageFrameMs = [double](($Frames | Measure-Object -Average).Average)
    $AverageFps = 1000.0 / $AverageFrameMs

    $FramePass = [bool]($FrameP95 -le $FrameBudgetMs)
    $GpuPass = [bool]($null -ne $GpuP95 -and $GpuP95 -le $FrameBudgetMs)
    $RatioPass = [bool]($OverBudgetRatio -le $AllowedOverBudgetRatio)
    $SectorPass = [bool]($FramePass -and $GpuPass -and $RatioPass -and $GpuPositive.Count -ge $MinimumPositiveGpuSamplesPerSector)

    if (-not $FramePass) { $Reasons += ("{0} frame p95 {1:F3} ms exceeds {2:F3} ms." -f $Sector, $FrameP95, $FrameBudgetMs) }
    if (-not $GpuPass) {
        $GpuText = if ($null -eq $GpuP95) { '<missing>' } else { '{0:F3}' -f $GpuP95 }
        $Reasons += ("{0} GPU p95 {1} ms exceeds/is unavailable for {2:F3} ms budget." -f $Sector, $GpuText, $FrameBudgetMs)
    }
    if (-not $RatioPass) { $Reasons += ("{0} over-budget ratio {1:P2} exceeds {2:P2}." -f $Sector, $OverBudgetRatio, $AllowedOverBudgetRatio) }

    $Results += [ordered]@{
        Sector = $Sector
        DistanceM = $DistanceM
        SampleCount = $Frames.Count
        PositiveGpuSampleCount = $GpuPositive.Count
        FrameP50Ms = $FrameP50
        FrameP95Ms = $FrameP95
        FrameP99Ms = $FrameP99
        FrameMaxMs = [double](($Frames | Measure-Object -Maximum).Maximum)
        FrameAverageMs = $AverageFrameMs
        AverageFps = $AverageFps
        GpuP95Ms = $GpuP95
        OverBudgetFrameCount = $OverBudget
        OverBudgetRatio = $OverBudgetRatio
        Pass = $SectorPass
    }
}

$OverallPass = [bool]($Reasons.Count -eq 0 -and $Results.Count -eq 3 -and (@($Results | Where-Object { -not $_.Pass }).Count -eq 0))
$Summary = [ordered]@{
    SchemaVersion = 1
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
    Branch = $Context.Branch
    Head = $Context.Head
    Resolution = '1920x1080'
    VSync = 'disabled'
    TargetFps = $TargetFps
    FrameBudgetMs = $FrameBudgetMs
    P95FrameBudgetMs = $FrameBudgetMs
    P95GpuBudgetMs = $FrameBudgetMs
    AllowedOverBudgetRatio = $AllowedOverBudgetRatio
    MinimumSamplesPerSector = $MinimumSamplesPerSector
    MinimumPositiveGpuSamplesPerSector = $MinimumPositiveGpuSamplesPerSector
    ReferenceGpuMatched = $ReferenceGpuMatched
    GpuNames = $GpuNames
    CpuNames = $CpuNames
    EditorExitCode = $Proc.ExitCode
    Result = if ($OverallPass) { 'PASS' } else { 'FAIL' }
    Sectors = $Results
    FailureReasons = $Reasons
}
$Summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8

Write-Host '[4/5] Sector results' -ForegroundColor Cyan
foreach ($Result in $Results) {
    $GpuDisplay = if ($null -eq $Result.GpuP95Ms) { 'missing' } else { '{0:F3}' -f $Result.GpuP95Ms }
    Write-Host ("  {0,-12} p95 frame={1:F3} ms p95 GPU={2} ms avg={3:F2} FPS over={4:P2} pass={5}" -f $Result.Sector, $Result.FrameP95Ms, $GpuDisplay, $Result.AverageFps, $Result.OverBudgetRatio, $Result.Pass)
}

Write-Host '[5/5] Fail-closed result' -ForegroundColor Cyan
if (-not $OverallPass) {
    Write-Host 'STAGE 3G ENVIRONMENT PERFORMANCE GATE FAILED:' -ForegroundColor Red
    foreach ($Reason in $Reasons) { Write-Host ("  - {0}" -f $Reason) -ForegroundColor Red }
    Write-Host ("Summary: {0}" -f $SummaryPath)
    exit 1
}

Write-Host 'STAGE 3G ENVIRONMENT PERFORMANCE GATE PASSED.' -ForegroundColor Green
Write-Host ("Summary: {0}" -f $SummaryPath)
exit 0
