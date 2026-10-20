#requires -Version 7.4
<#
.SYNOPSIS
  Bounded YACS disk maintenance independent of the GitHub runner.
.DESCRIPTION
  Audit by default. Apply handles ONLY aged temporary Unreal build caches
  authorized by Clear-YacsRunnerWorkspace and old filesystem DDC files.
  No source, map, Zen, LFS, lesson or proof deletion.
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [ValidateRange(7,120)][int]$MinimumAgeDays = 14,
    [ValidateRange(10,1000)][double]$TargetFreeGiB = 50,
    [ValidateRange(1,40)][double]$MaxReclaimGiB = 12,
    [switch]$Json
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Windows is required for YACS disk maintenance.' }

$root = 'D:\yacs'
$runnerRoot = Join-Path $root 'runner'
$ddcRoot = Join-Path $root 'cache\DerivedDataCache'
$maintenanceRoot = Join-Path $root 'maintenance'
$runnerCleaner = Join-Path $PSScriptRoot 'Clear-YacsRunnerWorkspace.ps1'
if (-not (Test-Path -LiteralPath (Join-Path $root 'workspace.json') -PathType Leaf)) {
    throw 'Canonical YACS workspace is missing.'
}
if (-not (Test-Path -LiteralPath (Join-Path $runnerRoot '.runner') -PathType Leaf)) {
    throw 'Registered YACS runner is missing.'
}
if (-not (Test-Path -LiteralPath $runnerCleaner -PathType Leaf)) {
    throw 'Existing reviewed runner cleanup helper is unavailable.'
}

function Assert-NoReparse {
    param([Parameter(Mandatory=$true)][string]$Path)
    $part = [IO.Path]::GetFullPath($Path)
    while ($part) {
        if (Test-Path -LiteralPath $part) {
            $item = Get-Item -LiteralPath $part -Force -ErrorAction Stop
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing symlink or junction: $part"
            }
        }
        $parent = [IO.Path]::GetDirectoryName($part)
        if (-not $parent -or $parent -eq $part) { break }
        $part = $parent
    }
}
foreach ($path in @($root,$runnerRoot,$ddcRoot,$maintenanceRoot,$runnerCleaner)) {
    Assert-NoReparse $path
}
$busyNames = @('Runner.Worker','UnrealEditor','UnrealEditor-Cmd',
    'ShaderCompileWorker','UnrealBuildTool','hython','houdini',
    'houdinifx','hbatch')
function Get-BusyWorkloads {
    return @(Get-Process -Name $busyNames -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty ProcessName -Unique)
}

$busy = @(Get-BusyWorkloads)
$zenActive = @(Get-Process -Name 'zenserver' -ErrorAction SilentlyContinue).Count -gt 0
$before = [long]([IO.DriveInfo]::new('D:\')).AvailableFreeSpace
$needed = [long][Math]::Max(0,[Math]::Ceiling($TargetFreeGiB*1GB-$before))
$budget = [long][Math]::Floor($MaxReclaimGiB*1GB)
$ageHours = $MinimumAgeDays * 24
$cutoff = [DateTime]::UtcNow.AddDays(-$MinimumAgeDays)
$runnerPlan = $null
$runnerBytes = 0L
$takeRunner = $false
$ddcSelected = [System.Collections.Generic.List[object]]::new()
$ddcTotal = 0L
$ddcEligible = 0L
$notes = [System.Collections.Generic.List[string]]::new()

if ($busy.Count -gt 0) {
    $notes.Add('Native processes busy: ' + ($busy -join ', '))
} elseif ($needed -eq 0) {
    $notes.Add('Disk free >= target: keep warm caches.')
} else {
    $workspace = Join-Path $runnerRoot '_work\YetAnotherCyclingSim\YetAnotherCyclingSim'
    if (Test-Path -LiteralPath $workspace -PathType Container) {
        $runnerPlan = (& $runnerCleaner -RunnerRoot $runnerRoot -MinimumAgeHours $ageHours -Json) | ConvertFrom-Json
        $runnerBytes = [long]$runnerPlan.estimated_reclaim_bytes
        if ($runnerBytes -gt 0 -and $runnerBytes -le $budget) {
            $takeRunner = $true
        } elseif ($runnerBytes -gt $budget) {
            $notes.Add('Runner candidates exceed per-run budget: manual review required.')
        }
    }
    $reserved = [long]$(if ($takeRunner) { $runnerBytes } else { 0L })
    $room = $budget-$reserved
    $shortfall = [long][Math]::Max(0,$needed-$reserved)
    if ($zenActive) {
        $notes.Add('Zenserver active: do not touch filesystem DDC.')
    } elseif ($room -gt 0 -and $shortfall -gt 0 -and
              (Test-Path -LiteralPath $ddcRoot -PathType Container)) {
        $entries = @(Get-ChildItem -LiteralPath $ddcRoot -Recurse -Force -ErrorAction Stop)
        if (@($entries | Where-Object {
            ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
        }).Count -gt 0) {
            throw 'DDC contains a symlink or junction; stopping cleanup.'
        }
        $files = @($entries | Where-Object { -not $_.PSIsContainer })
        foreach ($file in $files) { $ddcTotal += [long]$file.Length }
        foreach ($file in @($files | Where-Object {
            $_.LastWriteTimeUtc -lt $cutoff
        } | Sort-Object LastWriteTimeUtc)) {
            $ddcEligible += [long]$file.Length
            if ($ddcSelected.Count -ge 10000 -or $file.Length -gt $room -or
                $shortfall -le 0) { continue }
            $ddcSelected.Add([pscustomobject]@{
                Path=[string]$file.FullName
                Length=[long]$file.Length
                LastWriteTimeUtc=$file.LastWriteTimeUtc.ToString('o')
            })
            $room -= [long]$file.Length
            $shortfall -= [long]$file.Length
        }
    }
}
$selected = [long]$(if ($takeRunner) { $runnerBytes } else { 0L })
foreach ($f in $ddcSelected) { $selected += [long]$f.Length }
$deleted = 0L
$runnerDeleted = 0L
$ddcDeleted = 0
$status = if ($busy.Count -gt 0) { 'SKIPPED_BUSY' } elseif ($needed -eq 0) {
    'HEALTHY_NO_CLEANUP'
} elseif ($selected -eq 0) { 'LOW_SPACE_NO_SAFE_CANDIDATES' } else { 'AUDIT_READY' }

if ($Apply -and $selected -gt 0 -and $busy.Count -eq 0) {
    [void][IO.Directory]::CreateDirectory($maintenanceRoot)
    Assert-NoReparse $maintenanceRoot
    $lockPath = Join-Path $maintenanceRoot 'autoclean.lock'
    Assert-NoReparse $lockPath
    $lock = [IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,
        [IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    try {
        if (@(Get-BusyWorkloads).Count -gt 0) {
            throw 'Native work started during planning. No cleanup allowed.'
        }
        if ($takeRunner) {
            $again = (& $runnerCleaner -RunnerRoot $runnerRoot -MinimumAgeHours $ageHours -Json) | ConvertFrom-Json
            if ([long]$again.estimated_reclaim_bytes -ne $runnerBytes -or
                [int]$again.candidate_count -ne [int]$runnerPlan.candidate_count) {
                throw 'Runner cache inventory changed. No cleanup allowed.'
            }
            $applied = (& $runnerCleaner -RunnerRoot $runnerRoot -MinimumAgeHours $ageHours -ExpectedCandidateCount ([int]$again.candidate_count) -ExpectedReclaimBytes ([long]$again.estimated_reclaim_bytes) -Apply -Json) | ConvertFrom-Json
            $runnerDeleted = [long]$applied.deleted_bytes
            if ($runnerDeleted -ne $runnerBytes) {
                throw 'Reviewed runner cleanup did not remove the expected bytes.'
            }
            $deleted += $runnerDeleted
        }
        if ($ddcSelected.Count -gt 0 -and
            @(Get-Process -Name zenserver -ErrorAction SilentlyContinue).Count -gt 0) {
            throw 'Zenserver started during planning. DDC cleanup cancelled.'
        }
        foreach ($f in $ddcSelected) {
            if (@(Get-BusyWorkloads).Count -gt 0 -or
                @(Get-Process -Name zenserver -ErrorAction SilentlyContinue).Count -gt 0) {
                throw 'A native process started; remaining DDC cleanup cancelled.'
            }
            Assert-NoReparse $f.Path
            $current = Get-Item -LiteralPath $f.Path -Force -ErrorAction Stop
            if ($current.PSIsContainer -or $current.Length -ne $f.Length -or
                $current.LastWriteTimeUtc.ToString('o') -ne $f.LastWriteTimeUtc -or
                $current.LastWriteTimeUtc -ge $cutoff) {
                throw "A DDC file changed after audit: $($f.Path)"
            }
            Remove-Item -LiteralPath $f.Path -Force -ErrorAction Stop
            $deleted += [long]$f.Length
            $ddcDeleted++
        }
        $status = 'APPLIED'
    }
    finally { $lock.Dispose() }
}
$after = [long]([IO.DriveInfo]::new('D:\')).AvailableFreeSpace
$receipt = [ordered]@{
    schema_version=1
    status=$status
    time_utc=[DateTime]::UtcNow.ToString('o')
    mode=$(if ($Apply) { 'apply' } else { 'audit' })
    drive='D:\'
    free_before_gib=[math]::Round($before/1GB,2)
    free_after_gib=[math]::Round($after/1GB,2)
    target_free_gib=$TargetFreeGiB
    minimum_age_days=$MinimumAgeDays
    max_reclaim_gib=$MaxReclaimGiB
    runner_old_cache_gib=[math]::Round($runnerBytes/1GB,2)
    runner_cache_selected=$takeRunner
    runner_deleted_gib=[math]::Round($runnerDeleted/1GB,2)
    ddc_total_gib=[math]::Round($ddcTotal/1GB,2)
    ddc_eligible_gib=[math]::Round($ddcEligible/1GB,2)
    ddc_files_selected=$ddcSelected.Count
    ddc_files_deleted=$ddcDeleted
    planned_reclaim_gib=[math]::Round($selected/1GB,2)
    deleted_gib=[math]::Round($deleted/1GB,2)
    zen_running=$zenActive
    native_busy=$busy
    protected=@('project','engine','data','tools','cache\Zen',
        'cache\git-lfs','work\lesson*','work\runner-retention',
        'project\Saved\RuntimeProof','project\.git')
    warnings=@($notes)
}
if ($Apply) {
    Assert-NoReparse $maintenanceRoot
    $receiptPath = Join-Path $maintenanceRoot 'latest-autoclean.json'
    $tempPath = Join-Path $maintenanceRoot ('autoclean-' + [guid]::NewGuid().ToString('n') + '.tmp')
    $receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $tempPath -Encoding utf8
    Move-Item -LiteralPath $tempPath -Destination $receiptPath -Force
}
if ($Json) { $receipt | ConvertTo-Json -Depth 6 } else { $receipt | Format-List }
