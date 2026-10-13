#requires -Version 7.4
<#
.SYNOPSIS
  Prepare or install owner-logon YACS Live Host independently of GitHub Actions.
.DESCRIPTION
  -Apply is an explicit mutation, not default. Never modifies runner service.
  No Task Scheduler registration from unknown desktop identity or active UE.
  Copies pinned tracked scripts to a release outside runner/_work; every source
  is code-only and no LFS materialization, keys, caches or engine files are copied.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedHead,
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path,
  [string]$InstallRoot = 'D:\yacs\live-host',
  [switch]$Apply,
  [switch]$Verify,
  [switch]$Uninstall
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Assert-YacsLiveTaskPrincipal.ps1')
if (-not $IsWindows) { throw 'Windows host is required.' }
if ($Apply -and $Uninstall -or $Verify -and ($Apply -or $Uninstall)) {
  throw 'Choose only one install/verify/uninstall operation.'
}
$RepoRoot=(Resolve-Path -LiteralPath $RepoRoot).Path
$InstallRoot=[IO.Path]::GetFullPath($InstallRoot)
if ($InstallRoot -ine 'D:\yacs\live-host') { throw 'Only the dedicated D:\yacs\live-host root is supported.' }
$taskName='YACS Live Host'
$active=Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
$desktopUser=[string]$active.UserName
if (-not $desktopUser) { throw 'No logged-in Windows console user; defer Live Host installation.' }
$sid=([Security.Principal.NTAccount]::new($desktopUser)).Translate(
  [Security.Principal.SecurityIdentifier]).Value
if ($sid -in @('S-1-5-18','S-1-5-19','S-1-5-20')) {
  throw 'A Windows service identity cannot own the interactive UE task.'
}
if ((& git -C $RepoRoot rev-parse HEAD).Trim() -cne $ExpectedHead) {
  throw 'Installer source checkout differs from the exact requested HEAD.'
}
if (@(& git -C $RepoRoot status --porcelain --untracked-files=no).Count) {
  throw 'Installer refuses modified tracked source.'
}
$task=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
$liveHostRoot=Join-Path $InstallRoot 'state'
$installRecord=Join-Path $liveHostRoot 'installation.json'
$release=Join-Path $InstallRoot "releases\$ExpectedHead"
$startScript=Join-Path $release 'scripts/live_host/Start-YacsLiveHost.ps1'

function Assert-NoReparseAncestor([string]$Path) {
  $path=[IO.Path]::GetFullPath($Path)
  while($path) {
    if (Test-Path -LiteralPath $path) {
      $item=Get-Item -LiteralPath $path -Force
      if($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refuse redirected live-host path: $path" }
    }
    $parent=Split-Path -Path $path -Parent
    if($parent -eq $path) { break }
    $path=$parent
  }
}
Assert-NoReparseAncestor $InstallRoot
Assert-NoReparseAncestor $release
$hostState=( & (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1') )
if ($hostState.status -cne 'IDLE' -and ($Apply -or $Uninstall)) {
  throw "Active/unknown Unreal owner: $($hostState.status); refuse task mutation."
}
if ($task -and $task.State -eq 'Running' -and ($Apply -or $Uninstall)) {
  throw 'Existing Live Host task is running; installer must not interrupt it.'
}
if ($Uninstall) {
  if (-not $task) { Write-Host 'YACS Live Host not registered.'; return }
  # Refuse uninstall of another user's task even when the Principal is
  # returned as a SID rather than DOMAIN\User. Never stop a running task.
  Assert-YacsLiveTaskPrincipal -Task $task -ExpectedSid $sid | Out-Null
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
  Write-Host 'Task unregistered; all installed releases, evidence, engine, runner and maps retained.'
  return
}
if ($Verify) {
  if (-not $task) { throw 'YACS Live Host is not installed.' }
  # Windows often reports Principal.UserId as S-1-5-21-... even when the
  # registered identity was DOMAIN\User. Match by resolved SID instead.
  $principalProof=Assert-YacsLiveTaskPrincipal -Task $task -ExpectedSid $sid
  $data=Get-Content -LiteralPath $installRecord -Raw | ConvertFrom-Json
  if ($data.source_sha -cnotmatch '^[a-f0-9]{40}$' -or $data.desktop_sid -cne $sid) {
    throw 'Installed source identity or desktop SID differs.'
  }
  $installedRelease=Join-Path $InstallRoot "releases/$($data.source_sha)"
  $installedScript=Join-Path $installedRelease 'scripts/live_host/Start-YacsLiveHost.ps1'
  if (-not (Test-Path -LiteralPath $installedScript -PathType Leaf)) {
    throw 'Pinned installed startup source missing.'
  }
  if (@($data.file_proofs).Count -lt 50 -or @($data.file_proofs).Count -ne $data.installed_files) {
    throw 'No complete immutable installed code hash manifest.'
  }
  foreach ($proof in @($data.file_proofs)) {
    if ($proof.path -cnotmatch '^(scripts/[a-zA-Z0-9_./-]+|worldgen/sa_calobra/pcg365_rejected_sites_review_v1.json)$' -or
        $proof.path -match '\.\.') { throw 'Unsafe installed manifest path.' }
    $file=Join-Path $installedRelease $proof.path
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw 'Installed file missing.' }
    $actual=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -cne $proof.sha256) { throw "Installed reviewed source bytes differ: $($proof.path)" }
  }
  $info=Get-ScheduledTaskInfo -TaskName $taskName
  [pscustomobject]@{
    status='INSTALLED_NOT_LIVE_PROOF';task=$taskName
    state=[string]$task.State;lastResult=$info.LastTaskResult
    desktop_sid=$sid;source_sha=$data.source_sha
    principal_id=[string]$task.Principal.UserId
    principal_validation=$principalProof.status
    root=$InstallRoot;browser_proven=$false;post_job_survival_proven=$false
    world_profile_id=if($null -ne $data.PSObject.Properties['world_profile_id']) { $data.world_profile_id } else { 'DIAGNOSTIC_LEGACY_NOT_LATEST' }
  } | ConvertTo-Json -Depth 6
  return
}

$tracked=@(& git -C $RepoRoot ls-files -- scripts)
if($LASTEXITCODE -ne 0 -or $tracked.Count -lt 50 -or $tracked.Count -gt 2500) {
  throw 'Unable to authenticate bounded repository script source closure.'
}
if ([IO.DriveInfo]::new('D:\').AvailableFreeSpace -lt 5GB) {
  throw 'D: reserve below five GiB.'
}
# New Live Host installs must point to the latest saved accepted map; validate
# road/shoulder package hashes rather than falling back to red-site diagnostics.
$world=& (Join-Path $RepoRoot 'scripts/live_host/Resolve-YacsLiveWorld.ps1') -SourceRoot $RepoRoot
if ($world.status -cne 'LATEST_VERIFIED_WORLD_PREFLIGHT_PASS' -or
    $world.profile_id -cne 'sa_calobra_road_v0_3_1') {
  throw 'No admitted latest verified world; no historical fallback.'
}
foreach($relative in $tracked) {
  if($relative -cnotmatch '^scripts/[a-zA-Z0-9_./-]+$' -or $relative -match '\.\.') {
    throw "Unexpected installed script path: $relative"
  }
  $item=Get-Item -LiteralPath (Join-Path $RepoRoot $relative) -Force
  if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint -or
      $item.PSIsContainer -or $item.Length -gt 8MB) {
    throw "Unsafe or oversize executable source: $relative"
  }
}
$manifestRelative='worldgen/sa_calobra/pcg365_rejected_sites_review_v1.json'
$manifestPath=Join-Path $RepoRoot $manifestRelative
$manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.source_producer_sha -cne 'd361e7651d16ff424ae4e812c7d8cbe1fe81d662' -or
    @($manifest.markers).Count -ne 5 -or $manifest.placement -ne $false) {
  throw 'Unreviewed live diagnostic authority.'
}
$estimated=@($tracked | ForEach-Object {(Get-Item -LiteralPath (Join-Path $RepoRoot $_)).Length} |
  Measure-Object -Sum)[0].Sum
if ($estimated -gt 256MB) { throw 'Live Host code-only closure exceeds 256 MiB.' }
$arguments='-NoLogo -NoProfile -File "' + $startScript + '" -InstallRoot "' + $InstallRoot + '"'
Write-Host "LIVE_HOST_PREFLIGHT PASS: source=$ExpectedHead; user=$desktopUser; scripts=$($tracked.Count); approxBytes=$estimated"
if (-not $Apply) { Write-Host 'DRY_RUN_ONLY: no release copied, task registered or Editor launched.'; return }

if ($task) { throw 'Existing Live Host task must be verified/removed explicitly before changing releases.' }
if (Test-Path -LiteralPath $InstallRoot) {
  $unknown=@(Get-ChildItem -LiteralPath $InstallRoot -Force |
    Where-Object Name -notin @('releases','runtime','state'))
  if ($unknown.Count) { throw 'InstallRoot contains unknown data; do not overwrite.' }
}
if (Test-Path -LiteralPath $release) { throw 'Selected release already exists; refuse overwrite.' }
$pending=Join-Path $InstallRoot "releases\$ExpectedHead.incomplete"
if (Test-Path -LiteralPath $pending) { throw 'Prior incomplete release retained for investigation.' }
[void][IO.Directory]::CreateDirectory($pending)
$count=0
$fileProofs=[Collections.Generic.List[object]]::new()
foreach($relative in @($tracked)+@($manifestRelative)) {
  $src=Join-Path $RepoRoot $relative
  $dst=Join-Path $pending $relative
  [void][IO.Directory]::CreateDirectory((Split-Path -Path $dst -Parent))
  Copy-Item -LiteralPath $src -Destination $dst
  $a=(Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
  $b=(Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash
  if($a -cne $b) { throw "Installed file differs: $relative" }
  $fileProofs.Add([ordered]@{path=$relative;sha256=$b.ToLowerInvariant()})
  $count++
}
Move-Item -LiteralPath $pending -Destination $release -ErrorAction Stop
[void][IO.Directory]::CreateDirectory($liveHostRoot)
[void][IO.Directory]::CreateDirectory((Join-Path $InstallRoot 'runtime'))
$record=[ordered]@{
  schema_version=1;source_sha=$ExpectedHead
  desktop_user=$desktopUser;desktop_sid=$sid;install_root=$InstallRoot
  release_root=$release;installed_files=$count
  file_proofs=@($fileProofs)
  # New installations use explicit documented default. Existing immutable
  # f4a0366a sessions are upgraded through Upgrade-YacsLiveHostCodec.ps1.
  video_codec='VP9'
  world_profile_id='latest_verified';world_version=$world.version
  map_package=$world.map_package
  task=$taskName;no_service_changes=$true
  no_runner_changes=$true;placement=$false
  installed_at_utc=[DateTime]::UtcNow.ToString('o')
}
if (Test-Path -LiteralPath $installRecord) { throw 'Existing installation record; retain old state.' }
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $installRecord -Encoding utf8
$pwsh='D:\yacs\tools\powershell-7.6.6-win-x64\pwsh.exe'
if(-not (Test-Path -LiteralPath $pwsh -PathType Leaf)) { throw 'Pinned portable PowerShell unavailable.' }
$action=New-ScheduledTaskAction -Execute $pwsh -Argument $arguments -WorkingDirectory $release
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $desktopUser
$principal=New-ScheduledTaskPrincipal -UserId $desktopUser -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 0 -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -ErrorAction Stop | Out-Null
Write-Host "LIVE_HOST_INSTALLED: $taskName as $desktopUser, limited interactive logon; user must log in for startup."
Write-Host 'Neither UE nor the GitHub Actions service was started/restarted. Native/reboot/browser proof NOT RUN.'
