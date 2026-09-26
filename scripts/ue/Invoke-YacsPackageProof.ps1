<#
.SYNOPSIS
    Fail-closed Win64 cook/package proof for YACS.

.DESCRIPTION
    Runs Unreal AutomationTool BuildCookRun against the exact trusted checkout,
    explicitly cooking the YACS prototype map instead of relying on the current
    engine-template GameDefaultMap. The proof validates the archived package
    shape but leaves package binaries under Saved/RuntimeProof so CI can upload
    only concise logs/summaries and clean the workspace afterwards.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [ValidateSet('Development', 'Shipping')] [string] $Configuration = 'Development',
    [string] $MapPackage = '/Game/Prototype/Maps/L_CyclingTest'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) {
    $ProjectPath = Join-Path -Path $RepoRoot -ChildPath 'YetAnotherCyclingSim.uproject'
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/CI/Package'
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$Preflight = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Preflight-YacsProof.ps1'
$PreflightArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $ArtifactRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
}
$Context = & $Preflight @PreflightArgs
if ($LASTEXITCODE -ne 0) {
    throw 'Package proof preflight failed.'
}

if (-not $Context.UATPath -or -not (Test-Path -LiteralPath $Context.UATPath -PathType Leaf)) {
    throw 'RunUAT.bat was not resolved by preflight.'
}

$ArchiveRoot = Join-Path -Path $ArtifactRoot -ChildPath 'Archive'
$LogPath = Join-Path -Path $ArtifactRoot -ChildPath 'buildcookrun.log'
$SummaryPath = Join-Path -Path $ArtifactRoot -ChildPath 'package_summary.json'
$SummaryTextPath = Join-Path -Path $ArtifactRoot -ChildPath 'package_summary.txt'

if (Test-Path -LiteralPath $ArchiveRoot) {
    Remove-Item -LiteralPath $ArchiveRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $ArchiveRoot -Force | Out-Null
if (Test-Path -LiteralPath $LogPath) {
    Remove-Item -LiteralPath $LogPath -Force
}

Write-Host '=== YACS Win64 package proof ===' -ForegroundColor Cyan
Write-Host ('Project       : {0}' -f $ProjectPath)
Write-Host ('Configuration : {0}' -f $Configuration)
Write-Host ('Map           : {0}' -f $MapPackage)
Write-Host ('Archive       : {0}' -f $ArchiveRoot)

$UatArgs = @(
    'BuildCookRun'
    ('-project="' + $ProjectPath + '"')
    '-noP4'
    '-utf8output'
    '-unattended'
    '-platform=Win64'
    ('-clientconfig=' + $Configuration)
    '-build'
    '-cook'
    '-stage'
    '-pak'
    '-archive'
    ('-archivedirectory="' + $ArchiveRoot + '"')
    ('-map=' + $MapPackage)
)

Write-Host ('Running: RunUAT.bat {0}' -f ($UatArgs -join ' ')) -ForegroundColor Cyan
& $Context.UATPath @UatArgs 2>&1 | Tee-Object -FilePath $LogPath
$ExitCode = $LASTEXITCODE

if ($null -eq $ExitCode) {
    throw 'RunUAT exit code is unavailable.'
}
if ($ExitCode -ne 0) {
    throw "BuildCookRun failed with exit code $ExitCode; see $LogPath"
}

$ExeFiles = @(
    Get-ChildItem -LiteralPath $ArchiveRoot -Recurse -File -Filter '*.exe' -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ieq 'YetAnotherCyclingSim.exe' }
)
$PakFiles = @(
    Get-ChildItem -LiteralPath $ArchiveRoot -Recurse -File -Filter '*.pak' -ErrorAction SilentlyContinue
)
$UtocFiles = @(
    Get-ChildItem -LiteralPath $ArchiveRoot -Recurse -File -Filter '*.utoc' -ErrorAction SilentlyContinue
)
$UcasFiles = @(
    Get-ChildItem -LiteralPath $ArchiveRoot -Recurse -File -Filter '*.ucas' -ErrorAction SilentlyContinue
)

if ($ExeFiles.Count -lt 1) {
    throw "Packaged YetAnotherCyclingSim.exe was not found under $ArchiveRoot"
}

$HasPak = $PakFiles.Count -gt 0
$HasIoStore = $UtocFiles.Count -gt 0 -and $UcasFiles.Count -gt 0
if (-not $HasPak -and -not $HasIoStore) {
    throw 'No packaged content container was found (.pak or .utoc/.ucas pair).'
}

$LogText = Get-Content -LiteralPath $LogPath -Raw -ErrorAction Stop
if ($LogText -notmatch [regex]::Escape($MapPackage)) {
    throw "BuildCookRun log does not mention required map '$MapPackage'."
}

$ArchiveFiles = @(Get-ChildItem -LiteralPath $ArchiveRoot -Recurse -File -ErrorAction Stop)
$ArchiveMeasure = $ArchiveFiles | Measure-Object -Property Length -Sum
$ArchiveBytes = if ($null -eq $ArchiveMeasure.Sum) { [int64]0 } else { [int64]$ArchiveMeasure.Sum }
if ($ArchiveBytes -le 0) {
    throw 'Packaged archive is empty.'
}

$Summary = [ordered]@{
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
    Branch = $Context.Branch
    Head = $Context.Head
    Configuration = $Configuration
    MapPackage = $MapPackage
    UatExitCode = $ExitCode
    ArchiveRoot = $ArchiveRoot
    ArchiveFileCount = $ArchiveFiles.Count
    ArchiveBytes = $ArchiveBytes
    ExecutableCount = $ExeFiles.Count
    PakCount = $PakFiles.Count
    UtocCount = $UtocFiles.Count
    UcasCount = $UcasFiles.Count
    HasPak = $HasPak
    HasIoStore = $HasIoStore
    LogPath = $LogPath
}
$Summary | ConvertTo-Json -Depth 4 |
    Set-Content -LiteralPath $SummaryPath -Encoding UTF8

@(
    '=== YACS Win64 package proof summary ==='
    ('TimestampUtc  : {0}' -f $Summary.TimestampUtc)
    ('Branch        : {0}' -f $Summary.Branch)
    ('Head          : {0}' -f $Summary.Head)
    ('Configuration : {0}' -f $Summary.Configuration)
    ('Map           : {0}' -f $Summary.MapPackage)
    ('UAT exit      : {0}' -f $Summary.UatExitCode)
    ('Archive files : {0}' -f $Summary.ArchiveFileCount)
    ('Archive bytes : {0}' -f $Summary.ArchiveBytes)
    ('Executables   : {0}' -f $Summary.ExecutableCount)
    ('PAK files     : {0}' -f $Summary.PakCount)
    ('UTOC files    : {0}' -f $Summary.UtocCount)
    ('UCAS files    : {0}' -f $Summary.UcasCount)
) | Set-Content -LiteralPath $SummaryTextPath -Encoding UTF8

Write-Host ''
Write-Host 'PACKAGE PROOF PASSED.' -ForegroundColor Green
Write-Host ('Archive files={0}; bytes={1}; exe={2}; pak={3}; utoc={4}; ucas={5}' -f $Summary.ArchiveFileCount, $Summary.ArchiveBytes, $Summary.ExecutableCount, $Summary.PakCount, $Summary.UtocCount, $Summary.UcasCount)
exit 0
