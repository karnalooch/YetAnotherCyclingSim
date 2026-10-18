#requires -Version 7.4
<#
.SYNOPSIS
    Open the isolated Lesson05 map, or explicitly import from saved Lesson04 with a fixed-rate native D3D12 NVENC stream.
.DESCRIPTION
    Starts one editor only on an idle host. Never kills an editor, saves a map,
    changes global configuration or manages other applications. -ImportLesson05 runs the bounded import.
    The local generated map must already exist. Use -WhatIf to inspect arguments.
#>
[CmdletBinding(SupportsShouldProcess)]
param([switch] $ImportLesson05, [switch] $RecoverBaseline, [switch] $RepairContext, [switch] $ScreeCloseup)

if ($ScreeCloseup -and $ImportLesson05) { throw 'Close-up only opens the saved map; it cannot import.' }
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'The native review stream requires Windows.' }
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$Project = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject'
$Map = '/Game/Generated/YACS/Lesson04Repair_20261018/L_SaCalobra_Lesson04_Test'
if ($RepairContext -and (-not $ImportLesson05 -or $RecoverBaseline)) { throw 'Context repair requires import and excludes baseline recovery.' }
if ($RepairContext) { $env:YACS_LESSON05_CONTEXT_REPAIR='1' } else { $env:YACS_LESSON05_CONTEXT_REPAIR='0' }
if ($RecoverBaseline -and -not $ImportLesson05) { throw 'Recovery requires explicit import.' }
if ($RecoverBaseline) { $env:YACS_LESSON05_RECOVER_BASELINE='1' } else { $env:YACS_LESSON05_RECOVER_BASELINE='0' }
if (-not $ImportLesson05 -or $RecoverBaseline -or $RepairContext) { $Map = '/Game/Generated/YACS/Lesson05_20261018/L_SaCalobra_Lesson05' }
$MapFile = Join-Path $RepoRoot ('Content/' + $Map.Substring(6) + '.umap')
if (-not (Test-Path -LiteralPath $MapFile)) { throw "Saved repaired map is missing: $MapFile" }
. (Join-Path $RepoRoot 'scripts/ci/Resolve-YacsUnrealEngine.ps1')
$Engine = Resolve-YacsUnrealEngine -ProjectPath $Project
if (-not $Engine -or $Engine.Version -ne '5.8.2-56702186') {
    throw 'Revalidate this workaround for an engine other than UE 5.8.2 CL56702186.'
}
$Log = Join-Path $RepoRoot ('Saved/Logs/lesson05-stream-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
$Arguments = @(
    ('"' + $Project + '"'), $Map,
    '-EnablePlugins=PixelStreaming2,ToolsetRegistry',
    '-DisablePlugins=Wingman,AndroidFileServer',
    '-NoLiveCoding', '-NoP4', '-Unattended', '-RenderOffscreen',
    '-ResX=1920', '-ResY=1080', '-ExecCmds="t.MaxFPS 30"',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorSource=LevelEditorViewport',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorStartOnLaunch=True',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorUseRemoteSignallingServer=False',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:ConnectionURL=ws://127.0.0.1:8888',
    '-EditorPixelStreamingRes=1920x1080',
    # CUDA interop failed with NVENC 20 / CUDA 700 when a second viewer joined.
    # Fixed local bitrate reduces rate reconfiguration; bounded runtime proof is required.
    '-AVCodecs.NvEnc.D3D12UsesCUDA=false',
    '-PixelStreamingEncoderCodec=H264', '-PixelStreamingWebRTCMaxFps=30',
    '-PixelStreamingWebRTCMinBitrate=12000000',
    '-PixelStreamingWebRTCStartBitrate=12000000', '-PixelStreamingWebRTCMaxBitrate=12000000',
    '-PixelStreamingEncoderMinQuality=60', '-PixelStreamingEncoderTargetBitrate=12000000',
    '-PixelStreamingEncoderRateControl=CBR', '-NoSound', '-NoVSync',
    ('-AbsLog="' + $Log + '"')
)
if ($ImportLesson05) {
    $Arguments += '-ExecutePythonScript="' + (Join-Path $PSScriptRoot 'bootstrap_lesson05_import.py') + '"'
}
if ($ScreeCloseup) {
    $Arguments += '-ExecutePythonScript="' + (Join-Path $PSScriptRoot 'show_lesson05_scree.py') + '"'
}
if (-not $PSCmdlet.ShouldProcess($Map, 'Start isolated Lesson05 H264/D3D12 editor stream')) {
    [ordered]@{ map = $Map; arguments = $Arguments; started = $false } | ConvertTo-Json
    return
}
$HostState = & (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
if ($HostState.status -ne 'IDLE') { throw "Unreal host is occupied: $($HostState.status). Leave its session running." }
$Listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object LocalPort -in @(80, 8888))
if ($Listeners.Count) { throw 'Stream ports 80 or 8888 are already occupied.' }
New-Item -ItemType Directory -Path (Split-Path $Log -Parent) -Force | Out-Null
$Process = Start-Process -FilePath $Engine.UnrealEditorPath -ArgumentList $Arguments -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru
[ordered]@{
    pid = $Process.Id
    map = $Map
    viewer_url = 'http://127.0.0.1/?AutoConnect=true&AutoPlayVideo=true'
    log = $Log
    status = 'STARTED_NOT_YET_VERIFIED'
    codec = 'H264'
    d3d12_uses_cuda = $false
    target_bitrate = 12000000
    scree_closeup = [bool]$ScreeCloseup
} | ConvertTo-Json
