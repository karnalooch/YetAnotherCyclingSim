<#
.SYNOPSIS
    Measure and optionally package the local UE 5.8 Launcher install for CircleCI.

.DESCRIPTION
    Creates a conservative Win64/Editor archive from an existing UE 5.8 installation.
    Generated/local-only directories and obvious sample/template payloads are excluded.
    Engine source, binaries, content, shaders and plugins are otherwise preserved.

    Default mode is measurement only. Use -CreateArchive after reviewing the manifest.
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
    $sum = (Get-ChildItem -LiteralPath $Path -File -Recurse -Force -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum
    if ($null -eq $sum) { return [int64]0 }
    return [int64]$sum
}

function Convert-BytesToGiB {
    param([int64] $Bytes)
    return [math]::Round($Bytes / 1GB, 3)
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

$totalBytes = Measure-TreeBytes -Path $EngineRoot
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
$archivePath = Join-Path $OutputRoot 'ue58-win64.tar.gz'
$manifestPath = Join-Path $OutputRoot 'ue58-win64-manifest.json'

$manifest = [ordered]@{
    Schema = 1
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
}

if ($manifest.EstimatedIncludedGiB -gt $MaxIncludedGiB) {
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    throw ("Slim UE estimate is {0} GiB, above safety limit {1} GiB. Review exclusions before archiving." -f $manifest.EstimatedIncludedGiB, $MaxIncludedGiB)
}

if ($CreateArchive) {
    if (Test-Path -LiteralPath $archivePath) { Remove-Item -LiteralPath $archivePath -Force }
    $tar = (Get-Command tar.exe -ErrorAction Stop).Source
    $engineParent = Split-Path -Parent $EngineRoot
    $engineLeaf = Split-Path -Leaf $EngineRoot
    $args = @('-czf', $archivePath)
    foreach ($relative in $excludeRelative) {
        $unixRelative = ($relative -replace '\\', '/')
        $args += "--exclude=$engineLeaf/$unixRelative"
    }
    $args += @('-C', $engineParent, $engineLeaf)
    & $tar @args
    if ($LASTEXITCODE -ne 0) { throw "tar.exe failed with exit code $LASTEXITCODE." }

    $archive = Get-Item -LiteralPath $archivePath
    $hash = Get-FileHash -LiteralPath $archivePath -Algorithm SHA256
    $manifest.ArchiveCreated = $true
    $manifest.ArchiveBytes = [int64]$archive.Length
    $manifest.ArchiveGiB = Convert-BytesToGiB -Bytes $archive.Length
    $manifest.ArchiveSha256 = $hash.Hash.ToLowerInvariant()
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
    Write-Host ("Archive GiB  : {0}" -f $manifest.ArchiveGiB)
    Write-Host ("SHA256       : {0}" -f $manifest.ArchiveSha256)
    Write-Host ("Archive      : {0}" -f $archivePath)
} else {
    Write-Host 'Measurement only. Re-run with -CreateArchive after reviewing size.'
}
