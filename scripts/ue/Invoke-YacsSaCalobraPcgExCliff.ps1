<#
.SYNOPSIS
    Build and prove the transient Sa Calobra Component_230 PCGEx cliff topology.

.DESCRIPTION
    Installs the exact reviewed PCGEx 0.79 revision, builds
    YetAnotherCyclingSimEditor against it, executes the transient Phase 2C
    commandlet twice, and fails closed unless both mesh receipts are
    canonically identical.

    The commandlet never saves a PCG graph, map, DynamicMesh asset or Landscape.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path,
    [string] $ProjectPath,
    [Parameter(Mandatory=$true)] [string] $PlanPath,
    [Parameter(Mandatory=$true)] [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [string] $ExpectedBranch = 'HEAD',
    [int] $TimeoutSec = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) { $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject' }
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
$PlanPath = (Resolve-Path -LiteralPath $PlanPath).Path

if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) {
    $ArtifactRoot = Join-Path $RepoRoot $ArtifactRoot
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$Bootstrap = Join-Path $RepoRoot 'scripts/worldgen/Bootstrap-YacsPcgEx.ps1'
$BootstrapReport = Join-Path $ArtifactRoot 'pcgex-bootstrap.json'
$BuildLog = Join-Path $ArtifactRoot 'build_editor_pcgex.log'
$MeshA = Join-Path $ArtifactRoot 'phase2c-pcgex-cliff-a.json'
$MeshB = Join-Path $ArtifactRoot 'phase2c-pcgex-cliff-b.json'
$LogA = Join-Path $ArtifactRoot 'phase2c-commandlet-a.log'
$LogB = Join-Path $ArtifactRoot 'phase2c-commandlet-b.log'
$StdoutA = Join-Path $ArtifactRoot 'phase2c-commandlet-a.stdout.log'
$StdoutB = Join-Path $ArtifactRoot 'phase2c-commandlet-b.stdout.log'
$StderrA = Join-Path $ArtifactRoot 'phase2c-commandlet-a.stderr.log'
$StderrB = Join-Path $ArtifactRoot 'phase2c-commandlet-b.stderr.log'
$ProofPath = Join-Path $ArtifactRoot 'phase2c-pcgex-topology-proof.json'

foreach ($Path in @(
    $BootstrapReport, $BuildLog, $MeshA, $MeshB,
    $LogA, $LogB, $StdoutA, $StdoutB, $StderrA, $StderrB, $ProofPath
)) {
    Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
}

$PreflightArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $ArtifactRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
}
$Context = & $Preflight @PreflightArgs
if ($LASTEXITCODE -ne 0) { throw 'Phase 2C preflight failed.' }

Write-Host '[1/4] Installing exact PCGEx authoring revision...' -ForegroundColor Cyan
& $Bootstrap -Mode Install -RepoRoot $RepoRoot -ReportPath $BootstrapReport
if ($LASTEXITCODE -ne 0) { throw 'PCGEx exact-revision bootstrap failed.' }

$BootstrapData = Get-Content -LiteralPath $BootstrapReport -Raw | ConvertFrom-Json
if ($BootstrapData.status -ne 'PASS') { throw 'PCGEx bootstrap report did not report PASS.' }
if ($BootstrapData.actual_commit -ne '39a8f1bdc65b2c4613a1e87b71d93b4576db0a66') {
    throw 'PCGEx bootstrap revision drift.'
}
if ([bool]$BootstrapData.shipping_runtime_dependency -ne $false) {
    throw 'PCGEx unexpectedly became a shipping runtime dependency.'
}
if (
    [string]$BootstrapData.compatibility_patch -ne 'yacs-pcgex-0.79-horizontal-boundary-v2' -or
    [string]$BootstrapData.compatibility_patch_state -ne 'applied' -or
    [string]$BootstrapData.compatibility_patch_sha256 -ne '8182824990670e560d1a1f0d052288cc8a98dc5cdb370bdbf63f2666f9593d89'
) {
    throw 'PCGEx compatibility patch provenance drift.'
}

$DirtyAfterBootstrap = @(git -C $RepoRoot status --porcelain --untracked-files=all)
if ($DirtyAfterBootstrap.Count -gt 0) {
    throw ("PCGEx bootstrap dirtied the tracked worktree: {0}" -f ($DirtyAfterBootstrap -join '; '))
}

Write-Host '[2/4] Building exact-head YetAnotherCyclingSimEditor + PCGEx...' -ForegroundColor Cyan
$UbtConfigDir = Join-Path $RepoRoot 'Saved/UnrealBuildTool'
New-Item -ItemType Directory -Path $UbtConfigDir -Force | Out-Null
$UbtConfigPath = Join-Path $UbtConfigDir 'BuildConfiguration.xml'
$LogicalProcessors = [Math]::Max(1, [Environment]::ProcessorCount)
$FreeVirtualGb = [double]$Context.Machine.FreeVirtualGb
$CpuActionCap = [Math]::Max(2, [Math]::Floor($LogicalProcessors * 0.67))
if ($FreeVirtualGb -ge 14.0) {
    $MemoryActionCap = 4
}
elseif ($FreeVirtualGb -ge 8.0) {
    $MemoryActionCap = 3
}
else {
    $MemoryActionCap = 2
}
$MaxParallelActions = [int][Math]::Max(
    2,
    [Math]::Min($MemoryActionCap, $CpuActionCap)
)
$UbtConfig = @"
<?xml version="1.0" encoding="utf-8" ?>
<Configuration xmlns="https://www.unrealengine.com/BuildConfiguration">
  <BuildConfiguration>
    <bAllowUBAExecutor>false</bAllowUBAExecutor>
    <bAllowUBALocalExecutor>false</bAllowUBALocalExecutor>
    <MaxParallelActions>$MaxParallelActions</MaxParallelActions>
  </BuildConfiguration>
</Configuration>
"@
$UbtConfig | Set-Content -LiteralPath $UbtConfigPath -Encoding UTF8

$BuildBat = Join-Path $Context.EngineRoot 'Engine/Build/BatchFiles/Build.bat'
$BuildArgs = @(
    $ProjectPath,
    'YetAnotherCyclingSimEditor',
    'Win64',
    'Development',
    '-WaitMutex',
    '-NoHotReloadFromIDE',
    '-FromMsBuild'
)
$BuildStart = Get-Date
$BuildProc = Start-Process -FilePath $BuildBat -ArgumentList $BuildArgs -WorkingDirectory (Split-Path $BuildBat -Parent) -NoNewWindow -PassThru -RedirectStandardOutput $BuildLog
if (-not $BuildProc.WaitForExit($TimeoutSec * 1000)) {
    try { $BuildProc | Stop-Process -Force } catch { }
    throw 'Phase 2C PCGEx-enabled editor build timed out.'
}
$BuildSeconds = ((Get-Date) - $BuildStart).TotalSeconds
if ($BuildProc.ExitCode -ne 0) {
    Get-Content -LiteralPath $BuildLog -Tail 160 -ErrorAction SilentlyContinue | Write-Host
    throw "Phase 2C PCGEx-enabled editor build failed with exit $($BuildProc.ExitCode)."
}
$BuildText = Get-Content -LiteralPath $BuildLog -Raw -ErrorAction Stop
if ($BuildText -notmatch 'Result:\s+Succeeded' -and $BuildText -notmatch 'Target is up to date') {
    throw 'Phase 2C build log is missing a success marker.'
}

function Invoke-Phase2CCommandlet {
    param(
        [Parameter(Mandatory=$true)] [string] $OutputPath,
        [Parameter(Mandatory=$true)] [string] $EngineLog,
        [Parameter(Mandatory=$true)] [string] $StdoutLog,
        [Parameter(Mandatory=$true)] [string] $StderrLog
    )

    $Args = @(
        $ProjectPath,
        '-run=YacsSaCalobraPcgExCliff',
        ('-Plan=' + $PlanPath),
        ('-ExecutionOutput=' + $OutputPath),
        '-Unattended',
        '-NoPause',
        '-NullRHI',
        '-SkipAssetScan',
        '-AssetGatherAll=false',
        '-YacsPhase2CTopologyProof',
        '-NoSplash',
        '-NoP4',
        '-stdout',
        ('-AbsLog=' + $EngineLog)
    )
    $Started = Get-Date
    $Proc = Start-Process -FilePath $Context.UnrealEditorCmdPath -ArgumentList $Args -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog

    if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
        try { $Proc | Stop-Process -Force } catch { }
        throw 'Phase 2C commandlet timed out.'
    }
    $Seconds = ((Get-Date) - $Started).TotalSeconds
    $EngineText = Get-Content -LiteralPath $EngineLog -Raw -ErrorAction SilentlyContinue
    $StdoutText = Get-Content -LiteralPath $StdoutLog -Raw -ErrorAction SilentlyContinue
    $CombinedText = [string]$StdoutText + [Environment]::NewLine + [string]$EngineText

    if ($CombinedText -match '(?i)Fatal error|Unhandled Exception|Critical error') {
        throw 'Phase 2C commandlet log contains a fatal/crash marker.'
    }

    $HasOutput = Test-Path -LiteralPath $OutputPath -PathType Leaf
    $HasSuccessMarker = $CombinedText -match 'YACS Phase 2C PCGEx PASS:'
    $HasCommandletResultZero = $CombinedText -match 'finished execution \(result 0\)'

    if ($Proc.ExitCode -ne 0) {
        # UnrealEditor-Cmd promotes unrelated project-content load errors to the
        # process exit code even when this isolated commandlet completed with
        # result 0. Accept only the exact known Git-LFS-pointer fallout and
        # retain fail-closed behavior for every commandlet/PCG/geometry error.
        if (-not ($HasOutput -and $HasSuccessMarker -and $HasCommandletResultZero)) {
            foreach ($Diagnostic in @($StdoutLog, $StderrLog, $EngineLog)) {
                if (Test-Path -LiteralPath $Diagnostic -PathType Leaf) {
                    Write-Host "===== TAIL $Diagnostic ====="
                    Get-Content -LiteralPath $Diagnostic -Tail 220 | Write-Host
                }
            }
            throw "Phase 2C commandlet returned exit $($Proc.ExitCode) without a successful isolated commandlet receipt."
        }

        $UnexpectedErrors = @()
        foreach ($Line in ($CombinedText -split "\r?\n")) {
            if ($Line -notmatch 'Error:') {
                continue
            }

            $KnownLfsPointerNoise = (
                $Line -match "LoadErrors: Error: The summary for the package '.+' is invalid\. Check that the file is of the expected type and not corrupted\."
            ) -or (
                $Line -match 'LogUObjectGlobals: Error: CDO Constructor \(Stage3PrototypeTerrainActor\): Failed to find /Game/Prototype/Environment/Stage3F/Materials/MI_Stage3F_(Asphalt|Edge|Terrain)\.MI_Stage3F_(Asphalt|Edge|Terrain)'
            ) -or (
                $Line -match 'LogUObjectBase: Warning: LogUObjectGlobals: Error: CDO Constructor \(Stage3PrototypeTerrainActor\): Failed to find /Game/Prototype/Environment/Stage3F/Materials/MI_Stage3F_(Asphalt|Edge|Terrain)\.MI_Stage3F_(Asphalt|Edge|Terrain)'
            )

            if (-not $KnownLfsPointerNoise) {
                $UnexpectedErrors += $Line
            }
        }

        if ($UnexpectedErrors.Count -gt 0) {
            Write-Host '===== UNEXPECTED PHASE 2C COMMANDLET ERRORS ====='
            $UnexpectedErrors | Select-Object -Unique | Write-Host
            throw "Phase 2C commandlet returned exit $($Proc.ExitCode) with errors outside the admitted LFS-pointer startup noise."
        }

        Write-Host (
            "Phase 2C scoped commandlet result PASS despite process exit {0}; " +
            "all error lines were proven unrelated LFS-pointer startup noise." -f
                $Proc.ExitCode
        ) -ForegroundColor Yellow
    }

    if (-not $HasOutput) {
        throw "Phase 2C commandlet did not write $OutputPath"
    }
    if (-not $HasSuccessMarker -or -not $HasCommandletResultZero) {
        throw 'Phase 2C commandlet log is missing the isolated result-0 success contract.'
    }

    $Data = Get-Content -LiteralPath $OutputPath -Raw | ConvertFrom-Json
    if ($Data.status -ne 'YACS_SA_CALOBRA_PCGEX_CLIFF_MESH_PASS') {
        throw 'Phase 2C mesh receipt did not report PASS.'
    }
    if ($Data.pcgex_commit -ne '39a8f1bdc65b2c4613a1e87b71d93b4576db0a66') {
        throw 'Phase 2C mesh receipt PCGEx revision drift.'
    }
    if ([bool]$Data.canonical_landscape_mutation -ne $false -or
        [bool]$Data.assets_saved -ne $false -or
        [bool]$Data.graph_saved -ne $false) {
        throw 'Phase 2C transient/no-mutation contract failed.'
    }
    if ([int]$Data.vertex_count -le 0 -or [int]$Data.triangle_count -le 0) {
        throw 'Phase 2C mesh receipt is empty.'
    }
    if ([double]$Data.max_edge_cm_after -gt 157.5) {
        throw "Phase 2C post-tessellation edge gate failed: $($Data.max_edge_cm_after) cm."
    }
    if ([int]$Data.triangle_count -gt 120000) {
        throw "Phase 2C aggregate triangle budget failed: $($Data.triangle_count)."
    }
    return [pscustomobject]@{
        Data = $Data
        Seconds = [double]$Seconds
    }
}

Write-Host '[3/4] Executing transient PCGEx topology twice...' -ForegroundColor Cyan
$RunA = Invoke-Phase2CCommandlet -OutputPath $MeshA -EngineLog $LogA -StdoutLog $StdoutA -StderrLog $StderrA
$RunB = Invoke-Phase2CCommandlet -OutputPath $MeshB -EngineLog $LogB -StdoutLog $StdoutB -StderrLog $StderrB
$DataA = $RunA.Data
$DataB = $RunB.Data

$CanonicalScript = @'
import hashlib
import json
import sys

def canonical(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), len(payload)

a_hash, a_bytes = canonical(sys.argv[1])
b_hash, b_bytes = canonical(sys.argv[2])
print(json.dumps({
    "status": "PASS" if a_hash == b_hash else "FAIL",
    "canonical_sha256_a": a_hash,
    "canonical_sha256_b": b_hash,
    "canonical_bytes_a": a_bytes,
    "canonical_bytes_b": b_bytes,
}))
raise SystemExit(0 if a_hash == b_hash else 2)
'@
$DeterminismRaw = $CanonicalScript | python - $MeshA $MeshB
if ($LASTEXITCODE -ne 0) {
    Write-Host $DeterminismRaw
    throw 'Phase 2C canonical mesh determinism failed.'
}
$Determinism = $DeterminismRaw | ConvertFrom-Json
if ($Determinism.status -ne 'PASS') {
    throw 'Phase 2C canonical mesh determinism receipt did not report PASS.'
}

Write-Host '[4/4] Writing exact-head Phase 2C proof...' -ForegroundColor Cyan
$Head = (git -C $RepoRoot rev-parse HEAD).Trim()
if ($Head -ne $ExpectedHead) {
    throw "Phase 2C HEAD drifted: actual=$Head expected=$ExpectedHead"
}

$TrackedDirty = @(git -C $RepoRoot status --porcelain=v1 --untracked-files=no)
if ($TrackedDirty.Count -gt 0) {
    throw ("Phase 2C proof mutated tracked files: {0}" -f ($TrackedDirty -join '; '))
}

$Proof = [ordered]@{
    schema_version = 1
    proof = 'yacs-sa-calobra-component230-pcgex-cliff-topology'
    status = 'PASS'
    repository_head = $Head
    pcgex_commit = [string]$BootstrapData.actual_commit
    pcgex_compatibility_patch = [string]$BootstrapData.compatibility_patch
    pcgex_compatibility_patch_sha256 = [string]$BootstrapData.compatibility_patch_sha256
    pcgex_compatibility_patch_state = [string]$BootstrapData.compatibility_patch_state
    pcgex_shipping_runtime_dependency = $false
    source_plan = $PlanPath
    build_seconds = [math]::Round([double]$BuildSeconds, 3)
    run_a_seconds = [math]::Round([double]$RunA.Seconds, 3)
    run_b_seconds = [math]::Round([double]$RunB.Seconds, 3)
    generator = [ordered]@{
        pipeline = [string]$DataA.pipeline
        source_skin_cell_count = [int]$DataA.source_skin_cell_count
        mesh_count = [int]$DataA.mesh_count
        vertex_count = [int]$DataA.vertex_count
        triangle_count = [int]$DataA.triangle_count
        target_edge_cm = [double]$DataA.target_edge_cm
        max_edge_cm_before = [double]$DataA.max_edge_cm_before
        max_edge_cm_after = [double]$DataA.max_edge_cm_after
        max_tessellation = [int]$DataA.max_tessellation
    }
    determinism = [ordered]@{
        canonical_sha256 = [string]$Determinism.canonical_sha256_a
        canonical_bytes = [int64]$Determinism.canonical_bytes_a
        independent_runs = 2
    }
    canonical_landscape_mutation = $false
    assets_saved = $false
    graph_saved = $false
}
$Proof | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ProofPath -Encoding UTF8

Write-Host "Phase 2C PCGEx topology proof: PASS ($Head)" -ForegroundColor Green
Write-Host "Mesh A: $MeshA"
Write-Host "Proof: $ProofPath"
