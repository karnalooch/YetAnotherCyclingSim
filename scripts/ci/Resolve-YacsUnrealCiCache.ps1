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
    [ValidateSet('none','warm','cold')] [string] $CompletedCompileKind = 'none',
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

Push-Location $RepoRoot
try { $ActualHead = (& git rev-parse HEAD).Trim() } finally { Pop-Location }
if ($ActualHead -ne $ExpectedHead) {
    throw "Unreal cache provenance mismatch: HEAD '$ActualHead' != expected '$ExpectedHead'."
}

$EngineResolverPath = Join-Path $RepoRoot 'scripts/ci/Resolve-YacsUnrealEngine.ps1'
if (-not (Test-Path -LiteralPath $EngineResolverPath -PathType Leaf)) {
    throw "Canonical Unreal Engine resolver is missing: $EngineResolverPath"
}
. $EngineResolverPath
$Engine = Resolve-YacsUnrealEngine -ProjectPath (Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject')
$EngineIdentity = if ($Engine) { [string] $Engine.Identity } else { 'unresolved' }
$EngineRoot = if ($Engine) { [string] $Engine.Root } else { 'unresolved' }

function Resolve-YacsToolchainIdentity {
    $VsRoots = [System.Collections.Generic.List[string]]::new()
    $VsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    if (Test-Path -LiteralPath $VsWhere -PathType Leaf) {
        $Resolved = @(
            & $VsWhere -products * -latest -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null
        )
        foreach ($Path in $Resolved) {
            if ($Path -and (Test-Path -LiteralPath $Path -PathType Container)) {
                [void]$VsRoots.Add((Resolve-Path -LiteralPath $Path).Path)
            }
        }
    }

    foreach ($Edition in @('BuildTools','Community','Professional','Enterprise')) {
        $Candidate = Join-Path $env:ProgramFiles "Microsoft Visual Studio/2022/$Edition"
        if (Test-Path -LiteralPath $Candidate -PathType Container) {
            [void]$VsRoots.Add((Resolve-Path -LiteralPath $Candidate).Path)
        }
    }

    $Compiler = $null
    $Linker = $null
    foreach ($VsRoot in @($VsRoots | Select-Object -Unique)) {
        $MsvcRoot = Join-Path $VsRoot 'VC/Tools/MSVC'
        if (-not (Test-Path -LiteralPath $MsvcRoot -PathType Container)) { continue }
        $ToolVersion = Get-ChildItem -LiteralPath $MsvcRoot -Directory -ErrorAction SilentlyContinue |
            Sort-Object -Property Name -Descending |
            Select-Object -First 1
        if (-not $ToolVersion) { continue }

        $Cl = Join-Path $ToolVersion.FullName 'bin/Hostx64/x64/cl.exe'
        $Link = Join-Path $ToolVersion.FullName 'bin/Hostx64/x64/link.exe'
        if ((Test-Path -LiteralPath $Cl -PathType Leaf) -and
            (Test-Path -LiteralPath $Link -PathType Leaf)) {
            $Compiler = $Cl
            $Linker = $Link
            break
        }
    }

    if (-not $Compiler) {
        $Command = Get-Command cl.exe -ErrorAction SilentlyContinue
        if ($Command) {
            $Compiler = $Command.Source
            $LinkCandidate = Join-Path (Split-Path -Parent $Compiler) 'link.exe'
            if (Test-Path -LiteralPath $LinkCandidate -PathType Leaf) {
                $Linker = $LinkCandidate
            }
        }
    }

    if (-not $Compiler -or -not $Linker) {
        return $null
    }

    $SdkRc = $null
    $SdkBin = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits/10/bin'
    if (Test-Path -LiteralPath $SdkBin -PathType Container) {
        $SdkRc = Get-ChildItem -LiteralPath $SdkBin -Directory -ErrorAction SilentlyContinue |
            Sort-Object -Property Name -Descending |
            ForEach-Object { Join-Path $_.FullName 'x64/rc.exe' } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
            Select-Object -First 1
    }

    $ClHash = (Get-FileHash -LiteralPath $Compiler -Algorithm SHA256).Hash.ToLowerInvariant()
    $LinkHash = (Get-FileHash -LiteralPath $Linker -Algorithm SHA256).Hash.ToLowerInvariant()
    $RcIdentity = if ($SdkRc) {
        $RcHash = (Get-FileHash -LiteralPath $SdkRc -Algorithm SHA256).Hash.ToLowerInvariant()
        "rc=$($SdkRc.ToLowerInvariant())|rcSha256=$RcHash"
    }
    else {
        'rc=unresolved'
    }

    return @(
        "cl=$($Compiler.ToLowerInvariant())",
        "clSha256=$ClHash",
        "link=$($Linker.ToLowerInvariant())",
        "linkSha256=$LinkHash",
        $RcIdentity
    ) -join '|'
}

$ToolchainIdentity = Resolve-YacsToolchainIdentity
$EnvironmentIdentity = if ($Engine -and $ToolchainIdentity) {
    $EnvironmentSeed = "$EngineIdentity`n$ToolchainIdentity"
    $Bytes = [System.Text.Encoding]::UTF8.GetBytes($EnvironmentSeed)
    $Hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        ([System.BitConverter]::ToString($Hasher.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $Hasher.Dispose()
    }
}
else {
    'unresolved'
}

if ($Action -eq 'Record') {
    if (-not $CompletedMode) { throw '-CompletedMode is required for Record.' }
    if ($CompletedMode -eq 'runtime' -and $CompletedCompileKind -ne 'none') {
        throw 'Runtime-only proof must record CompletedCompileKind=none.'
    }
    if ($CompletedMode -eq 'compile' -and $CompletedCompileKind -eq 'none') {
        throw 'Compile proof must record CompletedCompileKind=warm or cold.'
    }
    $SummaryPath = Join-Path $EvidenceDir 'unreal_ci_summary.json'
    if (-not (Test-Path -LiteralPath $SummaryPath -PathType Leaf)) {
        throw "Cannot record Unreal cache state without successful proof summary: $SummaryPath"
    }
    $Summary = Get-Content -LiteralPath $SummaryPath -Raw | ConvertFrom-Json
    if ([int]$Summary.Failed -ne 0 -or [int]$Summary.Errors -ne 0 -or [int]$Summary.Discovered -le 0) {
        throw 'Refusing to record non-green Unreal proof state.'
    }
    if (-not $Engine -or $EnvironmentIdentity -eq 'unresolved') {
        throw 'Cannot record cache state because UE/toolchain identity is unresolved.'
    }

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
        SchemaVersion = 3
        CompileFingerprint = $ExpectedCompileFingerprint
        ProofFingerprint = $ExpectedProofFingerprint
        EngineIdentity = $EngineIdentity
        EngineRoot = $EngineRoot
        ToolchainIdentity = $ToolchainIdentity
        EnvironmentIdentity = $EnvironmentIdentity
        CompilePassed = $true
        ProofPassed = $true
        CompileHead = $CompileHead
        ProofHead = $ExpectedHead
        LastCompileKind = $CompletedCompileKind
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
$CompileKind = 'cold'
$Reason = 'missing-cache-state'
$Purge = $true
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
            'EngineRoot',
            'ToolchainIdentity',
            'EnvironmentIdentity',
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
        if (-not $Engine -or $EnvironmentIdentity -eq 'unresolved') {
            $Mode = 'compile'
            $CompileKind = 'cold'
            $Reason = 'environment-identity-unresolved'
            $Purge = $true
        }
        elseif ([int]$State.SchemaVersion -ne 3) {
            $Mode = 'compile'
            $CompileKind = 'cold'
            $Reason = 'cache-schema-mismatch'
            $Purge = $true
        }
        elseif ([string]$State.EnvironmentIdentity -ne $EnvironmentIdentity) {
            $Mode = 'compile'
            $CompileKind = 'cold'
            $Reason = 'environment-identity-mismatch'
            $Purge = $true
        }
        elseif (-not [bool]$State.CompilePassed) {
            $Mode = 'compile'
            $CompileKind = 'warm'
            $Reason = 'previous-compile-not-verified'
            $Purge = $false
        }
        elseif ([string]$State.CompileFingerprint -ne $ExpectedCompileFingerprint) {
            $Mode = 'compile'
            $CompileKind = 'warm'
            $Reason = 'compile-fingerprint-mismatch'
            $Purge = $false
        }
        elseif (@($ExpectedBinaries | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) }).Count -gt 0) {
            $Mode = 'compile'
            $CompileKind = 'warm'
            $Reason = 'expected-binary-missing'
            $Purge = $false
        }
        elseif (-not [bool]$State.ProofPassed) {
            $Mode = 'runtime'
            $CompileKind = 'none'
            $Reason = 'previous-proof-not-verified'
            $Purge = $false
        }
        elseif ([string]$State.ProofFingerprint -ne $ExpectedProofFingerprint) {
            $Mode = 'runtime'
            $CompileKind = 'none'
            $Reason = 'proof-fingerprint-mismatch'
            $Purge = $false
        }
        else {
            $Mode = 'static'
            $CompileKind = 'none'
            $Reason = 'verified-equivalent-proof'
            $Purge = $false
        }
    }
    catch {
        $Mode = 'compile'
        $CompileKind = 'cold'
        $Reason = 'invalid-cache-state-shape'
        $Purge = $true
        $PreviousProofHead = $null
        Write-Warning ("Ignoring invalid Unreal cache state: {0}" -f $_.Exception.Message)
    }
}

$PreviousStateInvalidated = $false
if ($Mode -eq 'compile' -and $State) {
    if ($State.PSObject.Properties.Name -contains 'CompilePassed') {
        $State.CompilePassed = $false
    }
    if ($State.PSObject.Properties.Name -contains 'ProofPassed') {
        $State.ProofPassed = $false
    }
    $InvalidateTmp = "$StatePath.invalidate.tmp"
    $State | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $InvalidateTmp -Encoding UTF8
    Move-Item -LiteralPath $InvalidateTmp -Destination $StatePath -Force
    $PreviousStateInvalidated = $true
}
elseif ($Mode -eq 'runtime' -and $State) {
    $State.ProofPassed = $false
    $InvalidateTmp = "$StatePath.invalidate.tmp"
    $State | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $InvalidateTmp -Encoding UTF8
    Move-Item -LiteralPath $InvalidateTmp -Destination $StatePath -Force
    $PreviousStateInvalidated = $true
}

$Evidence = [ordered]@{
    SchemaVersion = 3
    Head = $ExpectedHead
    Mode = $Mode
    CompileKind = $CompileKind
    Reason = $Reason
    PurgeBuildCache = $Purge
    PreviousStateInvalidated = $PreviousStateInvalidated
    CompileFingerprint = $ExpectedCompileFingerprint
    ProofFingerprint = $ExpectedProofFingerprint
    EngineIdentity = $EngineIdentity
    EngineRoot = $EngineRoot
    ToolchainIdentity = $ToolchainIdentity
    EnvironmentIdentity = $EnvironmentIdentity
    PreviousProofHead = $PreviousProofHead
    ExpectedBinaries = $ExpectedBinaries
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
}
$Evidence | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $EvidencePath -Encoding UTF8

$Out = if ($GithubOutput) { $GithubOutput } elseif ($env:GITHUB_OUTPUT) { $env:GITHUB_OUTPUT } else { $null }
if ($Out) {
    "mode=$Mode" | Out-File -LiteralPath $Out -Append -Encoding utf8
    "compile_kind=$CompileKind" | Out-File -LiteralPath $Out -Append -Encoding utf8
    "reason=$Reason" | Out-File -LiteralPath $Out -Append -Encoding utf8
    "purge_build_cache=$($Purge.ToString().ToLowerInvariant())" | Out-File -LiteralPath $Out -Append -Encoding utf8
    "previous_state_invalidated=$($PreviousStateInvalidated.ToString().ToLowerInvariant())" | Out-File -LiteralPath $Out -Append -Encoding utf8
    "engine_identity=$EngineIdentity" | Out-File -LiteralPath $Out -Append -Encoding utf8
    "environment_identity=$EnvironmentIdentity" | Out-File -LiteralPath $Out -Append -Encoding utf8
}

Write-Host "UNREAL CACHE: mode=$Mode compileKind=$CompileKind reason=$Reason purge=$Purge invalidated=$PreviousStateInvalidated"
exit 0
