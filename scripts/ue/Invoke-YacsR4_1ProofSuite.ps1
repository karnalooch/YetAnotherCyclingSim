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

$SessionScript = Join-Path $RepoRoot 'scripts/ue/r4_1_editor_session.py'
$SessionLog = Join-Path $ArtifactRoot 'editor_session.log'
$SessionStdout = Join-Path $ArtifactRoot 'editor_session.stdout.log'
$SessionErr = Join-Path $ArtifactRoot 'editor_session.stderr.log'
$SessionSummaryPath = Join-Path $ArtifactRoot 'editor_session_summary.json'
foreach ($Path in @($SessionLog,$SessionStdout,$SessionErr,$SessionSummaryPath)) {
    Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
}
if (-not (Test-Path -LiteralPath $SessionScript -PathType Leaf)) {
    throw "R4.1 editor-session dispatcher is missing: $SessionScript"
}
$UEditor = [string]$Context.UnrealEditorPath
if (-not $UEditor -or -not (Test-Path -LiteralPath $UEditor -PathType Leaf)) {
    throw 'R4.1 prepared suite could not resolve UnrealEditor.exe.'
}

Write-Host '[3/6] Booting Unreal once for the complete R4.1 proof bundle...' -ForegroundColor Cyan
$env:YACS_R4_1_SESSION_ARTIFACT_ROOT = $ArtifactRoot
$env:YACS_R4_1_SESSION_EXPECTED_HEAD = $ExpectedHead
try {
    $SessionArgs = @(
        $ProjectPath,
        ('-ExecutePythonScript="' + $SessionScript + '"'),
        '-Unattended','-NoPause','-NoSplash','-NoP4',
        '-windowed','-ResX=1920','-ResY=1080','-NoVSync','-FixedSeed',
        '-ScriptErrorsAreFatal','-log','-stdout',('-AbsLog=' + $SessionLog)
    )
    $SessionProc = Start-Process -FilePath $UEditor -ArgumentList $SessionArgs -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $SessionStdout -RedirectStandardError $SessionErr
    if (-not $SessionProc.WaitForExit($TimeoutSec * 1000)) {
        try { $SessionProc | Stop-Process -Force } catch { }
        throw 'R4.1 single-editor proof session timed out.'
    }
    $SessionExitCode = $SessionProc.ExitCode
}
finally {
    Remove-Item Env:YACS_R4_1_SESSION_ARTIFACT_ROOT -ErrorAction SilentlyContinue
    Remove-Item Env:YACS_R4_1_SESSION_EXPECTED_HEAD -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $SessionSummaryPath -PathType Leaf)) {
    throw "R4.1 editor-session summary is missing (exit=$SessionExitCode)."
}
$SessionSummary = Get-Content -LiteralPath $SessionSummaryPath -Raw | ConvertFrom-Json
if ($SessionSummary.r4_1_editor_session -ne 'PASS') {
    throw "R4.1 editor session did not report PASS: $($SessionSummary.error)"
}
if ([int]$SessionSummary.editor_process_count -ne 1 -or [bool]$SessionSummary.single_editor_process -ne $true) {
    throw 'R4.1 proof bundle did not use exactly one Unreal Editor process.'
}
if ([string]$SessionSummary.expected_head -ne $ExpectedHead -or [string]$SessionSummary.actual_head -ne $ExpectedHead) {
    throw 'R4.1 editor-session exact-SHA provenance mismatch.'
}
if ($SessionExitCode -notin @(0,1)) {
    throw "R4.1 single-editor proof session returned unexpected exit code $SessionExitCode."
}
$SessionLogText = Get-Content -LiteralPath $SessionLog -Raw -ErrorAction Stop
if ($SessionLogText -match '(?i)Fatal error|Unhandled Exception|Critical error') {
    throw 'R4.1 single-editor session log contains a crash/fatal marker.'
}
if ($SessionLogText -notmatch '\[YacsR41EditorSession\] PASS: all R4\.1 proofs completed in one editor process') {
    throw 'R4.1 single-editor session log is missing the final PASS marker.'
}

$Pwsh = (Get-Command pwsh -ErrorAction Stop).Source
function Test-R4_1SessionEvidence {
    param(
        [Parameter(Mandatory=$true)] [string] $Label,
        [Parameter(Mandatory=$true)] [string] $ScriptRelative,
        [Parameter(Mandatory=$true)] [string] $ArtifactName
    )
    $ScriptPath = Join-Path $RepoRoot $ScriptRelative
    if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
        throw "R4.1 proof validator is missing: $ScriptPath"
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
        '-ValidateOnly',
        '-TimeoutSec', [string]$TimeoutSec
    )
    & $Pwsh @ChildArgs
    if ($LASTEXITCODE -ne 0) {
        throw "$Label validation failed with exit code $LASTEXITCODE."
    }
}

Write-Host '[4/6] Validating capability and topology evidence without rebooting Unreal...' -ForegroundColor Cyan
Test-R4_1SessionEvidence -Label 'Geometry Script capability proof' -ScriptRelative 'scripts/ue/Invoke-YacsGeometryScriptProbe.ps1' -ArtifactName 'GeometryScriptProbe'
Test-R4_1SessionEvidence -Label 'SP638 topology proof' -ScriptRelative 'scripts/ue/Invoke-YacsSp638CorridorTopologyProbe.ps1' -ArtifactName 'LocalCorridorTopology'

Write-Host '[5/6] Validating bounded hairpin evidence without rebooting Unreal...' -ForegroundColor Cyan
Test-R4_1SessionEvidence -Label 'SP638 hairpin proof' -ScriptRelative 'scripts/ue/Invoke-YacsPassoGiauHairpinCorridorProof.ps1' -ArtifactName 'HairpinCorridor'

Write-Host '[6/6] Validating rider-close evidence without rebooting Unreal...' -ForegroundColor Cyan
Test-R4_1SessionEvidence -Label 'SP638 local corridor visual proof' -ScriptRelative 'scripts/ue/Invoke-YacsSp638LocalCorridorVisualProof.ps1' -ArtifactName 'LocalCorridorVisual'

$TrackedChanges = @(git -C $RepoRoot status --porcelain=v1 --untracked-files=no)
if ($TrackedChanges.Count -gt 0) {
    throw ("R4.1 prepared proof suite mutated tracked files: {0}" -f ($TrackedChanges -join '; '))
}

$Summary = [ordered]@{
    r4_1_prepared_proof_suite = 'PASS'
    expected_head = $ExpectedHead
    editor_build_count = 1
    editor_process_count = 1
    editor_boot_count = 1
    lfs_map_materialization_count = 1
    editor_session_summary = $SessionSummaryPath
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
