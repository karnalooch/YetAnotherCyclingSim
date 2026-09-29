<#
.SYNOPSIS
    Run the read-only real-SP638 local corridor topology proof on trusted UE 5.8.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [string] $PreparedWorkspaceStamp,
    [switch] $ValidateOnly,
    [int] $TimeoutSec = 300
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) { $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject' }
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) { $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/CI/Stage3GR4_1/LocalCorridorTopology' }
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) { $ArtifactRoot = Join-Path $RepoRoot $ArtifactRoot }
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$SpikeMapRelative = 'Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap'
$SpikeMapPath = Join-Path $RepoRoot $SpikeMapRelative
$ProbeScript = Join-Path $RepoRoot 'scripts/ue/probe_sp638_local_corridor_topology.py'
$ProbeLog = Join-Path $ArtifactRoot 'sp638_corridor_topology.log'
$ProbeStdout = Join-Path $ArtifactRoot 'sp638_corridor_topology.stdout.log'
$ProbeErr = $ProbeLog + '.stderr'
$ProbeJson = Join-Path $ArtifactRoot 'sp638_corridor_topology.json'

if (-not $ValidateOnly) {
    foreach ($Path in @($ProbeLog,$ProbeStdout,$ProbeErr,$ProbeJson)) {
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    }
}

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) { throw 'SP638 local corridor topology preflight failed.' }

if (git -C $RepoRoot status --porcelain=v1 --untracked-files=no) {
    throw 'SP638 local corridor topology checkout has tracked changes before proof.'
}

if ($ValidateOnly) {
    $ProbeExitCode = 0
    Write-Host '[validate-only] Reusing evidence from the single R4.1 editor session.' -ForegroundColor Cyan
}
else {
    $PreparedValidator = Join-Path $RepoRoot 'scripts/ue/Test-YacsR4_1PreparedWorkspace.ps1'
    if ($PreparedWorkspaceStamp) {
        & $PreparedValidator -StampPath $PreparedWorkspaceStamp -RepoRoot $RepoRoot -ExpectedHead $ExpectedHead -RequireMap | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Prepared R4.1 workspace validation failed before SP638 topology proof.' }
        Write-Host '[1/2] Reusing materialized Passo Giau map from prepared R4.1 workspace.' -ForegroundColor Cyan
    }
    else {
        Write-Host '[1/2] Materializing only the persisted Passo Giau map...' -ForegroundColor Cyan
        git -C $RepoRoot lfs install --local
        if ($LASTEXITCODE -ne 0) { throw 'git lfs install failed.' }
        git -C $RepoRoot lfs pull --include=$SpikeMapRelative --exclude=''
        if ($LASTEXITCODE -ne 0) { throw 'git lfs pull for Passo Giau spike map failed.' }
        if (-not (Test-Path -LiteralPath $SpikeMapPath -PathType Leaf)) {
            throw "Passo Giau map is missing: $SpikeMapPath"
        }
        $MapBytes = (Get-Item -LiteralPath $SpikeMapPath).Length
        if ($MapBytes -lt 100000000) {
            throw "Passo Giau map was not materialized from LFS (bytes=$MapBytes)."
        }
    }
    
    Write-Host '[2/2] Running real-SP638 DynamicMesh topology proof...' -ForegroundColor Cyan
    if (-not (Test-Path -LiteralPath $ProbeScript -PathType Leaf)) {
        throw "Topology probe script is missing: $ProbeScript"
    }
    $UEditor = $Context.UnrealEditorPath
    if (-not $UEditor -or -not (Test-Path -LiteralPath $UEditor)) {
        throw 'UnrealEditor.exe GUI executable is unavailable.'
    }
    
    $env:YACS_SP638_CORRIDOR_TOPOLOGY_JSON = $ProbeJson
    try {
        $Args = @(
            $ProjectPath,
            ('-ExecutePythonScript="' + $ProbeScript + '"'),
            '-Unattended','-NoPause','-NoSplash','-NoP4',
            '-ScriptErrorsAreFatal','-log','-stdout',('-AbsLog=' + $ProbeLog)
        )
        $Proc = Start-Process -FilePath $UEditor -ArgumentList $Args -WorkingDirectory $RepoRoot -NoNewWindow -PassThru -RedirectStandardOutput $ProbeStdout -RedirectStandardError $ProbeErr
        if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
            try { $Proc | Stop-Process -Force } catch { }
            throw 'SP638 local corridor topology probe timed out.'
        }
        $ProbeExitCode = $Proc.ExitCode
    }
    finally {
        Remove-Item Env:YACS_SP638_CORRIDOR_TOPOLOGY_JSON -ErrorAction SilentlyContinue
    }
}

if ($ProbeExitCode -notin @(0,1)) {
    throw "SP638 local corridor topology probe returned unexpected exit code $ProbeExitCode."
}
if (-not (Test-Path -LiteralPath $ProbeJson -PathType Leaf)) {
    throw 'SP638 local corridor topology JSON is missing.'
}

$Proof = Get-Content -LiteralPath $ProbeJson -Raw | ConvertFrom-Json
if ($Proof.sp638_local_corridor_topology -ne 'PASS') {
    throw 'SP638 local corridor topology proof did not report PASS.'
}
if ([bool]$Proof.saved_to_map -ne $false) {
    throw 'SP638 local corridor topology proof violated its no-save contract.'
}
if ([bool]$Proof.authoritative_physics -ne $false) {
    throw 'SP638 local corridor topology proof incorrectly claims physics authority.'
}
if ([int]$Proof.station_count -lt 100) {
    throw "SP638 local corridor topology proof sampled too few stations: $($Proof.station_count)"
}
if ([int]$Proof.triangle_count -lt 1000) {
    throw "SP638 local corridor topology proof generated too few triangles: $($Proof.triangle_count)"
}
if ([double]$Proof.source_geometry_analysis.half_window_m -lt 5.0) {
    throw "SP638 topology proof used a sub-source curvature window: $($Proof.source_geometry_analysis.half_window_m) m"
}
if ([bool]$Proof.source_geometry_analysis.canonical_centerline_xy_modified -ne $false) {
    throw 'SP638 topology proof modified canonical centerline XY.'
}
if ([bool]$Proof.validation.source_scale_curvature_estimation -ne $true) {
    throw 'SP638 topology proof did not confirm source-scale curvature estimation.'
}
if ([double]$Proof.adaptive_inside_offset.minimum_actual_shoulder_width_m -lt 0.25) {
    throw "SP638 topology proof pinched the shoulder below 0.25 m: $($Proof.adaptive_inside_offset.minimum_actual_shoulder_width_m)"
}

if (-not $ValidateOnly) {
    $ProbeLogText = Get-Content -LiteralPath $ProbeLog -Raw -ErrorAction Stop
    if ($ProbeLogText -match '(?i)Fatal error|Unhandled Exception|Critical error') {
        throw 'SP638 local corridor topology log contains a crash/fatal marker.'
    }
    if ($ProbeLogText -notmatch '\[YacsSp638CorridorTopology\] PASS:') {
        throw 'SP638 local corridor topology log is missing the explicit PASS marker.'
    }
}

$TrackedChanges = @(git -C $RepoRoot status --porcelain=v1 --untracked-files=no)
if ($TrackedChanges.Count -gt 0) {
    throw ("SP638 local corridor topology probe mutated tracked files: {0}" -f ($TrackedChanges -join '; '))
}

Write-Host 'R4.1B.3 real-SP638 corridor topology proof: PASS.' -ForegroundColor Green
Write-Host ("Topology snapshot: {0}" -f $ProbeJson)
exit 0
