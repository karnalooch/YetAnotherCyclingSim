#requires -Version 5.1
<#
.SYNOPSIS
    Installs the exact portable PowerShell toolchain pinned by YACS.

.DESCRIPTION
    Downloads the official PowerShell win-x64 ZIP, verifies the pinned SHA-256,
    validates the staged pwsh.exe version, then publishes it below the persistent
    YACS workspace tools directory. No MSI, system PATH or C: installation is used.
#>
[CmdletBinding()]
param(
    [string] $WorkspaceConfig = $(if ($env:YACS_WORKSPACE_CONFIG) { $env:YACS_WORKSPACE_CONFIG } else { 'D:\yacs\workspace.json' }),
    [string] $ManifestPath = (Join-Path $PSScriptRoot 'powershell-toolchain.json'),
    [switch] $Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Write-Result {
    param([hashtable] $Payload)
    if ($Json) {
        $Payload | ConvertTo-Json -Depth 6
    }
    else {
        $Payload.GetEnumerator() | Sort-Object Name | Format-Table Name, Value -AutoSize
    }
}

function Test-PinnedPowerShell {
    param(
        [Parameter(Mandatory = $true)][string] $Executable,
        [Parameter(Mandatory = $true)][string] $ExpectedVersion
    )
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        return $false
    }
    $actual = (& $Executable -NoLogo -NoProfile -NonInteractive -Command '$PSVersionTable.PSVersion.ToString()' 2>&1 | Out-String).Trim()
    return ($LASTEXITCODE -eq 0 -and $actual -eq $ExpectedVersion)
}

$WorkspaceConfig = (Resolve-Path -LiteralPath $WorkspaceConfig).Path
$ManifestPath = (Resolve-Path -LiteralPath $ManifestPath).Path
$config = Get-Content -LiteralPath $WorkspaceConfig -Raw | ConvertFrom-Json
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json

if ([int]$config.schema_version -ne 1) { throw 'Unsupported YACS workspace schema.' }
if ([int]$manifest.schema_version -ne 1) { throw 'Unsupported PowerShell toolchain schema.' }

$root = Split-Path -Parent $WorkspaceConfig
$relativeTarget = [string]$manifest.workspace_directory
if ([IO.Path]::IsPathRooted($relativeTarget) -or $relativeTarget -match '(^|[\/])\.\.([\/]|$)') {
    throw 'PowerShell toolchain target must remain workspace-relative.'
}
$target = [IO.Path]::GetFullPath((Join-Path $root $relativeTarget))
$rootPrefix = $root.TrimEnd('\') + '\'
if (-not $target.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'PowerShell toolchain target escapes the workspace root.'
}
$executable = Join-Path $target ([string]$manifest.executable)
$expectedVersion = [string]$manifest.version

if (Test-PinnedPowerShell -Executable $executable -ExpectedVersion $expectedVersion) {
    $payload = [ordered]@{
        schema_version = 1
        status = 'PASS'
        action = 'reuse'
        version = $expectedVersion
        executable = $executable
        archive_sha256 = ([string]$manifest.sha256).ToLowerInvariant()
    }
    Write-Result -Payload $payload
    return
}

$cacheRoot = Join-Path $root 'cache\tools\powershell'
$workRoot = Join-Path $root 'work\toolchain-staging'
$receiptRoot = Join-Path $root 'work\toolchain-receipts'
$archiveRoot = Join-Path $root 'archive\toolchains'
foreach ($path in @($cacheRoot, $workRoot, $receiptRoot, $archiveRoot)) {
    [void][IO.Directory]::CreateDirectory($path)
}

$download = Join-Path $cacheRoot ([string]$manifest.archive_name)
$expectedHash = ([string]$manifest.sha256).ToLowerInvariant()
$downloadOk = $false
if (Test-Path -LiteralPath $download -PathType Leaf) {
    $downloadHash = (Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash.ToLowerInvariant()
    $downloadOk = ($downloadHash -eq $expectedHash)
    if (-not $downloadOk) {
        $quarantine = "$download.bad-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Move-Item -LiteralPath $download -Destination $quarantine
    }
}

if (-not $downloadOk) {
    $partial = "$download.part"
    if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
    Invoke-WebRequest -Uri ([string]$manifest.download_url) -OutFile $partial -UseBasicParsing
    $actualHash = (Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) {
        throw "PowerShell archive SHA-256 mismatch: expected $expectedHash, got $actualHash"
    }
    Move-Item -LiteralPath $partial -Destination $download -Force
}

$stage = Join-Path $workRoot ("powershell-{0}-{1}" -f $expectedVersion, [guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($stage)
try {
    Expand-Archive -LiteralPath $download -DestinationPath $stage -Force
    $stageExe = Join-Path $stage ([string]$manifest.executable)
    if (-not (Test-PinnedPowerShell -Executable $stageExe -ExpectedVersion $expectedVersion)) {
        throw "Staged PowerShell did not report exact version $expectedVersion."
    }

    if (Test-Path -LiteralPath $target) {
        $retained = Join-Path $archiveRoot ("powershell-unexpected-{0}" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
        Move-Item -LiteralPath $target -Destination $retained
    }

    Move-Item -LiteralPath $stage -Destination $target
}
finally {
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}

if (-not (Test-PinnedPowerShell -Executable $executable -ExpectedVersion $expectedVersion)) {
    throw 'Published portable PowerShell failed exact-version verification.'
}

$receipt = [ordered]@{
    schema_version = 1
    status = 'PASS'
    action = 'install'
    installed_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    version = $expectedVersion
    executable = $executable
    archive = $download
    archive_sha256 = $expectedHash
    source_url = [string]$manifest.download_url
}
$receiptPath = Join-Path $receiptRoot ("powershell-{0}.json" -f $expectedVersion)
$receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
Write-Result -Payload $receipt
