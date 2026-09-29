#<
.SYNOPSIS
    Validate an in-job prepared R4.1 Unreal workspace before a child proof reuses it.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)] [string] $StampPath,
    [Parameter(Mandatory=$true)] [string] $RepoRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [switch] $RequireMap,
    [switch] $RequireBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$StampPath = (Resolve-Path -LiteralPath $StampPath).Path
$Stamp = Get-Content -LiteralPath $StampPath -Raw -ErrorAction Stop | ConvertFrom-Json

if ([int]$Stamp.schema_version -ne 1) {
    throw "Unsupported prepared-workspace schema version: $($Stamp.schema_version)"
}

$ActualHead = (git -C $RepoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve current HEAD while validating prepared R4.1 workspace.' }
if ($ActualHead -ne $ExpectedHead) {
    throw "Prepared R4.1 workspace HEAD mismatch: actual '$ActualHead', expected '$ExpectedHead'."
}
if ([string]$Stamp.expected_head -ne $ExpectedHead) {
    throw "Prepared R4.1 stamp HEAD mismatch: stamp '$($Stamp.expected_head)', expected '$ExpectedHead'."
}

$StampedRepoRoot = [System.IO.Path]::GetFullPath([string]$Stamp.repo_root)
$ActualRepoRoot = [System.IO.Path]::GetFullPath($RepoRoot)
if (-not [string]::Equals($StampedRepoRoot, $ActualRepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Prepared R4.1 stamp belongs to a different worktree: '$StampedRepoRoot'."
}

if ($RequireBuild) {
    if ([string]$Stamp.editor_build -ne 'PASS') {
        throw 'Prepared R4.1 workspace does not contain a verified editor build.'
    }
    if ([string]$Stamp.build_target -ne 'YetAnotherCyclingSimEditor' -or
        [string]$Stamp.build_platform -ne 'Win64' -or
        [string]$Stamp.build_configuration -ne 'Development') {
        throw 'Prepared R4.1 workspace build identity is incompatible with the proof suite.'
    }
}

if ($RequireMap) {
    $ExpectedMapRelative = 'Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap'
    if ([string]$Stamp.map_relative -ne $ExpectedMapRelative) {
        throw "Prepared R4.1 workspace map identity is invalid: '$($Stamp.map_relative)'."
    }
    $MapPath = Join-Path $RepoRoot $ExpectedMapRelative
    if (-not (Test-Path -LiteralPath $MapPath -PathType Leaf)) {
        throw "Prepared R4.1 workspace map is missing: $MapPath"
    }
    $MapBytes = [int64](Get-Item -LiteralPath $MapPath).Length
    if ($MapBytes -lt 100000000) {
        throw "Prepared R4.1 workspace map is not materialized (bytes=$MapBytes)."
    }
    if ($MapBytes -ne [int64]$Stamp.map_bytes) {
        throw "Prepared R4.1 workspace map byte count changed: current=$MapBytes stamp=$($Stamp.map_bytes)."
    }
}

return $Stamp
