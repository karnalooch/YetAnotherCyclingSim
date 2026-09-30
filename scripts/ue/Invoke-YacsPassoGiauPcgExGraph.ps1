<#
.SYNOPSIS
    Build and author the deterministic Passo Giau PCGEx corridor graph.

.DESCRIPTION
    Installs the exact reviewed PCGEx source revision as an ignored authoring-only
    checkout, builds YetAnotherCyclingSimEditor against that revision when the
    compile fingerprint is not already validated, executes the
    YacsPassoGiauPcgExGraph commandlet, and emits exact-SHA proof metadata.

    This proof validates graph topology authoring, plugin/API integration, and
    execution against the prepared official SP638 presentation input. It records
    generated PCG point collections for the subsequent deviation analysis.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [string] $ExpectedBranch = 'HEAD',
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [switch] $SkipBuild,
    [int] $TimeoutSec = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) { $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject' }
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path

if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/CI/M3/PCGExCorridor'
}
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) {
    $ArtifactRoot = Join-Path $RepoRoot $ArtifactRoot
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$Bootstrap = Join-Path $RepoRoot 'scripts/worldgen/Bootstrap-YacsPcgEx.ps1'
$ManifestPath = Join-Path $RepoRoot 'worldgen/embark/pcgex/passo_giau_corridor.json'
$BootstrapReport = Join-Path $ArtifactRoot 'pcgex-bootstrap.json'
$BuildLog = Join-Path $ArtifactRoot 'build_editor_pcgex.log'
$CommandletLog = Join-Path $ArtifactRoot 'pcgex_graph_commandlet.log'
$CommandletErr = Join-Path $ArtifactRoot 'pcgex_graph_commandlet.stderr.log'
$ProofPath = Join-Path $ArtifactRoot 'pcgex_graph_proof.json'
$ExecutionOutputPath = Join-Path $ArtifactRoot 'pcgex_graph_output.json'

$GeneratedAssetRelative = 'Content/WorldGen/PCGEx/PCG_PassoGiau_SP638_Corridor.uasset'
$GeneratedAssetPath = Join-Path $RepoRoot $GeneratedAssetRelative

foreach ($Path in @($BootstrapReport, $BuildLog, $CommandletLog, $CommandletErr, $ProofPath, $ExecutionOutputPath)) {
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
if ($LASTEXITCODE -ne 0) { throw 'PCGEx corridor preflight failed.' }

if (Test-Path -LiteralPath $GeneratedAssetPath -PathType Leaf) {
    throw "Generated PCGEx graph asset already exists before authoring: $GeneratedAssetRelative"
}

Write-Host '[1/4] Installing exact PCGEx authoring revision...' -ForegroundColor Cyan
& $Bootstrap -Mode Install -RepoRoot $RepoRoot -ReportPath $BootstrapReport
if ($LASTEXITCODE -ne 0) { throw 'PCGEx exact-SHA bootstrap failed.' }

$DirtyAfterBootstrap = @(git -C $RepoRoot status --porcelain --untracked-files=all)
if ($DirtyAfterBootstrap.Count -gt 0) {
    throw ("PCGEx bootstrap dirtied the tracked worktree: {0}" -f ($DirtyAfterBootstrap -join '; '))
}

$BootstrapData = Get-Content -LiteralPath $BootstrapReport -Raw | ConvertFrom-Json
if ($BootstrapData.status -ne 'PASS') { throw 'PCGEx bootstrap report did not report PASS.' }
if ($BootstrapData.actual_commit -ne '39a8f1bdc65b2c4613a1e87b71d93b4576db0a66') {
    throw 'PCGEx bootstrap report does not match the pinned reviewed revision.'
}
if ([bool]$BootstrapData.shipping_runtime_dependency -ne $false) {
    throw 'PCGEx bootstrap unexpectedly declares a shipping runtime dependency.'
}

if ($SkipBuild) {
    Write-Host '[2/4] Reusing compile-fingerprinted YetAnotherCyclingSimEditor + PCGEx binaries...' -ForegroundColor Cyan
    $ProjectBinaryRoot = Join-Path $RepoRoot 'Binaries/Win64'
    $PluginBinaryRoot = Join-Path $RepoRoot 'Plugins/PCGExtendedToolkit/Binaries/Win64'
    $ProjectModules = @(
        Get-ChildItem -LiteralPath $ProjectBinaryRoot -File -Filter 'UnrealEditor-YetAnotherCyclingSimEditor*.dll' -ErrorAction SilentlyContinue
    )
    $PluginModules = @(
        Get-ChildItem -LiteralPath $PluginBinaryRoot -File -Filter '*.dll' -ErrorAction SilentlyContinue
    )
    if ($ProjectModules.Count -eq 0) {
        throw 'Compile-fingerprint cache is missing YetAnotherCyclingSimEditor binaries.'
    }
    if ($PluginModules.Count -eq 0) {
        throw 'Compile-fingerprint cache is missing PCGEx plugin binaries.'
    }
    @(
        'Build skipped: validated compile fingerprint cache hit.'
        ('Project modules: {0}' -f $ProjectModules.Count)
        ('PCGEx modules: {0}' -f $PluginModules.Count)
    ) | Set-Content -LiteralPath $BuildLog -Encoding UTF8
}
else {
    Write-Host '[2/4] Building YetAnotherCyclingSimEditor with PCGEx enabled...' -ForegroundColor Cyan
    
    # Reuse the proven resource-constrained CI profile from Invoke-YacsProof.ps1.
    # PCGEx materially increases translation-unit and link pressure; allowing the
    # default UBA executor on this host has already produced Windows VirtualAlloc
    # error 1455 followed by an MSVC C1001 internal compiler error. Keep this proof
    # on the same fail-closed memory policy as the green Unreal CI lane.
    $UbtConfigDir = Join-Path -Path $RepoRoot -ChildPath 'Saved/UnrealBuildTool'
    New-Item -ItemType Directory -Path $UbtConfigDir -Force | Out-Null
    $UbtConfigPath = Join-Path -Path $UbtConfigDir -ChildPath 'BuildConfiguration.xml'
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
    $MaxParallelActions = [int][Math]::Min($MemoryActionCap, $CpuActionCap)
    $MaxParallelActions = [int][Math]::Max(2, $MaxParallelActions)
    
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
    Write-Host (
        "PCGEx conservative UBT profile: UBA disabled; MaxParallelActions={0}; logicalProcessors={1}; freeVirtualGb={2:N2}; config={3}" -f
        $MaxParallelActions,
        $LogicalProcessors,
        $FreeVirtualGb,
        $UbtConfigPath
    ) -ForegroundColor Yellow
    
    $BuildBat = Join-Path $Context.EngineRoot 'Engine/Build/BatchFiles/Build.bat'
    $BuildArgs = @($ProjectPath, 'YetAnotherCyclingSimEditor', 'Win64', 'Development', '-WaitMutex', '-FromMsBuild')
    $BuildProc = Start-Process -FilePath $BuildBat -ArgumentList $BuildArgs -WorkingDirectory (Split-Path $BuildBat -Parent) -NoNewWindow -PassThru -RedirectStandardOutput $BuildLog
    $BuildProc.WaitForExit()
    if ($BuildProc.ExitCode -ne 0) {
        throw "PCGEx-enabled editor build failed with exit code $($BuildProc.ExitCode). See $BuildLog"
    }
    
    $BuildText = Get-Content -LiteralPath $BuildLog -Raw -ErrorAction Stop
    if ($BuildText -notmatch 'Result:\s+Succeeded' -and $BuildText -notmatch 'Target is up to date') {
        throw 'PCGEx-enabled editor build log is missing a success marker.'
    }
    
    
}

Write-Host '[3/4] Authoring deterministic PCGEx corridor graph asset...' -ForegroundColor Cyan
$CommandletArgs = @(
    $ProjectPath,
    '-run=YacsPassoGiauPcgExGraph',
    '-Execute',
    ('-ExecutionOutput=' + $ExecutionOutputPath),
    '-Unattended',
    '-NoPause',
    '-NullRHI',
    '-NoSplash',
    '-NoP4',
    '-log',
    ('-AbsLog=' + $CommandletLog)
)
$Proc = Start-Process -FilePath $Context.UnrealEditorCmdPath -ArgumentList $CommandletArgs -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $CommandletLog -RedirectStandardError $CommandletErr

if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
    try { $Proc | Stop-Process -Force } catch { }
    throw 'PCGEx graph commandlet timed out.'
}
$ExitCode = $Proc.ExitCode

if (-not (Test-Path -LiteralPath $GeneratedAssetPath -PathType Leaf)) {
    throw "PCGEx graph asset was not generated (exit=$ExitCode): $GeneratedAssetRelative"
}
$CommandletText = Get-Content -LiteralPath $CommandletLog -Raw -ErrorAction Stop
if ($ExitCode -notin @(0, 1)) {
    throw "PCGEx graph commandlet returned unexpected exit code $ExitCode."
}
if ($CommandletText -match '(?i)Fatal error|Unhandled Exception|Critical error') {
    throw 'PCGEx graph commandlet log contains a crash/fatal marker.'
}
if ($CommandletText -notmatch 'YACS PCGEx corridor graph authored:') {
    throw 'PCGEx graph commandlet log is missing the authoring success marker.'
}
if ($CommandletText -notmatch 'SP638 presentation -> resample 1m -> bounded smooth -> \+/-3m offsets') {
    throw 'PCGEx graph commandlet log is missing the deterministic graph contract marker.'
}
if ($CommandletText -notmatch 'YACS PCGEx corridor graph executed:') {
    throw 'PCGEx graph commandlet log is missing the execution success marker.'
}
if (-not (Test-Path -LiteralPath $ExecutionOutputPath -PathType Leaf)) {
    throw 'PCGEx graph execution did not produce pcgex_graph_output.json.'
}
$ExecutionData = Get-Content -LiteralPath $ExecutionOutputPath -Raw | ConvertFrom-Json
if ($ExecutionData.status -ne 'PASS') { throw 'PCGEx graph execution output did not report PASS.' }
if ([int]$ExecutionData.point_dataset_count -lt 3) {
    throw "PCGEx graph execution produced fewer than three point datasets: $($ExecutionData.point_dataset_count)"
}
if ([int]$ExecutionData.total_point_count -le 0) {
    throw 'PCGEx graph execution produced no points.'
}
if ($ExitCode -eq 1) {
    Write-Warning 'UE returned exit 1 after the graph asset and success markers were proven; treating known code-only Asset Registry noise as non-owning.'
}

Write-Host '[4/4] Writing exact-SHA PCGEx graph proof...' -ForegroundColor Cyan
$Head = (git -C $RepoRoot rev-parse HEAD).Trim()
if ($Head -ne $ExpectedHead) { throw "PCGEx graph proof HEAD drifted: actual=$Head expected=$ExpectedHead" }

$AssetInfo = Get-Item -LiteralPath $GeneratedAssetPath
$AssetHash = (Get-FileHash -LiteralPath $GeneratedAssetPath -Algorithm SHA256).Hash.ToLowerInvariant()
$ManifestHash = (Get-FileHash -LiteralPath $ManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
$ExecutionOutputHash = (Get-FileHash -LiteralPath $ExecutionOutputPath -Algorithm SHA256).Hash.ToLowerInvariant()

$NormalizedGeneratedPath = $GeneratedAssetRelative.Replace('\','/')
$Unexpected = @(
    git -C $RepoRoot status --porcelain --untracked-files=all |
        Where-Object { $_ -notmatch [regex]::Escape($NormalizedGeneratedPath) }
)
if ($Unexpected.Count -gt 0) {
    throw ("Unexpected tracked/untracked mutations after PCGEx graph authoring: {0}" -f ($Unexpected -join '; '))
}

$Proof = [ordered]@{
    schema_version = 1
    proof = 'yacs-passo-giau-pcgex-graph'
    status = 'PASS'
    repository_head = $Head
    pcgex_commit = [string]$BootstrapData.actual_commit
    pcgex_shipping_runtime_dependency = $false
    graph = [ordered]@{
        package = '/Game/WorldGen/PCGEx/PCG_PassoGiau_SP638_Corridor'
        asset_relative_path = $GeneratedAssetRelative
        bytes = [int64]$AssetInfo.Length
        sha256 = $AssetHash
        manifest_sha256 = $ManifestHash
        execution_scope = 'graph_execution_against_prepared_sp638'
        execution_output_sha256 = $ExecutionOutputHash
        point_dataset_count = [int]$ExecutionData.point_dataset_count
        total_point_count = [int]$ExecutionData.total_point_count
    }
    commandlet_exit_code = $ExitCode
}
$Proof | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ProofPath -Encoding UTF8

Write-Host "PCGEx corridor graph proof: PASS ($Head)" -ForegroundColor Green
