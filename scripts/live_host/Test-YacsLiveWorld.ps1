#requires -Version 7.4
<#
.SYNOPSIS
  Owner/runner read-only verification of actual local latest-road packages.
.DESCRIPTION
  This is an evidence gate only. It cannot start/stop Unreal, change a
  Scheduled Task, write files, save a map or move a road actor.
#>
[CmdletBinding()]
param(
  [string]$SourceRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$world=& (Join-Path $PSScriptRoot 'Resolve-YacsLiveWorld.ps1') -SourceRoot $SourceRoot
if ($world.status -cne 'LATEST_VERIFIED_WORLD_PREFLIGHT_PASS' -or
    $world.version -cne '0.3.1' -or
    $world.profile_id -cne 'sa_calobra_road_v0_3_1' -or
    $world.validated_packages -ne 5 -or
    $world.native_expected_actors -ne 559 -or
    $world.native_expected_bindings -ne 186 -or
    $world.fallback_used -ne $false -or
    $world.editor_started -ne $false -or
    $world.map_saved -ne $false -or
    $world.terrain_modified -ne $false) {
  throw 'YACS_LATEST_WORLD_PREFLIGHT_FAILED: source-backed identity changed'
}
Write-Host ('YACS_LATEST_WORLD_PREFLIGHT_PASS version={0} packages={1} actors={2} bindings={3} source_unchanged=true' -f
  $world.version,$world.validated_packages,$world.native_expected_actors,
  $world.native_expected_bindings)
