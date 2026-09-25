<#
.SYNOPSIS
    Local entry point for the future real Unreal Engine CI lane (#24).

.DESCRIPTION
    Performs a fail-closed runner preflight, enforces Unreal Engine 5.8,
    then reuses Invoke-YacsProof.ps1 to build YetAnotherCyclingSimEditor
    and execute the scoped Automation suites required by issue #24.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [string] $ExpectedBranch,
    [string] $TestFilter = 'CyclingSession+CyclingPhysics+CyclingInput'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) {
    $ProjectPath = Join-Path -Path $RepoRoot -ChildPath 'YetAnotherCyclingSim.uproject'
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/CI/Unreal'
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

Push-Location -LiteralPath $RepoRoot
try {
    $ActualBranch = (& git rev-parse --abbrev-ref HEAD).Trim()
    $ActualHead = (& git rev-parse HEAD).Trim()
} finally {
    Pop-Location
}

if (-not $ExpectedBranch) { $ExpectedBranch = $ActualBranch }
if ($ActualHead -ne $ExpectedHead) {
    throw "Unreal CI provenance mismatch: HEAD '$ActualHead' != expected '$ExpectedHead'."
}

$PreflightRoot = Join-Path -Path $ArtifactRoot -ChildPath 'Preflight'
$Preflight = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Preflight-YacsProof.ps1'
$PreflightArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $PreflightRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
}
$Context = & $Preflight @PreflightArgs
if ($LASTEXITCODE -ne 0) {
    throw "Unreal CI preflight failed with exit code $LASTEXITCODE."
}

if (-not $Context.EngineVersion) { throw 'Unreal CI preflight did not resolve an engine version.' }
if ($Context.EngineVersion.MajorVersion -ne 5 -or $Context.EngineVersion.MinorVersion -ne 8) {
    throw ("Unreal CI requires UE 5.8.x; resolved {0}.{1}.{2}." -f $Context.EngineVersion.MajorVersion, $Context.EngineVersion.MinorVersion, $Context.EngineVersion.PatchVersion)
}

$ProofRoot = Join-Path -Path $ArtifactRoot -ChildPath 'Proof'
$Proof = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Invoke-YacsProof.ps1'
$ProofArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $ProofRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
    TestFilter = $TestFilter
}
& $Proof @ProofArgs
if ($LASTEXITCODE -ne 0) {
    throw "Unreal build/Automation proof failed with exit code $LASTEXITCODE."
}

$SummaryPath = Join-Path -Path $ProofRoot -ChildPath 'summary.json'
if (-not (Test-Path -LiteralPath $SummaryPath)) { throw "Unreal CI summary missing: $SummaryPath" }
$Summary = Get-Content -LiteralPath $SummaryPath -Raw -ErrorAction Stop | ConvertFrom-Json
if ([int]$Summary.Discovered -le 0) { throw 'Unreal CI requested suites but discovered zero tests.' }
if ([int]$Summary.Failed -ne 0 -or [int]$Summary.Errors -ne 0) {
    throw ("Unreal CI summary is not green: failed={0}, errors={1}." -f $Summary.Failed, $Summary.Errors)
}

$CiSummary = [ordered]@{
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
    Branch = $ActualBranch
    Head = $ActualHead
    ExpectedHead = $ExpectedHead
    UnrealVersion = ('{0}.{1}.{2}' -f $Context.EngineVersion.MajorVersion, $Context.EngineVersion.MinorVersion, $Context.EngineVersion.PatchVersion)
    TestFilter = $TestFilter
    Discovered = [int]$Summary.Discovered
    Passed = [int]$Summary.Passed
    Failed = [int]$Summary.Failed
    Errors = [int]$Summary.Errors
}
$CiSummaryPath = Join-Path -Path $ArtifactRoot -ChildPath 'unreal_ci_summary.json'
$CiSummary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $CiSummaryPath -Encoding UTF8

Write-Host 'UNREAL CI PROOF PASSED.' -ForegroundColor Green
Write-Host ("Summary: {0}" -f $CiSummaryPath)
exit 0
