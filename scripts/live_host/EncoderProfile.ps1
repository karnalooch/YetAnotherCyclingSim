#requires -Version 7.4
<#
.SYNOPSIS
  Pure, offline Pixel Streaming 2 codec profile arguments (Epic UE 5.8).
.DESCRIPTION
  No Unreal process/network/Task Scheduler/filesystem mutation. VP9 CPU encoding
  is an opt-in diagnostic for nvEncodeAPI64.dll 0xC0000409; H264 remains an
  explicit comparison mode, never a silent fallback if VP9 fails.
#>
Set-StrictMode -Version Latest

function Get-YacsLiveEncoderArgs {
  [CmdletBinding()]
  param([Parameter(Mandatory)][string]$VideoCodec)

  # A value must match the *entire* codec token, not merely a prefix.
  # Absolute \A/\z regex anchors reject trailing CR/LF and other invisible
  # suffixes, including values that render as plain "VP9" in error consoles.
  if ($VideoCodec -cnotmatch '\A(?:VP9|H264)\z' -or
      $VideoCodec -cnotin @('VP9','H264')) {
    throw 'Only exact VP9 and H264 tokens are accepted (no whitespace or controls).'
  }
  return @(
    "-PixelStreamingEncoderCodec=$VideoCodec"
    '-PixelStreamingWebRTCMaxFps=30'
  )
}
