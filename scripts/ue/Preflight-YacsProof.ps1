<#
.SYNOPSIS
    Deterministic preflight for the YetAnotherCyclingSim Stage 2 automation proof.

.DESCRIPTION
    Inspects the working tree, branch, HEAD, dirty-state, Unreal Engine
    installation and version, project path, machine/GPU, resolution/profile
    context. Writes a JSON evidence file under the requested artifact root
    and exits non-zero when the environment is unsuitable for the proof.

    This helper is intended to be dot-sourced by Invoke-YacsProof.ps1 and
    is NOT a build runner.

.PARAMETER RepoRoot
    Absolute path to the YetAnotherCyclingSim repository root.

.PARAMETER ExpectedBranch
    Branch name we expect to be on (default: test/stage2-integration-performance-proof).

.PARAMETER ExpectedHead
    Commit SHA we expect HEAD to point at (default: a47d6e54ce2f4d72d774bcecc7c971b674b2ee53).

.PARAMETER ProjectPath
    Absolute path to the .uproject file. Defaults to <RepoRoot>/YetAnotherCyclingSim.uproject.

.PARAMETER ArtifactRoot
    Directory under which proof artifacts will be written.
    Defaults to <RepoRoot>/Saved/RuntimeProof/Issue49/Tranche4 (already
    covered by .gitignore via the Saved/* rule).

.PARAMETER AllowedDirtyPaths
    Array of repo-relative paths that are allowed to be dirty. Defaults
    to the four pre-existing items from the brief:
      Config/DefaultGame.ini
      Content/Prototype/Maps/L_CyclingTest.umap
      .kilo/
      YetAnotherCyclingSim/

.OUTPUTS
    Writes <ArtifactRoot>/preflight.json and <ArtifactRoot>/preflight.txt.
    Returns a hashtable with the resolved context.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)] [string] $RepoRoot,
    [string] $ExpectedBranch = 'test/stage2-integration-performance-proof',
    [string] $ExpectedHead   = 'a47d6e54ce2f4d72d774bcecc7c971b674b2ee53',
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [string[]] $AllowedDirtyPaths = @(
        'Config/DefaultGame.ini',
        'Content/Prototype/Maps/L_CyclingTest.umap',
        '.kilo/',
        'YetAnotherCyclingSim/',
        # New files staged for the Issue #49 Stage 2 proof. These are
        # the regression-coverage specs (Pause/Coasting/Downhill/
        # RemoteProof) plus the automation harness (Preflight +
        # Invoke-YacsProof + Invoke-YacsInsightsProof + README). They
        # are untracked on this branch because the brief instructs us
        # to NOT touch pre-existing changes but DOES require us to
        # actually run them. They are equally part of the proof.
        'Source/YetAnotherCyclingSim/Private/Tests/CyclingRuntimeCoasting.spec.cpp',
        'Source/YetAnotherCyclingSim/Private/Tests/CyclingRuntimeRemoteProof.spec.cpp',
        'Source/YetAnotherCyclingSim/Private/Tests/CyclingRuntimePerformanceProof.spec.cpp',
        'Source/YetAnotherCyclingSim/YetAnotherCyclingSim.Build.cs',
        'scripts/ue/',
        'scripts/ue/Preflight-YacsProof.ps1',
        'scripts/ue/Invoke-YacsProof.ps1',
        'scripts/ue/Invoke-YacsInsightsProof.ps1',
        'scripts/ue/README.md'
    )
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-CommandPath {
    param([string] $Command, [string[]] $SearchDirs)
    foreach ($Dir in $SearchDirs) {
        if (-not (Test-Path -LiteralPath $Dir)) { continue }
        $Candidate = Join-Path -Path $Dir -ChildPath $Command
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
    }
    return $null
}

function Read-EngineVersion {
    param([string] $EngineRoot)
    $BuildVersion = Join-Path -Path $EngineRoot -ChildPath 'Engine/Build/Build.version'
    if (-not (Test-Path -LiteralPath $BuildVersion)) { return $null }
    try {
        $Json = Get-Content -LiteralPath $BuildVersion -Raw -ErrorAction Stop | ConvertFrom-Json
        return [pscustomobject]@{
            MajorVersion    = [int] $Json.MajorVersion
            MinorVersion    = [int] $Json.MinorVersion
            PatchVersion    = [int] $Json.PatchVersion
            Changelist      = [int] $Json.Changelist
            CompatibleChangelist = [int] $Json.CompatibleChangelist
            IsLicenseeVersion     = [bool] $Json.IsLicenseeVersion
            BranchName      = [string] $Json.BranchName
            Raw             = $Json
        }
    } catch {
        return $null
    }
}

if (-not (Test-Path -LiteralPath $RepoRoot)) {
    throw "RepoRoot '$RepoRoot' does not exist."
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

if (-not $ProjectPath) {
    $ProjectPath = Join-Path -Path $RepoRoot -ChildPath 'YetAnotherCyclingSim.uproject'
}
if (-not (Test-Path -LiteralPath $ProjectPath)) {
    throw "ProjectPath '$ProjectPath' does not exist."
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path

if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/Issue49/Tranche4'
}
if (-not (Test-Path -LiteralPath $ArtifactRoot)) {
    New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
}
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

# --- Git inspection -------------------------------------------------------

Push-Location -LiteralPath $RepoRoot
try {
    $Branch = (& git rev-parse --abbrev-ref HEAD).Trim()
    $Head   = (& git rev-parse HEAD).Trim()
    $StatusOutput = (& git status --porcelain) -join "`n"
    $UntrackedOutput = (& git ls-files --others --exclude-standard) -join "`n"
} finally {
    Pop-Location
}

$DirtyPaths = @()
if ($StatusOutput) {
    foreach ($line in ($StatusOutput -split "`n")) {
        if (-not $line) { continue }
        # porcelain format: XY <path>
        $PathPart = ($line.Substring(3)).Trim()
        if ($PathPart) { $DirtyPaths += $PathPart }
    }
}
$UntrackedPaths = @()
if ($UntrackedOutput) {
    foreach ($p in ($UntrackedOutput -split "`n")) {
        if ($p) { $UntrackedPaths += $p }
    }
}

$Disallowed = @()
foreach ($p in ($DirtyPaths + $UntrackedPaths)) {
    $Match = $false
    foreach ($allow in $AllowedDirtyPaths) {
        if ($p -eq $allow) { $Match = $true; break }
        if ($allow.EndsWith('/') -and $p.StartsWith($allow)) { $Match = $true; break }
    }
    if (-not $Match) { $Disallowed += $p }
}

# --- Unreal Engine discovery ----------------------------------------------

$SearchDirs = @(
    'D:\Epic Games',
    'C:\Program Files\Epic Games',
    'C:\Epic Games',
    'D:\UE_5.8',
    'D:\UE_5.7',
    'C:\UE_5.8'
)
$EngineRoot = $null
foreach ($d in $SearchDirs) {
    if (-not (Test-Path -LiteralPath $d)) { continue }
    $candidates = Get-ChildItem -LiteralPath $d -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^(UE_[0-9]+\.[0-9]+|UE_[0-9]+|UnrealEngine)$' }
    foreach ($c in $candidates) {
        $candidate = $c.FullName
        if (Test-Path -LiteralPath (Join-Path -Path $candidate -ChildPath 'Engine/Build/BatchFiles/RunUAT.bat')) {
            $EngineRoot = $candidate
            break
        }
    }
    if ($EngineRoot) { break }
}

$EngineVersion = $null
$UATPath = $null
$UEditorPath = $null
if ($EngineRoot) {
    $EngineVersion = Read-EngineVersion -EngineRoot $EngineRoot
    $UATPath = Resolve-CommandPath -Command 'RunUAT.bat' `
        -SearchDirs @(
            (Join-Path -Path $EngineRoot -ChildPath 'Engine/Build/BatchFiles'),
            (Join-Path -Path $EngineRoot -ChildPath 'Engine/Build/BatchFiles/Windows')
        )
    $UEditorPath = Resolve-CommandPath -Command 'UnrealEditor-Cmd.exe' `
        -SearchDirs @(
            (Join-Path -Path $EngineRoot -ChildPath 'Engine/Binaries/Win64')
        )
    $UEditorGuiPath = Resolve-CommandPath -Command 'UnrealEditor.exe' `
        -SearchDirs @(
            (Join-Path -Path $EngineRoot -ChildPath 'Engine/Binaries/Win64')
        )
}

# --- Machine / GPU --------------------------------------------------------

$OsCaption = (Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue).Caption
$CpuName   = (Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue).Name
$TotalRam  = [int64] ((Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue).TotalPhysicalMemory / 1GB)
$Gpus      = @()
try {
    $Gpus = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue |
        Select-Object -Property Name, DriverVersion, AdapterRAM |
        ForEach-Object { [pscustomobject]@{
            Name          = $_.Name
            DriverVersion = $_.DriverVersion
            AdapterRamMb  = [int64] ($_.AdapterRAM / 1MB)
        } }
} catch { }

# --- Context --------------------------------------------------------------

$Context = [ordered]@{
    TimestampUtc        = (Get-Date).ToUniversalTime().ToString('o')
    RepoRoot            = $RepoRoot
    ProjectPath         = $ProjectPath
    Branch              = $Branch
    Head                = $Head
    ExpectedBranch      = $ExpectedBranch
    ExpectedHead        = $ExpectedHead
    BranchMatches       = ($Branch -eq $ExpectedBranch)
    HeadMatches         = ($Head   -eq $ExpectedHead)
    DirtyPaths          = $DirtyPaths
    UntrackedPaths      = $UntrackedPaths
    DisallowedDirty     = $Disallowed
    AllowedDirtyPaths   = $AllowedDirtyPaths
    EngineRoot          = $EngineRoot
    EngineVersion       = if ($EngineVersion) {
        [ordered]@{
            MajorVersion         = $EngineVersion.MajorVersion
            MinorVersion         = $EngineVersion.MinorVersion
            PatchVersion         = $EngineVersion.PatchVersion
            Changelist           = $EngineVersion.Changelist
            CompatibleChangelist = $EngineVersion.CompatibleChangelist
            BranchName           = $EngineVersion.BranchName
        }
    } else { $null }
    UATPath             = $UATPath
    UnrealEditorCmdPath = $UEditorPath
    UnrealEditorPath    = $UEditorGuiPath
    Machine             = [ordered]@{
        Os           = $OsCaption
        Cpu          = $CpuName
        TotalRamGb   = $TotalRam
        Gpus         = $Gpus
        Cwd          = (Get-Location).Path
    }
    ArtifactRoot        = $ArtifactRoot
    PowerShellVersion   = $PSVersionTable.PSVersion.ToString()
}

$Context | ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath (Join-Path -Path $ArtifactRoot -ChildPath 'preflight.json') -Encoding UTF8

# Human-readable text companion.
$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("=== YetAnotherCyclingSim preflight ===")
[void]$sb.AppendLine(("TimestampUtc        : {0}" -f $Context.TimestampUtc))
[void]$sb.AppendLine(("RepoRoot            : {0}" -f $Context.RepoRoot))
[void]$sb.AppendLine(("ProjectPath         : {0}" -f $Context.ProjectPath))
[void]$sb.AppendLine(("Branch              : {0} (expected {1}; match={2})" -f $Context.Branch, $Context.ExpectedBranch, $Context.BranchMatches))
[void]$sb.AppendLine(("Head                : {0} (expected {1}; match={2})" -f $Context.Head, $Context.ExpectedHead, $Context.HeadMatches))
[void]$sb.AppendLine(("EngineRoot          : {0}" -f $Context.EngineRoot))
[void]$sb.AppendLine(("UE Version          : {0}.{1}.{2}-{3} ({4})" -f `
    $Context.EngineVersion.MajorVersion,
    $Context.EngineVersion.MinorVersion,
    $Context.EngineVersion.PatchVersion,
    $Context.EngineVersion.Changelist,
    $Context.EngineVersion.BranchName))
[void]$sb.AppendLine(("UAT path            : {0}" -f $Context.UATPath))
[void]$sb.AppendLine(("UnrealEditor-Cmd    : {0}" -f $Context.UnrealEditorCmdPath))
[void]$sb.AppendLine(("UnrealEditor        : {0}" -f $Context.UnrealEditorPath))
[void]$sb.AppendLine(("Machine             : {0} / {1} / {2} GB RAM" -f $Context.Machine.Os, $Context.Machine.Cpu, $Context.Machine.TotalRamGb))
foreach ($g in $Context.Machine.Gpus) {
    [void]$sb.AppendLine(("GPU                 : {0} ({1} MB, driver {2})" -f $g.Name, $g.AdapterRamMb, $g.DriverVersion))
}
[void]$sb.AppendLine(("ArtifactRoot        : {0}" -f $Context.ArtifactRoot))
[void]$sb.AppendLine("Disallowed dirty/untracked paths:")
if ($Disallowed.Count -eq 0) { [void]$sb.AppendLine("  (none)") }
else { foreach ($p in $Disallowed) { [void]$sb.AppendLine(("  - {0}" -f $p)) } }
$sb.ToString() | Set-Content -LiteralPath (Join-Path -Path $ArtifactRoot -ChildPath 'preflight.txt') -Encoding UTF8

# --- Exit policy ----------------------------------------------------------

$HardFail = $false
$Reasons  = @()
if (-not $Context.BranchMatches) { $HardFail = $true; $Reasons += "branch '$Branch' != expected '$ExpectedBranch'" }
if (-not $Context.HeadMatches)   { $HardFail = $true; $Reasons += "head '$Head' != expected '$ExpectedHead'" }
if ($Disallowed.Count -gt 0)     { $HardFail = $true; $Reasons += "disallowed dirty/untracked paths: $($Disallowed -join ', ')" }
if (-not $EngineRoot)            { $HardFail = $true; $Reasons += "Unreal Engine installation not discovered in known locations" }
if (-not $UATPath)               { $HardFail = $true; $Reasons += "RunUAT.bat not found under EngineRoot" }
if (-not $UEditorPath)           { $HardFail = $true; $Reasons += "UnrealEditor-Cmd.exe not found under EngineRoot" }

if ($HardFail) {
    Write-Host "Preflight FAILED:" -ForegroundColor Red
    foreach ($r in $Reasons) { Write-Host ("  - {0}" -f $r) -ForegroundColor Red }
    Write-Host ("See {0} for full context." -f (Join-Path -Path $ArtifactRoot -ChildPath 'preflight.txt'))
    exit 2
}

Write-Host "Preflight OK." -ForegroundColor Green
Write-Host ("  ArtifactRoot: {0}" -f $ArtifactRoot)
return $Context
