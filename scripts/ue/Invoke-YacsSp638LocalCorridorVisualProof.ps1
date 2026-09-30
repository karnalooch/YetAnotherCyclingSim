<#
.SYNOPSIS
    Render the R4.1B.3 cyclist-height proof with continuous DynamicMesh local ground.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '../..')).Path,
    [string] $ProjectPath,
    [string] $ArtifactRoot,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [string] $PreparedWorkspaceStamp,
    [string] $PcgExExecutionOutput,
    [string] $NativeDtmPatchMetadata,
    [ValidateSet('A','B','C','D','E','C3')] [string] $Variant = 'E',
    [switch] $ValidateOnly,
    [int] $TimeoutSec = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $ProjectPath) { $ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject' }
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not $ArtifactRoot) { $ArtifactRoot = Join-Path $RepoRoot 'Saved/RuntimeProof/CI/Stage3GR4_1/LocalCorridorVisual' }
if (-not [System.IO.Path]::IsPathRooted($ArtifactRoot)) { $ArtifactRoot = Join-Path $RepoRoot $ArtifactRoot }
New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
$ArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path

$SpikeMapRelative = 'Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap'
$SpikeMapPath = Join-Path $RepoRoot $SpikeMapRelative
$CaptureScript = Join-Path $RepoRoot 'scripts/ue/stage3g_capture_sp638_local_corridor.py'
$VariantLower = $Variant.ToLowerInvariant()
if (-not $NativeDtmPatchMetadata) { $NativeDtmPatchMetadata = Join-Path $RepoRoot 'ExternalAssets/Terrain/PassoGiau/PreparedNearField/passo_giau_native_dtm_patch.json' }
$CaptureLog = Join-Path $ArtifactRoot ("local_corridor_visual_{0}.log" -f $VariantLower)
$CaptureStdout = Join-Path $ArtifactRoot ("local_corridor_visual_{0}.stdout.log" -f $VariantLower)
$CaptureErr = $CaptureLog + '.stderr'
$CapturePng = Join-Path $ArtifactRoot ("sp638_surface_{0}_rider_3840x2160.png" -f $VariantLower)
$CaptureProof = Join-Path $ArtifactRoot ("surface_ownership_{0}_proof.json" -f $VariantLower)

if ($PcgExExecutionOutput) {
    if (-not [System.IO.Path]::IsPathRooted($PcgExExecutionOutput)) {
        $PcgExExecutionOutput = Join-Path $RepoRoot $PcgExExecutionOutput
    }
    if (-not (Test-Path -LiteralPath $PcgExExecutionOutput -PathType Leaf)) {
        throw "PCGEx execution output is missing: $PcgExExecutionOutput"
    }
    $PcgExExecutionOutput = (Resolve-Path -LiteralPath $PcgExExecutionOutput).Path
}

if (-not $ValidateOnly) {
    foreach ($Path in @($CaptureLog,$CaptureStdout,$CaptureErr,$CapturePng,$CaptureProof)) {
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    }
}

$Preflight = Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1'
$AdditionalAllowedDirtyPaths = @()
if ($PcgExExecutionOutput) {
    # The immediately preceding PCGEx authoring step deliberately creates this
    # untracked authoring-only asset. Keep preflight fail-closed for everything
    # else while allowing the known handoff product to coexist with the render.
    $AdditionalAllowedDirtyPaths += 'Content/WorldGen/'
}
$Context = & $Preflight -RepoRoot $RepoRoot -ProjectPath $ProjectPath -ArtifactRoot $ArtifactRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead -AdditionalAllowedDirtyPaths $AdditionalAllowedDirtyPaths
if ($LASTEXITCODE -ne 0) { throw 'SP638 local-corridor visual preflight failed.' }

if (git -C $RepoRoot status --porcelain=v1 --untracked-files=no) {
    throw 'SP638 local-corridor visual checkout has tracked changes before proof.'
}

if ($ValidateOnly) {
    $CaptureExitCode = 0
    Write-Host '[validate-only] Reusing evidence from the single R4.1 editor session.' -ForegroundColor Cyan
}
else {
    $PreparedValidator = Join-Path $RepoRoot 'scripts/ue/Test-YacsR4_1PreparedWorkspace.ps1'
    if ($PreparedWorkspaceStamp) {
        & $PreparedValidator -StampPath $PreparedWorkspaceStamp -RepoRoot $RepoRoot -ExpectedHead $ExpectedHead -RequireMap | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Prepared R4.1 workspace validation failed before local-corridor visual proof.' }
        Write-Host '[1/3] Reusing materialized Passo Giau map from prepared R4.1 workspace.' -ForegroundColor Cyan
    }
    else {
        Write-Host '[1/3] Materializing only the persisted Passo Giau map...' -ForegroundColor Cyan
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
    
    Write-Host '[2/3] Rendering continuous DynamicMesh rider-close proof...' -ForegroundColor Cyan
    $UEditor = $Context.UnrealEditorPath
    if (-not $UEditor -or -not (Test-Path -LiteralPath $UEditor)) {
        throw 'UnrealEditor.exe GUI executable is unavailable.'
    }
    if (-not (Test-Path -LiteralPath $CaptureScript -PathType Leaf)) {
        throw "Local corridor visual script is missing: $CaptureScript"
    }
    
    $env:YACS_SP638_LOCAL_CORRIDOR_VISUAL_PNG = $CapturePng
    $env:YACS_SP638_LOCAL_CORRIDOR_VISUAL_PROOF = $CaptureProof
    $env:YACS_SP638_LOCAL_CORRIDOR_VARIANT = $Variant
    if ($Variant -eq 'C3') {
        if (-not (Test-Path -LiteralPath $NativeDtmPatchMetadata -PathType Leaf)) {
            throw "Gate C.3 native DTM patch metadata is missing: $NativeDtmPatchMetadata"
        }
        $NativeDtmPatchMetadata = (Resolve-Path -LiteralPath $NativeDtmPatchMetadata).Path
        $meta = Get-Content -LiteralPath $NativeDtmPatchMetadata -Raw | ConvertFrom-Json
        $binary = Join-Path (Split-Path -Parent $NativeDtmPatchMetadata) ([string]$meta.binary.file)
        if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) {
            throw "Gate C.3 native DTM patch binary is missing: $binary"
        }
        $env:YACS_NATIVE_DTM_PATCH_METADATA = $NativeDtmPatchMetadata
    }
    if ($PcgExExecutionOutput) {
        $env:YACS_PCGEX_CORRIDOR_OUTPUT = $PcgExExecutionOutput
    }
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
            throw 'SP638 local-corridor visual capture timed out.'
        }
        $CaptureExitCode = $Proc.ExitCode
    }
    finally {
        Remove-Item Env:YACS_SP638_LOCAL_CORRIDOR_VISUAL_PNG -ErrorAction SilentlyContinue
        Remove-Item Env:YACS_SP638_LOCAL_CORRIDOR_VISUAL_PROOF -ErrorAction SilentlyContinue
        Remove-Item Env:YACS_SP638_LOCAL_CORRIDOR_VARIANT -ErrorAction SilentlyContinue
        Remove-Item Env:YACS_NATIVE_DTM_PATCH_METADATA -ErrorAction SilentlyContinue
        Remove-Item Env:YACS_PCGEX_CORRIDOR_OUTPUT -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path -LiteralPath $CapturePng -PathType Leaf)) {
    throw "SP638 local-corridor PNG is missing (exit=$CaptureExitCode)."
}
if ((Get-Item -LiteralPath $CapturePng).Length -lt 100000) {
    throw 'SP638 local-corridor PNG is unexpectedly small.'
}
if (-not (Test-Path -LiteralPath $CaptureProof -PathType Leaf)) {
    throw "SP638 local-corridor proof JSON is missing (exit=$CaptureExitCode)."
}

$Proof = Get-Content -LiteralPath $CaptureProof -Raw | ConvertFrom-Json
if ($Proof.sp638_local_corridor_visual -ne 'PASS') {
    throw 'SP638 local-corridor visual proof did not report PASS.'
}
if ([int]$Proof.resolution[0] -ne 3840 -or [int]$Proof.resolution[1] -ne 2160) {
    throw 'SP638 local-corridor proof resolution is invalid.'
}
if ([bool]$Proof.saved_to_map -ne $false -or [bool]$Proof.authoritative_physics -ne $false) {
    throw 'SP638 local-corridor visual proof violated the presentation-only contract.'
}
if ([bool]$Proof.road_xy_snapped_to_terrain_grid -ne $false) {
    throw 'SP638 local-corridor visual proof snapped road XY to terrain.'
}
if ($PcgExExecutionOutput) {
    if ([bool]$Proof.render_centerline.pcgex_presentation_only -ne $true) {
        throw 'PCGEx visual proof did not identify its render centerline as presentation-only.'
    }
    if ([bool]$Proof.render_centerline.canonical_route_authority_preserved -ne $true) {
        throw 'PCGEx visual proof did not preserve canonical route authority.'
    }
    if ([int]$Proof.render_centerline.source_collection_index -ne 0) {
        throw 'PCGEx visual proof used an unexpected centerline dataset.'
    }
}
if ([string]$Proof.diagnostic_variant -ne $Variant) {
    throw "SP638 diagnostic proof variant mismatch: expected $Variant got $($Proof.diagnostic_variant)."
}
if ([string]$Proof.landscape_cut_fill.selected_earthworks_layer -ne 'Road_Earthworks') {
    throw 'SP638 diagnostic proof did not select Road_Earthworks explicitly.'
}
$AvailableLayers = @($Proof.landscape_cut_fill.available_edit_layers)
if ($AvailableLayers -notcontains 'Base_DTM' -or $AvailableLayers -notcontains 'Road_Earthworks') {
    throw "SP638 diagnostic proof is missing required edit layers: $($AvailableLayers -join ', ')."
}
if ([bool]$Proof.spatial_grid_guardrail.canonical_road_xy_preserved -ne $true) {
    throw 'SP638 local-corridor proof did not preserve canonical road XY.'
}
if ([bool]$Proof.spatial_grid_guardrail.snapped_to_landscape_vertices -ne $false) {
    throw 'SP638 local-corridor proof snapped to Landscape vertices.'
}
if ([double]$Proof.source_geometry_analysis.half_window_m -lt 5.0) {
    throw "SP638 visual proof used a sub-source geometry window: $($Proof.source_geometry_analysis.half_window_m) m"
}
if ([bool]$Proof.source_geometry_analysis.canonical_centerline_xy_modified -ne $false) {
    throw 'SP638 visual proof modified canonical centerline XY.'
}
if ([string]$Proof.proof_viewmode -ne 'lit') {
    throw "SP638 visual proof must use lit acceptance mode, got '$($Proof.proof_viewmode)'."
}
if ([bool]$Proof.neutral_landscape_material -ne $true) {
    throw 'SP638 visual proof did not apply the required neutral Landscape proof material.'
}

if ($Variant -eq 'C3') {
    $ExpectedMacro = $false
    $ExpectedLocal = $true
    $ExpectedCorridor = $false
    $ExpectedCutFill = $false
} else {
    $ExpectedMacro = $Variant -in @('A','B','E')
    $ExpectedLocal = $Variant -in @('C','D','E')
    $ExpectedCorridor = $Variant -in @('B','D','E')
    $ExpectedCutFill = $Variant -ne 'A'
}

if ([bool]$Proof.surface_visibility.macro_landscape -ne $ExpectedMacro) {
    throw "Variant $Variant macro Landscape visibility mismatch."
}
if ([bool]$Proof.surface_visibility.local_terrain -ne $ExpectedLocal) {
    throw "Variant $Variant local terrain visibility mismatch."
}
if ([bool]$Proof.surface_visibility.corridor -ne $ExpectedCorridor) {
    throw "Variant $Variant corridor visibility mismatch."
}
if ([bool]$Proof.landscape_cut_fill.applied -ne $ExpectedCutFill) {
    throw "Variant $Variant Landscape cut/fill state mismatch."
}
if ([bool]$Proof.local_terrain_skin.macro_landscape_visible -ne $ExpectedMacro) {
    throw "Variant $Variant proof recorded the wrong macro Landscape state."
}

if ($ExpectedLocal) {
    if ([bool]$Proof.local_terrain_skin.enabled -ne $true) {
        throw "Variant $Variant did not sample the required local terrain."
    }
    if ([bool]$Proof.local_geometry.terrain_skin.spawned -ne $true) {
        throw "Variant $Variant did not spawn the required local terrain mesh."
    }
    if ([bool]$Proof.local_terrain_skin.world_aligned -ne $true) {
        throw "Variant $Variant terrain skin is not world-aligned."
    }
    if ([bool]$Proof.local_terrain_skin.canonical_road_xy_modified -ne $false) {
        throw "Variant $Variant terrain skin modified canonical road XY."
    }
    if ($Variant -eq 'C3') {
        if ([bool]$Proof.local_terrain_skin.native_metric_dtm -ne $true) {
            throw 'Gate C.3 did not use the native metric DTM.'
        }
        if ([bool]$Proof.local_terrain_skin.landscape_collision_sampled -ne $false) {
            throw 'Gate C.3 unexpectedly sampled Landscape collision.'
        }
        if ([bool]$Proof.local_terrain_skin.smoothing_applied -ne $false) {
            throw 'Gate C.3 unexpectedly smoothed the native DTM patch.'
        }
        if ([string]$Proof.local_terrain_skin.source -ne 'prepared native metric DTM bounded patch') {
            throw "Gate C.3 source drifted: $($Proof.local_terrain_skin.source)"
        }
        if ([double]$Proof.local_terrain_skin.grid_step_m -gt 1.01) {
            throw "Gate C.3 native grid is too coarse: $($Proof.local_terrain_skin.grid_step_m) m"
        }
        if ([int]$Proof.local_terrain_skin.sample_count -lt 250000) {
            throw "Gate C.3 native patch sampled too few points: $($Proof.local_terrain_skin.sample_count)"
        }
        if ([double]$Proof.local_terrain_skin.proof_focus_margin_m -lt 100.0) {
            throw "Gate C.3 patch is not centered on the rendered hairpin: margin=$($Proof.local_terrain_skin.proof_focus_margin_m) m"
        }
        if ([int]$Proof.local_geometry.terrain_skin.triangles -lt 500000) {
            throw "Gate C.3 native terrain mesh is unexpectedly sparse."
        }
    } else {
        if ([double]$Proof.local_terrain_skin.grid_step_m -gt 4.01) {
            throw "Variant $Variant terrain skin grid is too coarse: $($Proof.local_terrain_skin.grid_step_m) m"
        }
        if ([int]$Proof.local_terrain_skin.sample_count -lt 10000) {
            throw "Variant $Variant terrain skin sampled too few points: $($Proof.local_terrain_skin.sample_count)"
        }
        if ([double]$Proof.local_terrain_skin.max_abs_adjustment_m -gt 0.901) {
            throw "Variant $Variant terrain skin exceeded bounded smoothing: $($Proof.local_terrain_skin.max_abs_adjustment_m) m"
        }
        if ([double]$Proof.local_terrain_skin.max_abs_laplacian_after_m -ge [double]$Proof.local_terrain_skin.max_abs_laplacian_before_m) {
            throw "Variant $Variant terrain skin did not reduce high-frequency height curvature."
        }
        if ([int]$Proof.local_geometry.terrain_skin.triangles -lt 25000) {
            throw "Variant $Variant rider-close terrain skin mesh is unexpectedly sparse."
        }
    }
} else {
    if ([bool]$Proof.local_terrain_skin.enabled -ne $false -or [bool]$Proof.local_geometry.terrain_skin.spawned -ne $false) {
        throw "Variant $Variant unexpectedly created local terrain."
    }
}

if ($ExpectedCorridor) {
    if ([bool]$Proof.local_geometry.earthwork.spawned -ne $true -or [bool]$Proof.local_geometry.asphalt.spawned -ne $true) {
        throw "Variant $Variant did not spawn the required road corridor."
    }
    if ([int]$Proof.local_geometry.earthwork.triangles -lt 3000) {
        throw "Variant $Variant earthwork mesh is unexpectedly sparse."
    }
    if ([int]$Proof.station_count -lt 250) {
        throw "Variant $Variant sampled too few corridor stations: $($Proof.station_count)"
    }
} else {
    if ([bool]$Proof.local_geometry.earthwork.spawned -ne $false -or [bool]$Proof.local_geometry.asphalt.spawned -ne $false) {
        throw "Variant $Variant unexpectedly spawned road corridor geometry."
    }
}

if (-not $ValidateOnly) {
    $CaptureLogText = Get-Content -LiteralPath $CaptureLog -Raw -ErrorAction Stop
    if ($CaptureExitCode -notin @(0,1)) {
        throw "SP638 local-corridor capture returned unexpected exit code $CaptureExitCode."
    }
    if ($CaptureLogText -match '(?i)Fatal error|Unhandled Exception|Critical error') {
        throw 'SP638 local-corridor capture log contains a crash/fatal marker.'
    }
    if ($CaptureLogText -notmatch '\[YacsSp638LocalCorridorVisual\] PASS:') {
        throw 'SP638 local-corridor log is missing the explicit PASS marker.'
    }
}

Write-Host '[3/3] Enforcing non-persistent proof contract...' -ForegroundColor Cyan
$TrackedChanges = @(git -C $RepoRoot status --porcelain=v1 --untracked-files=no)
if ($TrackedChanges.Count -gt 0) {
    throw ("SP638 local-corridor visual proof mutated tracked files: {0}" -f ($TrackedChanges -join '; '))
}

$GateLabel = if ($Variant -eq 'C3') { 'Gate C.3 native-DTM patch' } else { 'Gate C.1 surface-ownership variant' }
Write-Host ("{0} {1}: PASS." -f $GateLabel,$Variant) -ForegroundColor Green
Write-Host ("Rendered proof: {0}" -f $CapturePng)
exit 0
