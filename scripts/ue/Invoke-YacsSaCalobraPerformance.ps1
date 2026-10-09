<# Exact-SHA native Sa Calobra terrain baseline; shares the existing timing policy. #>
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$ExpectedHead,
 [Parameter(Mandatory=$true)][string]$ArtifactRoot,
 [string]$ConsumerManifest,
 [string]$WorkspaceConfig
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $repo
if ($ExpectedHead -notmatch '^[0-9a-f]{40}$' -or (git rev-parse HEAD).Trim() -ne $ExpectedHead) { throw 'Exact SHA mismatch.' }
$consumer = -not [string]::IsNullOrWhiteSpace($ConsumerManifest)
function Assert-YacsUnrealHostIdle {
 $state = & (Join-Path $repo 'scripts/runner/Get-YacsUnrealHostState.ps1')
 if ($state.status -ne 'IDLE') { throw "Unreal host already owned; status=$($state.status)." }
}
if ($consumer) {
 if (-not [IO.Path]::IsPathRooted($ConsumerManifest) -or -not (Test-Path -LiteralPath $ConsumerManifest -PathType Leaf)) { throw 'Saved-consumer manifest requires an explicit absolute file path.' }
 if (-not [IO.Path]::IsPathRooted($ArtifactRoot) -or (Test-Path -LiteralPath $ArtifactRoot)) { throw 'Saved-consumer performance requires a new absolute evidence directory.' }
 if (-not $WorkspaceConfig) { throw 'Canonical workspace configuration is required.' }
 $workspaceText=python -c 'import json,sys; from pathlib import Path; from scripts.manage_local_workspace import load_workspace; print(json.dumps(load_workspace(Path(sys.argv[1]))))' $WorkspaceConfig
 if ($LASTEXITCODE -ne 0) { throw 'Workspace configuration failed.' }
 $workspace = $workspaceText | ConvertFrom-Json
 if ((Resolve-Path -LiteralPath $workspace.project).Path -eq $repo) { throw 'Never build or measure from the open authoring project.' }
 python scripts/ci/sa_calobra_performance.py verify-consumer --root $ArtifactRoot --head $ExpectedHead --consumer-manifest $ConsumerManifest
 if ($LASTEXITCODE -ne 0) { throw 'Saved/fresh-rendered material consumer admission failed before launch.' }
 New-Item -ItemType Directory -Path $ArtifactRoot | Out-Null
}
. ./scripts/ci/Resolve-YacsUnrealEngine.ps1
$project=Join-Path $repo 'YetAnotherCyclingSim.uproject'
$engine=Resolve-YacsUnrealEngine -ProjectPath $project
if ($null -eq $engine -or -not $engine.UnrealEditorPath) { throw 'Required Unreal Engine editor could not be resolved.' }
$gpu=@(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name })
if (-not ($gpu | Where-Object { $_ -match '(?i)RTX\s*2070.*SUPER' })) { throw 'RTX 2070 SUPER required.' }
$buildRoot=Join-Path $repo 'Saved/RuntimeProof/CI/SaCalobraPerformanceBuild'
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
$buildBat=$engine.BuildBatPath
$buildArgs=@('YetAnotherCyclingSimEditor','Win64','Development',('"'+$project+'"'),'-WaitMutex','-FromMsBuild')
Assert-YacsUnrealHostIdle
$build=Start-Process -FilePath $buildBat -ArgumentList $buildArgs -PassThru -NoNewWindow -Wait -RedirectStandardOutput (Join-Path $buildRoot 'build.log') -RedirectStandardError (Join-Path $buildRoot 'build.stderr.log')
if ($build.ExitCode -ne 0) { Get-Content (Join-Path $buildRoot 'build.log') -Tail 80; throw 'Performance editor build failed.' }
if (-not $consumer) {
 Assert-YacsUnrealHostIdle
 & ./scripts/ue/Invoke-YacsRegionTerrainImport.ps1 -ExpectedBranch HEAD -ExpectedHead $ExpectedHead -ArtifactRoot $ArtifactRoot
 if ($LASTEXITCODE -ne 0) { throw 'Native terrain import failed.' }
}
$root=(Resolve-Path $ArtifactRoot).Path
if ($consumer) {
 python scripts/ci/sa_calobra_performance.py prepare-consumer --root $root --head $ExpectedHead --consumer-manifest $ConsumerManifest
} else {
 python scripts/ci/sa_calobra_performance.py prepare --root $root
}
if ($LASTEXITCODE -ne 0) { throw 'Performance settings preparation failed.' }
$map = if ($consumer) { '/Game/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview' } else { '/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline' }
@{ exact_sha=$ExpectedHead; cpus=@(Get-CimInstance Win32_Processor | ForEach-Object { $_.Name }); gpus=$gpu; consumer=$consumer; source_imported=(-not $consumer) } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $root 'hardware.json') -Encoding utf8
$env:YACS_SA_PERF_CSV=Join-Path $root 'sa-calobra-terrain-performance.csv'
$env:YACS_SA_PERF_SETTINGS=Join-Path $root 'sa-calobra-settings.json'
$arguments=@(('"'+$project+'"'),($map+'?game=/Script/Engine.GameModeBase'),'-game','-windowed','-ResX=1920','-ResY=1080','-ForceRes','-NoVSync','-FixedSeed','-NoSplash','-unattended','-stdout',('-AbsLog="'+(Join-Path $root 'performance.engine.log')+'"'),'-execcmds="Automation RunTests CyclingRuntime.SaCalobraTerrainPerformanceProof;Quit"')
if ($consumer) {
 $arguments += ('-ZenDataPath="'+(Join-Path $workspace.cache 'Zen')+'"')
 $arguments += ('-LocalDataCachePath="'+(Join-Path $workspace.cache 'DerivedDataCache')+'"')
}
Assert-YacsUnrealHostIdle
$proc=Start-Process -FilePath $engine.UnrealEditorPath -ArgumentList $arguments -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $root 'performance.stdout.log') -RedirectStandardError (Join-Path $root 'performance.stderr.log')
$timeoutMs = if ($consumer) { 600000 } else { 300000 }
if (-not $proc.WaitForExit($timeoutMs)) { $proc | Stop-Process -Force; throw 'Performance sampler timed out.' }
if ($consumer) {
 python scripts/ci/sa_calobra_performance.py verify-consumer --root $root --head $ExpectedHead --consumer-manifest $ConsumerManifest
 if ($LASTEXITCODE -ne 0) { throw 'Saved consumer changed during performance; timing is inadmissible.' }
}
python scripts/ci/sa_calobra_performance.py evaluate --root $root --head $ExpectedHead --editor-exit-code $proc.ExitCode
if ($LASTEXITCODE -ne 0) { throw 'Sa Calobra 60 FPS performance gate failed.' }
