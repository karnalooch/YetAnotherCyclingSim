#requires -Version 7.4
<#
.SYNOPSIS
  Stage exactly one reviewed GitHub-commit editor recipe for a LIVE UE session.
.DESCRIPTION
  A remote Actions job may publish data and versioned vetted code but never
  starts/stops UE, invokes PowerShell from a request, or bypasses source proof.
  This is a trusted-code loading mechanism, NOT a sandbox for malicious Python.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidatePattern('^[a-f0-9]{40}$')][string]$ExpectedHead,
  [Parameter(Mandatory)][ValidatePattern('^[a-z][a-z0-9_]{2,47}$')][string]$Recipe,
  [string]$RepoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path,
  [string]$InstallRoot='D:\yacs\live-host',
  [switch]$Apply
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$RepoRoot=(Resolve-Path -LiteralPath $RepoRoot).Path
$InstallRoot=[IO.Path]::GetFullPath($InstallRoot)
if ($InstallRoot -ine 'D:\yacs\live-host') { throw 'Unknown Live Host root.' }
if ((& git -C $RepoRoot rev-parse HEAD).Trim() -cne $ExpectedHead) {
  throw 'Editor recipe publisher HEAD drift.'
}
if (@(& git -C $RepoRoot status --porcelain --untracked-files=no).Count) {
  throw 'Uncommitted recipe publisher inputs.'
}
$catalogPath=Join-Path $RepoRoot 'scripts/live_host/recipes/catalog.json'
$catalog=Get-Content -LiteralPath $catalogPath -Raw | ConvertFrom-Json
if($catalog.schema_version -ne 1 -or $catalog.review_issue -ne 476 -or
   $catalog.policy -cne 'SOURCE_REVIEWED_RECIPES_ONLY') {
  throw 'Unknown reviewed recipe catalog.'
}
$known=@($catalog.recipes | Where-Object id -CEQ $Recipe)
if($known.Count -ne 1) { throw 'Recipe not declared exactly once in reviewed catalog.' }
$row=$known[0]
if($row.capability -cnotin @('world_inspection','actor_presentation','material_presentation','lighting_presentation','asset_authoring','pcg_authoring','animation_authoring','editor_tooling') -or
   @($row.intents).Count -eq 0 -or @($row.intents | Where-Object { $_ -cnotin @('preview','author') }).Count) {
  throw 'Unknown recipe capability/authoring intent.'
}
$rel="scripts/live_host/recipes/$Recipe.py"
$source=Join-Path $RepoRoot $rel
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw 'Reviewed recipe source missing.' }
$item=Get-Item -LiteralPath $source -Force
if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint -or $item.Length -gt 512KB) {
  throw 'Aliased/oversized recipe source.'
}
$sourceBlob=(& git -C $RepoRoot rev-parse "$($ExpectedHead):$rel").Trim()
if ($LASTEXITCODE -ne 0 -or $sourceBlob -cnotmatch '^[a-f0-9]{40}$') { throw 'Uncommitted or missing exact recipe Git blob.' }
$physicalBlob=(& git -C $RepoRoot hash-object -- $rel).Trim()
if ($LASTEXITCODE -ne 0 -or $physicalBlob -cne $sourceBlob) { throw 'Executing recipe bytes differ from committed Git source.' }
$manifestBlob=(& git -C $RepoRoot rev-parse "$($ExpectedHead):scripts/live_host/recipes/catalog.json").Trim()
if ($LASTEXITCODE -ne 0 -or $manifestBlob -cnotmatch '^[a-f0-9]{40}$') { throw 'Unpinned reviewed catalog.' }
$catalogPhysical=(& git -C $RepoRoot hash-object -- 'scripts/live_host/recipes/catalog.json').Trim()
if ($catalogPhysical -cne $manifestBlob) { throw 'Reviewed catalog differs from Git.' }
$hash=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
$runtime=Join-Path $InstallRoot "runtime/recipes/$ExpectedHead"
$destination=Join-Path $runtime "$Recipe.py"
$contract=Join-Path $runtime "$Recipe.json"
$doc=[ordered]@{
  schema_version=1
  repository='karnalooch/YetAnotherCyclingSim'
  revision=$ExpectedHead
  recipe=$Recipe
  source_path=$rel
  sha256=$hash
  intents=@($row.intents)
  capability=$row.capability
  parameters=$row.parameters
  asset_scope=@($row.asset_scope)
  review_issue=476
  ci_admitted=$true
}
$summary=[pscustomobject]@{
  status='SOURCE_VALIDATED_NOT_LIVE_PROOF'
  source_sha=$ExpectedHead;source_git_blob=$sourceBlob;source_sha256=$hash
  recipe=$Recipe;intents=@($row.intents);target=$destination
  editor_restarted=$false
}
if (-not $Apply) { $summary | ConvertTo-Json -Depth 8;return }
if ($env:GITHUB_ACTIONS -cne 'true' -or $env:GITHUB_ACTOR -cne 'karnalooch' -or
    $env:YACS_LIVE_ADMITTED_SHA -cne $ExpectedHead) {
  throw 'Actual owner/exact-head successful CI admission is required to publish executable UE code.'
}
$install=Get-Content -LiteralPath (Join-Path $InstallRoot 'state/installation.json') -Raw | ConvertFrom-Json
if($install.source_sha -cnotmatch '^[a-f0-9]{40}$') { throw 'Live Host installation has no exact code identity.' }
if ((Test-Path -LiteralPath $destination) -or (Test-Path -LiteralPath $contract)) {
  throw 'Versioned receipt/source already exists. No overwrite or second code load.'
}
[void][IO.Directory]::CreateDirectory($runtime)
Copy-Item -LiteralPath $source -Destination $destination -ErrorAction Stop
if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -cne $hash) {
  throw 'Published source changed during local copy.'
}
$doc | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $contract -Encoding utf8
if ((Get-Content -LiteralPath $contract -Raw | ConvertFrom-Json).sha256 -cne $hash) {
  throw 'Published recipe manifest readback drift.'
}
$summary.status='RECIPE_STAGED_IN_LIVE_HOST'
$summary | ConvertTo-Json -Depth 8
