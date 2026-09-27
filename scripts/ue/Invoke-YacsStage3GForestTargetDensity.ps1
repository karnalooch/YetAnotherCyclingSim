<# Stage 3G forest target-density performance gate. #>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [double] $ForestP95BudgetMs = 14.0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) { $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject' }
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) { $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/Issue201/ForestTargetDensity' }
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) { $ArtifactRoot = Join-Path $RepoRoot $ArtifactRoot }
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

if ($ForestP95BudgetMs -le 0.0 -or $ForestP95BudgetMs -gt 16.6667) {
    throw 'ForestP95BudgetMs must be inside (0, 16.6667].'
}

$PerfRoot = Join-Path $ArtifactRoot 'EnvironmentPerformance'
$PerfHarness = Join-Path $RepoRoot 'scripts/ue/Invoke-YacsStage3GEnvironmentPerformance.ps1'
$PerfArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $PerfRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
    TargetFps = 60.0
    AllowedOverBudgetRatio = 0.05
}
& $PerfHarness @PerfArgs
if ($LASTEXITCODE -ne 0) {
    throw 'Base Stage 3G environment 60 FPS gate failed for target-density forest.'
}

$SummaryPath = Join-Path $PerfRoot 'stage3g_environment_performance_summary.json'
if (-not (Test-Path -LiteralPath $SummaryPath -PathType Leaf)) {
    throw 'Environment performance summary is missing.'
}
$Summary = Get-Content -LiteralPath $SummaryPath -Raw -ErrorAction Stop | ConvertFrom-Json
$Forest = @($Summary.Sectors | Where-Object { $_.Sector -eq 'forest' })
if ($Forest.Count -ne 1) {
    throw "Expected exactly one forest sector result; found $($Forest.Count)."
}

$ForestResult = $Forest[0]
$Reasons = @()
if ([double]$ForestResult.FrameP95Ms -gt $ForestP95BudgetMs) {
    $Reasons += ("forest frame p95 {0:F3} ms exceeds target-density budget {1:F3} ms" -f [double]$ForestResult.FrameP95Ms, $ForestP95BudgetMs)
}
if ($null -eq $ForestResult.GpuP95Ms -or [double]$ForestResult.GpuP95Ms -gt $ForestP95BudgetMs) {
    $GpuText = if ($null -eq $ForestResult.GpuP95Ms) { '<missing>' } else { '{0:F3}' -f [double]$ForestResult.GpuP95Ms }
    $Reasons += ("forest GPU p95 {0} ms exceeds/is unavailable for target-density budget {1:F3} ms" -f $GpuText, $ForestP95BudgetMs)
}

$Result = [ordered]@{
    SchemaVersion = 1
    Branch = $Summary.Branch
    Head = $Summary.Head
    Resolution = $Summary.Resolution
    ReferenceGpuMatched = $Summary.ReferenceGpuMatched
    ForestP95BudgetMs = $ForestP95BudgetMs
    ForestFrameP95Ms = [double]$ForestResult.FrameP95Ms
    ForestGpuP95Ms = $ForestResult.GpuP95Ms
    ForestAverageFps = [double]$ForestResult.AverageFps
    ForestOverBudgetRatio = [double]$ForestResult.OverBudgetRatio
    Base60FpsGate = $Summary.Result
    ShadowBenchmarkMode = 'normal project rendering; no shadow-disable override'
    ForestLayerProfile = 'target_density_v1'
    Result = if ($Reasons.Count -eq 0) { 'PASS' } else { 'FAIL' }
    FailureReasons = $Reasons
}
$ResultPath = Join-Path $ArtifactRoot 'stage3g_forest_target_density_summary.json'
$Result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ResultPath -Encoding UTF8

if ($Reasons.Count -gt 0) {
    Write-Host 'STAGE 3G FOREST TARGET-DENSITY GATE FAILED:' -ForegroundColor Red
    foreach ($Reason in $Reasons) { Write-Host ("  - {0}" -f $Reason) -ForegroundColor Red }
    exit 1
}

Write-Host ("FOREST TARGET-DENSITY PASS: frame p95={0:F3} ms GPU p95={1:F3} ms avg={2:F2} FPS" -f [double]$ForestResult.FrameP95Ms, [double]$ForestResult.GpuP95Ms, [double]$ForestResult.AverageFps) -ForegroundColor Green
exit 0
