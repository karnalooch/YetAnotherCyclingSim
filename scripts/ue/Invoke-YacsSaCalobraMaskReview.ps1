<# Run the fixed diagnostic consumer on an existing map; no build/import/save. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ReviewRoot,
    [Parameter(Mandatory=$true)][string]$ProjectPath,
    [Parameter(Mandatory=$true)][string]$ExpectedHead,
    [switch]$KeepOpen
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$repo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
if ($ExpectedHead -notmatch '^[0-9a-f]{40}$' -or (git -C $repo rev-parse HEAD).Trim() -ne $ExpectedHead) { throw 'Exact script commit mismatch.' }
if (git -C $repo status --porcelain) { throw 'Review script checkout must be clean.' }
$ReviewRoot=(Resolve-Path -LiteralPath $ReviewRoot).Path
$ProjectPath=(Resolve-Path -LiteralPath $ProjectPath).Path
$projectRoot=Split-Path $ProjectPath -Parent
if (Test-Path -LiteralPath (Join-Path $ReviewRoot 'unreal-review-proof.json')) { throw 'Existing proof must be preserved.' }
$map=Join-Path $projectRoot 'Content/Worlds/SaCalobra/L_SaCalobraTerrainBaseline.umap'
if (-not (Test-Path -LiteralPath $map)) { throw 'Existing frozen map missing; do not generate or import it.' }
. (Join-Path $repo 'scripts/ci/Resolve-YacsUnrealEngine.ps1')
$engine=Resolve-YacsUnrealEngine -ProjectPath $ProjectPath
$version=Get-Content -LiteralPath (Join-Path $engine.Root 'Engine/Build/Build.version') -Raw | ConvertFrom-Json
if ($version.MajorVersion -ne 5 -or $version.MinorVersion -ne 8 -or $version.PatchVersion -ne 2) { throw 'Reviewed engine version must be 5.8.2.' }
$env:YACS_MASK_REVIEW_ROOT=$ReviewRoot
$env:YACS_MASK_REVIEW_SHA=$ExpectedHead
$env:YACS_MASK_COMPILED_PROJECT_SHA=(git -C $projectRoot rev-parse HEAD).Trim()
$env:YACS_MASK_REVIEW_KEEP_OPEN=if ($KeepOpen) {'1'} else {'0'}
try {
    $script=Join-Path $PSScriptRoot 'sa_calobra_mask_review.py'
    $arguments=@(('"'+$ProjectPath+'"'),('-ExecutePythonScript="'+$script+'"'),'-NoP4','-NoSplash','-windowed','-ResX=1920','-ResY=1080',('-AbsLog="'+$ReviewRoot+'\review.engine.log"'))
    # This visible session is the explicitly requested interactive mask review.
    $process=Start-Process -FilePath $engine.UnrealEditorPath -ArgumentList $arguments -PassThru
    @{script_commit=$ExpectedHead;compiled_project_commit=$env:YACS_MASK_COMPILED_PROJECT_SHA;process_id=$process.Id;map_sha256_before=(Get-FileHash -LiteralPath $map -Algorithm SHA256).Hash.ToLowerInvariant();existing_map_only=$true;build_executed=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $ReviewRoot 'launch-receipt.json') -Encoding utf8
    Write-Output "Review Editor PID $($process.Id); inspect unreal-review-proof.json for completion."
} finally {
    Remove-Item Env:YACS_MASK_REVIEW_ROOT,Env:YACS_MASK_REVIEW_SHA,Env:YACS_MASK_COMPILED_PROJECT_SHA,Env:YACS_MASK_REVIEW_KEEP_OPEN
}
