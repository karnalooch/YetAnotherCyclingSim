<# 
.SYNOPSIS
    Resolve or record reusable YACS Unreal CI state.

.DESCRIPTION
    Separates compile reuse from runtime/proof reuse. A cache hit is accepted
    only when the repository fingerprints, installed UE build identity and
    expected Editor binaries match. Missing or ambiguous evidence fails closed.
#>
[CmdletBinding()]
param(
    [ValidateSet('Resolve','Record')] [string] $Action = 'Resolve',
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [Parameter(Mandatory=$true)] [string] $ExpectedCompileFingerprint,
    [Parameter(Mandatory=$true)] [string] $ExpectedProofFingerprint,
    [ValidateSet('compile','runtime')] [string] $CompletedMode,
    [string] $GithubOutput
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$StateDir = Join-Path $RepoRoot 'Saved/BuildCache/UnrealCi'
$StatePath = Join-Path $StateDir 'state.json'
$EvidenceDir = Join-Path $RepoRoot 'Saved/RuntimeProof/CI/Unreal'
$EvidencePath = Join-Path $EvidenceDir 'cache_resolution.json'
$ExpectedBinaries = @(
    (Join-Path $RepoRoot 'Binaries/Win64/UnrealEditor-YetAnotherCyclingSim.dll'),
    (Join-Path $RepoRoot 'Binaries/Win64/UnrealEditor-YetAnotherCyclingSimEditor.dll')
)

function Get-YacsEngineIdentity {
    $Roots = @(
        'D:\Epic Games\UE_5.8',
        'D:\UE_5.8',
        'C:\Program Files\Epic Games\UE_5.8',
        'C:\UE_5.8'
    )
    foreach ($Root in $Roots) {
        $BuildVersion = Join-Path $Root 'Engine/Build/Build.version'
        if (-not (Test-Path -LiteralPath $BuildVersion -PathType Leaf)) { continue }
        $Hash = (Get-FileHash -LiteralPath $BuildVersion -Algorithm SHA256).Hash.ToLowerInvariant()
        $Json = Get-Content -LiteralPath $BuildVersion -Raw | ConvertFrom-Json
        return [pscustomobject]@{
            Root = (Resolve-Path -LiteralPath $Root).Path
            Hash = $Hash
            Version = ('{0}.{1}.{2}-{3}' -f $Json.MajorVersion,$Json.MinorVersion,$Json.PatchVersion,$Json.Changelist)
        }
    }
    return $null
}

Push-Location $RepoRoot
try { $ActualHead = (& git rev-parse HEAD).Trim() } finally { Pop-Location }
if ($ActualHead -ne $ExpectedHead) {
    throw "Unreal cache provenance mismatch: HEAD '$ActualHead' != expected '$ExpectedHead'."
}

$Engine = Get-YacsEngineIdentity
$EngineIdentity = if ($Engine) { "$($Engine.Version):$($Engine.Hash)" } else { 'unresolved' }

if ($Action -eq 'Record') {
    if (-not $CompletedMode) { throw '-CompletedMode is required for Record.' }
    $SummaryPath = Join-Path $EvidenceDir 'unreal_ci_summary.json'
    if (-not (Test-Path -LiteralPath $SummaryPath -PathType Leaf)) {
        throw "Cannot record Unreal cache state without successful proof summary: $SummaryPath"
    }
    $Summary = Get-Content -LiteralPath $SummaryPath -Raw | ConvertFrom-Json
    if ([int]$Summary.Failed -ne 0 -or [int]$Summary.Errors -ne 0 -or [int]$Summary.Discovered -le 0) {
        throw 'Refusing to record non-green Unreal proof state.'
    }
    if (-not $Engine) { throw 'Cannot record cache state because UE engine identity is unresolved.' }

    $Previous = $null
    if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
        try { $Previous = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json } catch { $Previous = $null }
    }
    $PreviousCompileHead = $null
    if ($Previous -and $Previous.PSObject.Properties.Name -contains 'CompileHead') {
        $PreviousCompileHead = [string]$Previous.CompileHead
    }
    $CompileHead = if ($CompletedMode -eq 'compile') {
        $ExpectedHead
    }
    elseif ($PreviousCompileHead) {
        $PreviousCompileHead
    }
    else {
        $ExpectedHead
    }

    New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
    $State = [ordered]@{
        SchemaVersion = 1
        CompileFingerprint = $ExpectedCompileFingerprint
        ProofFingerprint = $ExpectedProofFingerprint
        EngineIdentity = $EngineIdentity
        CompilePassed = $true
        ProofPassed = $true
        CompileHead = $CompileHead
        ProofHead = $ExpectedHead
        UpdatedUtc = (Get-Date).ToUniversalTime().ToString('o')
    }
    $Tmp = "$StatePath.tmp"
    $State | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Tmp -Encoding UTF8
    Move-Item -LiteralPath $Tmp -Destination $StatePath -Force
    Write-Host "Recorded verified Unreal CI state: $StatePath"
    exit 0
}

New-Item -ItemType Directory -Path $EvidenceDir -Force | Out-Null
$Mode = 'compile'
$Reason = 'missing-cache-state'
$Purge = $false
$PreviousProofHead = $null

$State = $null
if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
    try { $State = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json }
    catch {
        $Reason = 'invalid-cache-state'
        $Purge = $true
    }
}

if ($State) {
    try {
        $RequiredStateFields = @(
            'SchemaVersion',
            'CompileFingerprint',
            'ProofFingerprint',
            'EngineIdentity',
            'CompilePassed',
            'ProofPassed',
            'ProofHead'
        )
        foreach ($Field in $RequiredStateFields) {
            if ($State.PSObject.Properties.Name -notcontains $Field) {
                throw "cache state missing required field '$Field'"
            }
        }

        $PreviousProofHead = [string]$State.ProofHead
        if (-not $Engine) {
            $Reason = 'engine-identity-unresolved'
            $Purge = $true
        }
        elseif ([int]$State.SchemaVersion -ne 1) {
            $Reason = 'cache-schema-mismatch'
            $Purge = $true
        }
        elseif ([string]$State.EngineIdentity -ne $EngineIdentity) {
            $Reason = 'engine-identity-mismatch'
            $Purge = $true
        }
        elseif (-not [bool]$State.CompilePassed) {
            $Reason = 'previous-compile-not-verified'
        }
        elseif ([string]$State.CompileFingerprint -ne $ExpectedCompileFingerprint) {
            $Reason = 'compile-fingerprint-mismatch'
        }
        elseif (@($ExpectedBinaries | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) }).Count -gt 0) {
            $Reason = 'expected-binary-missing'
        }
        elseif (-not [bool]$State.ProofPassed) {
            $Mode = 'runtime'
            $Reason = 'previous-proof-not-verified'
        }
        elseif ([string]$State.ProofFingerprint -ne $ExpectedProofFingerprint) {
            $Mode = 'runtime'
            $Reason = 'proof-fingerprint-mismatch'
        }
        else {
            $Mode = 'static'
            $Reason = 'verified-equivalent-proof'
        }
    }
    catch {
        $Mode = 'compile'
        $Reason = 'invalid-cache-state-shape'
        $Purge = $true
        $PreviousProofHead = $null
        Write-Warning ("Ignoring invalid Unreal cache state: {0}" -f $_.Exception.Message)
    }
}

$Evidence = [ordered]@{
    SchemaVersion = 1
    Head = $ExpectedHead
    Mode = $Mode
    Reason = $Reason
    PurgeBuildCache = $Purge
    CompileFingerprint = $ExpectedCompileFingerprint
    ProofFingerprint = $ExpectedProofFingerprint
    EngineIdentity = $EngineIdentity
    PreviousProofHead = $PreviousProofHead
    ExpectedBinaries = $ExpectedBinaries
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
}
$Evidence | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $EvidencePath -Encoding UTF8

$Out = if ($GithubOutput) { $GithubOutput } elseif ($env:GITHUB_OUTPUT) { $env:GITHUB_OUTPUT } else { $null }
if ($Out) {
    "mode=$Mode" | Out-File -LiteralPath $Out -Append -Encoding utf8
    "reason=$Reason" | Out-File -LiteralPath $Out -Append -Encoding utf8
    "purge_build_cache=$($Purge.ToString().ToLowerInvariant())" | Out-File -LiteralPath $Out -Append -Encoding utf8
    "engine_identity=$EngineIdentity" | Out-File -LiteralPath $Out -Append -Encoding utf8
}

Write-Host "UNREAL CACHE: mode=$Mode reason=$Reason purge=$Purge"
exit 0
