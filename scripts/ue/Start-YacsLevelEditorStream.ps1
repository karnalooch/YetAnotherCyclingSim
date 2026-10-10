#requires -Version 7.4
<#
.SYNOPSIS
    Open the retained #364 road viewport for the owner's local/LAN review.
.DESCRIPTION
    Copies authenticated saved packages into a fresh project, uses Epic's stock
    PixelStreaming2 editor stream and hands that one Editor session to the owner.
    No build, source-world save, firewall/router change or public tunnel is run.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string] $ExpectedHead,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$')]
    [string] $SessionToken
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Level Editor review requires the Windows home host.' }
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$RuntimeSha = '1ef46dacedba5ed1fc909422529be41808d3dbe4'
$SessionRoot = "D:\yacs\work\level-editor-review\$($RuntimeSha.Substring(0, 12))-$SessionToken"
$EvidenceRoot = Join-Path $RepoRoot "Saved/RuntimeProof/LevelEditorStream/$SessionToken"
$Map = '/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview'
$ViewerUrl = 'http://127.0.0.1/'
$EditorProcess = $null
$HandedOff = $false
$SnapshotOwned = $false
$OwnedProcesses = @{}

function Assert-NoReparseAncestor([string] $Path) {
    $entryPath = [IO.Path]::GetFullPath($Path)
    while ($entryPath) {
        if (Test-Path -LiteralPath $entryPath) {
            $entry = Get-Item -LiteralPath $entryPath -Force
            if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Review cannot use a junction or symlink: $entryPath"
            }
        }
        $entryPath = Split-Path -Path $entryPath -Parent
    }
}

function Observe-OwnedProcesses {
    if (-not $EditorProcess) { return }
    $processes = @(Get-CimInstance Win32_Process)
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($candidate in $processes) {
            $processKey = [string] $candidate.ProcessId
            if ($OwnedProcesses.ContainsKey($processKey)) { continue }
            if (-not $OwnedProcesses.ContainsKey([string] $candidate.ParentProcessId)) { continue }
            $parentIdentity = $OwnedProcesses[[string] $candidate.ParentProcessId]
            $parent = Get-Process -Id $parentIdentity.pid -ErrorAction SilentlyContinue
            if (-not $parent -or $parent.HasExited -or
                $parent.StartTime.ToUniversalTime().ToString('o') -ne $parentIdentity.start_time_utc -or
                $parent.Path -ne $parentIdentity.executable_path) { continue }
            $native = Get-Process -Id $candidate.ProcessId -ErrorAction SilentlyContinue
            if (-not $native -or $native.HasExited -or $native.StartTime.ToUniversalTime() -lt $EditorProcess.StartTime.ToUniversalTime()) { continue }
            if ($native.Path -ne [string] $candidate.ExecutablePath -or
                [Math]::Abs(($native.StartTime.ToUniversalTime() - $candidate.CreationDate.ToUniversalTime()).TotalMilliseconds) -gt 1) { continue }
            $OwnedProcesses[$processKey] = [ordered]@{
                pid = [int] $candidate.ProcessId
                parent_pid = [int] $candidate.ParentProcessId
                executable_path = [string] $candidate.ExecutablePath
                start_time_utc = $native.StartTime.ToUniversalTime().ToString('o')
            }
            $changed = $true
        }
    }
}

function Stop-OwnedProcesses {
    foreach ($identity in @($OwnedProcesses.Values | Sort-Object start_time_utc -Descending)) {
        $native = Get-Process -Id $identity.pid -ErrorAction SilentlyContinue
        if (-not $native -or $native.HasExited) { continue }
        if ($native.StartTime.ToUniversalTime().ToString('o') -ne $identity.start_time_utc) { continue }
        if ($native.Path -ne $identity.executable_path) { continue }
        $native | Stop-Process -Force
    }
}

Assert-NoReparseAncestor $EvidenceRoot
Assert-NoReparseAncestor $SessionRoot
if (Test-Path -LiteralPath $EvidenceRoot) { throw 'Use a fresh evidence/session token.' }
New-Item -ItemType Directory -Path $EvidenceRoot | Out-Null
$ReceiptPath = Join-Path $EvidenceRoot 'level-editor-stream-session.json'
$receipt = [ordered]@{
    schema_version = 1
    issue = 364
    status = 'BLOCKED'
    launcher_sha = $ExpectedHead
    runtime_source_sha = $RuntimeSha
    runtime_source_run = '38084733503-1'
    session_root = $SessionRoot
    stream_source = 'LevelEditorViewport'
    viewer_url = $ViewerUrl
    lan_viewer_url_candidates = @()
    received_browser_frame = $false
    owner_handoff = $false
    owner_visual_status = 'PENDING_FINAL_M3'
    performance_status = 'DEFERRED_AFTER_M3'
    performance_pass = $false
    source_world_saved = $false
    started_at_utc = [DateTime]::UtcNow.ToString('o')
}

try {
    Push-Location -LiteralPath $RepoRoot
    try {
        $actual = (& git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or $actual -ne $ExpectedHead) { throw 'Launcher HEAD differs from its exact requested SHA.' }
        $changed = @(& git status --porcelain --untracked-files=no)
        if ($LASTEXITCODE -ne 0 -or $changed.Count) { throw 'Launcher requires an unchanged tracked checkout.' }
        & git check-ignore --no-index --quiet -- $ReceiptPath
        if ($LASTEXITCODE -ne 0) { throw 'Review evidence must remain ignored by Git.' }
    }
    finally { Pop-Location }
    $hostState = & (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
    $receipt.host_before = $hostState.status
    if ($hostState.status -ne 'IDLE') { throw "Shared Unreal host is occupied: $($hostState.status). Existing work keeps ownership." }
    $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object LocalPort -in @(80, 8888))
    if ($listeners.Count) { throw 'Epic viewer or streamer port is already occupied (80/8888).' }
    . (Join-Path $RepoRoot 'scripts/ci/Resolve-YacsUnrealEngine.ps1')
    $engine = Resolve-YacsUnrealEngine -ProjectPath (Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject')
    if (-not $engine -or $engine.Version -ne '5.8.2-56702186' -or -not $engine.UnrealEditorPath) { throw 'The inspected UE 5.8.2 CL 56702186 installation is required.' }
    $plugin = Join-Path $engine.Root 'Engine/Plugins/Media/PixelStreaming2/PixelStreaming2.uplugin'
    if ((Get-FileHash -LiteralPath $plugin -Algorithm SHA256).Hash.ToLowerInvariant() -ne '609e80122117d62b6affba640ec2d10c5168a41eee16c8d9768ca145abd59ea6') { throw 'PixelStreaming2 descriptor differs from the installed source inspection.' }
    $receipt.engine_identity = $engine.Identity
    Push-Location -LiteralPath $RepoRoot
    try {
        & python -m scripts.ue.prepare_level_editor_review --destination $SessionRoot --launcher-sha $ExpectedHead
        if ($LASTEXITCODE -ne 0) { throw 'Saved road snapshot preparation failed.' }
    }
    finally { Pop-Location }
    $preparationPath = Join-Path $SessionRoot 'level-editor-review-preparation.json'
    $preparation = Get-Content -LiteralPath $preparationPath -Raw | ConvertFrom-Json
    if ($preparation.status -ne 'READY_FOR_EDITOR_LAUNCH' -or $preparation.launcher_sha -ne $ExpectedHead -or $preparation.runtime_source_sha -ne $RuntimeSha) { throw 'Snapshot preparation receipt is not ready for this launch.' }
    $SnapshotOwned = $true
    Copy-Item -LiteralPath $preparationPath -Destination (Join-Path $EvidenceRoot 'level-editor-review-preparation.json')
    $sessionEvidence = Join-Path $SessionRoot 'Saved/LevelEditorStream'
    New-Item -ItemType Directory -Path $sessionEvidence | Out-Null
    $scenePath = Join-Path $sessionEvidence 'scene.json'
    $engineLog = Join-Path $sessionEvidence 'editor.log'
    $project = Join-Path $SessionRoot 'YetAnotherCyclingSim.uproject'
    $arguments = @(
        ('"' + $project + '"'), $Map,
        '-EnablePlugins=PixelStreaming2',
        '-DisablePlugins=ModelContextProtocol,Wingman,AndroidFileServer',
        '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorSource=LevelEditorViewport',
        '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorStartOnLaunch=True',
        '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorUseRemoteSignallingServer=False',
        '-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:ConnectionURL=ws://127.0.0.1:8888',
        '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
        '-ini:EditorPerProjectUserSettings:[/Script/UnrealEd.EditorLoadingSavingSettings]:bAutoSaveEnable=False',
        '-EditorPixelStreamingRes=1280x720', '-RenderOffscreen',
        '-NoP4', '-NoSplash', '-NoSound', '-NoLiveCoding', '-NoVSync',
        '-ExecCmds="t.MaxFPS 30"', '-ScriptErrorsAreFatal',
        ('-ExecutePythonScript="' + (Join-Path $PSScriptRoot 'bootstrap_level_editor_stream.py') + '"'),
        ('-AbsLog="' + $engineLog + '"')
    )
    $receipt.launch_arguments = $arguments
    $hostState = & (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
    if ($hostState.status -ne 'IDLE') { throw 'Another Unreal session acquired the host during snapshot preparation.' }
    $environmentKeys = @('RUNNER_TRACKING_ID', 'YACS_OWNER_HANDOFF', 'PYTHONPATH', 'PYTHONHOME', 'YACS_LEVEL_EDITOR_REVIEW_ROOT', 'YACS_LEVEL_EDITOR_LAUNCHER_SHA', 'YACS_LEVEL_EDITOR_PREPARATION_SHA256')
    $oldEnvironment = @{}
    foreach ($key in $environmentKeys) { $oldEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, 'Process') }
    try {
        # Existing repository owner-handoff convention: this requested review
        # remains alive after the Actions job; no unrelated process is adopted.
        foreach ($key in @('RUNNER_TRACKING_ID', 'YACS_OWNER_HANDOFF', 'PYTHONPATH', 'PYTHONHOME')) { [Environment]::SetEnvironmentVariable($key, '', 'Process') }
        $env:YACS_LEVEL_EDITOR_REVIEW_ROOT = $SessionRoot
        $env:YACS_LEVEL_EDITOR_LAUNCHER_SHA = $ExpectedHead
        $env:YACS_LEVEL_EDITOR_PREPARATION_SHA256 = (Get-FileHash -LiteralPath $preparationPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $EditorProcess = Start-Process -FilePath $engine.UnrealEditorPath -ArgumentList $arguments -WorkingDirectory $SessionRoot -PassThru
    }
    finally {
        foreach ($key in $environmentKeys) { [Environment]::SetEnvironmentVariable($key, $oldEnvironment[$key], 'Process') }
    }
    $OwnedProcesses[[string] $EditorProcess.Id] = [ordered]@{
        pid = $EditorProcess.Id
        parent_pid = $PID
        executable_path = $engine.UnrealEditorPath
        start_time_utc = $EditorProcess.StartTime.ToUniversalTime().ToString('o')
    }
    $receipt.editor_pid = $EditorProcess.Id
    $receipt.editor_start_time_utc = $EditorProcess.StartTime.ToUniversalTime().ToString('o')
    $deadline = [DateTime]::UtcNow.AddSeconds(240)
    $httpReady = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        $EditorProcess.Refresh()
        if ($EditorProcess.HasExited) { throw "Owned Editor exited during startup: $($EditorProcess.ExitCode)" }
        Observe-OwnedProcesses
        if (Test-Path -LiteralPath $scenePath) {
            $scene = Get-Content -LiteralPath $scenePath -Raw | ConvertFrom-Json
            if ($scene.status -ne 'VIEWPORT_SCENE_READY' -or $scene.editor_pid -ne $EditorProcess.Id) { throw 'Native viewport scene validation failed.' }
            try {
                $response = Invoke-WebRequest -Uri $ViewerUrl -TimeoutSec 3 -MaximumRedirection 0
                $httpReady = $response.StatusCode -eq 200 -and $response.Content -match '(?i)pixel.?stream|<video|<!doctype html'
            }
            catch { $httpReady = $false }
            if ($httpReady) { break }
        }
        Start-Sleep -Seconds 2
    }
    if (-not $httpReady) { throw 'The native viewport and Epic viewer did not become ready within 240 seconds.' }
    $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -in @(80, 8888))
    if (@($listeners.LocalPort | Select-Object -Unique).Count -ne 2) { throw 'Both Epic viewer and streamer listeners are required.' }
    foreach ($listener in $listeners) {
        if (-not $OwnedProcesses.ContainsKey([string] $listener.OwningProcess)) { throw 'A listener belongs to a process outside this review session.' }
    }
    $receipt.listeners = @($listeners | Select-Object LocalAddress, LocalPort, OwningProcess)
    Copy-Item -LiteralPath $scenePath -Destination (Join-Path $EvidenceRoot 'scene.json')
    foreach ($config in @(Get-NetIPConfiguration | Where-Object { $null -ne $_.IPv4DefaultGateway })) {
        foreach ($address in @($config.IPv4Address)) {
            if ($address.IPAddress -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)') {
                $receipt.lan_viewer_url_candidates += "http://$($address.IPAddress)/"
            }
        }
    }
    $receipt.status = 'HTTP_READY_CLIENT_PENDING'
    $clientRoot = Join-Path $EvidenceRoot 'client'
    & (Join-Path $PSScriptRoot 'Test-YacsLevelEditorStreamClient.ps1') -ViewerUrl $ViewerUrl -OutputRoot $clientRoot
    $clientPath = Join-Path $clientRoot 'level-editor-stream-client.json'
    if (Test-Path -LiteralPath $clientPath) {
        $client = Get-Content -LiteralPath $clientPath -Raw | ConvertFrom-Json
        $receipt.received_browser_frame = $client.received_browser_frame -eq $true
        if ($receipt.received_browser_frame) { $receipt.status = 'BROWSER_VIDEO_RECEIVED' }
    }
    $EditorProcess.Refresh()
    if ($EditorProcess.HasExited) { throw 'The owned Editor exited during the browser check.' }
    $HandedOff = $true
    $receipt.owner_handoff = $true
    $receipt.note = 'This retained review owns the host until closed. LAN candidate URLs require a client on the same reachable network.'
}
catch {
    $receipt.error = $_.Exception.Message
    $receipt.status = 'BLOCKED'
    throw
}
finally {
    Observe-OwnedProcesses
    if (-not $HandedOff) { Stop-OwnedProcesses }
    $receipt.owned_processes = @($OwnedProcesses.Values)
    $receipt.finished_at_utc = [DateTime]::UtcNow.ToString('o')
    $receipt | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $ReceiptPath -Encoding utf8
    if ($SnapshotOwned -and (Test-Path -LiteralPath (Join-Path $SessionRoot 'Saved/LevelEditorStream/editor.log'))) {
        Copy-Item -LiteralPath (Join-Path $SessionRoot 'Saved/LevelEditorStream/editor.log') -Destination (Join-Path $EvidenceRoot 'editor.log')
    }
    if ($SnapshotOwned) {
        Copy-Item -LiteralPath $ReceiptPath -Destination (Join-Path $SessionRoot 'level-editor-stream-session.json')
        $nativeScene = Join-Path $SessionRoot 'Saved/LevelEditorStream/scene.json'
        if (Test-Path -LiteralPath $nativeScene) {
            Copy-Item -LiteralPath $nativeScene -Destination (Join-Path $EvidenceRoot 'scene.json') -Force
        }
    }
    Write-Host ('YACS_LEVEL_EDITOR_STREAM ' + ($receipt | ConvertTo-Json -Depth 12 -Compress))
}
