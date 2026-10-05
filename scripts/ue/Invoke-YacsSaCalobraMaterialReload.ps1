<# Read saved candidate data in an isolated checkout; no rendering or build. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ExpectedHead,
    [Parameter(Mandatory=$true)][string]$ArtifactRoot,
    [Parameter(Mandatory=$true)][string]$WorkspaceConfig,
    [int]$TimeoutSec=300
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if ($ExpectedHead -notmatch '^[0-9a-f]{40}$' -or (git -C $repo rev-parse HEAD).Trim() -ne $ExpectedHead) { throw 'Exact SHA mismatch.' }
Push-Location $repo
try {
    $configText=python -c 'import json,sys; from pathlib import Path; from scripts.manage_local_workspace import load_workspace; print(json.dumps(load_workspace(Path(sys.argv[1]))))' $WorkspaceConfig
    if ($LASTEXITCODE -ne 0) { throw 'Workspace configuration failed.' }
    $config=$configText | ConvertFrom-Json
} finally { Pop-Location }
if ($repo -eq $config.project) { throw 'Fresh verification cannot use the open authoring checkout.' }
if ($TimeoutSec -lt 30 -or $TimeoutSec -gt 900) { throw 'Reload timeout must be 30 through 900 seconds.' }
if (-not [IO.Path]::IsPathRooted($ArtifactRoot)) { throw 'Use an absolute evidence directory.' }
if (Test-Path -LiteralPath $ArtifactRoot) { throw 'Existing reload evidence must be preserved.' }
$editor=Join-Path $config.engine 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
if (-not (Test-Path -LiteralPath $editor)) { throw 'Configured editor commandlet is missing.' }
# Verified reusable modules must be prepared independently under compile-reuse policy.
foreach ($module in @('UnrealEditor-YetAnotherCyclingSim.dll','UnrealEditor-YetAnotherCyclingSimEditor.dll')) {
    if (-not (Test-Path -LiteralPath (Join-Path $repo ('Binaries/Win64/'+$module)))) { throw ('Missing prepared module: '+$module) }
}
# Asset registry scans the complete mounted Content tree, not just map dependencies.
foreach ($asset in (Get-ChildItem -LiteralPath (Join-Path $repo 'Content') -Recurse -File | Where-Object { $_.Extension -in @('.uasset','.umap') })) {
    $stream=[IO.File]::OpenRead($asset.FullName)
    try {
        $prefix=New-Object byte[] 42
        $read=$stream.Read($prefix,0,42)
        if ([Text.Encoding]::ASCII.GetString($prefix,0,$read).StartsWith('version https://git-lfs.github.com/spec/v1')) { throw ('Unhydrated Unreal asset: '+$asset.FullName) }
    } finally { $stream.Dispose() }
}
New-Item -ItemType Directory -Path $ArtifactRoot | Out-Null
$root=(Resolve-Path -LiteralPath $ArtifactRoot).Path
$names=@('YACS_WORKSPACE_CONFIG','YACS_2B_EXPECTED_HEAD','YACS_2B_RELOAD_REPORT')
$previous=@{}
foreach ($name in $names) { $previous[$name]=[Environment]::GetEnvironmentVariable($name,'Process') }
try {
    $env:YACS_WORKSPACE_CONFIG=$config.config
    $env:YACS_2B_EXPECTED_HEAD=$ExpectedHead
    $env:YACS_2B_RELOAD_REPORT=Join-Path $root 'consumer-proof.json'
    $zen=Join-Path $config.cache 'Zen'
    $localCache=Join-Path $config.cache 'DerivedDataCache'
    $arguments=@(('"'+(Join-Path $repo 'YetAnotherCyclingSim.uproject')+'"'),'-run=pythonscript',('-script="'+(Join-Path $PSScriptRoot 'verify_saved_sa_calobra_material_foundation.py')+'"'),'-Unattended','-NoPause','-NullRHI','-NoSplash','-NoP4','-ScriptErrorsAreFatal',('-ZenDataPath="'+$zen+'"'),('-LocalDataCachePath="'+$localCache+'"'),('-AbsLog="'+(Join-Path $root 'reload.engine.log')+'"'))
    $process=Start-Process -FilePath $editor -ArgumentList $arguments -WorkingDirectory $repo -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root 'reload.stdout.log') -RedirectStandardError (Join-Path $root 'reload.stderr.log')
    $deadline=[DateTime]::UtcNow.AddSeconds($TimeoutSec)
    while (-not $process.WaitForExit(20000)) {
        if ([DateTime]::UtcNow -gt $deadline) { Stop-Process -Id $process.Id; throw 'Isolated saved-consumer verification timed out.' }
    }
    @{exact_sha=$ExpectedHead;exit_code=$process.ExitCode;pid=$process.Id;zen_data_path=$zen;rendered=$false;performance_measured=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'process-result.json') -Encoding utf8
    if ($process.ExitCode -ne 0) { throw ('Saved-consumer process failed with exit '+$process.ExitCode+'; inspect reload.engine.log.') }
    if (-not (Test-Path -LiteralPath $env:YACS_2B_RELOAD_REPORT)) { throw 'Successful process produced no saved-consumer proof.' }
    $proof=Get-Content -LiteralPath $env:YACS_2B_RELOAD_REPORT -Raw | ConvertFrom-Json
    if ($proof.exact_sha -ne $ExpectedHead -or -not $proof.fresh_material_load -or $proof.component_roots_verified -ne 1024 -or -not $proof.scene_snapshot_equal -or $proof.map_saved) { throw 'Saved-consumer proof contract differs.' }
    Write-Output 'Fresh saved data consumer verified; rendering and performance remain unproven.'
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') }
}
