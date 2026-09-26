<#
.SYNOPSIS
    Record the actual GitHub-hosted Windows executor baseline for YACS.

.DESCRIPTION
    Lightweight diagnostic probe. It does not install or build Unreal Engine.
    The result captures the hosted Windows toolchain and machine baseline so
    YACS can make informed decisions about which jobs belong on GitHub-hosted
    versus the repository-scoped yacs-ue58 self-hosted runner.
#>
[CmdletBinding()]
param(
    [string] $ArtifactRoot = (Join-Path -Path (Get-Location).Path -ChildPath 'Saved/RuntimeProof/CI/GitHub-Windows-Probe')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

function Get-CommandInfo {
    param([Parameter(Mandatory=$true)][string] $Name)

    $cmd = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $cmd) {
        return [ordered]@{
            Found = $false
            Path = $null
            Version = $null
        }
    }

    $version = $null
    try {
        switch ($Name) {
            'git' { $version = (& git --version).Trim() }
            'pwsh' { $version = (& pwsh --version).Trim() }
            'cmake' { $version = ((& cmake --version | Select-Object -First 1).Trim()) }
            'ninja' { $version = (& ninja --version).Trim() }
            default {
                if ($cmd.Version) {
                    $version = $cmd.Version.ToString()
                }
            }
        }
    }
    catch {
        $version = $null
    }

    return [ordered]@{
        Found = $true
        Path = $cmd.Source
        Version = $version
    }
}

$os = Get-CimInstance Win32_OperatingSystem
$computer = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$logicalDisks = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
    [ordered]@{
        DeviceId = $_.DeviceID
        SizeGb = [math]::Round($_.Size / 1GB, 2)
        FreeGb = [math]::Round($_.FreeSpace / 1GB, 2)
    }
}

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$visualStudio = $null
if (Test-Path -LiteralPath $vswhere) {
    $vsJson = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format json
    if ($LASTEXITCODE -eq 0 -and $vsJson) {
        $vs = $vsJson | ConvertFrom-Json | Select-Object -First 1
        if ($vs) {
            $visualStudio = [ordered]@{
                InstallationPath = $vs.installationPath
                Version = $vs.installationVersion
                ProductId = $vs.productId
            }
        }
    }
}

$gitLfs = [ordered]@{ Found = $false; Version = $null }
try {
    $lfsText = (& git lfs version 2>$null).Trim()
    if ($LASTEXITCODE -eq 0 -and $lfsText) {
        $gitLfs.Found = $true
        $gitLfs.Version = $lfsText
    }
}
catch { }

$ueCandidates = @(
    'D:\Epic Games\UE_5.8',
    'C:\Program Files\Epic Games\UE_5.8',
    'C:\Epic Games\UE_5.8',
    'D:\UE_5.8',
    'C:\UE_5.8'
)
$ueRoots = @($ueCandidates | Where-Object { Test-Path -LiteralPath $_ })

$payload = [ordered]@{
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
    GitHubActions = [ordered]@{
        RunId = $env:GITHUB_RUN_ID
        RunAttempt = $env:GITHUB_RUN_ATTEMPT
        Workflow = $env:GITHUB_WORKFLOW
        Ref = $env:GITHUB_REF
        Sha = $env:GITHUB_SHA
        Actor = $env:GITHUB_ACTOR
    }
    Host = [ordered]@{
        ComputerName = $env:COMPUTERNAME
        OsCaption = $os.Caption
        OsVersion = $os.Version
        Cpu = $cpu.Name
        LogicalProcessors = $computer.NumberOfLogicalProcessors
        TotalRamGb = [math]::Round($computer.TotalPhysicalMemory / 1GB, 2)
        Disks = @($logicalDisks)
    }
    Tools = [ordered]@{
        Git = Get-CommandInfo -Name 'git'
        GitLfs = $gitLfs
        PowerShell7 = Get-CommandInfo -Name 'pwsh'
        CMake = Get-CommandInfo -Name 'cmake'
        Ninja = Get-CommandInfo -Name 'ninja'
        VisualStudio = $visualStudio
    }
    Unreal = [ordered]@{
        Detected = ($ueRoots.Count -gt 0)
        CandidateRoots = @($ueRoots)
    }
}

$jsonPath = Join-Path $ArtifactRoot 'windows_probe.json'
$textPath = Join-Path $ArtifactRoot 'windows_probe.txt'
$payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
$payload | Format-List | Out-String | Set-Content -LiteralPath $textPath -Encoding UTF8

Write-Host '=== GitHub Actions Windows probe ==='
Write-Host ("OS              : {0}" -f $payload.Host.OsCaption)
Write-Host ("CPU             : {0}" -f $payload.Host.Cpu)
Write-Host ("Logical CPUs    : {0}" -f $payload.Host.LogicalProcessors)
Write-Host ("RAM GB          : {0}" -f $payload.Host.TotalRamGb)
foreach ($disk in $payload.Host.Disks) {
    Write-Host ("Disk {0}        : {1} GB total / {2} GB free" -f $disk.DeviceId, $disk.SizeGb, $disk.FreeGb)
}
Write-Host ("Git             : found={0} version={1}" -f $payload.Tools.Git.Found, $payload.Tools.Git.Version)
Write-Host ("Git LFS         : found={0} version={1}" -f $payload.Tools.GitLfs.Found, $payload.Tools.GitLfs.Version)
Write-Host ("PowerShell 7    : found={0} version={1}" -f $payload.Tools.PowerShell7.Found, $payload.Tools.PowerShell7.Version)
Write-Host ("CMake           : found={0} version={1}" -f $payload.Tools.CMake.Found, $payload.Tools.CMake.Version)
Write-Host ("Ninja           : found={0} version={1}" -f $payload.Tools.Ninja.Found, $payload.Tools.Ninja.Version)
Write-Host ("Visual Studio   : {0}" -f $(if ($payload.Tools.VisualStudio) { $payload.Tools.VisualStudio.Version } else { 'not detected with VC tools' }))
Write-Host ("UE 5.8 detected : {0}" -f $payload.Unreal.Detected)
Write-Host ("Artifact root   : {0}" -f $ArtifactRoot)

if (-not $payload.Tools.Git.Found) {
    throw 'GitHub-hosted Windows image is missing Git.'
}
if (-not $payload.Tools.GitLfs.Found) {
    throw 'GitHub-hosted Windows image is missing Git LFS.'
}
if (-not $payload.Tools.VisualStudio) {
    throw 'GitHub-hosted Windows image is missing Visual Studio C++ tools.'
}

Write-Host 'GITHUB WINDOWS PROBE PASSED.' -ForegroundColor Green
