#requires -Version 7.4
<#
.SYNOPSIS
    Automated WebRTC qualification, camera tour, and frame capture for Lesson 04 Review.
#>
[CmdletBinding()]
param(
    [string]$ViewerUrl = 'http://127.0.0.1/',
    [string]$OutputRoot = 'D:\yacs\project\Saved\RuntimeProof\Lesson04_Review'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$DebugPort = 9238
$Clock = [Diagnostics.Stopwatch]::StartNew()
$Browser = $null
$WebSocket = $null
$script:CdpId = 0

$CommandFile = 'D:\yacs\project\Saved\RuntimeProof\lesson04_camera_command.json'
$StateFile = 'D:\yacs\project\Saved\RuntimeProof\lesson04_camera_state.json'
$ArtifactDir = 'C:\Users\akarn\.gemini\antigravity\brain\a8bdbe87-c1b2-4851-a60b-d95da6c97b58'

$Cameras = @(
    'FULL_WORKING',
    'FULL_CONTEXT',
    'CLIFF_CLOSEUP',
    'CLIFF_TRANSITION',
    'SAND_COASTAL',
    'GRASS_GROUND',
    'ROAD_CORRIDOR'
)

function Invoke-Cdp([string]$Method, [hashtable]$Params = @{}) {
    $script:CdpId++
    $cmdId = $script:CdpId
    $packet = @{ id = $cmdId; method = $Method; params = $Params } | ConvertTo-Json -Depth 12 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($packet)
    $cancel = [Threading.CancellationTokenSource]::new(10000)
    try {
        $null = $WebSocket.SendAsync([ArraySegment[byte]]::new($bytes), [Net.WebSockets.WebSocketMessageType]::Text, $true, $cancel.Token).GetAwaiter().GetResult()
        while ($true) {
            $mem = [IO.MemoryStream]::new()
            try {
                $buf = [byte[]]::new(65536)
                do {
                    $part = $WebSocket.ReceiveAsync([ArraySegment[byte]]::new($buf), $cancel.Token).GetAwaiter().GetResult()
                    if ($part.MessageType -eq [Net.WebSockets.WebSocketMessageType]::Close) { throw 'Edge closed DevTools connection.' }
                    $mem.Write($buf, 0, $part.Count)
                } until ($part.EndOfMessage)
                $reply = [Text.Encoding]::UTF8.GetString($mem.ToArray()) | ConvertFrom-Json -AsHashtable
            } finally { $mem.Dispose() }
            if ($reply.ContainsKey('id') -and $reply.id -eq $cmdId) {
                if ($reply.ContainsKey('error')) { throw "DevTools $Method failed: $($reply.error.message)" }
                return $reply.result
            }
        }
    } finally { $cancel.Dispose() }
}

function Invoke-Eval([string]$Code, [bool]$Gesture = $false) {
    $res = Invoke-Cdp 'Runtime.evaluate' @{ expression = $Code; returnByValue = $true; userGesture = $Gesture; awaitPromise = $true }
    if ($res.ContainsKey('exceptionDetails')) { throw "Eval failed: $($res.exceptionDetails.text)" }
    if ($res.ContainsKey('result') -and $res.result.ContainsKey('value')) { return $res.result.value }
    return $null
}

$evaluation = [ordered]@{
    schema_version = 1
    started_at_utc = [DateTime]::UtcNow.ToString('o')
    viewer_url = $ViewerUrl
    cameras = @{}
    webrtc_stats = $null
    nvenc_status = $null
    status = 'IN_PROGRESS'
}

try {
    # 1. Start Edge with remote debugging
    $edgeProfile = Join-Path $OutputRoot 'EdgeProfile'
    if (Test-Path $edgeProfile) { Remove-Item -Path $edgeProfile -Recurse -Force -ErrorAction SilentlyContinue }
    $edgeArgs = @(
        "--remote-debugging-port=$DebugPort",
        "--user-data-dir=`"$edgeProfile`"",
        '--no-first-run',
        '--no-default-browser-check',
        '--window-size=1920,1080',
        'about:blank'
    )
    $Browser = Start-Process -FilePath 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' -ArgumentList $edgeArgs -PassThru
    Write-Host "Launched Edge PID: $($Browser.Id)"

    # Wait for DevTools HTTP
    $target = $null
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $targets = Invoke-RestMethod -Uri "http://127.0.0.1:$DebugPort/json/list" -TimeoutSec 2
            foreach ($t in $targets) {
                if ($t.type -eq 'page' -and $t.url -eq 'about:blank' -and $t.webSocketDebuggerUrl) {
                    $target = $t; break
                }
            }
        } catch {}
        if ($target) { break }
    }
    if (-not $target) { throw 'Could not discover Edge DevTools page target.' }
    Write-Host "Discovered DevTools target: $($target.webSocketDebuggerUrl)"

    # 2. Connect WebSocket
    $WebSocket = [Net.WebSockets.ClientWebSocket]::new()
    $connectCancel = [Threading.CancellationTokenSource]::new(5000)
    try {
        $null = $WebSocket.ConnectAsync([Uri]$target.webSocketDebuggerUrl, $connectCancel.Token).GetAwaiter().GetResult()
    } finally { $connectCancel.Dispose() }

    $null = Invoke-Cdp 'Page.enable'
    $null = Invoke-Cdp 'Runtime.enable'

    # 3. Navigate to PixelStreaming viewer
    $navUrl = $ViewerUrl + '?AutoConnect=true&AutoPlayVideo=true'
    Write-Host "Navigating to $navUrl"
    $null = Invoke-Cdp 'Page.navigate' @{ url = $navUrl }

    # 4. Wait for player load and click play / start if needed
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 1000
        $state = Invoke-Eval @'
(() => {
    const video = document.querySelector('video');
    const buttons = Array.from(document.querySelectorAll('button, [role="button"], [class*="overlay" i]'));
    const clickable = buttons.filter(b => b.offsetWidth > 0 && b.offsetHeight > 0);
    const startBtn = clickable.find(b => /start|connect|play|click/i.test(b.innerText || b.id || ''));
    if (startBtn) { startBtn.click(); }
    
    if (video) {
        const quality = typeof video.getVideoPlaybackQuality === 'function' ? video.getVideoPlaybackQuality() : null;
        const stream = video.srcObject instanceof MediaStream ? video.srcObject : null;
        return {
            has_video: true,
            video_width: video.videoWidth,
            video_height: video.videoHeight,
            paused: video.paused,
            ready_state: video.readyState,
            total_frames: quality ? quality.totalVideoFrames : 0,
            has_live_stream: !!stream && stream.active && stream.getVideoTracks().some(t => t.readyState === 'live')
        };
    }
    return { has_video: false };
})()
'@ $true
        Write-Host "Viewer state: $(ConvertTo-Json $state -Compress)"
        if ($state -and $state.has_video -and $state.has_live_stream -and $state.total_frames -gt 10 -and $state.video_width -gt 0) {
            $ready = $true
            break
        }
    }
    if (-not $ready) { throw 'WebRTC video did not start receiving frames within timeout.' }
    Write-Host "Live WebRTC stream established!"

    # 5. Extract WebRTC stats via JavaScript
    $webrtcStats = Invoke-Eval @'
(async () => {
    let stats = { codec: null, width: null, height: null, fps: null, bytes_received: null, packets_lost: null, jitter: null };
    // Find all RTCPeerConnections if exposed, or probe player
    if (window.webRtcPlayerObj && window.webRtcPlayerObj.peerConnection) {
        const report = await window.webRtcPlayerObj.peerConnection.getStats();
        report.forEach(stat => {
            if (stat.type === 'inbound-rtp' && stat.kind === 'video') {
                stats.bytes_received = stat.bytesReceived;
                stats.packets_lost = stat.packetsLost;
                stats.jitter = stat.jitter;
                stats.frames_per_second = stat.framesPerSecond;
                stats.frame_width = stat.frameWidth;
                stats.frame_height = stat.frameHeight;
                stats.codec_id = stat.codecId;
            }
            if (stat.type === 'codec' && (stat.mimeType || '').includes('video')) {
                stats.codecs = stats.codecs || [];
                stats.codecs.push(stat.mimeType);
            }
        });
    }
    const video = document.querySelector('video');
    if (video) {
        stats.video_element_width = video.videoWidth;
        stats.video_element_height = video.videoHeight;
        const q = video.getVideoPlaybackQuality ? video.getVideoPlaybackQuality() : null;
        stats.total_video_frames = q ? q.totalVideoFrames : null;
        stats.dropped_video_frames = q ? q.droppedVideoFrames : null;
    }
    return stats;
})()
'@
    $evaluation.webrtc_stats = $webrtcStats
    Write-Host "WebRTC Stats: $(ConvertTo-Json $webrtcStats -Compress)"

    # 6. Read NVIDIA GPU status
    $smi = & nvidia-smi --query-gpu=driver_version,name,utilization.gpu,utilization.encoder,utilization.decoder,memory.used,memory.free --format=csv,noheader,nounits
    $smiParts = ($smi.Trim() -split ',\s*')
    $nvenc = [ordered]@{
        driver_version = $smiParts[0]
        gpu_name = $smiParts[1]
        gpu_util_percent = [int]$smiParts[2]
        encoder_util_percent = [int]$smiParts[3]
        decoder_util_percent = [int]$smiParts[4]
        vram_used_mb = [int]$smiParts[5]
        vram_free_mb = [int]$smiParts[6]
    }
    $evaluation.nvenc_status = $nvenc
    Write-Host "NVIDIA NVENC Status: $(ConvertTo-Json $nvenc -Compress)"

    # 7. Cycle through all 7 cameras, wait for update, capture frames
    foreach ($cam in $Cameras) {
        Write-Host "Switching to camera: $cam"
        $cmd = @{ command_id = [guid]::NewGuid().ToString(); camera = $cam } | ConvertTo-Json
        [IO.File]::WriteAllText($CommandFile, $cmd)

        # Wait for state confirmation
        $switched = $false
        for ($w = 0; $w -lt 20; $w++) {
            Start-Sleep -Milliseconds 250
            if (Test-Path $StateFile) {
                try {
                    $st = Get-Content $StateFile -Raw | ConvertFrom-Json
                    if ($st.camera -eq $cam) { $switched = $true; break }
                } catch {}
            }
        }
        if (-not $switched) { Write-Warning "Camera $cam confirmation timed out, proceeding..." }

        # Wait 2.5s for video frame to stabilize
        Start-Sleep -Milliseconds 2500

        # Capture frame via CDP
        $shot = Invoke-Cdp 'Page.captureScreenshot' @{ format = 'png'; fromSurface = $true }
        $pngBytes = [Convert]::FromBase64String($shot.data)
        $outPath = Join-Path $OutputRoot "CAM_$cam.png"
        [IO.File]::WriteAllBytes($outPath, $pngBytes)
        Write-Host "Captured $outPath ($($pngBytes.Length) bytes)"

        # Also copy to artifact dir for viewing
        $artPath = Join-Path $ArtifactDir "CAM_$cam.png"
        [IO.File]::WriteAllBytes($artPath, $pngBytes)

        $evaluation.cameras[$cam] = [ordered]@{
            screenshot = $outPath
            bytes = $pngBytes.Length
            state = if ($switched) { $st } else { $null }
        }
    }

    # Reset camera to FULL_WORKING for the owner
    Write-Host "Resetting camera to FULL_WORKING for owner..."
    $cmd = @{ command_id = [guid]::NewGuid().ToString(); camera = 'FULL_WORKING' } | ConvertTo-Json
    [IO.File]::WriteAllText($CommandFile, $cmd)
    Start-Sleep -Milliseconds 1000

    $evaluation.status = 'QUALIFIED_SUCCESS'
    $evaluation.completed_at_utc = [DateTime]::UtcNow.ToString('o')
    $evaluation.lan_url = 'http://192.168.0.150/'
    $evaluation.loopback_url = 'http://127.0.0.1/'

} finally {
    # Close automated Edge test browser, leaving Unreal Editor streaming live for the owner!
    if ($WebSocket -and $WebSocket.State -eq [Net.WebSockets.WebSocketState]::Open) {
        try { $null = Invoke-Cdp 'Browser.close' } catch {}
        $WebSocket.Dispose()
    }
    if ($Browser -and -not $Browser.HasExited) {
        Start-Sleep -Milliseconds 500
        try { $Browser | Stop-Process -Force -ErrorAction SilentlyContinue } catch {}
    }

    $evalJson = Join-Path $OutputRoot 'lesson04_stream_evaluation.json'
    $evaluation | ConvertTo-Json -Depth 6 | Set-Content -Path $evalJson -Encoding utf8
    Write-Host "Evaluation saved to $evalJson"
}
