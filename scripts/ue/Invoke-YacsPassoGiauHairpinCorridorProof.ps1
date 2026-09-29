<# 
.SYNOPSIS
    Fast R4.1B.2 cyclist-height proof using the persisted Passo Giau map.
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
if (-not $ArtifactRoot) { $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/CI/Stage3GR4_1/HairpinCorridor' }
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) { $ArtifactRoot = Join-Path $RepoRoot $ArtifactRoot }
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$SpikeMapRelative = 'Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap'
$SpikeMapPath = Join-Path $RepoRoot $SpikeMapRelative
$CaptureScript = Join-Path $RepoRoot 'scripts/ue/stage3g_capture_passo_giau_hairpin_corridor.py'
$BuildLog = Join-Path $ArtifactRoot 'build_editor.log'
$CaptureLog = Join-Path $ArtifactRoot 'hairpin_capture.log'
$CaptureStdout = Join-Path $ArtifactRoot 'hairpin_capture.stdout.log'
$CaptureErr = $CaptureLog + '.stderr'
$CapturePng = Join-Path $ArtifactRoot 'passo_giau_sp638_hairpin_corridor_3840x2160.png'
$CaptureProof = Join-Path $ArtifactRoot 'hairpin_capture_proof.json'

foreach ($Path in @($BuildLog,$CaptureLog,$CaptureStdout,$CaptureErr,$CapturePng,$CaptureProof)) {
    Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
}

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) { throw 'Hairpin corridor preflight failed.' }

if (git -C $RepoRoot status --porcelain --untracked-files=all) {
    throw 'Hairpin corridor checkout is dirty before LFS materialization.'
}

Write-Host '[1/4] Materializing only the persisted Passo Giau map...' -ForegroundColor Cyan
git -C $RepoRoot lfs install --local
if ($LASTEXITCODE -ne 0) { throw 'git lfs install failed.' }
git -C $RepoRoot lfs pull --include=$SpikeMapRelative --exclude=''
if ($LASTEXITCODE -ne 0) { throw 'git lfs pull for Passo Giau spike map failed.' }
if (-not (Test-Path -LiteralPath $SpikeMapPath -PathType Leaf)) { throw "Passo Giau map is missing: $SpikeMapPath" }
$MapBytes = (Get-Item -LiteralPath $SpikeMapPath).Length
if ($MapBytes -lt 100000000) { throw "Passo Giau map was not materialized from LFS (bytes=$MapBytes)." }

Write-Host '[2/4] Building exact UE 5.8 editor revision...' -ForegroundColor Cyan
$BuildBat = Join-Path $Context.EngineRoot 'Engine/Build/BatchFiles/Build.bat'
$BuildArgs = @($ProjectPath,'YetAnotherCyclingSimEditor','Win64','Development','-WaitMutex','-FromMsBuild')
$BuildProc = Start-Process -FilePath $BuildBat -ArgumentList $BuildArgs -NoNewWindow -PassThru -RedirectStandardOutput $BuildLog -WorkingDirectory (Split-Path $BuildBat -Parent)
$BuildProc.WaitForExit()
if ($BuildProc.ExitCode -ne 0) { throw "Editor build failed with exit code $($BuildProc.ExitCode). See $BuildLog" }

Write-Host '[3/4] Rendering bounded SP638 hairpin corridor proof...' -ForegroundColor Cyan
$UEditor = $Context.UnrealEditorPath
if (-not $UEditor -or -not (Test-Path -LiteralPath $UEditor)) { throw 'UnrealEditor.exe GUI executable is unavailable.' }
if (-not (Test-Path -LiteralPath $CaptureScript -PathType Leaf)) { throw "Hairpin capture script is missing: $CaptureScript" }

$env:YACS_PASSO_GIAU_HAIRPIN_CAPTURE_PNG = $CapturePng
$env:YACS_PASSO_GIAU_HAIRPIN_CAPTURE_PROOF = $CaptureProof
try {
    $Args = @(
        $ProjectPath,
        ('-ExecutePythonScript="' + $CaptureScript + '"'),
        '-Unattended','-NoPause','-NoSplash','-NoP4',
        '-windowed','-ResX=1920','-ResY=1080','-NoVSync','-FixedSeed',
        '-ScriptErrorsAreFatal','-log','-stdout',('-AbsLog=' + $CaptureLog)
    )
    $Proc = Start-Process -FilePath $UEditor -ArgumentList $Args -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $CaptureStdout -RedirectStandardError $CaptureErr
    if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
        try { $Proc | Stop-Process -Force } catch { }
        throw 'Hairpin corridor visual capture timed out.'
    }
    $CaptureExitCode = $Proc.ExitCode
}
finally {
    Remove-Item Env:YACS_PASSO_GIAU_HAIRPIN_CAPTURE_PNG -ErrorAction SilentlyContinue
    Remove-Item Env:YACS_PASSO_GIAU_HAIRPIN_CAPTURE_PROOF -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $CapturePng -PathType Leaf)) { throw "Hairpin corridor PNG is missing (exit=$CaptureExitCode)." }
if ((Get-Item -LiteralPath $CapturePng).Length -lt 100000) { throw 'Hairpin corridor PNG is unexpectedly small.' }
if (-not (Test-Path -LiteralPath $CaptureProof -PathType Leaf)) { throw "Hairpin corridor proof JSON is missing (exit=$CaptureExitCode)." }

$Proof = Get-Content -LiteralPath $CaptureProof -Raw | ConvertFrom-Json
if ($Proof.passo_giau_hairpin_corridor_capture -ne 'PASS') { throw 'Hairpin corridor proof did not report PASS.' }
if ([int]$Proof.resolution[0] -ne 3840 -or [int]$Proof.resolution[1] -ne 2160) { throw 'Hairpin corridor proof resolution is invalid.' }
if ([double]$Proof.slice_length_m -lt 500.0 -or [double]$Proof.slice_length_m -gt 900.0) { throw 'Hairpin corridor slice length is outside the bounded proof contract.' }
if ([double]$Proof.curvature_score -le 0.0) { throw 'Hairpin corridor proof did not select a curved segment.' }
if ($Proof.landscape_cut_fill.api -ne 'LandscapeProxy.editor_apply_spline') { throw 'Hairpin corridor proof did not use the intended Landscape spline deformation API.' }
if ([bool]$Proof.landscape_cut_fill.raise_heights -ne $true -or [bool]$Proof.landscape_cut_fill.lower_heights -ne $true) { throw 'Hairpin corridor proof did not perform bounded raise/lower cut-fill.' }
if ([bool]$Proof.landscape_cut_fill.saved_to_map -ne $false) { throw 'Hairpin corridor proof unexpectedly claims persistent Landscape mutation.' }
if ([int]$Proof.proof_mesh.road_segments -lt 50 -or [int]$Proof.proof_mesh.shoulder_segments -lt 50) { throw 'Hairpin corridor proof mesh is unexpectedly sparse.' }

$CaptureLogText = Get-Content -LiteralPath $CaptureLog -Raw -ErrorAction Stop
if ($CaptureExitCode -notin @(0,1)) { throw "Hairpin corridor capture returned unexpected exit code $CaptureExitCode." }
if ($CaptureLogText -match '(?i)Fatal error|Unhandled Exception|Critical error') { throw 'Hairpin corridor capture log contains a crash/fatal marker.' }
if ($CaptureLogText -notmatch '\[PassoGiauHairpinCorridor\] PASS:') { throw 'Hairpin corridor capture log is missing the explicit PASS marker.' }

Write-Host '[4/4] Enforcing non-persistent spike contract...' -ForegroundColor Cyan
$TrackedChanges = @(git -C $RepoRoot status --porcelain=v1 --untracked-files=no)
if ($TrackedChanges.Count -gt 0) {
    throw ("Hairpin corridor proof mutated tracked files: {0}" -f ($TrackedChanges -join '; '))
}

Write-Host 'Passo Giau R4.1B.2 hairpin corridor proof: PASS.' -ForegroundColor Green
Write-Host ("Rendered proof: {0}" -f $CapturePng)
exit 0
