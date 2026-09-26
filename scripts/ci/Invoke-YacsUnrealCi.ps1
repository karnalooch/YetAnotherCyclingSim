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


function Write-YacsUnrealFailureContext {
    param(
        [Parameter(Mandatory=$true)] [string] $Reason
    )

    $FailureContextPath = Join-Path -Path $ArtifactRoot -ChildPath 'failure_context.txt'
    $Lines = [System.Collections.Generic.List[string]]::new()
    [void]$Lines.Add('=== YACS Unreal CI failure context ===')
    [void]$Lines.Add(('TimestampUtc : {0}' -f (Get-Date).ToUniversalTime().ToString('o')))
    [void]$Lines.Add(('Reason       : {0}' -f $Reason))
    [void]$Lines.Add('')

    $Candidates = @(
        [pscustomobject]@{ Label = 'preflight'; Path = (Join-Path $ArtifactRoot 'Preflight/preflight.txt'); Tail = 120 },
        [pscustomobject]@{ Label = 'build_editor'; Path = (Join-Path $ArtifactRoot 'Proof/build_editor.log'); Tail = 160 },
        [pscustomobject]@{ Label = 'automation_run'; Path = (Join-Path $ArtifactRoot 'Proof/automation_run.log'); Tail = 160 },
        [pscustomobject]@{ Label = 'proof_summary'; Path = (Join-Path $ArtifactRoot 'Proof/summary.txt'); Tail = 120 },
        [pscustomobject]@{ Label = 'automation_index'; Path = (Join-Path $ArtifactRoot 'Proof/AutomationReport/index.json'); Tail = 120 }
    )

    foreach ($Candidate in $Candidates) {
        [void]$Lines.Add(('--- {0}: {1} ---' -f $Candidate.Label, $Candidate.Path))
        if (-not (Test-Path -LiteralPath $Candidate.Path -PathType Leaf)) {
            [void]$Lines.Add('<missing>')
            [void]$Lines.Add('')
            continue
        }

        try {
            $TailLines = @(Get-Content -LiteralPath $Candidate.Path -Tail $Candidate.Tail -ErrorAction Stop)
            foreach ($Line in $TailLines) {
                [void]$Lines.Add([string]$Line)
            }
        }
        catch {
            [void]$Lines.Add(('<read failed: {0}>' -f $_.Exception.Message))
        }
        [void]$Lines.Add('')
    }

    [void]$Lines.Add('--- artifact inventory ---')
    try {
        $Files = @(Get-ChildItem -LiteralPath $ArtifactRoot -Recurse -File -ErrorAction Stop | Sort-Object FullName)
        if ($Files.Count -eq 0) {
            [void]$Lines.Add('<no files>')
        }
        foreach ($File in $Files) {
            $Relative = $File.FullName.Substring($ArtifactRoot.Length).TrimStart('\', '/')
            [void]$Lines.Add(('{0} ({1} bytes)' -f $Relative, $File.Length))
        }
    }
    catch {
        [void]$Lines.Add(('<inventory failed: {0}>' -f $_.Exception.Message))
    }

    $Lines | Set-Content -LiteralPath $FailureContextPath -Encoding UTF8

    Write-Host ''
    Write-Host '===== YACS UNREAL CI FAILURE CONTEXT =====' -ForegroundColor Red
    foreach ($Line in $Lines) {
        Write-Host $Line
    }
    Write-Host ('Failure context saved: {0}' -f $FailureContextPath) -ForegroundColor Yellow
}

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
try {
    $Context = & $Preflight @PreflightArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Unreal CI preflight failed with exit code $LASTEXITCODE."
    }
}
catch {
    Write-YacsUnrealFailureContext -Reason ('Preflight failed: {0}' -f $_.Exception.Message)
    throw
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
try {
    & $Proof @ProofArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Unreal build/Automation proof failed with exit code $LASTEXITCODE."
    }

    $SummaryPath = Join-Path -Path $ProofRoot -ChildPath 'summary.json'
    if (-not (Test-Path -LiteralPath $SummaryPath)) {
        throw "Unreal CI summary missing: $SummaryPath"
    }

    $Summary = Get-Content -LiteralPath $SummaryPath -Raw -ErrorAction Stop | ConvertFrom-Json
    if ([int]$Summary.Discovered -le 0) {
        throw 'Unreal CI requested suites but discovered zero tests.'
    }
    if ([int]$Summary.Failed -ne 0 -or [int]$Summary.Errors -ne 0) {
        throw ("Unreal CI summary is not green: failed={0}, errors={1}." -f $Summary.Failed, $Summary.Errors)
    }
}
catch {
    Write-YacsUnrealFailureContext -Reason ('Build/Automation failed: {0}' -f $_.Exception.Message)
    throw
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
    GithubRef = [string]$env:GITHUB_REF
    GithubHeadRef = [string]$env:GITHUB_HEAD_REF
    GithubBaseRef = [string]$env:GITHUB_BASE_REF
}
$CiSummaryPath = Join-Path -Path $ArtifactRoot -ChildPath 'unreal_ci_summary.json'
$CiSummary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $CiSummaryPath -Encoding UTF8

Write-Host 'UNREAL CI PROOF PASSED.' -ForegroundColor Green
Write-Host ("Summary: {0}" -f $CiSummaryPath)
exit 0
