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
$CompatibilityPatchId = 'yacs-pcgex-0.79-horizontal-boundary-v2'
$CompatibilityPatchRelative = 'scripts/worldgen/patches/pcgex-0.79-triangulate-holes-flat-union.patch'
$CompatibilityTargetRelative = 'Source/PCGExElementsClipper2/Private/Clipper2Lib/clipper.triangulation.cpp'
$ExpectedCompatibilityPatchSha256 = '8182824990670e560d1a1f0d052288cc8a98dc5cdb370bdbf63f2666f9593d89'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $PluginRoot) { $PluginRoot = Join-Path $RepoRoot 'Plugins/PCGExtendedToolkit' }
$PluginRoot = [System.IO.Path]::GetFullPath($PluginRoot)

if (-not $ReportPath) {
    $ReportPath = Join-Path $RepoRoot 'Saved/RuntimeProof/CI/M3/EmbarkTerrain/pcgex-bootstrap.json'
}
$ReportPath = [System.IO.Path]::GetFullPath($ReportPath)
# Reports must never create an untracked file inside the checkout being validated.
$PluginPrefix = $PluginRoot.TrimEnd([char[]]'\/') + [System.IO.Path]::DirectorySeparatorChar
if ($ReportPath.Equals($PluginRoot, [StringComparison]::OrdinalIgnoreCase) -or
    $ReportPath.StartsWith($PluginPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'PCGEx report path must be outside the plugin checkout.'
}

function Invoke-PluginGit {
    param([Parameter(Mandatory=$true)] [string[]] $GitArguments)
    # Git warnings belong to diagnostics, never to machine-readable path output.
    # diff can refresh stat-only index entries despite --no-optional-locks.
    # This per-process option keeps validation byte-read-only without changing config.
    $start = [Diagnostics.ProcessStartInfo]::new('git')
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($argument in @('--no-optional-locks', '-c', 'diff.autoRefreshIndex=false', '-C', $PluginRoot) + $GitArguments) {
        $start.ArgumentList.Add($argument)
    }
    $process = [Diagnostics.Process]::Start($start)
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $outputText = $stdout.GetAwaiter().GetResult()
    $errorText = $stderr.GetAwaiter().GetResult()
    if ($process.ExitCode -ne 0) {
        throw "PCGEx git $($GitArguments -join ' ') failed (exit=$($process.ExitCode)): $errorText$outputText"
    }
    if ($errorText) { Write-Verbose $errorText.TrimEnd() }
    if ($outputText.Length -gt 0) {
        return $outputText.TrimEnd("`r", "`n") -split "`r?`n"
    }

}

$CompatibilityPatchPath = Join-Path $RepoRoot $CompatibilityPatchRelative
if (-not (Test-Path -LiteralPath $CompatibilityPatchPath -PathType Leaf)) {
    throw "PCGEx compatibility patch is missing: $CompatibilityPatchPath"
}
$PatchText = [System.IO.File]::ReadAllText($CompatibilityPatchPath).Replace("`r`n", "`n")
$ActualCompatibilityPatchSha256 = [Convert]::ToHexString(
    [System.Security.Cryptography.SHA256]::HashData(
        [System.Text.Encoding]::UTF8.GetBytes($PatchText)
    )
).ToLowerInvariant()
if ($ActualCompatibilityPatchSha256 -ne $ExpectedCompatibilityPatchSha256) {
    throw "PCGEx compatibility patch hash drift: $ActualCompatibilityPatchSha256"
}

function Test-YacsPcgExCompatibilityPatchApplied {
    param([Parameter(Mandatory=$true)] [string] $TargetPath)

    if (-not (Test-Path -LiteralPath $TargetPath -PathType Leaf)) {
        return $false
    }

    # Exact full-file verification rejects extra edits in the allowed path.
    # Normalize line endings only; Windows checkouts may contain CRLF.
    $Text = [System.IO.File]::ReadAllText($TargetPath).Replace("`r`n", "`n")
    $Bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $Hash = [Convert]::ToHexString(
        [System.Security.Cryptography.SHA256]::HashData($Bytes)
    ).ToLowerInvariant()
    return $Hash -eq '68614ae15d6bb03f2e58b0fb1dfa33e8eeebbfd31da08bd94ebfb378aeb63977'
}

# Only a fresh, empty destination may be initialized/fetched. Existing checkouts
# are authenticated below before any patch write; never fetch/reset user source.
if ($Mode -eq 'Install' -and -not (Test-Path -LiteralPath (Join-Path $PluginRoot '.git'))) {
    if (Test-Path -LiteralPath $PluginRoot) {
        if (@(Get-ChildItem -LiteralPath $PluginRoot -Force).Count -gt 0) {
            throw "PCGEx destination already exists and is not an exact Git checkout: $PluginRoot"
        }
    } else {
        New-Item -ItemType Directory -Path $PluginRoot -Force | Out-Null
    }
    Invoke-PluginGit @('init') | Out-Null
    Invoke-PluginGit @('config', 'core.autocrlf', 'false') | Out-Null
    Invoke-PluginGit @('remote', 'add', 'origin', $ExpectedRepository) | Out-Null
    Invoke-PluginGit @('fetch', '--depth', '1', 'origin', $ExpectedCommit) | Out-Null
    Invoke-PluginGit @('checkout', '--detach', 'FETCH_HEAD') | Out-Null
}

$CompatibilityTargetPath = Join-Path $PluginRoot $CompatibilityTargetRelative
$PatchApplied = Test-YacsPcgExCompatibilityPatchApplied -TargetPath $CompatibilityTargetPath
$PatchApplicable = $false
if (Test-Path -LiteralPath (Join-Path $PluginRoot '.git')) {
    & git --no-optional-locks -C $PluginRoot apply --check --ignore-space-change --ignore-whitespace $CompatibilityPatchPath *> $null
    $PatchApplicable = ($LASTEXITCODE -eq 0)
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
    $Head = ((Invoke-PluginGit @('rev-parse', 'HEAD')) -join '').Trim()
    $Origin = ((Invoke-PluginGit @('remote', 'get-url', 'origin')) -join '').Trim()
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
$StagedPaths = @()
$HiddenTrackedPaths = @()
if (Test-Path -LiteralPath $GitDir) {
    $Dirty = (Invoke-PluginGit @('status', '--porcelain', '--untracked-files=all')) -join [Environment]::NewLine
    # --name-only may report stat-only differences when auto-refresh is disabled.
    # --numstat computes content differences without rewriting the source index.
    $ChangedPaths = @(Invoke-PluginGit @('diff', 'HEAD', '--numstat', '--no-ext-diff') | ForEach-Object {
        $fields = $_ -split "`t", 3
        if ($fields.Count -ne 3) { throw 'Unexpected Git content-diff record.' }
        $fields[2]
    })
    $StagedPaths = @(Invoke-PluginGit @('diff', '--cached', '--name-only'))
    # These flags suppress ordinary status/diff evidence; never trust that view.
    $HiddenTrackedPaths = @(Invoke-PluginGit @('ls-files', '-v') | Where-Object { $_ -cmatch '^[a-zS] ' })
    $UntrackedPaths = @(Invoke-PluginGit @('ls-files', '--others', '--exclude-standard'))
}
$UpstreamClean = (
    $ChangedPaths.Count -eq 0 -and
    $UntrackedPaths.Count -eq 0 -and
    $StagedPaths.Count -eq 0
)
$ExpectedPatchOnly = (
    $PatchApplied -and
    $ChangedPaths.Count -eq 1 -and
    $ChangedPaths[0] -eq $CompatibilityTargetRelative -and
    $UntrackedPaths.Count -eq 0 -and
    $StagedPaths.Count -eq 0
)
$CompatibilityReady = $PatchApplied -or $PatchApplicable
$CheckoutPolicyOk = ($UpstreamClean -and $PatchApplicable) -or $ExpectedPatchOnly
Add-Check 'visible_tracked_files' ($HiddenTrackedPaths.Count -eq 0) ($HiddenTrackedPaths -join [Environment]::NewLine)
Add-Check 'clean_checkout' $CheckoutPolicyOk ([string]$Dirty)
Add-Check 'compatibility_patch' $CompatibilityReady $CompatibilityPatchId
Add-Check 'expected_patch_only' $CheckoutPolicyOk ([string]$Dirty)

# All source identity, license and dirt checks must pass before a write.
$PreflightFailed = @($Checks | Where-Object { $_.status -ne 'PASS' })
if ($Mode -eq 'Install' -and $PreflightFailed.Count -eq 0 -and -not $PatchApplied) {
    Invoke-PluginGit @('apply', '--whitespace=nowarn', '--ignore-space-change', '--ignore-whitespace', $CompatibilityPatchPath) | Out-Null
    $PatchApplied = Test-YacsPcgExCompatibilityPatchApplied -TargetPath $CompatibilityTargetPath
    $PatchApplicable = $false
    Add-Check 'installed_patch_exact' $PatchApplied $CompatibilityTargetRelative
}

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
    compatibility_patch_state = $(if ($PatchApplied) {'applied'} elseif ($PatchApplicable) {'applicable'} else {'invalid'})
    compatibility_patch_sha256 = $ActualCompatibilityPatchSha256
    compatibility_target = $CompatibilityTargetRelative
    upstream_clean_before_install = $UpstreamClean
    exact_patch_only_before_install = $ExpectedPatchOnly
    changed_paths_before_install = @($ChangedPaths)
    staged_paths_before_install = @($StagedPaths)
    hidden_tracked_paths_before_install = @($HiddenTrackedPaths)
    untracked_paths_before_install = @($UntrackedPaths)
    plugin_root = $PluginRoot
    status = $(if ($Failed.Count -eq 0) {'PASS'} else {'FAIL'})
    checks = $Checks
}
New-Item -ItemType Directory -Path (Split-Path -Parent $ReportPath) -Force | Out-Null
$Report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding UTF8

if ($Failed.Count -gt 0) {
    $Names = ($Failed | ForEach-Object { $_.name }) -join ', '
    throw "PCGEx bootstrap validation failed: $Names"
}

Write-Host "PCGEx bootstrap validation: PASS ($ExpectedCommit)" -ForegroundColor Green

