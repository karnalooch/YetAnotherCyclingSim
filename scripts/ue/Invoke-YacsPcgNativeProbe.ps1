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
    [ValidateSet('inspect','create','reload','material','material-reload','terrain')][string]$Action = 'inspect',
    [switch]$QualificationSources,
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
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
if ($Action -ne 'inspect') {
    if (-not (Test-Path -LiteralPath $Project -PathType Leaf)) { throw 'Create/reload requires an existing owned inspected diagnostic stage.' }
    $registry = Get-Content (Join-Path $Root 'staged-files.json') -Raw | ConvertFrom-Json
    if ($registry.expected_head -cne $ExpectedHead -or $registry.probe_sha256_lf -cne $ProbeHash) { throw 'Existing stage identity drift.' }
    foreach ($entry in $registry.files) { Assert-SameFile (Join-Path $Root $entry.path) $entry.identity }
    $inspection = Get-Content (Join-Path $Proof 'inspect/inspect-receipt.json') -Raw | ConvertFrom-Json
    if ($inspection.status -cne 'NATIVE_INSPECTION_COMPLETED') { throw 'Native inspection must complete before graph operations.' }
    $completedInspection = Get-Content (Join-Path $Proof 'inspect/launcher-completed.json') -Raw | ConvertFrom-Json
    if ($completedInspection.code_sha -cne $ExpectedHead -or $completedInspection.exit_code -ne 0) { throw 'Native inspection process did not finish cleanly.' }
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
    if ($QualificationSources) {
        $qualificationPath = Join-Path $RepoRoot 'worldgen/sa_calobra/pcg365_qualification_sources_v1.json'
        $qualification = Get-Content -LiteralPath $qualificationPath -Raw | ConvertFrom-Json
        if ($qualification.scope -cne 'LOCAL_DIAGNOSTIC_ONLY_NOT_REGIONAL_PLACEMENT' -or $qualification.terrain.assets.Count -ne 14) { throw 'Unexpected qualification source contract.' }
        Stage-QualifiedFile $qualificationPath 'qualification-sources.json' (File-Identity $qualificationPath)
        foreach ($scriptRelative in @('scripts/ue/sa_calobra_pcg_material_binding.py','scripts/ue/sa_calobra_pcg_terrain_contact.py','scripts/ue/import_material_forge_variant.py','scripts/assets/road_material_contract.py')) {
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
        Stage-QualifiedFile (Join-Path $RepoRoot $qualification.contact_input.path) 'contact-request.json' $qualification.contact_input
    }
    $plugins = @('PythonScriptPlugin','EditorScriptingUtilities','PCG','PCGToolset','PCGExtendedToolkit') | ForEach-Object { [ordered]@{Name=$_;Enabled=$true;Optional=$false} }
    [ordered]@{FileVersion=3;EngineAssociation='5.8';Category='';Description='YACS #365 owned local diagnostic';Plugins=@($plugins)} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Project -Encoding utf8
    $entries.Add([ordered]@{path='Pcg365Diagnostic.uproject';identity=(File-Identity $Project)})
    [ordered]@{status='LOCAL_DIAGNOSTIC_ONLY';expected_head=$ExpectedHead;probe_sha256_lf=$ProbeHash;plugin_pin=$bootstrap.actual_commit;plugin_patch=$bootstrap.compatibility_patch_sha256;binary_provenance='retained prebuilt; not an exact-head native build';engine_build_id=$EngineModules.BuildId;files=$entries} | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $Root 'staged-files.json') -Encoding utf8
}
New-Item -ItemType Directory -Path $Proof -Force | Out-Null
$Output = Join-Path $Proof $Action
$Receipt = Join-Path $Output "$Action-receipt.json"
if ($Action -eq 'reload') {
    $saved = Get-Content (Join-Path $Proof 'create/saved-packages.json') -Raw | ConvertFrom-Json
    if ($saved.code_sha -cne $ExpectedHead -or $saved.files.Count -ne 2) { throw 'Saved mechanical package identity mismatch.' }
    if (@($saved.files.path | Sort-Object -Unique).Count -ne 2) { throw 'Duplicate saved mechanical package path.' }
    foreach ($entry in $saved.files) {
        if ([string]$entry.path -notmatch '^Content/Generated/YACS/PCG365Mechanical/(PCG_XYFixture\.uasset|L_XYFixture\.umap)$') { throw 'Unexpected mechanical package path.' }
        Assert-SameFile (Join-Path $Root $entry.path) $entry
    }
}
if ($Action -in @('material','material-reload','terrain') -and -not (Test-Path -LiteralPath (Join-Path $Root 'qualification-sources.json'))) { throw 'Qualification sources were not staged.' }
if ($Action -in @('material-reload','terrain')) {
    $materialCompleted = Get-Content (Join-Path $Proof 'material/launcher-completed.json') -Raw | ConvertFrom-Json
    if ($materialCompleted.code_sha -cne $ExpectedHead -or $materialCompleted.exit_code -ne 0) { throw 'Material save process did not complete cleanly.' }
    $binding = Get-Content (Join-Path $Proof 'material/binding.json') -Raw | ConvertFrom-Json
    if ($binding.code_sha -cne $ExpectedHead -or $binding.saved_packages.Count -ne 7) { throw 'Unexpected saved material inventory.' }
    foreach ($entry in $binding.saved_packages) {
        if ($entry.path -notmatch '^Content/Generated/YACS/PCG365Qualification/[^:]+\.uasset$' -or $entry.path -match '\.\.') { throw 'Unsafe material package path.' }
        Assert-SameFile (Join-Path $Root $entry.path) $entry
    }
}
if ($Action -eq 'terrain') {
    $materialReloadCompleted = Get-Content (Join-Path $Proof 'material-reload/launcher-completed.json') -Raw | ConvertFrom-Json
    if ($materialReloadCompleted.code_sha -cne $ExpectedHead -or $materialReloadCompleted.exit_code -ne 0) { throw 'Material fresh readback must complete before terrain measurement.' }
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
foreach ($argument in @($Project,'-NullRHI','-Unattended','-NoSplash','-NoSound','-NoLiveCoding','-NoP4','-NoPause',
    '-DisablePlugins=ModelContextProtocol,Wingman,AndroidFileServer',
    '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',"-ExecutePythonScript=$Probe", "-abslog=$(Join-Path $Proof "$Action-editor.log")")) { $psi.ArgumentList.Add($argument) }
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
$result = Get-Content -LiteralPath $Receipt -Raw | ConvertFrom-Json
$expectedStatus = @{inspect='NATIVE_INSPECTION_COMPLETED'; create='MECHANICAL_GRAPH_SAVED'; reload='MECHANICAL_GRAPH_FRESH_RELOAD_REGENERATED'; material='MATERIAL_BINDING_SAVED'; 'material-reload'='MATERIAL_BINDING_FRESH_READBACK'; terrain='REAL_TERRAIN_CONTACT_MEASURED'}[$Action]
if ($result.status -cne $expectedStatus -or $result.code_sha -cne $ExpectedHead -or $result.placement -isnot [bool] -or $result.placement) { throw 'Native diagnostic did not complete; inspect receipt diagnostics.' }
if ($result.PSObject.Properties.Name -contains 'error') { throw 'Native diagnostic contains an error; refusing success.' }
if ($Action -eq 'reload') {
    foreach ($entry in $saved.files) { Assert-SameFile (Join-Path $Root $entry.path) $entry }
}
if ($Action -in @('material-reload','terrain')) {
    foreach ($entry in $binding.saved_packages) { Assert-SameFile (Join-Path $Root $entry.path) $entry }
}
foreach ($entry in (Get-Content (Join-Path $Root 'staged-files.json') -Raw | ConvertFrom-Json).files) { Assert-SameFile (Join-Path $Root $entry.path) $entry.identity }
[ordered]@{code_sha=$ExpectedHead;exit_code=0;staged_bytes_unchanged=$true;proof_admission='LOCAL_DIAGNOSTIC_ONLY'} | ConvertTo-Json | Set-Content (Join-Path $Output 'launcher-completed.json') -Encoding utf8
Write-Host "LOCAL_DIAGNOSTIC_ONLY: $Action completed; inspect $Receipt. Native build NOT RUN."
