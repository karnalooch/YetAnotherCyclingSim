<#
.SYNOPSIS
    Restore a validated cached UE 5.8 seed ZIP onto a CircleCI hosted Windows VM.
#>
[CmdletBinding()]
param(
    [string] $SeedRoot = (Join-Path -Path (Get-Location).Path -ChildPath 'Saved/RuntimeProof/CI/UE58Seed'),
    [string] $DestinationRoot = 'C:\UE_5.8',
    [double] $SafetyGiB = 8.0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$archivePath = Join-Path $SeedRoot 'ue58-win64.zip'
$manifestPath = Join-Path $SeedRoot 'ue58-win64-manifest.json'
if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) {
    throw "UE cache archive missing: $archivePath"
}
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "UE cache manifest missing: $manifestPath"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ([int]$manifest.Schema -lt 2) {
    throw "UE cache manifest schema is too old: $($manifest.Schema)"
}
if ([string]$manifest.EngineVersion -notmatch '^5\.8\.') {
    throw "Cached engine version is not UE 5.8.x: $($manifest.EngineVersion)"
}
if (-not [bool]$manifest.ArchiveCreated -or -not [bool]$manifest.ArchiveIntegrityValidated) {
    throw 'UE cache manifest does not mark the archive as created and integrity-validated.'
}

$actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne [string]$manifest.ArchiveSha256) {
    throw 'UE cache archive SHA256 mismatch.'
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

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$destinationParent = Split-Path -Parent $DestinationRoot
New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
$destinationParentFull = [System.IO.Path]::GetFullPath($destinationParent).TrimEnd('\') + '\'
$engineLeaf = Split-Path -Leaf $DestinationRoot
$expectedPrefix = "$engineLeaf/"
$createdDestination = $false

try {
    $readStream = [System.IO.File]::OpenRead($archivePath)
    try {
        $zip = [System.IO.Compression.ZipArchive]::new(
            $readStream,
            [System.IO.Compression.ZipArchiveMode]::Read,
            $false
        )
        try {
            $fileEntries = @($zip.Entries | Where-Object { -not [string]::IsNullOrEmpty($_.Name) })
            if ($fileEntries.Count -ne [int]$manifest.ArchivedFileCount) {
                throw ("Archive entry count mismatch: manifest={0}, zip={1}." -f $manifest.ArchivedFileCount, $fileEntries.Count)
            }

            $validatedTargets = [System.Collections.Generic.Dictionary[string,string]]::new(
                [System.StringComparer]::OrdinalIgnoreCase
            )
            foreach ($entry in $fileEntries) {
                $normalized = $entry.FullName.Replace('\', '/')
                if (-not $normalized.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                    throw "Archive entry is outside expected UE root: $normalized"
                }
                if (
                    $normalized.StartsWith('/') -or
                    $normalized.Contains(':') -or
                    $normalized -match '(^|/)\.\.(/|$)'
                ) {
                    throw "Unsafe archive entry path: $normalized"
                }

                $relativeWindows = $normalized.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
                $targetPath = [System.IO.Path]::GetFullPath((Join-Path $destinationParent $relativeWindows))
                if (-not $targetPath.StartsWith($destinationParentFull, [System.StringComparison]::OrdinalIgnoreCase)) {
                    throw "Archive entry escapes destination root: $normalized"
                }
                if ($validatedTargets.ContainsKey($normalized)) {
                    throw "Duplicate archive entry: $normalized"
                }
                $validatedTargets.Add($normalized, $targetPath)
            }

            $createdDestination = $true
            foreach ($entry in $fileEntries) {
                $normalized = $entry.FullName.Replace('\', '/')
                $targetPath = $validatedTargets[$normalized]
                $targetDirectory = Split-Path -Parent $targetPath
                New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
                $input = $entry.Open()
                try {
                    $output = [System.IO.File]::Open(
                        $targetPath,
                        [System.IO.FileMode]::CreateNew,
                        [System.IO.FileAccess]::Write,
                        [System.IO.FileShare]::None
                    )
                    try {
                        $input.CopyTo($output, 1MB)
                    } finally {
                        $output.Dispose()
                    }
                } finally {
                    $input.Dispose()
                }
            }
        } finally {
            $zip.Dispose()
        }
    } finally {
        $readStream.Dispose()
    }

    $buildVersionPath = Join-Path $DestinationRoot 'Engine/Build/Build.version'
    if (-not (Test-Path -LiteralPath $buildVersionPath -PathType Leaf)) {
        throw 'Restored UE tree is missing Engine/Build/Build.version.'
    }
    $restoredVersion = Get-Content -LiteralPath $buildVersionPath -Raw | ConvertFrom-Json
    $restoredVersionText = ('{0}.{1}.{2}' -f $restoredVersion.MajorVersion, $restoredVersion.MinorVersion, $restoredVersion.PatchVersion)
    if ($restoredVersionText -ne [string]$manifest.EngineVersion) {
        throw "Restored UE version mismatch: manifest=$($manifest.EngineVersion), restored=$restoredVersionText"
    }

    foreach ($relative in $manifest.RequiredFiles) {
        $requiredPath = Join-Path $DestinationRoot ([string]$relative)
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Restored UE tree is missing required file: $relative"
        }
    }
} catch {
    if ($createdDestination -and (Test-Path -LiteralPath $DestinationRoot)) {
        Remove-Item -LiteralPath $DestinationRoot -Recurse -Force
    }
    throw
}

Remove-Item -LiteralPath $archivePath -Force
Write-Host ("UE 5.8 restore: PASS -> {0}" -f $DestinationRoot) -ForegroundColor Green
