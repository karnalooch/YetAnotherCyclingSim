<#
.SYNOPSIS
    Exact-SHA UE 5.8 Geometry Script / Dynamic Mesh capability probe for R4.1B.3.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [string] $PreparedWorkspaceStamp,
    [int] $TimeoutSec = 600
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) { $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject' }
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) { $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/CI/Stage3GR4_1/GeometryScriptProbe' }
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) { $ArtifactRoot = Join-Path $RepoRoot $ArtifactRoot }
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$ProbeScript = Join-Path $RepoRoot 'scripts/ue/probe_geometry_script_api.py'
$BuildLog = Join-Path $ArtifactRoot 'build_editor.log'
$ProbeLog = Join-Path $ArtifactRoot 'geometry_script_probe.log'
$ProbeStdout = Join-Path $ArtifactRoot 'geometry_script_probe.stdout.log'
$ProbeErr = $ProbeLog + '.stderr'
$ProbeJson = Join-Path $ArtifactRoot 'geometry_script_probe.json'

foreach ($Path in @($BuildLog,$ProbeLog,$ProbeStdout,$ProbeErr,$ProbeJson)) {
    Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
}

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead
if ($LASTEXITCODE -ne 0) { throw 'Geometry Script probe preflight failed.' }

if (git -C $RepoRoot status --porcelain --untracked-files=all) {
    throw 'Geometry Script probe checkout is dirty before build.'
}

$PreparedValidator = Join-Path $RepoRoot 'scripts/ue/Test-YacsR4_1PreparedWorkspace.ps1'
if ($PreparedWorkspaceStamp) {
    & $PreparedValidator -StampPath $PreparedWorkspaceStamp -RepoRoot $RepoRoot -ExpectedHead $ExpectedHead -RequireBuild | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Prepared R4.1 workspace validation failed before Geometry Script probe.' }
    Write-Host '[1/3] Reusing exact-SHA editor build from prepared R4.1 workspace.' -ForegroundColor Cyan
}
else {
    Write-Host '[1/3] Building exact UE 5.8 editor revision...' -ForegroundColor Cyan
    $BuildBat = Join-Path $Context.EngineRoot 'Engine/Build/BatchFiles/Build.bat'
    $BuildArgs = @($ProjectPath,'YetAnotherCyclingSimEditor','Win64','Development','-WaitMutex','-FromMsBuild')
    $BuildProc = Start-Process -FilePath $BuildBat -ArgumentList $BuildArgs -NoNewWindow -PassThru -RedirectStandardOutput $BuildLog -WorkingDirectory (Split-Path $BuildBat -Parent)
    $BuildProc.WaitForExit()
    if ($BuildProc.ExitCode -ne 0) { throw "Editor build failed with exit code $($BuildProc.ExitCode). See $BuildLog" }
}

Write-Host '[2/3] Probing Geometry Script / Dynamic Mesh Python API...' -ForegroundColor Cyan
$UEditor = $Context.UnrealEditorPath
if (-not $UEditor -or -not (Test-Path -LiteralPath $UEditor)) { throw 'UnrealEditor.exe GUI executable is unavailable.' }
if (-not (Test-Path -LiteralPath $ProbeScript -PathType Leaf)) { throw "Probe script is missing: $ProbeScript" }

$env:YACS_GEOMETRY_SCRIPT_PROBE_JSON = $ProbeJson
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
        throw 'Geometry Script capability probe timed out.'
    }
    $ProbeExitCode = $Proc.ExitCode
}
finally {
    Remove-Item Env:YACS_GEOMETRY_SCRIPT_PROBE_JSON -ErrorAction SilentlyContinue
}

if ($ProbeExitCode -notin @(0,1)) { throw "Geometry Script probe returned unexpected exit code $ProbeExitCode." }
if (-not (Test-Path -LiteralPath $ProbeJson -PathType Leaf)) { throw 'Geometry Script probe JSON is missing.' }

$Proof = Get-Content -LiteralPath $ProbeJson -Raw | ConvertFrom-Json
if ($Proof.geometry_script_probe -ne 'PASS') { throw 'Geometry Script probe did not report PASS.' }
if ([bool]$Proof.read_only -ne $true -or [bool]$Proof.map_loaded -ne $false) { throw 'Geometry Script probe violated its read-only contract.' }
if (@($Proof.matched_unreal_symbols).Count -lt 1) { throw 'Geometry Script probe found no matching Unreal symbols.' }

$ProbeLogText = Get-Content -LiteralPath $ProbeLog -Raw -ErrorAction Stop
if ($ProbeLogText -match '(?i)Fatal error|Unhandled Exception|Critical error') { throw 'Geometry Script probe log contains a crash/fatal marker.' }
if ($ProbeLogText -notmatch '\[YacsGeometryScriptProbe\] PASS:') { throw 'Geometry Script probe log is missing the explicit PASS marker.' }

Write-Host '[3/3] Enforcing read-only repository contract...' -ForegroundColor Cyan
$TrackedChanges = @(git -C $RepoRoot status --porcelain=v1 --untracked-files=no)
if ($TrackedChanges.Count -gt 0) {
    throw ("Geometry Script probe mutated tracked files: {0}" -f ($TrackedChanges -join '; '))
}

Write-Host 'R4.1B.3 Geometry Script capability probe: PASS.' -ForegroundColor Green
Write-Host ("Capability snapshot: {0}" -f $ProbeJson)
exit 0
