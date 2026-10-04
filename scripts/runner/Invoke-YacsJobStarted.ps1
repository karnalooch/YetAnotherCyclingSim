#requires -Version 7.4
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Assert-YacsDiskReserve.ps1')
if (-not $env:YACS_WORKSPACE_CONFIG) { throw 'YACS_WORKSPACE_CONFIG is required by the runner disk guard.' }
$workspace = Split-Path -Parent (Resolve-Path -LiteralPath $env:YACS_WORKSPACE_CONFIG).Path
Assert-YacsDiskReserve -Path $workspace
