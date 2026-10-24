#requires -Version 7.4
<#
.SYNOPSIS
  Submit one allowlisted visual instruction to an independently running Editor.
.DESCRIPTION
  Never accepts code, command text, arbitrary paths, arbitrary coordinates,
  asset/terrain mutation, or a restart flag. No GitHub job may own the Editor.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidateSet('inspect','focus_site','focus_road','set_markers_visible','run_recipe')][string]$Action,
  [ValidateSet('P0','P1','P2','P3','P4')][string]$Site,
  [Nullable[bool]]$Visible,
  [ValidatePattern('^[a-z][a-z0-9_]{2,47}$')][string]$Recipe,
  [ValidatePattern('^[a-f0-9]{40}$')][string]$RecipeRevision,
  [ValidateSet('preview','author')][string]$Intent='preview',
  [string]$ParametersJson,
  [string]$InstallRoot = 'D:\yacs\live-host'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$InstallRoot=[IO.Path]::GetFullPath($InstallRoot)
if ($InstallRoot -ine 'D:\yacs\live-host') { throw 'Command target must be the dedicated Live Host.' }
if ($Action -ceq 'focus_site' -and -not $Site) { throw 'Fixed P0-P4 site required.' }
if ($Action -cne 'focus_site' -and $Site) { throw 'Unexpected camera coordinate/site.' }
if ($Action -ceq 'set_markers_visible' -and $null -eq $Visible) { throw 'Explicit visibility boolean required.' }
if ($Action -cne 'set_markers_visible' -and $null -ne $Visible) { throw 'Unexpected visibility argument.' }
if ($Action -ceq 'run_recipe') {
  if (-not $Recipe -or -not $RecipeRevision -or -not $ParametersJson) { throw 'Exact recipe, SHA and typed JSON parameters required.' }
  if ([Text.Encoding]::UTF8.GetByteCount($ParametersJson) -gt 2048) { throw 'Recipe parameters exceed bound.' }
} elseif ($Recipe -or $RecipeRevision -or $ParametersJson) {
  throw 'Non-recipe commands cannot include recipe parameters or code.'
}
$statusRaw=& (Join-Path $PSScriptRoot 'Get-YacsLiveHostStatus.ps1') -InstallRoot $InstallRoot -RequireLive
$status=$statusRaw | ConvertFrom-Json
if ($status.status -cne 'LIVE_VIDEO_VERIFIED' -or $status.post_job_alive -ne $true -or
    $status.source_sha -cnotmatch '^[a-f0-9]{40}$' -or
    $status.session -cnotmatch '^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}$') {
  throw 'Authenticated independent Live Host is not ready.'
}
$runtime=Join-Path $InstallRoot 'runtime'
$session=[string]$status.session
$inbox=Join-Path $runtime "inbox/$session"
$sessionRoot=Join-Path $runtime "sessions/$session"
$bridge=Join-Path $sessionRoot 'live-heartbeat.json'
if (-not (Test-Path -LiteralPath $bridge -PathType Leaf) -or
    -not (Test-Path -LiteralPath $inbox -PathType Container)) { throw 'Native command queue not alive.' }
$heartbeat=Get-Content -LiteralPath $bridge -Raw | ConvertFrom-Json
$isInteger=($heartbeat.sequence -is [long] -or $heartbeat.sequence -is [int])
if ($heartbeat.session -cne $session -or $heartbeat.source_sha -cne $status.source_sha -or
    $heartbeat.status -cne 'EDITOR_TICK_ALIVE' -or -not $isInteger -or
    $heartbeat.sequence -lt 0 -or $heartbeat.sequence -ge 999999) {
  throw 'Editor-side command authority/sequence differs.'
}
$lockPath=Join-Path $sessionRoot 'single-writer.lock'
$lock=$null
try {
  $lock=[IO.File]::Open($lockPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
  $pending=@(Get-ChildItem -LiteralPath $inbox -File -Filter '*.json' -ErrorAction Stop)
  if ($pending.Count -ne 0) { throw 'A command remains unacknowledged; do not send another sequence.' }
  $token=[Guid]::NewGuid().ToString('N').Substring(0,20)
  $next=[long]$heartbeat.sequence+1
  $row=[ordered]@{
    schema_version=1;session=$session;source_sha=$status.source_sha
    request_id=$token;sequence=$next;action=$Action
  }
  if ($Action -ceq 'focus_site') { $row.site=$Site }
  if ($Action -ceq 'set_markers_visible') { $row.visible=[bool]$Visible }
  if ($Action -ceq 'run_recipe') {
    $manifestPath=Join-Path $runtime "recipes/$RecipeRevision/$Recipe.json"
    $sourcePath=Join-Path $runtime "recipes/$RecipeRevision/$Recipe.py"
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
      throw 'Vetted live editor recipe was not published on host.'
    }
    $doc=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $hash=(Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($doc.recipe -cne $Recipe -or $doc.revision -cne $RecipeRevision -or
        $doc.sha256 -cne $hash -or $doc.ci_admitted -ne $true -or
        $Intent -cnotin @($doc.intents)) { throw 'Staged recipe provenance or permission differs.' }
    $args=$ParametersJson | ConvertFrom-Json -AsHashtable -Depth 8
    if ($args -isnot [System.Collections.IDictionary] -or @($args.Keys).Count -gt 32) {
      throw 'Recipe parameter envelope must be a bounded object.'
    }
    $row.recipe=$Recipe
    $row.recipe_revision=$RecipeRevision
    $row.recipe_sha256=$hash
    $row.intent=$Intent
    $row.parameters=$args
  }
  $name=('{0:D6}-{1}.json' -f $next,$token)
  $scratch=Join-Path $sessionRoot ("input-$token.tmp")
  $target=Join-Path $inbox $name
  if (Test-Path -LiteralPath $target) { throw 'Replay/collision; no command written.' }
  $bytes=[Text.Encoding]::UTF8.GetBytes(($row | ConvertTo-Json -Depth 4 -Compress) + [Environment]::NewLine)
  if ($bytes.Length -gt 4096) { throw 'Bounded command exceeds maximum bytes.' }
  [IO.File]::WriteAllBytes($scratch,$bytes)
  Move-Item -LiteralPath $scratch -Destination $target -ErrorAction Stop
  Write-Host "YACS_LIVE_COMMAND_SUBMITTED: $Action session=$session sequence=$next"
} finally {
  if ($lock) { $lock.Dispose();Remove-Item -LiteralPath $lockPath -ErrorAction SilentlyContinue }
}
