#requires -Version 7.4
<#
.SYNOPSIS
    Prepare the exact accepted #384 session with independently built binaries.
.DESCRIPTION
    Fresh short code-only worktrees only. The original project descriptor is
    built normally; BuildPlugin independently builds the opt-in domain plugin.
    Hash-bound DLLs and unchanged module manifests are copied exclusively into
    the fresh session. The accepted checkpoint stager authenticates its bytes.
    One owned Editor and one fixed loopback client share a 420 second deadline.
    This script never certifies an old cache or edits a module manifest.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string] $ExpectedHead
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'The accepted BOB session requires Windows.' }
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$runId = [string]$env:GITHUB_RUN_ID
$attempt = [string]$env:GITHUB_RUN_ATTEMPT
if ($runId -cnotmatch '^[1-9][0-9]{0,19}$' -or $attempt -cnotmatch '^[1-9][0-9]{0,5}$') {
    throw 'The fixed session requires its exact Actions run and attempt.'
}
$runIdentity = $runId + '-' + $attempt
$ArtifactRoot = Join-Path $RepoRoot ('Saved/RuntimeProof/OfficialMcpBobSession/' + $runIdentity)
$BuildRoot = Join-Path 'D:\yacs\runner\_work\b384' ($runIdentity + '-session-project')
$SessionRoot = Join-Path 'D:\yacs\runner\_work\s384' $runIdentity
$PluginPackage = Join-Path 'D:\yacs\runner\_work\b384' ($runIdentity + '-session-plugin')
$ownedBuild = $null
$ownedEditor = $null
$ownedClient = $null
$ownedValidation = $null
$artifactOwned = $false
$receipt = [ordered]@{
    schema_version = 1; exact_sha = $ExpectedHead; run = $runId; attempt = $attempt
    status = 'PREPARATION_PENDING'; build_root = $BuildRoot; session_root = $SessionRoot
    plugin_package_root = $PluginPackage; engine_identity = $null; build_environment_identity = $null
    source_fingerprints = [ordered]@{}; tracked_source_sha256 = [ordered]@{}
    project_build = $null; plugin_build = $null; binary_provenance = @(); staged_binary_provenance = @()
    source_unchanged = $false; accepted_bytes_staged = $false; owned_build_exit_observed = $false
    editor_launched = $false; listener_started = $false; official_mcp_transport_verified = $false
    official_mcp_admitted = $false; native_automation_verified = $false; native_bob_capture_verified = $false
    persistent_world_mutation = $false; performance_pass = $false; performance_status = 'DEFERRED_AFTER_M3'
    error = $null; secondary_errors = @()
    owned_editor_pid = $null; owned_client_pid = $null; owned_editor_exit_observed = $false; owned_client_exit_observed = $false
    startup_config_overrides = @(); loopback_binding = @(); proof_files = [ordered]@{}
}

function Assert-SessionPlainPath {
    param([Parameter(Mandatory)][string] $Path)
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'The session refuses symlinks and junctions.'
            }
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}
function Get-SessionFileIdentity {
    param([Parameter(Mandatory)][string] $Path, [long] $Limit = 512MB)
    Assert-SessionPlainPath $Path
    $before = Get-Item -LiteralPath $Path -Force
    if ($before.PSIsContainer -or $before.Length -le 0 -or $before.Length -gt $Limit) {
        throw 'A fixed session input is not a bounded nonempty regular file.'
    }
    $beforeLength = $before.Length
    $beforeTicks = $before.LastWriteTimeUtc.Ticks
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { $digest = [Convert]::ToHexString($algorithm.ComputeHash($stream)).ToLowerInvariant() }
    finally { $algorithm.Dispose(); $stream.Dispose() }
    $after = Get-Item -LiteralPath $Path -Force
    if ($after.Length -ne $beforeLength -or $after.LastWriteTimeUtc.Ticks -ne $beforeTicks) {
        throw 'A fixed session input changed during hashing.'
    }
    return [ordered]@{ path = [IO.Path]::GetFullPath($Path); size_bytes = $beforeLength; sha256 = $digest }
}
function Write-SessionJson {
    param([Parameter(Mandatory)][string] $Path, [Parameter(Mandatory)] $Value)
    Assert-SessionPlainPath $Path
    $bytes = [Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 30))
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
}
function Read-SessionJson {
    param([string] $Path, [long] $Limit = 256KB)
    $identity = Get-SessionFileIdentity $Path $Limit
    $stream = [IO.File]::OpenRead($Path)
    try {
        $buffer = [byte[]]::new([int]$identity.size_bytes + 1)
        $count = 0
        while (($part = $stream.Read($buffer, $count, $buffer.Length - $count)) -gt 0) { $count += $part }
    } finally { $stream.Dispose() }
    if ($count -ne $identity.size_bytes) { throw 'A bounded JSON input changed before parsing.' }
    $bytes = [byte[]]::new($count)
    [Array]::Copy($buffer, $bytes, $count)
    if ([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant() -cne $identity.sha256 `
        -or (Get-SessionFileIdentity $Path $Limit).sha256 -cne $identity.sha256) { throw 'A bounded JSON input changed before parsing.' }
    $value = [Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json -AsHashtable -Depth 40
    if ($value -isnot [Collections.IDictionary]) { throw 'The fixed JSON evidence must be an object.' }
    return [ordered]@{ identity = $identity; value = $value }
}
function Get-SessionOwnedLogIdentity {
    param([string] $Path, [Diagnostics.Process] $Process, [switch] $IncludeText)
    if ($null -eq $Process -or -not $Process.HasExited) { throw 'An owned redirected log requires the observed process exit.' }
    Assert-SessionPlainPath $Path
    $before = Get-Item -LiteralPath $Path -Force
    if ($before.PSIsContainer -or $before.Length -gt 32MB) { throw 'The owned redirected log exceeds its regular-file bound.' }
    $size = $before.Length
    $ticks = $before.LastWriteTimeUtc.Ticks
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try {
        $buffer = [byte[]]::new(32MB + 1)
        $count = 0
        while (($part = $stream.Read($buffer, $count, $buffer.Length - $count)) -gt 0) {
            $count += $part
            if ($count -gt 32MB) { throw 'The owned redirected log grew beyond its bound.' }
        }
    } finally { $stream.Dispose() }
    $after = Get-Item -LiteralPath $Path -Force
    if ($count -ne $size -or $count -ne $after.Length -or $ticks -ne $after.LastWriteTimeUtc.Ticks) { throw 'The owned redirected log changed during retention.' }
    $bytes = [byte[]]::new($count)
    [Array]::Copy($buffer, $bytes, $count)
    $result = [ordered]@{ path = [IO.Path]::GetFullPath($Path); size_bytes = $count
        sha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant() }
    if ($IncludeText) { $result.text = [Text.Encoding]::UTF8.GetString($bytes) }
    return $result
}
function Assert-SessionIdleHost {
    $state = & (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
    $receipt.host_status = $state.status
    $receipt.host_checked_at_utc = $state.checked_at_utc
    if ($state.status -cne 'IDLE') { throw "The session yields to the Unreal host owner: $($state.status)." }
}
function Get-SessionTrackedSources {
    param([Parameter(Mandatory)][string] $Root)
    $head = (& git -C $Root rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $head -cne $ExpectedHead) { throw 'A session worktree has a different HEAD.' }
    & git -C $Root diff --quiet HEAD -- . ':(exclude)Content/**'
    if ($LASTEXITCODE -ne 0) { throw 'Tracked session source/config differs from its claimed HEAD.' }
    $paths = @(& git -C $Root ls-files)
    if ($LASTEXITCODE -ne 0 -or $paths.Count -gt 10000) { throw 'Cannot establish the bounded tracked input inventory.' }
    $hashes = [ordered]@{}
    foreach ($relative in $paths) {
        # Content pointers are authenticated by the accepted checkpoint stager.
        # Preserve the separate code/config identity after their hydration.
        if ($relative.StartsWith('Content/', [StringComparison]::Ordinal)) { continue }
        if ($relative -cmatch '(^|/)(\.\.?)(/|$)|[\\:\x00]') { throw 'Tracked source path is not canonical.' }
        $path = Join-Path $Root $relative
        $entry = Get-Item -LiteralPath $path -Force
        if ($entry.Length -eq 0) {
            Assert-SessionPlainPath $path
            $hashes[$relative] = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
        } else { $hashes[$relative] = (Get-SessionFileIdentity $path 16MB).sha256 }
    }
    return $hashes
}
function Assert-SessionTrackedSources {
    param([string] $Root)
    $actual = Get-SessionTrackedSources $Root
    if ($actual.Count -ne $receipt.tracked_source_sha256.Count) { throw 'Tracked source inventory changed.' }
    foreach ($relative in $receipt.tracked_source_sha256.Keys) {
        if ($actual[$relative] -cne $receipt.tracked_source_sha256[$relative]) { throw 'Tracked source/config bytes changed.' }
    }
}
function Assert-SessionNoUntrackedNativeInputs {
    param([string] $Root)
    # No exclude filters: ignored native inputs are still compiler inputs.
    # Generated Intermediate/Binaries outputs are outside these exact roots.
    $extra = @(& git -C $Root ls-files --others -- Source ':(glob)Plugins/*/Source/**' ':(glob)Plugins/*/*.uplugin' '*.uproject')
    if ($LASTEXITCODE -ne 0 -or $extra.Count -ne 0) { throw 'Unexpected untracked native source/descriptor inputs cannot be certified.' }
}
function Get-SessionFingerprints {
    param([string] $Root)
    Push-Location -LiteralPath $Root
    try {
        $result = & python -c 'import json; from scripts.ci.classify_changes import unreal_compile_fingerprint, unreal_proof_fingerprint; print(json.dumps(dict(compile=unreal_compile_fingerprint(),proof=unreal_proof_fingerprint())))'
        if ($LASTEXITCODE -ne 0 -or @($result).Count -ne 1) { throw 'Code-only source fingerprint computation failed.' }
        return ($result | ConvertFrom-Json -AsHashtable)
    } finally { Pop-Location }
}
function Invoke-SessionBuildProcess {
    param([string] $Executable, [string[]] $Arguments, [string] $Root, [string] $Name)
    Assert-SessionIdleHost
    $log = Join-Path $ArtifactRoot ($Name + '.log')
    $errors = Join-Path $ArtifactRoot ($Name + '-stderr.log')
    $started = (Get-Date).ToUniversalTime().ToString('o')
    $receipt.owned_build_exit_observed = $false
    $script:ownedBuild = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $Root `
        -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError $errors
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $heartbeat = 30
    while (-not $script:ownedBuild.WaitForExit(2000)) {
        if ($timer.Elapsed.TotalSeconds -ge 1200) { throw 'The owned build exceeded its fixed 20 minute deadline.' }
        if ($timer.Elapsed.TotalSeconds -ge $heartbeat) {
            Write-Host ('Session build heartbeat: {0}, ownedPID={1}, elapsed={2:N0}s.' -f $Name, $script:ownedBuild.Id, $timer.Elapsed.TotalSeconds)
            $heartbeat += 30
        }
    }
    $script:ownedBuild.WaitForExit()
    $exit = $script:ownedBuild.ExitCode
    if ($null -eq $exit -or $exit -ne 0) { throw "The owned fixed build failed: $Name exit=$exit." }
    $receipt.owned_build_exit_observed = $true
    $record = [ordered]@{ executable = $Executable; arguments = $Arguments; started_at_utc = $started
        ended_at_utc = (Get-Date).ToUniversalTime().ToString('o'); exit_code = $exit
        log = Get-SessionOwnedLogIdentity $log $script:ownedBuild
        stderr = Get-SessionOwnedLogIdentity $errors $script:ownedBuild }
    $script:ownedBuild.Dispose()
    $script:ownedBuild = $null
    return $record
}
function Get-SessionModuleClosure {
    param([string] $Root, [string] $ManifestRelative, [hashtable] $ExpectedModules, [string] $BuildId)
    $path = Join-Path $Root $ManifestRelative
    $parsed = Read-SessionJson $path 64KB
    $identity = $parsed.identity
    $data = $parsed.value
    if ($data -isnot [Collections.IDictionary] -or $data.BuildId -isnot [string] -or $data.BuildId -cne $BuildId `
        -or $data.Modules -isnot [Collections.IDictionary] -or $data.Modules.Count -ne $ExpectedModules.Count) {
        throw 'A generated module manifest does not match the actual installed engine and fixed module closure.'
    }
    $rows = @([ordered]@{ relative = $ManifestRelative; identity = $identity; build_id = $data.BuildId; modules = $data.Modules })
    foreach ($name in $ExpectedModules.Keys) {
        if ($data.Modules[$name] -cne $ExpectedModules[$name]) { throw 'A module manifest maps a fixed module to another binary.' }
        $relative = ([IO.Path]::GetDirectoryName($ManifestRelative).Replace('\', '/') + '/' + $ExpectedModules[$name])
        $rows += [ordered]@{ relative = $relative; identity = Get-SessionFileIdentity (Join-Path $Root $relative) }
    }
    if ((Get-SessionFileIdentity $path 64KB).sha256 -cne $identity.sha256) { throw 'Module manifest changed during validation.' }
    return $rows
}
function Copy-SessionBinaryExclusive {
    param([string] $Source, [string] $Relative, $Identity)
    $target = Join-Path $SessionRoot $Relative
    Assert-SessionPlainPath $target
    if (Test-Path -LiteralPath $target) { throw 'The session cannot replace a binary or module manifest.' }
    New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
    $inputStream = [IO.File]::OpenRead($Source)
    $outputStream = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $inputStream.CopyTo($outputStream) } finally { $outputStream.Dispose(); $inputStream.Dispose() }
    $copied = Get-SessionFileIdentity $target
    if ($copied.sha256 -cne $Identity.sha256 -or $copied.size_bytes -ne $Identity.size_bytes `
        -or (Get-SessionFileIdentity $Source).sha256 -cne $Identity.sha256) {
        throw 'An exclusive copied binary differs from its successful build receipt.'
    }
    return [ordered]@{ relative = $Relative; identity = $copied }
}
function Get-SessionListener {
    # No external address or port is accepted. The OS process owner is checked
    # independently of a C++ StartServer return or an in-memory bind setting.
    if (-not (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) { throw 'The fixed OS listener ownership check is unavailable.' }
    return @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq 18784)
}
function Assert-SessionOwnLoopback {
    param([switch] $RequireListener)
    $listeners = @(Get-SessionListener)
    if ($RequireListener -and $listeners.Count -ne 1) { throw 'The fixed MCP listener must be exactly one owned IPv4 loopback socket.' }
    foreach ($listener in $listeners) {
        if ($listener.LocalAddress -cne '127.0.0.1' -or $listener.OwningProcess -ne $ownedEditor.Id) { throw 'A fixed-port listener is external or belongs to another process.' }
    }
    return @($listeners | ForEach-Object { [ordered]@{ address = $_.LocalAddress; port = $_.LocalPort; owned_editor_pid = $_.OwningProcess } })
}
function Assert-SessionAttemptDeadline {
    if ($attemptTimer.Elapsed.TotalSeconds -ge 420) { throw 'The entire owned Editor/client attempt exceeded its shared 420 second deadline.' }
}
function Assert-SessionStagedBinaries {
    foreach ($row in $receipt.staged_binary_provenance) {
        $actual = Get-SessionFileIdentity (Join-Path $SessionRoot $row.relative)
        if ($actual.sha256 -cne $row.identity.sha256 -or $actual.size_bytes -ne $row.identity.size_bytes) { throw 'A staged binary/module manifest changed.' }
    }
}
function Assert-SessionJsonFields {
    param($Value, [string[]] $Fields)
    if ($Value.Count -ne $Fields.Count) { throw 'The fixed session object has unexpected fields.' }
    foreach ($field in $Fields) { if (-not $Value.Contains($field)) { throw 'The fixed session object is missing a field.' } }
}
function Test-SessionInteger {
    param($Value, [long] $Expected)
    return (($Value -is [int] -or $Value -is [long]) -and $Value -eq $Expected)
}
function Wait-SessionObject {
    param([string] $Path, [Diagnostics.Process] $Owner)
    while ($true) {
        Assert-SessionAttemptDeadline
        if ($Owner.HasExited) { throw 'The owned Editor exited before fixed readiness.' }
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            # A CreateNew file can become visible before the bounded writer's
            # final close. No malformed value is admitted or used for dispatch.
            try { return (Read-SessionJson $Path 1MB) } catch { }
        }
        Start-Sleep -Milliseconds 200
    }
}
function Assert-SessionFixedAutomation {
    param($Result)
    if (-not (Test-SessionInteger $Result.total 1) -or -not (Test-SessionInteger $Result.passed 1) `
        -or -not (Test-SessionInteger $Result.failed 0) -or -not (Test-SessionInteger $Result.skipped 0) `
        -or @($Result.tests).Count -ne 1) { throw 'The official fixed Automation result is incomplete or failed.' }
    $test = $Result.tests[0]
    if ($test.name -cne 'CyclingPhysics.RoadPhysics.ProfileInterpolation' -or $test.state -isnot [string] -or [string]::IsNullOrWhiteSpace($test.state) `
        -or @($test.errors).Count -ne 0 -or @($test.warnings).Count -ne 0) { throw 'The official result does not prove the one literal test passed cleanly.' }
}
function Stop-SessionOwnedProcess {
    param([Diagnostics.Process] $Process, [string] $Kind, [switch] $BuildTree)
    if ($null -eq $Process) { return }
    try {
        if (-not $Process.HasExited) {
            # Batch wrappers spawn UBT/UAT children owned by this invocation.
            # Editor/client are terminated only through their current handles.
            if ($BuildTree) { $Process.Kill($true) } else { $Process.Kill() }
            if (-not $Process.WaitForExit(10000)) { throw 'Owned process exit was not observed.' }
        }
        $receipt[('owned_' + $Kind + '_exit_observed')] = $Process.HasExited
    } catch { $receipt.secondary_errors += ('Cannot terminate/observe this invocation owned ' + $Kind + ' handle.') }
    finally { $Process.Dispose() }
}

try {
    foreach ($path in @($RepoRoot, $BuildRoot, $SessionRoot, $PluginPackage, $ArtifactRoot)) { Assert-SessionPlainPath $path }
    if (-not $env:GITHUB_WORKSPACE -or -not [string]::Equals($RepoRoot, (Join-Path ([IO.Path]::GetFullPath($env:GITHUB_WORKSPACE).TrimEnd('\')) '_official-mcp-native-probe'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The fixed session must originate in its Actions code-only checkout.'
    }
    $workRoot = [IO.Path]::GetDirectoryName([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($env:GITHUB_WORKSPACE)))
    if (-not [string]::Equals($workRoot, 'D:\yacs\runner\_work', [StringComparison]::OrdinalIgnoreCase)) { throw 'Canonical runner work root differs.' }
    foreach ($path in @($BuildRoot, $SessionRoot, $PluginPackage, $ArtifactRoot)) {
        if (Test-Path -LiteralPath $path) { throw 'A fixed session output already exists; preserve it.' }
    }
    & (Join-Path $RepoRoot 'scripts/ci/Test-YacsCodeOnlyCheckout.ps1') -RepoRoot $RepoRoot
    $receipt.tracked_source_sha256 = Get-SessionTrackedSources $RepoRoot
    $receipt.source_fingerprints = Get-SessionFingerprints $RepoRoot
    . (Join-Path $RepoRoot 'scripts/ci/Resolve-YacsUnrealBuildEnvironment.ps1')
    $environment = Resolve-YacsUnrealBuildEnvironment -ProjectPath (Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject')
    if (-not $environment -or $environment.Engine.Version -cne '5.8.2-56702186') { throw 'Canonical UE5.8.2/CL56702186/toolchain is required.' }
    $engine = $environment.Engine
    $receipt.engine_identity = $engine.Identity
    $receipt.build_environment_identity = $environment.Identity
    foreach ($path in @($engine.Root, $engine.BuildBatPath, $engine.UATPath)) { Assert-SessionPlainPath $path }
    . (Join-Path $RepoRoot 'scripts/runner/Assert-YacsDiskReserve.ps1')
    . (Join-Path $RepoRoot 'scripts/ci/Assert-YacsBuildIsolation.ps1')
    Assert-YacsDiskReserve -Path $BuildRoot
    Assert-SessionIdleHost
    New-Item -ItemType Directory -Path $ArtifactRoot | Out-Null
    $artifactOwned = $true
    & (Join-Path $RepoRoot 'scripts/ue/Read-YacsOfficialMcpRuntimeDependencies.ps1') -EngineRoot $engine.Root -ArtifactRoot $ArtifactRoot -ExpectedHead $ExpectedHead
    $sdk = Read-SessionJson (Join-Path $ArtifactRoot 'runtime-dependencies.json') 4MB
    if ($sdk.value.exact_sha -cne $ExpectedHead -or $sdk.value.source_only -isnot [bool] -or -not $sdk.value.source_only) { throw 'The observed installed SDK receipt differs from this source-bound session.' }
    $serverRows = @($sdk.value.source_files | Where-Object { $_.path.EndsWith('/ModelContextProtocolServer.cpp', [StringComparison]::Ordinal) })
    if ($serverRows.Count -ne 1 -or $serverRows[0].sha256 -cne '56e519b8a956a1d916f421781767f85a999d02b9e02f806b3594d96b96d2a104') { throw 'The actual installed official MCP Server source does not match the fixed reviewed protocol.' }
    $receipt.proof_files.runtime_dependencies = $sdk.identity
    $receipt.observed_official_server_source = $serverRows[0]
    $engineModuleRecord = Read-SessionJson (Join-Path $engine.Root 'Engine/Binaries/Win64/UnrealEditor.modules') 64KB
    $engineManifest = $engineModuleRecord.identity
    $engineModules = $engineModuleRecord.value
    if ($engineModules.BuildId -isnot [string] -or [string]::IsNullOrWhiteSpace($engineModules.BuildId)) { throw 'Installed engine BuildId is unavailable.' }
    $receipt.installed_engine_module_manifest = $engineManifest
    $receipt.installed_engine_build_id = $engineModules.BuildId
    $oldSmudge = [Environment]::GetEnvironmentVariable('GIT_LFS_SKIP_SMUDGE', 'Process')
    try {
        [Environment]::SetEnvironmentVariable('GIT_LFS_SKIP_SMUDGE', '1', 'Process')
        foreach ($root in @($BuildRoot, $SessionRoot)) {
            New-Item -ItemType Directory -Path (Split-Path $root -Parent) -Force | Out-Null
            & git -C $RepoRoot worktree add --detach $root $ExpectedHead
            if ($LASTEXITCODE -ne 0) { throw 'Fresh exact-source detached worktree creation failed.' }
            & (Join-Path $RepoRoot 'scripts/ci/Test-YacsCodeOnlyCheckout.ps1') -RepoRoot $root
            Assert-SessionTrackedSources $root
            $fingerprints = Get-SessionFingerprints $root
            if ($fingerprints.compile -cne $receipt.source_fingerprints.compile -or $fingerprints.proof -cne $receipt.source_fingerprints.proof) {
                throw 'Fresh code-only worktree fingerprint differs before generated binaries.'
            }
        }
    } finally { [Environment]::SetEnvironmentVariable('GIT_LFS_SKIP_SMUDGE', $oldSmudge, 'Process') }
    $project = Join-Path $BuildRoot 'YetAnotherCyclingSim.uproject'
    # Use the established conservative UBT configuration only in this fresh
    # producer. No shared cache, user configuration or live project is edited.
    $ubtDirectory = Join-Path $BuildRoot 'Saved/UnrealBuildTool'
    New-Item -ItemType Directory -Path $ubtDirectory | Out-Null
    $ubtXml = @'
<?xml version="1.0" encoding="utf-8" ?>
<Configuration xmlns="https://www.unrealengine.com/BuildConfiguration">
  <BuildConfiguration>
    <bAllowUBAExecutor>false</bAllowUBAExecutor>
    <bAllowUBALocalExecutor>false</bAllowUBALocalExecutor>
    <MaxParallelActions>2</MaxParallelActions>
  </BuildConfiguration>
</Configuration>
'@
    [IO.File]::WriteAllText((Join-Path $ubtDirectory 'BuildConfiguration.xml'), $ubtXml, [Text.UTF8Encoding]::new($false))
    Assert-YacsBuildIsolation -ProjectPath $project
    Assert-YacsDiskReserve -Path $project
    Assert-SessionNoUntrackedNativeInputs $BuildRoot
    $receipt.status = 'PROJECT_BUILD_PENDING'
    $receipt.project_build = Invoke-SessionBuildProcess $engine.BuildBatPath @(
        ('"' + $project + '"'), 'YetAnotherCyclingSimEditor', 'Win64', 'Development', '-WaitMutex', '-NoHotReloadFromIDE', '-FromMsBuild'
    ) (Join-Path $engine.Root 'Engine/Build/BatchFiles') 'original-project-build'
    Assert-SessionTrackedSources $BuildRoot
    Assert-SessionNoUntrackedNativeInputs $BuildRoot
    $receipt.status = 'DOMAIN_PLUGIN_BUILD_PENDING'
    # BuildPlugin copies its whole input directory. Compile only the exact
    # tracked plugin source, never incidental untracked native files.
    $inputPlugin = Join-Path $ArtifactRoot 'InputPlugin/YacsBobInspection'
    $prefix = 'Plugins/YacsBobInspection/'
    $pluginPaths = @($receipt.tracked_source_sha256.Keys | Where-Object { $_.StartsWith($prefix, [StringComparison]::Ordinal) })
    if ($pluginPaths.Count -lt 4 -or $pluginPaths.Count -gt 64) { throw 'The tracked domain source inventory is incomplete or oversized.' }
    foreach ($relative in $pluginPaths) {
        $target = Join-Path $inputPlugin $relative.Substring($prefix.Length)
        Assert-SessionPlainPath $target
        New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
        $input = [IO.File]::OpenRead((Join-Path $RepoRoot $relative))
        $output = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $input.CopyTo($output) } finally { $output.Dispose(); $input.Dispose() }
        if ((Get-SessionFileIdentity $target 16MB).sha256 -cne $receipt.tracked_source_sha256[$relative]) { throw 'Tracked-only native input copy differs.' }
    }
    $actionExample = Join-Path $PluginPackage 'HostProject/Plugins/YacsBobInspection/Intermediate/Build/Win64/x64/UnrealEditor/Development/YacsBobInspection/Module.YacsBobInspection.cpp.obj.rsp'
    if ($actionExample.Length -ge 240) { throw 'The fixed native package exceeds the established Windows UBT action path bound.' }
    $receipt.planned_plugin_action_path_length = $actionExample.Length
    $receipt.staged_tracked_plugin_only = $true
    Assert-YacsDiskReserve -Path $PluginPackage
    $receipt.plugin_build = Invoke-SessionBuildProcess $engine.UATPath @(
        'BuildPlugin', ('-Plugin="' + (Join-Path $inputPlugin 'YacsBobInspection.uplugin') + '"'),
        ('-Package="' + $PluginPackage + '"'), '-TargetPlatforms=Win64', '-StrictIncludes', '-NoDeleteHostProject'
    ) (Join-Path $engine.Root 'Engine/Build/BatchFiles') 'domain-plugin-build'
    Assert-SessionTrackedSources $BuildRoot
    Assert-SessionTrackedSources $SessionRoot
    $projectRows = @(Get-SessionModuleClosure $BuildRoot 'Binaries/Win64/UnrealEditor.modules' @{
        YetAnotherCyclingSim = 'UnrealEditor-YetAnotherCyclingSim.dll'; YetAnotherCyclingSimEditor = 'UnrealEditor-YetAnotherCyclingSimEditor.dll'
    } $engineModules.BuildId)
    $roadRows = @(Get-SessionModuleClosure $BuildRoot 'Plugins/RoadForge/Binaries/Win64/UnrealEditor.modules' @{
        RoadForge = 'UnrealEditor-RoadForge.dll'
    } $engineModules.BuildId)
    $pluginRoot = Join-Path $PluginPackage 'HostProject/Plugins/YacsBobInspection'
    foreach ($relative in $pluginPaths) {
        foreach ($root in @($inputPlugin, $pluginRoot)) {
            if ((Get-SessionFileIdentity (Join-Path $root $relative.Substring($prefix.Length)) 16MB).sha256 -cne $receipt.tracked_source_sha256[$relative]) { throw 'Actual compiled domain source differs from its tracked-only input.' }
        }
    }
    $bobRows = @(Get-SessionModuleClosure $pluginRoot 'Binaries/Win64/UnrealEditor.modules' @{
        YacsBobInspection = 'UnrealEditor-YacsBobInspection.dll'
    } $engineModules.BuildId)
    foreach ($row in @($projectRows + $roadRows)) {
        $receipt.binary_provenance += $row
        $receipt.staged_binary_provenance += Copy-SessionBinaryExclusive $row.identity.path $row.relative $row.identity
    }
    foreach ($row in $bobRows) {
        $receipt.binary_provenance += $row
        $receipt.staged_binary_provenance += Copy-SessionBinaryExclusive $row.identity.path ('Plugins/YacsBobInspection/' + $row.relative) $row.identity
    }
    if ((Get-SessionFileIdentity $engineManifest.path 64KB).sha256 -cne $engineManifest.sha256) { throw 'Installed engine manifest changed during compilation.' }
    Assert-SessionTrackedSources $SessionRoot
    Assert-SessionTrackedSources $RepoRoot
    $receipt.source_unchanged = $true
    $receipt.status = 'ACCEPTED_BYTES_STAGING_PENDING'
    Push-Location -LiteralPath $SessionRoot
    try {
        & python -m scripts.ci.official_mcp_bob_session --exact-sha $ExpectedHead
        if ($LASTEXITCODE -ne 0) { throw 'Fixed accepted checkpoint staging failed.' }
    } finally { Pop-Location }
    $receipt.accepted_bytes_staged = $true
    Assert-SessionTrackedSources $SessionRoot
    $proofRoot = Join-Path $SessionRoot 'Saved/RuntimeProof/OfficialMcpBob'
    $preparation = Read-SessionJson (Join-Path $proofRoot 'session-preparation.json') 4MB
    if ($preparation.value.exact_sha -cne $ExpectedHead -or $preparation.value.status -cne 'ACCEPTED_CONSUMER_BYTES_STAGED' `
        -or $preparation.value.native_runtime_verified -isnot [bool] -or $preparation.value.native_runtime_verified `
        -or $preparation.value.official_mcp_admitted -isnot [bool] -or $preparation.value.official_mcp_admitted) { throw 'The actual staged consumer receipt is missing or does not match this build.' }
    $receipt.proof_files.session_preparation = $preparation.identity
    $mapPackage = '/Game/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview'
    $operationName = 'YacsBobInspection.InspectAcceptedCheckpoint'
    $bootstrap = Join-Path $SessionRoot 'scripts/ue/bootstrap_official_mcp_bob_session.py'
    foreach ($relative in @('scripts/ue/bootstrap_official_mcp_bob_session.py', 'scripts/ue/Invoke-YacsOfficialMcpBobSession.ps1')) {
        if (-not $receipt.tracked_source_sha256.Contains($relative)) { throw 'The exact executed harness source is absent from committed inputs.' }
    }
    Push-Location -LiteralPath $SessionRoot
    try {
        $sourceOutput = @(& python -c 'import json,sys; from scripts.ci import official_mcp_bob_client as c; print(json.dumps(dict(source_sha256=c._source_hashes(sys.argv[1]),denial_cases=[row[0] for row in c.DENIAL_CASES])))' $ExpectedHead)
        if ($LASTEXITCODE -ne 0 -or $sourceOutput.Count -ne 1) { throw 'The pinned fixed client source closure cannot be established.' }
        $clientInputs = $sourceOutput[0] | ConvertFrom-Json -AsHashtable -Depth 30
        if (@($clientInputs.denial_cases).Count -ne 22 -or $clientInputs.source_sha256 -isnot [Collections.IDictionary]) { throw 'The fixed client input contract differs.' }
    } finally { Pop-Location }
    Assert-SessionStagedBinaries
    Assert-SessionIdleHost
    if (@(Get-SessionListener).Count -ne 0) { throw 'The fixed MCP port is already owned; preserve its owner.' }
    Assert-YacsDiskReserve -Path $SessionRoot
    $receipt.startup_config_overrides = @(
        '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
        '-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]:bAutoStartServer=False'
    )
    # These installed parser/adoption paths are source-proved. The bootstrap
    # and native owner still verify effective CDO booleans before any listener.
    $editorArguments = @(
        ('"' + (Join-Path $SessionRoot 'YetAnotherCyclingSim.uproject') + '"'), $mapPackage,
        '-EnablePlugins=YacsBobInspection,ModelContextProtocol', '-DisablePlugins=AndroidFileServer',
        '-YacsBobOfficialProof', '-unattended', '-NoSplash', '-NoSound', '-NoLiveCoding',
        ('-ExecutePythonScript="' + $bootstrap + '"'), ('-abslog="' + (Join-Path $ArtifactRoot 'owned-editor.log') + '"')
    ) + $receipt.startup_config_overrides
    Assert-SessionPlainPath $engine.UnrealEditorPath
    $receipt.owned_editor_executable = Get-SessionFileIdentity $engine.UnrealEditorPath 1GB
    $pythonExecutable = (Get-Command python -CommandType Application -ErrorAction Stop).Source
    $receipt.owned_client_executable = Get-SessionFileIdentity $pythonExecutable 128MB
    $attemptTimer = [Diagnostics.Stopwatch]::StartNew()
    $receipt.attempt_started_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    $receipt.status = 'OWNED_EDITOR_STARTING'
    $ownedEditor = Start-Process -FilePath $engine.UnrealEditorPath -ArgumentList $editorArguments -WorkingDirectory $SessionRoot `
        -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $ArtifactRoot 'owned-editor-stdout.log') `
        -RedirectStandardError (Join-Path $ArtifactRoot 'owned-editor-stderr.log') -Environment @{
            YACS_MCP_BOB_PROJECT_ROOT = $SessionRoot; YACS_MCP_BOB_EXPECTED_HEAD = $ExpectedHead
            YACS_MCP_BOB_OWNED_EDITOR_PID = ''; YACS_OWNER_HANDOFF = ''; PYTHONPATH = ''; PYTHONHOME = ''
        }
    $receipt.editor_launched = $true
    $receipt.owned_editor_pid = $ownedEditor.Id
    $context = Wait-SessionObject (Join-Path $proofRoot 'session-context.json') $ownedEditor
    Assert-SessionJsonFields $context.value @('schema_version', 'exact_sha', 'source_sha256', 'profile_sha256', 'profile_source_sha', 'consumer_source_sha', 'consumer_assets', 'landscape')
    if (-not (Test-SessionInteger $context.value.schema_version 1) -or $context.value.exact_sha -cne $ExpectedHead `
        -or $context.value.landscape.path -isnot [string] -or [string]::IsNullOrWhiteSpace($context.value.landscape.path)) { throw 'The actual native session context is invalid.' }
    Assert-SessionTrackedSources $SessionRoot
    $receipt.proof_files.session_context = $context.identity
    $marker = [ordered]@{
        schema_version = 1; exact_sha = $ExpectedHead; project_root = $SessionRoot
        owned_editor_pid = $ownedEditor.Id; source_sha256 = $clientInputs.source_sha256
        session_context_sha256 = $context.identity.sha256
    }
    Write-SessionJson (Join-Path $proofRoot 'transport-context.json') $marker
    $receipt.proof_files.transport_context = Get-SessionFileIdentity (Join-Path $proofRoot 'transport-context.json') 1MB
    $counter = Wait-SessionObject (Join-Path $proofRoot 'native-counter.json') $ownedEditor
    Assert-SessionJsonFields $counter.value @('schema_version', 'exact_sha', 'body_invocation_count')
    if (-not (Test-SessionInteger $counter.value.schema_version 1) -or $counter.value.exact_sha -cne $ExpectedHead `
        -or -not (Test-SessionInteger $counter.value.body_invocation_count 0)) { throw 'The fixed native readiness counter differs.' }
    $receipt.loopback_binding = @(Assert-SessionOwnLoopback -RequireListener)
    $receipt.listener_started = $true
    Assert-SessionAttemptDeadline
    $receipt.status = 'FIXED_CLIENT_RUNNING'
    $ownedClient = Start-Process -FilePath $pythonExecutable -ArgumentList @('-m', 'scripts.ci.official_mcp_bob_client') `
        -WorkingDirectory $SessionRoot -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $ArtifactRoot 'owned-client-stdout.log') `
        -RedirectStandardError (Join-Path $ArtifactRoot 'owned-client-stderr.log') -Environment @{
            YACS_MCP_BOB_PROJECT_ROOT = $SessionRoot; YACS_MCP_BOB_EXPECTED_HEAD = $ExpectedHead
            YACS_MCP_BOB_OWNED_EDITOR_PID = [string]$ownedEditor.Id; YACS_OWNER_HANDOFF = ''; PYTHONPATH = ''; PYTHONHOME = ''
        }
    $receipt.owned_client_pid = $ownedClient.Id
    $heartbeat = 30
    while (-not $ownedClient.WaitForExit(200)) {
        Assert-SessionAttemptDeadline
        # The bootstrap may observe terminal native evidence and quit before
        # the fixed Python client finishes printing/teardown. Both clean exits
        # and stable final receipts are mandatory below; no request is retried.
        # Native completion can stop its listener immediately after the client
        # writes its final receipt, while Python is still exiting. Every socket
        # that remains must still be exactly this Editor's IPv4 loopback socket.
        [void](Assert-SessionOwnLoopback)
        if ($attemptTimer.Elapsed.TotalSeconds -ge $heartbeat) {
            Write-Host ('Accepted session heartbeat: ownedEditor={0}, ownedClient={1}, elapsed={2:N0}s.' -f $ownedEditor.Id, $ownedClient.Id, $attemptTimer.Elapsed.TotalSeconds)
            $heartbeat += 30
        }
    }
    $ownedClient.WaitForExit()
    $receipt.owned_client_exit_observed = $true
    $receipt.owned_client_exit_code = $ownedClient.ExitCode
    if ($ownedClient.ExitCode -ne 0) { throw 'The fixed loopback client failed; retain its evidence without another call.' }
    $receipt.status = 'OWNED_EDITOR_SHUTDOWN_PENDING'
    while (-not $ownedEditor.WaitForExit(200)) {
        Assert-SessionAttemptDeadline
        [void](Assert-SessionOwnLoopback)
    }
    $ownedEditor.WaitForExit()
    $receipt.owned_editor_exit_observed = $true
    $receipt.owned_editor_exit_code = $ownedEditor.ExitCode
    if ($ownedEditor.ExitCode -ne 0) { throw 'The owned Editor did not exit cleanly.' }
    Assert-SessionAttemptDeadline
    if (@(Get-SessionListener).Count -ne 0) { throw 'A fixed-port listener remains after the owned session exit.' }
    $native = Read-SessionJson (Join-Path $proofRoot 'native-session.json') 1MB
    $transport = Read-SessionJson (Join-Path $proofRoot 'transport-receipt.json') 4MB
    $finalCounter = Read-SessionJson (Join-Path $proofRoot 'native-counter.json') 1MB
    Assert-SessionJsonFields $finalCounter.value @('schema_version', 'exact_sha', 'body_invocation_count')
    $n = $native.value
    $t = $transport.value
    if (-not (Test-SessionInteger $n.schema_version 1) -or $n.exact_sha -cne $ExpectedHead -or $n.status -cne 'NATIVE_BODY_COMPLETED' `
        -or $n.error -cne '' -or -not (Test-SessionInteger $n.owned_editor_pid $ownedEditor.Id) -or $n.map_package -cne $mapPackage `
        -or $n.landscape_path -cne $context.value.landscape.path -or $n.python_startup_complete -isnot [bool] -or -not $n.python_startup_complete `
        -or $n.python_settings_class_path -cne '/Script/PythonScriptPlugin.PythonScriptPluginSettings' `
        -or $n.python_remote_execution -isnot [bool] -or $n.python_remote_execution `
        -or -not (Test-SessionInteger $n.body_invocation_count 1) -or -not (Test-SessionInteger $n.denied_input_count 15) -or $n.operation -cne $operationName `
        -or $n.bundle_hash_verification -cne 'fixed_producer_and_client; not_native_sha256') { throw 'The final native session proof is incomplete or mismatched.' }
    foreach ($flag in @('official_mcp_transport_verified', 'native_bob_capture_verified', 'official_mcp_admitted', 'performance_pass')) {
        if ($n[$flag] -isnot [bool] -or $n[$flag]) { throw 'The native evidence claimed unsupported admission.' }
    }
    Assert-SessionFixedAutomation $n.official_automation_result
    if (-not (Test-SessionInteger $t.schema_version 1) -or $t.exact_sha -cne $ExpectedHead -or $t.status -cne 'LOCAL_TRANSPORT_AND_BOB_ARTIFACTS_VERIFIED' `
        -or -not (Test-SessionInteger $t.owned_editor_pid $ownedEditor.Id) -or $t.official_mcp_transport_verified -isnot [bool] -or -not $t.official_mcp_transport_verified `
        -or $t.valid_call_attempted -isnot [bool] -or -not $t.valid_call_attempted -or -not (Test-SessionInteger $t.body_invocation_count 1) `
        -or $t.persistent_files_unchanged -isnot [bool] -or -not $t.persistent_files_unchanged `
        -or $t.domain_status -cnotin @('REVIEW_REQUIRED', 'INSPECTION_INCOMPLETE') -or @($t.denials).Count -ne 22) { throw 'The fixed transport/bundle/conservation receipt is incomplete.' }
    for ($index = 0; $index -lt 22; $index++) {
        $denial = $t.denials[$index]
        if ($denial.case -cne $clientInputs.denial_cases[$index] -or $denial.explicit_error -isnot [bool] -or -not $denial.explicit_error `
            -or -not (Test-SessionInteger $denial.body_invocation_count 0)) { throw 'A required fixed denial entered a body or is missing from the client receipt.' }
    }
    foreach ($flag in @('official_mcp_admitted', 'native_automation_verified', 'persistent_world_mutation', 'performance_pass')) {
        if ($t[$flag] -isnot [bool] -or $t[$flag]) { throw 'The transport evidence claimed unsupported admission.' }
    }
    if (-not (Test-SessionInteger $finalCounter.value.schema_version 1) -or $finalCounter.value.exact_sha -cne $ExpectedHead `
        -or -not (Test-SessionInteger $finalCounter.value.body_invocation_count 1)) { throw 'The sole valid body counter did not remain exactly one.' }
    if ($t.source_sha256 -isnot [Collections.IDictionary] -or $t.source_sha256.Count -ne $clientInputs.source_sha256.Count `
        -or $t.tool.name -cne $operationName -or $t.endpoint -cne 'http://127.0.0.1:18784/mcp' `
        -or $t.requested_protocol -cne '2025-06-18' -or $t.negotiated_protocol -cne '2025-06-18' `
        -or $t.expected_server_source_sha256 -cne $receipt.observed_official_server_source.sha256) { throw 'The final client source/tool/protocol closure differs.' }
    foreach ($relative in $clientInputs.source_sha256.Keys) {
        if ($t.source_sha256[$relative] -cne $clientInputs.source_sha256[$relative]) { throw 'The final client source hash differs.' }
    }
    foreach ($entry in @(@('session_preparation', 'session-preparation.json'), @('session_context', 'session-context.json'), @('transport_context', 'transport-context.json'))) {
        if ((Get-SessionFileIdentity (Join-Path $proofRoot $entry[1]) 4MB).sha256 -cne $receipt.proof_files[$entry[0]].sha256) { throw 'A fixed preparation/context file changed.' }
    }
    # The trusted fixed client re-read all six bundle files, reran the adapter,
    # checked scene census and conserved project Content/Config/profile bytes.
    $receipt.proof_files.native_session = $native.identity
    $receipt.proof_files.transport_receipt = $transport.identity
    $receipt.proof_files.native_counter = $finalCounter.identity
    $bundleNames = @('capture-proof.json', 'direct-inspection.json', 'native-samples.json', 'proof.json', 'receipt.json', 'result.json')
    Assert-SessionJsonFields $t.bundle $bundleNames
    $receipt.bundle_files = [ordered]@{}
    foreach ($name in $bundleNames) {
        $relative = 'Saved/RuntimeProof/OfficialMcpBob/bundle/' + $name
        $identity = Get-SessionFileIdentity (Join-Path $SessionRoot $relative) 8MB
        if ($t.bundle[$name].path -cne $relative -or $t.bundle[$name].sha256 -cne $identity.sha256 `
            -or -not (Test-SessionInteger $t.bundle[$name].size_bytes $identity.size_bytes)) { throw 'The actual fixed bundle bytes differ from client-verified hashes.' }
        $receipt.bundle_files[$name] = $identity
    }
    # Recheck conservation after native teardown and Editor exit, including
    # untracked Content/Config files. Client conservation alone ends earlier.
    $capture = Read-SessionJson (Join-Path $proofRoot 'bundle/capture-proof.json') 8MB
    if ($capture.identity.sha256 -cne $receipt.bundle_files['capture-proof.json'].sha256) { throw 'The authenticated capture evidence changed.' }
    $validationProgram = 'import hashlib; from scripts.ue import official_mcp_bob_operation as o; print(hashlib.sha256(o.adapter.canonical_json_bytes(o._persistent_snapshot())).hexdigest())'
    $ownedValidation = Start-Process -FilePath $pythonExecutable -ArgumentList @('-c', ('"' + $validationProgram + '"')) `
        -WorkingDirectory $SessionRoot -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $ArtifactRoot 'final-conservation-stdout.log') `
        -RedirectStandardError (Join-Path $ArtifactRoot 'final-conservation-stderr.log') -Environment @{ PYTHONPATH = ''; PYTHONHOME = ''; YACS_OWNER_HANDOFF = '' }
    while (-not $ownedValidation.WaitForExit(200)) { Assert-SessionAttemptDeadline }
    $ownedValidation.WaitForExit()
    if ($ownedValidation.ExitCode -ne 0) { throw 'The final owned persistent-file inventory failed.' }
    $conservation = Get-SessionOwnedLogIdentity (Join-Path $ArtifactRoot 'final-conservation-stdout.log') $ownedValidation -IncludeText
    $digest = $conservation.text.Trim()
    if ($conservation.size_bytes -gt 128 -or $digest -cnotmatch '^[0-9a-f]{64}$' `
        -or $digest -cne $capture.value.persistent_inventory_sha256) { throw 'Content/Config/project bytes changed during native teardown or Editor shutdown.' }
    $conservation.Remove('text')
    $receipt.proof_files.final_conservation_stdout = $conservation
    $receipt.proof_files.final_conservation_stderr = Get-SessionOwnedLogIdentity (Join-Path $ArtifactRoot 'final-conservation-stderr.log') $ownedValidation
    $receipt.final_persistent_inventory_sha256 = $digest
    $receipt.official_automation_result = $n.official_automation_result
    $receipt.domain_status = $t.domain_status
    $receipt.client_source_sha256 = $clientInputs.source_sha256
    Assert-SessionStagedBinaries
    foreach ($root in @($BuildRoot, $SessionRoot, $RepoRoot)) { Assert-SessionTrackedSources $root }
    Assert-SessionNoUntrackedNativeInputs $BuildRoot
    if ((Get-SessionFileIdentity $engineManifest.path 64KB).sha256 -cne $engineManifest.sha256) { throw 'The installed engine manifest changed.' }
    if ((Get-SessionFileIdentity (Join-Path $engine.Root $serverRows[0].path) 2MB).sha256 -cne $serverRows[0].sha256) { throw 'The actual official server source changed.' }
    foreach ($kind in @('client', 'editor')) {
        $process = if ($kind -ceq 'client') { $ownedClient } else { $ownedEditor }
        foreach ($streamName in @('stdout', 'stderr')) {
            $receipt.proof_files[($kind + '_' + $streamName)] = Get-SessionOwnedLogIdentity (Join-Path $ArtifactRoot ('owned-' + $kind + '-' + $streamName + '.log')) $process
        }
    }
    $receipt.proof_files.editor_log = Get-SessionOwnedLogIdentity (Join-Path $ArtifactRoot 'owned-editor.log') $ownedEditor
    Assert-SessionAttemptDeadline
    $receipt.attempt_elapsed_seconds = $attemptTimer.Elapsed.TotalSeconds
    $receipt.official_mcp_transport_verified = $true
    $receipt.native_automation_verified = $true
    $receipt.native_bob_capture_verified = $true
    $receipt.status = 'ACCEPTED_SESSION_LOCAL_PROOF_VERIFIED'
}
catch {
    $receipt.error = $_.Exception.Message
    $receipt.status = 'BLOCKED'
    $receipt.official_mcp_transport_verified = $false
    $receipt.native_automation_verified = $false
    $receipt.native_bob_capture_verified = $false
    throw
}
finally {
    Stop-SessionOwnedProcess $ownedValidation 'validation'
    Stop-SessionOwnedProcess $ownedClient 'client'
    Stop-SessionOwnedProcess $ownedEditor 'editor'
    Stop-SessionOwnedProcess $ownedBuild 'build' -BuildTree
    if ($artifactOwned) {
        Write-SessionJson (Join-Path $ArtifactRoot 'accepted-session-build.json') $receipt
    }
    Write-Host ('YACS_MCP_BOB_SESSION status={0}, acceptedBytes={1}, runtimeVerified={2}.' -f $receipt.status, $receipt.accepted_bytes_staged, $receipt.official_mcp_transport_verified)
}
