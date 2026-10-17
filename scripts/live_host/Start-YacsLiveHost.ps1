#requires -Version 7.4
<#
.SYNOPSIS
  Interactive per-user scheduled-task owner of one persistent YACS Unreal Editor.
.DESCRIPTION
  This is NOT a GitHub runner job. It remains running for the whole Editor
  lifetime after AtLogOn, and never automatically restarts a crashed Editor.
  No Save/SaveAll, firewall, service changes, public tunnel or arbitrary scripts.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$InstallRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'YACS Live Host requires an interactive Windows desktop.' }
if ($env:GITHUB_ACTIONS -eq 'true' -or $env:RUNNER_TRACKING_ID) {
  throw 'Live Host may not be launched inside an Actions runner job.'
}
$InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
if ($InstallRoot -ine 'D:\yacs\live-host') { throw 'Unexpected Live Host installation root.' }
$stateRoot=Join-Path $InstallRoot 'state'
$install=Get-Content -LiteralPath (Join-Path $stateRoot 'installation.json') -Raw | ConvertFrom-Json
$sha=[string]$install.source_sha
if ($sha -cnotmatch '^[a-f0-9]{40}$') { throw 'Missing exact installed source SHA.' }
# The encoder is chosen by the *desktop Task owner's* authenticated install
# record, not by browser PreferredCodec or a GitHub Actions process.
$videoCodec=if ($null -ne $install.PSObject.Properties['video_codec']) { [string]$install.video_codec } else { 'H264' }
if ($videoCodec -cnotin @('H264','VP9')) { throw 'Unreviewed Pixel Streaming 2 codec; refuse auto fallback.' }
# An old installation without an explicit world target MUST NOT show stale P3.
if ($null -eq $install.PSObject.Properties['world_profile_id'] -or
    $install.world_profile_id -cne 'latest_verified') {
  throw 'LATEST_VERIFIED_WORLD_BLOCKED: update the owner installation before starting UE; no historical-map fallback.'
}
$release=Join-Path $InstallRoot "releases\$sha"
$codecHelper=Join-Path $release 'scripts/live_host/EncoderProfile.ps1'
if (-not (Test-Path -LiteralPath $codecHelper -PathType Leaf)) { throw 'Expected reviewed encoder helper missing.' }
. $codecHelper
$encoderArgs=@(Get-YacsLiveEncoderArgs -VideoCodec $videoCodec)
if ($encoderArgs.Count -ne 2) { throw 'Expected exact codec and FPS flags.' }
$root=Join-Path $InstallRoot 'runtime'
if (-not (Test-Path -LiteralPath (Join-Path $release 'scripts/live_host/bootstrap.py') -PathType Leaf)) {
  throw 'Pinned Python bootstrap missing from independent release.'
}
$principal=[Security.Principal.WindowsIdentity]::GetCurrent()
if ($principal.User.Value -cne $install.desktop_sid) { throw 'Live Host is running under wrong Windows identity.' }
$proc=Get-Process -Id $PID -ErrorAction Stop
if ($proc.SessionId -le 0) { throw 'Live Host must start inside interactive desktop session.' }
$consoleUser=(Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
if (-not $consoleUser -or $consoleUser -ine $principal.Name) { throw 'Active console login is not the expected owner.' }

# Read-only source-backed latest-world selection. Missing/dirty inputs STOP;
# never fall back to the prior red-site P0-P4 diagnostic map.
$world=& (Join-Path $release 'scripts/live_host/Resolve-YacsLiveWorld.ps1') -SourceRoot $release
if ($world.status -cne 'LATEST_VERIFIED_WORLD_PREFLIGHT_PASS' -or
    $world.fallback_used -ne $false -or $world.validated_packages -ne 5) {
  throw 'Latest saved road map is not authenticated.'
}
$stage=[string]$world.project_root
$project=[string]$world.project_file
$map=[string]$world.map_file
$mapPackage=[string]$world.map_package
$expectedMapSha=[string]$world.map_sha256
if ((Get-FileHash -LiteralPath $map -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expectedMapSha) {
  throw 'Latest-world map changed after preflight; refuse old map fallback.'
}
$hostScript=Join-Path $release 'scripts/runner/Get-YacsUnrealHostState.ps1'
$before=& $hostScript
if ($before.status -cne 'IDLE') { throw "Unreal host already occupied: $($before.status)" }
if ([IO.DriveInfo]::new('D:\').AvailableFreeSpace -lt 5GB) { throw 'Five GiB reserve not met.' }
$busy=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object LocalPort -in @(80,8000,8888,18784))
if ($busy.Count) { throw 'Streaming/MCP network ports already have an owner.' }
$engine='D:\yacs\engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
$plugin='D:\yacs\engine\UE_5.8\Engine\Plugins\Media\PixelStreaming2\PixelStreaming2.uplugin'
if (-not (Test-Path -LiteralPath $engine -PathType Leaf)) { throw 'Expected UE5.8 engine unavailable.' }
if ((Get-FileHash -LiteralPath $plugin -Algorithm SHA256).Hash.ToLowerInvariant() -cne
    '609e80122117d62b6affba640ec2d10c5168a41eee16c8d9768ca145abd59ea6') {
  throw 'Pixel Streaming 2 plugin identity drift.'
}

$session=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,12)
$sessionRoot=Join-Path $root "sessions\$session"
if (Test-Path -LiteralPath $sessionRoot) { throw 'Generated session already exists.' }
[void][IO.Directory]::CreateDirectory($sessionRoot)
$source=Join-Path $release 'scripts/live_host/bootstrap.py'
$viewer='http://127.0.0.1/'
$editor=$null
$status='STARTING'
$browserProved=$false
$ownerStart=$null
$worldReady=$false
$verifiedBindings=0
$lightingObserved=$null

function Save-Status([string]$CurrentStatus) {
  $heartbeat=[ordered]@{
    schema_version=1;status=$CurrentStatus;session=$session;source_sha=$sha
    editor_pid=if ($editor) {$editor.Id} else {$null}
    editor_started_utc=$ownerStart;desktop_sid=$principal.User.Value
    live_host_pid=$PID
    owner_handoff=$browserProved
    browser_frames_received=$browserProved
    map_saved=$false;terrain_modified=$false;placement=$false
    qualified_assets=@();performance_pass=$false
    requested_video_codec=$videoCodec
    world_profile_id='latest_verified';map_package=$mapPackage
    world_native_verified=$worldReady;material_binding_count=$verifiedBindings
    lighting_observed=$lightingObserved;global_lighting_visual_pass=$false
    last_seen_utc=[DateTime]::UtcNow.ToString('o')
  }
  $tmp=Join-Path $sessionRoot 'host-status.tmp'
  $dst=Join-Path $sessionRoot 'host-status.json'
  $heartbeat | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $tmp -Encoding utf8
  Move-Item -LiteralPath $tmp -Destination $dst -Force
}
try {
  $args=@(
    ('"' + $project + '"'),
    $mapPackage,
    # Owner-authorized #365 PCGEx authoring through Epic's local MCP server.
    # Graphs consume the accepted world; the original map remains protected.
    '-EnablePlugins=PixelStreaming2,PCGExtendedToolkit,PCGExAssistant,PCGToolset,EditorToolset,ModelContextProtocol',
    '-DisablePlugins=Wingman,AndroidFileServer',
    '-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]:bAutoStartServer=True',
    '-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]:ServerPortNumber=8000',
    '-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]:ServerUrlPath=/mcp',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorSource=LevelEditorViewport',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorStartOnLaunch=True',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorUseRemoteSignallingServer=False',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:ConnectionURL=ws://127.0.0.1:8888',
    '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
    '-ini:EditorPerProjectUserSettings:[/Script/UnrealEd.EditorLoadingSavingSettings]:bAutoSaveEnable=False',
    '-EditorPixelStreamingRes=1280x720','-RenderOffscreen',
    '-NoP4','-NoSplash','-NoSound','-NoLiveCoding','-NoVSync',
    '-ExecCmds="t.MaxFPS 30"'
  ) + $encoderArgs + @(
    ('-ExecutePythonScript="' + $source + '"'),
    ('-AbsLog="' + (Join-Path $sessionRoot 'editor.log') + '"')
  )
  $oldEnv=@{}
  foreach($key in @('YACS_LIVE_WORLD_PROFILE','YACS_LIVE_CODEC','PYTHONHOME','PYTHONPATH','YACS_LIVE_RELEASE','YACS_LIVE_SESSION_ID','YACS_LIVE_SOURCE_SHA','YACS_LIVE_ROOT')) {
    $oldEnv[$key]=[Environment]::GetEnvironmentVariable($key,'Process')
  }
  try {
    Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    $env:YACS_LIVE_RELEASE=$release
    $env:YACS_LIVE_SESSION_ID=$session
    $env:YACS_LIVE_SOURCE_SHA=$sha
    $env:YACS_LIVE_CODEC=$videoCodec
    $env:YACS_LIVE_WORLD_PROFILE='latest_verified'
    $env:YACS_LIVE_ROOT=$root
    $editor=Start-Process -FilePath $engine -ArgumentList $args -WorkingDirectory $stage -PassThru
  } finally {
    foreach($key in $oldEnv.Keys) { [Environment]::SetEnvironmentVariable($key,$oldEnv[$key],'Process') }
  }
  $ownerStart=$editor.StartTime.ToUniversalTime().ToString('o')
  $active=[ordered]@{
    schema_version=1;session=$session;source_sha=$sha
    editor_pid=$editor.Id;editor_started_utc=$ownerStart
    desktop_sid=$principal.User.Value;live_host_pid=$PID
    status='STARTING_NOT_ADMITTED';map_saved=$false;placement=$false
    requested_video_codec=$videoCodec
    world_profile_id='latest_verified';map_package=$mapPackage
  }
  $active | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $stateRoot 'current-session.json') -Encoding utf8
  $deadline=[DateTime]::UtcNow.AddMinutes(4)
  $readback=Join-Path $sessionRoot 'live-scene-ready.json'
  while ([DateTime]::UtcNow -lt $deadline) {
    $editor.Refresh()
    if ($editor.HasExited) { throw "Owned Unreal Editor exited during startup: $($editor.ExitCode)" }
    $errorFile=Join-Path $sessionRoot 'live-start-failed.json'
    if (Test-Path -LiteralPath $errorFile) {
      throw "Owned Unreal bootstrap refused scene: $(Get-Content -LiteralPath $errorFile -Raw)"
    }
    if (Test-Path -LiteralPath $readback) {
      $ready=Get-Content -LiteralPath $readback -Raw | ConvertFrom-Json
      if ($ready.status -cne 'LIVE_SCENE_AND_COMMAND_BRIDGE_READY' -or
        $ready.code_sha -cne $sha -or $ready.editor_pid -ne $editor.Id -or
        $ready.world_profile_id -cne 'latest_verified' -or
        $ready.world_package -cne $mapPackage -or
        $ready.road_native_actor_count -ne 559 -or
        $ready.material_binding_count -ne 186 -or
        $ready.map_saved -ne $false -or
        $ready.placement -ne $false -or
        $ready.requested_video_codec -cne $videoCodec) { throw 'Latest road scene/bridge readback differs.' }
      $worldReady=$true
      $verifiedBindings=186
      $lightingObserved=$ready.lighting
      break
    }
    # Do not write into the fresh session until Unreal's Python bootstrap
    # has authenticated the sole initial editor.log.
    Start-Sleep -Seconds 2
  }
  if (-not (Test-Path -LiteralPath $readback)) { throw 'No native scene within 240s.' }
  $listeners=@(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -in @(80,8888))
  if (@($listeners.LocalPort | Select-Object -Unique).Count -ne 2) {
    throw 'Local PixelStreaming2 viewer and signalling listeners missing.'
  }
  $status='HTTP_READY_BROWSER_NOT_YET_VERIFIED'
  Save-Status $status
  # VP9 is only a requested encoder at this stage; browser playback does not
  # establish an actually negotiated VP9 stream. Do not mark codec proven.
  # This Edge probe is *independent* of the GitHub runner and owns only its
  # temporary browser process/profile; no Editor PID or session is touched.
  $receiver=Join-Path $release 'scripts/ue/Test-YacsLevelEditorStreamClient.ps1'
  try {
    & $receiver -ViewerUrl $viewer -OutputRoot (Join-Path $sessionRoot 'receiver')
    if ($LASTEXITCODE -ne 0) { throw 'Receiver did not verify real live frames.' }
    $r=Get-Content -LiteralPath (Join-Path $sessionRoot 'receiver/level-editor-stream-client.json') -Raw | ConvertFrom-Json
    if ($r.received_browser_frame -ne $true -or $r.cleanup_complete -ne $true) {
      throw 'Receiver proof did not establish two increasing frames.'
    }
    $browserProved=$true
    $status='LIVE_RECEIVER_PROVEN_AWAITING_POST_JOB_VERIFICATION'
  } catch {
    # Keep the healthy native Editor alive for owner examination without
    # automatically relaunching/rebuilding a second time.
    $status='BROWSER_RECEIVER_FAILED_EDITOR_STILL_RUNNING'
    $message=($_.Exception.Message | Out-String).Trim()
    [ordered]@{status=$status;error=$message;session=$session} |
      ConvertTo-Json | Set-Content -LiteralPath (Join-Path $sessionRoot 'receiver-failure.json') -Encoding utf8
  }
  Save-Status $status
  while ($true) {
    $editor.Refresh()
    if ($editor.HasExited) {
      $status='EDITOR_EXITED_NO_AUTORESTART'
      Save-Status $status
      break
    }
    $native=Get-Process -Id $editor.Id -ErrorAction SilentlyContinue
    if (-not $native -or $native.StartTime.ToUniversalTime().ToString('o') -cne $ownerStart) {
      $status='EDITOR_IDENTITY_LOST_NO_AUTORESTART'
      Save-Status $status
      break
    }
    Save-Status $status
    Start-Sleep -Seconds 10
  }
} catch {
  $status='STARTUP_BLOCKED_NO_AUTORESTART'
  $message=$_.Exception.Message
  [ordered]@{status=$status;error=$message;session=$session;source_sha=$sha} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $sessionRoot 'failure.json') -Encoding utf8
  Save-Status $status
  if ($editor) {
    $native=Get-Process -Id $editor.Id -ErrorAction SilentlyContinue
    if ($native -and $native.StartTime.ToUniversalTime().ToString('o') -ceq $ownerStart) {
      $native | Stop-Process -Force
    }
  }
  throw
}
