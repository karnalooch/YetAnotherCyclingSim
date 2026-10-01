<# Import one verified native Sa Calobra DTM window; no road or visual acceptance. #>
[CmdletBinding()]
param(
    [string] $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path,
    [Parameter(Mandatory=$true)] [string] $ExpectedBranch,
    [Parameter(Mandatory=$true)] [string] $ExpectedHead,
    [Parameter(Mandatory=$true)] [string] $ArtifactRoot,
    [int] $TimeoutSec = 900
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not [IO.Path]::IsPathRooted($ArtifactRoot)) { $ArtifactRoot = Join-Path $RepoRoot $ArtifactRoot }
if (Test-Path -LiteralPath $ArtifactRoot) { throw 'Evidence directory already exists; preserve it and choose a new run directory.' }
$Context = & (Join-Path $RepoRoot 'scripts/ue/Preflight-YacsProof.ps1') -RepoRoot $RepoRoot -ExpectedBranch $ExpectedBranch -ExpectedHead $ExpectedHead -ArtifactRoot $ArtifactRoot
if ($LASTEXITCODE -ne 0) { throw 'Region terrain preflight failed.' }
$prepared = Join-Path $ArtifactRoot 'Prepared'
& python (Join-Path $RepoRoot 'scripts/assets/prepare_region_terrain.py') --output-dir $prepared
if ($LASTEXITCODE -ne 0) { throw 'Region terrain source admission failed.' }
$manifestPath = Join-Path $prepared 'terrain-import.json'
$heightmap = Join-Path $prepared 'terrain.r16'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $heightmap -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.heightmap_sha256) {
    throw 'Prepared terrain hash mismatch.'
}
$mapFile = Join-Path $RepoRoot (($manifest.map_package -replace '^/Game/', 'Content/') + '.umap')
if (Test-Path -LiteralPath $mapFile) { throw 'Existing terrain asset must be retained before authoring; no asset was deleted.' }
$env:YACS_TERRAIN_MANIFEST = $manifestPath
function Invoke-TerrainEditor([string[]] $EditorArguments, [string] $LogName) {
    $stdout = Join-Path $ArtifactRoot ($LogName + '.stdout.log')
    $stderr = Join-Path $ArtifactRoot ($LogName + '.stderr.log')
    $process = Start-Process -FilePath $Context.UnrealEditorCmdPath -ArgumentList $EditorArguments -WorkingDirectory $RepoRoot -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    if (-not $process.WaitForExit($TimeoutSec * 1000)) {
        $process | Stop-Process -Force
        throw "Terrain $LogName timed out."
    }
    if ($process.ExitCode -ne 0) { throw "Terrain $LogName failed with exit $($process.ExitCode); inspect $stdout and $stderr." }
}
try {
    $project = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject'
    $common = @('-Unattended', '-NoPause', '-NullRHI', '-NoSplash', '-NoP4')
    $mapScript = Join-Path $RepoRoot 'scripts/ue/prepare_region_terrain_map.py'
    Invoke-TerrainEditor (@(('"' + $project + '"'), '-run=pythonscript', ('-script="' + $mapScript + '"')) + $common) 'map-preparation'
    $proofPath = Join-Path $ArtifactRoot 'terrain-import-proof.json'
    Invoke-TerrainEditor (@(('"' + $project + '"'), '-run=CyclingPassoGiauLandscapeSpike', ('-TerrainManifest="' + $manifestPath + '"'), ('-Heightmap="' + $heightmap + '"'), ('-Proof="' + $proofPath + '"')) + $common) 'landscape-import'
    if (-not (Test-Path -LiteralPath $proofPath)) { throw 'Terrain import proof is missing.' }
    $proof = Get-Content -LiteralPath $proofPath -Raw | ConvertFrom-Json
    if ($proof.passo_giau_landscape_import -ne 'PASS' -or $proof.terrain_region_id -ne 'sa_calobra' -or $proof.map -ne $manifest.map_package) { throw 'Terrain import identity mismatch.' }
    if ($proof.unreal_native_import_reader_parity -ne 'PASS' -or $proof.component_count -ne 1024) { throw 'Terrain topology/import-reader proof failed.' }
    if ($proof.base_edit_layer -ne 'Base_DTM' -or $proof.road_edit_layer -ne 'Road_Earthworks' -or $proof.edit_layer_count -ne 2 -or $proof.road_imported) { throw 'Terrain layer ownership proof failed.' }
    foreach ($field in @('scale_z','location_z_cm')) {
        if ([Math]::Abs([double]$proof.$field - [double]$manifest.$field) -gt 0.001) { throw "Terrain $field differs from prepared input." }
    }
    if ([Math]::Abs([double]$proof.scale_x_cm_per_vertex - 50.0) -gt 0.000001 -or [Math]::Abs([double]$proof.scale_y_cm_per_vertex - 50.0) -gt 0.000001) { throw 'Native horizontal spacing changed.' }
    if ([Math]::Abs([double]$proof.sampled_elevation_min_m - [double]$manifest.elevation_min_m) -gt 0.01 -or [Math]::Abs([double]$proof.sampled_elevation_max_m - [double]$manifest.elevation_max_m) -gt 0.01) { throw 'Imported height domain differs from the native DTM.' }
    @{
        schema_version = 1; exact_sha = $ExpectedHead; region_id = 'sa_calobra'
        source_sha256 = $manifest.source_sha256; profile_sha256 = $manifest.profile_sha256
        heightmap_sha256 = $manifest.heightmap_sha256; technical_import_status = 'PASS'
        human_visual_status = 'PENDING'; performance_status = 'PENDING'; road_status = 'NOT_AUTHORED'
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $ArtifactRoot 'region-terrain-proof.json') -Encoding utf8
} finally {
    Remove-Item Env:YACS_TERRAIN_MANIFEST -ErrorAction SilentlyContinue
}
Write-Host 'Sa Calobra terrain import PASS; visual and performance acceptance remain pending.'
