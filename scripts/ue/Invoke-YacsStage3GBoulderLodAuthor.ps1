<#
.SYNOPSIS
    Deterministically author the accepted Stage 3G Boulder LOD policy.

.DESCRIPTION
    Builds the exact trusted revision, runs the UE 5.8 StaticMeshEditorSubsystem
    LOD authoring script, verifies the resulting proof, and rejects any tracked
    mutation outside SM_Stage3G_Boulder.uasset.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) { $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject' }
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) { $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/Issue80/Stage3G/BoulderLOD' }
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$ScriptPath = Join-Path $RepoRoot 'scripts/ue/stage3g_author_boulder_lods.py'
$ProofPath = Join-Path $ArtifactRoot 'stage3g_boulder_lod_authoring.json'
$BuildLog = Join-Path $ArtifactRoot 'build_editor.log'
$AuthorLog = Join-Path $ArtifactRoot 'boulder_lod_authoring.log'
$AuthorErr = $AuthorLog + '.stderr'
$AllowedTrackedPath = 'Content/Prototype/Environment/Stage3G/Imported/Meshes/SM_Stage3G_Boulder.uasset'

foreach ($Path in @($ProofPath, $BuildLog, $AuthorLog, $AuthorErr)) {
    Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
}

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$PreflightArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $ArtifactRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
}
$Context = & $Preflight @PreflightArgs
if ($LASTEXITCODE -ne 0) { throw 'Boulder LOD authoring preflight failed.' }

& git -C $RepoRoot lfs fsck
if ($LASTEXITCODE -ne 0) { throw 'git lfs fsck failed before Boulder authoring.' }
if (git -C $RepoRoot status --porcelain) { throw 'Boulder authoring checkout is dirty before mutation.' }

Write-Host '[1/3] Building exact editor revision...' -ForegroundColor Cyan
$BuildBat = Join-Path $Context.EngineRoot 'Engine/Build/BatchFiles/Build.bat'
$BuildArgs = @($ProjectPath, 'YetAnotherCyclingSimEditor', 'Win64', 'Development', '-WaitMutex', '-FromMsBuild')
$BuildProc = Start-Process -FilePath $BuildBat -ArgumentList $BuildArgs -NoNewWindow -PassThru -RedirectStandardOutput $BuildLog -WorkingDirectory (Split-Path $BuildBat -Parent)
$BuildProc.WaitForExit()
if ($BuildProc.ExitCode -ne 0) {
    throw "Editor build failed with exit code $($BuildProc.ExitCode). See $BuildLog"
}

Write-Host '[2/3] Applying deterministic Boulder LOD policy...' -ForegroundColor Cyan
$env:YACS_STAGE3G_BOULDER_LOD_PROOF = $ProofPath
try {
    $EditorArgs = @(
        $ProjectPath,
        ('-ExecutePythonScript="' + $ScriptPath + '"'),
        '-Unattended',
        '-NoPause',
        '-NullRHI',
        '-NoSplash',
        '-NoP4',
        '-log',
        ('-AbsLog=' + $AuthorLog)
    )
    $Proc = Start-Process -FilePath $Context.UnrealEditorCmdPath -ArgumentList $EditorArgs -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $AuthorLog -RedirectStandardError $AuthorErr
    if (-not $Proc.WaitForExit(180000)) {
        try { $Proc | Stop-Process -Force } catch { }
        throw 'Boulder LOD authoring timed out.'
    }
    if ($Proc.ExitCode -ne 0) {
        throw "Boulder LOD authoring failed with exit code $($Proc.ExitCode)."
    }
}
finally {
    Remove-Item Env:YACS_STAGE3G_BOULDER_LOD_PROOF -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $ProofPath -PathType Leaf)) {
    throw 'Boulder LOD authoring proof was not produced.'
}
$Proof = Get-Content -LiteralPath $ProofPath -Raw | ConvertFrom-Json
if ($Proof.stage3g_boulder_lod_authoring -ne 'PASS') {
    throw 'Boulder LOD authoring proof did not report PASS.'
}
if ([int]$Proof.after_lod_count -ne 4) {
    throw "Expected 4 Boulder LODs, got $($Proof.after_lod_count)."
}

Write-Host '[3/3] Enforcing mutation guard...' -ForegroundColor Cyan
$TrackedChanges = @(
    git -C $RepoRoot diff --name-only --diff-filter=ACMRTUXB |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ }
)
$Unexpected = @($TrackedChanges | Where-Object { $_ -ne $AllowedTrackedPath })
if ($Unexpected.Count -gt 0) {
    throw ("Unexpected tracked mutations: {0}" -f ($Unexpected -join ', '))
}
if ($TrackedChanges -notcontains $AllowedTrackedPath) {
    throw 'Boulder authoring produced no persisted mesh change.'
}

Write-Host ("Boulder LOD authoring PASS. Triangles: {0}" -f (@($Proof.after_triangles) -join ' -> ')) -ForegroundColor Green
Write-Host ("Only tracked mutation: {0}" -f $AllowedTrackedPath)
exit 0
