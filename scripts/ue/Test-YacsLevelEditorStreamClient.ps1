#requires -Version 7.4
<#
.SYNOPSIS
    Receive the local Level Editor stream in an isolated, temporary Edge client.
.DESCRIPTION
    Requires installed Microsoft Edge and a new or empty OutputRoot. Uses a
    fresh browser profile and loopback-only DevTools; never attaches to another
    browser. Success requires two increasing, nonzero video frame counters on
    the same live MediaStream video element. HTTP or a screenshot is not PASS.
    The 90-second budget includes a reserved cleanup window. Only processes
    descended from this client's recorded process identity may be stopped.

    Protocol references:
    https://learn.microsoft.com/en-us/microsoft-edge/devtools/protocol/
    https://chromedevtools.github.io/devtools-protocol/tot/Runtime/
    https://chromedevtools.github.io/devtools-protocol/tot/Page/
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $ViewerUrl,
    [Parameter(Mandatory = $true)] [string] $OutputRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$DebugPort = 9237
$Clock = [Diagnostics.Stopwatch]::StartNew()
$WorkLimitMilliseconds = 80000
$Browser = $null
$WebSocket = $null
$script:CdpMessageId = 0
$OwnedProcesses = @{}
$BrowserEvents = [Collections.Generic.List[object]]::new()
$Observations = [Collections.Generic.List[object]]::new()
$Actions = [Collections.Generic.List[object]]::new()
$CleanupErrors = [Collections.Generic.List[string]]::new()
$ReceiptPath = $null
$LocalPageObserved = $false
$receipt = [ordered]@{
    schema_version = 1
    status = 'BLOCKED'
    received_browser_frame = $false
    viewer_url = $ViewerUrl
    browser = 'Microsoft Edge'
    debug_port = $DebugPort
    runtime_limit_seconds = 90
    started_at_utc = [DateTime]::UtcNow.ToString('o')
    owner_visual_status = 'PENDING_FINAL_M3'
    performance_status = 'DEFERRED_AFTER_M3'
    performance_pass = $false
    cleanup_complete = $false
    error = $null
}

function Get-RemainingMilliseconds([int] $Maximum = 3000) {
    $remaining = $WorkLimitMilliseconds - [int] $Clock.ElapsedMilliseconds
    if ($remaining -le 0) { throw 'The receiving-client proof time budget expired.' }
    return [Math]::Min($Maximum, $remaining)
}

function Add-OwnedProcess([Diagnostics.Process] $Process, [int] $ParentId) {
    # Holding the handle keeps this object associated with the original process.
    $null = $Process.Handle
    $OwnedProcesses[[string] $Process.Id] = @{
        process = $Process
        pid = $Process.Id
        parent_pid = $ParentId
        start_ticks = $Process.StartTime.ToUniversalTime().Ticks
        executable = $Process.Path
    }
}

function Observe-OwnedProcesses {
    if (-not $Browser) { return }
    $rows = @(Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId, CreationDate -OperationTimeoutSec 2)
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($row in $rows) {
            $key = [string] $row.ProcessId
            $parentKey = [string] $row.ParentProcessId
            if ($OwnedProcesses.ContainsKey($key) -or -not $OwnedProcesses.ContainsKey($parentKey)) { continue }
            $parent = $OwnedProcesses[$parentKey]
            $createdTicks = $row.CreationDate.ToUniversalTime().Ticks
            if ($createdTicks -lt $parent.start_ticks) { continue }
            # A reused parent PID cannot authorize newly created processes.
            if ($parent.process.HasExited -and $createdTicks -gt $parent.process.ExitTime.ToUniversalTime().Ticks) { continue }
            $child = Get-Process -Id $row.ProcessId -ErrorAction SilentlyContinue
            if (-not $child) { continue }
            try {
                $null = $child.Handle
                if ($child.HasExited -or [Math]::Abs($child.StartTime.ToUniversalTime().Ticks - $createdTicks) -gt 10000) {
                    $child.Dispose()
                    continue
                }
                Add-OwnedProcess $child ([int] $row.ParentProcessId)
                $changed = $true
            }
            catch { $child.Dispose() }
        }
    }
}

function Stop-OwnedProcesses {
    if (-not $Browser) { return }
    if (-not $OwnedProcesses.ContainsKey([string] $Browser.Id) -and -not $Browser.HasExited) {
        $CleanupErrors.Add('The launched browser identity could not be recorded; cleanup cannot be confirmed.')
    }
    # Reobserve after termination to catch a child created between the first
    # snapshot and its parent's exit. Never adopt children born after that exit.
    foreach ($pass in 1..2) {
        try { Observe-OwnedProcesses } catch { $CleanupErrors.Add($_.Exception.Message) }
        # Stop the root first to prevent it from replacing renderer processes.
        $identities = @($OwnedProcesses.Values | Sort-Object @{ Expression = { $_.pid -ne $Browser.Id } }, start_ticks)
        foreach ($identity in $identities) {
            try {
                $process = $identity.process
                if ($process.HasExited) { continue }
                if ($process.StartTime.ToUniversalTime().Ticks -ne $identity.start_ticks -or $process.Path -ne $identity.executable) {
                    throw "Refused cleanup after process identity changed: $($identity.pid)."
                }
                $process.Kill()
            }
            catch { $CleanupErrors.Add($_.Exception.Message) }
        }
    }
    $receipt.owned_processes = @($identities | ForEach-Object {
        @{ pid = $_.pid; parent_pid = $_.parent_pid; start_ticks_utc = $_.start_ticks; executable = $_.executable }
    })
    foreach ($identity in $identities) {
        try {
            $waitMilliseconds = [Math]::Max(0, [Math]::Min(250, 88000 - [int] $Clock.ElapsedMilliseconds))
            if (-not $identity.process.HasExited -and -not $identity.process.WaitForExit($waitMilliseconds)) {
                $CleanupErrors.Add("Owned client process is still running: $($identity.pid).")
            }
        }
        catch { $CleanupErrors.Add($_.Exception.Message) }
        finally { $identity.process.Dispose() }
    }
}

function Invoke-Cdp([string] $Method, [hashtable] $Parameters = @{}) {
    $script:CdpMessageId += 1
    $commandId = $script:CdpMessageId
    $packet = @{ id = $commandId; method = $Method; params = $Parameters } | ConvertTo-Json -Depth 12 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($packet)
    $cancel = [Threading.CancellationTokenSource]::new((Get-RemainingMilliseconds))
    try {
        $WebSocket.SendAsync([ArraySegment[byte]]::new($bytes), [Net.WebSockets.WebSocketMessageType]::Text, $true, $cancel.Token).GetAwaiter().GetResult()
        while ($true) {
            $message = [IO.MemoryStream]::new()
            try {
                $buffer = [byte[]]::new(16384)
                do {
                    $part = $WebSocket.ReceiveAsync([ArraySegment[byte]]::new($buffer), $cancel.Token).GetAwaiter().GetResult()
                    if ($part.MessageType -eq [Net.WebSockets.WebSocketMessageType]::Close) { throw 'Edge closed the DevTools connection.' }
                    $message.Write($buffer, 0, $part.Count)
                    if ($message.Length -gt 12582912) { throw 'DevTools response exceeded the 12 MiB evidence limit.' }
                } until ($part.EndOfMessage)
                $reply = [Text.Encoding]::UTF8.GetString($message.ToArray()) | ConvertFrom-Json -AsHashtable
            }
            finally { $message.Dispose() }
            if ($reply.ContainsKey('id') -and $reply.id -eq $commandId) {
                if ($reply.ContainsKey('error')) { throw "DevTools $Method failed: $($reply.error.message)" }
                return $reply.result
            }
            if ($reply.ContainsKey('method') -and $reply.method -in @('Runtime.exceptionThrown', 'Log.entryAdded')) {
                $detail = $reply | ConvertTo-Json -Depth 8 -Compress
                $BrowserEvents.Add($detail.Substring(0, [Math]::Min(1000, $detail.Length)))
                if ($BrowserEvents.Count -gt 20) { $BrowserEvents.RemoveAt(0) }
            }
        }
    }
    finally { $cancel.Dispose() }
}

function Invoke-PageExpression([string] $Expression, [bool] $UserGesture = $false) {
    $result = Invoke-Cdp 'Runtime.evaluate' @{ expression = $Expression; returnByValue = $true; userGesture = $UserGesture }
    if ($result.ContainsKey('exceptionDetails')) { throw "Viewer evaluation failed: $($result.exceptionDetails.text)" }
    if (-not $result.result.ContainsKey('value')) { throw 'Viewer evaluation returned no evidence value.' }
    return $result.result.value
}

try {
    if (-not $IsWindows) { throw 'The stream receiving-client proof requires Windows and installed Microsoft Edge.' }
    if (-not [IO.Path]::IsPathFullyQualified($OutputRoot)) { throw 'OutputRoot must be an absolute, new or empty directory.' }
    $OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
    $ancestor = $OutputRoot
    while ($ancestor) {
        if (Test-Path -LiteralPath $ancestor) {
            $item = Get-Item -LiteralPath $ancestor -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'OutputRoot cannot use a junction or symlink.' }
        }
        $ancestor = Split-Path -Path $ancestor -Parent
    }
    if ((Test-Path -LiteralPath $OutputRoot) -and @(Get-ChildItem -LiteralPath $OutputRoot -Force).Count) {
        throw 'OutputRoot is not empty; use a fresh proof directory.'
    }
    $null = [IO.Directory]::CreateDirectory($OutputRoot)
    $ReceiptPath = Join-Path $OutputRoot 'level-editor-stream-client.json'
    if ($ViewerUrl -notmatch '^http://127\.0\.0\.1(?::[0-9]{1,5})?/$') {
        throw 'ViewerUrl must be exactly http://127.0.0.1[:port]/, without credentials, path, query or fragment.'
    }
    $viewerUri = [Uri] $ViewerUrl
    if ($viewerUri.Port -lt 1 -or $viewerUri.Port -gt 65535 -or $viewerUri.Port -eq $DebugPort) { throw 'Invalid or conflicting viewer port.' }
    $origin = $viewerUri.GetLeftPart([UriPartial]::Authority)
    $navigationUrl = $viewerUri.AbsoluteUri + '?AutoConnect=true&AutoPlayVideo=true'
    $receipt.navigation_url = $navigationUrl
    $edgeCandidates = @(${env:ProgramFiles(x86)}, $env:ProgramFiles, $env:LOCALAPPDATA) |
        Where-Object { $_ } | ForEach-Object { Join-Path $_ 'Microsoft/Edge/Application/msedge.exe' }
    $edgePath = $edgeCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if (-not $edgePath) { throw 'Microsoft Edge was not found at a standard installed executable path; no installation was attempted.' }
    $receipt.browser_executable = $edgePath
    $receipt.browser_version = [Diagnostics.FileVersionInfo]::GetVersionInfo($edgePath).ProductVersion
    $reservation = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $DebugPort)
    $reservation.Server.ExclusiveAddressUse = $true
    try { $reservation.Start() } finally { $reservation.Stop() }

    $profilePath = Join-Path $OutputRoot 'edge-profile'
    $null = [IO.Directory]::CreateDirectory($profilePath)
    $receipt.fresh_profile = $profilePath
    $start = [Diagnostics.ProcessStartInfo]::new($edgePath)
    $start.UseShellExecute = $false
    foreach ($argument in @(
        '--headless=new', '--remote-debugging-address=127.0.0.1', "--remote-debugging-port=$DebugPort",
        "--user-data-dir=$profilePath", '--no-first-run', '--no-default-browser-check',
        '--disable-sync', '--disable-background-networking', '--disable-extensions',
        '--autoplay-policy=no-user-gesture-required', '--mute-audio', '--window-size=1280,720', 'about:blank'
    )) { $start.ArgumentList.Add($argument) }
    $Browser = [Diagnostics.Process]::Start($start)
    Add-OwnedProcess $Browser $PID
    $receipt.browser_pid = $Browser.Id
    $receipt.browser_started_at_utc = $Browser.StartTime.ToUniversalTime().ToString('o')
    $receipt.status = 'WAITING_FOR_BROWSER_FRAMES'
    $target = $null
    $discoveryEnd = [Math]::Min(20000 + $Clock.ElapsedMilliseconds, $WorkLimitMilliseconds)
    while ($Clock.ElapsedMilliseconds -lt $discoveryEnd) {
        if ($Browser.HasExited) { throw 'The isolated Edge process exited before DevTools was ready.' }
        Observe-OwnedProcesses
        $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $DebugPort -ErrorAction SilentlyContinue)
        foreach ($listener in $listeners) {
            if ($listener.LocalAddress -ne '127.0.0.1' -or -not $OwnedProcesses.ContainsKey([string] $listener.OwningProcess)) {
                throw 'DevTools is not exclusively bound to loopback by the owned Edge process tree.'
            }
            $listenerOwner = Get-Process -Id $listener.OwningProcess -ErrorAction Stop
            try {
                $ownerIdentity = $OwnedProcesses[[string] $listener.OwningProcess]
                if ($listenerOwner.HasExited -or $listenerOwner.StartTime.ToUniversalTime().Ticks -ne $ownerIdentity.start_ticks -or
                    $listenerOwner.Path -ne $ownerIdentity.executable) { throw 'DevTools listener process identity changed.' }
            }
            finally { $listenerOwner.Dispose() }
        }
        if ($listeners.Count) {
            try {
                $targets = @(Invoke-RestMethod -Uri "http://127.0.0.1:$DebugPort/json/list" -NoProxy -MaximumRedirection 0 -TimeoutSec 2)
                $target = $targets | Where-Object { $_.type -eq 'page' -and $_.url -eq 'about:blank' } | Select-Object -First 1
            }
            catch { $receipt.last_discovery_error = $_.Exception.Message }
        }
        if ($target) { break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $target) { throw 'No owned blank Edge page became available within the bounded discovery window.' }
    $debugUri = [Uri] $target.webSocketDebuggerUrl
    if ($debugUri.Scheme -ne 'ws' -or $debugUri.Host -notin @('127.0.0.1', 'localhost') -or $debugUri.Port -ne $DebugPort -or
        $debugUri.UserInfo -or $debugUri.Query -or $debugUri.Fragment -or
        $debugUri.AbsolutePath -notlike '/devtools/page/*') { throw 'Refused a non-local or unexpected DevTools endpoint.' }
    $debugBuilder = [UriBuilder]::new($debugUri)
    $debugBuilder.Host = '127.0.0.1'
    $WebSocket = [Net.WebSockets.ClientWebSocket]::new()
    $connectCancel = [Threading.CancellationTokenSource]::new((Get-RemainingMilliseconds))
    try { $WebSocket.ConnectAsync($debugBuilder.Uri, $connectCancel.Token).GetAwaiter().GetResult() }
    finally { $connectCancel.Dispose() }
    $null = Invoke-Cdp 'Page.enable'
    $null = Invoke-Cdp 'Runtime.enable'
    $null = Invoke-Cdp 'Log.enable'
    $navigation = Invoke-Cdp 'Page.navigate' @{ url = $navigationUrl }
    if ($navigation.ContainsKey('errorText')) { throw "Local viewer navigation failed: $($navigation.errorText)" }

    $originJson = $origin | ConvertTo-Json -Compress
    $snapshotExpression = @'
(() => {
  if (location.origin !== __ORIGIN__ || location.pathname !== '/') {
    return { unexpected_navigation: true, url: location.href };
  }
  const state = window.__yacsLevelStreamProof ||= { ids: new WeakMap(), nextId: 1 };
  const visible = e => {
    const box = e.getBoundingClientRect(), style = getComputedStyle(e);
    return box.width > 0 && box.height > 0 && style.display !== 'none' &&
      style.visibility === 'visible' && Number(style.opacity) !== 0;
  };
  const label = e => (e.innerText || e.value || e.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
  const startLabel = /^(connect|play|start streaming|click to (start|connect|play( video)?))$/i;
  return {
    unexpected_navigation: false, url: location.href, title: document.title,
    document_ready_state: document.readyState, navigation_token: performance.timeOrigin,
    videos: Array.from(document.querySelectorAll('video')).slice(0, 8).map(v => {
      if (!state.ids.has(v)) state.ids.set(v, state.nextId++);
      const quality = typeof v.getVideoPlaybackQuality === 'function' ? v.getVideoPlaybackQuality() : null;
      const stream = v.srcObject instanceof MediaStream ? v.srcObject : null;
      return { element_token: state.ids.get(v), id: v.id, video_width: v.videoWidth,
        video_height: v.videoHeight, ready_state: v.readyState, paused: v.paused,
        current_time: v.currentTime, total_video_frames: quality ? quality.totalVideoFrames : null,
        dropped_video_frames: quality ? quality.droppedVideoFrames : null,
        live_media_stream: !!stream && stream.active && stream.getVideoTracks().some(t => t.readyState === 'live'),
        media_error: v.error ? v.error.message : null };
    }),
    controls: Array.from(document.querySelectorAll('button,[role="button"],input[type="button"],input[type="submit"],[class*="overlay" i],[id*="overlay" i]'))
      .filter(visible).reverse().slice(0, 30).map(e => ({ id: e.id, tag: e.tagName,
        label: label(e).slice(0, 100), enabled: !e.disabled, can_start: startLabel.test(label(e)) }))
  };
})()
'@
    $snapshotExpression = $snapshotExpression.Replace('__ORIGIN__', $originJson)
    $previous = @{}
    $nextActionAt = $Clock.ElapsedMilliseconds + 3000
    while ($Clock.ElapsedMilliseconds -lt ($WorkLimitMilliseconds - 5000)) {
        Observe-OwnedProcesses
        $snapshot = Invoke-PageExpression $snapshotExpression
        $LocalPageObserved = -not $snapshot.unexpected_navigation
        if (-not $LocalPageObserved) { throw 'The viewer navigated away from the explicitly allowed loopback root.' }
        $snapshot.observed_at_utc = [DateTime]::UtcNow.ToString('o')
        $snapshot.elapsed_ms = $Clock.ElapsedMilliseconds
        $Observations.Add($snapshot)
        if ($Observations.Count -gt 16) { $Observations.RemoveAt(0) }
        foreach ($video in $snapshot.videos) {
            $key = "$($snapshot.navigation_token):$($video.element_token)"
            $valid = $video.live_media_stream -and $video.video_width -gt 0 -and $video.video_height -gt 0 -and
                $video.ready_state -ge 2 -and $null -ne $video.total_video_frames -and $video.total_video_frames -gt 0
            if (-not $valid) { $previous.Remove($key); continue }
            $sample = @{ observed_at_utc = $snapshot.observed_at_utc; elapsed_ms = $snapshot.elapsed_ms; video = $video }
            if ($previous.ContainsKey($key) -and $video.total_video_frames -gt $previous[$key].video.total_video_frames -and
                $sample.elapsed_ms - $previous[$key].elapsed_ms -ge 1000) {
                $receipt.received_browser_frame = $true
                $receipt.frame_samples = @($previous[$key], $sample)
                $receipt.status = 'RECEIVED_BROWSER_FRAMES'
                break
            }
            $previous[$key] = $sample
        }
        if ($receipt.received_browser_frame) { break }
        if ($Actions.Count -lt 3 -and $Clock.ElapsedMilliseconds -ge $nextActionAt) {
            $control = $snapshot.controls | Where-Object { $_.can_start -and $_.enabled } | Select-Object -First 1
            if ($control) {
                $labelJson = $control.label | ConvertTo-Json -Compress
                $idJson = $control.id | ConvertTo-Json -Compress
                $clickExpression = @'
(() => {
  if (location.origin !== __ORIGIN__ || location.pathname !== '/') return { action: 'refused_navigation' };
  const elements = Array.from(document.querySelectorAll('button,[role="button"],input[type="button"],input[type="submit"],[class*="overlay" i],[id*="overlay" i]')).reverse();
  const element = elements.find(e => {
    const box = e.getBoundingClientRect(), style = getComputedStyle(e);
    const text = (e.innerText || e.value || e.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
    return e.id === __ID__ && text === __LABEL__ && !e.disabled && box.width > 0 && box.height > 0 &&
      style.display !== 'none' && style.visibility === 'visible' && Number(style.opacity) !== 0;
  });
  if (!element) return { action: 'control_changed' };
  element.click();
  return { action: 'clicked_observed_start_control', label: __LABEL__, id: __ID__ };
})()
'@
                $clickExpression = $clickExpression.Replace('__ORIGIN__', $originJson).Replace('__LABEL__', $labelJson).Replace('__ID__', $idJson)
                $Actions.Add((Invoke-PageExpression $clickExpression $true))
            }
            $nextActionAt = $Clock.ElapsedMilliseconds + 7000
        }
        Start-Sleep -Milliseconds 1100
    }
    if (-not $receipt.received_browser_frame) { throw 'No two increasing, nonzero frame counters were observed on a live MediaStream video.' }
}
catch {
    if ($receipt.status -eq 'WAITING_FOR_BROWSER_FRAMES') { $receipt.status = 'NO_BROWSER_FRAMES' }
    $receipt.error = $_.Exception.Message
}
finally {
    if ($LocalPageObserved -and $WebSocket -and $WebSocket.State -eq [Net.WebSockets.WebSocketState]::Open -and $Clock.ElapsedMilliseconds -lt 76000) {
        try {
            $stillLocal = Invoke-PageExpression "location.origin === $originJson && location.pathname === '/'"
            if ($stillLocal) {
                $capture = Invoke-Cdp 'Page.captureScreenshot' @{ format = 'png'; fromSurface = $true }
                $png = [Convert]::FromBase64String($capture.data)
                $screenshotPath = Join-Path $OutputRoot 'level-editor-stream-client.png'
                [IO.File]::WriteAllBytes($screenshotPath, $png)
                $receipt.screenshot = @{ path = $screenshotPath; bytes = $png.Length; sha256 = (Get-FileHash -LiteralPath $screenshotPath -Algorithm SHA256).Hash.ToLowerInvariant() }
            }
        }
        catch { $receipt.screenshot_error = $_.Exception.Message }
    }
    if ($WebSocket) {
        try { $WebSocket.Abort(); $WebSocket.Dispose() } catch { $CleanupErrors.Add($_.Exception.Message) }
    }
    try { Stop-OwnedProcesses } catch { $CleanupErrors.Add($_.Exception.Message) }
    $receipt.cleanup_complete = $CleanupErrors.Count -eq 0
    $receipt.cleanup_errors = @($CleanupErrors.ToArray())
    if (-not $receipt.cleanup_complete -and $receipt.received_browser_frame) { $receipt.status = 'RECEIVED_BROWSER_FRAMES_CLEANUP_INCOMPLETE' }
    $receipt.observations = @($Observations.ToArray())
    $receipt.viewer_actions = @($Actions.ToArray())
    $receipt.browser_events = @($BrowserEvents.ToArray())
    $receipt.completed_at_utc = [DateTime]::UtcNow.ToString('o')
    $receipt.elapsed_seconds = [Math]::Round($Clock.Elapsed.TotalSeconds, 3)
    if ($ReceiptPath) { $receipt | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $ReceiptPath -Encoding utf8 }
    [ordered]@{ status = $receipt.status; received_browser_frame = $receipt.received_browser_frame; cleanup_complete = $receipt.cleanup_complete; receipt_path = $ReceiptPath; error = $receipt.error } | ConvertTo-Json -Compress
}
if ($receipt.received_browser_frame -and $receipt.cleanup_complete) { exit 0 }
exit 1
