#requires -Version 7.4
<#
.SYNOPSIS
  Offline identity normalization regressions for task principal Verify/Uninstall.
.DESCRIPTION
  Pure synthetic principals. Never reads/writes task registrations, never starts
  Unreal, never changes the runner or user sessions.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if (-not $IsWindows) { throw 'Task principal SID tests require Windows.' }
. (Join-Path $PSScriptRoot 'Assert-YacsLiveTaskPrincipal.ps1')

function Require([bool]$Condition,[string]$Message) {
  if (-not $Condition) { throw $Message }
}
function SyntheticTask([string]$UserId,[string]$LogonType,[string]$RunLevel) {
  return [pscustomobject]@{
    Principal=[pscustomobject]@{
      UserId=$UserId
      LogonType=$LogonType
      RunLevel=$RunLevel
    }
  }
}
function ExpectReject([object]$Task,[string]$ExpectedSid,[string]$Reason) {
  $rejected=$false
  try {
    Assert-YacsLiveTaskPrincipal -Task $Task -ExpectedSid $ExpectedSid | Out-Null
  } catch {
    $rejected=$true
  }
  Require $rejected "Unsafe Task Scheduler principal accepted: $Reason"
}

$current=[Security.Principal.WindowsIdentity]::GetCurrent()
$name=$current.Name
$correctSid=$current.User.Value
Require ($correctSid -match '^S-1-\d+-') 'Actual test Windows SID invalid'
$accountProof=Resolve-YacsLiveWindowsSid -UserId $name
Require ($accountProof -ceq $correctSid) 'Windows identity SID translation differs'

foreach($type in @('Interactive','InteractiveToken')) {
  foreach($user in @($name,$correctSid)) {
    $task=SyntheticTask -UserId $user -LogonType $type -RunLevel 'Limited'
    $proof=Assert-YacsLiveTaskPrincipal -Task $task -ExpectedSid $correctSid
    Require ($proof.sid -ceq $correctSid -and
      $proof.status -ceq 'LIMITED_INTERACTIVE_DESKTOP_SID_VERIFIED') 'Valid Windows user representation wrongly rejected'
  }
}

$otherSid=if ($correctSid -cne 'S-1-5-18') { 'S-1-5-18' } else { 'S-1-5-32-544' }
ExpectReject (SyntheticTask $otherSid 'Interactive' 'Limited') $correctSid 'foreign SID'
ExpectReject (SyntheticTask 'S-1-5-21-invalid' 'Interactive' 'Limited') $correctSid 'malformed SID'
ExpectReject (SyntheticTask 'INVALID\unresolved-user-name' 'Interactive' 'Limited') $correctSid 'unresolvable NTAccount'
ExpectReject (SyntheticTask '' 'Interactive' 'Limited') $correctSid 'missing UserId'
foreach ($mode in @('Password','S4U','ServiceAccount','InteractiveOrPassword','None','')) {
  ExpectReject (SyntheticTask $name $mode 'Limited') $correctSid "disallowed logon: $mode"
}
foreach ($level in @('Highest','HighestAvailable','', 'Admin')) {
  ExpectReject (SyntheticTask $correctSid 'Interactive' $level) $correctSid "disallowed run level: $level"
}
ExpectReject (SyntheticTask $correctSid 'Interactive' 'Limited') $otherSid 'expected SID drift'

Write-Host "YACS_TASK_PRINCIPAL_TEST_PASS identity=$name SID=$correctSid valid=4 invalid=15"
