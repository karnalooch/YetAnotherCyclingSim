#requires -Version 7.4
<#
.SYNOPSIS
    Audits a clean Windows host before it becomes a trusted YACS UE runner.

.DESCRIPTION
    Performs read-only checks for the exact YACS toolchain. The script installs
    nothing and never prints credentials. It fails closed when a required
    prerequisite is absent or the wrong Unreal/Python version is selected.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path,
    [string] $RunnerRoot = 'D:\yacs\runner',
    [double] $MinimumFreeGiB = 50.0,
    [switch] $SkipGithubAuth,
    [switch] $Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $IsWindows) {
    throw 'YACS trusted Unreal host audit requires Windows x64.'
}

$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
$RunnerRoot = [System.IO.Path]::GetFullPath($RunnerRoot).TrimEnd('\')
$ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject'
$Results = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param(
        [Parameter(Mandatory = $true)][string] $Name,
        [Parameter(Mandatory = $true)][bool] $Passed,
        [Parameter(Mandatory = $true)][string] $Detail,
        [bool] $Required = $true
    )

    [void]$Results.Add([pscustomobject]@{
        Name = $Name
        Required = $Required
        Passed = $Passed
        Detail = $Detail
    })
}

function Get-CommandPath {
    param([Parameter(Mandatory = $true)][string] $Name)

    $Command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($Command) { return [string]$Command.Source }
    return ''
}

$GitPath = Get-CommandPath 'git'
Add-Check 'Git' (-not [string]::IsNullOrWhiteSpace($GitPath)) $(if ($GitPath) { $GitPath } else { 'not found in PATH' })

$LfsDetail = ''
$LfsPassed = $false
if ($GitPath) {
    $LfsDetail = (& git lfs version 2>&1 | Out-String).Trim()
    $LfsPassed = ($LASTEXITCODE -eq 0 -and $LfsDetail -match '^git-lfs/')
}
Add-Check 'Git LFS' $LfsPassed $(if ($LfsDetail) { $LfsDetail } else { 'git lfs version failed' })

$PwshPath = Get-CommandPath 'pwsh'
$PwshPassed = $PSVersionTable.PSVersion -ge [version]'7.4.0'
Add-Check 'PowerShell 7.4+' $PwshPassed ("{0} ({1})" -f $PSVersionTable.PSVersion, $(if ($PwshPath) { $PwshPath } else { 'current host' }))

$GhPath = Get-CommandPath 'gh'
Add-Check 'GitHub CLI' (-not [string]::IsNullOrWhiteSpace($GhPath)) $(if ($GhPath) { $GhPath } else { 'not found in PATH' })

if (-not $SkipGithubAuth) {
    $AuthDetail = ''
    $AuthPassed = $false
    if ($GhPath) {
        $AuthDetail = (& gh auth status --hostname github.com 2>&1 | Out-String).Trim()
        $AuthPassed = ($LASTEXITCODE -eq 0)
    }
    Add-Check 'GitHub authentication' $AuthPassed $(if ($AuthPassed) { 'authenticated to github.com' } else { 'run gh auth login --web --git-protocol https' })
}

$PythonPath = Get-CommandPath 'python'
$PythonVersion = ''
$PythonPassed = $false
if ($PythonPath) {
    $PythonVersion = (& python -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -eq 0) {
        try {
            $ParsedPython = [version]$PythonVersion
            $PythonPassed = ($ParsedPython.Major -eq 3 -and $ParsedPython.Minor -ge 12)
        }
        catch { }
    }
}
Add-Check 'Python 3.12+ x64' $PythonPassed $(if ($PythonVersion) { "$PythonVersion ($PythonPath)" } else { 'python not found in PATH' })

$VsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$VisualStudioPath = ''
if (Test-Path -LiteralPath $VsWhere -PathType Leaf) {
    $VisualStudioPath = (& $VsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null | Select-Object -First 1)
}
Add-Check 'Visual Studio C++ toolchain' (-not [string]::IsNullOrWhiteSpace($VisualStudioPath)) $(if ($VisualStudioPath) { $VisualStudioPath } else { 'Visual Studio 2022 Game development with C++ workload not found' })

$WindowsKitsRoot = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits/10/Lib'
$SdkVersions = @()
if (Test-Path -LiteralPath $WindowsKitsRoot -PathType Container) {
    $SdkVersions = @(Get-ChildItem -LiteralPath $WindowsKitsRoot -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | ForEach-Object Name)
}
Add-Check 'Windows SDK' ($SdkVersions.Count -gt 0) $(if ($SdkVersions.Count -gt 0) { $SdkVersions[0] } else { 'Windows SDK not found' })

$ResolverPath = Join-Path $RepoRoot 'scripts/ci/Resolve-YacsUnrealEngine.ps1'
$ResolvedEngine = $null
if ((Test-Path -LiteralPath $ResolverPath -PathType Leaf) -and (Test-Path -LiteralPath $ProjectPath -PathType Leaf)) {
    . $ResolverPath
    $ResolvedEngine = Resolve-YacsUnrealEngine -ProjectPath $ProjectPath
}
$EnginePassed = (
    $null -ne $ResolvedEngine -and
    $ResolvedEngine.VersionObject.MajorVersion -eq 5 -and
    $ResolvedEngine.VersionObject.MinorVersion -eq 8 -and
    $ResolvedEngine.VersionObject.PatchVersion -eq 2
)
$EngineDetail = if ($ResolvedEngine) { "{0} ({1})" -f $ResolvedEngine.Version, $ResolvedEngine.Root } else { 'UE 5.8.2 not found in a supported location' }
Add-Check 'Unreal Engine 5.8.2' $EnginePassed $EngineDetail

$RunnerDriveRoot = [System.IO.Path]::GetPathRoot($RunnerRoot)
$RunnerDrive = $null
try { $RunnerDrive = [System.IO.DriveInfo]::new($RunnerDriveRoot) } catch { }
$FreeGiB = if ($RunnerDrive) { [math]::Round($RunnerDrive.AvailableFreeSpace / 1GB, 2) } else { 0.0 }
Add-Check 'Runner disk free space' ($RunnerDrive -and $FreeGiB -ge $MinimumFreeGiB) ("{0:N2} GiB free; required {1:N2} GiB at {2}" -f $FreeGiB, $MinimumFreeGiB, $RunnerDriveRoot)

$PageFiles = @(Get-CimInstance Win32_PageFileUsage -ErrorAction SilentlyContinue)
$PageFileMiB = [int64](($PageFiles | Measure-Object AllocatedBaseSize -Sum).Sum)
Add-Check 'Windows page file' ($PageFileMiB -gt 0) $(if ($PageFileMiB -gt 0) { "$PageFileMiB MiB allocated" } else { 'no active page file; use Windows system-managed sizing' })

$GpuNames = @(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | ForEach-Object Name)
Add-Check 'GPU detection' ($GpuNames.Count -gt 0) $(if ($GpuNames.Count -gt 0) { $GpuNames -join '; ' } else { 'no GPU reported by Win32_VideoController' })

$Failures = @($Results | Where-Object { $_.Required -and -not $_.Passed })
$Payload = [ordered]@{
    schema_version = 1
    repo_root = $RepoRoot
    runner_root = $RunnerRoot
    passed = ($Failures.Count -eq 0)
    failure_count = $Failures.Count
    checks = @($Results)
}

if ($Json) {
    $Payload | ConvertTo-Json -Depth 5
}
else {
    $Results | Format-Table Name, Required, Passed, Detail -AutoSize
    Write-Host ("Host audit: {0}" -f $(if ($Failures.Count -eq 0) { 'PASS' } else { "FAIL ($($Failures.Count))" }))
}

if ($Failures.Count -gt 0) {
    throw ('YACS Windows host prerequisites failed: ' + (($Failures | ForEach-Object Name) -join ', '))
}
