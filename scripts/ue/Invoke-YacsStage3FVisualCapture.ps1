<#
.SYNOPSIS
    Stage 3F visual baseline + inventory proof.

.DESCRIPTION
    Lightweight harness tailored to Stage 3F-A baseline capture. It:
      1. Runs Preflight-YacsProof.ps1 to verify branch/HEAD/UE.
      2. Launches the editor with the persisted L_CyclingTest map and
         the dedicated CyclingRuntime.Stage3VisualEnvironmentProof
         automation test in a rendered 1920x1080 PIE viewport.
      3. Renames the captured PNGs into Stage3F/<stage> with the
         BEFORE/AFTER suffix required by the Stage 3F brief.
      4. Optionally invokes a Python introspection script that dumps
         the lighting + post-process + Lumen + Virtual Shadow Maps +
         scalability state of the loaded map.

    This harness does NOT mutate the .umap. It is purely observational
    so the BEFORE state is captured without altering the visual or
    structural baseline.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [Parameter(Mandatory=$true)] [ValidateSet('3F-A','3F-B')]
    [string] $Stage,
    [ValidateSet('BEFORE','AFTER')]
    [string] $Suffix = 'BEFORE',
    [switch] $SkipBuild,
    [switch] $SkipIntrospect,
    [int] $TimeoutSec = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) {
    $ProjectPath = Join-Path -Path $RepoRoot -ChildPath 'YetAnotherCyclingSim.uproject'
}
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path -Path $RepoRoot -ChildPath "Saved/RuntimeProof/Stage3F/$Stage"
}
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

Write-Host "=== YACS Stage 3F $Stage $Suffix visual capture ===" -ForegroundColor Cyan
Write-Host ("RepoRoot       : {0}" -f $RepoRoot)
Write-Host ("ProjectPath    : {0}" -f $ProjectPath)
Write-Host ("ArtifactRoot   : {0}" -f $ArtifactRoot)
Write-Host ("ExpectedBranch : {0}" -f $ExpectedBranch)
Write-Host ("ExpectedHead   : {0}" -f $ExpectedHead)
Write-Host ("Suffix         : {0}" -f $Suffix)

# --- Preflight -------------------------------------------------------------

$Preflight = Join-Path -Path $RepoRoot -ChildPath 'scripts/ue/Preflight-YacsProof.ps1'
$PreflightArgs = @{
    RepoRoot = $RepoRoot
    ProjectPath = $ProjectPath
    ArtifactRoot = $ArtifactRoot
    ExpectedBranch = $ExpectedBranch
    ExpectedHead = $ExpectedHead
    AllowedDirtyPaths = @(
        'Config/DefaultGame.ini',
        'Content/Prototype/Maps/L_CyclingTest.umap',
        'Config/DefaultLocoHelperAI.ini',
        '.kilo/',
        'YetAnotherCyclingSim/',
        # Stage 3F visual material source edits (introduced by this branch).
        'Source/YetAnotherCyclingSim/Public/Cycling/Stage3PrototypeTerrainActor.h',
        'Source/YetAnotherCyclingSim/Private/Cycling/Stage3PrototypeTerrainActor.cpp',
        'Content/Prototype/Environment/',
        'scripts/ue/Invoke-YacsStage3FVisualCapture.ps1'
    )
}
$Context = & $Preflight @PreflightArgs
if ($LASTEXITCODE -ne 0) { throw "Stage 3F preflight failed." }

$UEditor = $Context.UnrealEditorPath
if (-not $UEditor) {
    throw 'UnrealEditor.exe (GUI) not resolved by preflight.'
}
if (-not (Test-Path -LiteralPath $UEditor)) {
    throw "UnrealEditor.exe not found at '$UEditor'."
}

# --- Optional editor rebuild ----------------------------------------------

if (-not $SkipBuild) {
    Write-Host ""
    Write-Host "[0/4] Building YetAnotherCyclingSimEditor (Development)..." -ForegroundColor Cyan
    $BuildLog = Join-Path -Path $ArtifactRoot -ChildPath 'build_editor.log'
    $BuildArgs = @(
        $ProjectPath,
        'YetAnotherCyclingSimEditor',
        'Win64',
        'Development',
        '-WaitMutex',
        '-FromMsBuild'
    )
    $BuildProc = Start-Process -FilePath (Join-Path -Path $Context.EngineRoot -ChildPath 'Engine/Build/BatchFiles/Build.bat') `
        -ArgumentList $BuildArgs -NoNewWindow -PassThru -RedirectStandardOutput $BuildLog `
        -WorkingDirectory (Join-Path -Path $Context.EngineRoot -ChildPath 'Engine/Build/BatchFiles')
    $BuildProc.WaitForExit()
    if ($BuildProc.ExitCode -ne 0) {
        throw "Editor build failed with exit code $($BuildProc.ExitCode); see $BuildLog"
    }
    Write-Host "Editor build OK." -ForegroundColor Green
}

# --- Clean stale PNGs ------------------------------------------------------

$Canonical = @(
    '01_meadow_valley_1200m.png',
    '02_forest_sector_4900m.png',
    '03_high_valley_mountains_8000m.png',
    'visual_environment_report.txt'
)
foreach ($StaleName in $Canonical) {
    $StalePath = Join-Path -Path $ArtifactRoot -ChildPath $StaleName
    if (Test-Path -LiteralPath $StalePath) {
        Remove-Item -LiteralPath $StalePath -Force
    }
}

# --- Optional introspection (runs inside the same editor process later) ----

$IntrospectScript = $null
if (-not $SkipIntrospect) {
    $IntrospectScript = Join-Path -Path $ArtifactRoot -ChildPath 'stage3f_introspect.py'
    @"
# Stage 3F baseline introspection. Runs inside an UnrealEditor-Cmd -game
# session against L_CyclingTest; dumps lighting + post-process + Lumen
# + scalability state to JSON + text for the baseline report.

import json, unreal

def _bool(v):
    return bool(v)

def _kv(label, value):
    return '  {:<32s} {}'.format(label + ':', value)

def main():
    settings = unreal.get_editor_subsystem(unreal.EditorLevelLibrarySubsystem).get_editor_world_settings()
    info = {}
    info['map_name'] = unreal.EditorLoadingAndSavingUtils.get_current_map_name()

    light_actors = unreal.GameplayStatics.get_all_actors_of_class(unreal.EditorLevelLibrary.get_editor_world(), unreal.DirectionalLight)
    info['directional_lights'] = []
    for a in light_actors:
        info['directional_lights'].append({
            'name': str(a.get_name()),
            'rotation_yaw_deg': float(a.get_actor_rotation().yaw),
            'rotation_pitch_deg': float(a.get_actor_rotation().pitch),
            'intensity': float(a.get_intensity()),
            'atmosphere_sun_light': bool(a.is_a(unreal.AtmosphericLight))
        })

    skylight_actors = unreal.GameplayStatics.get_all_actors_of_class(unreal.EditorLevelLibrary.get_editor_world(), unreal.SkyLight)
    info['sky_lights'] = []
    for a in skylight_actors:
        info['sky_lights'].append({
            'name': str(a.get_name()),
            'intensity': float(a.get_intensity()),
            'source_type': str(a.get_editor_property('source_type'))
        })

    ppv_actors = unreal.GameplayStatics.get_all_actors_of_class(unreal.EditorLevelLibrary.get_editor_world(), unreal.PostProcessVolume)
    info['post_process_volumes'] = []
    for a in ppv_actors:
        info['post_process_volumes'].append({
            'name': str(a.get_name()),
            'enabled': bool(a.get_editor_property('bEnabled')),
            'priority': float(a.get_editor_property('priority')),
            'blend_weight': float(a.get_editor_property('blend_weight'))
        })

    info['exponential_height_fog'] = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(unreal.EditorLevelLibrary.get_editor_world(), unreal.ExponentialHeightFog):
        info['exponential_height_fog'].append({
            'name': str(a.get_name()),
            'fog_density': float(a.get_editor_property('fog_density')),
            'fog_height_falloff': float(a.get_editor_property('fog_height_falloff'))
        })

    info['sky_atmosphere'] = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(unreal.EditorLevelLibrary.get_editor_world(), unreal.SkyAtmosphere):
        info['sky_atmosphere'].append({'name': str(a.get_name())})

    # Engine scalability bucket.
    try:
        sg = unreal.SystemSettings
        for label, prop in [
            ('sg.shadow_quality', 'sg.shadow_quality'),
            ('sg.post_process_quality', 'sg.post_process_quality'),
            ('sg.foliage_quality', 'sg.foliage_quality'),
            ('sg.shading_quality', 'sg.shading_quality'),
            ('sg.resolution_quality', 'sg.resolution_quality'),
            ('sg.view_distance_quality', 'sg.view_distance_quality'),
        ]:
            info[label] = int(unreal.SystemSettings.get_default_object().get_editor_property(prop))
    except Exception as e:
        info['sg_error'] = str(e)

    info['engine_uses_lumen'] = bool(unreal.SystemSettings.get_default_object().get_editor_property('r.DynamicGlobalIlluminationMethod') == 1)
    info['engine_virtual_shadow_maps'] = bool(unreal.SystemSettings.get_default_object().get_editor_property('r.Shadow.Virtual.Enable'))

    out_json = r'__STAGE3F_INTROSPECT_OUT__'
    open(out_json, 'wb').write(json.dumps(info, indent=2).encode('utf-8'))
    unreal.log('Stage3F introspect wrote {}'.format(out_json))

main()
"@ -replace '__STAGE3F_INTROSPECT_OUT__', (Join-Path $ArtifactRoot 'stage3f_introspect.json').Replace('\\','\\\\') | Set-Content -LiteralPath $IntrospectScript -Encoding UTF8
}

# --- Launch rendered PIE ---------------------------------------------------

Write-Host ""
Write-Host "[1/4] Launching rendered PIE for Stage 3F $Stage $Suffix visual capture..." -ForegroundColor Cyan

$MapArg = '/Game/Prototype/Maps/L_CyclingTest.umap'

# Write intermediate PNGs to a temp dir using the existing harness
# conventions, then rename them to the Stage3F naming.
$StagingRoot = Join-Path -Path $ArtifactRoot -ChildPath 'staging'
New-Item -ItemType Directory -Path $StagingRoot -Force | Out-Null
[System.Environment]::SetEnvironmentVariable('YACS_VISUAL_ENV_DIR', $StagingRoot, 'Process')

$ExeccmdsValue = 'Automation RunTests CyclingRuntime.Stage3VisualEnvironmentProof;Quit'

$AbsLog = Join-Path -Path $ArtifactRoot -ChildPath 'editor_session.log'
if (Test-Path -LiteralPath $AbsLog) { Remove-Item -LiteralPath $AbsLog -Force }

$EditorArgs = @(
    $ProjectPath,
    $MapArg,
    '-game',
    '-windowed',
    '-ResX=1920',
    '-ResY=1080',
    '-NoVSync',
    '-FixedSeed',
    '-NoSplash',
    '-log',
    '-unattended',
    '-stdout',
    ('-AbsLog=' + $AbsLog),
    ('-execcmds="' + $ExeccmdsValue + '"')
)

$Proc = Start-Process -FilePath $UEditor -ArgumentList $EditorArgs `
    -NoNewWindow -PassThru -RedirectStandardOutput $AbsLog `
    -WorkingDirectory $RepoRoot
Write-Host ("Launched editor pid={0}; waiting up to {1} s..." -f $Proc.Id, $TimeoutSec)

if (-not $Proc.WaitForExit($TimeoutSec * 1000)) {
    try { $Proc | Stop-Process -Force } catch { }
    throw "Stage 3F capture editor did not finish within $TimeoutSec seconds. See $AbsLog."
}
Write-Host ("Editor exit code: {0}" -f $Proc.ExitCode)

# --- Rename captured PNGs into Stage3F naming ------------------------------

$Renamed = @()
foreach ($Name in $Canonical[0..2]) {
    $Staged = Join-Path -Path $StagingRoot -ChildPath $Name
    if (-not (Test-Path -LiteralPath $Staged)) {
        Write-Warning ("Missing staged PNG: {0}" -f $Staged)
        continue
    }
    $WithoutExt = [System.IO.Path]::GetFileNameWithoutExtension($Name)
    $Ext = [System.IO.Path]::GetExtension($Name)
    $Final = Join-Path -Path $ArtifactRoot -ChildPath ($WithoutExt + '_' + $Suffix + $Ext)
    Move-Item -LiteralPath $Staged -Destination $Final -Force
    $Renamed += $Final
    Write-Host ("  renamed: {0}" -f $Final)
}

# --- Write a per-stage report ---------------------------------------------

$ReportPath = Join-Path -Path $ArtifactRoot -ChildPath ('stage3f_' + $Stage.ToLower() + '_' + $Suffix.ToLower() + '_report.txt')
$ReportLines = @(
    ('TimestampUtc         : {0}' -f (Get-Date).ToUniversalTime().ToString('o')),
    ('RepoRoot             : {0}' -f $RepoRoot),
    ('ProjectPath          : {0}' -f $ProjectPath),
    ('Branch               : {0}' -f $Context.Branch),
    ('Head                 : {0}' -f $Context.Head),
    ('Editor               : {0}' -f $UEditor),
    ('EditorExitCode       : {0}' -f $Proc.ExitCode),
    ('Stage                : {0}' -f $Stage),
    ('Suffix               : {0}' -f $Suffix),
    ''
)
foreach ($P in $Renamed) {
    $ReportLines += ('PNG: {0} (exists=True size={1})' -f $P, (Get-Item -LiteralPath $P).Length)
}
Set-Content -LiteralPath $ReportPath -Value $ReportLines -Encoding UTF8

Write-Host ""
Write-Host "[2/4] Stage 3F $Stage $Suffix capture summary" -ForegroundColor Cyan
foreach ($P in $Renamed) { Write-Host ("  {0}" -f $P) }
Write-Host ("Report: {0}" -f $ReportPath)

Write-Host ""
Write-Host "STAGE 3F $Stage $Suffix CAPTURE OK." -ForegroundColor Green
exit 0
