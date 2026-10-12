#requires -Version 7.4
<#
.SYNOPSIS
  Open one owner-requested PCG365 red-review Level Editor PixelStreaming2 session.
.DESCRIPTION
  Reuse the authenticated disposable d361e765 saved terrain stage. This starts
  no build, never writes a map or asset, and never adopts/stops other UE owners.
  A successful live receiver handoff leaves only this authenticated Editor open.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedHead,
  [Parameter(Mandatory)][ValidatePattern('^[0-9]+-[0-9]+$')][string]$SessionToken
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$RepoRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $PSScriptRoot 'Assert-YacsPcg365NativeCompletion.ps1')
$Stage='D:/yacs/work/pcg365/d361e7651d16ff424ae4e812c7d8cbe1fe81d662/38278235093-1'
$Runtime='d361e7651d16ff424ae4e812c7d8cbe1fe81d662'
$Session=[IO.Path]::GetFullPath("D:/yacs/work/pcg365-live-review/$ExpectedHead/$SessionToken")
$Project=Join-Path $Stage 'Pcg365Diagnostic.uproject'
$MapFile=Join-Path $Stage 'Content/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview.umap'
$MapHash='bf2b92945865e2307990b6d3da40095dfa0774d28affb32a1e42e55f288764dd'
$Viewer='http://127.0.0.1/'
$Launch=$null
$HandedOff=$false
$OutputReceipt=Join-Path $Session 'pcg365-stream-session.json'

function Require([bool]$Condition,[string]$Message) {
  if (-not $Condition) { throw $Message }
}
function Assert-NotAliased([string]$Path) {
  $cursor=[IO.Path]::GetFullPath($Path)
  while ($cursor) {
    if (Test-Path -LiteralPath $cursor) {
      $item=Get-Item -LiteralPath $cursor -Force
      Require (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) "Reparse/junction refused: $cursor"
    }
    $parent=Split-Path -Path $cursor -Parent
    if ($parent -eq $cursor) { break }
    $cursor=$parent
  }
}
function Assert-SourceIdentity {
  $manifest=Get-Content -LiteralPath (Join-Path $RepoRoot 'worldgen/sa_calobra/pcg365_rejected_sites_review_v1.json') -Raw | ConvertFrom-Json
  Require ($manifest.source_producer_sha -ceq $Runtime -and
    $manifest.source_run -ceq '38278235093-1' -and
    $manifest.source_map_sha256 -ceq $MapHash -and
    $manifest.placement -eq $false -and
    @($manifest.qualified_assets).Count -eq 0 -and
    @($manifest.markers).Count -eq 5) 'Red review manifest/authority differs'
  $expectedStage=Get-Content -LiteralPath (Join-Path $Stage 'staged-files.json') -Raw | ConvertFrom-Json
  Require ($expectedStage.expected_head -ceq $Runtime) 'Native stage producer SHA differs'
  $completed=Get-Content -LiteralPath (Join-Path $Stage 'proof/collection-contact-review/launcher-completed.json') -Raw | ConvertFrom-Json
  Assert-YacsPcg365NativeCompletion -Receipt $completed -ExpectedHead $Runtime
  $contact=Join-Path $Stage 'proof/collection-contact-review/contact-fresh-phase.json'
  $contactFile=Get-Item -LiteralPath $contact -Force
  Require ($contactFile.Length -eq $manifest.source_contact_fresh_bytes -and
    (Get-FileHash -LiteralPath $contact -Algorithm SHA256).Hash.ToLowerInvariant() -ceq
       $manifest.source_contact_fresh_sha256) 'Contact phase original bytes differ'
  Require ((Get-FileHash -LiteralPath $MapFile -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $MapHash) 'Accepted map SHA256 differs'
}
function Assert-OwnedStillAlive {
  Require ($null -ne $Launch) 'No owned Editor'
  $Launch.Refresh()
  Require (-not $Launch.HasExited) "Owned UE Editor unexpectedly exited: $($Launch.ExitCode)"
  $native=Get-Process -Id $Launch.Id -ErrorAction Stop
  Require ($native.StartTime.ToUniversalTime().ToString('o') -ceq
    $Launch.StartTime.ToUniversalTime().ToString('o')) 'Owned Editor process identity changed'
}
function Stop-OnlyOwned {
  if ($null -eq $Launch) { return }
  try {
    $native=Get-Process -Id $Launch.Id -ErrorAction SilentlyContinue
    if ($native -and -not $native.HasExited -and
      $native.StartTime.ToUniversalTime().ToString('o') -ceq
        $Launch.StartTime.ToUniversalTime().ToString('o')) {
      $native | Stop-Process -Force
    }
  } catch { Write-Warning "Could not dispose of our exact UE process: $($_.Exception.Message)" }
}

Assert-NotAliased $Session
Assert-NotAliased $Stage
Require (-not (Test-Path -LiteralPath $Session)) 'Previous stream session is immutable; use a new token'
Require (((& git -C $RepoRoot rev-parse HEAD).Trim()) -ceq $ExpectedHead) 'Stream launcher HEAD differs'
Require (@(& git -C $RepoRoot status --porcelain --untracked-files=no).Count -eq 0) 'Tracked launcher checkout is dirty'
$hostStatus= & (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
Require ($hostStatus.status -ceq 'IDLE') "Existing Unreal owner must not be disturbed ($($hostStatus.status))"
Require ([IO.DriveInfo]::new('D:/').AvailableFreeSpace -gt 5GB) 'D: 5 GiB reserve must survive'
Require ((Test-Path -LiteralPath $Project -PathType Leaf) -and
         (Test-Path -LiteralPath $MapFile -PathType Leaf)) 'Pinned successful native project unavailable'
Assert-SourceIdentity
$bound=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object LocalPort -in @(80,8888,18784))
Require ($bound.Count -eq 0) 'Existing Viewer/MCP listeners own these ports; refuse second streamer'

$Editor='D:/yacs/engine/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe'
Require (Test-Path -LiteralPath $Editor -PathType Leaf) 'Pinned UE 5.8 Editor unavailable'
$Plugin='D:/yacs/engine/UE_5.8/Engine/Plugins/Media/PixelStreaming2/PixelStreaming2.uplugin'
Require ((Get-FileHash -LiteralPath $Plugin -Algorithm SHA256).Hash.ToLowerInvariant() -ceq
  '609e80122117d62b6affba640ec2d10c5168a41eee16c8d9768ca145abd59ea6') 'Installed PixelStreaming2 plugin changed'
$script=Join-Path $RepoRoot 'scripts/ue/bootstrap_pcg365_red_stream.py'
$bootstrap=Get-Item -LiteralPath $script -Force
Require (-not ($bootstrap.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'Untrusted bootstrap alias'
[void][IO.Directory]::CreateDirectory($Session)
$receipt=[ordered]@{
  schema_version=1;issue=365;source_sha=$ExpectedHead;native_producer_sha=$Runtime
  status='PREPARING';editor_pid=$null;viewer_url=$Viewer
  browser_frames_received=$false;owner_handoff=$false;placement=$false
  qualified_assets=@();map_saved=$false;performance_pass=$false
  source_map_sha256=$MapHash;session_root=$Session
}

try {
  $arguments=@(
    ('"' + $Project + '"'),
    '/Game/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview',
    '-EnablePlugins=PixelStreaming2',
    '-DisablePlugins=ModelContextProtocol,Wingman,AndroidFileServer',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorSource=LevelEditorViewport',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorStartOnLaunch=True',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorUseRemoteSignallingServer=False',
    '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:ConnectionURL=ws://127.0.0.1:8888',
    '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
    '-ini:EditorPerProjectUserSettings:[/Script/UnrealEd.EditorLoadingSavingSettings]:bAutoSaveEnable=False',
    '-EditorPixelStreamingRes=1280x720','-RenderOffscreen',
    '-NoP4','-NoSplash','-NoSound','-NoLiveCoding','-NoVSync',
    '-ExecCmds="t.MaxFPS 30"','-ScriptErrorsAreFatal',
    ('-ExecutePythonScript="' + $script + '"'),
    ('-AbsLog="' + (Join-Path $Session 'editor.log') + '"')
  )
  $oldEnv=@{}
  $keys=@('RUNNER_TRACKING_ID','YACS_OWNER_HANDOFF','PYTHONPATH','PYTHONHOME','YACS_PCG365_STAGE','YACS_PCG365_LIVE_SESSION','YACS_PCG365_LIVE_HEAD')
  foreach ($key in $keys) { $oldEnv[$key]=[Environment]::GetEnvironmentVariable($key,'Process') }
  try {
    foreach ($key in @('RUNNER_TRACKING_ID','PYTHONPATH','PYTHONHOME')) {
      [Environment]::SetEnvironmentVariable($key,'','Process')
    }
    $env:YACS_OWNER_HANDOFF='true'
    $env:YACS_PCG365_STAGE=$Stage
    $env:YACS_PCG365_LIVE_SESSION=$Session
    $env:YACS_PCG365_LIVE_HEAD=$ExpectedHead
    $Launch=Start-Process -FilePath $Editor -ArgumentList $arguments -WorkingDirectory $Stage -PassThru
  } finally {
    foreach ($key in $keys) { [Environment]::SetEnvironmentVariable($key,$oldEnv[$key],'Process') }
  }
  $receipt.editor_pid=$Launch.Id
  $receipt.editor_start_time_utc=$Launch.StartTime.ToUniversalTime().ToString('o')
  $scenePath=Join-Path $Session 'scene/red-review-live-scene.json'
  $ready=$false
  $deadline=[DateTime]::UtcNow.AddSeconds(240)
  while ([DateTime]::UtcNow -lt $deadline) {
    Assert-OwnedStillAlive
    if (Test-Path -LiteralPath (Join-Path $Session 'red-live-error.json')) {
      $err=Get-Content -LiteralPath (Join-Path $Session 'red-live-error.json') -Raw
      throw "Native red stream scene FAILED: $err"
    }
    if (Test-Path -LiteralPath $scenePath -PathType Leaf) {
      $scene=Get-Content -LiteralPath $scenePath -Raw | ConvertFrom-Json
      Require ($scene.status -ceq 'RED_LIVE_SCENE_READY' -and
        @($scene.markers).Count -eq 5 -and $scene.map_saved -eq $false -and
        $scene.placement -eq $false -and $scene.review_tool_sha -ceq $ExpectedHead) 'Live red scene identity drift'
      try {
        $http=Invoke-WebRequest -Uri $Viewer -TimeoutSec 3 -MaximumRedirection 0
        $ready=$http.StatusCode -eq 200 -and $http.Content -match '(?i)pixel.?stream|<video|<!doctype html'
      } catch { $ready=$false }
      if ($ready) { break }
    }
    Start-Sleep -Seconds 2
  }
  Require $ready 'The red scene and Epic viewer did not become HTTP-ready in 240s'
  $listeners=@(Get-NetTCPConnection -State Listen -ErrorAction Stop |
    Where-Object LocalPort -in @(80,8888))
  Require (@($listeners.LocalPort | Select-Object -Unique).Count -eq 2) 'PixelStreaming2 viewer or signalling listener missing'
  Assert-OwnedStillAlive
  # Browser VIDEO proof: HTTP readiness alone is never accepted.
  & (Join-Path $RepoRoot 'scripts/ue/Test-YacsLevelEditorStreamClient.ps1') -ViewerUrl $Viewer -OutputRoot (Join-Path $Session 'client')
  Require ($LASTEXITCODE -eq 0) 'No verified received browser video'
  $client=Get-Content -LiteralPath (Join-Path $Session 'client/level-editor-stream-client.json') -Raw | ConvertFrom-Json
  Require ($client.received_browser_frame -eq $true -and $client.cleanup_complete -eq $true) 'Browser video/proof cleanup differs'
  Assert-OwnedStillAlive
  Assert-SourceIdentity
  $receipt.browser_frames_received=$true
  $receipt.viewer_client_receipt_sha256=(Get-FileHash -LiteralPath (Join-Path $Session 'client/level-editor-stream-client.json') -Algorithm SHA256).Hash.ToLowerInvariant()
  $receipt.status='BROWSER_VIDEO_RECEIVED'
  $receipt.owner_handoff=$true
  $receipt.lan_url_candidates=@()
  foreach($nic in @(Get-NetIPConfiguration | Where-Object { $null -ne $_.IPv4DefaultGateway })) {
    foreach($ip in @($nic.IPv4Address)) {
      if($ip.IPAddress -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)') {
        $receipt.lan_url_candidates+= "http://$($ip.IPAddress)/"
      }
    }
  }
  $HandedOff=$true
  Write-Host "PCG365 RED PIXEL STREAM HANDOFF PASS; on the host open $Viewer"
  $receipt | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputReceipt -Encoding utf8
} catch {
  $receipt.status='BLOCKED'
  $receipt.error=$_.Exception.Message
  throw
} finally {
  if (-not $HandedOff) { Stop-OnlyOwned }
  $receipt.finished_at_utc=[DateTime]::UtcNow.ToString('o')
  $receipt | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputReceipt -Encoding utf8
}
