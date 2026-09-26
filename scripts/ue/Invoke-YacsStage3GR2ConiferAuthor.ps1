<#
.SYNOPSIS
    Author and validate the accepted Stage 3G R2 mass-forest conifer.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [string] $ExpectedBranch = 'HEAD',
    [int] $TimeoutSec = 2400
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) {
    $ProjectPath = Join-Path -Path $RepoRoot -ChildPath 'YetAnotherCyclingSim.uproject'
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath 'Saved/RuntimeProof/CI/Stage3GR2/ConiferAuthor'
}
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath $ArtifactRoot
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$Preflight = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) { throw 'Stage 3G R2 conifer authoring preflight failed.' }

$DownloadScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/assets/download_stage3g_assets.py'
$AuthorScript = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/stage3g_author_conifer.py'
$AssetCache = Join-Path -Path $RepoRoot -ChildPath 'ExternalAssets/Stage3G/PolyHaven'
$ProofJson = Join-Path -Path $ArtifactRoot -ChildPath 'conifer_authoring_proof.json'
$AuthorLog = Join-Path -Path $ArtifactRoot -ChildPath 'conifer_authoring.log'
$ErrLog = $AuthorLog + '.stderr'
$ZenDataPath = Join-Path -Path $ArtifactRoot -ChildPath 'ZenData'
New-Item -ItemType Directory -Path $ZenDataPath -Force | Out-Null

& python $DownloadScript --destination $AssetCache --asset fir_sapling_medium --max-total-mib 1536
if ($LASTEXITCODE -ne 0) { throw 'Fir Sapling Medium download failed.' }

Remove-Item -LiteralPath $ProofJson -Force -ErrorAction SilentlyContinue
$env:YACS_STAGE3G_ASSET_CACHE = $AssetCache
$env:YACS_STAGE3G_CONIFER_PROOF = $ProofJson
try {
    $Arguments = @(
        $ProjectPath
        ('-ExecutePythonScript="' + $AuthorScript + '"')
        '-Unattended'
        '-NoPause'
        '-NullRHI'
        '-ddc=noshared'
        ('-ZenDataPath="' + $ZenDataPath + '"')
        '-NoSplash'
        '-NoP4'
        '-log'
    )
    $Proc = Start-Process -FilePath $Context.UnrealEditorCmdPath -ArgumentList $Arguments -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $AuthorLog -RedirectStandardError $ErrLog
    if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
        try { $Proc | Stop-Process -Force } catch { }
        throw "Stage 3G R2 conifer authoring timed out; see $AuthorLog"
    }
    if ($Proc.ExitCode -ne 0) {
        throw "Stage 3G R2 conifer authoring failed with exit code $($Proc.ExitCode); see $AuthorLog"
    }
}
finally {
    Remove-Item Env:YACS_STAGE3G_ASSET_CACHE -ErrorAction SilentlyContinue
    Remove-Item Env:YACS_STAGE3G_CONIFER_PROOF -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $ProofJson -PathType Leaf)) {
    throw 'Conifer authoring proof JSON is missing.'
}
$Proof = Get-Content -LiteralPath $ProofJson -Raw | ConvertFrom-Json
if ($Proof.stage3g_r2_conifer_authoring -ne 'success') {
    throw 'Conifer authoring proof did not report success.'
}
if ($Proof.profile -ne 'aggressive') {
    throw "Unexpected conifer LOD profile: $($Proof.profile)"
}
$ExpectedTriangles = @(420822, 75748, 21042, 5260)
$ActualTriangles = @($Proof.lods | ForEach-Object { [int]$_.triangles })
if (($ActualTriangles -join ',') -ne ($ExpectedTriangles -join ',')) {
    throw "Unexpected conifer LOD triangle chain: $($ActualTriangles -join ',')"
}

$Required = @(
    'Content/Prototype/Environment/Stage3G/Imported/Meshes/SM_Stage3G_FirSaplingMedium.uasset'
    'Content/Prototype/Environment/Stage3G/Materials/M_Stage3G_FirBranches.uasset'
    'Content/Prototype/Environment/Stage3G/Materials/MI_Stage3G_FirBranches.uasset'
    'Content/Prototype/Environment/Stage3G/Materials/M_Stage3G_FirTwigs.uasset'
    'Content/Prototype/Environment/Stage3G/Materials/MI_Stage3G_FirTwigs.uasset'
)
foreach ($Path in $Required) {
    if (-not (Test-Path -LiteralPath (Join-Path -Path $RepoRoot -ChildPath $Path) -PathType Leaf)) {
        throw "Required Stage 3G R2 conifer output is missing: $Path"
    }
}

Push-Location -LiteralPath $RepoRoot
try {
    $Dirty = @(git status --porcelain=v1 --untracked-files=all)
}
finally {
    Pop-Location
}
$AllowedPrefix = 'Content/Prototype/Environment/Stage3G/'
$Unexpected = @(
    $Dirty | Where-Object {
        if (-not $_ -or $_.Length -lt 4) { return $false }
        $Path = $_.Substring(3).Trim()
        return -not $Path.StartsWith($AllowedPrefix)
    }
)
if ($Unexpected.Count -gt 0) {
    throw ("Conifer authoring changed unexpected paths: {0}" -f ($Unexpected -join '; '))
}

Write-Host 'STAGE3G R2 CONIFER AUTHORING OK.' -ForegroundColor Green
exit 0
