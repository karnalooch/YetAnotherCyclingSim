#requires -Version 7.4
<#
.SYNOPSIS
  Opt-in immutable VP9 encoder trial upgrade for an idle YACS Live Host.
.DESCRIPTION
  Copies reviewed repo scripts to a NEW exact-SHA release, retains the original
  immutable release and installation metadata, updates ONLY the scheduled
  task's Action (not Principal/Triggers/Settings), and DOES NOT start UE.
  Never runs inside a GitHub Actions job. Dry run is the default.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedHead,
  [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedInstalledHead,
  [ValidateSet('VP9')][string]$VideoCodec='VP9',
  [string]$RepoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path,
  [string]$InstallRoot='D:\yacs\live-host',
  [switch]$Apply
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if (-not $IsWindows -or $env:GITHUB_ACTIONS -eq 'true' -or $env:RUNNER_TRACKING_ID) {
  throw 'An interactive Windows owner, not a runner job, must perform a Live Host upgrade.'
}
$RepoRoot=(Resolve-Path -LiteralPath $RepoRoot).Path
$InstallRoot=[IO.Path]::GetFullPath($InstallRoot)
if ($InstallRoot -ine 'D:\yacs\live-host') { throw 'Unexpected Live Host root.' }
if ($ExpectedHead -ceq $ExpectedInstalledHead) {
  throw 'New immutable release must have a different reviewed source SHA.'
}
if ((& git -C $RepoRoot rev-parse HEAD).Trim() -cne $ExpectedHead -or
    @(& git -C $RepoRoot status --porcelain --untracked-files=no).Count) {
  throw 'Expected exact clean Git HEAD, not modified source.'
}
. (Join-Path $PSScriptRoot 'Assert-YacsLiveTaskPrincipal.ps1')
$stateRoot=Join-Path $InstallRoot 'state'
$installedFile=Join-Path $stateRoot 'installation.json'
$install=Get-Content -LiteralPath $installedFile -Raw | ConvertFrom-Json
if ($install.source_sha -cne $ExpectedInstalledHead -or
    $install.install_root -ine $InstallRoot) {
  throw 'Currently installed release differs from caller-pinned expected old release.'
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$console=(Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
if ($identity.User.Value -cne $install.desktop_sid -or
    $identity.Name -ine $console -or
    (Get-Process -Id $PID -ErrorAction Stop).SessionId -le 0) {
  throw 'Installer must run as the installed interactive console owner.'
}
$task=Get-ScheduledTask -TaskName 'YACS Live Host' -ErrorAction Stop
$principal=Assert-YacsLiveTaskPrincipal -Task $task -ExpectedSid $install.desktop_sid
if ($task.State -cne 'Ready' -or @($task.Actions).Count -ne 1) {
  throw 'An active/unknown Live Host task must not be upgraded.'
}
$hostState=& (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
if ($hostState.status -cne 'IDLE' -or
    @(Get-Process -Name 'UnrealEditor*' -ErrorAction SilentlyContinue).Count -ne 0) {
  throw 'Another Unreal Editor owner/process is still present; refuse codec upgrade.'
}
$bound=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object LocalPort -in @(80,8888,18784))
if (@($bound).Count -ne 0) { throw 'Streaming/MCP listeners are still occupied.' }
if ([IO.DriveInfo]::new('D:\').AvailableFreeSpace -lt 5GB) {
  throw 'D: free space below five GiB reserve.'
}
function Assert-NoReparse([string]$Path) {
  $cursor=[IO.Path]::GetFullPath($Path)
  while ($cursor) {
    if (Test-Path -LiteralPath $cursor) {
      $item=Get-Item -LiteralPath $cursor -Force
      if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Aliased Live Host source or destination refused: $cursor"
      }
    }
    $parent=Split-Path -Path $cursor -Parent
    if ($parent -ceq $cursor) { break }
    $cursor=$parent
  }
}
$oldRelease=Join-Path $InstallRoot "releases\$ExpectedInstalledHead"
$newRelease=Join-Path $InstallRoot "releases\$ExpectedHead"
$incomplete="$newRelease.incomplete"
foreach ($p in @($oldRelease,$newRelease,$incomplete,$installedFile)) {
  Assert-NoReparse $p
}
if (-not (Test-Path -LiteralPath $oldRelease -PathType Container) -or
    (Test-Path -LiteralPath $newRelease) -or
    (Test-Path -LiteralPath $incomplete)) {
  throw 'Expected old immutable release unavailable or new release already exists.'
}
if (@($install.file_proofs).Count -ne [int]$install.installed_files -or
    @($install.file_proofs).Count -lt 50) {
  throw 'Old installed code hash manifest is not complete.'
}
foreach ($proof in @($install.file_proofs)) {
  $rel=[string]$proof.path
  if ($rel -cnotmatch '^(scripts/[A-Za-z0-9_./-]+|worldgen/sa_calobra/pcg365_rejected_sites_review_v1.json)$' -or
      $rel -match '\.\.') { throw 'Invalid old immutable release path.' }
  $file=Join-Path $oldRelease $rel
  if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw 'Missing old installed source.' }
  if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne
      [string]$proof.sha256) { throw "Immutable previous release differs: $rel" }
}
$oldScript=Join-Path $oldRelease 'scripts\live_host\Start-YacsLiveHost.ps1'
$newScript=Join-Path $newRelease 'scripts\live_host\Start-YacsLiveHost.ps1'
$pwsh='D:\yacs\tools\powershell-7.6.6-win-x64\pwsh.exe'
if (-not (Test-Path -LiteralPath $pwsh -PathType Leaf)) { throw 'Pinned PowerShell missing.' }
$oldArgs='-NoLogo -NoProfile -File "'+$oldScript+'" -InstallRoot "'+$InstallRoot+'"'
$newArgs='-NoLogo -NoProfile -File "'+$newScript+'" -InstallRoot "'+$InstallRoot+'"'
$originalAction=$task.Actions[0]
if ($originalAction.Execute -ine $pwsh -or
    $originalAction.WorkingDirectory -ine $oldRelease -or
    $originalAction.Arguments -cne $oldArgs) {
  throw 'Existing task Action differs from the exact known-good corrected action.'
}
$tracked=@(& git -C $RepoRoot ls-files -- scripts)
if ($LASTEXITCODE -ne 0 -or @($tracked).Count -lt 50 -or @($tracked).Count -gt 2500) {
  throw 'Unexpected source closure for new codec profile.'
}
$relFiles=@($tracked)+@('worldgen/sa_calobra/pcg365_rejected_sites_review_v1.json')
$proofs=[Collections.Generic.List[object]]::new()
$total=[long]0
foreach($rel in $relFiles) {
  if($rel -cnotmatch '^(scripts/[A-Za-z0-9_./-]+|worldgen/sa_calobra/pcg365_rejected_sites_review_v1.json)$' -or
    $rel -match '\.\.') { throw "Unsafe new source file path: $rel" }
  $path=Join-Path $RepoRoot $rel
  Assert-NoReparse $path
  $info=Get-Item -LiteralPath $path -Force
  if ($info.PSIsContainer -or $info.Length -gt 8MB) { throw "Unsafe new code input: $rel" }
  $total += $info.Length
  $proofs.Add([ordered]@{
    path=$rel
    sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
  })
}
if ($total -gt 256MB) { throw 'Code-only upgrade exceeds 256 MiB.' }
$manifest=(Get-Content -LiteralPath (Join-Path $RepoRoot 'worldgen/sa_calobra/pcg365_rejected_sites_review_v1.json') -Raw | ConvertFrom-Json)
if ($manifest.source_producer_sha -cne 'd361e7651d16ff424ae4e812c7d8cbe1fe81d662' -or
    @($manifest.markers).Count -ne 5 -or $manifest.placement -ne $false) {
  throw 'Diagnostic authority changed: no codec upgrade.'
}
$preview=[ordered]@{
  status='VP9_CODEC_UPGRADE_PREFLIGHT_PASS'
  current_source_sha=$ExpectedInstalledHead
  next_source_sha=$ExpectedHead
  requested_codec=$VideoCodec
  console_sid=$install.desktop_sid
  task_state=[string]$task.State
  source_files=$relFiles.Count
  source_bytes=$total
  old_release_preserved=$true
  new_editor_started=$false
}
if (-not $Apply) {
  [pscustomobject]$preview | ConvertTo-Json -Depth 8
  Write-Host 'DRY_RUN: No Task Scheduler, Editor, runner or installation file mutated.'
  return
}

# One explicit interactive desktop owner action. Copy/hashes new release before
# changing the task's Action. Never mutate either immutable installed release.
[void][IO.Directory]::CreateDirectory($incomplete)
foreach($proof in @($proofs)) {
  $from=Join-Path $RepoRoot $proof.path
  $to=Join-Path $incomplete $proof.path
  [void][IO.Directory]::CreateDirectory((Split-Path $to -Parent))
  Copy-Item -LiteralPath $from -Destination $to -ErrorAction Stop
  if ((Get-FileHash -LiteralPath $to -Algorithm SHA256).Hash.ToLowerInvariant() -cne
       $proof.sha256) { throw "Code-only release copy differs: $($proof.path)" }
}
Move-Item -LiteralPath $incomplete -Destination $newRelease -ErrorAction Stop
$upgradeToken=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$oldBackup=Join-Path $stateRoot "installation-before-vp9-$upgradeToken.json"
if (Test-Path -LiteralPath $oldBackup) { throw 'Previous receipt already exists.' }
Copy-Item -LiteralPath $installedFile -Destination $oldBackup -ErrorAction Stop
if ((Get-FileHash -LiteralPath $oldBackup -Algorithm SHA256).Hash -cne
    (Get-FileHash -LiteralPath $installedFile -Algorithm SHA256).Hash) {
  throw 'Original installation metadata backup differs.'
}
$updated=$install | ConvertTo-Json -Depth 18 | ConvertFrom-Json
$updated.source_sha=$ExpectedHead
$updated.release_root=$newRelease
$updated.installed_files=$relFiles.Count
$updated.file_proofs=@($proofs)
$updated.installed_at_utc=[DateTime]::UtcNow.ToString('o')
$updated | Add-Member -NotePropertyName 'previous_source_sha' -NotePropertyValue $ExpectedInstalledHead -Force
$updated | Add-Member -NotePropertyName 'video_codec' -NotePropertyValue $VideoCodec -Force
$updated | Add-Member -NotePropertyName 'vp9_trial' -NotePropertyValue $true -Force
$nextRecord=Join-Path $stateRoot "installation-pending-vp9-$upgradeToken.json"
$updated | ConvertTo-Json -Depth 18 | Set-Content -LiteralPath $nextRecord -Encoding utf8
$nextAction=New-ScheduledTaskAction -Execute $pwsh -Argument $newArgs -WorkingDirectory $newRelease

try {
  Set-ScheduledTask -TaskName 'YACS Live Host' -Action $nextAction -ErrorAction Stop | Out-Null
  Move-Item -LiteralPath $nextRecord -Destination $installedFile -Force -ErrorAction Stop
  $observed=Get-ScheduledTask -TaskName 'YACS Live Host' -ErrorAction Stop
  $record=Get-Content -LiteralPath $installedFile -Raw | ConvertFrom-Json
  if ($observed.State -cne 'Ready' -or
    $observed.Actions.Count -ne 1 -or
    $observed.Actions[0].Arguments -cne $newArgs -or
    $record.source_sha -cne $ExpectedHead -or
    $record.video_codec -cne $VideoCodec) {
    throw 'Task or installation readback changed during one-shot upgrade.'
  }
} catch {
  $errorMessage=$_.Exception.Message
  try {
    Set-ScheduledTask -TaskName 'YACS Live Host' -Action $originalAction -ErrorAction Stop | Out-Null
    Copy-Item -LiteralPath $oldBackup -Destination $installedFile -Force -ErrorAction Stop
  } catch {
    throw "UPGRADE_PARTIAL_ROLLBACK_FAILED: $errorMessage; rollback: $($_.Exception.Message). Refuse startup."
  }
  throw "UPGRADE_ROLLED_BACK_NO_START: $errorMessage"
}
[pscustomobject]@{
  status='VP9_IMMUTABLE_RELEASE_INSTALLED_NOT_STARTED'
  source_sha=$ExpectedHead;previous_source_sha=$ExpectedInstalledHead
  requested_video_codec=$VideoCodec;task_state='Ready'
  source_bytes=$total;old_release_unchanged=$true
  editor_started=$false;codec_negotiated_verified=$false
  metadata_backup=$oldBackup
} | ConvertTo-Json -Depth 8
