#requires -Version 7.4
<#
.SYNOPSIS
    Previews or removes allow-listed ephemeral YACS runner output directories.

.DESCRIPTION
    Preview is the default. Deletion requires -Apply. Only direct children of
    the canonical repository workspace matching versioned `_unreal-build-*` or
    `_unreal-region-*` output names are eligible. Persistent world data, retained
    LFS payloads, source caches, Git data, runner credentials and unknown paths
    are never candidates.
#>
[CmdletBinding()]
param(
    [string] $RunnerRoot = 'D:\actions-runner-yacs',
    [ValidateRange(0, 8760)][int] $MinimumAgeHours = 1,
    [ValidateRange(-1, 2147483647)][int] $ExpectedCandidateCount = -1,
    [long] $ExpectedReclaimBytes = -1,
    [switch] $Apply,
    [switch] $Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string] $Path)
    return [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
}

function Get-DirectoryInventory {
    param([Parameter(Mandatory = $true)][string] $Path)

    $Bytes = 0L
    $Files = 0
    $Newest = (Get-Item -LiteralPath $Path -Force -ErrorAction Stop).LastWriteTimeUtc
    foreach ($Item in @(Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction Stop)) {
        if (($Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Cleanup candidate contains a reparse point: $($Item.FullName)"
        }
        if ($Item.PSIsContainer) { continue }
        $Bytes += [int64]$Item.Length
        $Files++
        if ($Item.LastWriteTimeUtc -gt $Newest) { $Newest = $Item.LastWriteTimeUtc }
    }
    return [pscustomobject]@{ Bytes = $Bytes; Files = $Files; NewestUtc = $Newest }
}

$RunnerRoot = Get-NormalizedPath $RunnerRoot
$DriveRoot = [System.IO.Path]::GetPathRoot($RunnerRoot).TrimEnd('\', '/')
if ($RunnerRoot -eq $DriveRoot -or $RunnerRoot.Length -le ($DriveRoot.Length + 3)) {
    throw "Unsafe runner root: $RunnerRoot"
}

$RepositoryWorkspace = Get-NormalizedPath (Join-Path $RunnerRoot '_work/YetAnotherCyclingSim/YetAnotherCyclingSim')
if (-not (Test-Path -LiteralPath $RepositoryWorkspace -PathType Container)) {
    throw "Canonical YACS runner workspace does not exist: $RepositoryWorkspace"
}

$ProtectedNames = @(
    '.git',
    '_yacs-world-data',
    '_yacs-retained-lfs',
    '_yacs-sa-calobra-assets',
    '_embark-terrain-worktree',
    '_terrain-recovery-worktree',
    '_passo-giau-worktree',
    '_passo-giau-hairpin-worktree',
    '_sa-calobra-performance',
    '_unreal-ci-warm'
)
$EligiblePatterns = @(
    '^_unreal-build-[0-9]+-[0-9]+$',
    '^_unreal-region-[0-9]+-[0-9]+$'
)
$Cutoff = [DateTime]::UtcNow.AddHours(-$MinimumAgeHours)
$Candidates = [System.Collections.Generic.List[object]]::new()
$WorkspacePrefix = $RepositoryWorkspace + [System.IO.Path]::DirectorySeparatorChar

foreach ($Directory in @(Get-ChildItem -LiteralPath $RepositoryWorkspace -Directory -Force -ErrorAction Stop)) {
    if ($Directory.Name -in $ProtectedNames) { continue }
    $Eligible = $false
    foreach ($Pattern in $EligiblePatterns) {
        if ($Directory.Name -match $Pattern) { $Eligible = $true; break }
    }
    if (-not $Eligible) { continue }
    if (($Directory.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Cleanup candidate is a reparse point: $($Directory.FullName)"
    }

    $Resolved = Get-NormalizedPath $Directory.FullName
    if (-not $Resolved.StartsWith($WorkspacePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Cleanup candidate escaped the workspace: $Resolved"
    }
    if ((Get-NormalizedPath (Split-Path -Parent $Resolved)) -ne $RepositoryWorkspace) {
        throw "Cleanup candidate is not a direct workspace child: $Resolved"
    }

    $Inventory = Get-DirectoryInventory $Resolved
    if ($Inventory.NewestUtc -gt $Cutoff) { continue }
    [void]$Candidates.Add([pscustomobject]@{
        Name = $Directory.Name
        Path = $Resolved
        Bytes = [int64]$Inventory.Bytes
        Files = [int]$Inventory.Files
        NewestUtc = $Inventory.NewestUtc.ToString('o')
        AgeHours = [math]::Round(([DateTime]::UtcNow - $Inventory.NewestUtc).TotalHours, 2)
    })
}

$Drive = [System.IO.DriveInfo]::new([System.IO.Path]::GetPathRoot($RunnerRoot))
$FreeBefore = [int64]$Drive.AvailableFreeSpace
$EstimatedBytes = [int64](($Candidates | Measure-Object Bytes -Sum).Sum)
$DeletedBytes = 0L

if ($Apply) {
    if ($ExpectedCandidateCount -lt 0 -or $ExpectedReclaimBytes -lt 0) {
        throw 'Apply mode requires -ExpectedCandidateCount and -ExpectedReclaimBytes from a reviewed preview.'
    }
    if ($Candidates.Count -ne $ExpectedCandidateCount -or $EstimatedBytes -ne $ExpectedReclaimBytes) {
        throw (
            'Cleanup plan changed after preview: expected {0} candidates/{1} bytes, found {2}/{3}. Run preview again.' -f
            $ExpectedCandidateCount, $ExpectedReclaimBytes, $Candidates.Count, $EstimatedBytes
        )
    }
    if (-not $IsWindows) { throw 'Cleanup apply mode is supported only on Windows.' }
    $Workers = @(Get-Process -Name 'Runner.Worker' -ErrorAction SilentlyContinue)
    if ($Workers.Count -gt 0) {
        throw 'Runner.Worker is active. Wait for the GitHub Actions job to finish before cleanup.'
    }
    $UnrealNames = @('UnrealEditor.exe', 'UnrealEditor-Cmd.exe', 'ShaderCompileWorker.exe', 'CrashReportClient.exe')
    $ActiveUnreal = @(
        Get-CimInstance Win32_Process -ErrorAction Stop |
            Where-Object {
                $_.Name -in $UnrealNames -and
                $_.CommandLine -and
                $_.CommandLine.IndexOf($RepositoryWorkspace, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
            }
    )
    if ($ActiveUnreal.Count -gt 0) {
        $Description = $ActiveUnreal | ForEach-Object { "{0} pid={1}" -f $_.Name, $_.ProcessId }
        throw ('Workspace-scoped Unreal processes are active: ' + ($Description -join ', '))
    }

    foreach ($Candidate in $Candidates) {
        $Resolved = Get-NormalizedPath $Candidate.Path
        if (-not $Resolved.StartsWith($WorkspacePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Candidate escaped the workspace before deletion: $Resolved"
        }
        if ((Split-Path -Leaf $Resolved) -in $ProtectedNames) {
            throw "Protected directory cannot be deleted: $Resolved"
        }
        $CurrentInventory = Get-DirectoryInventory $Resolved
        if (
            $CurrentInventory.Bytes -ne $Candidate.Bytes -or
            $CurrentInventory.Files -ne $Candidate.Files -or
            $CurrentInventory.NewestUtc.ToString('o') -ne $Candidate.NewestUtc
        ) {
            throw "Cleanup candidate changed during apply; nothing further was deleted: $Resolved"
        }
        Remove-Item -LiteralPath $Resolved -Recurse -Force -ErrorAction Stop
        if (Test-Path -LiteralPath $Resolved) { throw "Cleanup target still exists after deletion: $Resolved" }
        $DeletedBytes += [int64]$Candidate.Bytes
    }
}

$DriveAfter = [System.IO.DriveInfo]::new([System.IO.Path]::GetPathRoot($RunnerRoot))
$FreeAfter = [int64]$DriveAfter.AvailableFreeSpace
$Payload = [ordered]@{
    schema_version = 1
    apply = [bool]$Apply
    runner_root = $RunnerRoot
    repository_workspace = $RepositoryWorkspace
    minimum_age_hours = $MinimumAgeHours
    expected_candidate_count = $ExpectedCandidateCount
    expected_reclaim_bytes = $ExpectedReclaimBytes
    candidate_count = $Candidates.Count
    estimated_reclaim_bytes = $EstimatedBytes
    deleted_bytes = $DeletedBytes
    free_before_bytes = $FreeBefore
    free_after_bytes = $FreeAfter
    protected_names = $ProtectedNames
    candidates = @($Candidates)
}

if ($Json) {
    $Payload | ConvertTo-Json -Depth 5
}
else {
    $Candidates | Sort-Object Bytes -Descending | Format-Table Name, Files, Bytes, AgeHours, Path -AutoSize
    Write-Host ("Cleanup mode: {0}" -f $(if ($Apply) { 'APPLY' } else { 'PREVIEW (no deletion)' }))
    Write-Host ("Candidates: {0}; estimated reclaim: {1:N2} GiB" -f $Candidates.Count, ($EstimatedBytes / 1GB))
    Write-Host ("Disk free before/after: {0:N2} / {1:N2} GiB" -f ($FreeBefore / 1GB), ($FreeAfter / 1GB))
    if (-not $Apply) { Write-Host 'Re-run with -Apply only after reviewing every listed target.' }
}
