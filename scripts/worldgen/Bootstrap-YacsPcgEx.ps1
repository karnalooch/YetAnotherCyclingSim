<#
.SYNOPSIS
    Install or validate the exact PCGEx source revision used by the YACS Passo Giau authoring pipeline.

.DESCRIPTION
    PCGEx is an authoring-time dependency. The script fetches one reviewed MIT-licensed
    revision into Plugins/PCGExtendedToolkit and fails closed on revision/version drift.
    It does not modify YACS project files and does not make PCGEx a shipping runtime dependency.
#>
[CmdletBinding()]
param(
    [ValidateSet('Validate','Install')] [string] $Mode = 'Validate',
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path,
    [string] $PluginRoot,
    [string] $ReportPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExpectedRepository = 'https://github.com/PCGEx/PCGExtendedToolkit.git'
$ExpectedCommit = '39a8f1bdc65b2c4613a1e87b71d93b4576db0a66'
$ExpectedVersion = '0.79'
$ExpectedEngineVersion = '5.8.0'
$ExpectedLicenseFirstLine = 'MIT License'
$CompatibilityPatchId = 'yacs-pcgex-0.79-triangulate-hole-winding-v1'
$CompatibilityPatchRelative = 'scripts/worldgen/patches/pcgex-0.79-triangulate-holes-winding.patch'
$CompatibilityTargetRelative = 'Source/PCGExElementsClipper2/Private/Clipper2Lib/clipper.triangulation.cpp'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $PluginRoot) { $PluginRoot = Join-Path $RepoRoot 'Plugins/PCGExtendedToolkit' }
$PluginRoot = [System.IO.Path]::GetFullPath($PluginRoot)

if (-not $ReportPath) {
    $ReportPath = Join-Path $RepoRoot 'Saved/RuntimeProof/CI/M3/EmbarkTerrain/pcgex-bootstrap.json'
}
$ReportPath = [System.IO.Path]::GetFullPath($ReportPath)
New-Item -ItemType Directory -Path (Split-Path -Parent $ReportPath) -Force | Out-Null

if ($Mode -eq 'Install' -and -not (Test-Path -LiteralPath (Join-Path $PluginRoot '.git'))) {
    if (Test-Path -LiteralPath $PluginRoot) {
        $Existing = @(Get-ChildItem -LiteralPath $PluginRoot -Force)
        if ($Existing.Count -gt 0) {
            throw "PCGEx destination already exists and is not an exact Git checkout: $PluginRoot"
        }
    } else {
        New-Item -ItemType Directory -Path $PluginRoot -Force | Out-Null
    }

    & git -C $PluginRoot init
    if ($LASTEXITCODE -ne 0) { throw 'Failed to initialize PCGEx checkout.' }
    & git -C $PluginRoot config core.autocrlf false
    & git -C $PluginRoot remote add origin $ExpectedRepository
    if ($LASTEXITCODE -ne 0) { throw 'Failed to configure PCGEx origin.' }
    & git -C $PluginRoot fetch --depth 1 origin $ExpectedCommit
    if ($LASTEXITCODE -ne 0) { throw "Failed to fetch pinned PCGEx commit $ExpectedCommit." }
    & git -C $PluginRoot checkout --detach FETCH_HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Failed to checkout pinned PCGEx revision.' }
}

$CompatibilityPatchPath = Join-Path $RepoRoot $CompatibilityPatchRelative
if (-not (Test-Path -LiteralPath $CompatibilityPatchPath -PathType Leaf)) {
    throw "PCGEx compatibility patch is missing: $CompatibilityPatchPath"
}

$PatchApplied = $false
if (Test-Path -LiteralPath (Join-Path $PluginRoot '.git')) {
    & git -C $PluginRoot apply --reverse --check $CompatibilityPatchPath *> $null
    $PatchApplied = ($LASTEXITCODE -eq 0)

    if (-not $PatchApplied -and $Mode -eq 'Install') {
        & git -C $PluginRoot apply --check $CompatibilityPatchPath
        if ($LASTEXITCODE -ne 0) {
            throw 'Pinned PCGEx source does not accept the reviewed YACS compatibility patch.'
        }
        & git -C $PluginRoot apply --whitespace=nowarn $CompatibilityPatchPath
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to apply the reviewed YACS PCGEx compatibility patch.'
        }
        & git -C $PluginRoot apply --reverse --check $CompatibilityPatchPath *> $null
        $PatchApplied = ($LASTEXITCODE -eq 0)
    }
}

$Checks = [System.Collections.Generic.List[object]]::new()
function Add-Check([string] $Name, [bool] $Ok, [string] $Detail) {
    $Checks.Add([ordered]@{ name=$Name; status=$(if ($Ok) {'PASS'} else {'FAIL'}); detail=$Detail })
}

$GitDir = Join-Path $PluginRoot '.git'
Add-Check 'git_checkout' (Test-Path -LiteralPath $GitDir) $PluginRoot

$Head = $null
$Origin = $null
if (Test-Path -LiteralPath $GitDir) {
    $Head = (& git -C $PluginRoot rev-parse HEAD).Trim()
    $Origin = (& git -C $PluginRoot remote get-url origin).Trim()
}
Add-Check 'exact_commit' ($Head -eq $ExpectedCommit) ([string]$Head)
Add-Check 'origin' ($Origin -eq $ExpectedRepository) ([string]$Origin)

$DescriptorPath = Join-Path $PluginRoot 'PCGExtendedToolkit.uplugin'
$LicensePath = Join-Path $PluginRoot 'LICENSE'
Add-Check 'descriptor' (Test-Path -LiteralPath $DescriptorPath -PathType Leaf) $DescriptorPath
Add-Check 'license' (Test-Path -LiteralPath $LicensePath -PathType Leaf) $LicensePath

if (Test-Path -LiteralPath $DescriptorPath -PathType Leaf) {
    $Descriptor = Get-Content -LiteralPath $DescriptorPath -Raw | ConvertFrom-Json
    Add-Check 'version' ([string]$Descriptor.VersionName -eq $ExpectedVersion) ([string]$Descriptor.VersionName)
    Add-Check 'engine_version' ([string]$Descriptor.EngineVersion -eq $ExpectedEngineVersion) ([string]$Descriptor.EngineVersion)
}

if (Test-Path -LiteralPath $LicensePath -PathType Leaf) {
    $LicenseFirstLine = Get-Content -LiteralPath $LicensePath -TotalCount 1
    Add-Check 'license_type' ($LicenseFirstLine -eq $ExpectedLicenseFirstLine) $LicenseFirstLine
}

$Dirty = $null
$ChangedPaths = @()
$UntrackedPaths = @()
if (Test-Path -LiteralPath $GitDir) {
    $Dirty = (& git -C $PluginRoot status --porcelain --untracked-files=all) -join [Environment]::NewLine
    $ChangedPaths = @(& git -C $PluginRoot diff --name-only)
    $UntrackedPaths = @(& git -C $PluginRoot ls-files --others --exclude-standard)
}
$ExpectedPatchOnly = (
    $PatchApplied -and
    $ChangedPaths.Count -eq 1 -and
    $ChangedPaths[0] -eq $CompatibilityTargetRelative -and
    $UntrackedPaths.Count -eq 0
)
Add-Check 'compatibility_patch' $PatchApplied $CompatibilityPatchId
Add-Check 'expected_patch_only' $ExpectedPatchOnly ([string]$Dirty)

$Failed = @($Checks | Where-Object { $_.status -ne 'PASS' })
$Report = [ordered]@{
    schema_version = 1
    dependency = 'PCGEx'
    role = 'authoring-only'
    shipping_runtime_dependency = $false
    repository = $ExpectedRepository
    expected_commit = $ExpectedCommit
    actual_commit = $Head
    compatibility_patch = $CompatibilityPatchId
    compatibility_patch_sha256 = (Get-FileHash -LiteralPath $CompatibilityPatchPath -Algorithm SHA256).Hash.ToLowerInvariant()
    compatibility_target = $CompatibilityTargetRelative
    plugin_root = $PluginRoot
    status = $(if ($Failed.Count -eq 0) {'PASS'} else {'FAIL'})
    checks = $Checks
}
$Report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding UTF8

if ($Failed.Count -gt 0) {
    $Names = ($Failed | ForEach-Object { $_.name }) -join ', '
    throw "PCGEx bootstrap validation failed: $Names"
}

Write-Host "PCGEx bootstrap validation: PASS ($ExpectedCommit)" -ForegroundColor Green
