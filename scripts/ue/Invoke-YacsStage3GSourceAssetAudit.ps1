<#
.SYNOPSIS
    Non-mutating Stage 3G source-asset lifecycle audit.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) {
    $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject'
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/Issue80/Stage3G/SourceAssetAudit'
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$ProofPath = Join-Path $ArtifactRoot 'stage3g_source_asset_audit.json'
$LogPath = Join-Path $ArtifactRoot 'stage3g_source_asset_audit.log'
$ErrPath = $LogPath + '.stderr'
$ScriptPath = Join-Path $RepoRoot 'scripts/ue/stage3g_source_asset_audit.py'

foreach ($Path in @($ProofPath, $LogPath, $ErrPath)) {
    Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    throw "Stage 3G source-asset audit script is missing: $ScriptPath"
}

Write-Host '=== YACS Stage 3G source-asset lifecycle audit ===' -ForegroundColor Cyan
Write-Host ("Branch / HEAD: {0} / {1}" -f $ExpectedBranch, $ExpectedHead)
Write-Host 'Mode         : audit-only / no asset mutation'

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$PreflightArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $ArtifactRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
}
$Context = & $Preflight @PreflightArgs
if ($LASTEXITCODE -ne 0) {
    throw 'Stage 3G source-asset audit preflight failed.'
}

$EditorCmd = $Context.UnrealEditorCmdPath
if (-not $EditorCmd -or -not (Test-Path -LiteralPath $EditorCmd -PathType Leaf)) {
    throw 'UnrealEditor-Cmd.exe is unavailable.'
}

Write-Host '[1/3] Verifying full-LFS repository state...' -ForegroundColor Cyan
& git -C $RepoRoot lfs fsck
if ($LASTEXITCODE -ne 0) { throw 'git lfs fsck failed.' }

$RequiredFiles = @(
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_Meadow_BaseColor.uasset',
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_ForestGround_BaseColor.uasset',
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_HighAlpine_BaseColor.uasset',
    'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_Boulder_BaseColor.uasset',
    'Content/Prototype/Environment/Stage3G/Imported/Meshes/SM_Stage3G_Boulder.uasset',
    'Content/YACS/WorldGen/PCG/PCG_Valley.uasset',
    'Content/YACS/WorldGen/PCG/PCG_HighAlpine.uasset'
)
$Missing = @(
    $RequiredFiles | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $RepoRoot $_) -PathType Leaf)
    }
)
if ($Missing.Count -gt 0) {
    throw ("Required persisted Stage 3G assets are missing: {0}" -f ($Missing -join ', '))
}

Write-Host '[2/3] Running non-mutating Unreal asset audit...' -ForegroundColor Cyan
$env:YACS_STAGE3G_SOURCE_ASSET_AUDIT_PROOF = $ProofPath
try {
    $EditorArgs = @(
        $ProjectPath,
        '-run=PythonScript',
        ('-script="' + $ScriptPath + '"'),
        '-Unattended',
        '-NoPause',
        '-NullRHI',
        '-NoSplash',
        '-NoP4',
        '-log',
        ('-AbsLog=' + $LogPath)
    )
    $StartArgs = @{
        FilePath = $EditorCmd
        ArgumentList = $EditorArgs
        WorkingDirectory = $RepoRoot
        NoNewWindow = $true
        PassThru = $true
        RedirectStandardOutput = $LogPath
        RedirectStandardError = $ErrPath
    }
    $Proc = Start-Process @StartArgs

    $TimeoutSec = 180
    if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
        try { $Proc | Stop-Process -Force } catch { }
        throw "Stage 3G source-asset audit timed out after $TimeoutSec s."
    }
    if ($Proc.ExitCode -ne 0 -and -not (Test-Path -LiteralPath $ProofPath)) {
        throw "Unreal source-asset audit failed with exit code $($Proc.ExitCode) before producing proof."
    }
}
finally {
    Remove-Item Env:YACS_STAGE3G_SOURCE_ASSET_AUDIT_PROOF -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $ProofPath -PathType Leaf)) {
    throw 'Stage 3G source-asset audit proof JSON was not produced.'
}

$Proof = Get-Content -LiteralPath $ProofPath -Raw -ErrorAction Stop | ConvertFrom-Json
if ($Proof.schema_version -ne 1) {
    throw "Unexpected source-asset audit schema: $($Proof.schema_version)"
}
if (-not $Proof.families) {
    throw 'Source-asset audit proof contains no family results.'
}

Write-Host '[3/3] Audit result' -ForegroundColor Cyan
foreach ($Name in @('sparse_grass','forrest_ground_03','rocky_terrain','boulder_01')) {
    $Family = $Proof.families.$Name
    if ($null -eq $Family) { throw "Audit proof is missing family $Name" }
    $State = if ($Family.pass) { 'PASS' } else { 'FAIL' }
    Write-Host ("  {0,-20} {1}" -f $Name, $State)
    foreach ($Failure in @($Family.failures)) {
        Write-Host ("    - {0}" -f $Failure) -ForegroundColor Yellow
    }
}

if ($Proof.stage3g_source_asset_audit -ne 'PASS') {
    Write-Host 'STAGE 3G SOURCE-ASSET AUDIT FAILED.' -ForegroundColor Red
    Write-Host ("Failed families: {0}" -f (@($Proof.failed_families) -join ', ')) -ForegroundColor Red
    Write-Host ("Proof: {0}" -f $ProofPath)
    exit 1
}

Write-Host 'STAGE 3G SOURCE-ASSET AUDIT PASSED.' -ForegroundColor Green
Write-Host ("Proof: {0}" -f $ProofPath)
exit 0
