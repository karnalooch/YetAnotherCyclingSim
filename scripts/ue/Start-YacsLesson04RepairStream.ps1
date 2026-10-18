#requires -Version 7.4
<#
.SYNOPSIS
    Reopen the saved isolated Lesson04 map with Epic's CUDA NVENC workaround.
.DESCRIPTION
    Starts one editor only on an idle host. Never kills an editor, saves a map,
    imports terrain, changes global configuration or manages other applications.
    The local generated map must already exist. Use -WhatIf to inspect arguments.
#>
[CmdletBinding(SupportsShouldProcess)]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'The native review stream requires Windows.' }
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$Project = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject'
$Map = '/Game/Generated/YACS/Lesson04Repair_20261018/L_SaCalobra_Lesson04_Test'
$MapFile = Join-Path $RepoRoot ('Content/' + $Map.Substring(6) + '.umap')
if (-not (Test-Path -LiteralPath $MapFile)) { throw "Saved repaired map is missing: $MapFile" }
. (Join-Path $RepoRoot 'scripts/ci/Resolve-YacsUnrealEngine.ps1')
$Engine = Resolve-YacsUnrealEngine -ProjectPath $Project
if (-not $Engine -or $Engine.Version -ne '5.8.2-56702186') {
    throw 'Revalidate this workaround for an engine other than UE 5.8.2 CL56702186.'
}
$Log = Join-Path $RepoRoot ('Saved/Logs/lesson04-repair-stream-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
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
    # Epic's supported workaround for the NVIDIA D3D12 H264 reconfigure leak.
    # Retains NVENC hardware H264; verify real frames, not merely flat memory.
    '-AVCodecs.NvEnc.D3D12UsesCUDA=true',
    '-PixelStreamingEncoderCodec=H264', '-PixelStreamingWebRTCMaxFps=30',
    '-PixelStreamingWebRTCStartBitrate=12000000', '-PixelStreamingWebRTCMaxBitrate=25000000',
    '-PixelStreamingEncoderMinQuality=60', '-PixelStreamingEncoderTargetBitrate=-1',
    '-PixelStreamingEncoderRateControl=CBR', '-NoSound', '-NoVSync',
    ('-AbsLog="' + $Log + '"')
)
if (-not $PSCmdlet.ShouldProcess($Map, 'Start isolated Lesson04 H264/CUDA editor stream')) {
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
    d3d12_uses_cuda = $true
} | ConvertTo-Json
