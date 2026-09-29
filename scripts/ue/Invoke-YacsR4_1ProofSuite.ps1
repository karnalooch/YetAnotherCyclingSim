<#
.SYNOPSIS
    Build once and run the bounded Stage 3G R4.1 proof sequence from one exact-SHA worktree.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [int] $TimeoutSec = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) { $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject' }
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) { $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/CI/Stage3GR4_1/PreparedSuite' }
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) { $ArtifactRoot = Join-Path $RepoRoot $ArtifactRoot }
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$SpikeMapRelative = 'Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap'
$SpikeMapPath = Join-Path $RepoRoot $SpikeMapRelative
$BuildLog = Join-Path $ArtifactRoot 'build_editor.log'
$StampPath = Join-Path $ArtifactRoot 'prepared_workspace.json'
$SummaryPath = Join-Path $ArtifactRoot 'proof_suite_summary.json'
foreach ($Path in @($BuildLog,$StampPath,$SummaryPath)) {
    Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
}

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) { throw 'R4.1 prepared proof-suite preflight failed.' }

if (git -C $RepoRoot status --porcelain --untracked-files=all) {
    throw 'R4.1 prepared proof-suite checkout is dirty before workspace preparation.'
}

Write-Host '[1/6] Materializing persisted Passo Giau map once...' -ForegroundColor Cyan
git -C $RepoRoot lfs install --local
if ($LASTEXITCODE -ne 0) { throw 'git lfs install failed.' }
git -C $RepoRoot lfs pull --include=$SpikeMapRelative --exclude=''
if ($LASTEXITCODE -ne 0) { throw 'git lfs pull for Passo Giau spike map failed.' }
if (-not (Test-Path -LiteralPath $SpikeMapPath -PathType Leaf)) {
    throw "Passo Giau map is missing after suite materialization: $SpikeMapPath"
}
$MapBytes = [int64](Get-Item -LiteralPath $SpikeMapPath).Length
if ($MapBytes -lt 100000000) {
    throw "Passo Giau map was not materialized from LFS (bytes=$MapBytes)."
}

Write-Host '[2/6] Building exact UE 5.8 editor revision once...' -ForegroundColor Cyan
$BuildBat = Join-Path $Context.EngineRoot 'Engine/Build/BatchFiles/Build.bat'
$BuildArgs = @($ProjectPath,'YetAnotherCyclingSimEditor','Win64','Development','-WaitMutex','-FromMsBuild')
$BuildProc = Start-Process -FilePath $BuildBat -ArgumentList $BuildArgs -NoNewWindow -PassThru -RedirectStandardOutput $BuildLog -WorkingDirectory (Split-Path $BuildBat -Parent)
$BuildProc.WaitForExit()
$BuildExit = $BuildProc.ExitCode
if ($null -eq $BuildExit -and (Test-Path -LiteralPath $BuildLog -PathType Leaf)) {
    $BuildText = Get-Content -LiteralPath $BuildLog -Raw -ErrorAction SilentlyContinue
    if ($BuildText -match 'Result: Succeeded') { $BuildExit = 0 }
}
if ($BuildExit -ne 0) { throw "Editor build failed with exit code $BuildExit. See $BuildLog" }

$Stamp = [ordered]@{
    schema_version = 1
    expected_head = $ExpectedHead
    repo_root = $RepoRoot
    project_path = $ProjectPath
    map_relative = $SpikeMapRelative
    map_bytes = $MapBytes
    map_materialized = $true
    editor_build = 'PASS'
    build_target = 'YetAnotherCyclingSimEditor'
    build_platform = 'Win64'
    build_configuration = 'Development'
    prepared_utc = (Get-Date).ToUniversalTime().ToString('o')
}
$Stamp | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $StampPath -Encoding UTF8

$Pwsh = (Get-Command pwsh -ErrorAction Stop).Source
function Invoke-R4_1ChildProof {
    param(
        [Parameter(Mandatory=$true)] [string] $Label,
        [Parameter(Mandatory=$true)] [string] $ScriptRelative,
        [Parameter(Mandatory=$true)] [string] $ArtifactName
    )
    $ScriptPath = Join-Path $RepoRoot $ScriptRelative
    if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
        throw "R4.1 proof script is missing: $ScriptPath"
    }
    $ChildArtifactRoot = Join-Path $ArtifactRoot $ArtifactName
    $ChildArgs = @(
        '-NoProfile',
        '-File', $ScriptPath,
        '-RepoRoot', $RepoRoot,
        '-ProjectPath', $ProjectPath,
        '-ArtifactRoot', $ChildArtifactRoot,
        '-ExpectedBranch', $ExpectedBranch,
        '-ExpectedHead', $ExpectedHead,
        '-PreparedWorkspaceStamp', $StampPath,
        '-TimeoutSec', [string]$TimeoutSec
    )
    & $Pwsh @ChildArgs
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

Write-Host '[3/6] Geometry Script capability proof...' -ForegroundColor Cyan
Invoke-R4_1ChildProof -Label 'Geometry Script capability proof' -ScriptRelative 'scripts/ue/Invoke-YacsGeometryScriptProbe.ps1' -ArtifactName 'GeometryScriptProbe'

Write-Host '[4/6] Real SP638 topology proof...' -ForegroundColor Cyan
Invoke-R4_1ChildProof -Label 'SP638 topology proof' -ScriptRelative 'scripts/ue/Invoke-YacsSp638CorridorTopologyProbe.ps1' -ArtifactName 'LocalCorridorTopology'

Write-Host '[5/6] Bounded SP638 hairpin cut/fill proof...' -ForegroundColor Cyan
Invoke-R4_1ChildProof -Label 'SP638 hairpin proof' -ScriptRelative 'scripts/ue/Invoke-YacsPassoGiauHairpinCorridorProof.ps1' -ArtifactName 'HairpinCorridor'

Write-Host '[6/6] Rider-close local corridor visual proof...' -ForegroundColor Cyan
Invoke-R4_1ChildProof -Label 'SP638 local corridor visual proof' -ScriptRelative 'scripts/ue/Invoke-YacsSp638LocalCorridorVisualProof.ps1' -ArtifactName 'LocalCorridorVisual'

$TrackedChanges = @(git -C $RepoRoot status --porcelain=v1 --untracked-files=no)
if ($TrackedChanges.Count -gt 0) {
    throw ("R4.1 prepared proof suite mutated tracked files: {0}" -f ($TrackedChanges -join '; '))
}

$Summary = [ordered]@{
    r4_1_prepared_proof_suite = 'PASS'
    expected_head = $ExpectedHead
    editor_build_count = 1
    lfs_map_materialization_count = 1
    prepared_workspace_stamp = $StampPath
    proofs = [ordered]@{
        geometry_script_capability = 'PASS'
        local_corridor_topology = 'PASS'
        hairpin_corridor = 'PASS'
        local_corridor_visual = 'PASS'
    }
}
$Summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8

Write-Host 'Stage 3G R4.1 prepared proof suite: PASS.' -ForegroundColor Green
Write-Host ("Summary: {0}" -f $SummaryPath)
exit 0
