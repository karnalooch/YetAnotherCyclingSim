#requires -Version 7.5
<#
.SYNOPSIS
  Read a bounded diagnostic excerpt for the one failed Lesson07 observer call.
.DESCRIPTION
  Requires this run's successful, fresh existing-Editor discovery. Reads only
  the fixed launcher log, never calls Unreal, and never retries the observer.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedHead,
  [Parameter(Mandatory)][ValidatePattern('^[0-9]+-[0-9]+$')][string]$RunToken
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Assert-L07FailurePlainPath([string]$Path) {
  $base='D:\yacs'
  $cursor=[IO.Path]::GetFullPath($Path)
  if (-not $cursor.StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'FAILURE_LOG_PATH' }
  while ($cursor.Length -ge $base.Length) {
    $item=Get-Item -LiteralPath $cursor -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'FAILURE_LOG_REPARSE_POINT' }
    if ($cursor -ieq $base) { return }
    $cursor=[IO.Path]::GetDirectoryName($cursor)
  }
  throw 'FAILURE_LOG_BOUNDARY'
}

function Read-L07FailureProof([string]$Path) {
  Assert-L07FailurePlainPath $Path
  $before=Get-Item -LiteralPath $Path
  if ($before.PSIsContainer -or $before.Length -le 0 -or $before.Length -gt 64KB) { throw 'FAILURE_LOG_PROOF_SIZE' }
  $bytes=[IO.File]::ReadAllBytes($Path)
  $after=Get-Item -LiteralPath $Path
  if ($bytes.Length -ne $before.Length -or $after.Length -ne $before.Length -or
      $after.LastWriteTimeUtc -ne $before.LastWriteTimeUtc) { throw 'FAILURE_LOG_PROOF_CHANGED' }
  return ([Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json -AsHashtable -DateKind String)
}

function Assert-L07FailureIdentity([Collections.IDictionary]$Identity,[string]$Head,[DateTimeOffset]$Now) {
  if ($Identity.status -isnot [string] -or $Identity.status -cne 'L07_WINGMAN_HOST_IDENTITY_VERIFIED' -or
      $Identity.source_commit -isnot [string] -or $Identity.source_commit -cne $Head -or
      $Identity.pid -isnot [long] -or $Identity.pid -ne 17896 -or
      $Identity.process_start_filetime_utc -isnot [string] -or
      $Identity.process_start_filetime_utc -cne '134370120000674689' -or
      $Identity.executable -isnot [string] -or
      $Identity.executable -cne 'D:\yacs\engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe' -or
      $Identity.project -isnot [string] -or $Identity.project -cne 'D:\yacs\project\YetAnotherCyclingSim.uproject' -or
      $Identity.canonical_project_argument_matches -isnot [bool] -or -not $Identity.canonical_project_argument_matches -or
      $Identity.observed_utc -isnot [string]) { throw 'FAILURE_LOG_IDENTITY' }
  $stamp=[DateTimeOffset]::Parse($Identity.observed_utc,[Globalization.CultureInfo]::InvariantCulture)
  $age=($Now-$stamp).TotalSeconds
  if ($age -lt 0 -or $age -gt 120) { throw 'FAILURE_LOG_STALE_IDENTITY' }
}

function Assert-L07FailureDiscovery([Collections.IDictionary]$Probe,[string]$Head,[DateTimeOffset]$Now) {
  if ($Probe.status -isnot [string] -or $Probe.status -cne 'BRIDGE_DISCOVERY_COMPLETE_NATIVE_READBACK_PENDING' -or
      $Probe.source_commit -isnot [string] -or $Probe.source_commit -cne $Head -or
      $Probe.existing_editor_only_requested -isnot [bool] -or -not $Probe.existing_editor_only_requested -or
      $Probe.identity_stable_across_probe -isnot [bool] -or -not $Probe.identity_stable_across_probe -or
      $Probe.native_tool_call_attempts -isnot [long] -or $Probe.native_tool_call_attempts -ne 0 -or
      $Probe.editor_started_or_stopped -isnot [bool] -or $Probe.editor_started_or_stopped) { throw 'FAILURE_LOG_DISCOVERY' }
  foreach ($name in @('owner_before','owner_after')) {
    $owner=$Probe[$name]
    if ($owner -isnot [Collections.IDictionary] -or $owner.status -isnot [string] -or $owner.status -cne 'ATTACH_EXISTING' -or
        $owner.owner_sid_matches -isnot [bool] -or -not $owner.owner_sid_matches -or
        $owner.editor -isnot [Collections.IDictionary] -or
        $owner.editor.editor_pid -isnot [long] -or $owner.editor.editor_pid -ne 17896 -or
        $owner.editor.editor_start_filetime_utc -isnot [string] -or
        $owner.editor.editor_start_filetime_utc -cne '134370120000674689') { throw 'FAILURE_LOG_OWNER' }
  }
  Assert-L07FailureIdentity $Probe.identity_before $Head $Now
  Assert-L07FailureIdentity $Probe.identity_after $Head $Now
}

function Protect-L07FailureText([string]$Text) {
  # Redact before truncation, including credential-bearing URLs and headers.
  $safe=$Text -replace '(?i)\bBearer\s+[^\s,;]+','Bearer [REDACTED]'
  $safe=$safe -replace '(?i)(authorization\s*[:=]).*$','$1 [REDACTED]'
  $safe=$safe -replace '(?i)(["'']?(?:access[_-]?token|refresh[_-]?token|token|api[_-]?key|secret|password)["'']?\s*[:=]).*$','$1 [REDACTED]'
  $safe=$safe -replace '(?i)https?://[^\s]+','[URL OMITTED]'
  $safe=$safe -replace '[\p{Cc}\p{Cf}]',' '
  if ($safe.Length -gt 768) { $safe=$safe.Substring(0,768)+' [TRUNCATED]' }
  return $safe
}

function Select-L07FailureLines([string]$Text) {
  $records=[Collections.Generic.List[object]]::new()
  $matched=0
  foreach ($line in ($Text -split '\r?\n')) {
    # UE's bracket timestamp is observed in retained repository logs. Both
    # UTC and host-local windows are labelled; neither is silently assumed.
    if ($line -notmatch '^\[(?<stamp>(?:2026\.10\.20-23|2026\.10\.21-01)\.48\.(?<second>\d{2}):\d{3})\]\[[^\]]{1,8}\](?<body>.*)$') { continue }
    if ([int]$Matches.second -gt 30) { continue }
    $stamp=$Matches.stamp; $body=$Matches.body
    if ($body -notmatch '(?i)LogPython|Loco|Wingman|execute_python|\bError\b|\bWarning\b|Traceback') { continue }
    $matched++
    if ($records.Count -ge 24) { continue }
    $records.Add([ordered]@{
      log_timestamp=$stamp
      time_basis= $(if ($stamp.StartsWith('2026.10.20-23')) { 'UTC_CANDIDATE' } else { 'WARSAW_LOCAL_CANDIDATE' })
      text=(Protect-L07FailureText $body)
    })
  }
  return [ordered]@{records=$records.ToArray();matching_lines=$matched;truncated=($matched -gt $records.Count)}
}

function Assert-L07FailureProcess {
  $editor=Get-Process -Id 17896 -ErrorAction Stop
  if ($editor.HasExited -or $editor.Path -cne 'D:\yacs\engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe' -or
      $editor.StartTime.ToUniversalTime().ToFileTimeUtc().ToString() -cne '134370120000674689') { throw 'FAILURE_LOG_PROCESS_CHANGED' }
}

$reportRoot=Join-Path 'D:\yacs\lesson07-remote\reports' $RunToken
$logPath='D:\yacs\lesson07-remote\editor.log'
Assert-L07FailurePlainPath $reportRoot
$proof=Read-L07FailureProof (Join-Path $reportRoot 'probe.json')
$identity=Read-L07FailureProof (Join-Path $reportRoot 'identity.json')
$now=[DateTimeOffset]::UtcNow
Assert-L07FailureDiscovery $proof $ExpectedHead $now
Assert-L07FailureIdentity $identity $ExpectedHead $now
Assert-L07FailureProcess
$report=[ordered]@{
  schema_version=1; source_commit=$ExpectedHead; observed_utc=$now.ToString('o')
  status='LOG_UNAVAILABLE'; failed_observer_source='f485b18217deba19bc881aa78d22e5f862d13e3e'
  failed_observer_utc='2026-10-20T23:48:13.521280Z'; source_path=$logPath
  process_id=17896; process_start_filetime_utc='134370120000674689'
  read_limit_bytes=4MB; output_limit_bytes=32KB; native_tool_calls=0
  records=@(); matching_lines=0; truncated=$false
}
if (Test-Path -LiteralPath $logPath -PathType Leaf) {
  Assert-L07FailurePlainPath $logPath
  $stream=[IO.File]::Open($logPath,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
  try {
    $length=$stream.Length; $offset=[Math]::Max(0,$length-4MB)
    $null=$stream.Seek($offset,[IO.SeekOrigin]::Begin)
    $bytes=[byte[]]::new([int]($length-$offset))
    $stream.ReadExactly($bytes,0,$bytes.Length)
    $report.source_length_at_open=$length; $report.read_offset_bytes=$offset
    $report.read_bytes=$bytes.Length
    $report.read_sha256=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
  } finally { $stream.Dispose() }
  $text=[Text.Encoding]::UTF8.GetString($bytes)
  if ($offset -gt 0) {
    $firstBreak=$text.IndexOf("`n")
    $text=if ($firstBreak -ge 0) { $text.Substring($firstBreak+1) } else { '' }
  }
  $lastBreak=$text.LastIndexOf("`n")
  $text=if ($lastBreak -ge 0) { $text.Substring(0,$lastBreak+1) } else { '' }
  $selected=Select-L07FailureLines $text
  $report.records=$selected.records; $report.matching_lines=$selected.matching_lines; $report.truncated=$selected.truncated
  $report.status=if ($selected.matching_lines) { 'BOUNDED_FAILURE_LOG_EXCERPT' } else { 'NO_MATCHING_FAILURE_RECORDS_IN_BOUNDED_TAIL' }
}
Assert-L07FailureProcess
do {
  $encoded=[Text.UTF8Encoding]::new($false).GetBytes(($report | ConvertTo-Json -Depth 12 -Compress)+"`n")
  if ($encoded.Length -le 32KB) { break }
  if ($report.records.Count -eq 0) { throw 'FAILURE_LOG_OUTPUT_SIZE' }
  $report.records=@($report.records | Select-Object -SkipLast 1); $report.truncated=$true
} while ($true)
$outputPath=Join-Path $reportRoot 'observer-failure-log.json'
$output=[IO.File]::Open($outputPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try { $output.Write($encoded,0,$encoded.Length) } finally { $output.Dispose() }
Write-Host ('L07_OBSERVER_FAILURE_LOG '+$report.status+' records='+$report.records.Count)
