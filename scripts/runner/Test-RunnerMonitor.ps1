#requires -Version 7.4
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot 'RunnerMonitor.psm1') -Force
function Assert($condition, [string]$message) { if (-not $condition) { throw $message } }
$root = Join-Path ([IO.Path]::GetTempPath()) ('yacs-monitor-test-' + [Guid]::NewGuid())
[void][IO.Directory]::CreateDirectory($root)
try {
    $prefix = '[2026-10-02 18:00:00Z INFO Terminal] WRITE LINE: '
    Assert ($null -eq (ConvertFrom-YacsRunnerLine '[INFO StepsRunner] Step result: Succeeded')) 'Step success must not complete a job.'
    Assert ($null -eq (ConvertFrom-YacsRunnerLine '[INFO Worker] Job completed.')) 'Worker completion without result must not imply success.'
    $event = ConvertFrom-YacsRunnerLine ($prefix + '2026-10-02 18:00:00Z: Running job: BOB test')
    Assert ($event.Kind -eq 'started' -and $event.Job -eq 'BOB test') 'Start marker parsing failed.'
    foreach ($result in @('Succeeded', 'Failed', 'Canceled', 'Abandoned', 'SucceededWithIssues', 'Unknown')) {
        $event = ConvertFrom-YacsRunnerLine ($prefix + "Job BOB test completed with result: $result")
        Assert ($event.Kind -eq 'completed' -and $event.Result -eq $result) "Result lost: $result"
    }
    $path = Join-Path $root 'Runner_test.log'
    $cursor = @{}
    [IO.File]::WriteAllText($path, 'first', [Text.Encoding]::UTF8)
    Assert (@(Read-YacsLogDelta $path $cursor).Count -eq 0) 'Partial record must wait for newline.'
    [IO.File]::AppendAllText($path, " line`nsecond`n", [Text.Encoding]::UTF8)
    $lines = @(Read-YacsLogDelta $path $cursor)
    Assert ($lines.Count -eq 2 -and $lines[0].TrimStart([char]0xFEFF) -eq 'first line') 'Partial record assembly failed.'
    Assert (@(Read-YacsLogDelta $path $cursor).Count -eq 0) 'Records must not replay.'
    [IO.File]::WriteAllText($path, "new`n", [Text.UTF8Encoding]::new($false))
    Assert (@(Read-YacsLogDelta $path $cursor)[0] -eq 'new') 'Truncation must reset cursor.'
    $unicode = [Text.Encoding]::UTF8.GetBytes("zażółć`n")
    [IO.File]::WriteAllBytes($path, $unicode[0..2])
    $cursor = @{}
    [void]@(Read-YacsLogDelta $path $cursor)
    $append = [IO.File]::Open($path, 'Append', 'Write')
    try { $append.Write($unicode, 3, $unicode.Length - 3) } finally { $append.Dispose() }
    Assert (@(Read-YacsLogDelta $path $cursor)[0] -eq 'zażółć') 'Split UTF-8 code point must survive.'
    # A large input is consumed incrementally, with no dropped or duplicated lines.
    [IO.File]::WriteAllText($path, ("0123456789`n" * 50000), [Text.UTF8Encoding]::new($false))
    $cursor = @{}; $count = 0
    do { $count += @(Read-YacsLogDelta $path $cursor).Count } while ($cursor.Offset -lt (Get-Item $path).Length)
    Assert ($count -eq 50000) 'Bounded reader lost lines across chunks.'
    $log = Join-Path $root 'monitor.jsonl'
    for ($i = 0; $i -lt 8; $i++) {
        [IO.File]::WriteAllText($log, ('x' * 2MB))
        Write-YacsMonitorRecord $root @{ kind = 'health' }
    }
    Assert (@(Get-ChildItem $root -Filter 'monitor*.jsonl').Count -eq 6) 'Retention must bound history to five archives plus current.'
    Assert ((Get-Content $log | ConvertFrom-Json).kind -eq 'health') 'Current record is invalid JSON.'
    foreach ($file in Get-ChildItem $PSScriptRoot -Include '*.ps1', '*.psm1' -Recurse) {
        $tokens = $null; $errors = $null
        [void][Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$errors)
        Assert ($errors.Count -eq 0) ("Parser errors in " + $file.Name + ': ' + ($errors | Out-String))
    }
    Write-Host 'PASS: job result authority, partial lines, UTF-8, truncation, bounded reads, no replay, rotation and syntax.'
} finally { Remove-Item -LiteralPath $root -Recurse -Force }
