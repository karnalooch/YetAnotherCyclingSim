#requires -Version 7.4
<#
.SYNOPSIS
  Observe an installed YACS Live Host without touching its Editor, task or files.
.DESCRIPTION
  Pass -RequireLive only for independent native owner proof after the installing
  GitHub Actions job has exited. Historical browser frames and HTTP 200 alone
  never prove current live-editor ownership.
#>
[CmdletBinding()]
param(
  [string]$InstallRoot = 'D:\yacs\live-host',
  [switch]$RequireLive
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Convert-YacsLiveUtc.ps1')
$InstallRoot=[IO.Path]::GetFullPath($InstallRoot)
if ($InstallRoot -ine 'D:\yacs\live-host') { throw 'Unexpected installation root.' }
function Check([bool]$Ok,[string]$Message) { if (-not $Ok) { throw $Message } }
$task=Get-ScheduledTask -TaskName 'YACS Live Host' -ErrorAction Stop
$installPath=Join-Path $InstallRoot 'state/installation.json'
$livePath=Join-Path $InstallRoot 'state/current-session.json'
Check (Test-Path -LiteralPath $installPath -PathType Leaf) 'No installed Live Host metadata'
$install=Get-Content -LiteralPath $installPath -Raw | ConvertFrom-Json
Check ($install.source_sha -cmatch '^[a-f0-9]{40}$') 'Invalid installed source SHA'
$now=[DateTime]::UtcNow
$requestedCodec=if($null -ne $install.PSObject.Properties['video_codec']) {
  [string]$install.video_codec
} else { 'LEGACY_DEFAULT_NOT_PINNED' }
if($requestedCodec -cnotin @('H264','VP9','LEGACY_DEFAULT_NOT_PINNED')) {
  throw 'Unknown pinned Live Host encoder profile.'
}
$worldProfile=if($null -ne $install.PSObject.Properties['world_profile_id']) {
  [string]$install.world_profile_id
} else { 'DIAGNOSTIC_LEGACY_NOT_LATEST' }
$result=[ordered]@{
  schema_version=1;status='INSTALLED_UNVERIFIED';task='YACS Live Host'
  task_state=[string]$task.State;source_sha=$install.source_sha
  desktop_sid=$install.desktop_sid;editor_pid=$null;session=$null
  live_editor=$false;post_job_alive=$false;browser_frames_received=$false
  viewer_url='http://127.0.0.1/';placement=$false;performance_pass=$false
  heartbeat_age_seconds=$null;editor_start_delta_ms=$null
  editor_process_identity_verified=$false;heartbeat_fresh=$false
  requested_video_codec=$requestedCodec;negotiated_video_codec_verified=$false
  world_profile_id=$worldProfile;world_native_verified=$false
  map_package=$null;material_binding_count=0;lighting_observed=$null
  global_lighting_visual_pass=$false
}
if (Test-Path -LiteralPath $livePath -PathType Leaf) {
  $active=Get-Content -LiteralPath $livePath -Raw | ConvertFrom-Json
  Check ($active.session -cmatch '^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}$' -and
    $active.source_sha -ceq $install.source_sha -and
    $active.desktop_sid -ceq $install.desktop_sid -and
    $active.placement -eq $false -and
    $active.editor_pid -is [long] -and $active.editor_pid -gt 0) 'Live Host active session identity differs'
  $result.editor_pid=[int]$active.editor_pid
  $result.session=[string]$active.session
  $folder=Join-Path $InstallRoot "runtime/sessions/$($active.session)"
  $statusFile=Join-Path $folder 'host-status.json'
  if (Test-Path -LiteralPath $statusFile -PathType Leaf) {
    $receipt=Get-Content -LiteralPath $statusFile -Raw | ConvertFrom-Json
    $fresh=$false
    try {
      # ConvertFrom-Json has already parsed ISO8601 into a typed DateTime
      # on PowerShell 7. Never cast this object back to localized [string].
      $heartbeatUtc=ConvertTo-YacsLiveUtc -Value $receipt.last_seen_utc
      $delta=($now - $heartbeatUtc).TotalSeconds
      $result.heartbeat_age_seconds=[Math]::Round($delta,3)
      $fresh=$delta -ge -4 -and $delta -le 35
    } catch {
      $fresh=$false
    }
    $result.heartbeat_fresh=$fresh
    $process=Get-Process -Id $active.editor_pid -ErrorAction SilentlyContinue
    $alive=$false
    if ($process -and -not $process.HasExited) {
      try {
        $startedUtc=ConvertTo-YacsLiveUtc -Value $active.editor_started_utc
        $observedUtc=$process.StartTime.ToUniversalTime()
        $result.editor_start_delta_ms=[Math]::Round(
          ($observedUtc-$startedUtc).TotalMilliseconds,3)
        $sameProcess=Test-YacsLiveStartIdentity -ExpectedUtc $active.editor_started_utc -ObservedStart $process.StartTime
        $alive=$sameProcess -and
          $process.Path -ieq 'D:\yacs\engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
      } catch { $alive=$false }
    }
    $result.editor_process_identity_verified=$alive
    $startReceiptMatching=$false
    try {
      $activeUtc=ConvertTo-YacsLiveUtc -Value $active.editor_started_utc
      $receiptUtc=ConvertTo-YacsLiveUtc -Value $receipt.editor_started_utc
      $startReceiptMatching=[Math]::Abs(($activeUtc-$receiptUtc).TotalMilliseconds) -le 1
    } catch { $startReceiptMatching=$false }
    $requestedMatches=$true
    if ($requestedCodec -cne 'LEGACY_DEFAULT_NOT_PINNED') {
      $requestedMatches=($null -ne $receipt.PSObject.Properties['requested_video_codec']) -and
        ([string]$receipt.requested_video_codec -ceq $requestedCodec)
    }
    $worldMatches=($worldProfile -ceq 'latest_verified' -and
      $active.world_profile_id -ceq 'latest_verified' -and
      $receipt.world_profile_id -ceq 'latest_verified' -and
      $active.map_package -ceq '/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/L_RoadSurface' -and
      $receipt.map_package -ceq $active.map_package -and
      $receipt.world_native_verified -eq $true -and
      $receipt.material_binding_count -eq 186 -and
      $receipt.global_lighting_visual_pass -eq $false)
    if ($worldMatches) {
      $result.world_native_verified=$true
      $result.map_package=[string]$active.map_package
      $result.material_binding_count=[int]$receipt.material_binding_count
      $result.lighting_observed=$receipt.lighting_observed
    }
    $matching=($worldMatches -and $requestedMatches -and
      $receipt.session -ceq $active.session -and
      $receipt.source_sha -ceq $active.source_sha -and
      $receipt.editor_pid -eq $active.editor_pid -and
      $startReceiptMatching -and
      $receipt.desktop_sid -ceq $active.desktop_sid -and
      $receipt.placement -eq $false -and
      $receipt.map_saved -eq $false)
    $result.live_editor=$alive -and $fresh -and $matching -and $task.State -eq 'Running'
    if ($result.live_editor) {
      $listeners=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object LocalPort -in @(80,8888))
      $hasPorts=(@($listeners.LocalPort | Select-Object -Unique).Count -eq 2)
      $result.browser_frames_received=$hasPorts -and
        $receipt.browser_frames_received -eq $true -and
        $receipt.owner_handoff -eq $true
      $result.status=if($result.browser_frames_received) {
        'LIVE_RECEIVER_PROVEN_CURRENT_PROCESS'
      } else {
        'EDITOR_ALIVE_VIDEO_UNVERIFIED'
      }
    } else {
      $result.status='STALE_OR_DEAD_NOT_LIVE'
    }
  }
}
# RequireLive exists for a *later, separate Actions job*. The first install
# job must not emit a fake post-job persistence claim.
if ($RequireLive) {
  Check ($result.live_editor -eq $true -and $result.browser_frames_received -eq $true) 'Post-job process, new heartbeat or live-frame verification failed'
  $result.post_job_alive=$true
  $result.status='LIVE_VIDEO_VERIFIED'
}
[pscustomobject]$result | ConvertTo-Json -Depth 8
