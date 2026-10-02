<# Exact-SHA native Sa Calobra terrain baseline; shares the existing timing policy. #>
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$ExpectedHead,
 [Parameter(Mandatory=$true)][string]$ArtifactRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location $repo
if ($ExpectedHead -notmatch '^[0-9a-f]{40}$' -or (git rev-parse HEAD).Trim() -ne $ExpectedHead) { throw 'Exact SHA mismatch.' }
. ./scripts/ci/Resolve-YacsUnrealEngine.ps1
$project=Join-Path $repo 'YetAnotherCyclingSim.uproject'
$engine=Resolve-YacsUnrealEngine -ProjectPath $project
$gpu=@(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name })
if (-not ($gpu | Where-Object { $_ -match '(?i)RTX\s*2070.*SUPER' })) { throw 'RTX 2070 SUPER required.' }
$buildRoot=Join-Path $repo 'Saved/RuntimeProof/CI/SaCalobraPerformanceBuild'
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
$buildBat=Join-Path $engine.EngineRoot 'Engine/Build/BatchFiles/Build.bat'
$buildArgs=@('YetAnotherCyclingSimEditor','Win64','Development',('"'+$project+'"'),'-WaitMutex','-FromMsBuild')
$build=Start-Process -FilePath $buildBat -ArgumentList $buildArgs -PassThru -NoNewWindow -Wait -RedirectStandardOutput (Join-Path $buildRoot 'build.log') -RedirectStandardError (Join-Path $buildRoot 'build.stderr.log')
if ($build.ExitCode -ne 0) { Get-Content (Join-Path $buildRoot 'build.log') -Tail 80; throw 'Performance editor build failed.' }
& ./scripts/ue/Invoke-YacsRegionTerrainImport.ps1 -ExpectedBranch HEAD -ExpectedHead $ExpectedHead -ArtifactRoot $ArtifactRoot
if ($LASTEXITCODE -ne 0) { throw 'Native terrain import failed.' }
$root=(Resolve-Path $ArtifactRoot).Path
python scripts/ci/sa_calobra_performance.py prepare --root $root
if ($LASTEXITCODE -ne 0) { throw 'Performance settings preparation failed.' }
$env:YACS_SA_PERF_CSV=Join-Path $root 'sa-calobra-terrain-performance.csv'
$env:YACS_SA_PERF_SETTINGS=Join-Path $root 'sa-calobra-settings.json'
$arguments=@(('"'+$project+'"'),'/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline?game=/Script/Engine.GameModeBase','-game','-windowed','-ResX=1920','-ResY=1080','-ForceRes','-NoVSync','-FixedSeed','-NoSplash','-unattended','-stdout',('-AbsLog="'+(Join-Path $root 'performance.engine.log')+'"'),'-execcmds="Automation RunTests CyclingRuntime.SaCalobraTerrainPerformanceProof;Quit"')
$proc=Start-Process -FilePath $engine.UnrealEditorPath -ArgumentList $arguments -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $root 'performance.stdout.log') -RedirectStandardError (Join-Path $root 'performance.stderr.log')
if (-not $proc.WaitForExit(300000)) { $proc | Stop-Process -Force; throw 'Performance sampler timed out.' }
python scripts/ci/sa_calobra_performance.py evaluate --root $root --head $ExpectedHead --editor-exit-code $proc.ExitCode
if ($LASTEXITCODE -ne 0) { throw 'Sa Calobra 60 FPS performance gate failed.' }
