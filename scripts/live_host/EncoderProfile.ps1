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

  if ($VideoCodec -cnotin @('VP9','H264')) {
    throw 'Only explicitly admitted VP9 and original H264 codecs are supported.'
  }
  return @(
    "-PixelStreamingEncoderCodec=$VideoCodec"
    '-PixelStreamingWebRTCMaxFps=30'
  )
}
