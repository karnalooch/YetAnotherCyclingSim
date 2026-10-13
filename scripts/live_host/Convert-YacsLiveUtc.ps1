#requires -Version 7.4
<#
.SYNOPSIS
  Convert persisted UTC timestamps without locale-dependent string roundtrips.
.DESCRIPTION
  ConvertFrom-Json can automatically materialize "2026-10-12T...Z" as a
  System.DateTime. Casting that value to [string] loses ISO ordering, the UTC
  suffix and fractional seconds; parsing its Polish "12.10.2026" representation
  under en-US can silently turn 12 October into 10 December.

  Preserve the typed DateTime/DateTimeOffset instant. Accept string input only
  if it is ISO8601 with an explicit UTC/offset designator. Never guess timezone.
#>
Set-StrictMode -Version Latest

function ConvertTo-YacsLiveUtc {
  [CmdletBinding()]
  param([Parameter(Mandatory)][AllowNull()][object]$Value)

  if ($Value -is [DateTimeOffset]) {
    return $Value.UtcDateTime
  }
  if ($Value -is [DateTime]) {
    if ($Value.Kind -eq [DateTimeKind]::Unspecified) {
      throw 'Live Host timestamp has no timezone; refuse to guess UTC.'
    }
    return $Value.ToUniversalTime()
  }
  if ($Value -is [string] -and $Value -cmatch
    '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|[+-]\d{2}:\d{2})$') {
    return [DateTimeOffset]::Parse(
      $Value,
      [Globalization.CultureInfo]::InvariantCulture,
      [Globalization.DateTimeStyles]::None
    ).UtcDateTime
  }
  throw 'Live Host timestamp must be a timezone-aware ISO string or typed DateTime.'
}

function Test-YacsLiveStartIdentity {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][AllowNull()][object]$ExpectedUtc,
    [Parameter(Mandatory)][datetime]$ObservedStart,
    [double]$ToleranceMilliseconds = 1000
  )
  if ($ToleranceMilliseconds -lt 0 -or $ToleranceMilliseconds -gt 1000) {
    throw 'Invalid bounded process timestamp tolerance.'
  }
  $expected=ConvertTo-YacsLiveUtc -Value $ExpectedUtc
  $actual=$ObservedStart.ToUniversalTime()
  return ([Math]::Abs(($actual-$expected).TotalMilliseconds) -le $ToleranceMilliseconds)
}
