#requires -Version 7.4
<#
.SYNOPSIS
  Validate one limited, interactive Task Scheduler principal by Windows SID.
.DESCRIPTION
  Task Scheduler may return Principal.UserId as the user's SID, even when
  New-ScheduledTaskPrincipal was given DOMAIN\User. Never compare those raw
  string representations; resolve both via Windows identity APIs.

  This module is read-only and never registers, starts or stops a task.
#>
Set-StrictMode -Version Latest

function Resolve-YacsLiveWindowsSid {
  [CmdletBinding()]
  param([Parameter(Mandatory)][string]$UserId)

  if ([string]::IsNullOrWhiteSpace($UserId)) {
    throw 'Task Scheduler principal UserId is blank.'
  }

  try {
    if ($UserId -match '^S-1-\d+-') {
      return ([Security.Principal.SecurityIdentifier]::new($UserId)).Value
    }
    return ([Security.Principal.NTAccount]::new($UserId)).Translate(
      [Security.Principal.SecurityIdentifier]
    ).Value
  } catch {
    throw "Task Scheduler principal UserId cannot resolve to a Windows SID: $($_.Exception.GetType().Name)"
  }
}

function Assert-YacsLiveTaskPrincipal {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][object]$Task,
    [Parameter(Mandatory)][string]$ExpectedSid
  )

  if ($ExpectedSid -notmatch '^S-1-\d+-') {
    throw 'Expected Windows desktop SID is malformed.'
  }

  $principal = $Task.Principal
  if ($null -eq $principal) {
    throw 'Task Scheduler returned no principal.'
  }
  $actualSid = Resolve-YacsLiveWindowsSid -UserId ([string]$principal.UserId)
  if ($actualSid -cne $ExpectedSid) {
    throw 'Task principal SID differs from the logged-in console user.'
  }
  # ScheduledTasks returns 'Interactive' in some API versions; Windows Task
  # Scheduler API documentation calls the same mode INTERACTIVE_TOKEN.
  # Both map to an interactive user token, never S4U/Password/ServiceAccount.
  $logonType = [string]$principal.LogonType
  if ($logonType -notin @('Interactive','InteractiveToken')) {
    throw "Task is not interactive logon type: $logonType"
  }
  if ([string]$principal.RunLevel -ne 'Limited') {
    throw "Task requires a limited (non-elevated) token: $($principal.RunLevel)"
  }
  return [pscustomobject]@{
    sid=$actualSid
    logon_type=$logonType
    run_level='Limited'
    status='LIMITED_INTERACTIVE_DESKTOP_SID_VERIFIED'
  }
}
