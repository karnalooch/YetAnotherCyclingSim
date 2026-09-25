<#
.SYNOPSIS
    Restore a cached UE 5.8 seed archive onto a CircleCI hosted Windows VM.
#>
[CmdletBinding()]
param(
    [string] $SeedRoot = (Join-Path -Path (Get-Location).Path -ChildPath 'Saved/RuntimeProof/CI/UE58Seed'),
    [string] $DestinationRoot = 'C:\UE_5.8',
    [double] $SafetyGiB = 8.0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$archivePath = Join-Path $SeedRoot 'ue58-win64.tar.gz'
$manifestPath = Join-Path $SeedRoot 'ue58-win64-manifest.json'
if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
    throw "UE cache archive missing: $archivePath"
}
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "UE cache manifest missing: $manifestPath"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ([string]$manifest.EngineVersion -notmatch '^5\.8\.') {
    throw "Cached engine version is not UE 5.8.x: $($manifest.EngineVersion)"
}
$actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne [string]$manifest.ArchiveSha256) {
    throw "UE cache archive SHA256 mismatch."
}

$drive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$freeGiB = [math]::Round($drive.FreeSpace / 1GB, 3)
$archiveGiB = [math]::Round((Get-Item -LiteralPath $archivePath).Length / 1GB, 3)
$includedGiB = [double]$manifest.EstimatedIncludedGiB
$requiredGiB = [math]::Round($archiveGiB + $includedGiB + $SafetyGiB, 3)
Write-Host ("Disk preflight: free={0} GiB required~={1} GiB (archive={2}, engine={3}, safety={4})" -f $freeGiB, $requiredGiB, $archiveGiB, $includedGiB, $SafetyGiB)
if ($freeGiB -lt $requiredGiB) {
    throw ("Not enough free disk for UE restore: {0} GiB free, {1} GiB required." -f $freeGiB, $requiredGiB)
}

if (Test-Path -LiteralPath $DestinationRoot) {
    throw "Destination already exists: $DestinationRoot"
}
$destinationParent = Split-Path -Parent $DestinationRoot
New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null

$tar = (Get-Command tar.exe -ErrorAction Stop).Source
& $tar -xzf $archivePath -C $destinationParent
if ($LASTEXITCODE -ne 0) { throw "tar.exe extraction failed with exit code $LASTEXITCODE." }

if (-not (Test-Path -LiteralPath (Join-Path $DestinationRoot 'Engine/Build/Build.version'))) {
    throw 'Restored UE tree is missing Engine/Build/Build.version.'
}
if (-not (Test-Path -LiteralPath (Join-Path $DestinationRoot 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'))) {
    throw 'Restored UE tree is missing UnrealEditor-Cmd.exe.'
}

Remove-Item -LiteralPath $archivePath -Force
Write-Host ("UE 5.8 restore: PASS -> {0}" -f $DestinationRoot) -ForegroundColor Green
