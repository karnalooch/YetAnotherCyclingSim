#requires -Version 7.4
<#
.SYNOPSIS
  Revert a stopped VP9 codec trial to the original immutable Live Host release.
.DESCRIPTION
  No UE process/startup, runner configuration, driver, cache, or source map write.
  Restores exact original Task Scheduler Action and retained installation metadata.
  Dry run by default; explicit -Apply only when host is truly idle.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedTrialHead,
  [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedOriginalHead,
  [string]$InstallRoot='D:\yacs\live-host',
  [string]$RepoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path,
  [switch]$Apply
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if (-not $IsWindows -or $env:GITHUB_ACTIONS -eq 'true' -or $env:RUNNER_TRACKING_ID) {
  throw 'Live Host rollback requires the interactive desktop owner.'
}
$InstallRoot=[IO.Path]::GetFullPath($InstallRoot)
$RepoRoot=(Resolve-Path -LiteralPath $RepoRoot).Path
if ($InstallRoot -ine 'D:\yacs\live-host') { throw 'Unexpected Live Host root.' }
. (Join-Path $PSScriptRoot 'Assert-YacsLiveTaskPrincipal.ps1')
$state=Join-Path $InstallRoot 'state'
$recordPath=Join-Path $state 'installation.json'
$trial=Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
if ($trial.source_sha -cne $ExpectedTrialHead -or
    $trial.previous_source_sha -cne $ExpectedOriginalHead -or
    $trial.video_codec -cne 'VP9' -or $trial.vp9_trial -ne $true) {
  throw 'VP9 test identity changed; refuse rollback to wrong release.'
}
$backup=@(Get-ChildItem -LiteralPath $state -File -Filter 'installation-before-vp9-*.json')
if ($backup.Count -ne 1) {
  throw 'Exactly one original metadata backup is required for rollback.'
}
$original=Get-Content -LiteralPath $backup[0].FullName -Raw | ConvertFrom-Json
if ($original.source_sha -cne $ExpectedOriginalHead -or
    $original.desktop_sid -cne $trial.desktop_sid -or
    $original.install_root -ine $InstallRoot) {
  throw 'Original immutable installation metadata differs.'
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$user=[string](Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
if ($identity.User.Value -cne $trial.desktop_sid -or $identity.Name -ine $user -or
    (Get-Process -Id $PID -ErrorAction Stop).SessionId -le 0) {
  throw 'Only the exact interactive Windows owner can rollback.'
}
$task=Get-ScheduledTask -TaskName 'YACS Live Host' -ErrorAction Stop
Assert-YacsLiveTaskPrincipal -Task $task -ExpectedSid $trial.desktop_sid | Out-Null
$hostState=& (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
if ($task.State -cne 'Ready' -or $hostState.status -cne 'IDLE' -or
    @(Get-Process -Name 'UnrealEditor*' -ErrorAction SilentlyContinue).Count -ne 0) {
  throw 'Active/unknown Unreal Host; refuse to interrupt the GPU owner.'
}
if (@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
      Where-Object LocalPort -in @(80,8888,18784)).Count -ne 0) {
  throw 'Original streaming/MCP listeners still owned; no rollback.'
}
$oldRelease=Join-Path $InstallRoot "releases\$ExpectedOriginalHead"
$trialRelease=Join-Path $InstallRoot "releases\$ExpectedTrialHead"
if (-not (Test-Path -LiteralPath $oldRelease -PathType Container) -or
    -not (Test-Path -LiteralPath $trialRelease -PathType Container)) {
  throw 'A source release is missing; preserve files.'
}
foreach ($proof in @($original.file_proofs)) {
  $rel=[string]$proof.path
  if($rel -cnotmatch '^(scripts/[A-Za-z0-9_./-]+|worldgen/sa_calobra/pcg365_rejected_sites_review_v1.json)$' -or
    $rel -match '\.\.') { throw 'Unsafe old source proof path.' }
  $path=Join-Path $oldRelease $rel
  if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
    (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne
      $proof.sha256) { throw 'Original immutable source bytes drifted.' }
}
$exe='D:\yacs\tools\powershell-7.6.6-win-x64\pwsh.exe'
$oldScript=Join-Path $oldRelease 'scripts/live_host/Start-YacsLiveHost.ps1'
$trialScript=Join-Path $trialRelease 'scripts/live_host/Start-YacsLiveHost.ps1'
$oldArgs='-NoLogo -NoProfile -File "'+$oldScript+'" -InstallRoot "'+$InstallRoot+'"'
$trialArgs='-NoLogo -NoProfile -File "'+$trialScript+'" -InstallRoot "'+$InstallRoot+'"'
if (@($task.Actions).Count -ne 1 -or
    $task.Actions[0].Execute -ine $exe -or
    $task.Actions[0].WorkingDirectory -ine $trialRelease -or
    $task.Actions[0].Arguments -cne $trialArgs) {
  throw 'Live Host task Action no longer matches known trial identity.'
}
$preview=[ordered]@{
  status='ROLLBACK_TO_ORIGINAL_READY_FOR_OWNER_CONFIRMATION'
  current_source_sha=$ExpectedTrialHead
  original_source_sha=$ExpectedOriginalHead
  original_video_codec='H264'
  trial_release_preserved=$true
  running_editor_stopped=$false
}
if (-not $Apply) {
  [pscustomobject]$preview | ConvertTo-Json -Depth 8
  Write-Host 'DRY_RUN_ONLY: No Task Scheduler or installation metadata changes.'
  return
}
$stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$trialBackup=Join-Path $state "installation-before-rollback-$stamp.json"
if (Test-Path -LiteralPath $trialBackup) { throw 'Prior rollback receipt exists.' }
Copy-Item -LiteralPath $recordPath -Destination $trialBackup -ErrorAction Stop
$oldTaskAction=New-ScheduledTaskAction -Execute $exe -Argument $oldArgs -WorkingDirectory $oldRelease
try {
  Set-ScheduledTask -TaskName 'YACS Live Host' -Action $oldTaskAction -ErrorAction Stop | Out-Null
  Copy-Item -LiteralPath $backup[0].FullName -Destination $recordPath -Force -ErrorAction Stop
  $now=Get-ScheduledTask -TaskName 'YACS Live Host' -ErrorAction Stop
  $restored=Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
  if ($now.State -cne 'Ready' -or
      $now.Actions[0].Arguments -cne $oldArgs -or
      $restored.source_sha -cne $ExpectedOriginalHead) {
    throw 'Post-rollback task and metadata did not match original.'
  }
} catch {
  $failure=$_.Exception.Message
  try {
    Set-ScheduledTask -TaskName 'YACS Live Host' -Action $task.Actions[0] -ErrorAction Stop | Out-Null
    Copy-Item -LiteralPath $trialBackup -Destination $recordPath -Force -ErrorAction Stop
  } catch {
    throw "PARTIAL_ROLLBACK_UNRECOVERED: $failure; $($_.Exception.Message). Do not start UE."
  }
  throw "ROLLBACK_CANCELLED_TRIAL_RESTORED: $failure"
}
[pscustomobject]@{
  status='H264_ORIGINAL_TASK_RESTORED_NO_START'
  source_sha=$ExpectedOriginalHead
  trial_release_preserved=$true
  original_media_failure_not_fixed=$true
  editor_started=$false
  trial_backup=$trialBackup
} | ConvertTo-Json -Depth 8
