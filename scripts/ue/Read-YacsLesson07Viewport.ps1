#requires -Version 7.5
<#
.SYNOPSIS
  Retain the exact JPEG returned by this run's dedicated viewport capture.
.DESCRIPTION
  Reads existing receipts and bounded files. -TrialMacro retains only completed
  A/B/A captures after verified restoration of the original material baseline.
  -ApplyReviewedMacro retains the verified 0.05 candidate's final capture.
  It never calls Unreal, selects
  a newest file, retries capture, changes the camera, or modifies source assets.
#>
[CmdletBinding(DefaultParameterSetName='Capture')]
param(
  [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedHead,
  [Parameter(Mandatory)][ValidatePattern('^[0-9]{1,20}-[0-9]{1,10}$')][string]$RunToken,
  [Parameter(ParameterSetName='MacroTrial')][switch]$TrialMacro,
  [Parameter(ParameterSetName='ReviewedMacroApply')][switch]$ApplyReviewedMacro
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Assert-L07ViewportSourcePath([string]$Path) {
  $canonical=$Path.Replace('/','\')
  if ($canonical -notmatch '^D:\\yacs\\project\\Saved\\LocoHelperAI\\ViewportShots\\[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}\.(?:jpg|jpeg)$') {
    throw 'VIEWPORT_SOURCE_PATH_REJECTED'
  }
  $name=$canonical.Substring($canonical.LastIndexOf('\')+1)
  if ($name -match '^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)') { throw 'VIEWPORT_SOURCE_NAME_REJECTED' }
  return $canonical
}

function Get-L07ViewportSourcePath([string]$Text) {
  if ([string]::IsNullOrWhiteSpace($Text) -or $Text.Length -gt 16384) { throw 'VIEWPORT_RESPONSE_TEXT_SIZE' }
  $values=[Collections.Generic.Queue[object]]::new()
  if ($Text.TrimStart() -match '^[{\["]') {
    try { $value=ConvertFrom-Json -InputObject $Text -AsHashtable -DateKind String -Depth 8 -NoEnumerate }
    catch { throw 'VIEWPORT_RESPONSE_JSON_INVALID' }
    $values.Enqueue(@{value=$value;depth=0})
  } else { $values.Enqueue(@{value=$Text;depth=0}) }
  $paths=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
  $visited=0
  while ($values.Count) {
    $entry=$values.Dequeue(); $visited++
    if ($visited -gt 256 -or $entry.depth -gt 8) { throw 'VIEWPORT_RESPONSE_STRUCTURE_LIMIT' }
    $value=$entry.value
    if ($value -is [string]) {
      # Keep the complete token: ADS, traversal, suffixes and unknown punctuation
      # are rejected by the anchored allowlist, never trimmed into a valid path.
      foreach ($match in [regex]::Matches($value,'(?<![\w\\/:])(?:[A-Za-z]:[\\/]|\\\\)[^\s"''`<>|]+')) {
        $null=$paths.Add((Assert-L07ViewportSourcePath $match.Value))
      }
    } elseif ($value -is [Collections.IDictionary]) {
      foreach ($child in $value.Values) { $values.Enqueue(@{value=$child;depth=($entry.depth+1)}) }
    } elseif ($value -is [array]) {
      foreach ($child in $value) { $values.Enqueue(@{value=$child;depth=($entry.depth+1)}) }
    }
  }
  if ($paths.Count -ne 1) { throw 'VIEWPORT_RESPONSE_PATH_AMBIGUOUS_OR_MISSING' }
  return @($paths)[0]
}

function Assert-L07ViewportPlainPath([string]$Path) {
  $cursor=[IO.Path]::GetFullPath($Path)
  while ($cursor) {
    $item=Get-Item -LiteralPath $cursor -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'VIEWPORT_REPARSE_POINT' }
    $parent=[IO.Path]::GetDirectoryName($cursor)
    if ($parent -eq $cursor) { break }
    $cursor=$parent
  }
}

function Read-L07ViewportProof([string]$Path,[long]$Limit) {
  Assert-L07ViewportPlainPath $Path
  $before=Get-Item -LiteralPath $Path
  if ($before.PSIsContainer -or $before.Length -le 0 -or $before.Length -gt $Limit) { throw 'VIEWPORT_PROOF_SIZE' }
  $stream=[IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  try {
    if ($stream.Length -ne $before.Length) { throw 'VIEWPORT_PROOF_CHANGED' }
    $bytes=[byte[]]::new([int]$before.Length)
    $stream.ReadExactly($bytes,0,$bytes.Length)
  } finally { $stream.Dispose() }
  $after=Get-Item -LiteralPath $Path
  if ($bytes.Length -ne $before.Length -or $after.Length -ne $before.Length -or
      $after.LastWriteTimeUtc -ne $before.LastWriteTimeUtc) { throw 'VIEWPORT_PROOF_CHANGED' }
  $data=[Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json -AsHashtable -DateKind String -Depth 32
  if ($data -isnot [Collections.IDictionary]) { throw 'VIEWPORT_PROOF_SHAPE' }
  return @{data=$data;sha256=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()}
}

function ConvertTo-L07ViewportUtc($Value) {
  if ($Value -isnot [string] -or $Value -notmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|\+00:00)$') {
    throw 'VIEWPORT_UTC_REQUIRED'
  }
  return [DateTimeOffset]::Parse($Value,[Globalization.CultureInfo]::InvariantCulture)
}

function Assert-L07ViewportIdentity([Collections.IDictionary]$Identity,[string]$Head,[DateTimeOffset]$Now) {
  if ($Identity.status -isnot [string] -or $Identity.status -cne 'L07_WINGMAN_HOST_IDENTITY_VERIFIED' -or
      $Identity.source_commit -isnot [string] -or $Identity.source_commit -cne $Head -or
      ($Identity.pid -isnot [int] -and $Identity.pid -isnot [long]) -or $Identity.pid -le 0 -or
      $Identity.process_start_filetime_utc -isnot [string] -or $Identity.process_start_filetime_utc -notmatch '^[1-9][0-9]{1,18}$' -or
      $Identity.executable -isnot [string] -or $Identity.executable -cne 'D:\yacs\engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe' -or
      $Identity.project -isnot [string] -or $Identity.project -cne 'D:\yacs\project\YetAnotherCyclingSim.uproject' -or
      $Identity.canonical_project_argument_matches -isnot [bool] -or -not $Identity.canonical_project_argument_matches -or
      $Identity.listener -isnot [Collections.IDictionary] -or
      $Identity.listener.address -isnot [string] -or $Identity.listener.address -cne '127.0.0.1' -or
      ($Identity.listener.port -isnot [int] -and $Identity.listener.port -isnot [long]) -or
      $Identity.listener.port -le 0 -or $Identity.listener.port -gt 65535 -or
      ($Identity.listener.pid -isnot [int] -and $Identity.listener.pid -isnot [long]) -or
      $Identity.listener.pid -ne $Identity.pid) { throw 'VIEWPORT_IDENTITY_REJECTED' }
  $observed=ConvertTo-L07ViewportUtc $Identity.observed_utc
  $created=ConvertTo-L07ViewportUtc $Identity.process_created_utc
  $start=[DateTimeOffset]::new([DateTime]::FromFileTimeUtc([long]$Identity.process_start_filetime_utc))
  if (($Now-$observed).TotalSeconds -lt 0 -or ($Now-$observed).TotalSeconds -gt 120 -or
      $created -gt $observed -or $start -gt $observed) { throw 'VIEWPORT_IDENTITY_TIME_REJECTED' }
}

function Assert-L07ViewportProofs([Collections.IDictionary]$Identity,[Collections.IDictionary]$Probe,
    [Collections.IDictionary]$Bridge,[string]$Head,[DateTimeOffset]$Now) {
  Assert-L07ViewportIdentity $Identity $Head $Now
  if ($Probe.status -isnot [string] -or $Probe.status -cne 'LESSON07_CAPTURE_RESPONSE_RECEIVED_FILE_PENDING' -or
      $Probe.source_commit -isnot [string] -or $Probe.source_commit -cne $Head -or
      $Probe.native_material_readback -isnot [string] -or $Probe.native_material_readback -cne 'NOT_RUN' -or
      ($Probe.native_tool_call_attempts -isnot [int] -and $Probe.native_tool_call_attempts -isnot [long]) -or
      $Probe.native_tool_call_attempts -ne 1 -or
      ($Probe.client_exit_code -isnot [int] -and $Probe.client_exit_code -isnot [long]) -or $Probe.client_exit_code -ne 0) {
    throw 'VIEWPORT_PROBE_REJECTED'
  }
  foreach ($field in @('capture_requested','existing_owner_required','identity_stable_across_probe',
      'native_tool_called','native_tool_attempted','native_tool_completed')) {
    if ($Probe[$field] -isnot [bool] -or -not $Probe[$field]) { throw 'VIEWPORT_PROBE_FLAG_REJECTED' }
  }
  foreach ($field in @('observation_requested','editor_started_or_stopped')) {
    if ($Probe[$field] -isnot [bool] -or $Probe[$field]) { throw 'VIEWPORT_PROBE_FLAG_REJECTED' }
  }
  foreach ($field in @('identity_before','identity_after')) {
    $other=$Probe[$field]
    Assert-L07ViewportIdentity $other $Head $Now
    foreach ($key in @('pid','process_start_filetime_utc','executable','project')) {
      if ($other[$key] -cne $Identity[$key]) { throw 'VIEWPORT_IDENTITY_CHANGED' }
    }
    if ((ConvertTo-L07ViewportUtc $other.process_created_utc) -ne (ConvertTo-L07ViewportUtc $Identity.process_created_utc) -or
        $other.listener.port -ne $Identity.listener.port) { throw 'VIEWPORT_IDENTITY_CHANGED' }
  }
  $sessionId=$null
  foreach ($field in @('owner_before','owner_after')) {
    $owner=$Probe[$field]
    if ($owner -isnot [Collections.IDictionary] -or $owner.status -isnot [string] -or $owner.status -cne 'ATTACH_EXISTING' -or
        $owner.owner_sid_matches -isnot [bool] -or -not $owner.owner_sid_matches -or
        $owner.editor -isnot [Collections.IDictionary]) { throw 'VIEWPORT_OWNER_REJECTED' }
    $editor=$owner.editor
    if (($editor.editor_pid -isnot [int] -and $editor.editor_pid -isnot [long]) -or $editor.editor_pid -ne $Identity.pid -or
        $editor.editor_start_filetime_utc -isnot [string] -or $editor.editor_start_filetime_utc -cne $Identity.process_start_filetime_utc -or
        $editor.editor_executable_path -isnot [string] -or $editor.editor_executable_path -cne $Identity.executable -or
        $editor.canonical_project_matches -isnot [bool] -or -not $editor.canonical_project_matches -or
        ($editor.interactive_session_id -isnot [int] -and $editor.interactive_session_id -isnot [long]) -or
        $editor.interactive_session_id -le 0) { throw 'VIEWPORT_OWNER_REJECTED' }
    if ($null -ne $sessionId -and $sessionId -ne $editor.interactive_session_id) { throw 'VIEWPORT_OWNER_CHANGED' }
    $sessionId=$editor.interactive_session_id
  }
  if ($Bridge.status -isnot [string] -or $Bridge.status -cne 'CAPTURE_RESPONSE_RECEIVED' -or
      $Bridge.native_material_readback -isnot [string] -or $Bridge.native_material_readback -cne 'NOT_RUN' -or
      $Bridge.native_tool_name -isnot [string] -or $Bridge.native_tool_name -cne 'take_viewport_screenshot' -or
      ($Bridge.native_tool_calls -isnot [int] -and $Bridge.native_tool_calls -isnot [long]) -or $Bridge.native_tool_calls -ne 1 -or
      $Bridge.capture_input_schema_sha256 -isnot [string] -or
      $Bridge.capture_input_schema_sha256 -cne '4ef41b0bf0c6c93d64a049687e0e43565fb351cd484169b58473801840b3dcdc' -or
      $Bridge.capture_arguments -isnot [Collections.IDictionary] -or $Bridge.capture_arguments.Count -ne 1 -or
      $Bridge.capture_arguments.return_image -isnot [bool] -or $Bridge.capture_arguments.return_image -ne $false) {
    throw 'VIEWPORT_CAPTURE_REJECTED'
  }
  foreach ($field in @('native_tool_attempted','native_tool_completed','native_tool_response_received')) {
    if ($Bridge[$field] -isnot [bool] -or -not $Bridge[$field]) { throw 'VIEWPORT_CAPTURE_FLAG_REJECTED' }
  }
  $hostIdentity=$Bridge.external_host_identity
  if ($hostIdentity -isnot [Collections.IDictionary] -or
      ($hostIdentity.pid -isnot [int] -and $hostIdentity.pid -isnot [long]) -or $hostIdentity.pid -ne $Identity.pid) {
    throw 'VIEWPORT_BRIDGE_IDENTITY_REJECTED'
  }
  foreach ($key in @('executable','project')) {
    if ($hostIdentity[$key] -isnot [string] -or $hostIdentity[$key] -cne $Identity[$key]) { throw 'VIEWPORT_BRIDGE_IDENTITY_REJECTED' }
  }
  # The Python client preserves UTC instants to microsecond precision; .NET
  # receipts carry a seventh fractional digit. Match its exact truncation.
  $createdTicks=(ConvertTo-L07ViewportUtc $Identity.process_created_utc).UtcTicks
  $observedTicks=(ConvertTo-L07ViewportUtc $Identity.observed_utc).UtcTicks
  if ((ConvertTo-L07ViewportUtc $hostIdentity.process_created_utc).UtcTicks -ne ($createdTicks-($createdTicks%10)) -or
      (ConvertTo-L07ViewportUtc $hostIdentity.observed_utc).UtcTicks -ne ($observedTicks-($observedTicks%10)) -or
      $hostIdentity.listener -isnot [Collections.IDictionary] -or
      $hostIdentity.listener.address -isnot [string] -or $hostIdentity.listener.address -cne $Identity.listener.address -or
      ($hostIdentity.listener.port -isnot [int] -and $hostIdentity.listener.port -isnot [long]) -or
      $hostIdentity.listener.port -ne $Identity.listener.port -or
      ($hostIdentity.listener.pid -isnot [int] -and $hostIdentity.listener.pid -isnot [long]) -or $hostIdentity.listener.pid -ne $Identity.pid) {
    throw 'VIEWPORT_BRIDGE_IDENTITY_REJECTED'
  }
  $capture=$Bridge.capture_result
  if ($capture -isnot [Collections.IDictionary] -or $capture.text -isnot [string] -or
      $capture.text_truncated -isnot [bool] -or $capture.text_truncated -or
      ($capture.text_block_count -isnot [int] -and $capture.text_block_count -isnot [long]) -or
      $capture.text_block_count -lt 1 -or $capture.text_block_count -gt 8 -or
      $capture.response_sha256 -isnot [string] -or $capture.response_sha256 -cnotmatch '^[0-9a-f]{64}$') {
    throw 'VIEWPORT_CAPTURE_TEXT_REJECTED'
  }
  $started=ConvertTo-L07ViewportUtc $Bridge.native_tool_started_utc
  $finished=ConvertTo-L07ViewportUtc $Bridge.native_tool_response_received_utc
  $before=ConvertTo-L07ViewportUtc $Probe.identity_before.observed_utc
  $after=ConvertTo-L07ViewportUtc $Probe.identity_after.observed_utc
  if ($started -lt $before -or $finished -lt $started -or $finished -gt $after -or
      $after -gt $Now -or ($Now-$finished).TotalSeconds -gt 120 -or
      (ConvertTo-L07ViewportUtc $Identity.observed_utc) -ne $before) { throw 'VIEWPORT_CAPTURE_TIME_REJECTED' }
  return @{path=(Get-L07ViewportSourcePath $capture.text);started=$started;finished=$finished;session_id=$sessionId}
}

function Assert-L07ViewportProcess([Collections.IDictionary]$Identity,[long]$SessionId) {
  $editor=Get-Process -Id ([int]$Identity.pid) -ErrorAction Stop
  if ($editor.HasExited -or $editor.Path -cne $Identity.executable -or $editor.SessionId -ne $SessionId -or
      $editor.StartTime.ToUniversalTime().ToFileTimeUtc().ToString() -cne $Identity.process_start_filetime_utc) {
    throw 'VIEWPORT_PROCESS_CHANGED'
  }
}

function Assert-L07TrialCamera([Collections.IDictionary]$Arguments) {
  if ($Arguments.Count -ne 4 -or $Arguments.return_image -isnot [bool] -or $Arguments.return_image -ne $false -or
      ($Arguments.fov -isnot [int] -and $Arguments.fov -isnot [long] -and $Arguments.fov -isnot [double]) -or
      $Arguments.fov -ne 90) { throw 'TRIAL_MACRO_CAMERA_REJECTED' }
  foreach ($key in @('return_image','camera_location','camera_rotation','fov')) {
    if ($Arguments.Keys -cnotcontains $key) { throw 'TRIAL_MACRO_CAMERA_REJECTED' }
  }
  $expected=@{
    camera_location=@(-16145.268182324218,84377.62518478667,49067.09993071173)
    camera_rotation=@(-18.85209781522559,165.400053560734,0)
  }
  foreach ($key in @('camera_location','camera_rotation')) {
    $values=$Arguments[$key]
    if ($values -isnot [array] -or $values.Count -ne 3) { throw 'TRIAL_MACRO_CAMERA_REJECTED' }
    for ($i=0;$i -lt 3;$i++) {
      if (($values[$i] -isnot [int] -and $values[$i] -isnot [long] -and $values[$i] -isnot [double]) -or
          -not [double]::IsFinite([double]$values[$i]) -or [double]$values[$i] -ne [double]$expected[$key][$i]) {
        throw 'TRIAL_MACRO_CAMERA_REJECTED'
      }
    }
  }
}

function Assert-L07TrialViewportProofs([Collections.IDictionary]$Identity,[Collections.IDictionary]$Probe,
    [Collections.IDictionary]$Bridge,[string]$Head,[DateTimeOffset]$Now) {
  # The client bounds the entire trial to 300 seconds. Keep the original
  # identity timestamp and allow 60 seconds for the final owner preflight;
  # the final observation must still be fresh. Original capture rules are unchanged.
  $before=ConvertTo-L07ViewportUtc $Identity.observed_utc
  $after=ConvertTo-L07ViewportUtc $Probe.identity_after.observed_utc
  if ($after -lt $before -or ($after-$before).TotalSeconds -gt 360 -or
      $Now -lt $after -or ($Now-$after).TotalSeconds -gt 120) { throw 'TRIAL_MACRO_IDENTITY_TIME_REJECTED' }
  Assert-L07ViewportIdentity $Identity $Head $before
  if ($Probe.source_commit -isnot [string] -or $Probe.source_commit -cne $Head -or
      $Probe.status -isnot [string] -or $Probe.status -cnotin @(
        'LESSON07_TRIAL_MACRO_RESTORED_IMAGES_PENDING','LESSON07_TRIAL_MACRO_INCOMPLETE_EDITOR_RETAINED') -or
      $Probe.trial_status -isnot [string] -or $Probe.trial_status -cne $Bridge.status -or
      $Bridge.status -isnot [string] -or $Bridge.status -cnotin @('TRIAL_MACRO_RESTORED_REVIEW_PENDING','TRIAL_MACRO_FAILED') -or
      ($Probe.client_exit_code -isnot [int] -and $Probe.client_exit_code -isnot [long]) -or
      ($Probe.native_tool_call_attempts -isnot [int] -and $Probe.native_tool_call_attempts -isnot [long]) -or
      ($Bridge.native_tool_calls -isnot [int] -and $Bridge.native_tool_calls -isnot [long]) -or
      $Bridge.native_tool_calls -lt 1 -or $Bridge.native_tool_calls -gt 15 -or
      $Probe.native_tool_call_attempts -ne $Bridge.native_tool_calls) { throw 'TRIAL_MACRO_PROBE_REJECTED' }
  foreach ($field in @('trial_macro_requested','existing_owner_required','identity_stable_across_probe','native_tool_attempted')) {
    if ($Probe[$field] -isnot [bool] -or -not $Probe[$field]) { throw 'TRIAL_MACRO_PROBE_FLAG_REJECTED' }
  }
  foreach ($field in @('capture_requested','inspection_requested','observation_requested','editor_started_or_stopped','performance_pass')) {
    if ($Probe[$field] -isnot [bool] -or $Probe[$field]) { throw 'TRIAL_MACRO_PROBE_FLAG_REJECTED' }
  }
  foreach ($field in @('trial_mutation_attempted','trial_restore_verified','trial_backup_verified','trial_registry_verified')) {
    if ($Bridge[$field] -isnot [bool] -or $Probe[$field] -isnot [bool] -or $Bridge[$field] -ne $Probe[$field]) {
      throw 'TRIAL_MACRO_RESTORATION_REJECTED'
    }
  }
  if (-not $Bridge.trial_restore_verified -or -not $Bridge.trial_registry_verified -or
      ($Bridge.trial_mutation_attempted -and -not $Bridge.trial_backup_verified)) { throw 'TRIAL_MACRO_RESTORATION_REJECTED' }
  $complete=$Bridge.status -ceq 'TRIAL_MACRO_RESTORED_REVIEW_PENDING'
  if ($Bridge.trial_results -isnot [array] -or $Bridge.trial_results.Count -gt 15 -or
      $Bridge.trial_captures -isnot [Collections.IDictionary] -or
      $Bridge.trial_captures.Count -lt 1 -or $Bridge.trial_captures.Count -gt 3 -or
      ($Probe.trial_captures_received -isnot [int] -and $Probe.trial_captures_received -isnot [long]) -or
      $Probe.trial_captures_received -ne $Bridge.trial_captures.Count) { throw 'TRIAL_MACRO_CAPTURE_SET_REJECTED' }
  if ($complete) {
    if ($Probe.status -cne 'LESSON07_TRIAL_MACRO_RESTORED_IMAGES_PENDING' -or $Probe.client_exit_code -ne 0 -or
        $Bridge.native_tool_calls -ne 12 -or $Bridge.trial_results.Count -ne 12 -or $Bridge.trial_captures.Count -ne 3 -or
        -not $Bridge.trial_mutation_attempted -or -not $Bridge.trial_backup_verified -or
        $Bridge.native_material_readback -isnot [string] -or $Bridge.native_material_readback -cne 'TRIAL_BASELINE_RESTORED_CAPTURE_REVIEW_PENDING') {
      throw 'TRIAL_MACRO_COMPLETION_REJECTED'
    }
    foreach ($field in @('native_tool_attempted','native_tool_completed','native_tool_response_received')) {
      if ($Bridge[$field] -isnot [bool] -or -not $Bridge[$field]) { throw 'TRIAL_MACRO_COMPLETION_REJECTED' }
    }
    foreach ($field in @('native_tool_called','native_tool_completed')) {
      if ($Probe[$field] -isnot [bool] -or -not $Probe[$field]) { throw 'TRIAL_MACRO_COMPLETION_REJECTED' }
    }
  } elseif ($Probe.status -cne 'LESSON07_TRIAL_MACRO_INCOMPLETE_EDITOR_RETAINED') { throw 'TRIAL_MACRO_COMPLETION_REJECTED' }
  foreach ($field in @('identity_before','identity_after')) {
    $other=$Probe[$field]
    if ($other -isnot [Collections.IDictionary]) { throw 'TRIAL_MACRO_IDENTITY_REJECTED' }
    $observed=ConvertTo-L07ViewportUtc $other.observed_utc
    Assert-L07ViewportIdentity $other $Head $observed
    foreach ($key in @('pid','process_start_filetime_utc','executable','project')) {
      if ($other[$key] -cne $Identity[$key]) { throw 'TRIAL_MACRO_IDENTITY_CHANGED' }
    }
    if ((ConvertTo-L07ViewportUtc $other.process_created_utc) -ne (ConvertTo-L07ViewportUtc $Identity.process_created_utc) -or
        $other.listener.port -ne $Identity.listener.port) { throw 'TRIAL_MACRO_IDENTITY_CHANGED' }
  }
  if ((ConvertTo-L07ViewportUtc $Probe.identity_before.observed_utc) -ne $before) { throw 'TRIAL_MACRO_IDENTITY_CHANGED' }
  $sessionId=$null
  foreach ($field in @('owner_before','owner_after')) {
    $owner=$Probe[$field]
    if ($owner -isnot [Collections.IDictionary] -or $owner.status -isnot [string] -or $owner.status -cne 'ATTACH_EXISTING' -or
        $owner.owner_sid_matches -isnot [bool] -or -not $owner.owner_sid_matches -or
        $owner.editor -isnot [Collections.IDictionary]) { throw 'TRIAL_MACRO_OWNER_REJECTED' }
    $editor=$owner.editor
    if (($editor.editor_pid -isnot [int] -and $editor.editor_pid -isnot [long]) -or $editor.editor_pid -ne $Identity.pid -or
        $editor.editor_start_filetime_utc -isnot [string] -or $editor.editor_start_filetime_utc -cne $Identity.process_start_filetime_utc -or
        $editor.editor_executable_path -isnot [string] -or $editor.editor_executable_path -cne $Identity.executable -or
        $editor.canonical_project_matches -isnot [bool] -or -not $editor.canonical_project_matches -or
        ($editor.interactive_session_id -isnot [int] -and $editor.interactive_session_id -isnot [long]) -or
        $editor.interactive_session_id -le 0) { throw 'TRIAL_MACRO_OWNER_REJECTED' }
    if ($null -ne $sessionId -and $sessionId -ne $editor.interactive_session_id) { throw 'TRIAL_MACRO_OWNER_CHANGED' }
    $sessionId=$editor.interactive_session_id
  }
  $hostIdentity=$Bridge.external_host_identity
  if ($hostIdentity -isnot [Collections.IDictionary] -or
      ($hostIdentity.pid -isnot [int] -and $hostIdentity.pid -isnot [long]) -or $hostIdentity.pid -ne $Identity.pid) {
    throw 'TRIAL_MACRO_BRIDGE_IDENTITY_REJECTED'
  }
  foreach ($key in @('executable','project')) {
    if ($hostIdentity[$key] -isnot [string] -or $hostIdentity[$key] -cne $Identity[$key]) { throw 'TRIAL_MACRO_BRIDGE_IDENTITY_REJECTED' }
  }
  $createdTicks=(ConvertTo-L07ViewportUtc $Identity.process_created_utc).UtcTicks
  if ((ConvertTo-L07ViewportUtc $hostIdentity.process_created_utc).UtcTicks -ne ($createdTicks-($createdTicks%10)) -or
      (ConvertTo-L07ViewportUtc $hostIdentity.observed_utc).UtcTicks -ne ($before.UtcTicks-($before.UtcTicks%10)) -or
      $hostIdentity.listener -isnot [Collections.IDictionary] -or
      $hostIdentity.listener.address -isnot [string] -or $hostIdentity.listener.address -cne $Identity.listener.address -or
      ($hostIdentity.listener.port -isnot [int] -and $hostIdentity.listener.port -isnot [long]) -or $hostIdentity.listener.port -ne $Identity.listener.port -or
      ($hostIdentity.listener.pid -isnot [int] -and $hostIdentity.listener.pid -isnot [long]) -or $hostIdentity.listener.pid -ne $Identity.pid) {
    throw 'TRIAL_MACRO_BRIDGE_IDENTITY_REJECTED'
  }
  $stages=[ordered]@{A_baseline=4;B_macro_005=9;A_restored=12}
  foreach ($key in $Bridge.trial_captures.Keys) {
    if ($stages.Keys -cnotcontains $key) { throw 'TRIAL_MACRO_CAPTURE_SET_REJECTED' }
  }
  $paths=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
  $captures=[Collections.Generic.List[object]]::new()
  $previousFinish=$before
  foreach ($stage in $stages.Keys) {
    if (-not $Bridge.trial_captures.Contains($stage)) { continue }
    $capture=$Bridge.trial_captures[$stage]
    $rows=@($Bridge.trial_results | Where-Object { $_ -is [Collections.IDictionary] -and $_['stage'] -is [string] -and $_['stage'] -ceq $stage })
    if ($rows.Count -ne 1 -or $capture -isnot [Collections.IDictionary] -or $capture.Count -ne 4) { throw 'TRIAL_MACRO_CAPTURE_ROW_REJECTED' }
    $row=$rows[0]
    if (($row.index -isnot [int] -and $row.index -isnot [long]) -or $row.index -ne $stages[$stage] -or
        $row.tool_name -isnot [string] -or $row.tool_name -cne 'take_viewport_screenshot' -or
        $row.input_schema_sha256 -isnot [string] -or $row.input_schema_sha256 -cne '4ef41b0bf0c6c93d64a049687e0e43565fb351cd484169b58473801840b3dcdc') {
      throw 'TRIAL_MACRO_CAPTURE_ROW_REJECTED'
    }
    foreach ($field in @('attempted','completed','response_received')) {
      if ($row[$field] -isnot [bool] -or -not $row[$field]) { throw 'TRIAL_MACRO_CAPTURE_ROW_REJECTED' }
    }
    Assert-L07TrialCamera $row.arguments
    Assert-L07TrialCamera $capture.capture_arguments
    $result=$capture.capture_result
    if ($result -isnot [Collections.IDictionary] -or $row.result -isnot [Collections.IDictionary] -or
        $result.text -isnot [string] -or $result.text_truncated -isnot [bool] -or $result.text_truncated -or
        ($result.text_block_count -isnot [int] -and $result.text_block_count -isnot [long]) -or
        $result.text_block_count -lt 1 -or $result.text_block_count -gt 8 -or
        $result.response_sha256 -isnot [string] -or $result.response_sha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'TRIAL_MACRO_CAPTURE_TEXT_REJECTED' }
    foreach ($key in @('text','text_truncated','text_block_count','response_sha256')) {
      if ($row.result[$key].GetType() -ne $result[$key].GetType() -or $row.result[$key] -cne $result[$key]) { throw 'TRIAL_MACRO_CAPTURE_ROW_REJECTED' }
    }
    $started=ConvertTo-L07ViewportUtc $capture.native_tool_started_utc
    $finished=ConvertTo-L07ViewportUtc $capture.native_tool_response_received_utc
    if ((ConvertTo-L07ViewportUtc $row.started_utc) -ne $started -or
        (ConvertTo-L07ViewportUtc $row.response_received_utc) -ne $finished -or
        $started -lt $previousFinish -or $finished -lt $started -or $finished -gt $after) { throw 'TRIAL_MACRO_CAPTURE_TIME_REJECTED' }
    $path=Get-L07ViewportSourcePath $result.text
    if (-not $paths.Add($path)) { throw 'TRIAL_MACRO_CAPTURE_PATH_REUSED' }
    $captures.Add(@{stage=$stage;path=$path;started=$started;finished=$finished;session_id=$sessionId;response_sha256=$result.response_sha256})
    $previousFinish=$finished
  }
  return @{captures=$captures.ToArray();complete=$complete;session_id=$sessionId}
}

function Assert-L07AppliedViewportProofs([Collections.IDictionary]$Identity,[Collections.IDictionary]$Probe,
    [Collections.IDictionary]$Bridge,[string]$Head,[DateTimeOffset]$Now) {
  $before=ConvertTo-L07ViewportUtc $Identity.observed_utc
  $after=ConvertTo-L07ViewportUtc $Probe.identity_after.observed_utc
  if ($after -lt $before -or ($after-$before).TotalSeconds -gt 360 -or
      $Now -lt $after -or ($Now-$after).TotalSeconds -gt 120) { throw 'APPLY_MACRO_IDENTITY_TIME_REJECTED' }
  Assert-L07ViewportIdentity $Identity $Head $before
  if ($Probe.source_commit -isnot [string] -or $Probe.source_commit -cne $Head -or
      $Probe.status -isnot [string] -or $Probe.status -cne 'LESSON07_REVIEWED_MACRO_APPLIED_IMAGE_PENDING' -or
      $Probe.apply_status -isnot [string] -or $Probe.apply_status -cne 'APPLY_REVIEWED_MACRO_VERIFIED_REVIEW_PENDING' -or
      $Bridge.status -isnot [string] -or $Bridge.status -cne 'APPLY_REVIEWED_MACRO_VERIFIED_REVIEW_PENDING' -or
      ($Probe.client_exit_code -isnot [int] -and $Probe.client_exit_code -isnot [long]) -or $Probe.client_exit_code -ne 0 -or
      ($Probe.native_tool_call_attempts -isnot [int] -and $Probe.native_tool_call_attempts -isnot [long]) -or $Probe.native_tool_call_attempts -ne 7 -or
      ($Bridge.native_tool_calls -isnot [int] -and $Bridge.native_tool_calls -isnot [long]) -or $Bridge.native_tool_calls -ne 7 -or
      $Bridge.native_material_readback -isnot [string] -or $Bridge.native_material_readback -cne 'REVIEWED_MACRO_APPLIED_CAPTURE_REVIEW_PENDING') {
    throw 'APPLY_MACRO_PROBE_REJECTED'
  }
  foreach ($field in @('apply_macro_requested','existing_owner_required','identity_stable_across_probe',
      'native_tool_called','native_tool_attempted','native_tool_completed')) {
    if ($Probe[$field] -isnot [bool] -or -not $Probe[$field]) { throw 'APPLY_MACRO_PROBE_FLAG_REJECTED' }
  }
  foreach ($field in @('capture_requested','inspection_requested','observation_requested','trial_macro_requested','editor_started_or_stopped','performance_pass')) {
    if ($Probe[$field] -isnot [bool] -or $Probe[$field]) { throw 'APPLY_MACRO_PROBE_FLAG_REJECTED' }
  }
  foreach ($field in @('apply_verified','apply_candidate_verified','apply_mutation_attempted','apply_backup_verified','apply_registry_verified','apply_reviewed_trial_verified')) {
    if ($Bridge[$field] -isnot [bool] -or -not $Bridge[$field] -or $Probe[$field] -isnot [bool] -or -not $Probe[$field]) {
      throw 'APPLY_MACRO_CANDIDATE_REJECTED'
    }
  }
  foreach ($field in @('apply_restore_attempted','apply_restore_verified')) {
    if ($Bridge[$field] -isnot [bool] -or $Bridge[$field] -or $Probe[$field] -isnot [bool] -or $Probe[$field]) {
      throw 'APPLY_MACRO_RESTORED_RESULT_REJECTED'
    }
  }
  foreach ($field in @('native_tool_attempted','native_tool_completed','native_tool_response_received')) {
    if ($Bridge[$field] -isnot [bool] -or -not $Bridge[$field]) { throw 'APPLY_MACRO_COMPLETION_REJECTED' }
  }
  if ($Bridge.apply_reviewed_trial_path -isnot [string] -or
      $Bridge.apply_reviewed_trial_path -cne 'D:\yacs\lesson07-remote\reports\39532652532-1\bridge.json' -or
      $Bridge.apply_reviewed_trial_sha256 -isnot [string] -or
      $Bridge.apply_reviewed_trial_sha256 -cne 'e901c56e83821e771816be8f4dff49cfdad21c015f0b516cd06368cce9d072f4' -or
      $Bridge.apply_reviewed_trial_source_commit -isnot [string] -or
      $Bridge.apply_reviewed_trial_source_commit -cne '71914188cbdaeac200074b8a070e2f44ed50e501') { throw 'APPLY_MACRO_REVIEWED_TRIAL_REJECTED' }
  if ($Bridge.apply_results -isnot [array] -or $Bridge.apply_results.Count -ne 7 -or
      $Bridge.apply_captures -isnot [Collections.IDictionary] -or $Bridge.apply_captures.Count -ne 1 -or
      $Bridge.apply_captures.Keys -cnotcontains 'B_applied_macro_005' -or
      ($Probe.apply_captures_received -isnot [int] -and $Probe.apply_captures_received -isnot [long]) -or
      $Probe.apply_captures_received -ne 1) { throw 'APPLY_MACRO_CAPTURE_SET_REJECTED' }
  foreach ($field in @('identity_before','identity_after')) {
    $other=$Probe[$field]
    if ($other -isnot [Collections.IDictionary]) { throw 'APPLY_MACRO_IDENTITY_REJECTED' }
    $observed=ConvertTo-L07ViewportUtc $other.observed_utc
    Assert-L07ViewportIdentity $other $Head $observed
    foreach ($key in @('pid','process_start_filetime_utc','executable','project')) {
      if ($other[$key] -cne $Identity[$key]) { throw 'APPLY_MACRO_IDENTITY_CHANGED' }
    }
    if ((ConvertTo-L07ViewportUtc $other.process_created_utc) -ne (ConvertTo-L07ViewportUtc $Identity.process_created_utc) -or
        $other.listener.port -ne $Identity.listener.port) { throw 'APPLY_MACRO_IDENTITY_CHANGED' }
  }
  if ((ConvertTo-L07ViewportUtc $Probe.identity_before.observed_utc) -ne $before) { throw 'APPLY_MACRO_IDENTITY_CHANGED' }
  $sessionId=$null
  foreach ($field in @('owner_before','owner_after')) {
    $owner=$Probe[$field]
    if ($owner -isnot [Collections.IDictionary] -or $owner.status -isnot [string] -or $owner.status -cne 'ATTACH_EXISTING' -or
        $owner.owner_sid_matches -isnot [bool] -or -not $owner.owner_sid_matches -or
        $owner.editor -isnot [Collections.IDictionary]) { throw 'APPLY_MACRO_OWNER_REJECTED' }
    $editor=$owner.editor
    if (($editor.editor_pid -isnot [int] -and $editor.editor_pid -isnot [long]) -or $editor.editor_pid -ne $Identity.pid -or
        $editor.editor_start_filetime_utc -isnot [string] -or $editor.editor_start_filetime_utc -cne $Identity.process_start_filetime_utc -or
        $editor.editor_executable_path -isnot [string] -or $editor.editor_executable_path -cne $Identity.executable -or
        $editor.canonical_project_matches -isnot [bool] -or -not $editor.canonical_project_matches -or
        ($editor.interactive_session_id -isnot [int] -and $editor.interactive_session_id -isnot [long]) -or
        $editor.interactive_session_id -le 0) { throw 'APPLY_MACRO_OWNER_REJECTED' }
    if ($null -ne $sessionId -and $sessionId -ne $editor.interactive_session_id) { throw 'APPLY_MACRO_OWNER_CHANGED' }
    $sessionId=$editor.interactive_session_id
  }
  $hostIdentity=$Bridge.external_host_identity
  if ($hostIdentity -isnot [Collections.IDictionary] -or
      ($hostIdentity.pid -isnot [int] -and $hostIdentity.pid -isnot [long]) -or $hostIdentity.pid -ne $Identity.pid) { throw 'APPLY_MACRO_BRIDGE_IDENTITY_REJECTED' }
  foreach ($key in @('executable','project')) {
    if ($hostIdentity[$key] -isnot [string] -or $hostIdentity[$key] -cne $Identity[$key]) { throw 'APPLY_MACRO_BRIDGE_IDENTITY_REJECTED' }
  }
  $createdTicks=(ConvertTo-L07ViewportUtc $Identity.process_created_utc).UtcTicks
  if ((ConvertTo-L07ViewportUtc $hostIdentity.process_created_utc).UtcTicks -ne ($createdTicks-($createdTicks%10)) -or
      (ConvertTo-L07ViewportUtc $hostIdentity.observed_utc).UtcTicks -ne ($before.UtcTicks-($before.UtcTicks%10)) -or
      $hostIdentity.listener -isnot [Collections.IDictionary] -or
      $hostIdentity.listener.address -isnot [string] -or $hostIdentity.listener.address -cne $Identity.listener.address -or
      ($hostIdentity.listener.port -isnot [int] -and $hostIdentity.listener.port -isnot [long]) -or $hostIdentity.listener.port -ne $Identity.listener.port -or
      ($hostIdentity.listener.pid -isnot [int] -and $hostIdentity.listener.pid -isnot [long]) -or $hostIdentity.listener.pid -ne $Identity.pid) {
    throw 'APPLY_MACRO_BRIDGE_IDENTITY_REJECTED'
  }
  $capture=$Bridge.apply_captures['B_applied_macro_005']
  $rows=@($Bridge.apply_results | Where-Object { $_ -is [Collections.IDictionary] -and $_['stage'] -is [string] -and $_['stage'] -ceq 'B_applied_macro_005' })
  if ($rows.Count -ne 1 -or $capture -isnot [Collections.IDictionary] -or $capture.Count -ne 4) { throw 'APPLY_MACRO_CAPTURE_ROW_REJECTED' }
  $row=$rows[0]
  if (($row.index -isnot [int] -and $row.index -isnot [long]) -or $row.index -ne 7 -or
      $row.tool_name -isnot [string] -or $row.tool_name -cne 'take_viewport_screenshot' -or
      $row.input_schema_sha256 -isnot [string] -or $row.input_schema_sha256 -cne '4ef41b0bf0c6c93d64a049687e0e43565fb351cd484169b58473801840b3dcdc') { throw 'APPLY_MACRO_CAPTURE_ROW_REJECTED' }
  foreach ($field in @('attempted','completed','response_received')) {
    if ($row[$field] -isnot [bool] -or -not $row[$field]) { throw 'APPLY_MACRO_CAPTURE_ROW_REJECTED' }
  }
  Assert-L07TrialCamera $row.arguments
  Assert-L07TrialCamera $capture.capture_arguments
  $result=$capture.capture_result
  if ($result -isnot [Collections.IDictionary] -or $row.result -isnot [Collections.IDictionary] -or
      $result.text -isnot [string] -or $result.text_truncated -isnot [bool] -or $result.text_truncated -or
      ($result.text_block_count -isnot [int] -and $result.text_block_count -isnot [long]) -or
      $result.text_block_count -lt 1 -or $result.text_block_count -gt 8 -or
      $result.response_sha256 -isnot [string] -or $result.response_sha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'APPLY_MACRO_CAPTURE_TEXT_REJECTED' }
  foreach ($key in @('text','text_truncated','text_block_count','response_sha256')) {
    if ($row.result[$key].GetType() -ne $result[$key].GetType() -or $row.result[$key] -cne $result[$key]) { throw 'APPLY_MACRO_CAPTURE_ROW_REJECTED' }
  }
  $started=ConvertTo-L07ViewportUtc $capture.native_tool_started_utc
  $finished=ConvertTo-L07ViewportUtc $capture.native_tool_response_received_utc
  if ((ConvertTo-L07ViewportUtc $row.started_utc) -ne $started -or
      (ConvertTo-L07ViewportUtc $row.response_received_utc) -ne $finished -or
      $started -lt $before -or $finished -lt $started -or $finished -gt $after) { throw 'APPLY_MACRO_CAPTURE_TIME_REJECTED' }
  return @{stage='B_applied_macro_005';path=(Get-L07ViewportSourcePath $result.text);started=$started;finished=$finished;session_id=$sessionId;response_sha256=$result.response_sha256}
}

function Assert-L07ViewportFileWindow([long]$Length,[DateTimeOffset]$Modified,[DateTimeOffset]$Started,[DateTimeOffset]$Finished) {
  if ($Length -le 0 -or $Length -gt 32MB) { throw 'VIEWPORT_FILE_SIZE_REJECTED' }
  if ($Modified -lt $Started -or $Modified -gt $Finished) { throw 'VIEWPORT_FILE_OUTSIDE_CAPTURE_WINDOW' }
}

function Read-L07ViewportBytes([string]$Path,[DateTimeOffset]$Started,[DateTimeOffset]$Finished) {
  Assert-L07ViewportPlainPath $Path
  $before=Get-Item -LiteralPath $Path
  if ($before.PSIsContainer) { throw 'VIEWPORT_SOURCE_NOT_FILE' }
  Assert-L07ViewportFileWindow $before.Length ([DateTimeOffset]$before.LastWriteTimeUtc) $Started $Finished
  $stream=[IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  try {
    if ($stream.Length -ne $before.Length) { throw 'VIEWPORT_SOURCE_CHANGED' }
    $bytes=[byte[]]::new([int]$before.Length)
    $stream.ReadExactly($bytes,0,$bytes.Length)
    $after=Get-Item -LiteralPath $Path
    if ($after.Length -ne $before.Length -or $after.LastWriteTimeUtc -ne $before.LastWriteTimeUtc) { throw 'VIEWPORT_SOURCE_CHANGED' }
    Assert-L07ViewportPlainPath $Path
  } finally { $stream.Dispose() }
  return @{bytes=$bytes;modified_utc=([DateTimeOffset]$before.LastWriteTimeUtc).ToString('o')}
}

function Test-L07ViewportJpeg([byte[]]$Bytes,[string]$PythonPath) {
  if ($Bytes.Length -lt 4 -or $Bytes.Length -gt 32MB -or $Bytes[0] -ne 255 -or $Bytes[1] -ne 216 -or
      $Bytes[2] -ne 255 -or $Bytes[-2] -ne 255 -or $Bytes[-1] -ne 217) { throw 'VIEWPORT_JPEG_SIGNATURE_REJECTED' }
  $code=@'
import io, json, sys, warnings
from PIL import Image
warnings.simplefilter('error')
try:
    data = sys.stdin.buffer.read(33554433)
    if not 0 < len(data) <= 33554432:
        raise ValueError()
    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size
        if image.format != 'JPEG' or not (0 < width <= 16384 and 0 < height <= 16384) or width * height > 67108864:
            raise ValueError()
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        image.load()
    print(json.dumps({'format': 'JPEG', 'width': width, 'height': height}))
except Exception:
    sys.exit(2)
'@
  $start=[Diagnostics.ProcessStartInfo]::new()
  $start.FileName=$PythonPath; $start.UseShellExecute=$false; $start.CreateNoWindow=$true
  $start.RedirectStandardInput=$true; $start.RedirectStandardOutput=$true; $start.RedirectStandardError=$true
  foreach ($argument in @('-I','-B','-c',$code)) { $start.ArgumentList.Add($argument) }
  $process=[Diagnostics.Process]::new(); $process.StartInfo=$start; $launched=$false
  try {
    if (-not $process.Start()) { throw 'VIEWPORT_JPEG_VERIFIER_UNAVAILABLE' }
    $launched=$true
    $stdout=$process.StandardOutput.ReadToEndAsync(); $stderr=$process.StandardError.ReadToEndAsync()
    $write=$process.StandardInput.BaseStream.WriteAsync($Bytes,0,$Bytes.Length)
    if (-not $write.Wait(15000)) { throw 'VIEWPORT_JPEG_VERIFIER_TIMEOUT' }
    $process.StandardInput.Close()
    if (-not $process.WaitForExit(15000)) { throw 'VIEWPORT_JPEG_VERIFIER_TIMEOUT' }
    $output=$stdout.GetAwaiter().GetResult(); $errorText=$stderr.GetAwaiter().GetResult()
    if ($process.ExitCode -ne 0 -or $output.Length -gt 1024 -or $errorText.Length) { throw 'VIEWPORT_JPEG_INVALID' }
    $result=$output | ConvertFrom-Json -AsHashtable -DateKind String
    if ($result.format -cne 'JPEG' -or $result.width -le 0 -or $result.height -le 0) { throw 'VIEWPORT_JPEG_INVALID' }
    return $result
  } finally {
    if ($launched -and -not $process.HasExited) { $process.Kill() }
    $process.Dispose()
  }
}

function Copy-L07ViewportExactBytes([byte[]]$Bytes,[string]$Destination) {
  $sha256=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes)).ToLowerInvariant()
  $stream=[IO.File]::Open($Destination,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
  try {
    $stream.Write($Bytes,0,$Bytes.Length); $stream.Flush($true); $stream.Position=0
    $copied=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($stream)).ToLowerInvariant()
    if ($copied -cne $sha256 -or $stream.Length -ne $Bytes.Length) { throw 'VIEWPORT_COPY_HASH_MISMATCH' }
  } finally { $stream.Dispose() }
  return $sha256
}

$reportRoot=Join-Path 'D:\yacs\lesson07-remote\reports' $RunToken
Assert-L07ViewportPlainPath $reportRoot
$identityProof=Read-L07ViewportProof (Join-Path $reportRoot 'identity.json') 64KB
$probeProof=Read-L07ViewportProof (Join-Path $reportRoot 'probe.json') 64KB
$bridgeProof=Read-L07ViewportProof (Join-Path $reportRoot 'bridge.json') 2MB
$identity=$identityProof.data
if ($ApplyReviewedMacro) {
  $capture=Assert-L07AppliedViewportProofs $identity $probeProof.data $bridgeProof.data $ExpectedHead ([DateTimeOffset]::UtcNow)
  $imagePath=Join-Path $reportRoot 'apply-macro.jpg'
  $manifestPath=Join-Path $reportRoot 'apply-macro.json'
  if ((Test-Path -LiteralPath $imagePath) -or (Test-Path -LiteralPath $manifestPath)) { throw 'VIEWPORT_OUTPUT_ALREADY_EXISTS' }
  Assert-L07ViewportProcess $identity $capture.session_id
  $source=Read-L07ViewportBytes $capture.path $capture.started $capture.finished
  $dimensions=Test-L07ViewportJpeg $source.bytes 'D:\yacs\tool-cache\material-forge\python\Scripts\python.exe'
  Assert-L07ViewportProcess $identity $capture.session_id
  Assert-L07ViewportPlainPath $reportRoot
  $hash=Copy-L07ViewportExactBytes $source.bytes $imagePath
  Assert-L07ViewportProcess $identity $capture.session_id
  Assert-L07ViewportPlainPath $imagePath
  $manifest=[ordered]@{
    schema_version=1;status='APPLY_MACRO_VIEWPORT_RETAINED_REVIEW_PENDING';stage=$capture.stage;source_commit=$ExpectedHead;run_token=$RunToken
    observed_utc=[DateTimeOffset]::UtcNow.ToString('o');source_path=$capture.path;copied_path=$imagePath
    sha256=$hash;source_sha256=$hash;byte_count=$source.bytes.Length;format='JPEG';width=$dimensions.width;height=$dimensions.height
    source_last_write_utc=$source.modified_utc;native_tool_started_utc=$capture.started.ToString('o');native_tool_response_received_utc=$capture.finished.ToString('o')
    process_id=$identity.pid;process_start_filetime_utc=$identity.process_start_filetime_utc;interactive_session_id=$capture.session_id
    identity_sha256=$identityProof.sha256;probe_sha256=$probeProof.sha256;bridge_sha256=$bridgeProof.sha256
    capture_response_sha256=$capture.response_sha256;operation_native_tool_calls=7;capture_native_tool_calls=1;additional_native_tool_calls=0
    apply_status=$bridgeProof.data.status;apply_verified=$true;apply_candidate_verified=$true;apply_restore_attempted=$false;apply_restore_verified=$false
    apply_reviewed_trial_path=$bridgeProof.data.apply_reviewed_trial_path;apply_reviewed_trial_sha256=$bridgeProof.data.apply_reviewed_trial_sha256
    apply_reviewed_trial_source_commit=$bridgeProof.data.apply_reviewed_trial_source_commit
    native_material_readback='REVIEWED_MACRO_APPLIED_CAPTURE_REVIEW_PENDING';whole_material_accepted=$false;visual_accepted=$false;performance_pass=$false
  }
  $encoded=[Text.UTF8Encoding]::new($false).GetBytes(($manifest | ConvertTo-Json -Depth 5 -Compress)+"`n")
  if ($encoded.Length -gt 16KB) { throw 'VIEWPORT_MANIFEST_SIZE' }
  $null=Copy-L07ViewportExactBytes $encoded $manifestPath
  Write-Host ('L07_REVIEWED_MACRO_VIEWPORT_RETAINED '+$dimensions.width+'x'+$dimensions.height+' sha256='+$hash)
  return
}
if ($TrialMacro) {
  $trial=Assert-L07TrialViewportProofs $identity $probeProof.data $bridgeProof.data $ExpectedHead ([DateTimeOffset]::UtcNow)
  $names=@{A_baseline='trial-macro-A-baseline';B_macro_005='trial-macro-B-005';A_restored='trial-macro-A-restored'}
  $aggregatePath=Join-Path $reportRoot 'trial-macro.json'
  if (Test-Path -LiteralPath $aggregatePath) { throw 'VIEWPORT_OUTPUT_ALREADY_EXISTS' }
  foreach ($capture in $trial.captures) {
    foreach ($suffix in @('.jpg','.json')) {
      if (Test-Path -LiteralPath (Join-Path $reportRoot ($names[$capture.stage]+$suffix))) { throw 'VIEWPORT_OUTPUT_ALREADY_EXISTS' }
    }
  }
  $retained=[Collections.Generic.List[object]]::new()
  foreach ($capture in $trial.captures) {
    Assert-L07ViewportProcess $identity $capture.session_id
    $source=Read-L07ViewportBytes $capture.path $capture.started $capture.finished
    $dimensions=Test-L07ViewportJpeg $source.bytes 'D:\yacs\tool-cache\material-forge\python\Scripts\python.exe'
    Assert-L07ViewportProcess $identity $capture.session_id
    Assert-L07ViewportPlainPath $reportRoot
    $imagePath=Join-Path $reportRoot ($names[$capture.stage]+'.jpg')
    $hash=Copy-L07ViewportExactBytes $source.bytes $imagePath
    Assert-L07ViewportProcess $identity $capture.session_id
    Assert-L07ViewportPlainPath $imagePath
    $manifest=[ordered]@{
      schema_version=1;status='TRIAL_MACRO_VIEWPORT_RETAINED';stage=$capture.stage;source_commit=$ExpectedHead;run_token=$RunToken
      observed_utc=[DateTimeOffset]::UtcNow.ToString('o');source_path=$capture.path;copied_path=$imagePath
      sha256=$hash;source_sha256=$hash;byte_count=$source.bytes.Length;format='JPEG';width=$dimensions.width;height=$dimensions.height
      source_last_write_utc=$source.modified_utc;native_tool_started_utc=$capture.started.ToString('o');native_tool_response_received_utc=$capture.finished.ToString('o')
      process_id=$identity.pid;process_start_filetime_utc=$identity.process_start_filetime_utc;interactive_session_id=$capture.session_id
      identity_sha256=$identityProof.sha256;probe_sha256=$probeProof.sha256;bridge_sha256=$bridgeProof.sha256
      capture_response_sha256=$capture.response_sha256;capture_native_tool_calls=1;additional_native_tool_calls=0
      trial_status=$bridgeProof.data.status;trial_restore_verified=$true
      native_material_readback='TRIAL_BASELINE_RESTORED_CAPTURE_REVIEW_PENDING';visual_accepted=$false;performance_pass=$false
    }
    $encoded=[Text.UTF8Encoding]::new($false).GetBytes(($manifest | ConvertTo-Json -Depth 5 -Compress)+"`n")
    if ($encoded.Length -gt 16KB) { throw 'VIEWPORT_MANIFEST_SIZE' }
    $null=Copy-L07ViewportExactBytes $encoded (Join-Path $reportRoot ($names[$capture.stage]+'.json'))
    $retained.Add(@{stage=$capture.stage;name=($names[$capture.stage]+'.jpg');sha256=$hash})
    Write-Host ('L07_TRIAL_MACRO_VIEWPORT_RETAINED '+$capture.stage+' '+$dimensions.width+'x'+$dimensions.height+' sha256='+$hash)
  }
  $aggregate=[ordered]@{
    schema_version=1;status=$(if ($trial.complete) { 'TRIAL_MACRO_CAPTURES_RETAINED_REVIEW_PENDING' } else { 'TRIAL_MACRO_CAPTURES_PARTIAL_RESTORED_REVIEW_PENDING' })
    source_commit=$ExpectedHead;run_token=$RunToken;trial_restore_verified=$true;trial_status=$bridgeProof.data.status
    capture_count=$retained.Count;captures=$retained.ToArray();additional_native_tool_calls=0
    identity_sha256=$identityProof.sha256;probe_sha256=$probeProof.sha256;bridge_sha256=$bridgeProof.sha256
    visual_accepted=$false;performance_pass=$false
  }
  $encoded=[Text.UTF8Encoding]::new($false).GetBytes(($aggregate | ConvertTo-Json -Depth 5 -Compress)+"`n")
  if ($encoded.Length -gt 16KB) { throw 'VIEWPORT_MANIFEST_SIZE' }
  $null=Copy-L07ViewportExactBytes $encoded $aggregatePath
  return
}
$capture=Assert-L07ViewportProofs $identity $probeProof.data $bridgeProof.data $ExpectedHead ([DateTimeOffset]::UtcNow)
$imagePath=Join-Path $reportRoot 'current-viewport.jpg'
$manifestPath=Join-Path $reportRoot 'viewport.json'
if ((Test-Path -LiteralPath $imagePath) -or (Test-Path -LiteralPath $manifestPath)) { throw 'VIEWPORT_OUTPUT_ALREADY_EXISTS' }
Assert-L07ViewportProcess $identity $capture.session_id
$source=Read-L07ViewportBytes $capture.path $capture.started $capture.finished
$dimensions=Test-L07ViewportJpeg $source.bytes 'D:\yacs\tool-cache\material-forge\python\Scripts\python.exe'
Assert-L07ViewportProcess $identity $capture.session_id
Assert-L07ViewportPlainPath $reportRoot
$hash=Copy-L07ViewportExactBytes $source.bytes $imagePath
Assert-L07ViewportProcess $identity $capture.session_id
Assert-L07ViewportPlainPath $imagePath
$manifest=[ordered]@{
  schema_version=1;status='VIEWPORT_CAPTURE_RETAINED';source_commit=$ExpectedHead;run_token=$RunToken
  observed_utc=[DateTimeOffset]::UtcNow.ToString('o');source_path=$capture.path;copied_path=$imagePath
  sha256=$hash;source_sha256=$hash;byte_count=$source.bytes.Length;format='JPEG'
  width=$dimensions.width;height=$dimensions.height;source_last_write_utc=$source.modified_utc
  native_tool_started_utc=$capture.started.ToString('o');native_tool_response_received_utc=$capture.finished.ToString('o')
  process_id=$identity.pid;process_start_filetime_utc=$identity.process_start_filetime_utc;interactive_session_id=$capture.session_id
  identity_sha256=$identityProof.sha256;probe_sha256=$probeProof.sha256;bridge_sha256=$bridgeProof.sha256
  capture_response_sha256=$bridgeProof.data.capture_result.response_sha256
  capture_native_tool_calls=1;additional_native_tool_calls=0;native_material_readback='NOT_RUN';visual_accepted=$false;performance_pass=$false
}
$encoded=[Text.UTF8Encoding]::new($false).GetBytes(($manifest | ConvertTo-Json -Depth 5 -Compress)+"`n")
if ($encoded.Length -gt 16KB) { throw 'VIEWPORT_MANIFEST_SIZE' }
$null=Copy-L07ViewportExactBytes $encoded $manifestPath
Write-Host ('L07_VIEWPORT_CAPTURE_RETAINED '+$dimensions.width+'x'+$dimensions.height+' sha256='+$hash)
