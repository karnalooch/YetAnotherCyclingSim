#requires -Version 7.4
<#
.SYNOPSIS
  Resolve the latest source-approved, saved-and-reopened YACS world on disk.
.DESCRIPTION
  Read-only. No fallback to the old P0-P4 diagnostic scene, no Unreal launch,
  no save, no task/runner mutation. The repo-owned registry is installed in
  the immutable source release and names the intended highest verified version.
#>
[CmdletBinding()]
param(
  [string]$SourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path,
  [switch]$AsJson
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Check([bool]$Passed,[string]$Reason) {
  if (-not $Passed) { throw "LATEST_VERIFIED_WORLD_BLOCKED: $Reason" }
}
function Assert-RegularOwnedFile([string]$ProjectRoot,[string]$Relative) {
  Check ($Relative -cmatch '^[A-Za-z0-9_./-]{1,220}$' -and
    $Relative -cnotmatch '(^|/)\.\.?(/|$)' -and $Relative -cnotmatch '//') 'Unsafe relative world file path'
  $root=[IO.Path]::GetFullPath($ProjectRoot)
  $path=[IO.Path]::GetFullPath((Join-Path $root $Relative))
  Check ($path.StartsWith($root+[IO.Path]::DirectorySeparatorChar,
      [StringComparison]::OrdinalIgnoreCase)) 'World package escaped its verified project'
  $cursor=$path
  while ($cursor.Length -ge $root.Length) {
    Check (Test-Path -LiteralPath $cursor) "Missing required verified world input: $Relative"
    $item=Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
    Check (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) "World path is redirected: $Relative"
    if ($cursor -ieq $root) { break }
    $cursor=Split-Path -Path $cursor -Parent
  }
  Check (Test-Path -LiteralPath $path -PathType Leaf) "Not a regular verified world input: $Relative"
  return $path
}
function Check-WorldFileProof([string]$Root,[string]$Relative,[long]$Bytes,[string]$Digest) {
  Check ($Bytes -gt 0 -and $Bytes -le 256MB -and
    $Digest -cmatch '^[a-f0-9]{64}$') "Invalid pinned hash or size: $Relative"
  $path=Assert-RegularOwnedFile -ProjectRoot $Root -Relative $Relative
  Check ((Get-Item -LiteralPath $path).Length -eq $Bytes) "World package byte-count drift: $Relative"
  Check ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $Digest) "World package SHA256 drift: $Relative"
  return $path
}
function Resolve-YacsLatestVerifiedWorld {
  [CmdletBinding()]
  param([Parameter(Mandatory)][string]$CodeRoot)

  $CodeRoot=(Resolve-Path -LiteralPath $CodeRoot).Path
  $registryFile=Join-Path $CodeRoot 'scripts/live_host/verified_worlds.json'
  Check (Test-Path -LiteralPath $registryFile -PathType Leaf) 'Installed source has no world registry'
  Check ((Get-Item -LiteralPath $registryFile).Length -le 8192) 'World registry exceeds size bound'
  $registry=Get-Content -LiteralPath $registryFile -Raw | ConvertFrom-Json
  Check ($registry.schema_version -eq 1 -and
    $registry.policy -ceq 'LATEST_VERIFIED_FAIL_CLOSED') 'Unsupported world registry policy'
  $worlds=@($registry.worlds)
  Check ($worlds.Count -ge 1 -and $worlds.Count -le 16) 'Invalid selected-world catalog size'
  $ids=@($worlds | ForEach-Object { [string]$_.id })
  Check (@($ids | Sort-Object -Unique).Count -eq $worlds.Count) 'Duplicate world profile identifiers'
  $choices=@($worlds | Where-Object { $_.id -ceq $registry.selected_world_id })
  Check ($choices.Count -eq 1) 'Latest world was not explicitly selected'
  $chosen=$choices[0]
  $allVersions=[Collections.Generic.List[version]]::new()
  foreach($entry in $worlds) {
    Check ($entry.id -cmatch '^[a-z][a-z0-9_]{2,47}$') 'Invalid world identity'
    Check ($entry.version -cmatch '^\d+\.\d+\.\d+$') 'Invalid semantic world version'
    $allVersions.Add([version]$entry.version)
  }
  $mostRecent=@($allVersions | Sort-Object -Descending)[0]
  Check ([version]$chosen.version -eq $mostRecent) 'Selected world is not the newest admitted version'
  Check ($chosen.evidence_status -ceq 'SAVED_CHECKPOINT_REOPENED_RENDERED' -and
    $chosen.owner_visual_status -ceq 'PENDING_FINAL_M3' -and
    $chosen.performance_pass -eq $false) 'World admission claim differs from retained evidence'
  # The only currently admitted live-authoring target is the accepted v0.3.1
  # road/material checkpoint, never the old PCG365 P0-P4 diagnostic snapshot.
  Check ($chosen.id -ceq 'sa_calobra_road_v0_3_1' -and
    $chosen.version -ceq '0.3.1' -and
    $chosen.project_root -ieq 'D:\yacs\work\level-editor-review\b9fddea3f602-y473save01' -and
    $chosen.project_file -ceq 'YetAnotherCyclingSim.uproject' -and
    $chosen.map_package -ceq '/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/L_RoadSurface' -and
    $chosen.evidence_reader_sha -ceq 'fde7a363d484c3693b65efe13eba76fb71bab6e1' -and
    $chosen.evidence_token -ceq 'v031-reopen02') 'Unreviewed v0.3.1 world identity'
  $root=[IO.Path]::GetFullPath([string]$chosen.project_root)
  Check (Test-Path -LiteralPath $root -PathType Container) 'Latest verified project directory missing'
  $uproject=Check-WorldFileProof $root $chosen.project_file $chosen.project_file_bytes $chosen.project_file_sha256
  $sourceMap=Check-WorldFileProof $root $chosen.source_map_relative $chosen.source_map_bytes $chosen.source_map_sha256
  $files=@($chosen.files)
  Check ($files.Count -eq 5 -and @($files | ForEach-Object path | Sort-Object -Unique).Count -eq 5) 'Expected exactly five unique pinned v0.3.1 packages'
  $names=@('L_RoadSurface.umap','M_Road.uasset','M_Shoulder.uasset','MI_Road.uasset','MI_Shoulder.uasset')
  $prefix='Content/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/'
  $actualNames=@($files | ForEach-Object { $_.path.Substring($prefix.Length) } | Sort-Object) -join ','
  $expectedNames=@($names | Sort-Object) -join ','
  Check ($actualNames -ceq $expectedNames) 'Unexpected v0.3.1 package inventory'
  Check ($chosen.map_relative -ceq ($prefix+'L_RoadSurface.umap') -and
    $chosen.receipt_relative -ceq ($prefix+'checkpoint-receipt.json')) 'World map or saved receipt path drift'
  foreach ($item in $files) {
    Check ([string]$item.path -clike "$prefix*") 'Package outside pinned v0.3.1 namespace'
    Check-WorldFileProof $root $item.path $item.bytes $item.sha256 | Out-Null
  }
  $receiptFile=Assert-RegularOwnedFile $root $chosen.receipt_relative
  Check ((Get-Item -LiteralPath $receiptFile).Length -le 2MB) 'Saved map receipt exceeds size cap'
  $receipt=Get-Content -LiteralPath $receiptFile -Raw | ConvertFrom-Json
  Check ($receipt.status -ceq 'DERIVED_CHECKPOINT_SAVED' -and
    $receipt.revision -ceq $chosen.handler_revision -and
    $receipt.map_package -ceq $chosen.map_package -and
    $receipt.preset -ceq 'worn' -and
    $receipt.active_source_unchanged -eq $true) 'Saved material checkpoint receipt differs'
  Check ($receipt.native_mesh_comparison.actor_count -eq 559 -and
    $receipt.native_mesh_comparison.road_equal -eq $true -and
    $receipt.native_mesh_comparison.all_attributes -eq $true -and
    $receipt.native_mesh_comparison.epsilon -eq 0 -and
    @($receipt.bindings).Count -eq 186) 'Road/native material checkpoint contract differs'
  Check ($receipt.repair.road_unchanged -eq $true -and
    $receipt.repair.landscape_mutated -eq $false) 'Frozen Landscape/road receipt differs'
  $observed=@($receipt.files)
  Check ($observed.Count -eq $files.Count) 'Checkpoint receipt has unexpected packages'
  foreach($f in $files) {
    $r=@($observed | Where-Object { $_.path -ceq $f.path })
    Check ($r.Count -eq 1 -and $r[0].bytes -eq $f.bytes -and
      $r[0].sha256 -ceq $f.sha256) "Pinned checkpoint receipt entry differs: $($f.path)"
  }
  $camera=@($chosen.camera_cm)
  $target=@($chosen.target_cm)
  Check ($camera.Count -eq 3 -and $target.Count -eq 3 -and
    @($camera + $target | Where-Object { $_ -isnot [int] -and $_ -isnot [long] -and $_ -isnot [double] -and $_ -isnot [decimal] }).Count -eq 0) 'Invalid native checkpoint camera'
  return [pscustomobject]@{
    status='LATEST_VERIFIED_WORLD_PREFLIGHT_PASS'
    profile_id=$chosen.id;version=$chosen.version;source_issue=$chosen.source_issue
    evidence_status=$chosen.evidence_status;project_root=$root;project_file=$uproject
    map_package=$chosen.map_package;map_file=(Join-Path $root $chosen.map_relative)
    map_sha256=(@($files | Where-Object { $_.path -ceq $chosen.map_relative })[0].sha256)
    source_map_file=$sourceMap;validated_packages=5;native_expected_actors=559
    native_expected_bindings=186;checkpoint_receipt_file=$receiptFile
    camera_cm=$camera;target_cm=$target
    terrain_modified=$false;map_saved=$false;editor_started=$false
    fallback_used=$false;owner_visual_status='PENDING_FINAL_M3'
  }
}

$world=Resolve-YacsLatestVerifiedWorld -CodeRoot $SourceRoot
if ($AsJson) { $world | ConvertTo-Json -Depth 8 } else { $world }
