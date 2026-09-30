<#
.SYNOPSIS
    Stage 3G reference-environment BEFORE/AFTER visual capture.

.DESCRIPTION
    Thin wrapper around the proven Stage 3F capture harness. It keeps the exact
    same rider-camera distances (1200 m, 4900 m, 8000 m) and 1920x1080 capture
    path so Stage 3G comparisons stay attributable and directly comparable.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [ValidateSet('BEFORE','AFTER')] [string] $Suffix = 'AFTER',
    [switch] $SkipBuild,
    [int] $TimeoutSec = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/Issue80/Stage3G'
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null

$Capture = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Invoke-YacsStage3FVisualCapture.ps1'
$Args = @{
    RepoRoot = $RepoRoot
    ArtifactRoot = $ArtifactRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
    Stage = '3F-B'
    Suffix = $Suffix
    TimeoutSec = $TimeoutSec
    SkipIntrospect = $true
}
if ($ProjectPath) { $Args['ProjectPath'] = $ProjectPath }
if ($SkipBuild) { $Args['SkipBuild'] = $true }

& $Capture @Args
if ($LASTEXITCODE -ne 0) {
    throw "Stage 3G visual capture failed with exit code $LASTEXITCODE"
}

$Manifest = [ordered]@{
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
    Branch = $ExpectedBranch
    Head = $ExpectedHead
    Suffix = $Suffix
    DistancesM = @(1200, 4900, 8000)
    Resolution = '1920x1080'
}
$ManifestPath = Join-Path -Path $ArtifactRoot -ChildPath ('stage3g_' + $Suffix.ToLower() + '_manifest.json')
$Manifest | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8
Write-Host ("Stage 3G {0} capture complete: {1}" -f $Suffix, $ManifestPath) -ForegroundColor Green
exit 0
