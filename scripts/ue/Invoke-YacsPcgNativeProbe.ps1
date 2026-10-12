#requires -Version 7.4
<#
.SYNOPSIS
    Run an owned, content-only #365 PCG API diagnostic using authenticated retained binaries.
.DESCRIPTION
    LOCAL_DIAGNOSTIC_ONLY. No native compilation or protected proof admission.
    Never opens or saves the canonical project. Existing stages are preserved.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedHead,
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9-]{0,63}$')][string]$RunToken,
    [ValidateSet('inspect','create','reload','material','material-reload','terrain','settle-render','mask-xy-create','mask-xy-reload','rock-qualify','rock-reload','rock-render','rock-pack','rock-pack-reload','rock-collection','rock-collection-reload','rock-collection-render','collection-contact-00','collection-contact-01','collection-contact-02','collection-contact-03','collection-contact-04','collection-contact-05','collection-contact-06','collection-contact-07','collection-contact-08','collection-contact-09','collection-contact-all','collection-contact-reload','collection-contact-render','collection-contact-prepare','collection-contact-measure','collection-contact-review')][string]$Action = 'inspect',
    [switch]$QualificationSources,
    [ValidateSet('baseline','rock-detail','natural20-contact')][string]$QualificationSet = 'baseline',
    [switch]$RockQualificationSources,
    [ValidateSet('source','lod0','support','scan-base','large-base')][string]$RockSet = 'source',
    [string]$RockCollectionCatalog,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedRockCollectionSha,
    [string]$RockVariantCatalog,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedRockVariantSha,
    [string]$MaskXyRequest,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedMaskXySha,
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$IsCollectionContact = $Action -cmatch '^collection-contact-(0[0-9]|all|reload|render)$'
$IsSessionContact = $Action -cin @('collection-contact-prepare','collection-contact-measure','collection-contact-review')
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$Retained = 'D:/yacs/runner/_work/YetAnotherCyclingSim/YetAnotherCyclingSim/_phase2c-pcgex-cliff/Plugins/PCGExtendedToolkit'
$Root = [IO.Path]::GetFullPath("D:/yacs/work/pcg365/$ExpectedHead/$RunToken")
$Proof = Join-Path $Root 'proof'
$Project = Join-Path $Root 'Pcg365Diagnostic.uproject'
$ProbeRelative = 'scripts/ue/sa_calobra_pcg_native_probe.py'
$ProbeSource = Join-Path $RepoRoot $ProbeRelative
$Probe = Join-Path $Root 'sa_calobra_pcg_native_probe.py'
function Read-RepoGit([string[]]$Arguments) {
    $lines = @(& git --no-optional-locks -C $RepoRoot @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "Source Git failed: $($lines -join ' ')" }
    return $lines
}
function Hash-Lf([string]$Text) {
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($Text.Replace("`r`n", "`n")))).ToLowerInvariant()
}
function File-Identity([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refuse source alias: $Path" }
    return [ordered]@{ bytes=$item.Length; sha256=(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
}
function Assert-SameFile([string]$Path, $Identity) {
    $actual = File-Identity $Path
    if ($actual.bytes -ne $Identity.bytes -or $actual.sha256 -ne $Identity.sha256) { throw "Staging byte drift: $Path" }
}
function Assert-SessionProof([string]$Session) {
    $folder = Join-Path $Proof $Session
    $marker = Get-Content (Join-Path $folder 'launcher-completed.json') -Raw | ConvertFrom-Json
    if ($marker.action -cne $Session -or $marker.code_sha -cne $ExpectedHead -or
        $marker.exit_code -is [bool] -or $marker.exit_code -ne 0 -or
        $marker.staged_bytes_unchanged -ne $true -or
        $marker.proof_admission -cne 'LOCAL_DIAGNOSTIC_ONLY') {
        throw "Three-session predecessor did not exit cleanly: $Session"
    }
    $receipt = Get-Content (Join-Path $folder "$Session-receipt.json") -Raw | ConvertFrom-Json
    $expectedStatus = @{
        'collection-contact-prepare'='COLLECTION_CONTACT_PREPARED'
        'collection-contact-measure'='COLLECTION_CONTACT_ALL_MEASURED'
    }[$Session]
    if ($receipt.action -cne $Session -or $receipt.code_sha -cne $ExpectedHead -or
        $receipt.status -cne $expectedStatus -or
        $receipt.asset_compilation_loading_barrier_completed -ne $true -or
        $receipt.placement -ne $false -or @($receipt.qualified_assets).Count -ne 0) {
        throw "Three-session predecessor receipt differs: $Session"
    }
    $expected = if ($Session -ceq 'collection-contact-prepare') {
        @{
            inspect='proof/inspect/inspect-receipt.json'
            binding='proof/material/binding.json'
            material='proof/material/material-receipt.json'
            inventory='proof/rock-collection/rock-collection-inventory.json'
            collection='proof/rock-collection/rock-collection-receipt.json'
        }
    } else {
        @{
            material_readback='proof/collection-contact-measure/material-fresh-phase.json'
            collection_readback='proof/collection-contact-measure/collection-fresh-phase.json'
            contact='proof/collection-contact-all/collection-contact-all-receipt.json'
        }
    }
    if ((@($receipt.phases.PSObject.Properties.Name | Sort-Object) -join ',') -cne
        (@($expected.Keys | Sort-Object) -join ',')) { throw "Three-session phase set differs: $Session" }
    foreach ($key in $expected.Keys) {
        $row = $receipt.phases.$key
        if ($row.path -cne $expected[$key]) { throw "Unsafe phase path: $key" }
        Assert-SameFile (Join-Path $Root $row.path) $row
    }
    return $receipt
}
function Stage-QualifiedFile([string]$Source, [string]$Relative, $Identity) {
    if ($Relative -match '(^/|\.\.|:|\\)') { throw 'Unsafe qualification stage path.' }
    Assert-SameFile $Source $Identity
    $destination = Join-Path $Root $Relative
    New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
    if (Test-Path -LiteralPath $destination) { throw 'Qualification staging collision.' }
    Copy-Item -LiteralPath $Source -Destination $destination
    Assert-SameFile $Source $Identity
    Assert-SameFile $destination $Identity
    $entries.Add([ordered]@{path=$Relative;identity=$Identity})
}
if (((Read-RepoGit @('rev-parse','HEAD')) -join '') -cne $ExpectedHead) { throw 'Exact source HEAD mismatch.' }
if (@(Read-RepoGit @('diff','HEAD','--name-only')).Count -ne 0 -or
    @(Read-RepoGit @('diff','--cached','--name-only')).Count -ne 0) { throw 'Tracked source changes must be committed first.' }
if (@(Read-RepoGit @('ls-files','-v') | Where-Object { $_ -cmatch '^[a-zS] ' }).Count -ne 0) { throw 'Hidden tracked source flags are forbidden.' }
foreach ($scriptRelative in @($ProbeRelative, 'scripts/ue/Invoke-YacsPcgNativeProbe.ps1')) {
    $committedScript = ((Read-RepoGit @('show', "${ExpectedHead}:$scriptRelative")) -join "`n") + "`n"
    if ((Hash-Lf ([IO.File]::ReadAllText((Join-Path $RepoRoot $scriptRelative)))) -cne (Hash-Lf $committedScript)) {
        throw "Diagnostic script differs from committed LF bytes: $scriptRelative"
    }
}
$Committed = ((Read-RepoGit @('show',"${ExpectedHead}:$ProbeRelative")) -join "`n") + "`n"
$ProbeHash = Hash-Lf ([IO.File]::ReadAllText($ProbeSource))
if ($ProbeHash -cne (Hash-Lf $Committed)) { throw 'Probe differs from committed LF bytes.' }
$hostState = & (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
if ($hostState.status -cne 'IDLE') { throw "Shared Unreal host is owned: $($hostState.status)" }
$drive = [IO.DriveInfo]::new('D:/')
if ($drive.AvailableFreeSpace -lt 5GB) { throw 'Native diagnostic requires the existing 5 GiB reserve.' }
. (Join-Path $RepoRoot 'scripts/ci/Resolve-YacsUnrealEngine.ps1')
$engine = Resolve-YacsUnrealEngine -ProjectPath (Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject') -SearchRoots @('D:/yacs/engine/UE_5.8')
if ($engine.VersionObject.MajorVersion -ne 5 -or $engine.VersionObject.MinorVersion -ne 8 -or
    $engine.VersionObject.PatchVersion -ne 2 -or $engine.VersionObject.Changelist -ne 56702186) { throw 'Engine pin drift.' }
$Editor = Join-Path $engine.Root 'Engine/Binaries/Win64/UnrealEditor.exe'
$EngineModules = Get-Content (Join-Path $engine.Root 'Engine/Binaries/Win64/UnrealEditor.modules') -Raw | ConvertFrom-Json
$PluginModules = Get-Content (Join-Path $Retained 'Binaries/Win64/UnrealEditor.modules') -Raw | ConvertFrom-Json
if ($PluginModules.BuildId -cne $EngineModules.BuildId) { throw 'Retained plugin/engine BuildId mismatch.' }
if ($Action -cnotin @('inspect','collection-contact-prepare')) {
    if (-not (Test-Path -LiteralPath $Project -PathType Leaf)) { throw 'Create/reload requires an existing owned inspected diagnostic stage.' }
    $registry = Get-Content (Join-Path $Root 'staged-files.json') -Raw | ConvertFrom-Json
    if ($registry.expected_head -cne $ExpectedHead -or $registry.probe_sha256_lf -cne $ProbeHash) { throw 'Existing stage identity drift.' }
    foreach ($entry in $registry.files) { Assert-SameFile (Join-Path $Root $entry.path) $entry.identity }
    if (-not $IsSessionContact) {
        $inspection = Get-Content (Join-Path $Proof 'inspect/inspect-receipt.json') -Raw | ConvertFrom-Json
        if ($inspection.status -cne 'NATIVE_INSPECTION_COMPLETED') { throw 'Native inspection must complete before graph operations.' }
        $completedInspection = Get-Content (Join-Path $Proof 'inspect/launcher-completed.json') -Raw | ConvertFrom-Json
        if ($completedInspection.code_sha -cne $ExpectedHead -or $completedInspection.exit_code -ne 0) { throw 'Native inspection process did not finish cleanly.' }
    }
} else {
    if (Test-Path -LiteralPath $Root) { throw 'Preserve existing stage; choose a fresh RunToken.' }
    New-Item -ItemType Directory -Path $Proof -Force | Out-Null
    & (Join-Path $RepoRoot 'scripts/worldgen/Bootstrap-YacsPcgEx.ps1') -Mode Validate -RepoRoot $RepoRoot -PluginRoot $Retained -ReportPath (Join-Path $Proof 'retained-bootstrap.json')
    $bootstrap = Get-Content (Join-Path $Proof 'retained-bootstrap.json') -Raw | ConvertFrom-Json
    if ($bootstrap.status -cne 'PASS' -or $bootstrap.compatibility_patch_state -cne 'applied') { throw 'Retained PCGEx authentication failed.' }
    $StagePlugin = Join-Path $Root 'Plugins/PCGExtendedToolkit'
    $Sources = [Collections.Generic.List[object]]::new()
    foreach ($directory in @('Source','Content','Config','Resources')) {
        $base = Join-Path $Retained $directory
        foreach ($item in Get-ChildItem -LiteralPath $base -Recurse -Force) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refuse retained alias: $($item.FullName)" }
            if (-not $item.PSIsContainer) { $Sources.Add($item) }
        }
    }
    foreach ($name in @('PCGExtendedToolkit.uplugin','LICENSE','THIRD_PARTY_NOTICE.md','Binaries/Win64/UnrealEditor.modules')) {
        $Sources.Add((Get-Item -LiteralPath (Join-Path $Retained $name)))
    }
    foreach ($module in $PluginModules.Modules.PSObject.Properties) {
        if ([IO.Path]::GetFileName([string]$module.Value) -cne [string]$module.Value -or [IO.Path]::GetExtension([string]$module.Value) -cne '.dll') { throw 'Unexpected module binary path.' }
        $Sources.Add((Get-Item -LiteralPath (Join-Path $Retained "Binaries/Win64/$($module.Value)")))
    }
    $entries = [Collections.Generic.List[object]]::new()
    foreach ($item in $Sources) {
        $relative = [IO.Path]::GetRelativePath($Retained, $item.FullName)
        $identity = File-Identity $item.FullName
        $destination = Join-Path $StagePlugin $relative
        New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $item.FullName -Destination $destination
        Assert-SameFile $destination $identity
        Assert-SameFile $item.FullName $identity
        $entries.Add([ordered]@{ path=[IO.Path]::GetRelativePath($Root,$destination).Replace('\','/'); identity=$identity })
    }
    # One final complete source pass rejects concurrent changes during staging.
    foreach ($entry in $entries) {
        $relative = $entry.path.Substring('Plugins/PCGExtendedToolkit/'.Length)
        Assert-SameFile (Join-Path $Retained $relative) $entry.identity
    }
    $CanonicalRoot = 'D:/yacs/project'
    $AssetPaths = @(
        'Content/Prototype/Environment/Stage3G/Imported/Meshes/SM_Stage3G_Boulder.uasset',
        'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_Boulder_BaseColor.uasset',
        'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_Boulder_Normal.uasset',
        'Content/Prototype/Environment/Stage3G/Imported/Textures/T_Stage3G_Boulder_Roughness.uasset',
        'Content/Prototype/Environment/Stage3G/Materials/M_Stage3G_Rock.uasset',
        'Content/Prototype/Environment/Stage3G/Materials/MI_Stage3G_Rock.uasset'
    )
    foreach ($relative in $AssetPaths) {
        $pointer = (Read-RepoGit @('show', "${ExpectedHead}:$relative")) -join "`n"
        $match = [regex]::Match($pointer, '\Aversion https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n?\z')
        if (-not $match.Success) { throw "Asset must be an exact committed LFS pointer: $relative" }
        $identity = [ordered]@{sha256=$match.Groups[1].Value; bytes=[long]$match.Groups[2].Value}
        $source = Join-Path $CanonicalRoot $relative
        Assert-SameFile $source $identity
        $destination = Join-Path $Root $relative
        New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination
        Assert-SameFile $source $identity
        Assert-SameFile $destination $identity
        $entries.Add([ordered]@{path=$relative;identity=$identity})
    }
    foreach ($entry in $entries | Where-Object { $_.path.StartsWith('Content/') }) {
        Assert-SameFile (Join-Path $CanonicalRoot $entry.path) $entry.identity
    }
    Copy-Item -LiteralPath $ProbeSource -Destination $Probe
    $entries.Add([ordered]@{path='sa_calobra_pcg_native_probe.py';identity=(File-Identity $Probe)})
    if ($MaskXyRequest) {
        if (-not $ExpectedMaskXySha) { throw 'Mask XY request requires an expected SHA256.' }
        $requestIdentity = File-Identity $MaskXyRequest
        if ($requestIdentity.sha256 -cne $ExpectedMaskXySha) { throw 'Mask XY request SHA drift.' }
        Stage-QualifiedFile $MaskXyRequest 'mask-xy-request.json' $requestIdentity
        $scriptRelative = 'scripts/ue/sa_calobra_pcg_mask_xy_graph.py'
        $source = Join-Path $RepoRoot $scriptRelative
        $committedScript = ((Read-RepoGit @('show', "${ExpectedHead}:$scriptRelative")) -join "`n") + "`n"
        if ((Hash-Lf ([IO.File]::ReadAllText($source))) -cne (Hash-Lf $committedScript)) { throw 'Uncommitted mask XY helper.' }
        Stage-QualifiedFile $source $scriptRelative (File-Identity $source)
    } elseif ($ExpectedMaskXySha) { throw 'Expected mask XY SHA requires a request path.' }
    if ($QualificationSources) {
        $qualificationName = @{baseline='pcg365_qualification_sources_v1.json';'rock-detail'='pcg365_rock_detail_sources_v1.json';'natural20-contact'='pcg365_natural20_contact_sources_v1.json'}[$QualificationSet]
        $qualificationPath = Join-Path $RepoRoot "worldgen/sa_calobra/$qualificationName"
        $qualification = Get-Content -LiteralPath $qualificationPath -Raw | ConvertFrom-Json
        $expectedTerrainAssets = if ($QualificationSet -ceq 'natural20-contact') { 202 } else { 14 }
        if ($qualification.scope -cne 'LOCAL_DIAGNOSTIC_ONLY_NOT_REGIONAL_PLACEMENT' -or $qualification.terrain.assets.Count -ne $expectedTerrainAssets) { throw 'Unexpected qualification source contract.' }
        Stage-QualifiedFile $qualificationPath 'qualification-sources.json' (File-Identity $qualificationPath)

        # "Saved/" belongs to the authoring workspace, not GitHub's code-only CI
        # checkout. Reuse the retained run04 input bytes, never a new/generated XY.
        # The pinned qualification contract still owns the exact SHA256 and size.
        $contactInput = $qualification.contact_input
        if ($QualificationSet -ceq 'natural20-contact') {
            if ($contactInput.path -cne 'Saved/RuntimeProof/WorldGraph365/real-contact-source02.json') {
                throw 'Natural20 contact input contract path drift.'
            }
            $contactSource = 'D:/yacs/work/pcg365/1a02ac21a7fb1dbc84364843e862b186a2ea0a18/natural20-contact04/contact-request.json'
        } else {
            $contactSource = Join-Path $RepoRoot $contactInput.path
        }
        if (-not (Test-Path -LiteralPath $contactSource -PathType Leaf)) {
            throw "Pinned contact input unavailable before bulk staging: $contactSource"
        }
        Assert-SameFile $contactSource $contactInput
        Stage-QualifiedFile $contactSource 'contact-request.json' $contactInput
        foreach ($scriptRelative in @('scripts/ue/sa_calobra_pcg_material_binding.py','scripts/ue/sa_calobra_pcg_terrain_contact.py','scripts/ue/import_material_forge_variant.py','scripts/assets/road_material_contract.py','scripts/assets/pcg_boulder_support.py','scripts/ue/sa_calobra_pcg_boulder_settle.py','scripts/ue/sa_calobra_pcg_boulder_capture.py')) {
            $source = Join-Path $RepoRoot $scriptRelative
            $committedScript = ((Read-RepoGit @('show', "${ExpectedHead}:$scriptRelative")) -join "`n") + "`n"
            if ((Hash-Lf ([IO.File]::ReadAllText($source))) -cne (Hash-Lf $committedScript)) { throw "Uncommitted qualification helper: $scriptRelative" }
            Stage-QualifiedFile $source $scriptRelative (File-Identity $source)
        }
        foreach ($file in $qualification.forge.files) {
            Stage-QualifiedFile (Join-Path $qualification.forge.root $file.path) "forge-source/$($file.path)" $file
        }
        foreach ($receiptName in @('consumer-manifest','reload-receipt','fresh-render-receipt')) {
            $source = Join-Path $qualification.terrain.retained_root "$receiptName.json"
            $identity = File-Identity $source
            $key = $receiptName.Replace('-','_') + '_sha256'
            if ($identity.sha256 -cne $qualification.terrain.$key) { throw 'Retained Terrain Authority receipt drift.' }
            Stage-QualifiedFile $source "terrain-source/$receiptName.json" $identity
        }
        foreach ($file in $qualification.terrain.assets) {
            if ($file.PSObject.Properties.Name -contains 'storage') {
                $source = Join-Path $qualification.terrain.retained_root $file.storage.asset
            } else {
                $source = Join-Path $qualification.terrain.canonical_root $file.path
                $pointer = (Read-RepoGit @('show', "${ExpectedHead}:$($file.path)")) -join "`n"
                if ($pointer -notmatch "oid sha256:$($file.sha256)\nsize $($file.size_bytes)(\n|$)") { throw 'Terrain dependency is not committed source.' }
            }
            Stage-QualifiedFile $source $file.path ([ordered]@{sha256=$file.sha256;bytes=$file.size_bytes})
        }

    }
    if ($RockQualificationSources) {
        if (-not $QualificationSources) { throw 'Rock qualification requires authenticated terrain/Forge sources.' }
        $rockRequestName = @{source='pcg365_rock_qualification_v1.json';lod0='pcg365_rock_lod0_qualification_v1.json';support='pcg365_support_rock_qualification_v1.json';'scan-base'='pcg365_scan_base_diagnostic_v1.json';'large-base'='pcg365_large_scan_base_diagnostic_v1.json'}[$RockSet]
        $requestPath = Join-Path $RepoRoot "worldgen/sa_calobra/$rockRequestName"
        $request = Get-Content -LiteralPath $requestPath -Raw | ConvertFrom-Json
        if ($request.scope -cne 'ISOLATED_ROCK_QUALIFICATION_ONLY' -or $request.assets.Count -ne 2 -or $request.placement) { throw 'Unexpected rock qualification request.' }
        Stage-QualifiedFile $requestPath 'rock-qualification-request.json' (File-Identity $requestPath)
        if ($request.PSObject.Properties.Name -contains 'source_inspection') {
            $sourceInspectionIdentity = File-Identity $request.source_inspection.path
            if ($sourceInspectionIdentity.sha256 -cne $request.source_inspection.sha256) { throw 'Rock source inspection receipt drift.' }
            Stage-QualifiedFile $request.source_inspection.path 'rock-source/source-inspection.json' $sourceInspectionIdentity
        }
        foreach ($asset in $request.assets) {
            if ($asset.id -cnotin @('rock_07','rock_09','support_rock_a','support_rock_b','namaqualand_boulder_02','namaqualand_boulder_06') -or $asset.source_relative -cne "rock-source/$($asset.id).fbx") { throw 'Unexpected rock source identity.' }
            Stage-QualifiedFile $asset.source $asset.source_relative $asset
        }
        foreach ($scriptRelative in @('scripts/assets/pcg_rock_contact_policy.py','scripts/assets/pcg_rock_patch_diagnostic.py','scripts/ue/sa_calobra_pcg_rock_qualification.py','scripts/ue/sa_calobra_pcg_rock_capture.py')) {
            $source = Join-Path $RepoRoot $scriptRelative
            $committedScript = ((Read-RepoGit @('show', "${ExpectedHead}:$scriptRelative")) -join "`n") + "`n"
            if ((Hash-Lf ([IO.File]::ReadAllText($source))) -cne (Hash-Lf $committedScript)) { throw "Uncommitted rock helper: $scriptRelative" }
            Stage-QualifiedFile $source $scriptRelative (File-Identity $source)
        }
    }
    if ($RockVariantCatalog) {
        if (-not $QualificationSources -or -not $ExpectedRockVariantSha) { throw 'Variant catalog requires authenticated Forge sources and expected SHA.' }
        $catalogIdentity = File-Identity $RockVariantCatalog
        if ($catalogIdentity.sha256 -cne $ExpectedRockVariantSha) { throw 'Variant catalog SHA drift.' }
        $catalog = Get-Content -LiteralPath $RockVariantCatalog -Raw | ConvertFrom-Json
        if ($catalog.schema_version -ne 1 -or $catalog.scope -cne 'LOCAL_ROCK_VARIANT_ASSET_LIBRARY_ONLY' -or $catalog.variants.Count -ne 6 -or $catalog.placement -isnot [bool] -or $catalog.placement -or $catalog.qualified_assets.Count -ne 0) { throw 'Unexpected variant catalog contract.' }
        Stage-QualifiedFile $RockVariantCatalog 'rock-variant-catalog.json' $catalogIdentity
        foreach ($variant in $catalog.variants) {
            if ($variant.id -cnotmatch '^namaqualand_boulder_(02|06)_s(75|100|125)$' -or $variant.source_relative -cne "rock-variants/$($variant.id).fbx") { throw 'Unexpected variant source identity.' }
            Stage-QualifiedFile $variant.source $variant.source_relative $variant
        }
        $scriptRelative = 'scripts/ue/sa_calobra_pcg_rock_variant_pack.py'
        $source = Join-Path $RepoRoot $scriptRelative
        $committedScript = ((Read-RepoGit @('show', "${ExpectedHead}:$scriptRelative")) -join "`n") + "`n"
        if ((Hash-Lf ([IO.File]::ReadAllText($source))) -cne (Hash-Lf $committedScript)) { throw 'Uncommitted variant helper.' }
        Stage-QualifiedFile $source $scriptRelative (File-Identity $source)
    } elseif ($ExpectedRockVariantSha) { throw 'Expected variant SHA requires catalog path.' }
    if ($RockCollectionCatalog) {
        if (-not $QualificationSources -or -not $ExpectedRockCollectionSha) { throw 'Collection requires authenticated Forge sources and expected SHA.' }
        $collectionIdentity = File-Identity $RockCollectionCatalog
        if ($collectionIdentity.sha256 -cne $ExpectedRockCollectionSha) { throw 'Collection catalog SHA drift.' }
        $collection = Get-Content -LiteralPath $RockCollectionCatalog -Raw | ConvertFrom-Json
        if ($collection.schema_version -ne 1 -or $collection.scope -cnotin @('LOCAL_ROCK_COLLECTION20_ASSET_LIBRARY_ONLY','LOCAL_NATURAL_ROCK_COLLECTION20_ASSET_LIBRARY_ONLY') -or $collection.variants.Count -ne 20 -or $collection.placement -isnot [bool] -or $collection.placement -or $collection.qualified_assets.Count -ne 0) { throw 'Unexpected collection catalog contract.' }
        if ($collection.scope -ceq 'LOCAL_NATURAL_ROCK_COLLECTION20_ASSET_LIBRARY_ONLY' -and ($collection.status -cne 'NATURAL_ROCK_COLLECTION20_PREPARED_ONLY' -or $collection.variant_count -ne 20 -or $collection.source_family_count -ne 8 -or $collection.rejected_sources.Count -ne 0 -or $collection.production_admission)) { throw 'Natural collection must be complete and unadmitted.' }
        Stage-QualifiedFile $RockCollectionCatalog 'rock-collection-catalog.json' $collectionIdentity
        foreach ($variant in $collection.variants) {
            if ($variant.id -cnotmatch '^(rock(02|06)_(0[1-9]|10)|(namaqualand_boulder_0[2-6]|rock_0[79]|boulder_01)_0[1-3])$' -or $variant.source_relative -cne "rock-collection/$($variant.id).fbx") { throw 'Unexpected collection source identity.' }
            Stage-QualifiedFile $variant.source $variant.source_relative $variant
        }
        $scriptRelative = 'scripts/ue/sa_calobra_pcg_rock_collection.py'
        $source = Join-Path $RepoRoot $scriptRelative
        $committedScript = ((Read-RepoGit @('show', "${ExpectedHead}:$scriptRelative")) -join "`n") + "`n"
        if ((Hash-Lf ([IO.File]::ReadAllText($source))) -cne (Hash-Lf $committedScript)) { throw 'Uncommitted collection helper.' }
        Stage-QualifiedFile $source $scriptRelative (File-Identity $source)
        foreach ($scriptRelative in @('scripts/ue/sa_calobra_pcg_collection_contact.py','scripts/ue/pcg365_three_session.py','scripts/assets/pcg_rock_contact_policy.py','scripts/assets/pcg_rock_patch_diagnostic.py','scripts/ue/sa_calobra_pcg_rock_qualification.py','scripts/ue/sa_calobra_pcg_rock_capture.py')) {
            if (@($entries | Where-Object { $_.path -ceq $scriptRelative }).Count -ne 0) { continue }
            $source = Join-Path $RepoRoot $scriptRelative
            $committedScript = ((Read-RepoGit @('show', "${ExpectedHead}:$scriptRelative")) -join "`n") + "`n"
            if ((Hash-Lf ([IO.File]::ReadAllText($source))) -cne (Hash-Lf $committedScript)) { throw "Uncommitted collection contact helper: $scriptRelative" }
            Stage-QualifiedFile $source $scriptRelative (File-Identity $source)
        }
    } elseif ($ExpectedRockCollectionSha) { throw 'Expected collection SHA requires catalog path.' }
    $plugins = @('PythonScriptPlugin','EditorScriptingUtilities','PCG','PCGToolset','PCGExtendedToolkit','LandscapePatch') | ForEach-Object { [ordered]@{Name=$_;Enabled=$true;Optional=$false} }
    [ordered]@{FileVersion=3;EngineAssociation='5.8';Category='';Description='YACS #365 owned local diagnostic';Plugins=@($plugins)} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Project -Encoding utf8
    $entries.Add([ordered]@{path='Pcg365Diagnostic.uproject';identity=(File-Identity $Project)})
    [ordered]@{status='LOCAL_DIAGNOSTIC_ONLY';expected_head=$ExpectedHead;probe_sha256_lf=$ProbeHash;plugin_pin=$bootstrap.actual_commit;plugin_patch=$bootstrap.compatibility_patch_sha256;binary_provenance='retained prebuilt; not an exact-head native build';engine_build_id=$EngineModules.BuildId;files=$entries} | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $Root 'staged-files.json') -Encoding utf8
}
New-Item -ItemType Directory -Path $Proof -Force | Out-Null
$Output = Join-Path $Proof $Action
$Receipt = Join-Path $Output "$Action-receipt.json"
if ($Action -in @('mask-xy-create','mask-xy-reload')) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root 'mask-xy-request.json'))) { throw 'Mask XY request was not staged.' }
}
if ($Action -eq 'mask-xy-reload') {
    $completedCreate = Get-Content (Join-Path $Proof 'mask-xy-create/launcher-completed.json') -Raw | ConvertFrom-Json
    if ($completedCreate.code_sha -cne $ExpectedHead -or $completedCreate.exit_code -ne 0) { throw 'Mask XY create process did not finish cleanly.' }
    $saved = Get-Content (Join-Path $Proof 'mask-xy-create/saved-packages.json') -Raw | ConvertFrom-Json
    if ($saved.code_sha -cne $ExpectedHead -or $saved.request_sha256 -cne (File-Identity (Join-Path $Root 'mask-xy-request.json')).sha256 -or $saved.files.Count -ne 2) { throw 'Saved mask XY package identity mismatch.' }
    if (@($saved.files.path | Sort-Object -Unique).Count -ne 2) { throw 'Duplicate mask XY package path.' }
    foreach ($entry in $saved.files) {
        if ([string]$entry.path -notmatch '^Content/Generated/YACS/PCG365MaskXYDiagnostic/(PCG_MaskXY\.uasset|L_MaskXY\.umap)$') { throw 'Unexpected mask XY package path.' }
        Assert-SameFile (Join-Path $Root $entry.path) $entry
    }
}
if ($Action -eq 'reload') {
    $saved = Get-Content (Join-Path $Proof 'create/saved-packages.json') -Raw | ConvertFrom-Json
    if ($saved.code_sha -cne $ExpectedHead -or $saved.files.Count -ne 2) { throw 'Saved mechanical package identity mismatch.' }
    if (@($saved.files.path | Sort-Object -Unique).Count -ne 2) { throw 'Duplicate saved mechanical package path.' }
    foreach ($entry in $saved.files) {
        if ([string]$entry.path -notmatch '^Content/Generated/YACS/PCG365Mechanical/(PCG_XYFixture\.uasset|L_XYFixture\.umap)$') { throw 'Unexpected mechanical package path.' }
        Assert-SameFile (Join-Path $Root $entry.path) $entry
    }
}
if ($Action -in @('rock-qualify','rock-reload','rock-render') -and -not (Test-Path -LiteralPath (Join-Path $Root 'rock-qualification-request.json'))) { throw 'Rock sources were not staged.' }
if (($IsCollectionContact -or $IsSessionContact -or $Action -in @('material','material-reload','terrain','settle-render','rock-qualify','rock-reload','rock-render','rock-pack','rock-pack-reload','rock-collection','rock-collection-reload','rock-collection-render')) -and -not (Test-Path -LiteralPath (Join-Path $Root 'qualification-sources.json'))) { throw 'Qualification sources were not staged.' }
if (($IsCollectionContact -or $Action -in @('material-reload','terrain','settle-render','rock-qualify','rock-reload','rock-render','rock-pack','rock-pack-reload','rock-collection','rock-collection-reload','rock-collection-render'))) {
    $materialCompleted = Get-Content (Join-Path $Proof 'material/launcher-completed.json') -Raw | ConvertFrom-Json
    if ($materialCompleted.code_sha -cne $ExpectedHead -or $materialCompleted.exit_code -ne 0) { throw 'Material save process did not complete cleanly.' }
    $binding = Get-Content (Join-Path $Proof 'material/binding.json') -Raw | ConvertFrom-Json
    if ($binding.code_sha -cne $ExpectedHead -or $binding.saved_packages.Count -ne 7) { throw 'Unexpected saved material inventory.' }
    foreach ($entry in $binding.saved_packages) {
        if ($entry.path -notmatch '^Content/Generated/YACS/PCG365Qualification/[^:]+\.uasset$' -or $entry.path -match '\.\.') { throw 'Unsafe material package path.' }
        Assert-SameFile (Join-Path $Root $entry.path) $entry
    }
}
if (($IsCollectionContact -or $Action -in @('terrain','settle-render','rock-qualify','rock-reload','rock-render','rock-pack','rock-pack-reload','rock-collection','rock-collection-reload','rock-collection-render'))) {
    $materialReloadCompleted = Get-Content (Join-Path $Proof 'material-reload/launcher-completed.json') -Raw | ConvertFrom-Json
    if ($materialReloadCompleted.code_sha -cne $ExpectedHead -or $materialReloadCompleted.exit_code -ne 0) { throw 'Material fresh readback must complete before terrain measurement.' }
}
if ($Action -in @('rock-reload','rock-render')) {
    $rockCompleted = Get-Content (Join-Path $Proof 'rock-qualify/launcher-completed.json') -Raw | ConvertFrom-Json
    if ($rockCompleted.code_sha -cne $ExpectedHead -or $rockCompleted.exit_code -ne 0) { throw 'Rock qualification process must complete before fresh readback.' }
    $rockInventory = Get-Content (Join-Path $Proof 'rock-qualify/mesh-inventory.json') -Raw | ConvertFrom-Json
    if ($rockInventory.code_sha -cne $ExpectedHead -or $rockInventory.saved_packages.Count -ne 2) { throw 'Unexpected rock inventory.' }
    foreach ($entry in $rockInventory.saved_packages) {
        if ($entry.path -notmatch '^Content/Generated/YACS/PCG365Rocks/SM_(rock_(07|09)|support_rock_[ab]|namaqualand_boulder_(02|06))_ForgeDiagnostic\.uasset$') { throw 'Unexpected rock package path.' }
        Assert-SameFile (Join-Path $Root $entry.path) $entry
    }
}
if ($Action -eq 'rock-render') {
    $rockReloadCompleted = Get-Content (Join-Path $Proof 'rock-reload/launcher-completed.json') -Raw | ConvertFrom-Json
    if ($rockReloadCompleted.code_sha -cne $ExpectedHead -or $rockReloadCompleted.exit_code -ne 0) { throw 'Rock fresh readback must complete before GPU capture.' }
}
if ($Action -in @('rock-pack','rock-pack-reload') -and -not (Test-Path -LiteralPath (Join-Path $Root 'rock-variant-catalog.json'))) { throw 'Variant catalog was not staged.' }
if ($Action -eq 'rock-pack-reload') {
    $packCompleted = Get-Content (Join-Path $Proof 'rock-pack/launcher-completed.json') -Raw | ConvertFrom-Json
    if ($packCompleted.code_sha -cne $ExpectedHead -or $packCompleted.exit_code -ne 0) { throw 'Variant save process must complete cleanly before reload.' }
    $packInventory = Get-Content (Join-Path $Proof 'rock-pack/rock-pack-inventory.json') -Raw | ConvertFrom-Json
    if ($packInventory.code_sha -cne $ExpectedHead -or $packInventory.meshes.Count -ne 6) { throw 'Variant inventory identity differs.' }
    foreach ($mesh in $packInventory.meshes) {
        if ($mesh.saved_package.path -cnotmatch '^Content/Generated/YACS/PCG365RockVariants/SM_namaqualand_boulder_(02|06)_s(75|100|125)\.uasset$') { throw 'Unexpected variant saved path.' }
        Assert-SameFile (Join-Path $Root $mesh.saved_package.path) $mesh.saved_package
    }
}
if (($IsCollectionContact -or $Action -in @('rock-collection','rock-collection-reload','rock-collection-render')) -and -not (Test-Path -LiteralPath (Join-Path $Root 'rock-collection-catalog.json'))) { throw 'Collection catalog was not staged.' }
if (($IsCollectionContact -or $Action -in @('rock-collection-reload','rock-collection-render'))) {
    $collectionCompleted = Get-Content (Join-Path $Proof 'rock-collection/launcher-completed.json') -Raw | ConvertFrom-Json
    if ($collectionCompleted.code_sha -cne $ExpectedHead -or $collectionCompleted.exit_code -ne 0) { throw 'Collection save must complete cleanly before reload/render.' }
    $collectionInventory = Get-Content (Join-Path $Proof 'rock-collection/rock-collection-inventory.json') -Raw | ConvertFrom-Json
    if ($collectionInventory.code_sha -cne $ExpectedHead -or $collectionInventory.meshes.Count -ne 20) { throw 'Collection inventory differs.' }
    foreach ($mesh in $collectionInventory.meshes) {
        if ($mesh.saved_package.path -cnotmatch '^Content/Generated/YACS/PCG365RockCollection20/SM_(rock(02|06)_(0[1-9]|10)|(namaqualand_boulder_0[2-6]|rock_0[79]|boulder_01)_0[1-3])\.uasset$') { throw 'Unexpected collection saved path.' }
        Assert-SameFile (Join-Path $Root $mesh.saved_package.path) $mesh.saved_package
    }
}
if ($Action -eq 'rock-collection-render') {
    $collectionReload = Get-Content (Join-Path $Proof 'rock-collection-reload/launcher-completed.json') -Raw | ConvertFrom-Json
    if ($collectionReload.code_sha -cne $ExpectedHead -or $collectionReload.exit_code -ne 0) { throw 'Collection fresh reload must complete before GPU capture.' }
}
if ($IsSessionContact) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root 'contact-request.json'))) { throw 'Three-session contact request was not staged.' }
    if (-not (Test-Path -LiteralPath (Join-Path $Root 'rock-collection-catalog.json'))) { throw 'Three-session catalog was not staged.' }
    if ($Action -cne 'collection-contact-prepare') {
        [void](Assert-SessionProof 'collection-contact-prepare')
        $binding = Get-Content (Join-Path $Proof 'material/binding.json') -Raw | ConvertFrom-Json
        if ($binding.code_sha -cne $ExpectedHead -or @($binding.saved_packages).Count -ne 7) { throw 'Three-session saved Forge binding differs.' }
        foreach ($item in $binding.saved_packages) {
            if ($item.path -notmatch '^Content/Generated/YACS/PCG365Qualification/[^:]+\.uasset$' -or $item.path -match '\.\.') { throw 'Unsafe session Forge package.' }
            Assert-SameFile (Join-Path $Root $item.path) $item
        }
        $collectionInventory = Get-Content (Join-Path $Proof 'rock-collection/rock-collection-inventory.json') -Raw | ConvertFrom-Json
        if ($collectionInventory.code_sha -cne $ExpectedHead -or @($collectionInventory.meshes).Count -ne 20) { throw 'Three-session saved collection differs.' }
        foreach ($mesh in $collectionInventory.meshes) {
            if ($mesh.saved_package.path -cnotmatch '^Content/Generated/YACS/PCG365RockCollection20/SM_(rock(02|06)_(0[1-9]|10)|(namaqualand_boulder_0[2-6]|rock_0[79]|boulder_01)_0[1-3])\.uasset$') { throw 'Unsafe session mesh path.' }
            Assert-SameFile (Join-Path $Root $mesh.saved_package.path) $mesh.saved_package
        }
    }
    if ($Action -ceq 'collection-contact-review') {
        [void](Assert-SessionProof 'collection-contact-measure')
        if ((Test-Path -LiteralPath (Join-Path $Proof 'collection-contact-all/launcher-completed.json'))) { throw 'Grouped contact phase must not invent exit marker.' }
    }
}
if ($IsCollectionContact) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root 'contact-request.json'))) { throw 'Contact request was not staged.' }
    $collectionReload = Get-Content (Join-Path $Proof 'rock-collection-reload/launcher-completed.json') -Raw | ConvertFrom-Json
    if ($collectionReload.code_sha -cne $ExpectedHead -or $collectionReload.exit_code -ne 0) { throw 'Collection fresh reload must complete before contact.' }
    $allContactExists = Test-Path -LiteralPath (Join-Path $Proof 'collection-contact-all')
    $batchContactExists = @(0..9 | Where-Object { Test-Path -LiteralPath (Join-Path $Proof ('collection-contact-{0:00}' -f $_)) }).Count -gt 0
    if (($allContactExists -and $batchContactExists) -or ($Action -ceq 'collection-contact-all' -and $batchContactExists) -or ($Action -cmatch '^collection-contact-0[0-9]$' -and $allContactExists)) { throw 'Mixed contact process layouts are forbidden; preserve partial results and use a fresh stage.' }
    $priorActions = if ($Action -ceq 'collection-contact-reload') { if ($allContactExists) { @('collection-contact-all') } else { @(0..9 | ForEach-Object { 'collection-contact-{0:00}' -f $_ }) } } elseif ($Action -ceq 'collection-contact-render') { @('collection-contact-reload') } else { @() }
    foreach ($priorAction in $priorActions) {
        $prior = Get-Content (Join-Path $Proof "$priorAction/launcher-completed.json") -Raw | ConvertFrom-Json
        if ($prior.code_sha -cne $ExpectedHead -or $prior.exit_code -ne 0 -or $prior.action -cne $priorAction) { throw "Contact prerequisite did not finish cleanly: $priorAction" }
    }
}
if (Test-Path -LiteralPath $Output) { throw 'Preserve existing action output.' }
New-Item -ItemType Directory -Path $Output | Out-Null
# Recheck host ownership immediately before launching the sole owned process.
if ((Hash-Lf ([IO.File]::ReadAllText($Probe))) -cne $ProbeHash -or
    (Hash-Lf ([IO.File]::ReadAllText($ProbeSource))) -cne $ProbeHash) {
    throw 'Probe changed during staging; refusing uncommitted execution.'
}
$hostState = & (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
if ($hostState.status -cne 'IDLE') { throw 'Shared Unreal host became occupied during staging.' }
if ([IO.DriveInfo]::new('D:/').AvailableFreeSpace -lt 5GB) { throw 'Staging consumed the mandatory 5 GiB reserve.' }
$psi = [Diagnostics.ProcessStartInfo]::new($Editor)
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
$psi.WorkingDirectory = $Root
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$renderArguments = if ($Action -in @('settle-render','rock-render','rock-collection-render','collection-contact-render','collection-contact-review')) { @('-RenderOffscreen','-norhithread') } else { @('-NullRHI') }
foreach ($argument in (@($Project) + $renderArguments + @('-Unattended','-NoSplash','-NoSound','-NoLiveCoding','-NoP4','-NoPause',
    '-DisablePlugins=ModelContextProtocol,Wingman,AndroidFileServer',
    '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',"-ExecutePythonScript=$Probe", "-abslog=$(Join-Path $Proof "$Action-editor.log")"))) { $psi.ArgumentList.Add($argument) }
$psi.Environment.Remove('PYTHONPATH') | Out-Null
$psi.Environment.Remove('PYTHONHOME') | Out-Null
$psi.Environment['YACS_PCG_PROBE_ACTION'] = $Action
$psi.Environment['YACS_PCG_PROBE_OUTPUT'] = $Output
$psi.Environment['YACS_PCG_PROBE_EXPECTED_HEAD'] = $ExpectedHead
$process = [Diagnostics.Process]::Start($psi)
$stdout = $process.StandardOutput.ReadToEndAsync()
$stderr = $process.StandardError.ReadToEndAsync()
$watch = [Diagnostics.Stopwatch]::StartNew()
try {
    while (-not $process.WaitForExit(1000)) {
        if ($watch.Elapsed.TotalSeconds -ge 420) {
            $process.Kill() # Only the process started above; never other Editors.
            $process.WaitForExit()
            throw 'Owned native probe exceeded 420 seconds.'
        }
        if ([int]$watch.Elapsed.TotalSeconds % 30 -eq 0) { Write-Host "LOCAL_DIAGNOSTIC_ONLY $Action PID=$($process.Id) elapsed=$([int]$watch.Elapsed.TotalSeconds)s" }
    }
} finally {
    if ($process.HasExited) {
        [IO.File]::WriteAllText((Join-Path $Proof "$Action-stdout.log"),$stdout.GetAwaiter().GetResult())
        [IO.File]::WriteAllText((Join-Path $Proof "$Action-stderr.log"),$stderr.GetAwaiter().GetResult())
    }
}
if ($process.ExitCode -ne 0) { throw "Owned native probe exit=$($process.ExitCode); see $Proof" }
if (-not (Test-Path -LiteralPath $Receipt -PathType Leaf)) { throw 'Probe exited without action receipt.' }
$nativeLog = Get-Content -LiteralPath (Join-Path $Proof "$Action-editor.log") -Raw
if ($nativeLog -match "Couldn't load edit layer object|Failed to find script package for import object|Failed to compile Material") { throw 'Native consumer lost a required class/edit layer or material shader; diagnostic rejected.' }
if (($IsCollectionContact -or $IsSessionContact -or $QualificationSet -ceq 'natural20-contact') -and $nativeLog -match 'LoadErrors: While trying to load package /Game/[^\r\n]*a dependent package /Game/[^\r\n]*was not available') { throw 'Native diagnostic lost a required Game package dependency; diagnostic rejected.' }
$result = Get-Content -LiteralPath $Receipt -Raw | ConvertFrom-Json
$expectedStatus = @{inspect='NATIVE_INSPECTION_COMPLETED'; create='MECHANICAL_GRAPH_SAVED'; reload='MECHANICAL_GRAPH_FRESH_RELOAD_REGENERATED'; material='MATERIAL_BINDING_SAVED'; 'material-reload'='MATERIAL_BINDING_FRESH_READBACK'; terrain='REAL_TERRAIN_CONTACT_MEASURED'; 'settle-render'='BOULDER_FITTED_REAL_GPU_CAPTURED'; 'mask-xy-create'='MASK_XY_GRAPH_SAVED'; 'mask-xy-reload'='MASK_XY_GRAPH_FRESH_RELOAD_REGENERATED'; 'rock-qualify'='ROCK_CONTACT_MATRIX_MEASURED'; 'rock-reload'='ROCK_MESHES_FRESH_READBACK'; 'rock-render'='ROCKS_REAL_GPU_CAPTURED'; 'rock-pack'='ROCK_VARIANT_ASSETS_SAVED'; 'rock-pack-reload'='ROCK_VARIANT_ASSETS_FRESH_RELOAD_VERIFIED'; 'rock-collection'='ROCK_COLLECTION_ASSETS_SAVED'; 'rock-collection-reload'='ROCK_COLLECTION_ASSETS_FRESH_RELOAD_VERIFIED'; 'rock-collection-render'='ROCK_COLLECTION_REAL_GPU_CAPTURED'}[$Action]
if ($IsSessionContact) { $expectedStatus = @{ 'collection-contact-prepare'='COLLECTION_CONTACT_PREPARED'; 'collection-contact-measure'='COLLECTION_CONTACT_ALL_MEASURED'; 'collection-contact-review'='COLLECTION_CONTACT_REAL_GPU_CAPTURED' }[$Action] }
if ($IsCollectionContact) { $expectedStatus = if ($Action -ceq 'collection-contact-render') { 'COLLECTION_CONTACT_REAL_GPU_CAPTURED' } elseif ($Action -ceq 'collection-contact-reload') { 'COLLECTION_CONTACT_FRESH_READBACK' } elseif ($Action -ceq 'collection-contact-all') { 'COLLECTION_CONTACT_ALL_MEASURED' } else { 'COLLECTION_CONTACT_BATCH_MEASURED' } }
if ($result.status -cne $expectedStatus -or $result.code_sha -cne $ExpectedHead -or $result.placement -isnot [bool] -or $result.placement) { throw 'Native diagnostic did not complete; inspect receipt diagnostics.' }
if ($result.PSObject.Properties.Name -contains 'error') { throw 'Native diagnostic contains an error; refusing success.' }
if ($Action -in @('rock-pack','rock-pack-reload')) {
    if ($result.meshes.Count -ne 6) { throw 'Completed variant inventory count differs.' }
    foreach ($mesh in $result.meshes) {
        if ($mesh.saved_package.path -cnotmatch '^Content/Generated/YACS/PCG365RockVariants/SM_namaqualand_boulder_(02|06)_s(75|100|125)\.uasset$') { throw 'Unexpected completed variant package path.' }
        Assert-SameFile (Join-Path $Root $mesh.saved_package.path) $mesh.saved_package
    }
}
if ($Action -in @('rock-collection','rock-collection-reload')) {
    if ($result.meshes.Count -ne 20) { throw 'Completed collection inventory count differs.' }
    foreach ($mesh in $result.meshes) {
        if ($mesh.saved_package.path -cnotmatch '^Content/Generated/YACS/PCG365RockCollection20/SM_(rock(02|06)_(0[1-9]|10)|(namaqualand_boulder_0[2-6]|rock_0[79]|boulder_01)_0[1-3])\.uasset$') { throw 'Unexpected completed collection path.' }
        Assert-SameFile (Join-Path $Root $mesh.saved_package.path) $mesh.saved_package
    }
}
if ($IsSessionContact) {
    $expectedPhases = @{
        'collection-contact-prepare'=@{
            inspect='proof/inspect/inspect-receipt.json'; binding='proof/material/binding.json';
            material='proof/material/material-receipt.json'; inventory='proof/rock-collection/rock-collection-inventory.json';
            collection='proof/rock-collection/rock-collection-receipt.json'
        }
        'collection-contact-measure'=@{
            material_readback='proof/collection-contact-measure/material-fresh-phase.json';
            collection_readback='proof/collection-contact-measure/collection-fresh-phase.json';
            contact='proof/collection-contact-all/collection-contact-all-receipt.json'
        }
        'collection-contact-review'=@{
            contact_readback='proof/collection-contact-review/contact-fresh-phase.json'
        }
    }[$Action]
    if ((@($result.phases.PSObject.Properties.Name | Sort-Object) -join ',') -cne
        (@($expectedPhases.Keys | Sort-Object) -join ',')) { throw 'Final session phase receipt set differs.' }
    foreach ($key in $expectedPhases.Keys) {
        $entry = $result.phases.$key
        if ($entry.path -cne $expectedPhases[$key]) { throw "Unexpected phase path: $key" }
        Assert-SameFile (Join-Path $Root $entry.path) $entry
    }
    if ($Action -ceq 'collection-contact-prepare') {
        $binding = Get-Content (Join-Path $Proof 'material/binding.json') -Raw | ConvertFrom-Json
        $collectionInventory = Get-Content (Join-Path $Proof 'rock-collection/rock-collection-inventory.json') -Raw | ConvertFrom-Json
        if ($binding.code_sha -cne $ExpectedHead -or @($binding.saved_packages).Count -ne 7 -or
            $collectionInventory.code_sha -cne $ExpectedHead -or @($collectionInventory.meshes).Count -ne 20) {
            throw 'Prepared native Forge/collection inventory differs.'
        }
    }
    foreach ($item in $binding.saved_packages) { Assert-SameFile (Join-Path $Root $item.path) $item }
    foreach ($mesh in $collectionInventory.meshes) { Assert-SameFile (Join-Path $Root $mesh.saved_package.path) $mesh.saved_package }
    if ($Action -ceq 'collection-contact-review') {
        if (@($result.captures).Count -ne 20) { throw 'Review requires 20 real UE capture receipts.' }
        if ((@($result.captures.mesh_id | Sort-Object -Unique) -join ',') -cne
            (@($collectionInventory.meshes.id | Sort-Object -Unique) -join ',')) { throw 'Incomplete rendered mesh identities.' }
        foreach ($capture in $result.captures) {
            if ($capture.capture.status -cne 'CAPTURE_COMPLETED' -or
                @($capture.capture.frames).Count -ne 2 -or
                @($capture.capture.warmup_frames).Count -ne 2) {
                throw 'Each rock requires two native frames and two warmup frames.'
            }
            foreach ($frame in $capture.capture.frames) {
                if ($frame.file -cnotmatch '^boulder-low-angle-(01|02)\.png$' -or
                    $frame.width_px -ne 1920 -or $frame.height_px -ne 1080) {
                    throw 'Invalid native Landscape screenshot metadata.'
                }
                Assert-SameFile (Join-Path $Output "$($capture.mesh_id)/$($frame.file)") ([ordered]@{bytes=$frame.size_bytes;sha256=$frame.sha256})
            }
        }
    }
}
if ($IsCollectionContact -or $Action -eq 'rock-collection-render') { foreach ($mesh in $collectionInventory.meshes) { Assert-SameFile (Join-Path $Root $mesh.saved_package.path) $mesh.saved_package } }
if ($Action -in @('reload','mask-xy-reload')) {
    foreach ($entry in $saved.files) { Assert-SameFile (Join-Path $Root $entry.path) $entry }
}
if ($Action -in @('rock-reload','rock-render')) {
    foreach ($entry in $rockInventory.saved_packages) { Assert-SameFile (Join-Path $Root $entry.path) $entry }
}
if (($IsCollectionContact -or $Action -in @('material-reload','terrain','settle-render','rock-qualify','rock-reload','rock-render','rock-pack','rock-pack-reload','rock-collection','rock-collection-reload','rock-collection-render'))) {
    foreach ($entry in $binding.saved_packages) { Assert-SameFile (Join-Path $Root $entry.path) $entry }
}
if ($Action -eq 'rock-pack-reload') { foreach ($mesh in $packInventory.meshes) { Assert-SameFile (Join-Path $Root $mesh.saved_package.path) $mesh.saved_package } }
foreach ($entry in (Get-Content (Join-Path $Root 'staged-files.json') -Raw | ConvertFrom-Json).files) { Assert-SameFile (Join-Path $Root $entry.path) $entry.identity }
[ordered]@{code_sha=$ExpectedHead;action=$Action;exit_code=0;staged_bytes_unchanged=$true;proof_admission='LOCAL_DIAGNOSTIC_ONLY'} | ConvertTo-Json | Set-Content (Join-Path $Output 'launcher-completed.json') -Encoding utf8
Write-Host "LOCAL_DIAGNOSTIC_ONLY: $Action completed; inspect $Receipt. Native build NOT RUN."
