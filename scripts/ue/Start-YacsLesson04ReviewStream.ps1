#requires -Version 7.4
<#
.SYNOPSIS
    Launch Unreal Editor 5.8 with Pixel Streaming 2 for Lesson 04 review.
#>
[CmdletBinding()]
param(
    [ValidateSet('H264', 'VP9')]
    [string]$Codec = 'H264',
    [string]$Resolution = '1920x1080',
    [int]$Fps = 30,
    [int]$StartBitrate = 12000000,
    [int]$MaxBitrate = 25000000,
    [int]$MinQuality = 60,
    [string]$RateControl = 'CBR'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Editor = 'D:/yacs/engine/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe'
$Project = 'D:/yacs/project/YetAnotherCyclingSim.uproject'
$Map = '/Game/Generated/YACS/Review/L_SaCalobra_Lesson04_Review'
$Script = 'D:/yacs/project/scripts/ue/bootstrap_lesson04_review_stream.py'
$Log = 'D:/yacs/project/Saved/Logs/lesson04_pixelstreaming.log'

$arguments = @(
    ('"' + $Project + '"'),
    $Map,
    '-EnablePlugins=PixelStreaming2,ToolsetRegistry',
    '-DisablePlugins=Wingman,AndroidFileServer',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorSource=LevelEditorViewport',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorStartOnLaunch=True',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorUseRemoteSignallingServer=False',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:ConnectionURL=ws://127.0.0.1:8888',
    "-EditorPixelStreamingRes=$Resolution",
    "-PixelStreamingEncoderCodec=$Codec",
    "-PixelStreamingWebRTCMaxFps=$Fps",
    "-PixelStreamingWebRTCStartBitrate=$StartBitrate",
    "-PixelStreamingWebRTCMaxBitrate=$MaxBitrate",
    "-PixelStreamingEncoderMinQuality=$MinQuality",
    '-PixelStreamingEncoderTargetBitrate=-1',
    "-PixelStreamingEncoderRateControl=$RateControl",
    '-RenderOffscreen',
    '-NoP4',
    '-NoSplash',
    '-NoSound',
    '-NoLiveCoding',
    '-NoVSync',
    "-ExecCmds=`"t.MaxFPS $Fps`"",
    ('-ExecutePythonScript="' + $Script + '"'),
    ('-AbsLog="' + $Log + '"')
)

$proc = Start-Process -FilePath $Editor -ArgumentList $arguments -WorkingDirectory 'D:/yacs/project' -PassThru
[ordered]@{
    PID = $proc.Id
    ProcessName = $proc.ProcessName
    StartTimeUtc = $proc.StartTime.ToUniversalTime().ToString('o')
    Codec = $Codec
    Resolution = $Resolution
    Fps = $Fps
    Bitrates = "$StartBitrate - $MaxBitrate"
    Log = $Log
} | ConvertTo-Json
