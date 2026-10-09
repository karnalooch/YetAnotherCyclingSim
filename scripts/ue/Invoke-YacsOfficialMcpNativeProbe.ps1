#requires -Version 7.4
<#
.SYNOPSIS
    Compile the opt-in #384 BOB plugin in an isolated BuildPlugin project.

.DESCRIPTION
    Requires a clean exact-SHA checkout, the canonical UE 5.8.2 / CL 56702186
    resolver and an idle shared host. Never builds or edits the live project,
    launches an Editor, enables MCP, kills processes or hydrates scene content.
    Compilation alone does not prove registry dispatch or official transport.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string] $ExpectedHead
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$PluginRelative = 'Plugins/YacsBobInspection/YacsBobInspection.uplugin'
$PluginPath = Join-Path $RepoRoot $PluginRelative
$ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject'
if (-not $IsWindows) { throw 'The native BOB compilation probe requires Windows.' }

$runIdentity = if ($env:GITHUB_RUN_ID -and $env:GITHUB_RUN_ATTEMPT) {
    "$env:GITHUB_RUN_ID-$env:GITHUB_RUN_ATTEMPT"
} else { [Guid]::NewGuid().ToString('N') }
$ArtifactRoot = Join-Path $RepoRoot "Saved/RuntimeProof/OfficialMcpNativeProbe/$runIdentity"
$cursor = $ArtifactRoot
while ($cursor) {
    if (Test-Path -LiteralPath $cursor) {
        if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'Native evidence cannot use a symlink/junction destination.'
        }
    }
    if ($cursor -eq $RepoRoot) { break }
    $cursor = Split-Path -Path $cursor -Parent
}
if (Test-Path -LiteralPath $ArtifactRoot) { throw 'Native proof destination already exists.' }
Push-Location -LiteralPath $RepoRoot
try {
    & git check-ignore --no-index --quiet -- (Join-Path $ArtifactRoot 'native-plugin-build.json')
    if ($LASTEXITCODE -ne 0) { throw 'Native proof destination is not Git-ignored.' }
}
finally { Pop-Location }
New-Item -ItemType Directory -Path $ArtifactRoot | Out-Null
$package = Join-Path $ArtifactRoot 'PluginPackage'
$receipt = [ordered]@{
    schema_version = 1
    exact_sha = $ExpectedHead
    status = 'PREFLIGHT_PENDING'
    engine_identity = $null
    engine_version = $null
    source_sha256 = [ordered]@{}
    staged_tracked_plugin_only = $false
    host_checked_at_utc = $null
    host_status = $null
    source_unchanged = $false
    compile_pass = $false
    native_registry_dispatch_verified = $false
    official_mcp_transport_verified = $false
    native_bob_capture_verified = $false
    existing_project_test_verified = $false
    official_mcp_admitted = $false
    persistent_world_mutation = $false
    performance_pass = $false
    performance_status = 'DEFERRED_AFTER_M3'
    error = $null
}
try {
Push-Location -LiteralPath $RepoRoot
try {
    $ActualHead = (& git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $ActualHead -cne $ExpectedHead) {
        throw 'Native probe HEAD does not match its exact requested revision.'
    }
    $trackedChanges = @(& git status --porcelain --untracked-files=no)
    if ($LASTEXITCODE -ne 0 -or $trackedChanges.Count) {
        throw 'Native probe requires unchanged tracked source.'
    }
    $SourcePaths = @(& git ls-files -- 'Plugins/YacsBobInspection' `
        'scripts/ue/Invoke-YacsOfficialMcpNativeProbe.ps1' `
        'scripts/ci/Resolve-YacsUnrealEngine.ps1' `
        'scripts/runner/Get-YacsUnrealHostState.ps1' 'YetAnotherCyclingSim.uproject')
    if ($LASTEXITCODE -ne 0 -or $PluginRelative -cnotin $SourcePaths) {
        throw 'Native plugin and proof sources must be tracked at the exact HEAD.'
    }
}
finally { Pop-Location }

function Get-ProbeSourceHashes {
    $hashes = [ordered]@{}
    foreach ($relative in $SourcePaths) {
        $path = Join-Path $RepoRoot $relative
        $cursor = $path
        while ($cursor) {
            $entry = Get-Item -LiteralPath $cursor -Force
            if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Native probe source cannot use symlink/junction paths.'
            }
            if ($cursor -eq $RepoRoot) { break }
            $cursor = Split-Path -Path $cursor -Parent
        }
        $hashes[$relative] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return $hashes
}

$SourceHashes = Get-ProbeSourceHashes
$receipt.source_sha256 = $SourceHashes
. (Join-Path $RepoRoot 'scripts/ci/Resolve-YacsUnrealEngine.ps1')
$engine = Resolve-YacsUnrealEngine -ProjectPath $ProjectPath
if ($engine) {
    $receipt.engine_identity = $engine.Identity
    $receipt.engine_version = $engine.Version
}
if (-not $engine -or $engine.Version -cne '5.8.2-56702186') {
    throw 'Native BOB probe requires the admitted UE 5.8.2 / CL 56702186 engine.'
}
$descriptor = Get-Content -LiteralPath $PluginPath -Raw | ConvertFrom-Json
if ($descriptor.EnabledByDefault -ne $false -or $descriptor.CanContainContent -ne $false `
    -or @($descriptor.Modules).Count -ne 1 -or $descriptor.Modules[0].Type -cne 'Editor') {
    throw 'Native BOB plugin must remain disabled by default, Editor-only and content-free.'
}

# The existing host classifier is read-only. Do not retain or print command lines.
$hostState = & (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
$receipt.host_checked_at_utc = $hostState.checked_at_utc
$receipt.host_status = $hostState.status
if ($hostState.status -cne 'IDLE') {
    throw "Native probe yields to the current Unreal host owner: $($hostState.status)."
}
$drive = [IO.Path]::GetPathRoot($RepoRoot).TrimEnd('\').TrimEnd(':')
if ((Get-PSDrive -Name $drive).Free -lt 5GB) {
    throw 'Native probe requires the existing 5 GiB disk floor; preserve retained content.'
}

# BuildPlugin sees a fresh plugin staged only from the exact tracked inventory.
# Retained ignored output or untracked source from previous runs cannot enter it.
$StagedPluginRoot = Join-Path $ArtifactRoot 'InputPlugin/YacsBobInspection'
$pluginPrefix = 'Plugins/YacsBobInspection/'
foreach ($relative in $SourcePaths) {
    if (-not $relative.StartsWith($pluginPrefix, [StringComparison]::Ordinal)) { continue }
    $target = Join-Path $StagedPluginRoot $relative.Substring($pluginPrefix.Length)
    New-Item -ItemType Directory -Path (Split-Path -Path $target -Parent) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $RepoRoot $relative) -Destination $target
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -cne $SourceHashes[$relative]) {
        throw 'Staged native source differs from its exact tracked input.'
    }
}
$receipt.staged_tracked_plugin_only = $true
$receipt.status = 'BUILD_PENDING'
$StagedPluginPath = Join-Path $StagedPluginRoot 'YacsBobInspection.uplugin'
    & $engine.UATPath BuildPlugin "-Plugin=$StagedPluginPath" "-Package=$package" `
        -TargetPlatforms=Win64 -StrictIncludes -NoDeleteHostProject 2>&1 |
        Tee-Object -FilePath (Join-Path $ArtifactRoot 'native-plugin-build.log')
    if ($LASTEXITCODE -ne 0) { throw 'Isolated YacsBobInspection BuildPlugin failed.' }
    if (-not (Test-Path -LiteralPath (Join-Path $package 'HostProject/HostProject.uproject') -PathType Leaf)) {
        throw 'BuildPlugin did not retain its isolated HostProject.'
    }
    $afterHashes = Get-ProbeSourceHashes
    foreach ($relative in $SourcePaths) {
        if ($SourceHashes[$relative] -cne $afterHashes[$relative]) {
            throw 'Native source changed during compilation.'
        }
        if ($relative.StartsWith($pluginPrefix, [StringComparison]::Ordinal)) {
            $target = Join-Path $StagedPluginRoot $relative.Substring($pluginPrefix.Length)
            if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -cne $SourceHashes[$relative]) {
                throw 'Staged native source changed during compilation.'
            }
        }
    }
    $receipt.source_unchanged = $true
    $receipt.compile_pass = $true
    $receipt.status = 'NATIVE_PLUGIN_COMPILED'
}
catch {
    $receipt.status = 'BLOCKED'
    $receipt.error = $_.Exception.Message
    throw
}
finally {
    $json = $receipt | ConvertTo-Json -Depth 8
    [IO.File]::WriteAllText((Join-Path $ArtifactRoot 'native-plugin-build.json'), $json, [Text.UTF8Encoding]::new($false))
    Write-Host $json
}
