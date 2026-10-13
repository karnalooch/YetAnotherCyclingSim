#requires -Version 7.4
<# Install a read-only progress HUD into the existing local Pixel Streaming page.
No Unreal code, process, scene, port, or command endpoint is changed. #>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedHead,
  [switch]$Apply,
  [switch]$Rollback
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if ($Apply -and $Rollback) { throw 'Choose apply or rollback.' }
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if ((& git -C $repo rev-parse HEAD).Trim() -cne $ExpectedHead -or
    @(& git -C $repo status --porcelain --untracked-files=no).Count) {
  throw 'Exact clean committed source required.'
}
$web='D:\yacs\engine\UE_5.8\Engine\Plugins\Media\PixelStreaming2\Resources\WebServers\SignallingWebServer\www'
$state='D:\yacs\live-host\state\progress-overlay'
$html=Join-Path $web 'player.html'
$manifest=Join-Path $state 'current.json'
$pending=Join-Path $state 'pending.json'
function Assert-PlainPath([string]$Path) {
  $cursor=[IO.Path]::GetFullPath($Path)
  while ($cursor) {
    if (Test-Path -LiteralPath $cursor) {
      if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse path refused: $cursor" }
    }
    $next=Split-Path $cursor -Parent
    if ($next -ceq $cursor) { break }
    $cursor=$next
  }
}
function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
foreach ($path in @($web,$state,$html,$manifest,$pending)) { Assert-PlainPath $path }
if (Test-Path -LiteralPath $pending) {
  $prepared=Get-Content -LiteralPath $pending -Raw | ConvertFrom-Json
  if ((Hash $html) -ceq $prepared.installed_html_sha256) {
    if ($Apply -or $Rollback) { Move-Item -LiteralPath $pending -Destination $manifest -Force }
    else { throw 'Interrupted deployment is recoverable; use Apply to finalize its receipt.' }
  } else { throw 'Pending overlay deployment requires inspection; preserved original is available.' }
}
$previous=$null
if (Test-Path -LiteralPath $manifest) {
  $previous=Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
  if ((Hash $html) -cne $previous.installed_html_sha256) { throw 'Viewer changed outside the recorded deployment.' }
}
if ($Rollback) {
  if (-not $previous -or $previous.source_sha -cne $ExpectedHead) { throw 'No matching overlay deployment.' }
  $backup=Join-Path $state ($previous.original_html_sha256 + '.html')
  Assert-PlainPath $backup
  if ((Hash $backup) -cne $previous.original_html_sha256) { throw 'Original page backup changed.' }
  $scratch=Join-Path $web 'yacs-player-rollback.tmp'
  Assert-PlainPath $scratch
  if (Test-Path -LiteralPath $scratch) { throw 'Rollback scratch already exists.' }
  Copy-Item -LiteralPath $backup -Destination $scratch
  Move-Item -LiteralPath $scratch -Destination $html -Force
  Move-Item -LiteralPath $manifest -Destination (Join-Path $state ($ExpectedHead+'.rolled-back.json'))
  Write-Output 'PROGRESS_OVERLAY_ROLLED_BACK_EDITOR_UNCHANGED'
  return
}
$source=Join-Path $PSScriptRoot 'remote-progress.js'
$name="yacs-progress-$ExpectedHead.js"
$destination=Join-Path $web $name
Assert-PlainPath $destination
if ($previous -and $previous.source_sha -ceq $ExpectedHead) {
  if ((Hash $destination) -cne (Hash $source)) { throw 'Installed overlay differs.' }
  Write-Output 'PROGRESS_OVERLAY_ALREADY_INSTALLED'
  return
}
$originalBytes=[IO.File]::ReadAllBytes($html)
$originalHash=Hash $html
if ($previous) {
  $originalHash=[string]$previous.original_html_sha256
  $oldBackup=Join-Path $state ($originalHash+'.html')
  Assert-PlainPath $oldBackup
  if ((Hash $oldBackup) -cne $originalHash) { throw 'Original page backup differs.' }
  $originalBytes=[IO.File]::ReadAllBytes($oldBackup)
}
$original=[Text.Encoding]::UTF8.GetString($originalBytes)
if ([regex]::Matches($original,'</head>').Count -ne 1 -or $original.Contains('yacs-progress-')) { throw 'Unexpected stock viewer markup.' }
$patched=$original.Replace('</head>',('<script defer src="/'+$name+'"></script></head>'))
if (-not $Apply) {
  [ordered]@{status='PROGRESS_OVERLAY_DRY_RUN';source_sha=$ExpectedHead;viewer='http://127.0.0.1/';original_sha256=$originalHash;editor_restarted=$false} | ConvertTo-Json
  return
}
$raw=& gh api "repos/karnalooch/YetAnotherCyclingSim/actions/runs?event=pull_request&head_sha=$ExpectedHead&per_page=100"
if ($LASTEXITCODE -ne 0) { throw 'Protected CI lookup failed.' }
$runs=($raw | ConvertFrom-Json).workflow_runs
$ci=@($runs | Where-Object { $_.name -ceq 'CyclingSim CI' -and $_.head_sha -ceq $ExpectedHead } | Sort-Object created_at -Descending)
if (-not $ci.Count -or $ci[0].status -cne 'completed' -or $ci[0].conclusion -cne 'success') { throw 'Exact-head protected CI not successful.' }
[void][IO.Directory]::CreateDirectory($state)
$backup=Join-Path $state ($originalHash+'.html')
Assert-PlainPath $backup
if (-not (Test-Path -LiteralPath $backup)) { [IO.File]::WriteAllBytes($backup,$originalBytes) }
if ((Hash $backup) -cne $originalHash) { throw 'Backup readback differs.' }
if (Test-Path -LiteralPath $destination) { throw 'Immutable overlay target exists without matching deployment.' }
Copy-Item -LiteralPath $source -Destination $destination
if ((Hash $destination) -cne (Hash $source)) { throw 'Overlay copy differs.' }
$scratch=Join-Path $web 'yacs-player-install.tmp'
Assert-PlainPath $scratch
if (Test-Path -LiteralPath $scratch) { throw 'Install scratch already exists.' }
[IO.File]::WriteAllText($scratch,$patched,[Text.UTF8Encoding]::new($false))
$receipt=[ordered]@{schema_version=1;source_sha=$ExpectedHead;ci_run_id=$ci[0].id;original_html_sha256=$originalHash;installed_html_sha256=(Hash $scratch);script_sha256=(Hash $destination);installed_utc=[DateTime]::UtcNow.ToString('o');editor_restarted=$false}
$receipt | ConvertTo-Json | Set-Content -LiteralPath $pending -Encoding utf8
Move-Item -LiteralPath $scratch -Destination $html -Force
Move-Item -LiteralPath $pending -Destination $manifest -Force
Write-Output 'PROGRESS_OVERLAY_INSTALLED_RELOAD_VIEWER'
