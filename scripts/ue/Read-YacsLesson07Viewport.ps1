#requires -Version 7.5
<#
.SYNOPSIS
  Retain the exact JPEG returned by this run's dedicated viewport capture.
.DESCRIPTION
  Reads existing receipts and one bounded file. It never calls Unreal, selects
  a newest file, retries capture, changes the camera, or modifies source assets.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedHead,
  [Parameter(Mandatory)][ValidatePattern('^[0-9]{1,20}-[0-9]{1,10}$')][string]$RunToken
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
