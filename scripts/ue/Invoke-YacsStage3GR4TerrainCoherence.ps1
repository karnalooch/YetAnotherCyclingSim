<#
.SYNOPSIS
    Rebuild and persist the Stage 3G R4 route-aware terrain on an exact trusted SHA.

.DESCRIPTION
    Proves the exact revision with CyclingStage3World Automation, runs the existing
    deterministic Stage 3 route/world setup commandlet, and fails closed unless the
    only tracked mutation is the canonical L_CyclingTest.umap.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [int] $TimeoutSec = 1800
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) {
    $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject'
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/CI/Stage3GR4/TerrainCoherenceAuthor'
}
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) {
    $ArtifactRoot = Join-Path $RepoRoot $ArtifactRoot
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$MapRelativePath = 'Content/Prototype/Maps/L_CyclingTest.umap'
$MapPath = Join-Path $RepoRoot $MapRelativePath
$SetupLog = Join-Path $ArtifactRoot 'stage3g_r4_route_setup.log'
$SetupErr = $SetupLog + '.stderr'
$ProofPath = Join-Path $ArtifactRoot 'stage3g_r4_terrain_coherence_author.json'

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) {
    throw 'Stage 3G R4 preflight failed.'
}

& git -C $RepoRoot lfs fsck
if ($LASTEXITCODE -ne 0) {
    throw 'git lfs fsck failed before Stage 3G R4 authoring.'
}
if (git -C $RepoRoot status --porcelain) {
    throw 'Stage 3G R4 checkout is dirty before authoring.'
}

$CiEntry = Join-Path $RepoRoot 'scripts/ci/Invoke-YacsUnrealCi.ps1'
$CanaryRoot = Join-Path $ArtifactRoot 'Canary'
& $CiEntry -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $CanaryRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead -TestFilter 'CyclingStage3World'
if ($LASTEXITCODE -ne 0) {
    throw 'Stage 3G R4 CyclingStage3World build/Automation canary failed.'
}

if (-not (Test-Path -LiteralPath $MapPath -PathType Leaf)) {
    throw "Canonical Stage 3 map is missing: $MapRelativePath"
}

$EditorCmd = $Context.UnrealEditorCmdPath
$Args = @(
    $ProjectPath
    '-run=CyclingStage3RouteSetup'
    '-Unattended'
    '-NoPause'
    '-NullRHI'
    '-NoSplash'
    '-NoP4'
    '-log'
    ('-AbsLog=' + $SetupLog)
)
$Proc = Start-Process -FilePath $EditorCmd -ArgumentList $Args -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $SetupLog -RedirectStandardError $SetupErr
if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
    try { $Proc | Stop-Process -Force } catch { }
    throw 'Stage 3G R4 route/world setup timed out.'
}
if ($Proc.ExitCode -ne 0) {
    throw "Stage 3G R4 route/world setup failed with exit code $($Proc.ExitCode)."
}

$SetupText = Get-Content -LiteralPath $SetupLog -Raw -ErrorAction Stop
if ($SetupText -notmatch 'CyclingStage3RouteSetupCommandlet: done') {
    throw 'CyclingStage3RouteSetup completion marker is missing.'
}

$TrackedChanges = @(
    git -C $RepoRoot diff --name-only --diff-filter=ACMRTUXB |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ }
)
$Unexpected = @($TrackedChanges | Where-Object { $_ -ne $MapRelativePath })
if ($Unexpected.Count -gt 0) {
    throw ("Unexpected tracked mutations: {0}" -f ($Unexpected -join ', '))
}
if ($TrackedChanges -notcontains $MapRelativePath) {
    throw 'Stage 3G R4 authoring produced no persisted map change.'
}

$Proof = [ordered]@{
    schema_version = 1
    stage3g_r4_terrain_coherence_author = 'PASS'
    expected_head = $ExpectedHead
    map = $MapRelativePath
    tracked_mutations = @($TrackedChanges)
    automation_filter = 'CyclingStage3World'
    note = 'Route-aware terrain shoulders and shared PCG/presentation grounding persisted; simulation truth unchanged.'
}
$Proof | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ProofPath -Encoding UTF8

Write-Host 'Stage 3G R4 terrain coherence authoring: PASS.' -ForegroundColor Green
Write-Host ("Only tracked mutation: {0}" -f $MapRelativePath)
exit 0
