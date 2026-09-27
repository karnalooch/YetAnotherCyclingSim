<# Stage 3G target-density forest authoring for PCG and canonical map. #>
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
if (-not $ProjectPath) { $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject' }
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) { $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/Issue201/TargetDensityAuthor' }
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) { $ArtifactRoot = Join-Path $RepoRoot $ArtifactRoot }
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) { throw 'Target-density forest preflight failed.' }

& git -C $RepoRoot lfs fsck
if ($LASTEXITCODE -ne 0) { throw 'git lfs fsck failed before target-density authoring.' }
if (git -C $RepoRoot status --porcelain) { throw 'Target-density authoring checkout is dirty.' }

$ForestHarness = Join-Path $RepoRoot 'scripts/ue/Invoke-YacsStage3GR2PCGForest.ps1'
$ForestProofRoot = Join-Path $ArtifactRoot 'PCGForest'
& $ForestHarness -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ForestProofRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) { throw 'Target-density PCG_Forest authoring failed.' }

$SetupLog = Join-Path $ArtifactRoot 'stage3g_target_density_route_setup.log'
$SetupErr = $SetupLog + '.stderr'
$EditorArgs = @(
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
$Proc = Start-Process -FilePath $Context.UnrealEditorCmdPath -ArgumentList $EditorArgs -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $SetupLog -RedirectStandardError $SetupErr
if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
    try { $Proc | Stop-Process -Force } catch { }
    throw 'Target-density canonical-map rebuild timed out.'
}
if ($Proc.ExitCode -ne 0) {
    throw "Target-density canonical-map rebuild failed with exit code $($Proc.ExitCode)."
}

$SetupText = Get-Content -LiteralPath $SetupLog -Raw -ErrorAction Stop
if ($SetupText -notmatch 'CyclingStage3RouteSetupCommandlet: done') {
    throw 'Target-density route setup completion marker missing.'
}
if ($SetupText -notmatch 'forest_props=(\d+)') {
    throw 'Target-density route setup forest_props marker missing.'
}
$ForestProps = [int]$Matches[1]
if ($SetupText -notmatch 'forest_canopy=(\d+)') {
    throw 'Target-density route setup forest_canopy marker missing.'
}
$ForestCanopy = [int]$Matches[1]
$ForestTotal = $ForestProps + $ForestCanopy
if ($ForestTotal -lt 1700 -or $ForestTotal -gt 2300) {
    throw "Persisted target-density forest count $ForestTotal is outside [1700, 2300]."
}

$Allowed = @(
    'Content/YACS/WorldGen/PCG/PCG_Forest.uasset',
    'Content/Prototype/Maps/L_CyclingTest.umap'
)
$Tracked = @(
    git -C $RepoRoot diff --name-only --diff-filter=ACMRTUXB |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ }
)
$Unexpected = @($Tracked | Where-Object { $_ -notin $Allowed })
if ($Unexpected.Count -gt 0) {
    throw ("Unexpected tracked mutations: {0}" -f ($Unexpected -join ', '))
}
foreach ($Path in $Allowed) {
    if ($Tracked -notcontains $Path) {
        throw "Target-density authoring did not persist required path: $Path"
    }
}

$Proof = [ordered]@{
    schema_version = 1
    stage3g_forest_target_density_author = 'PASS'
    expected_head = $ExpectedHead
    forest_props = $ForestProps
    forest_canopy = $ForestCanopy
    forest_total = $ForestTotal
    mutated_paths = @($Tracked)
    note = 'PCG_Forest and canonical L_CyclingTest consume the shared target-density forest-layout contract.'
}
$ProofPath = Join-Path $ArtifactRoot 'stage3g_forest_target_density_author.json'
$Proof | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ProofPath -Encoding UTF8

Write-Host ("TARGET-DENSITY FOREST AUTHOR PASS: forest_props={0} forest_canopy={1} total={2}" -f $ForestProps, $ForestCanopy, $ForestTotal) -ForegroundColor Green
exit 0
