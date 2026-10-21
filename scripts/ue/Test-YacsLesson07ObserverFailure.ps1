#requires -Version 7.5
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$source=Join-Path $PSScriptRoot 'Read-YacsLesson07ObserverFailure.ps1'
$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if (@($errors).Count) { throw ($errors | Out-String) }
foreach ($name in @('Assert-L07FailureIdentity','Assert-L07FailureDiscovery','Protect-L07FailureText','Select-L07FailureLines')) {
  $nodes=@($ast.FindAll({param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
  },$false))
  if ($nodes.Count -ne 1) { throw 'Missing one production function.' }
  . ([scriptblock]::Create($nodes[0].Extent.Text))
}
function Require([bool]$Value,[string]$Message) { if (-not $Value) { throw $Message } }
function Copy-Data($Value) { return ($Value | ConvertTo-Json -Depth 12 | ConvertFrom-Json -AsHashtable -DateKind String) }
function Expect-Rejection([scriptblock]$Action) {
  $rejected=$false
  try { & $Action } catch { $rejected=$true }
  Require $rejected 'Invalid proof was admitted.'
}
$head='f485b18217deba19bc881aa78d22e5f862d13e3e'
$now=[DateTimeOffset]::Parse('2026-10-21T00:00:00Z')
$identity=Copy-Data @{
  status='L07_WINGMAN_HOST_IDENTITY_VERIFIED';source_commit=$head;pid=17896
  process_start_filetime_utc='134370120000674689';observed_utc='2026-10-20T23:59:00Z'
  executable='D:\yacs\engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
  project='D:\yacs\project\YetAnotherCyclingSim.uproject';canonical_project_argument_matches=$true
}
$owner=@{status='ATTACH_EXISTING';owner_sid_matches=$true;editor=@{editor_pid=17896;editor_start_filetime_utc='134370120000674689'}}
$probe=Copy-Data @{
  status='BRIDGE_DISCOVERY_COMPLETE_NATIVE_READBACK_PENDING';source_commit=$head
  existing_editor_only_requested=$true;identity_stable_across_probe=$true
  native_tool_call_attempts=0;editor_started_or_stopped=$false
  owner_before=$owner;owner_after=$owner;identity_before=$identity;identity_after=$identity
}
Assert-L07FailureIdentity $identity $head $now
Assert-L07FailureDiscovery $probe $head $now
$cases=2
foreach ($change in @(
  @{key='source_commit';value=('a'*40)},@{key='pid';value=17897},@{key='pid';value='17896'},
  @{key='process_start_filetime_utc';value='134370120000674690'},
  @{key='canonical_project_argument_matches';value='true'},
  @{key='observed_utc';value='2026-10-20T23:57:59Z'},
  @{key='observed_utc';value='2026-10-21T00:00:01Z'}
)) {
  $bad=Copy-Data $identity; $bad[$change.key]=$change.value
  Expect-Rejection { Assert-L07FailureIdentity $bad $head $now }
  $cases++
}
foreach ($change in @(
  @{key='status';value='LESSON07_OBSERVATION_INCOMPLETE_EDITOR_RETAINED'},
  @{key='existing_editor_only_requested';value='true'},
  @{key='native_tool_call_attempts';value=1},
  @{key='native_tool_call_attempts';value='0'},
  @{key='editor_started_or_stopped';value=$true}
)) {
  $bad=Copy-Data $probe; $bad[$change.key]=$change.value
  Expect-Rejection { Assert-L07FailureDiscovery $bad $head $now }
  $cases++
}
$bad=Copy-Data $probe; $bad.owner_after.owner_sid_matches=$false
Expect-Rejection { Assert-L07FailureDiscovery $bad $head $now }; $cases++
$safe=Protect-L07FailureText ('Error: token="PRIVATE TOKEN" password=PRIVATEPASS api_key=''API SECRET'' Bearer BEARERSECRET https://host/path?token=URLSECRET'+[char]27+'[31m')
Require ($safe -notmatch 'PRIVATE|API SECRET|BEARERSECRET|URLSECRET|\x1b') 'Credential or control character leaked.'
$cases++
$safe=Protect-L07FailureText 'Error: token="ESCAPED\"PRIVATE continuation'
Require ($safe -notmatch 'ESCAPED|PRIVATE|continuation') 'Malformed quoted credential leaked.'; $cases++
$safe=Protect-L07FailureText 'Error: Authorization: Basic BASICSECRET'
Require ($safe -notmatch 'BASICSECRET') 'Authorization header leaked.'; $cases++
$text=@'
[2026.10.20-23.48.13:600][123]LogPython: Error: Traceback (most recent call last):
[2026.10.20-23.48.13:601][123]LogPython: Error: NameError: missing_name
[2026.10.21-01.48.13:602][123]LogLocoHelperAI: Warning: execute_python failed
[2026.10.20-23.48.13:603][123]LogRenderer: Informational unrelated content
[2026.10.20-23.48.31:000][123]LogPython: Error: OUTSIDE_WINDOW
[2026.10.20-23.47.13:600][123]LogPython: Error: OUTSIDE_MINUTE
LogPython: Error: UNTIMESTAMPED
'@
$result=Select-L07FailureLines $text
Require ($result.records.Count -eq 3 -and $result.matching_lines -eq 3 -and -not $result.truncated) 'Timestamp/category scope failed.'
Require (($result | ConvertTo-Json -Depth 6) -notmatch 'OUTSIDE|UNTIMESTAMPED|unrelated') 'Unselected log content leaked.'
$cases++
$many=(1..40 | ForEach-Object { '[2026.10.20-23.48.13:600][123]LogPython: Error: '+('x'*1000) }) -join "`n"
$result=Select-L07FailureLines $many
Require ($result.records.Count -eq 24 -and $result.matching_lines -eq 40 -and $result.truncated) 'Record bound failed.'
Require ($result.records[0].text.Length -le 780) 'Line bound failed.'; $cases++
Write-Output ('{"status":"LESSON07_FAILURE_LOG_TESTS_PASS","cases":'+$cases+',"native_host_actions":false}')
