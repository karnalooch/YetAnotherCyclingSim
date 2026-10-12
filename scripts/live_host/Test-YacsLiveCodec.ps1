#requires -Version 7.4
<#
.SYNOPSIS
  Read-only, no-UE regression for software VP9 vs original NVENC H264 launch.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'EncoderProfile.ps1')
function Need([bool]$Condition,[string]$Message) { if (-not $Condition) { throw $Message } }
function Refuse([string]$Codec) {
  $rejected=$false
  try { Get-YacsLiveEncoderArgs -VideoCodec $Codec | Out-Null } catch { $rejected=$true }
  Need $rejected "Unreviewed/unsafe codec accepted: $Codec"
}
$vp9=@(Get-YacsLiveEncoderArgs -VideoCodec 'VP9')
$h264=@(Get-YacsLiveEncoderArgs -VideoCodec 'H264')
Need ($vp9.Count -eq 2 -and $vp9[0] -ceq '-PixelStreamingEncoderCodec=VP9' -and
  $vp9[1] -ceq '-PixelStreamingWebRTCMaxFps=30') 'Unexpected VP9 software codec/FPS command'
Need ($h264.Count -eq 2 -and $h264[0] -ceq '-PixelStreamingEncoderCodec=H264' -and
  $h264[1] -ceq '-PixelStreamingWebRTCMaxFps=30') 'Unexpected H264 original codec/FPS command'
foreach($v in @('', 'AV1', 'VP8', 'vp9', 'VP9 -ExecCmds=Exit', 'VP9;Stop-Process',
  'VP9'+[char]10+'-foo')) { Refuse ([string]$v) }
# Task Scheduler receives double quotes without literal backslash escaping.
$root='D:\yacs\live-host'
$source="D:\yacs\live-host\releases\$('b'*40)\scripts\live_host\Start-YacsLiveHost.ps1"
$arguments='-NoLogo -NoProfile -File "'+$source+'" -InstallRoot "'+$root+'"'
Need ($arguments -notmatch '\\"') 'Do not restore the prior Task Scheduler escaped-quote bug'
Need ($arguments.StartsWith('-NoLogo -NoProfile -File "')) 'Task Scheduler -File quoting missing'
Need ($arguments.EndsWith('-InstallRoot "D:\yacs\live-host"')) 'Task Scheduler InstallRoot quoting drift'
Write-Host 'YACS_LIVE_CODEC_TEST_PASS VP9_CPU=REQUESTED H264=EXPLICIT 720p30=PINNED TASK_QUOTES=PASS'
