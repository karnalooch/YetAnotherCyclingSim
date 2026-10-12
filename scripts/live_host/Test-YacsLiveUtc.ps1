#requires -Version 7.4
<#
.SYNOPSIS
  Portable, read-only regressions for typed JSON UTC fields and PID identity.
.DESCRIPTION
  Does not inspect, modify, restart or install any real Windows task or Editor.
  Recreates the owner's two true date values from the live f4a0366a session.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Convert-YacsLiveUtc.ps1')

function Need([bool]$Passed,[string]$Description) {
  if (-not $Passed) { throw "YACS UTC regression failed: $Description" }
}
function MustReject([object]$Value,[string]$Description) {
  $rejected=$false
  try { ConvertTo-YacsLiveUtc -Value $Value | Out-Null } catch { $rejected=$true }
  Need $rejected $Description
}

# Original JSON source (saved by ToString("o")), before ConvertFrom-Json turns
# date strings into [DateTime], whose later [string] cast is culture-dependent.
$heartbeatJson='{"last_seen_utc":"2026-10-12T21:51:52.6404140Z"}'
$startedJson='{"editor_started_utc":"2026-10-12T21:41:03.5969630Z"}'
$heartbeat=$heartbeatJson | ConvertFrom-Json
$started=$startedJson | ConvertFrom-Json
$correctHeartbeat=[datetime]::ParseExact(
  '2026-10-12T21:51:52.6404140Z','o',
  [Globalization.CultureInfo]::InvariantCulture,
  [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
$correctStart=[datetime]::ParseExact(
  '2026-10-12T21:41:03.5969630Z','o',
  [Globalization.CultureInfo]::InvariantCulture,
  [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()

$previousCulture=[Threading.Thread]::CurrentThread.CurrentCulture
$previousUiCulture=[Threading.Thread]::CurrentThread.CurrentUICulture
try {
  foreach($culture in @('pl-PL','en-US')) {
    [Threading.Thread]::CurrentThread.CurrentCulture=
      [Globalization.CultureInfo]::GetCultureInfo($culture)
    [Threading.Thread]::CurrentThread.CurrentUICulture=
      [Globalization.CultureInfo]::GetCultureInfo($culture)

    $utc=ConvertTo-YacsLiveUtc -Value $heartbeat.last_seen_utc
    Need ($utc.Kind -eq [DateTimeKind]::Utc) "$culture must retain UTC Kind"
    Need ($utc.Ticks -eq $correctHeartbeat.Ticks) "$culture lost 100ns fidelity"

    $utcFromRaw=ConvertTo-YacsLiveUtc -Value '2026-10-12T21:51:52.6404140Z'
    Need ($utcFromRaw.Ticks -eq $utc.Ticks) "$culture ISO source disagrees with typed JSON"

    $now=$utc.AddSeconds(5)
    $age=($now-$utc).TotalSeconds
    Need ($age -eq 5) "$culture misread 12 October as December"

    Need (Test-YacsLiveStartIdentity -ExpectedUtc $started.editor_started_utc -ObservedStart $correctStart) "$culture same PID start was rejected"
    Need (-not (Test-YacsLiveStartIdentity -ExpectedUtc $started.editor_started_utc -ObservedStart $correctStart.AddSeconds(2))) "$culture unrelated reused PID time admitted"
    Need (-not (Test-YacsLiveStartIdentity -ExpectedUtc $started.editor_started_utc -ObservedStart $correctStart.AddDays(59))) "$culture swapped month/day"
  }
} finally {
  [Threading.Thread]::CurrentThread.CurrentCulture=$previousCulture
  [Threading.Thread]::CurrentThread.CurrentUICulture=$previousUiCulture
}

MustReject '12.10.2026 21:51:52' 'Localized ambiguous timestamp must never be reparsed'
MustReject '2026-10-12T21:51:52' 'Missing UTC/offset must be rejected'
MustReject ([datetime]::SpecifyKind($correctHeartbeat,[DateTimeKind]::Unspecified)) 'Ambiguous DateTime.Kind must be rejected'
MustReject $null 'Null instant must be rejected'
Write-Host 'YACS_LIVE_UTC_TEST_PASS cultures=pl-PL,en-US ISO_and_typed_JSON=PASS PID=PASS'
