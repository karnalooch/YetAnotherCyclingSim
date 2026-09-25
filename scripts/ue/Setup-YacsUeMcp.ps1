<#
.SYNOPSIS
    Prepare the pinned UE-MCP development tooling for YACS.

.DESCRIPTION
    Installs the exact ue-mcp version declared in tools/ue-mcp/package.json.
    Optionally runs ue-mcp init from the repository root, which deploys the
    local development bridge plugin. The bridge is intentionally gitignored
    during the Stage 3G spike.

    This script does NOT run Unreal validation. After init, build the UE 5.8.2
    editor target and run the existing Stage 3 proof before opening a PR.
#>
[CmdletBinding()]
param(
    [switch] $RunInit
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$ToolRoot = Join-Path $RepoRoot 'tools/ue-mcp'
$PackageJson = Join-Path $ToolRoot 'package.json'

if (-not (Test-Path -LiteralPath $PackageJson)) {
    throw "Missing UE-MCP package manifest: $PackageJson"
}

$Node = Get-Command node -ErrorAction Stop
$Npm = Get-Command npm -ErrorAction Stop
$NodeVersionText = (& $Node.Source --version).Trim()
if ($NodeVersionText -notmatch '^v(?<major>\d+)\.') {
    throw "Unable to parse Node.js version '$NodeVersionText'."
}
if ([int]$Matches.major -lt 20) {
    throw "UE-MCP 1.3.9 requires Node.js >=20; found $NodeVersionText."
}

Write-Host "RepoRoot : $RepoRoot"
Write-Host "Node     : $NodeVersionText"
Write-Host "ToolRoot : $ToolRoot"
Write-Host ""
Write-Host "[1/2] Installing pinned UE-MCP tooling..." -ForegroundColor Cyan
& $Npm.Source install --prefix $ToolRoot
if ($LASTEXITCODE -ne 0) {
    throw "npm install failed with exit code $LASTEXITCODE."
}

if ($RunInit) {
    Write-Host ""
    Write-Host "[2/2] Running ue-mcp init from repository root..." -ForegroundColor Cyan
    Push-Location $RepoRoot
    try {
        & $Npm.Source run init --prefix $ToolRoot
        if ($LASTEXITCODE -ne 0) {
            throw "ue-mcp init failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host ""
    Write-Host "[2/2] Install complete. Init was not requested." -ForegroundColor Yellow
    Write-Host "Run on the home PC when ready:"
    Write-Host "  pwsh ./scripts/ue/Setup-YacsUeMcp.ps1 -RunInit"
}

Write-Host ""
Write-Host "Next validation steps:" -ForegroundColor Cyan
Write-Host "  npm run doctor --prefix tools/ue-mcp"
Write-Host "  npm run start --prefix tools/ue-mcp"
Write-Host "Then run yacs_stage3g_inspect and yacs_stage3g_transient_smoke from the connected MCP client."
Write-Host "Finally rerun the normal YACS Stage 3 build/Automation/proof gates."
