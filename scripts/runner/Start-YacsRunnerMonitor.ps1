#requires -Version 7.4
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$RunnerRoot,
    [ValidateRange(5, 120)][int]$PollSeconds = 5,
    [ValidateRange(5, 240)][int]$QuietMinutes = 20
)
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'The tray monitor requires Windows and an interactive desktop.' }
if (-not [Environment]::UserInteractive -or (Get-Process -Id $PID).SessionId -eq 0) {
    throw 'Start this companion in the logged-in desktop session, not as a service.'
}
Import-Module (Join-Path $PSScriptRoot 'RunnerMonitor.psm1') -Force
$RunnerRoot = (Resolve-Path -LiteralPath $RunnerRoot).Path
$diag = Join-Path $RunnerRoot '_diag'
if (-not (Test-Path -LiteralPath $diag)) { throw "Missing runner diagnostics: $diag" }
$identity = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($RunnerRoot.ToLowerInvariant()))).Substring(0,16)
$mutex = [Threading.Mutex]::new($false, "Local\YacsRunnerMonitor-$identity")
try { $owned = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $owned = $true }
if (-not $owned) { $mutex.Dispose(); exit 0 }
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$logDirectory = Join-Path $PSScriptRoot 'logs'
$script:cursors = @{}
$script:job = ''
$script:quietWarned = $false
$script:lastActivity = [DateTime]::UtcNow
$script:lastHealth = [DateTime]::MinValue
$script:lastError = ''
$script:lastWorkerWrite = [DateTime]::MinValue
$script:muted = $false
$script:initial = $true
$script:status = 'Waiting for runner activity'
$icon = [Windows.Forms.NotifyIcon]::new()
$icon.Icon = [Drawing.SystemIcons]::Information
$icon.Text = 'YACS runner monitor'
$menu = [Windows.Forms.ContextMenuStrip]::new()
$context = [Windows.Forms.ApplicationContext]::new()
function Show-Notice([string]$Title, [string]$Message, [string]$Severity = 'Info') {
    if (-not $script:muted) { $icon.ShowBalloonTip(8000, $Title, $Message, [Windows.Forms.ToolTipIcon]::$Severity) }
}
$statusItem = $menu.Items.Add('Status')
$statusItem.add_Click({ [void][Windows.Forms.MessageBox]::Show($script:status, 'YACS runner') })
$actionsItem = $menu.Items.Add('Open GitHub Actions')
$actionsItem.add_Click({ Start-Process 'https://github.com/karnalooch/YetAnotherCyclingSim/actions' })
$logsItem = $menu.Items.Add('Open runner diagnostics')
$logsItem.add_Click({ Start-Process explorer.exe -ArgumentList ('"' + $diag + '"') })
$liveItem = $menu.Items.Add('Live job diagnostics')
$liveItem.add_Click({
    $viewer = Join-Path $PSScriptRoot 'Show-YacsRunnerLog.ps1'
    $argsText = '-NoLogo -NoProfile -NoExit -File "{0}" -RunnerRoot "{1}"' -f $viewer, $RunnerRoot
    Start-Process (Join-Path $PSHOME 'pwsh.exe') -ArgumentList $argsText
})
$monitorItem = $menu.Items.Add('Open monitor log')
$monitorItem.add_Click({ Start-Process notepad.exe -ArgumentList ('"' + (Join-Path $logDirectory 'monitor.jsonl') + '"') })
$testItem = $menu.Items.Add('Test notification')
$testItem.add_Click({ Show-Notice 'YACS - test' 'Desktop notifications are available. This is not a build result.' })
$muteItem = $menu.Items.Add('Mute notifications')
$muteItem.CheckOnClick = $true
$muteItem.add_Click({ $script:muted = $muteItem.Checked })
$exitItem = $menu.Items.Add('Exit monitor')
$exitItem.add_Click({ $context.ExitThread() })
$icon.ContextMenuStrip = $menu
$icon.add_BalloonTipClicked({ Start-Process 'https://github.com/karnalooch/YetAnotherCyclingSim/actions' })
$icon.Visible = $true
$timer = [Windows.Forms.Timer]::new()
$timer.Interval = $PollSeconds * 1000
$timer.add_Tick({
    try {
        $files = @(Get-ChildItem -LiteralPath $diag -Filter 'Runner_*.log' -File | Sort-Object Name | Select-Object -Last 2)
        foreach ($file in $files) {
            if (-not $script:cursors.ContainsKey($file.FullName)) {
                $script:cursors[$file.FullName] = @{}
                if ($script:initial) {
                    # Bootstrap state without replaying old completion notifications.
                    foreach ($line in (Get-Content -LiteralPath $file.FullName -Tail 200)) {
                        $event = ConvertFrom-YacsRunnerLine $line
                        if ($event -and $event.Kind -eq 'started') { $script:job = $event.Job }
                        if ($event -and $event.Kind -eq 'completed') { $script:job = '' }
                    }
                    $script:cursors[$file.FullName] = @{ Offset = $file.Length; Pending = ''; Decoder = [Text.Encoding]::UTF8.GetDecoder() }
                }
            }
            foreach ($line in (Read-YacsLogDelta $file.FullName $script:cursors[$file.FullName])) {
                $event = ConvertFrom-YacsRunnerLine $line
                if (-not $event) { continue }
                $script:lastActivity = [DateTime]::UtcNow
                $script:quietWarned = $false
                Write-YacsMonitorRecord $logDirectory @{ kind = $event.Kind; job = $event.Job; result = $event.Result }
                if ($event.Kind -eq 'started') {
                    $script:job = $event.Job
                    $icon.Icon = [Drawing.SystemIcons]::Application
                } else {
                    $script:job = ''
                    $success = $event.Result -in @('Succeeded', 'SucceededWithIssues')
                    $icon.Icon = if ($success) { [Drawing.SystemIcons]::Information } else { [Drawing.SystemIcons]::Warning }
                    $severity = if ($event.Result -eq 'Succeeded') { 'Info' } else { 'Warning' }
                    Show-Notice 'YACS - job completed' ($event.Job + ': ' + $event.Result) $severity
                }
            }
        }
        foreach ($key in @($script:cursors.Keys)) {
            if ($key -notin $files.FullName) { $script:cursors.Remove($key) }
        }
        $script:initial = $false
        $worker = Get-ChildItem -LiteralPath $diag -Filter 'Worker_*.log' -File | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
        if ($worker -and $worker.LastWriteTimeUtc -gt $script:lastWorkerWrite) {
            $script:lastWorkerWrite = $worker.LastWriteTimeUtc
            if ($worker.LastWriteTimeUtc -gt $script:lastActivity) { $script:lastActivity = $worker.LastWriteTimeUtc }
            $script:quietWarned = $false
        }
        $quiet = ([DateTime]::UtcNow - $script:lastActivity).TotalMinutes
        if ($script:job -and $quiet -ge $QuietMinutes -and -not $script:quietWarned) {
            Show-Notice 'YACS - check progress' "No diagnostic writes for $QuietMinutes minutes. This does not prove a hang." 'Warning'
            Write-YacsMonitorRecord $logDirectory @{ kind = 'quiet'; job = $script:job; quietMinutes = [Math]::Round($quiet, 1) }
            $script:quietWarned = $true
        }
        if (([DateTime]::UtcNow - $script:lastHealth).TotalSeconds -ge 60) {
            $serviceState = 'not configured'
            $serviceFile = Join-Path $RunnerRoot '.service'
            if (Test-Path -LiteralPath $serviceFile) {
                $serviceName = (Get-Content -LiteralPath $serviceFile -Raw).Trim()
                $service = Get-Service -Name $serviceName -ErrorAction Stop
                $serviceState = [string]$service.Status
            }
            $os = Get-CimInstance Win32_OperatingSystem
            $disk = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($RunnerRoot))
            $script:status = "Service: $serviceState`nLast observed job: $($script:job)`nFree RAM: $([Math]::Round($os.FreePhysicalMemory / 1MB, 1)) GiB`nFree disk: $([Math]::Round($disk.AvailableFreeSpace / 1GB, 1)) GiB`nDiagnostics: $diag"
            Write-YacsMonitorRecord $logDirectory @{ kind = 'health'; service = $serviceState; job = $script:job; freeRamGiB = [Math]::Round($os.FreePhysicalMemory / 1MB, 2); freeDiskGiB = [Math]::Round($disk.AvailableFreeSpace / 1GB, 2); quietMinutes = [Math]::Round($quiet, 1) }
            $script:lastHealth = [DateTime]::UtcNow
        }
        $tip = if ($script:job) { 'YACS: ' + $script:job } else { 'YACS: no active job observed' }
        $icon.Text = $tip.Substring(0, [Math]::Min(63, $tip.Length))
        $script:lastError = ''
    } catch {
        $icon.Icon = [Drawing.SystemIcons]::Error
        $script:status = 'Monitor error: ' + $_.Exception.Message
        if ($script:lastError -ne $script:status) {
            $script:lastError = $script:status
            Show-Notice 'YACS - monitor error' 'Unable to read runner status. Open Status from the tray menu.' 'Error'
            # Do not persist arbitrary exception text or raw diagnostic lines.
            try { Write-YacsMonitorRecord $logDirectory @{ kind = 'monitor_error'; type = $_.Exception.GetType().Name } } catch { [Console]::Error.WriteLine('Monitor log unavailable.') }
        }
    }
})
try {
    Write-YacsMonitorRecord $logDirectory @{ kind = 'monitor_started'; runner = $RunnerRoot }
    $timer.Start()
    [Windows.Forms.Application]::Run($context)
} finally {
    $timer.Stop(); $timer.Dispose(); $icon.Visible = $false; $icon.Dispose(); $menu.Dispose(); $context.Dispose()
    $mutex.ReleaseMutex(); $mutex.Dispose()
}
