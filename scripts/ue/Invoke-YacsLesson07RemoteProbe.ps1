#requires -Version 7.4
<#
.SYNOPSIS
  Authenticate the installed Wingman bridge belonging to the canonical Editor.
.DESCRIPTION
  Default mode observes processes/listeners and the vendor discovery file, then
  invokes the fixed discovery client. -ExistingEditorOnly additionally requires
  the same verified owner Editor before and after discovery. -ObserveLesson07
  requires that existing owner and requests only the fixed Lesson07 readback.
  These two switches are mutually exclusive. No launch, task mutation, stop or
  save. Discovery credentials stay on the Windows host.
#>
[CmdletBinding(DefaultParameterSetName='Discovery')]
param(
  [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedHead,
  [Parameter(Mandatory)][ValidatePattern('^[0-9]+-[0-9]+$')][string]$RunToken,
  [Parameter(ParameterSetName='Observation')][switch]$ObserveLesson07,
  [Parameter(ParameterSetName='ExistingEditorDiscovery')][switch]$ExistingEditorOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$requireExistingOwner = [bool]($ExistingEditorOnly -or $ObserveLesson07)
$ownerGuardPrefix = if ($ObserveLesson07) { 'OBSERVATION' } else { 'DISCOVERY' }
$projectRoot = 'D:\yacs\project'
$projectFile = Join-Path $projectRoot 'YetAnotherCyclingSim.uproject'
$expectedExe = 'D:\yacs\engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
$discoveryPath = Join-Path $projectRoot 'Saved\LocoAI\external-mcp-config.json'
$outputRoot = Join-Path 'D:\yacs\lesson07-remote\reports' $RunToken
$identityPath = Join-Path $outputRoot 'identity.json'
$clientPath = Join-Path $outputRoot 'bridge.json'
$resultPath = Join-Path $outputRoot 'probe.json'
$python = 'D:\yacs\tool-cache\material-forge\python\Scripts\python.exe'

function Assert-L07PlainPath([string]$Path, [string]$Boundary) {
  $full = [IO.Path]::GetFullPath($Path)
  $base = [IO.Path]::GetFullPath($Boundary).TrimEnd('\')
  if ($full -ine $base -and -not $full.StartsWith($base+'\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'PATH_OUTSIDE_BOUNDARY'
  }
  $cursor = $full
  while ($cursor.Length -ge $base.Length) {
    $item = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'REPARSE_POINT_REJECTED' }
    if ($cursor -ieq $base) { return }
    $cursor = [IO.Path]::GetDirectoryName($cursor)
  }
  throw 'PATH_BOUNDARY_NOT_REACHED'
}

function Get-L07ExistingOwner {
  # Avoid the saved-checkpoint preflight branch when there is no Editor.
  $editors=@(Get-CimInstance -ClassName Win32_Process -Filter "Name='UnrealEditor.exe' OR Name='UnrealEditor-Cmd.exe'")
  if ($editors.Count -ne 1) { throw ($ownerGuardPrefix+'_REQUIRES_EXISTING_EDITOR') }
  $proof=& (Join-Path $PSScriptRoot 'Start-YacsLesson07RemoteEditor.ps1') -ExpectedHead $ExpectedHead -PreflightOnly
  if ($proof.status -cne 'ATTACH_EXISTING' -or $proof.owner_sid_matches -ne $true -or $null -eq $proof.editor) {
    throw ($ownerGuardPrefix+'_REQUIRES_VERIFIED_OWNER')
  }
  return [ordered]@{status=$proof.status;owner_sid_matches=$true;editor=$proof.editor}
}

function Assert-L07OwnerProcess([object]$Owner) {
  $native=Get-Process -Id $Owner.editor.editor_pid -ErrorAction SilentlyContinue
  if (-not $native -or $native.HasExited -or $native.Path -ine $expectedExe -or
      $native.SessionId -ne $Owner.editor.interactive_session_id -or
      $native.StartTime.ToUniversalTime().ToFileTimeUtc().ToString() -cne $Owner.editor.editor_start_filetime_utc) {
    throw ($ownerGuardPrefix+'_OWNER_CHANGED')
  }
}

function Get-L07BridgeIdentity {
  if (-not (Test-Path -LiteralPath $discoveryPath -PathType Leaf)) { return $null }
  Assert-L07PlainPath $discoveryPath $projectRoot
  $metadata = Get-Item -LiteralPath $discoveryPath
  if ($metadata.Length -gt 16KB) { throw 'DISCOVERY_SIZE_REJECTED' }
  if ($metadata.Length -eq 0) { return $null }
  # Startup may expose the discovery file before its single JSON write ends.
  # Only file readiness is polled; no HTTP/native request is ever retried.
  $config = $null
  try { $config = Get-Content -LiteralPath $discoveryPath -Raw | ConvertFrom-Json }
  catch { return $null }
  $afterRead = Get-Item -LiteralPath $discoveryPath -ErrorAction SilentlyContinue
  if (-not $afterRead -or $afterRead.Length -ne $metadata.Length -or
      $afterRead.LastWriteTimeUtc -ne $metadata.LastWriteTimeUtc) {
    $config = $null
    return $null
  }
  try {
    $uri = $null
    if ($config.type -cne 'http' -or $config.token -isnot [string] -or
        [string]::IsNullOrWhiteSpace($config.token) -or $config.url -isnot [string] -or
        -not [Uri]::TryCreate($config.url, [UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -cne 'http' -or $uri.Host -cne '127.0.0.1' -or $uri.Port -le 0 -or
        $uri.AbsolutePath -cne '/loco' -or $uri.UserInfo -or $uri.Query -or $uri.Fragment) {
      throw 'DISCOVERY_CONTRACT_REJECTED'
    }
    $port = [int]$uri.Port
  } finally { $config = $null }
  $editors = @(Get-CimInstance -ClassName Win32_Process -Filter "Name='UnrealEditor.exe' OR Name='UnrealEditor-Cmd.exe'")
  # Refuse competing sessions rather than selecting a convenient process.
  if ($editors.Count -ne 1) { return $null }
  $editor = $editors[0]
  $native = Get-Process -Id ([int]$editor.ProcessId) -ErrorAction SilentlyContinue
  if (-not $native -or $native.HasExited -or $native.SessionId -le 0 -or
      [string]$editor.ExecutablePath -ine $expectedExe) { return $null }
  $arguments = @([regex]::Matches([string]$editor.CommandLine, '(?:"[^"]*"|\S)+') |
    ForEach-Object { ($_.Value -replace '^-project=', '').Trim('"') } |
    Where-Object { $_ -like '*.uproject' })
  if ($arguments.Count -ne 1 -or $arguments[0].Replace('/','\') -ine $projectFile) { return $null }
  if (-not $editor.CreationDate -or $metadata.LastWriteTimeUtc -lt $editor.CreationDate.ToUniversalTime().AddSeconds(-5)) {
    return $null
  }
  $listeners = @(Get-CimInstance -Namespace 'root/StandardCimv2' -ClassName MSFT_NetTCPConnection `
    -Filter ("State=2 AND LocalPort=" + $port))
  if ($listeners.Count -ne 1 -or $listeners[0].LocalAddress -cne '127.0.0.1' -or
      [int]$listeners[0].OwningProcess -ne [int]$editor.ProcessId) { return $null }
  return [ordered]@{
    schema_version=1;status='L07_WINGMAN_HOST_IDENTITY_VERIFIED'
    observed_utc=[DateTime]::UtcNow.ToString('o');source_commit=$ExpectedHead
    pid=[int]$editor.ProcessId;process_created_utc=$editor.CreationDate.ToUniversalTime().ToString('o')
    process_start_filetime_utc=$native.StartTime.ToUniversalTime().ToFileTimeUtc().ToString()
    executable=$expectedExe;project=$projectFile;canonical_project_argument_matches=$true
    listener=[ordered]@{address='127.0.0.1';port=$port;pid=[int]$editor.ProcessId}
  }
}

$report = [ordered]@{
  schema_version=1;source_commit=$ExpectedHead;status='PROBE_NOT_COMPLETE'
  observed_utc=[DateTime]::UtcNow.ToString('o');error_type=$null
  identity_stable_across_probe=$false;client_exit_code=$null
  observation_requested=[bool]$ObserveLesson07;owner_before=$null;owner_after=$null
  existing_editor_only_requested=[bool]$ExistingEditorOnly;existing_owner_required=$requireExistingOwner
  identity_before=$null;identity_after=$null
  native_tool_called=$false;editor_started_or_stopped=$false
  native_tool_attempted=$false;native_tool_completed=$false;native_tool_call_attempts=0
  native_material_readback='NOT_RUN';channel_comparison_performed=$false;performance_pass=$false
}
$failure = $false
$reportRootVerified = $false
try {
  Assert-L07PlainPath 'D:\yacs\lesson07-remote' 'D:\yacs'
  if (-not (Test-Path -LiteralPath $outputRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $outputRoot -ErrorAction Stop | Out-Null
  }
  Assert-L07PlainPath $outputRoot 'D:\yacs\lesson07-remote'
  $reportRootVerified = $true
  foreach ($path in @($identityPath,$clientPath,$resultPath)) {
    if (Test-Path -LiteralPath $path) { throw 'CURRENT_RUN_REPORT_ALREADY_EXISTS' }
  }
  $owner=$null
  if ($requireExistingOwner) {
    $owner=Get-L07ExistingOwner
    $report.owner_before=$owner
  }
  if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'EXISTING_PYTHON_UNAVAILABLE' }
  $deadline = [DateTime]::UtcNow.AddMinutes(6)
  $identity = $null
  do {
    if ($requireExistingOwner) { Assert-L07OwnerProcess $owner }
    $identity = Get-L07BridgeIdentity
    if ($null -ne $identity) { break }
    Start-Sleep -Seconds 3
  } while ([DateTime]::UtcNow -lt $deadline)
  if ($null -eq $identity) { throw 'NO_VERIFIED_WINGMAN_LISTENER_WITHIN_SIX_MINUTES' }
  if ($requireExistingOwner) {
    $freshOwner=Get-L07ExistingOwner
    if ($freshOwner.editor.editor_pid -ne $owner.editor.editor_pid -or
        $freshOwner.editor.editor_start_filetime_utc -cne $owner.editor.editor_start_filetime_utc -or
        $identity.pid -ne $owner.editor.editor_pid -or
        $identity.process_start_filetime_utc -cne $owner.editor.editor_start_filetime_utc) { throw ($ownerGuardPrefix+'_OWNER_CHANGED') }
    $report.owner_before=$freshOwner
  }
  $report.identity_before=$identity
  $identity | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $identityPath -Encoding utf8
  $clientArguments=@('-B',(Join-Path $PSScriptRoot 'lesson07_wingman_client.py'),'--identity-receipt',$identityPath,'--output',$clientPath)
  if ($ObserveLesson07) {
    $clientArguments+='--observe-lesson07'
    # Until its bounded receipt is read, a subprocess failure leaves completion unknown.
    $report.native_tool_called=$null;$report.native_tool_attempted=$null;$report.native_tool_completed=$null
    $report.native_tool_call_attempts=$null;$report.native_material_readback='UNVERIFIED'
  }
  & $python @clientArguments
  $report.client_exit_code = $LASTEXITCODE
  $clientReport=$null
  if ($requireExistingOwner) {
    Assert-L07PlainPath $clientPath $outputRoot
    if ((Get-Item -LiteralPath $clientPath).Length -gt 2MB) { throw ($ownerGuardPrefix+'_CLIENT_REPORT_SIZE') }
    $clientReport=Get-Content -LiteralPath $clientPath -Raw | ConvertFrom-Json -AsHashtable -Depth 32
  }
  if ($ObserveLesson07) {
    foreach ($field in @('native_tool_attempted','native_tool_completed')) {
      $report[$field]=if ($clientReport[$field] -is [bool]) { $clientReport[$field] } else { $null }
    }
    $report.native_tool_call_attempts=if (($clientReport['native_tool_calls'] -is [int] -or $clientReport['native_tool_calls'] -is [long]) -and
        $clientReport['native_tool_calls'] -in @(0,1)) { $clientReport['native_tool_calls'] } else { $null }
    $report.native_tool_called=if ($report.native_tool_attempted -eq $true -and $report.native_tool_completed -eq $true -and
        $report.native_tool_call_attempts -eq 1) { $true
    } elseif ($report.native_tool_attempted -eq $false -and $report.native_tool_call_attempts -eq 0) { $false
    } else { $null }
    if ($report.native_tool_attempted -eq $false -and $report.native_tool_call_attempts -eq 0) { $report.native_material_readback='NOT_RUN' }
  }
  if ($requireExistingOwner) {
    Assert-L07OwnerProcess $owner
    $report.owner_after=Get-L07ExistingOwner
    if ($report.owner_after.editor.editor_pid -ne $owner.editor.editor_pid -or
        $report.owner_after.editor.editor_start_filetime_utc -cne $owner.editor.editor_start_filetime_utc) { throw ($ownerGuardPrefix+'_OWNER_CHANGED') }
  }
  $after = Get-L07BridgeIdentity
  $report.identity_after=$after
  if ($null -eq $after -or $after.pid -ne $identity.pid -or
      $after.process_created_utc -cne $identity.process_created_utc -or
      $after.process_start_filetime_utc -cne $identity.process_start_filetime_utc -or
      $after.listener.port -ne $identity.listener.port) { throw 'BRIDGE_IDENTITY_CHANGED_DURING_PROBE' }
  $report.identity_stable_across_probe = $true
  if ($report.client_exit_code -ne 0) { throw 'AUTHENTICATED_BRIDGE_PROBE_FAILED' }
  if ($ObserveLesson07) {
    if ($clientReport['status'] -isnot [string] -or $clientReport['status'] -cne 'OBSERVATION_COMPLETE' -or
        $report.native_tool_call_attempts -ne 1 -or
        $report.native_tool_attempted -ne $true -or $report.native_tool_completed -ne $true -or
        $clientReport['native_material_readback'] -isnot [string] -or
        $clientReport['native_material_readback'] -cne 'OBSERVED_PARTIAL_DIAGNOSIS_NOT_ACCEPTANCE' -or
        $clientReport['observation'] -isnot [Collections.IDictionary] -or
        $clientReport['observation']['status'] -isnot [string] -or
        $clientReport['observation']['status'] -cne 'OBSERVED_PARTIAL_DIAGNOSIS_NOT_ACCEPTANCE') {
      throw 'OBSERVATION_READBACK_NOT_CONFIRMED'
    }
    $report.native_material_readback='OBSERVED_PARTIAL_DIAGNOSIS_NOT_ACCEPTANCE'
    $report.status='LESSON07_OBSERVATION_COMPLETE_DIAGNOSIS_PARTIAL'
  } else {
    if ($ExistingEditorOnly -and ($clientReport['status'] -isnot [string] -or
        $clientReport['status'] -cne 'DISCOVERY_COMPLETE' -or
        ($clientReport['native_tool_calls'] -isnot [int] -and $clientReport['native_tool_calls'] -isnot [long]) -or
        $clientReport['native_tool_calls'] -ne 0 -or
        $clientReport['native_material_readback'] -isnot [string] -or
        $clientReport['native_material_readback'] -cne 'NOT_RUN')) { throw 'DISCOVERY_ONLY_NOT_CONFIRMED' }
    $report.status = 'BRIDGE_DISCOVERY_COMPLETE_NATIVE_READBACK_PENDING'
  }
} catch {
  $failure = $true
  $report.status = if ($ObserveLesson07) { 'LESSON07_OBSERVATION_INCOMPLETE_EDITOR_RETAINED' } else { 'BRIDGE_DISCOVERY_INCOMPLETE_EDITOR_RETAINED' }
  # Never serialize exception messages that might contain discovery credentials.
  $report.error_type = $_.Exception.GetType().Name
  $safeCodes = @('CURRENT_RUN_REPORT_ALREADY_EXISTS','EXISTING_PYTHON_UNAVAILABLE',
    'NO_VERIFIED_WINGMAN_LISTENER_WITHIN_SIX_MINUTES','BRIDGE_IDENTITY_CHANGED_DURING_PROBE',
    'AUTHENTICATED_BRIDGE_PROBE_FAILED','DISCOVERY_SIZE_REJECTED','DISCOVERY_CONTRACT_REJECTED',
    'PATH_OUTSIDE_BOUNDARY','REPARSE_POINT_REJECTED','PATH_BOUNDARY_NOT_REACHED',
    'OBSERVATION_REQUIRES_EXISTING_EDITOR','OBSERVATION_REQUIRES_VERIFIED_OWNER','OBSERVATION_OWNER_CHANGED',
    'OBSERVATION_CLIENT_REPORT_SIZE','OBSERVATION_READBACK_NOT_CONFIRMED',
    'DISCOVERY_REQUIRES_EXISTING_EDITOR','DISCOVERY_REQUIRES_VERIFIED_OWNER','DISCOVERY_OWNER_CHANGED',
    'DISCOVERY_CLIENT_REPORT_SIZE','DISCOVERY_ONLY_NOT_CONFIRMED')
  $report['reason'] = if ($_.Exception.Message -cin $safeCodes) { $_.Exception.Message } else { 'PROBE_VALIDATION_ERROR' }
} finally {
  $report.observed_utc = [DateTime]::UtcNow.ToString('o')
  if ($reportRootVerified -and -not (Test-Path -LiteralPath $resultPath)) {
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $resultPath -Encoding utf8
  }
  Write-Host ('L07_REMOTE_PROBE=' + ($report | ConvertTo-Json -Depth 5 -Compress))
}
if ($failure) { throw 'L07 remote bridge probe incomplete; existing Editor retained. Read the bounded report.' }
