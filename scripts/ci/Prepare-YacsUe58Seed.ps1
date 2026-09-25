<#
.SYNOPSIS
    Measure and optionally package the local UE 5.8 Launcher install for CircleCI.

.DESCRIPTION
    Creates a conservative Win64/Editor ZIP from an existing UE 5.8 installation.
    Generated/local-only directories and obvious sample/template payloads are excluded.
    Engine source, binaries, content, shaders and plugins are otherwise preserved.

    Default mode is measurement only. Use -CreateArchive after reviewing the manifest.

    Archive creation stays on the output volume. A uniquely named .partial ZIP is
    written first, reopened and fully decompressed for validation, and compared against
    the complete expected input file set. Only a validated archive is renamed to the
    final ue58-win64.zip name.
#>
[CmdletBinding()]
param(
    [string] $EngineRoot,
    [string] $OutputRoot = (Join-Path -Path (Get-Location).Path -ChildPath 'Saved/RuntimeProof/CI/UE58Seed'),
    [switch] $CreateArchive,
    [double] $MaxIncludedGiB = 45.0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-YacsEngineRoot {
    param([string] $Requested)
    if ($Requested) {
        if (-not (Test-Path -LiteralPath $Requested -PathType Container)) {
            throw "EngineRoot '$Requested' does not exist."
        }
        return (Resolve-Path -LiteralPath $Requested).Path
    }

    $candidates = @(
        'D:\Epic Games\UE_5.8',
        'C:\Program Files\Epic Games\UE_5.8',
        'C:\Epic Games\UE_5.8',
        'D:\UE_5.8',
        'C:\UE_5.8'
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Container) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw 'UE 5.8 installation was not found in known locations.'
}

function Measure-TreeBytes {
    param([Parameter(Mandatory=$true)][string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) { return [int64]0 }
    $sum = (Get-ChildItem -LiteralPath $Path -File -Recurse -Force -ErrorAction Stop |
        Measure-Object -Property Length -Sum).Sum
    if ($null -eq $sum) { return [int64]0 }
    return [int64]$sum
}

function Convert-BytesToGiB {
    param([int64] $Bytes)
    return [math]::Round($Bytes / 1GB, 3)
}

function Get-IncludedFiles {
    param(
        [Parameter(Mandatory=$true)][string] $Root,
        [Parameter(Mandatory=$true)][string[]] $ExcludedRelative
    )

    $rootPrefix = $Root.TrimEnd('\') + '\'
    $excludedPrefixes = @(
        foreach ($relative in $ExcludedRelative) {
            (Join-Path $Root $relative).TrimEnd('\') + '\'
        }
    )

    foreach ($item in Get-ChildItem -LiteralPath $Root -File -Recurse -Force -ErrorAction Stop) {
        $isExcluded = $false
        foreach ($prefix in $excludedPrefixes) {
            if ($item.FullName.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                $isExcluded = $true
                break
            }
        }
        if (-not $isExcluded) {
            [pscustomobject]@{
                FullName = $item.FullName
                RelativePath = $item.FullName.Substring($rootPrefix.Length).Replace('\', '/')
                Length = [int64]$item.Length
            }
        }
    }
}

function Get-DriveFreeBytes {
    param([Parameter(Mandatory=$true)][string] $Path)
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetPathRoot($fullPath)
    if ([string]::IsNullOrWhiteSpace($root)) {
        throw "Could not determine filesystem root for '$Path'."
    }
    $drive = [System.IO.DriveInfo]::new($root)
    if (-not $drive.IsReady) {
        throw "Output drive '$root' is not ready."
    }
    return [int64]$drive.AvailableFreeSpace
}

function Get-FileSha256Hex {
    param([Parameter(Mandatory=$true)][string] $Path)

    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $hashBytes = $sha256.ComputeHash($stream)
        return ([System.BitConverter]::ToString($hashBytes)).Replace('-', '').ToLowerInvariant()
    } finally {
        $stream.Dispose()
        $sha256.Dispose()
    }
}

$EngineRoot = Resolve-YacsEngineRoot -Requested $EngineRoot
$buildVersionPath = Join-Path $EngineRoot 'Engine/Build/Build.version'
if (-not (Test-Path -LiteralPath $buildVersionPath -PathType Leaf)) {
    throw "Missing Unreal Build.version: $buildVersionPath"
}
$version = Get-Content -LiteralPath $buildVersionPath -Raw | ConvertFrom-Json
if ([int]$version.MajorVersion -ne 5 -or [int]$version.MinorVersion -ne 8) {
    throw ("Expected UE 5.8.x, found {0}.{1}.{2}." -f $version.MajorVersion, $version.MinorVersion, $version.PatchVersion)
}

$requiredFiles = @(
    'Engine/Build/BatchFiles/Build.bat',
    'Engine/Binaries/Win64/UnrealEditor.exe',
    'Engine/Binaries/Win64/UnrealEditor-Cmd.exe',
    'Engine/Binaries/Win64/ShaderCompileWorker.exe',
    'Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.dll'
)
foreach ($relative in $requiredFiles) {
    $candidate = Join-Path $EngineRoot $relative
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "Required UE file missing: $relative"
    }
}

$excludeRelative = @(
    'Engine\DerivedDataCache',
    'Engine\Intermediate',
    'Engine\Saved',
    'FeaturePacks',
    'Samples',
    'Templates'
)

Write-Host ("Scanning UE 5.8 tree: {0}" -f $EngineRoot)
$totalBytes = Measure-TreeBytes -Path $EngineRoot
Write-Host ("UE tree scan complete: {0} GiB" -f (Convert-BytesToGiB -Bytes $totalBytes))
$excluded = @()
$excludedBytes = [int64]0
foreach ($relative in $excludeRelative) {
    $path = Join-Path $EngineRoot $relative
    $bytes = Measure-TreeBytes -Path $path
    $excludedBytes += $bytes
    $excluded += [ordered]@{
        Path = $relative
        Exists = (Test-Path -LiteralPath $path)
        Bytes = $bytes
        GiB = Convert-BytesToGiB -Bytes $bytes
    }
}
$includedBytes = [math]::Max([int64]0, $totalBytes - $excludedBytes)

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$OutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path
$archivePath = Join-Path $OutputRoot 'ue58-win64.zip'
$manifestPath = Join-Path $OutputRoot 'ue58-win64-manifest.json'

$manifest = [ordered]@{
    Schema = 2
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
    EngineRoot = $EngineRoot
    EngineVersion = ('{0}.{1}.{2}' -f $version.MajorVersion, $version.MinorVersion, $version.PatchVersion)
    Changelist = [int64]$version.Changelist
    TotalBytes = $totalBytes
    TotalGiB = Convert-BytesToGiB -Bytes $totalBytes
    ExcludedBytes = $excludedBytes
    ExcludedGiB = Convert-BytesToGiB -Bytes $excludedBytes
    EstimatedIncludedBytes = $includedBytes
    EstimatedIncludedGiB = Convert-BytesToGiB -Bytes $includedBytes
    MaxIncludedGiB = $MaxIncludedGiB
    Exclusions = $excluded
    RequiredFiles = $requiredFiles
    ArchiveCreated = $false
    ArchivePath = $archivePath
    ArchiveBytes = $null
    ArchiveGiB = $null
    ArchiveSha256 = $null
    ArchiveIntegrityValidated = $false
    ExpectedFileCount = $null
    ArchivedFileCount = $null
    ArchiveError = $null
}

if ($manifest.EstimatedIncludedGiB -gt $MaxIncludedGiB) {
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    throw ("Slim UE estimate is {0} GiB, above safety limit {1} GiB. Review exclusions before archiving." -f $manifest.EstimatedIncludedGiB, $MaxIncludedGiB)
}

if ($CreateArchive) {
    if (Test-Path -LiteralPath $archivePath) {
        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
            throw "Existing final archive has no manifest proving prior validation: $archivePath"
        }

        $previousManifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        $countsMatch = (
            $null -ne $previousManifest.ExpectedFileCount -and
            $null -ne $previousManifest.ArchivedFileCount -and
            [int64]$previousManifest.ExpectedFileCount -gt 0 -and
            [int64]$previousManifest.ExpectedFileCount -eq [int64]$previousManifest.ArchivedFileCount
        )
        $wasValidated = ($previousManifest.ArchiveIntegrityValidated -eq $true)
        $postValidationHashFailure = (
            $countsMatch -and
            -not $wasValidated -and
            -not [string]::IsNullOrWhiteSpace([string]$previousManifest.ArchiveError) -and
            ([string]$previousManifest.ArchiveError -match 'Get-FileHash')
        )

        if ([string]$previousManifest.EngineVersion -ne [string]$manifest.EngineVersion) {
            throw ("Existing archive manifest version {0} does not match current UE version {1}." -f $previousManifest.EngineVersion, $manifest.EngineVersion)
        }
        if (-not ($wasValidated -or $postValidationHashFailure)) {
            throw "Existing final archive cannot be safely resumed because its manifest does not prove prior validation."
        }

        Write-Host ("Reusing validated UE seed archive without repacking: {0}" -f $archivePath)
        if ($postValidationHashFailure) {
            Write-Host 'Prior run completed full ZIP validation and failed only while invoking Get-FileHash; resuming at SHA256.'
        }

        $archive = Get-Item -LiteralPath $archivePath
        $currentHash = Get-FileSha256Hex -Path $archivePath
        if ($wasValidated -and -not [string]::IsNullOrWhiteSpace([string]$previousManifest.ArchiveSha256)) {
            $previousHash = ([string]$previousManifest.ArchiveSha256).ToLowerInvariant()
            if ($currentHash -ne $previousHash) {
                throw ("Existing archive SHA256 mismatch. expected={0}; actual={1}" -f $previousHash, $currentHash)
            }
        }

        $manifest.ArchiveCreated = $true
        $manifest.ArchiveBytes = [int64]$archive.Length
        $manifest.ArchiveGiB = Convert-BytesToGiB -Bytes $archive.Length
        $manifest.ArchiveSha256 = $currentHash
        $manifest.ArchiveIntegrityValidated = $true
        $manifest.ExpectedFileCount = [int64]$previousManifest.ExpectedFileCount
        $manifest.ArchivedFileCount = [int64]$previousManifest.ArchivedFileCount
        $manifest.ArchiveError = $null
    } else {
        $minimumFreeBytes = [int64]($includedBytes + 2GB)
    $freeBytes = Get-DriveFreeBytes -Path $OutputRoot
    if ($freeBytes -lt $minimumFreeBytes) {
        throw ("Not enough free space on the output drive. Free={0} GiB; safe minimum={1} GiB." -f (Convert-BytesToGiB $freeBytes), (Convert-BytesToGiB $minimumFreeBytes))
    }

    $partialPath = Join-Path $OutputRoot ("ue58-win64.partial.{0}.zip" -f [guid]::NewGuid().ToString('N'))
    try {
        Add-Type -AssemblyName System.IO.Compression
        Add-Type -AssemblyName System.IO.Compression.FileSystem

        $engineLeaf = Split-Path -Leaf $EngineRoot
        Write-Host 'Enumerating files for UE seed archive...'
        $sourceFiles = @(Get-IncludedFiles -Root $EngineRoot -ExcludedRelative $excludeRelative)
        $manifest.ExpectedFileCount = $sourceFiles.Count
        Write-Host ("Archive input files: {0}" -f $sourceFiles.Count)

        $fileStream = [System.IO.File]::Open(
            $partialPath,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
        try {
            $zip = [System.IO.Compression.ZipArchive]::new(
                $fileStream,
                [System.IO.Compression.ZipArchiveMode]::Create,
                $true
            )
            try {
                $packedCount = 0
                $packProgress = [System.Diagnostics.Stopwatch]::StartNew()
                foreach ($sourceFile in $sourceFiles) {
                    $entryName = "$engineLeaf/$($sourceFile.RelativePath)"
                    $entry = $zip.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
                    $input = [System.IO.File]::OpenRead($sourceFile.FullName)
                    try {
                        $output = $entry.Open()
                        try {
                            $input.CopyTo($output, 1MB)
                        } finally {
                            $output.Dispose()
                        }
                    } finally {
                        $input.Dispose()
                    }

                    $packedCount++
                    if ($packProgress.Elapsed.TotalSeconds -ge 30) {
                        $percent = [math]::Round(($packedCount / [double]$sourceFiles.Count) * 100, 1)
                        Write-Host ("Packing UE seed: {0}/{1} files ({2}%)" -f $packedCount, $sourceFiles.Count, $percent)
                        $packProgress.Restart()
                    }
                }
                Write-Host ("Packing UE seed complete: {0}/{1} files" -f $packedCount, $sourceFiles.Count)
            } finally {
                $zip.Dispose()
            }
        } finally {
            $fileStream.Dispose()
        }

        $expectedSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
        foreach ($sourceFile in $sourceFiles) {
            [void]$expectedSet.Add("$engineLeaf/$($sourceFile.RelativePath)")
        }

        $readStream = [System.IO.File]::OpenRead($partialPath)
        try {
            $zipRead = [System.IO.Compression.ZipArchive]::new(
                $readStream,
                [System.IO.Compression.ZipArchiveMode]::Read,
                $false
            )
            try {
                $archiveSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
                $validatedCount = 0
                $validationProgress = [System.Diagnostics.Stopwatch]::StartNew()
                foreach ($entry in $zipRead.Entries) {
                    if ([string]::IsNullOrEmpty($entry.Name)) { continue }
                    if (-not $archiveSet.Add($entry.FullName)) {
                        throw "Duplicate archive entry: $($entry.FullName)"
                    }

                    $entryStream = $entry.Open()
                    try {
                        $entryStream.CopyTo([System.IO.Stream]::Null, 1MB)
                    } finally {
                        $entryStream.Dispose()
                    }

                    $validatedCount++
                    if ($validationProgress.Elapsed.TotalSeconds -ge 30) {
                        Write-Host ("Validating UE seed: {0} files read" -f $validatedCount)
                        $validationProgress.Restart()
                    }
                }
                Write-Host ("Validating UE seed complete: {0} files read" -f $validatedCount)

                $manifest.ArchivedFileCount = $archiveSet.Count
                $missing = @(
                    foreach ($expected in $expectedSet) {
                        if (-not $archiveSet.Contains($expected)) { $expected }
                    }
                )
                $unexpected = @(
                    foreach ($actual in $archiveSet) {
                        if (-not $expectedSet.Contains($actual)) { $actual }
                    }
                )
                if ($missing.Count -gt 0 -or $unexpected.Count -gt 0) {
                    $missingPreview = ($missing | Select-Object -First 10) -join ', '
                    $unexpectedPreview = ($unexpected | Select-Object -First 10) -join ', '
                    throw ("Archive file-set validation failed. missing={0} [{1}]; unexpected={2} [{3}]" -f $missing.Count, $missingPreview, $unexpected.Count, $unexpectedPreview)
                }

                foreach ($relative in $requiredFiles) {
                    $requiredEntry = "$engineLeaf/$($relative.Replace('\', '/'))"
                    if (-not $archiveSet.Contains($requiredEntry)) {
                        throw "Required UE file missing from archive: $relative"
                    }
                }
            } finally {
                $zipRead.Dispose()
            }
        } finally {
            $readStream.Dispose()
        }

        Move-Item -LiteralPath $partialPath -Destination $archivePath
        $archive = Get-Item -LiteralPath $archivePath
        $hash = Get-FileSha256Hex -Path $archivePath
        $manifest.ArchiveCreated = $true
        $manifest.ArchiveBytes = [int64]$archive.Length
        $manifest.ArchiveGiB = Convert-BytesToGiB -Bytes $archive.Length
        $manifest.ArchiveSha256 = $hash
        $manifest.ArchiveIntegrityValidated = $true
    } catch {
        $manifest.ArchiveError = $_.Exception.Message
        if (Test-Path -LiteralPath $partialPath) {
            Remove-Item -LiteralPath $partialPath -Force
        }
        $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
        throw
    }
    }
}

$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Write-Host '=== YACS UE 5.8 seed package ==='
Write-Host ("Engine       : {0}" -f $manifest.EngineRoot)
Write-Host ("Version      : {0}" -f $manifest.EngineVersion)
Write-Host ("Original GiB : {0}" -f $manifest.TotalGiB)
Write-Host ("Excluded GiB : {0}" -f $manifest.ExcludedGiB)
Write-Host ("Included GiB : {0}" -f $manifest.EstimatedIncludedGiB)
Write-Host ("Manifest     : {0}" -f $manifestPath)
if ($CreateArchive) {
    Write-Host ("Files        : {0}/{1}" -f $manifest.ArchivedFileCount, $manifest.ExpectedFileCount)
    Write-Host ("Integrity    : {0}" -f $manifest.ArchiveIntegrityValidated)
    Write-Host ("Archive GiB  : {0}" -f $manifest.ArchiveGiB)
    Write-Host ("SHA256       : {0}" -f $manifest.ArchiveSha256)
    Write-Host ("Archive      : {0}" -f $archivePath)
    Write-Host 'ARCHIVE PASS' -ForegroundColor Green
} else {
    Write-Host 'Measurement only. Re-run with -CreateArchive after reviewing size.'
}
