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

Write-Host '[1/3] Materializing persisted Passo Giau map once...' -ForegroundColor Cyan
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

Write-Host '[2/3] Building exact UE 5.8 editor revision once...' -ForegroundColor Cyan
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

$SessionScript = Join-Path $RepoRoot 'scripts/ue/run_r4_1_proof_session.py'
$SessionLog = Join-Path $ArtifactRoot 'r4_1_session.log'
$SessionStdout = Join-Path $ArtifactRoot 'r4_1_session.stdout.log'
$SessionStderr = Join-Path $ArtifactRoot 'r4_1_session.stderr.log'
foreach ($Path in @($SessionLog,$SessionStdout,$SessionStderr,$SummaryPath)) {
    Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
}
if (-not (Test-Path -LiteralPath $SessionScript -PathType Leaf)) {
    throw "R4.1 session script is missing: $SessionScript"
}

Write-Host '[3/3] Booting Unreal once and running the fixed R4.1 proof session...' -ForegroundColor Cyan
$UEditor = $Context.UnrealEditorPath
if (-not $UEditor -or -not (Test-Path -LiteralPath $UEditor -PathType Leaf)) {
    throw 'UnrealEditor.exe GUI executable is unavailable.'
}

$env:YACS_R4_1_SESSION_ARTIFACT_ROOT = $ArtifactRoot
$env:YACS_R4_1_SESSION_EXACT_HEAD = $ExpectedHead
try {
    $SessionArgs = @(
        $ProjectPath,
        ('-ExecutePythonScript="' + $SessionScript + '"'),
        '-Unattended','-NoPause','-NoSplash','-NoP4',
        '-windowed','-ResX=1920','-ResY=1080','-NoVSync','-FixedSeed',
        '-ScriptErrorsAreFatal','-log','-stdout',('-AbsLog=' + $SessionLog)
    )
    $SessionProc = Start-Process -FilePath $UEditor -ArgumentList $SessionArgs -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $SessionStdout -RedirectStandardError $SessionStderr
    if (-not $SessionProc.WaitForExit($TimeoutSec * 1000)) {
        try { $SessionProc | Stop-Process -Force } catch { }
        throw 'R4.1 boot-once proof session timed out.'
    }
    $SessionExit = $SessionProc.ExitCode
}
finally {
    Remove-Item Env:YACS_R4_1_SESSION_ARTIFACT_ROOT -ErrorAction SilentlyContinue
    Remove-Item Env:YACS_R4_1_SESSION_EXACT_HEAD -ErrorAction SilentlyContinue
}

if ($SessionExit -notin @(0,1)) {
    throw "R4.1 boot-once proof session returned unexpected exit code $SessionExit."
}
if (-not (Test-Path -LiteralPath $SummaryPath -PathType Leaf)) {
    throw 'R4.1 boot-once proof session summary is missing.'
}
$SessionSummary = Get-Content -LiteralPath $SummaryPath -Raw | ConvertFrom-Json
if ($SessionSummary.r4_1_boot_once_proof_suite -ne 'PASS') {
    throw "R4.1 boot-once proof session did not PASS: $($SessionSummary.error)"
}
if ([string]$SessionSummary.expected_head -ne $ExpectedHead) {
    throw 'R4.1 boot-once proof session summary HEAD mismatch.'
}
if ([int]$SessionSummary.editor_boot_count -ne 1) {
    throw "R4.1 proof session booted Unreal more than once: $($SessionSummary.editor_boot_count)"
}

$Evidence = @(
    @{ Path = (Join-Path $ArtifactRoot 'GeometryScriptProbe/geometry_script_probe.json'); Field = 'geometry_script_probe'; Png = $null },
    @{ Path = (Join-Path $ArtifactRoot 'LocalCorridorTopology/sp638_corridor_topology.json'); Field = 'sp638_local_corridor_topology'; Png = $null },
    @{ Path = (Join-Path $ArtifactRoot 'HairpinCorridor/hairpin_capture_proof.json'); Field = 'passo_giau_hairpin_corridor_capture'; Png = (Join-Path $ArtifactRoot 'HairpinCorridor/passo_giau_sp638_hairpin_corridor_3840x2160.png') },
    @{ Path = (Join-Path $ArtifactRoot 'LocalCorridorVisual/local_corridor_visual_proof.json'); Field = 'sp638_local_corridor_visual'; Png = (Join-Path $ArtifactRoot 'LocalCorridorVisual/sp638_local_corridor_rider_3840x2160.png') }
)
foreach ($Item in $Evidence) {
    if (-not (Test-Path -LiteralPath $Item.Path -PathType Leaf)) {
        throw "R4.1 proof evidence is missing: $($Item.Path)"
    }
    $Proof = Get-Content -LiteralPath $Item.Path -Raw | ConvertFrom-Json
    if ([string]$Proof.($Item.Field) -ne 'PASS') {
        throw "R4.1 proof evidence did not report PASS: $($Item.Path)"
    }
    if ([string]$Proof.exact_head -ne $ExpectedHead) {
        throw "R4.1 proof evidence HEAD mismatch: $($Item.Path)"
    }
    if ([string]$Proof.r4_1_session_id -ne [string]$SessionSummary.r4_1_session_id) {
        throw "R4.1 proof evidence session mismatch: $($Item.Path)"
    }
    if ([int]$Proof.editor_pid -ne [int]$SessionSummary.editor_pid) {
        throw "R4.1 proof evidence came from a different Unreal process: $($Item.Path)"
    }
    if ([int]$Proof.editor_boot_count -ne 1) {
        throw "R4.1 proof evidence reports more than one Unreal boot: $($Item.Path)"
    }
    if ($Item.Png) {
        if (-not (Test-Path -LiteralPath $Item.Png -PathType Leaf)) {
            throw "R4.1 proof PNG is missing: $($Item.Png)"
        }
        if ((Get-Item -LiteralPath $Item.Png).Length -lt 100000) {
            throw "R4.1 proof PNG is unexpectedly small: $($Item.Png)"
        }
    }
}

$SessionLogText = Get-Content -LiteralPath $SessionLog -Raw -ErrorAction Stop
if ($SessionLogText -notmatch '\[YacsR41Session\] PASS:') {
    throw 'R4.1 session log is missing the explicit PASS marker.'
}

$TrackedChanges = @(git -C $RepoRoot status --porcelain=v1 --untracked-files=no)
if ($TrackedChanges.Count -gt 0) {
    throw ("R4.1 prepared proof suite mutated tracked files: {0}" -f ($TrackedChanges -join '; '))
}

$FinalSummary = [ordered]@{
    r4_1_prepared_proof_suite = 'PASS'
    r4_1_boot_once_proof_suite = 'PASS'
    expected_head = $ExpectedHead
    editor_build_count = 1
    editor_boot_count = 1
    editor_pid = [int]$SessionSummary.editor_pid
    r4_1_session_id = [string]$SessionSummary.r4_1_session_id
    lfs_map_materialization_count = 1
    prepared_workspace_stamp = $StampPath
    proofs = [ordered]@{
        geometry_script_capability = 'PASS'
        local_corridor_topology = 'PASS'
        hairpin_corridor = 'PASS'
        local_corridor_visual = 'PASS'
    }
}
$FinalSummary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8

Write-Host 'Stage 3G R4.1 build-once / boot-once proof suite: PASS.' -ForegroundColor Green
Write-Host ("Summary: {0}" -f $SummaryPath)
exit 0
