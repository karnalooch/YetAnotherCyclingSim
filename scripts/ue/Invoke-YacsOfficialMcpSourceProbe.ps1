#requires -Version 7.4
<#
.SYNOPSIS
    Collect installed official MCP declarations for Issues #384/#364, without activation.

.DESCRIPTION
    Uses the canonical engine resolver and a bounded filesystem-only collector.
    Never builds, launches or stops Unreal, starts MCP, enables plugins, executes
    tools, or modifies the authoring project. Evidence is exclusive-write under
    this checkout's ignored Saved directory; it is not an admission receipt.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string] $ExpectedHead,
    [ValidateSet('stock_control_flow', 'domain_extension', 'material_declarations')]
    [string] $EvidenceFocus = 'stock_control_flow',
    [string] $ArtifactRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject'
if (-not $ArtifactRoot) {
    $runIdentity = if ($env:GITHUB_RUN_ID -and $env:GITHUB_RUN_ATTEMPT) {
        "$env:GITHUB_RUN_ID-$env:GITHUB_RUN_ATTEMPT"
    } else {
        [Guid]::NewGuid().ToString('N')
    }
    $ArtifactRoot = Join-Path $RepoRoot "Saved/RuntimeProof/OfficialMcpSourceProbe/$runIdentity"
}
$ArtifactRoot = [IO.Path]::GetFullPath($ArtifactRoot)
$savedPrefix = [IO.Path]::GetFullPath((Join-Path $RepoRoot 'Saved')).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
if (-not $ArtifactRoot.StartsWith($savedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Official MCP source evidence must be below this checkout Saved directory.'
}
# Reject junction/symlink ancestors before the first evidence write.
$ancestor = $ArtifactRoot
while ($ancestor) {
    if (Test-Path -LiteralPath $ancestor) {
        $entry = Get-Item -LiteralPath $ancestor -Force
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'Official MCP evidence cannot use a junction or symbolic link.'
        }
    }
    if ($ancestor -eq $RepoRoot) { break }
    $ancestor = Split-Path -Path $ancestor -Parent
}
if (Test-Path -LiteralPath (Join-Path $ArtifactRoot 'official-mcp-source-probe.json')) {
    throw 'Source-probe receipt already exists; use a fresh artifact directory.'
}

Push-Location -LiteralPath $RepoRoot
try {
    $ActualHead = (& git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot determine the actual repository SHA.' }
    $trackedChanges = @(& git status --porcelain --untracked-files=no)
    if ($LASTEXITCODE -ne 0 -or $trackedChanges.Count) {
        throw 'Source probe requires an unchanged tracked checkout to bind its exact repository SHA.'
    }
    & git ls-files --error-unmatch -- 'YetAnotherCyclingSim.uproject' `
        'scripts/ue/official_mcp_source_probe.py' 'scripts/ue/Invoke-YacsOfficialMcpSourceProbe.ps1' `
        'scripts/ci/Resolve-YacsUnrealEngine.ps1' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Canonical project/probe/resolver inputs must be tracked at HEAD.' }
    & git check-ignore --no-index --quiet -- (Join-Path $ArtifactRoot 'official-mcp-source-probe.json')
    if ($LASTEXITCODE -ne 0) { throw 'Source-probe evidence destination is not ignored by Git.' }
}
finally { Pop-Location }

. (Join-Path $RepoRoot 'scripts/ci/Resolve-YacsUnrealEngine.ps1')
$engine = $null
$resolverError = $null
try { $engine = Resolve-YacsUnrealEngine -ProjectPath $ProjectPath }
catch { $resolverError = $_.Exception.Message }
if (-not $engine -and -not $resolverError) { $resolverError = 'Canonical UE 5.8 engine was not found.' }

$hostContext = [ordered]@{
    status = 'UNVERIFIED'
    inspected_at_utc = [DateTime]::UtcNow.ToString('o')
    resolver_error = $resolverError
    resolver_identity = if ($engine) { $engine.Identity } else { $null }
    processes = @()
    active_engine_matches_resolver = $null
    active_plugin_state_verified = $false
    repository_tracked_clean = $true
    probe_sha256 = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'official_mcp_source_probe.py') -Algorithm SHA256).Hash.ToLowerInvariant()
    resolver_sha256 = (Get-FileHash -LiteralPath (Join-Path $RepoRoot 'scripts/ci/Resolve-YacsUnrealEngine.ps1') -Algorithm SHA256).Hash.ToLowerInvariant()
}
if ($IsWindows) {
    try {
        $observations = @()
        foreach ($candidate in @(Get-CimInstance Win32_Process | Where-Object {
            $_.Name -in @('UnrealEditor.exe', 'UnrealEditor-Cmd.exe')
        })) {
            $native = Get-Process -Id ([int]$candidate.ProcessId) -ErrorAction SilentlyContinue
            if (-not $native -or $native.HasExited) { continue }
            $executable = [string]$candidate.ExecutablePath
            $matches = $false
            $binaryHash = $null
            if ($engine -and $executable) {
                $binaryRoot = [IO.Path]::GetFullPath((Join-Path $engine.Root 'Engine/Binaries/Win64')).TrimEnd('\') + '\'
                $matches = [IO.Path]::GetFullPath($executable).StartsWith($binaryRoot, [StringComparison]::OrdinalIgnoreCase)
                if ($matches -and (Test-Path -LiteralPath $executable -PathType Leaf)) {
                    $binaryHash = (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash.ToLowerInvariant()
                }
            }
            $observations += [ordered]@{
                process_id = [int]$candidate.ProcessId
                name = [string]$candidate.Name
                executable_path = $executable
                executable_sha256 = $binaryHash
                executable_under_resolved_engine = $matches
                plugin_state_verified = $false
            }
        }
        $hostContext.processes = $observations
        $hostContext.status = if ($observations.Count) { 'PROCESS_PATHS_OBSERVED' } else { 'NO_RUNNING_EDITOR_OBSERVED' }
        if ($observations.Count) {
            $hostContext.active_engine_matches_resolver = @($observations | Where-Object {
                -not $_.executable_under_resolved_engine
            }).Count -eq 0
        }
    }
    catch { $hostContext.observation_error = $_.Exception.Message }
}

New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$hostPath = Join-Path $ArtifactRoot 'running-editor-observation.json'
if (Test-Path -LiteralPath $hostPath) { throw 'Host observation already exists; use a fresh artifact directory.' }
$hostContext | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $hostPath -Encoding UTF8
$engineRoot = if ($engine) { $engine.Root } else { Join-Path $ArtifactRoot 'unavailable-engine' }
$python = Get-Command python -ErrorAction Stop
& $python.Source (Join-Path $PSScriptRoot 'official_mcp_source_probe.py') `
    --engine-root $engineRoot --project $ProjectPath --repository-root $RepoRoot `
    --expected-sha $ExpectedHead --actual-sha $ActualHead --artifact-root $ArtifactRoot `
    --host-context $hostPath --evidence-focus $EvidenceFocus
if ($LASTEXITCODE -ne 0) {
    throw "Official MCP source probe is blocked (collector exit $LASTEXITCODE); retain its receipt."
}
if ($EvidenceFocus -eq 'material_declarations') {
    Write-Host 'Filesystem material declarations collected. Runtime schemas, execution and #364 authoring remain unverified.'
} else {
    Write-Host 'Filesystem source evidence collected. Guard parity and #384 admission remain unverified.'
}
