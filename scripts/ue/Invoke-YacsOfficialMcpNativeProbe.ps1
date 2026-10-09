#requires -Version 7.4
<#
.SYNOPSIS
    Build the opt-in #384 plugin and prove its input boundary in a bare project.
.DESCRIPTION
    Exact tracked inputs, canonical UE 5.8.2 / CL 56702186 and an idle host only.
    BuildPlugin uses a fresh short retained runner path. One owned Editor-Cmd
    process runs InputBoundary on Entry; optional Python reflection shares it.
    No accepted scene, live project, MCP transport or performance admission.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string] $ExpectedHead
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$PluginRelative = 'Plugins/YacsBobInspection/YacsBobInspection.uplugin'
$PluginPrefix = 'Plugins/YacsBobInspection/'
$ProjectPath = Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject'
$TestName = 'YacsBobInspection.InputBoundary'
if (-not $IsWindows) { throw 'The native BOB probe requires Windows.' }

function Assert-ProbePlainPath {
    param([Parameter(Mandatory)][string] $Path)
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Native proof paths cannot use symlinks or junctions.'
            }
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}
function Get-ProbeFileIdentity {
    param([Parameter(Mandatory)][string] $Path)
    Assert-ProbePlainPath $Path
    $entry = Get-Item -LiteralPath $Path -Force
    if ($entry.PSIsContainer) { throw 'A native proof file is unexpectedly a directory.' }
    return [ordered]@{
        path = [IO.Path]::GetFullPath($Path)
        size_bytes = $entry.Length
        sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
function Write-ProbeJson {
    param([Parameter(Mandatory)][string] $Path, [Parameter(Mandatory)] $Value)
    Assert-ProbePlainPath $Path
    if (Test-Path -LiteralPath $Path) { throw 'Native proof cannot replace an existing evidence file.' }
    [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
}
function Assert-ProbeDiskFloor {
    param([Parameter(Mandatory)][string] $Path)
    $driveName = [IO.Path]::GetPathRoot($Path).TrimEnd('\').TrimEnd(':')
    if ((Get-PSDrive -Name $driveName).Free -lt 5GB) {
        throw 'Native proof requires 5 GiB free on its output drive; retain existing output.'
    }
}
function Assert-ProbeIdleHost {
    $state = & (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
    $receipt.host_checked_at_utc = $state.checked_at_utc
    $receipt.host_status = $state.status
    # The classifier also owns process metadata. Never print/retain command lines.
    if ($state.status -cne 'IDLE') { throw "Native proof yields to the Unreal host owner: $($state.status)." }
}
function Test-ProbeNonnegativeInteger {
    param($Value)
    return (($Value -is [int] -or $Value -is [long]) -and $Value -ge 0)
}
function Get-ProbeMacroClosingParenthesis {
    param([Parameter(Mandatory)][string] $Code, [int] $OpeningIndex)
    if ($Code[$OpeningIndex] -ne '(') { throw 'Expected a native declaration opening parenthesis.' }
    $depth = 1
    for ($index = $OpeningIndex + 1; $index -lt $Code.Length; $index++) {
        if ($Code[$index] -eq '(') { $depth++ }
        elseif ($Code[$index] -eq ')') { $depth--; if ($depth -eq 0) { return $index } }
    }
    throw 'Native settings declaration has an incomplete annotation.'
}
function Get-ProbeTopLevelMetadata {
    param([Parameter(Mandatory)][string] $Metadata)
    $result = [Text.StringBuilder]::new()
    $depth = 0
    foreach ($character in $Metadata.ToCharArray()) {
        if ($character -eq '(') { $depth++; [void]$result.Append(' ') }
        elseif ($character -eq ')') { $depth--; [void]$result.Append(' ') }
        elseif ($depth -eq 0) { [void]$result.Append($character) }
        else { [void]$result.Append(' ') }
    }
    return $result.ToString()
}

if ($env:GITHUB_RUN_ID -notmatch '^[0-9]{1,20}$' -or $env:GITHUB_RUN_ATTEMPT -notmatch '^[0-9]{1,4}$') {
    throw 'Native proof requires the bounded Actions run identity.'
}
$runIdentity = "$env:GITHUB_RUN_ID-$env:GITHUB_RUN_ATTEMPT"
$ArtifactRoot = Join-Path $RepoRoot "Saved/RuntimeProof/OfficialMcpNativeProbe/$runIdentity"
Assert-ProbePlainPath $ArtifactRoot
if (Test-Path -LiteralPath $ArtifactRoot) { throw 'Native proof destination already exists.' }
Push-Location -LiteralPath $RepoRoot
try {
    & git check-ignore --no-index --quiet -- (Join-Path $ArtifactRoot 'native-plugin-build.json')
    if ($LASTEXITCODE -ne 0) { throw 'Native proof destination is not Git-ignored.' }
}
finally { Pop-Location }
New-Item -ItemType Directory -Path $ArtifactRoot | Out-Null
$receipt = [ordered]@{
    schema_version = 1
    exact_sha = $ExpectedHead
    status = 'PREFLIGHT_PENDING'
    engine_identity = $null
    engine_version = $null
    source_sha256 = [ordered]@{}
    staged_tracked_plugin_only = $false
    package_root = $null
    host_project_root = $null
    retained_short_run_root = $null
    planned_action_path_length = $null
    host_checked_at_utc = $null
    host_status = $null
    dependency_preflights = [ordered]@{}
    python_reflection_requested = $false
    python_reflection_blocked_reason = $null
    python_remote_execution_config_verified = $false
    source_unchanged = $false
    compile_pass = $false
    native_input_boundary_verified = $false
    native_python_reflection_verified = $false
    owned_editor_pid = $null
    owned_editor_exit_code = $null
    owned_editor_timed_out = $false
    proof_files = [ordered]@{}
    host_project_plugin_list = @()
    host_project_source_sha256 = [ordered]@{}
    native_registry_dispatch_verified = $false
    official_mcp_transport_verified = $false
    native_bob_capture_verified = $false
    existing_project_test_verified = $false
    accepted_checkpoint_verified = $false
    official_mcp_admitted = $false
    persistent_world_mutation = $false
    performance_pass = $false
    performance_status = 'DEFERRED_AFTER_M3'
    error = $null
}
$ownedEditor = $null
try {
    $requiredInputs = @(
        $PluginRelative,
        'scripts/ue/Invoke-YacsOfficialMcpNativeProbe.ps1',
        'scripts/ue/Read-YacsOfficialMcpRuntimeDependencies.ps1',
        'scripts/ue/Read-YacsAcceptedMaterialCheckpoint.ps1',
        'scripts/ue/probe_official_mcp_bob_reflection.py',
        'scripts/ci/Resolve-YacsUnrealEngine.ps1',
        'scripts/ci/Test-YacsCodeOnlyCheckout.ps1',
        'scripts/runner/Get-YacsUnrealHostState.ps1',
        '.github/workflows/official-unreal-mcp-native-probe.yml',
        'YetAnotherCyclingSim.uproject'
    )
    Push-Location -LiteralPath $RepoRoot
    try {
        $actualHead = (& git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or $actualHead -cne $ExpectedHead) { throw 'Native proof HEAD is not its exact requested SHA.' }
        $trackedChanges = @(& git status --porcelain --untracked-files=no)
        if ($LASTEXITCODE -ne 0 -or $trackedChanges.Count) { throw 'Native proof requires unchanged tracked source.' }
        $SourcePaths = @(& git ls-files -- 'Plugins/YacsBobInspection' @requiredInputs)
        if ($LASTEXITCODE -ne 0) { throw 'Cannot establish the native proof tracked source inventory.' }
        foreach ($required in $requiredInputs) {
            if ($required -cnotin $SourcePaths) { throw "Native proof required input is not tracked: $required" }
        }
    }
    finally { Pop-Location }
    function Get-ProbeSourceHashes {
        $hashes = [ordered]@{}
        foreach ($relative in $SourcePaths) {
            $hashes[$relative] = (Get-ProbeFileIdentity (Join-Path $RepoRoot $relative)).sha256
        }
        return $hashes
    }
    $SourceHashes = Get-ProbeSourceHashes
    $receipt.source_sha256 = $SourceHashes
    . (Join-Path $RepoRoot 'scripts/ci/Resolve-YacsUnrealEngine.ps1')
    $engine = Resolve-YacsUnrealEngine -ProjectPath $ProjectPath
    if (-not $engine -or $engine.Version -cne '5.8.2-56702186') {
        throw 'Native proof requires canonical UE 5.8.2 / CL 56702186.'
    }
    foreach ($path in @($engine.Root, $engine.UATPath, $engine.UnrealEditorCmdPath)) { Assert-ProbePlainPath $path }
    $receipt.engine_identity = $engine.Identity
    $receipt.engine_version = $engine.Version
    $descriptor = Get-Content -LiteralPath (Join-Path $RepoRoot $PluginRelative) -Raw | ConvertFrom-Json -AsHashtable
    if ($descriptor.EnabledByDefault -ne $false -or $descriptor.CanContainContent -ne $false `
        -or @($descriptor.Modules).Count -ne 1 -or $descriptor.Modules[0].Name -cne 'YacsBobInspection' `
        -or $descriptor.Modules[0].Type -cne 'Editor' -or $descriptor.Modules[0].LoadingPhase -cne 'PostEngineInit') {
        throw 'Native plugin must remain disabled by default, Editor-only and content-free.'
    }
    Assert-ProbeIdleHost

    # This fixed child is authorized retained runner output, never RUNNER_TEMP
    # (Actions clears that directory). Preserve all previous run directories.
    if (-not $env:GITHUB_WORKSPACE) { throw 'Native proof lacks its canonical Actions workspace.' }
    $githubWorkspace = [IO.Path]::GetFullPath($env:GITHUB_WORKSPACE).TrimEnd('\')
    $workRoot = [IO.Path]::GetDirectoryName([IO.Path]::GetDirectoryName($githubWorkspace))
    if (-not [string]::Equals($workRoot, 'D:\yacs\runner\_work', [StringComparison]::OrdinalIgnoreCase) `
        -or -not [string]::Equals($RepoRoot, (Join-Path $githubWorkspace '_official-mcp-native-probe'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Native proof may use only the canonical runner _work checkout and its fixed b384 output child.'
    }
    Assert-ProbePlainPath $workRoot
    $shortParent = Join-Path $workRoot 'b384'
    $shortRunRoot = Join-Path $shortParent $runIdentity
    $package = Join-Path $shortRunRoot 'p'
    $HostProjectRoot = Join-Path $package 'HostProject'
    $HostProjectPath = Join-Path $HostProjectRoot 'HostProject.uproject'
    Assert-ProbePlainPath $shortRunRoot
    if (Test-Path -LiteralPath $shortRunRoot) { throw 'Short retained native proof run destination already exists.' }
    if ([IO.Path]::GetPathRoot($package) -ine [IO.Path]::GetPathRoot($engine.Root)) {
        throw 'The short native package must use the canonical engine drive.'
    }
    Assert-ProbeDiskFloor $RepoRoot
    Assert-ProbeDiskFloor $package
    $actionExample = Join-Path $package 'HostProject/Plugins/YacsBobInspection/Intermediate/Build/Win64/x64/UnrealEditor/Development/YacsBobInspection/Module.YacsBobInspection.cpp.obj.rsp'
    if ($actionExample.Length -ge 240) { throw 'The retained package root is still too long for bounded Windows UBT action paths.' }
    if (-not (Test-Path -LiteralPath $shortParent)) { New-Item -ItemType Directory -Path $shortParent | Out-Null }
    New-Item -ItemType Directory -Path $shortRunRoot | Out-Null
    $receipt.retained_short_run_root = $shortRunRoot
    $receipt.package_root = $package
    $receipt.host_project_root = $HostProjectRoot
    $receipt.planned_action_path_length = $actionExample.Length

    # Evidence gaps cannot admit runtime and do not prevent independent compile.
    foreach ($preflight in @(
        @{ name = 'runtime_dependencies'; script = 'Read-YacsOfficialMcpRuntimeDependencies.ps1' },
        @{ name = 'accepted_363'; script = 'Read-YacsAcceptedMaterialCheckpoint.ps1' }
    )) {
        try {
            $readerPath = Join-Path $PSScriptRoot $preflight.script
            if ($preflight.name -ceq 'runtime_dependencies') {
                & $readerPath -EngineRoot $engine.Root -ArtifactRoot $ArtifactRoot -ExpectedHead $ExpectedHead
            }
            else { & $readerPath -ArtifactRoot $ArtifactRoot }
            $receipt.dependency_preflights[$preflight.name] = @{ invocation_completed = $true; admission = $false }
        }
        catch {
            # Readers retain their own bounded failure receipt. Never serialize
            # a network exception here, since it may contain a signed URL.
            $receipt.dependency_preflights[$preflight.name] = @{ invocation_completed = $false; admission = $false; gap = 'Fixed dependency reader failed; inspect its retained receipt.' }
            Write-Host "Fixed dependency preflight incomplete: $($preflight.name); standalone input-boundary proof continues."
        }
    }

    # Read exactly this installed declaration, as data, before any Python opt-in.
    # An absent/unproved declaration disables only the reflection sub-proof.
    $settingsPath = Join-Path $engine.Root 'Engine/Plugins/Experimental/PythonScriptPlugin/Source/PythonScriptPlugin/Public/PythonScriptPluginSettings.h'
    $settingsEvidence = [ordered]@{
        schema_version = 1; exact_sha = $ExpectedHead; path = $settingsPath
        status = 'UNESTABLISHED'; source_sha256 = $null; config_engine = $false
        public_config_remote_execution = $false; context = @(); error = $null
        official_mcp_admitted = $false; persistent_world_mutation = $false
    }
    try {
        Assert-ProbePlainPath $settingsPath
        if (-not (Test-Path -LiteralPath $settingsPath -PathType Leaf)) { throw 'Fixed Python settings header is absent.' }
        $settingsIdentity = Get-ProbeFileIdentity $settingsPath
        if ($settingsIdentity.size_bytes -gt 256KB) { throw 'Fixed Python settings header exceeds 256 KiB.' }
        $settingsEvidence.source_sha256 = $settingsIdentity.sha256
        $stream = [IO.File]::OpenRead($settingsPath)
        try {
            $settingsBuffer = [byte[]]::new(256KB + 1)
            $settingsCount = 0
            while (($readCount = $stream.Read($settingsBuffer, $settingsCount, $settingsBuffer.Length - $settingsCount)) -gt 0) {
                $settingsCount += $readCount
                if ($settingsCount -gt 256KB) { throw 'Fixed Python settings read exceeds 256 KiB.' }
            }
            $settingsBytes = [byte[]]::new($settingsCount)
            [Array]::Copy($settingsBuffer, $settingsBytes, $settingsCount)
        }
        finally { $stream.Dispose() }
        $settingsSource = [Text.UTF8Encoding]::new($false, $true).GetString($settingsBytes)
        $settingsCode = [regex]::Replace($settingsSource, '(?s)/\*.*?\*/|//(?:\\\r?\n|[^\r\n])*|"(?:\\.|[^"\\])*"|''(?:\\.|[^''\\])*''', {
            param($match)
            return [regex]::Replace($match.Value, '[^\r\n]', ' ')
        })
        $classMatches = @()
        foreach ($annotation in [regex]::Matches($settingsCode, '\bUCLASS\s*\(')) {
            $opening = $annotation.Index + $annotation.Length - 1
            $closing = Get-ProbeMacroClosingParenthesis $settingsCode $opening
            $declaration = [regex]::Match($settingsCode.Substring($closing + 1), '(?s)^\s*class\s+(?:\w+_API\s+)?UPythonScriptPluginSettings\b[^;{]*\{')
            if ($declaration.Success) {
                $metadata = Get-ProbeTopLevelMetadata ($settingsCode.Substring($opening + 1, $closing - $opening - 1))
                $classMatches += @{ annotation = $annotation; declaration = $declaration; metadata = $metadata; body_start = $closing + 1 + $declaration.Length }
            }
        }
        # Retain only short actual source contexts, including failed selectors.
        $lines = $settingsSource -split '\r?\n'
        $contextNumbers = [Collections.Generic.SortedSet[int]]::new()
        foreach ($anchor in [regex]::Matches($settingsCode, '\b(?:UPythonScriptPluginSettings|bRemoteExecution)\b')) {
            $anchorLine = @($settingsCode.Substring(0, $anchor.Index) -split '\n').Count
            for ($line = [Math]::Max(1, $anchorLine - 3); $line -le [Math]::Min($anchorLine + 3, $lines.Length); $line++) {
                if ($contextNumbers.Count -lt 30) { [void]$contextNumbers.Add($line) }
            }
        }
        foreach ($line in $contextNumbers) { $settingsEvidence.context += ('{0}: {1}' -f $line, $lines[$line - 1]) }
        if ($classMatches.Count -ne 1 -or $classMatches[0].metadata -notmatch '(?:^|,)\s*(?i:Config)\s*=\s*Engine\s*(?:,|$)') {
            throw 'Actual UPythonScriptPluginSettings Config=Engine declaration is unestablished.'
        }
        $start = $classMatches[0].body_start
        $depth = 1
        $end = $start
        while ($end -lt $settingsCode.Length -and $depth -gt 0) {
            if ($settingsCode[$end] -eq '{') { $depth++ }
            elseif ($settingsCode[$end] -eq '}') { $depth-- }
            $end++
        }
        if ($depth -ne 0) { throw 'Fixed Python settings class body is incomplete.' }
        $body = $settingsCode.Substring($start, $end - $start - 1)
        $properties = @()
        foreach ($annotation in [regex]::Matches($body, '\bUPROPERTY\s*\(')) {
            $opening = $annotation.Index + $annotation.Length - 1
            $closing = Get-ProbeMacroClosingParenthesis $body $opening
            $declaration = [regex]::Match($body.Substring($closing + 1), '^\s*bool\s+bRemoteExecution\s*(?:=\s*(?:true|false)\s*)?;')
            if ($declaration.Success) {
                $metadata = Get-ProbeTopLevelMetadata ($body.Substring($opening + 1, $closing - $opening - 1))
                $properties += @{ annotation_index = $annotation.Index; metadata = $metadata }
            }
        }
        if ($properties.Count -ne 1 -or $properties[0].metadata -notmatch '(?:^|,)\s*(?i:Config)\s*(?:,|$)') {
            throw 'Actual Config bool bRemoteExecution declaration is unestablished.'
        }
        $visibility = [regex]::Matches($body.Substring(0, $properties[0].annotation_index), '\b(public|protected|private)\s*:')
        if ($visibility.Count -eq 0 -or $visibility[$visibility.Count - 1].Groups[1].Value -cne 'public') {
            throw 'Actual bRemoteExecution declaration is not established public.'
        }
        if ((Get-ProbeFileIdentity $settingsPath).sha256 -cne $settingsIdentity.sha256) {
            throw 'Fixed Python settings source changed during the preflight read.'
        }
        $settingsEvidence.status = 'SOURCE_DECLARATION_VERIFIED'
        $settingsEvidence.source_sha256 = $settingsIdentity.sha256
        $settingsEvidence.config_engine = $true
        $settingsEvidence.public_config_remote_execution = $true
        $receipt.python_reflection_requested = $true
        $receipt.python_remote_execution_config_verified = $true
    }
    catch {
        $settingsEvidence.error = $_.Exception.Message
        $receipt.python_reflection_blocked_reason = $_.Exception.Message
        Write-Host "Native Python reflection unavailable: $($_.Exception.Message)"
    }
    Write-ProbeJson (Join-Path $ArtifactRoot 'python-runtime-settings.json') $settingsEvidence
    foreach ($line in $settingsEvidence.context) { Write-Host $line }

    # A fresh staged plugin contains only tracked exact-SHA source files.
    $StagedPluginRoot = Join-Path $ArtifactRoot 'InputPlugin/YacsBobInspection'
    foreach ($relative in $SourcePaths) {
        if (-not $relative.StartsWith($PluginPrefix, [StringComparison]::Ordinal)) { continue }
        $target = Join-Path $StagedPluginRoot $relative.Substring($PluginPrefix.Length)
        New-Item -ItemType Directory -Path (Split-Path -Path $target -Parent) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $RepoRoot $relative) -Destination $target
        if ((Get-ProbeFileIdentity $target).sha256 -cne $SourceHashes[$relative]) { throw 'Staged native source differs from exact tracked input.' }
    }
    $receipt.staged_tracked_plugin_only = $true
    $receipt.status = 'BUILD_PENDING'
    Assert-ProbeIdleHost
    & $engine.UATPath BuildPlugin "-Plugin=$(Join-Path $StagedPluginRoot 'YacsBobInspection.uplugin')" "-Package=$package" `
        -TargetPlatforms=Win64 -StrictIncludes -NoDeleteHostProject 2>&1 |
        Tee-Object -FilePath (Join-Path $ArtifactRoot 'native-plugin-build.log')
    if ($LASTEXITCODE -ne 0) { throw 'Isolated YacsBobInspection BuildPlugin failed.' }
    Assert-ProbePlainPath $HostProjectPath
    if (-not (Test-Path -LiteralPath $HostProjectPath -PathType Leaf)) { throw 'BuildPlugin did not retain its bare HostProject.' }

    function Assert-ProbeInputsUnchanged {
        $afterHashes = Get-ProbeSourceHashes
        foreach ($relative in $SourcePaths) {
            if ($SourceHashes[$relative] -cne $afterHashes[$relative]) { throw 'Tracked native proof source changed.' }
            if ($relative.StartsWith($PluginPrefix, [StringComparison]::Ordinal)) {
                $suffix = $relative.Substring($PluginPrefix.Length)
                foreach ($root in @($StagedPluginRoot, (Join-Path $HostProjectRoot 'Plugins/YacsBobInspection'))) {
                    if ((Get-ProbeFileIdentity (Join-Path $root $suffix)).sha256 -cne $SourceHashes[$relative]) {
                        throw 'Staged or bare HostProject native source differs from its tracked input.'
                    }
                }
            }
        }
    }
    Assert-ProbeInputsUnchanged
    $receipt.source_unchanged = $true
    $receipt.compile_pass = $true
    $receipt.status = 'NATIVE_PLUGIN_COMPILED'
    $hostOriginal = Get-ProbeFileIdentity $HostProjectPath
    Copy-Item -LiteralPath $HostProjectPath -Destination (Join-Path $ArtifactRoot 'host-project-original.json')
    $receipt.proof_files.host_project_original = $hostOriginal
    $hostDescriptor = Get-Content -LiteralPath $HostProjectPath -Raw | ConvertFrom-Json -AsHashtable
    if ($hostDescriptor.Contains('Modules') -and ($hostDescriptor.Modules -isnot [array] -or $hostDescriptor.Modules.Count -gt 0)) { throw 'The generated HostProject is not a bare plugin host.' }
    if ($hostDescriptor.Contains('Plugins') -and $hostDescriptor.Plugins -isnot [array]) { throw 'Generated HostProject plugins must be a list.' }
    $hostPlugins = @()
    if ($hostDescriptor.Contains('Plugins')) {
        $hostPlugins = @($hostDescriptor.Plugins | Where-Object { $_.Name -cnotin @('YacsBobInspection', 'PythonScriptPlugin', 'ModelContextProtocol') })
    }
    $hostPlugins += @{ Name = 'YacsBobInspection'; Enabled = $true }
    $hostPlugins += @{ Name = 'PythonScriptPlugin'; Enabled = [bool]$receipt.python_reflection_requested }
    $hostPlugins += @{ Name = 'ModelContextProtocol'; Enabled = $false }
    $hostDescriptor.Plugins = $hostPlugins
    # Preserve other engine defaults/dependencies; only these explicit opt-ins
    # and official MCP transport opt-out belong to this generated project.
    [IO.File]::WriteAllText($HostProjectPath, ($hostDescriptor | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
    Copy-Item -LiteralPath $HostProjectPath -Destination (Join-Path $ArtifactRoot 'host-project-probe.json')
    $hostProbe = Get-ProbeFileIdentity $HostProjectPath
    $receipt.proof_files.host_project_probe = $hostProbe
    $receipt.host_project_plugin_list = $hostPlugins
    $protectedHostFiles = [ordered]@{ descriptor = $HostProjectPath }
    $dllPath = Join-Path $HostProjectRoot 'Plugins/YacsBobInspection/Binaries/Win64/UnrealEditor-YacsBobInspection.dll'
    $protectedHostFiles.native_plugin_dll = $dllPath

    $entryMap = Join-Path $engine.Root 'Engine/Content/Maps/Entry.umap'
    Assert-ProbePlainPath $entryMap
    if (-not (Test-Path -LiteralPath $entryMap -PathType Leaf)) { throw 'Fixed /Engine/Maps/Entry map is not present in the admitted engine.' }
    $receipt.proof_files.entry_map = Get-ProbeFileIdentity $entryMap
    $reflectionScript = Join-Path $PSScriptRoot 'probe_official_mcp_bob_reflection.py'
    if ($receipt.python_reflection_requested) {
        $configPath = Join-Path $HostProjectRoot 'Config/DefaultEngine.ini'
        Assert-ProbePlainPath $configPath
        if (Test-Path -LiteralPath $configPath) { throw 'Fresh bare HostProject already has DefaultEngine.ini; preserve it for review.' }
        New-Item -ItemType Directory -Path (Split-Path -Path $configPath -Parent) -Force | Out-Null
        [IO.File]::WriteAllText($configPath, "[/Script/PythonScriptPlugin.PythonScriptPluginSettings]`nbRemoteExecution=False`n", [Text.UTF8Encoding]::new($false))
        $protectedHostFiles.python_config = $configPath
        $markerPath = Join-Path $HostProjectRoot '.yacs-mcp-native-reflection-proof.json'
        $marker = [ordered]@{
            schema_version = 1; exact_sha = $ExpectedHead
            host_project_root = $HostProjectRoot; artifact_root = $ArtifactRoot
            script_sha256 = $SourceHashes['scripts/ue/probe_official_mcp_bob_reflection.py']
            public_header_sha256 = $SourceHashes['Plugins/YacsBobInspection/Source/YacsBobInspection/Public/YacsBobLandscapeHit.h']
            plugin_descriptor_sha256 = $SourceHashes[$PluginRelative]
            host_project_descriptor_sha256 = $hostProbe.sha256
            host_engine_config_sha256 = (Get-ProbeFileIdentity $configPath).sha256
        }
        Write-ProbeJson $markerPath $marker
        $protectedHostFiles.reflection_marker = $markerPath
    }
    foreach ($key in $protectedHostFiles.Keys) {
        $receipt.host_project_source_sha256[$key] = (Get-ProbeFileIdentity $protectedHostFiles[$key]).sha256
    }

    $reportRoot = Join-Path $ArtifactRoot 'InputBoundaryReport'
    New-Item -ItemType Directory -Path $reportRoot | Out-Null
    $editorLog = Join-Path $ArtifactRoot 'input-boundary-editor.log'
    $stdoutLog = Join-Path $ArtifactRoot 'input-boundary-stdout.log'
    $stderrLog = Join-Path $ArtifactRoot 'input-boundary-stderr.log'
    $editorArgs = @(
        ('"' + $HostProjectPath + '"'), '/Engine/Maps/Entry',
        '-Unattended', '-NoPause', '-NullRHI', '-NoSplash', '-NoSound', '-log',
        ('-AbsLog="' + $editorLog + '"'), ('-ReportExportPath="' + $reportRoot + '"'),
        ('-execcmds="Automation RunTests ' + $TestName + ';Quit"')
    )
    if ($receipt.python_reflection_requested) {
        $editorArgs += ('-ExecutePythonScript="' + $reflectionScript + '"')
        $editorArgs += '-ScriptErrorsAreFatal'
    }
    Assert-ProbeInputsUnchanged
    Assert-ProbeIdleHost
    Assert-ProbeDiskFloor $package
    $environmentNames = @('YACS_MCP_NATIVE_HOST_PROJECT_ROOT', 'YACS_MCP_NATIVE_ARTIFACT_ROOT', 'YACS_MCP_NATIVE_EXPECTED_HEAD', 'YACS_CHECKPOINT_READ_TOKEN')
    $previousEnvironment = @{}
    foreach ($name in $environmentNames) { $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
    try {
        [Environment]::SetEnvironmentVariable('YACS_MCP_NATIVE_HOST_PROJECT_ROOT', $HostProjectRoot, 'Process')
        [Environment]::SetEnvironmentVariable('YACS_MCP_NATIVE_ARTIFACT_ROOT', $ArtifactRoot, 'Process')
        [Environment]::SetEnvironmentVariable('YACS_MCP_NATIVE_EXPECTED_HEAD', $ExpectedHead, 'Process')
        [Environment]::SetEnvironmentVariable('YACS_CHECKPOINT_READ_TOKEN', $null, 'Process')
        $ownedEditor = Start-Process -FilePath $engine.UnrealEditorCmdPath -ArgumentList $editorArgs `
            -WorkingDirectory $HostProjectRoot -NoNewWindow -PassThru `
            -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog
    }
    finally {
        foreach ($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process') }
    }
    $receipt.owned_editor_pid = $ownedEditor.Id
    $receipt.status = 'INPUT_BOUNDARY_PENDING'
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $nextHeartbeat = 30
    while (-not $ownedEditor.WaitForExit(2000)) {
        if ($timer.Elapsed.TotalSeconds -ge 180) {
            $receipt.owned_editor_timed_out = $true
            throw 'The owned bare HostProject Editor exceeded the 180 second input-boundary proof limit.'
        }
        if ($timer.Elapsed.TotalSeconds -ge $nextHeartbeat) {
            Write-Host ("InputBoundary heartbeat: owned PID {0}, elapsed {1:N0}s." -f $ownedEditor.Id, $timer.Elapsed.TotalSeconds)
            $nextHeartbeat += 30
        }
    }
    $ownedEditor.WaitForExit()
    $receipt.owned_editor_exit_code = $ownedEditor.ExitCode
    if ($null -eq $ownedEditor.ExitCode -or $ownedEditor.ExitCode -ne 0) { throw 'The owned bare HostProject Editor did not exit successfully.' }
    Assert-ProbeInputsUnchanged
    foreach ($key in $protectedHostFiles.Keys) {
        if ((Get-ProbeFileIdentity $protectedHostFiles[$key]).sha256 -cne $receipt.host_project_source_sha256[$key]) {
            throw 'A generated HostProject proof input changed during the owned Editor session.'
        }
    }
    if ((Get-ProbeFileIdentity $entryMap).sha256 -cne $receipt.proof_files.entry_map.sha256) { throw 'Entry map changed during the isolated proof.' }
    $indexPath = Join-Path $reportRoot 'index.json'
    $indexIdentity = Get-ProbeFileIdentity $indexPath
    if ($indexIdentity.size_bytes -gt 8MB) { throw 'InputBoundary report exceeds 8 MiB.' }
    $index = Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json -AsHashtable
    if ($index -isnot [Collections.IDictionary] -or $index.tests -isnot [array] -or $index.tests.Count -ne 1) {
        throw 'InputBoundary requires exactly one real Automation report test.'
    }
    $test = $index.tests[0]
    if ($test.fullTestPath -cne $TestName -or $test.state -cne 'Success' `
        -or -not (Test-ProbeNonnegativeInteger $test.errors) -or $test.errors -ne 0) {
        throw 'The exact InputBoundary Automation test must report Success and zero errors.'
    }
    foreach ($counter in @('succeeded', 'succeededWithWarnings', 'failed', 'notRun', 'inProcess')) {
        if (-not (Test-ProbeNonnegativeInteger $index[$counter])) { throw 'InputBoundary report has malformed counters.' }
    }
    if (($index.succeeded + $index.succeededWithWarnings) -ne 1 -or $index.failed -ne 0 -or $index.notRun -ne 0 -or $index.inProcess -ne 0) {
        throw 'InputBoundary Automation summary did not finish exactly one successful test.'
    }
    if ($test.entries -isnot [array]) { throw 'InputBoundary Automation entries are malformed.' }
    foreach ($entry in $test.entries) {
        if ($entry -isnot [Collections.IDictionary] -or $entry.event -isnot [Collections.IDictionary] -or $entry.event.type -isnot [string]) {
            throw 'InputBoundary Automation event is malformed.'
        }
        if ($entry.event.type -ceq 'Error') { throw 'InputBoundary Automation includes an error event.' }
    }
    if ((Get-ProbeFileIdentity $indexPath).sha256 -cne $indexIdentity.sha256) { throw 'InputBoundary report changed during verification.' }
    $receipt.proof_files.input_boundary_report = $indexIdentity
    $receipt.native_input_boundary_verified = $true
    if ($receipt.python_reflection_requested) {
        $reflectionPath = Join-Path $ArtifactRoot 'native-python-reflection.json'
        $reflectionIdentity = Get-ProbeFileIdentity $reflectionPath
        if ($reflectionIdentity.size_bytes -gt 256KB) { throw 'Native reflection receipt exceeds its 256 KiB bound.' }
        $reflection = Get-Content -LiteralPath $reflectionPath -Raw | ConvertFrom-Json -AsHashtable
        if ($reflection.exact_sha -cne $ExpectedHead -or $reflection.status -cne 'NATIVE_PYTHON_REFLECTION_VERIFIED' `
            -or $reflection.reflection_verified -isnot [bool] -or -not $reflection.reflection_verified `
            -or $reflection.source_unchanged -isnot [bool] -or -not $reflection.source_unchanged `
            -or $reflection.python_remote_execution -isnot [bool] -or $reflection.python_remote_execution -ne $false) {
            throw 'Native Python reflection did not supply its exact-SHA actual success receipt.'
        }
        foreach ($flag in @('native_bob_capture_verified', 'native_registry_dispatch_verified', 'official_mcp_transport_verified', 'official_mcp_admitted', 'accepted_checkpoint_verified', 'persistent_world_mutation', 'performance_pass')) {
            if ($reflection[$flag] -isnot [bool] -or $reflection[$flag] -ne $false) { throw 'Native reflection receipt contains an invalid wider admission claim.' }
        }
        foreach ($name in @('script_sha256', 'public_header_sha256', 'plugin_descriptor_sha256', 'host_project_descriptor_sha256', 'host_engine_config_sha256')) {
            if ($reflection.source_sha256[$name] -cne $marker[$name]) { throw 'Native reflection source hashes disagree with the trusted marker.' }
        }
        if ((Get-ProbeFileIdentity $reflectionPath).sha256 -cne $reflectionIdentity.sha256) { throw 'Native reflection receipt changed during verification.' }
        $receipt.proof_files.native_python_reflection = $reflectionIdentity
        $receipt.native_python_reflection_verified = $true
    }
    $receipt.status = if ($receipt.native_python_reflection_verified) { 'NATIVE_INPUT_BOUNDARY_AND_REFLECTION_VERIFIED' } else { 'NATIVE_INPUT_BOUNDARY_VERIFIED_REFLECTION_UNESTABLISHED' }
}
catch {
    $receipt.status = 'BLOCKED'
    $receipt.error = $_.Exception.Message
    $receipt.source_unchanged = $false
    throw
}
finally {
    # Kill only the process handle created by this invocation, never a name,
    # another owner's PID or a process tree. All generated output is retained.
    if ($null -ne $ownedEditor) {
        try {
            if (-not $ownedEditor.HasExited) {
                $ownedEditor.Kill()
                if (-not $ownedEditor.WaitForExit(10000)) { $receipt.error = 'Owned Editor did not exit after bounded termination.'; $receipt.status = 'BLOCKED' }
            }
        }
        catch { $receipt.error = 'Cannot terminate the owned isolated Editor handle.'; $receipt.status = 'BLOCKED' }
        finally { $ownedEditor.Dispose() }
    }
    foreach ($name in @('native-plugin-build.log', 'input-boundary-editor.log', 'input-boundary-stdout.log', 'input-boundary-stderr.log', 'python-runtime-settings.json', 'runtime-dependencies.json')) {
        $path = Join-Path $ArtifactRoot $name
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            try { $receipt.proof_files[$name] = Get-ProbeFileIdentity $path }
            catch { $receipt.status = 'BLOCKED'; $receipt.error = 'Cannot retain a native proof output identity.' }
        }
    }
    $json = $receipt | ConvertTo-Json -Depth 20
    [IO.File]::WriteAllText((Join-Path $ArtifactRoot 'native-plugin-build.json'), $json, [Text.UTF8Encoding]::new($false))
    Write-Host $json
    if ($receipt.status -ceq 'BLOCKED') { throw $receipt.error }
}
