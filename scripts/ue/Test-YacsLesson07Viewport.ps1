#requires -Version 7.5
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$source=Join-Path $PSScriptRoot 'Read-YacsLesson07Viewport.ps1'
$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if (@($errors).Count) { throw ($errors | Out-String) }
# Only load function definitions. The remote entrypoint is never executed.
foreach ($node in $ast.FindAll({param($candidate)
  $candidate -is [Management.Automation.Language.FunctionDefinitionAst]
},$false)) { . ([scriptblock]::Create($node.Extent.Text)) }
function Require([bool]$Value,[string]$Message) { if (-not $Value) { throw $Message } }
function Copy-Data($Value) { return ($Value | ConvertTo-Json -Depth 16 | ConvertFrom-Json -AsHashtable -DateKind String) }
function Expect-Rejection([scriptblock]$Action) {
  $rejected=$false
  try { $null=& $Action } catch { $rejected=$true }
  Require $rejected 'Invalid viewport input was admitted.'
}
$cases=0
$path='D:\yacs\project\Saved\LocoHelperAI\ViewportShots\Viewport_20261021-001500.jpg'
foreach ($text in @(
  $path,('Screenshot saved to '+$path),('Screenshot saved to `'+$path+'`'),
  ('{"file_path":"'+$path.Replace('\','\\')+'","width":1920}'),
  ('{"result":{"path":"'+$path.Replace('\','/')+'"}}'),
  ($path+"`n"+$path)
)) {
  Require ((Get-L07ViewportSourcePath $text) -ceq $path) 'Exact path extraction failed.'; $cases++
}
Require ((Assert-L07ViewportSourcePath $path.Replace('.jpg','.JPEG')) -ieq $path.Replace('.jpg','.jpeg')) 'JPEG suffix rejected.'; $cases++
foreach ($bad in @(
  '',('x'*16385),'No file was returned.',
  ($path+"`n"+$path.Replace('001500','001501')),
  $path.Replace('D:','E:'),$path.Replace('ViewportShots\','ViewportShots\sub\'),
  $path.Replace('ViewportShots\','ViewportShots\..\'),
  $path.Replace('ViewportShots\','ViewportShots2\'),
  ($path+':evil'),($path+'.exe'),($path+'?download=1'),
  ('\\server\share\'+$path.Substring(3)),('\\?\'+$path),('file:///'+$path.Replace('\','/')),
  $path.Replace('Viewport_20261021-001500','CON'),
  $path.Replace('Viewport_20261021-001500','.hidden'),
  $path.Replace('Viewport_20261021-001500','name with spaces'),
  ('{"path":"'+$path.Replace('\','\\')+'"'),
  ('{"path":"'+$path.Replace('\','\\')+'","other":"E:/other.jpg"}')
)) {
  Expect-Rejection { Get-L07ViewportSourcePath $bad }; $cases++
}

$head='f485b18217deba19bc881aa78d22e5f862d13e3e'
$now=[DateTimeOffset]::Parse('2026-10-21T00:16:00Z')
$identity=Copy-Data @{
  status='L07_WINGMAN_HOST_IDENTITY_VERIFIED';source_commit=$head;pid=17896
  process_start_filetime_utc='134370120000674689';process_created_utc='2026-10-20T23:20:00.0674680Z'
  observed_utc='2026-10-21T00:15:00Z'
  executable='D:\yacs\engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
  project='D:\yacs\project\YetAnotherCyclingSim.uproject';canonical_project_argument_matches=$true
  listener=@{address='127.0.0.1';port=19315;pid=17896}
}
$owner=@{status='ATTACH_EXISTING';owner_sid_matches=$true;editor=@{
  editor_pid=17896;editor_start_filetime_utc='134370120000674689'
  editor_executable_path=$identity.executable;canonical_project_matches=$true;interactive_session_id=1
}}
$probe=Copy-Data @{
  status='LESSON07_CAPTURE_RESPONSE_RECEIVED_FILE_PENDING';source_commit=$head
  capture_requested=$true;existing_owner_required=$true;identity_stable_across_probe=$true
  observation_requested=$false;native_tool_called=$true;native_tool_attempted=$true;native_tool_completed=$true
  native_tool_call_attempts=1;editor_started_or_stopped=$false;client_exit_code=0;native_material_readback='NOT_RUN'
  owner_before=$owner;owner_after=$owner;identity_before=$identity;identity_after=$identity
}
$probe.identity_after.observed_utc='2026-10-21T00:15:03Z'
$bridge=Copy-Data @{
  status='CAPTURE_RESPONSE_RECEIVED';native_tool_name='take_viewport_screenshot';native_tool_calls=1
  native_tool_attempted=$true;native_tool_completed=$true;native_tool_response_received=$true
  native_material_readback='NOT_RUN';native_tool_started_utc='2026-10-21T00:15:01Z'
  native_tool_response_received_utc='2026-10-21T00:15:02Z'
  capture_input_schema_sha256='4ef41b0bf0c6c93d64a049687e0e43565fb351cd484169b58473801840b3dcdc'
  capture_arguments=@{return_image=$false};external_host_identity=$identity
  capture_result=@{text=$path;text_truncated=$false;text_block_count=1;response_sha256=('a'*64)}
}
$validated=Assert-L07ViewportProofs $identity $probe $bridge $head $now
Require ($validated.path -ceq $path -and $validated.session_id -eq 1) 'Valid capture proof rejected.'; $cases++
$preciseIdentity=Copy-Data $identity; $preciseProbe=Copy-Data $probe; $preciseBridge=Copy-Data $bridge
$preciseIdentity.observed_utc='2026-10-21T00:15:00.1234567Z'
$preciseProbe.identity_before.observed_utc=$preciseIdentity.observed_utc
$preciseBridge.external_host_identity.observed_utc='2026-10-21T00:15:00.123456+00:00'
$null=Assert-L07ViewportProofs $preciseIdentity $preciseProbe $preciseBridge $head $now; $cases++
$preciseBridge.external_host_identity.observed_utc='2026-10-21T00:15:00.123455+00:00'
Expect-Rejection { Assert-L07ViewportProofs $preciseIdentity $preciseProbe $preciseBridge $head $now }; $cases++
foreach ($change in @(
  @{key='status';value=@('L07_WINGMAN_HOST_IDENTITY_VERIFIED','L07_WINGMAN_HOST_IDENTITY_VERIFIED')},
  @{key='source_commit';value=('a'*40)},@{key='pid';value=17897},@{key='pid';value='17896'},
  @{key='process_start_filetime_utc';value='134370120000674690'},
  @{key='canonical_project_argument_matches';value='true'},
  @{key='observed_utc';value='2026-10-21T00:13:59Z'},
  @{key='observed_utc';value='2026-10-21T00:16:01Z'},
  @{key='observed_utc';value='2026-10-21T00:15:00'},
  @{key='project';value='D:\yacs\project\other.uproject'}
)) {
  $bad=Copy-Data $identity; $bad[$change.key]=$change.value
  Expect-Rejection { Assert-L07ViewportProofs $bad $probe $bridge $head $now }; $cases++
}
foreach ($change in @(
  @{key='status';value='LESSON07_CAPTURE_INCOMPLETE_EDITOR_RETAINED'},
  @{key='source_commit';value=('a'*40)},@{key='capture_requested';value='true'},
  @{key='native_tool_call_attempts';value=0},@{key='native_tool_call_attempts';value='1'},
  @{key='native_tool_completed';value=$false},@{key='editor_started_or_stopped';value=$true},
  @{key='observation_requested';value=$true},@{key='existing_owner_required';value=$false},
  @{key='client_exit_code';value=1}
)) {
  $bad=Copy-Data $probe; $bad[$change.key]=$change.value
  Expect-Rejection { Assert-L07ViewportProofs $identity $bad $bridge $head $now }; $cases++
}
$bad=Copy-Data $probe; $bad.owner_after.owner_sid_matches=$false
Expect-Rejection { Assert-L07ViewportProofs $identity $bad $bridge $head $now }; $cases++
$bad=Copy-Data $probe; $bad.owner_after.editor.interactive_session_id=2
Expect-Rejection { Assert-L07ViewportProofs $identity $bad $bridge $head $now }; $cases++
$bad=Copy-Data $probe; $bad.identity_after.process_start_filetime_utc='134370120000674690'
Expect-Rejection { Assert-L07ViewportProofs $identity $bad $bridge $head $now }; $cases++
foreach ($change in @(
  @{key='status';value='CAPTURE_FAILED'},@{key='native_tool_name';value='execute_python'},
  @{key='native_tool_calls';value=2},@{key='native_tool_completed';value=$null},
  @{key='capture_input_schema_sha256';value=('a'*64)},
  @{key='capture_arguments';value=@{return_image=$true}},
  @{key='capture_arguments';value=@{return_image=$false;fov=90}},
  @{key='native_tool_started_utc';value='2026-10-21T00:14:59Z'},
  @{key='native_tool_response_received_utc';value='2026-10-21T00:15:00Z'},
  @{key='native_tool_response_received_utc';value='2026-10-21T00:15:04Z'}
)) {
  $bad=Copy-Data $bridge; $bad[$change.key]=$change.value
  Expect-Rejection { Assert-L07ViewportProofs $identity $probe $bad $head $now }; $cases++
}
foreach ($change in @(
  @{key='text_truncated';value=$true},@{key='text_truncated';value='false'},
  @{key='text_block_count';value=9},@{key='response_sha256';value='not-a-sha256'}
)) {
  $bad=Copy-Data $bridge; $bad.capture_result[$change.key]=$change.value
  Expect-Rejection { Assert-L07ViewportProofs $identity $probe $bad $head $now }; $cases++
}
$bad=Copy-Data $bridge; $bad.external_host_identity.pid=17897
Expect-Rejection { Assert-L07ViewportProofs $identity $probe $bad $head $now }; $cases++
$bad=Copy-Data $bridge; $bad.status=@('CAPTURE_RESPONSE_RECEIVED','CAPTURE_RESPONSE_RECEIVED')
Expect-Rejection { Assert-L07ViewportProofs $identity $probe $bad $head $now }; $cases++

$started=[DateTimeOffset]::Parse('2026-10-21T00:15:01Z')
$finished=$started.AddSeconds(1)
Assert-L07ViewportFileWindow 32MB $started $started $finished; $cases++
Assert-L07ViewportFileWindow 1 $finished $started $finished; $cases++
Expect-Rejection { Assert-L07ViewportFileWindow 0 $started $started $finished }; $cases++
Expect-Rejection { Assert-L07ViewportFileWindow (32MB+1) $started $started $finished }; $cases++
Expect-Rejection { Assert-L07ViewportFileWindow 10 $started.AddTicks(-1) $started $finished }; $cases++
Expect-Rejection { Assert-L07ViewportFileWindow 10 $finished.AddTicks(1) $started $finished }; $cases++

# A synthetic 2x3 JPEG fixture, unrelated to the user's viewport or material.
$jpeg=[Convert]::FromBase64String('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAADAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDjaKKK988E/9k=')
$python=if ($IsWindows) { 'D:\yacs\tool-cache\material-forge\python\Scripts\python.exe' } else { (Get-Command python -CommandType Application).Source }
$dimensions=Test-L07ViewportJpeg $jpeg $python
Require ($dimensions.width -eq 2 -and $dimensions.height -eq 3) 'JPEG validation lost dimensions.'; $cases++
Expect-Rejection { Test-L07ViewportJpeg ([byte[]](137,80,78,71)) $python }; $cases++
Expect-Rejection { Test-L07ViewportJpeg ([byte[]]$jpeg[0..($jpeg.Length-2)]) $python }; $cases++
Expect-Rejection { Test-L07ViewportJpeg ([byte[]](255,216,255,0,0,255,217)) $python }; $cases++

$temp=Join-Path ([IO.Path]::GetTempPath()) ('yacs-l07-viewport-test-'+[guid]::NewGuid().ToString('N'))
$null=New-Item -ItemType Directory -Path $temp
try {
  $inputPath=Join-Path $temp 'source.jpg'; $outputPath=Join-Path $temp 'current-viewport.jpg'
  [IO.File]::WriteAllBytes($inputPath,$jpeg)
  [IO.File]::SetLastWriteTimeUtc($inputPath,$started.AddMilliseconds(500).UtcDateTime)
  $read=Read-L07ViewportBytes $inputPath $started $finished
  $hash=Copy-L07ViewportExactBytes $read.bytes $outputPath
  $expected=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($jpeg)).ToLowerInvariant()
  Require ($hash -ceq $expected -and (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $expected) 'Copy hash differs.'
  Require ([Convert]::ToBase64String([IO.File]::ReadAllBytes($outputPath)) -ceq [Convert]::ToBase64String($jpeg)) 'Copy bytes differ.'; $cases++
  Expect-Rejection { Copy-L07ViewportExactBytes ([byte[]](1,2,3)) $outputPath }
  Require ((Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $expected) 'Existing copy was overwritten.'; $cases++
  [IO.File]::SetLastWriteTimeUtc($inputPath,$started.AddSeconds(-1).UtcDateTime)
  Expect-Rejection { Read-L07ViewportBytes $inputPath $started $finished }; $cases++
  $proofPath=Join-Path $temp 'proof.json'
  [IO.File]::WriteAllText($proofPath,'{"status":"fixture"}',[Text.UTF8Encoding]::new($false))
  $proof=Read-L07ViewportProof $proofPath 64KB
  Require ($proof.data.status -ceq 'fixture' -and $proof.sha256 -ceq (Get-FileHash $proofPath).Hash.ToLowerInvariant()) 'Bounded proof receipt/hash failed.'; $cases++
  Expect-Rejection { Read-L07ViewportProof $proofPath 1 }; $cases++
  if (-not $IsWindows) {
    # Actual symlink detection, without requiring Windows symlink privileges.
    $link=Join-Path $temp 'linked.jpg'
    $null=New-Item -ItemType SymbolicLink -Path $link -Target $inputPath
    Expect-Rejection { Assert-L07ViewportPlainPath $link }; $cases++
  }
} finally { Remove-Item -LiteralPath $temp -Recurse -Force }
Write-Output ('{"status":"LESSON07_VIEWPORT_TESTS_PASS","cases":'+$cases+',"native_host_actions":false}')
