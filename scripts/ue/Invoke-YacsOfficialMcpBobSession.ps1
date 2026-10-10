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
    [string] $ExpectedHead,
    # One fixed retained build failure only; no caller-supplied paths or PIDs.
    [switch] $DiagnosePreviousFailure
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
# These are the only frozen scene dependencies outside Content. Their physical
# payloads have separate asset proofs; they are never code/config byte hashes.
$FrozenNonContentAssets = [ordered]@{
    'worldgen/materials/visual_fill/material-weights.png' = @{ sha256 = 'af16fc7c43ec8a3a3b2e000fe716232a3229fe0ac6b4e9708baae5842ef99f6c'; size_bytes = 28497885 }
    'worldgen/materials/visual_fill/sample-availability.png' = @{ sha256 = '9c9906268977a8f49ba20c194cecb101e8bb8c25c44b51ee30f66e7e88a7522a'; size_bytes = 861726 }
    'worldgen/materials/visual_fill/inference-kind.png' = @{ sha256 = 'cc3bc3490878c5a96c20586cd28b0cd3cc812c5506ae97a7110c59e6ed3a3176'; size_bytes = 879841 }
}
$receipt = [ordered]@{
    schema_version = 1; exact_sha = $ExpectedHead; run = $runId; attempt = $attempt
    status = 'PREPARATION_PENDING'; build_root = $BuildRoot; session_root = $SessionRoot
    plugin_package_root = $PluginPackage; engine_identity = $null; build_environment_identity = $null
    source_fingerprints = [ordered]@{}; tracked_source_sha256 = [ordered]@{}
    project_build = $null; plugin_build = $null; binary_provenance = @(); staged_binary_provenance = @()
    frozen_asset_provenance = [ordered]@{}; final_frozen_asset_provenance = [ordered]@{}; frozen_assets_unchanged = $false
    installed_plugin_descriptors = [ordered]@{}
    source_unchanged = $false; accepted_bytes_staged = $false; owned_build_exit_observed = $false
    editor_launched = $false; listener_started = $false; official_mcp_transport_verified = $false
    official_mcp_admitted = $false; native_automation_verified = $false; native_bob_capture_verified = $false
    persistent_world_mutation = $false; performance_pass = $false; performance_status = 'DEFERRED_AFTER_M3'
    error = $null; secondary_errors = @()
    owned_editor_pid = $null; owned_client_pid = $null; owned_editor_exit_observed = $false; owned_client_exit_observed = $false
    startup_config_overrides = @(); host_stage_events = @(); loopback_binding = @(); proof_files = [ordered]@{}
}

function Assert-SessionPlainPath {
    param([Parameter(Mandatory)][string] $Path)
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        try { $attributes = [IO.File]::GetAttributes($cursor) }
        catch [IO.FileNotFoundException] { $attributes = $null }
        catch [IO.DirectoryNotFoundException] { $attributes = $null }
        if ($null -ne $attributes -and ($attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'The session refuses symlinks and junctions.'
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
        $observedSize = if ($before.PSIsContainer) { $null } else { $before.Length }
        $receipt['input_identity_failure'] = [ordered]@{ path = [IO.Path]::GetFullPath($Path)
            size_bytes = $observedSize; limit_bytes = $Limit; is_directory = $before.PSIsContainer }
        throw ('A fixed session input is not a bounded nonempty regular file: path={0}; size_bytes={1}; limit_bytes={2}; is_directory={3}.' -f
            $receipt.input_identity_failure.path, $observedSize, $Limit, $before.PSIsContainer)
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
        if ($relative.StartsWith('Content/', [StringComparison]::Ordinal) -or $relative -cin $FrozenNonContentAssets.Keys) { continue }
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
function Assert-SessionFrozenAssets {
    param([switch] $Final)
    $prepared = Read-SessionJson (Join-Path $SessionRoot 'Saved/RuntimeProof/OfficialMcpBob/session-preparation.json') 4MB
    if ($prepared.identity.sha256 -cne $receipt.proof_files.session_preparation.sha256 `
        -or $prepared.value.exact_sha -cne $ExpectedHead -or $prepared.value.status -cne 'ACCEPTED_CONSUMER_BYTES_STAGED' `
        -or $prepared.value.consumer_source_sha -cne '94827365ef8e83e52717bb21f9d6efa921aa2d1e' `
        -or $prepared.value.source_dependencies -isnot [array] -or $prepared.value.source_dependencies.Count -ne 236) {
        throw 'The fixed asset proof requires unchanged accepted staging evidence.'
    }
    foreach ($relative in $FrozenNonContentAssets.Keys) {
        if ($Final) { Assert-SessionAttemptDeadline }
        $expected = $FrozenNonContentAssets[$relative]
        $rows = @($prepared.value.source_dependencies | Where-Object { $_.path -ceq $relative })
        if ($rows.Count -ne 1) { throw 'A fixed frozen non-Content asset row is missing or duplicated.' }
        Assert-SessionJsonFields $rows[0] @('path', 'sha256', 'size_bytes')
        if ($rows[0].sha256 -cne $expected.sha256 -or -not (Test-SessionInteger $rows[0].size_bytes $expected.size_bytes)) {
            throw 'A fixed asset staging row differs from the frozen LFS payload identity.'
        }
        $actual = Get-SessionFileIdentity (Join-Path $SessionRoot $relative) $expected.size_bytes
        if ($actual.sha256 -cne $expected.sha256 -or $actual.size_bytes -ne $expected.size_bytes) { throw 'A fixed frozen asset payload differs.' }
        if ($Final) {
            if (-not $receipt.frozen_asset_provenance.Contains($relative) `
                -or $actual.sha256 -cne $receipt.frozen_asset_provenance[$relative].sha256 `
                -or $actual.size_bytes -ne $receipt.frozen_asset_provenance[$relative].size_bytes) { throw 'A frozen asset payload changed during the owned session.' }
            $receipt.final_frozen_asset_provenance[$relative] = $actual
        } else { $receipt.frozen_asset_provenance[$relative] = $actual }
    }
    if ($Final) { $receipt.frozen_assets_unchanged = $true }
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
function Write-SessionHostStage {
    param([ValidateSet('WAITING_CONTEXT', 'CONTEXT_VERIFIED', 'TRACKED_SOURCES_VERIFIED', 'TRANSPORT_CONTEXT_PUBLISHED')][string] $Stage)
    $event = [ordered]@{ stage = $Stage; at_utc = (Get-Date).ToUniversalTime().ToString('o')
        attempt_elapsed_seconds = $attemptTimer.Elapsed.TotalSeconds }
    $receipt.host_stage_events += $event
    Write-Host ('SESSION_HOST_STAGE ' + ($event | ConvertTo-Json -Compress))
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
function Get-SessionSafeFailureText {
    param([string] $Text)
    $truncated = $Text.Length -gt 512
    if ($truncated) { $Text = $Text.Substring(0, 512) }
    $safe = [regex]::Replace($Text, '(?i)https?://\S+', '[URL_REDACTED]')
    $safe = [regex]::Replace($safe, '(?i)\b[A-Za-z0-9_]*(?:authorization|bearer|token|secret|password|credential|api.?key|signature|sig)[A-Za-z0-9_]*\s*["'']?\s*[:=]\s*["'']?\S+', '[SECRET_FIELD_REDACTED]')
    if ($safe.Length -gt 512) { $safe = $safe.Substring(0, 512); $truncated = $true }
    if ($truncated) { return $safe + '[TRUNCATED]' }
    return $safe
}
function Read-SessionFixedFailureFile {
    param([ValidateSet('original-project-build.log', 'original-project-build-stderr.log',
        'domain-plugin-build.log', 'domain-plugin-build-stderr.log', 'owned-editor.log',
        'owned-editor-stdout.log', 'owned-editor-stderr.log', 'owned-client-stdout.log', 'owned-client-stderr.log', 'native-session.json', 'accepted-session-build.json', 'session-preparation.json',
        'session-context.json', 'transport-context.json', 'native-counter.json')][string] $Name)
    $limit = if ($Name -ceq 'native-session.json') { 256KB } elseif ($Name -ceq 'accepted-session-build.json') { 1MB }
        elseif ($Name -ceq 'session-preparation.json') { 4MB }
        elseif ($Name -cin @('session-context.json', 'transport-context.json', 'native-counter.json')) { 1MB } else { 32MB }
    if ($DiagnosePreviousFailure) {
        if ($Name -cnotin @('accepted-session-build.json', 'session-preparation.json', 'session-context.json', 'transport-context.json', 'native-counter.json', 'native-session.json', 'owned-editor.log', 'owned-editor-stdout.log', 'owned-editor-stderr.log')) { throw 'Previous failure readback covers only its nine fixed session files.' }
        $path = if ($Name.EndsWith('.json', [StringComparison]::Ordinal) -and $Name -cne 'accepted-session-build.json') {
            Join-Path 'D:\yacs\runner\_work\s384\38013644520-1\Saved\RuntimeProof\OfficialMcpBob' $Name
        } else { Join-Path 'D:\yacs\runner\_work\YetAnotherCyclingSim\YetAnotherCyclingSim\_official-mcp-native-probe\Saved\RuntimeProof\OfficialMcpBobSession\38013644520-1' $Name }
    } else {
        if ($Name -cin @('accepted-session-build.json', 'session-preparation.json', 'session-context.json', 'transport-context.json', 'native-counter.json')) { throw 'Retained context receipts are read only in fixed previous-failure mode.' }
        $path = if ($Name -ceq 'native-session.json') { Join-Path $SessionRoot 'Saved/RuntimeProof/OfficialMcpBob/native-session.json' }
            else { Join-Path $ArtifactRoot $Name }
    }
    Assert-SessionPlainPath $path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $null }
    $before = Get-Item -LiteralPath $path -Force
    $size = $before.Length
    $ticks = $before.LastWriteTimeUtc.Ticks
    $observeMetadata = $DiagnosePreviousFailure -and $Name -cin @('session-context.json', 'transport-context.json')
    if ($observeMetadata) {
        $creationTicks = $before.CreationTimeUtc.Ticks
        $createdUtc = $before.CreationTimeUtc.ToString('o')
        $writtenUtc = $before.LastWriteTimeUtc.ToString('o')
    }
    if ($before.PSIsContainer -or $size -gt $limit -or $readBudget.bytes + $size + 1 -gt 64MB) { throw 'Fixed failure files exceed their read bound.' }
    # Charge the reserved read even if instability later rejects this log.
    $readBudget.bytes += $size + 1
    $stream = [IO.FileStream]::new($path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try {
        $buffer = [byte[]]::new([int]$size + 1)
        $count = 0
        while (($part = $stream.Read($buffer, $count, $buffer.Length - $count)) -gt 0) { $count += $part }
    } finally { $stream.Dispose() }
    Assert-SessionPlainPath $path
    $after = Get-Item -LiteralPath $path -Force
    if ($count -ne $size -or $count -ne $after.Length -or $ticks -ne $after.LastWriteTimeUtc.Ticks) { throw 'Fixed failure log changed during readback.' }
    if ($observeMetadata -and $creationTicks -ne $after.CreationTimeUtc.Ticks) { throw 'Fixed retained context metadata changed during readback.' }
    $bytes = [byte[]]::new($count)
    [Array]::Copy($buffer, $bytes, $count)
    $result = [ordered]@{ bytes = $bytes; text = [Text.Encoding]::UTF8.GetString($bytes); identity = [ordered]@{
        path = [IO.Path]::GetFullPath($path); size_bytes = $count
        sha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
    } }
    if ($observeMetadata) {
        $result['filesystem_metadata'] = [ordered]@{ scope = 'CURRENT_OBSERVED_FILESYSTEM_METADATA; NOT_ORIGINAL_HASH_PINNED_CHRONOLOGY'
            creation_time_utc = $createdUtc; last_write_time_utc = $writtenUtc }
    }
    return $result
}
function Write-SessionFixedFailureLogContext {
    param([string] $Name, $File)
    $lines = $File.text -split '\r?\n'
    $matched = [Collections.Generic.SortedSet[int]]::new()
    $startup = [Collections.Generic.SortedSet[int]]::new()
    $nativeMilestones = [Collections.Generic.SortedSet[int]]::new()
    $categories = [ordered]@{
        engine = '(?i)LogInit:.*(?:Engine Version|Build:)'
        bob = '(?i)LogPluginManager:.*(?:YacsBobInspection|ModelContextProtocol|ToolsetRegistry)|YacsBob|BOB_|LogModelContextProtocol'
        map = '(?i)LogLoad:.*(?:LoadMap|SaCalobra)|LogWorld:.*(?:SaCalobra|Bringing World)'
        python = '(?i)LogPython:|LogPluginManager:.*PythonScriptPlugin'
        automation = '(?i)LogAutomation(?:Controller|Test)|LogPluginManager:.*AutomationTestToolset'
    }
    $categoryLines = [ordered]@{}
    foreach ($category in $categories.Keys) { $categoryLines[$category] = [Collections.Generic.SortedSet[int]]::new() }
    $commandLines = [Collections.Generic.SortedSet[int]]::new()
    for ($index = 0; $index -lt $lines.Length; $index++) {
        if ($DiagnosePreviousFailure -and $lines[$index] -match '(?i)LogInit:\s*Command\s*Line:') {
            [void]$commandLines.Add($index)
            continue
        }
        if ($lines[$index] -match '(?i)error C[0-9]+|fatal error|error LNK[0-9]+|LogPython:.*(?:Error|Fatal)|Traceback|Exception|(?:Runtime|Attribute|Type|Value|Name|Import|ModuleNotFound|Syntax)Error|Assertion failed') {
            for ($line = [Math]::Max(0, $index - 1); $line -le [Math]::Min($index + 2, $lines.Length - 1); $line++) { [void]$matched.Add($line) }
        }
        if ($lines[$index].Contains('LogYacsBobOfficialSession:')) { [void]$nativeMilestones.Add($index) }
        if ($DiagnosePreviousFailure) {
            foreach ($category in $categories.Keys) {
                if ($lines[$index] -match $categories[$category]) {
                    [void]$categoryLines[$category].Add($index)
                    [void]$startup.Add($index)
                }
            }
        }
    }
    $chosen = @($matched | Select-Object -First 16) + @($matched | Select-Object -Last 8)
    if (-not $DiagnosePreviousFailure -and $nativeMilestones.Count -gt 0) {
        $chosen = @($matched | Select-Object -First 12) + @($matched | Select-Object -Last 8) `
            + @($nativeMilestones | Select-Object -First 2) + @($nativeMilestones | Select-Object -Last 2)
    }
    if ($DiagnosePreviousFailure) {
        # Five independently reserved categories (at most four each) plus
        # four error-context lines retain the existing 24-line hard cap.
        $chosen = @($matched | Select-Object -First 2) + @($matched | Select-Object -Last 2)
        foreach ($category in $categories.Keys) {
            $selected = if ($category -ceq 'bob' -and $nativeMilestones.Count -gt 0) { $nativeMilestones } else { $categoryLines[$category] }
            $chosen += @($selected | Select-Object -First 2) + @($selected | Select-Object -Last 2)
        }
    }
    $context = @()
    $identityScope = if ($DiagnosePreviousFailure -and $File.Contains('identity_scope')) { $File.identity_scope }
        elseif ($DiagnosePreviousFailure) { 'CURRENT_OBSERVED_RETAINED_BYTES; NO_ORIGINAL_HOST_HASH' }
        else { 'CURRENT_INVOCATION_OBSERVED_BYTES' }
    $label = if (-not $DiagnosePreviousFailure) { 'CURRENT_SESSION_ERROR ' }
        elseif ($identityScope -ceq 'MATCHES_ORIGINAL_HOST_RECEIPT') { 'PREVIOUS_AUTHENTICATED_SESSION_ERROR ' }
        else { 'CURRENT_OBSERVED_RETAINED_SESSION_ERROR ' }
    foreach ($line in ($chosen | Sort-Object -Unique)) {
        if ($lines[$line] -match '(?i)command\s*line|authorization|bearer\s') { continue }
        $text = Get-SessionSafeFailureText ('{0}:{1}: {2}' -f $Name, ($line + 1), $lines[$line])
        $context += $text
        Write-Host ($label + $text)
    }
    $observations = @()
    if ($DiagnosePreviousFailure) {
        foreach ($line in ((@($commandLines | Select-Object -First 1) + @($commandLines | Select-Object -Last 1)) | Sort-Object -Unique)) {
            $command = [regex]::Match($lines[$line], '(?i)LogInit:\s*Command\s*Line:\s*(?<command>.*)$').Groups['command'].Value
            $plugins = @()
            $enabled = [regex]::Matches($command, '(?i)(?:^|\s)-EnablePlugins=(?:"(?<quoted>[^"]*)"|(?<plain>[^\s"]+))')
            foreach ($enable in $enabled) {
                $value = if ($enable.Groups['quoted'].Success) { $enable.Groups['quoted'].Value } else { $enable.Groups['plain'].Value }
                $plugins += @($value.Split(',') | ForEach-Object { $_.Trim() })
            }
            $observation = [ordered]@{
                line = $line + 1
                identity_scope = $identityScope
                official_proof_opt_in_observed = [regex]::IsMatch($command, '(?i)(?:^|\s)-YacsBobOfficialProof(?=\s|$)')
                enable_plugins_argument_observed = $enabled.Count -gt 0
                bob_enable_plugins_observed = $plugins -icontains 'YacsBobInspection'
                mcp_enable_plugins_observed = $plugins -icontains 'ModelContextProtocol'
            }
            $observations += $observation
            Write-Host ('PREVIOUS_SESSION_LAUNCH_OBSERVATION ' + $Name + ' ' + ($observation | ConvertTo-Json -Compress))
        }
    }
    return [ordered]@{ lines = $context; truncated = ($matched.Count + $startup.Count + $nativeMilestones.Count) -gt $context.Count
        identity_scope = $identityScope
        launch_observations = $observations; command_line_observed = $commandLines.Count -gt 0; launch_observations_truncated = $commandLines.Count -gt $observations.Count }
}
function Invoke-SessionPreviousFailureDiagnostic {
    $previousRoot = 'D:\yacs\runner\_work\YetAnotherCyclingSim\YetAnotherCyclingSim\_official-mcp-native-probe\Saved\RuntimeProof\OfficialMcpBobSession\38013644520-1'
    if (-not [string]::Equals([IO.Path]::GetFullPath((Join-Path $RepoRoot 'Saved/RuntimeProof/OfficialMcpBobSession/38013644520-1')), $previousRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Fixed previous failure requires its exact retained checkout.' }
    $readBudget = [ordered]@{ bytes = 0 }
    $file = Read-SessionFixedFailureFile 'accepted-session-build.json'
    if ($null -eq $file -or $file.identity.size_bytes -ne 442120 -or $file.identity.sha256 -cne '43aabf46532692520645dd4bb5eaf4e6a17f07c873889e6985a657374d290f28') { throw 'The retained host receipt differs from the original console-pinned bytes.' }
    $previous = $file.text | ConvertFrom-Json -AsHashtable -Depth 40
    if ($previous -isnot [Collections.IDictionary] -or -not (Test-SessionInteger $previous.schema_version 1) -or $previous.exact_sha -cne '9b50911a058f1213fad6f17bd85086fa76830e2f' -or $previous.run -cne '38013644520' -or $previous.attempt -cne '1' -or $previous.status -cne 'BLOCKED') { throw 'The retained receipt disagrees with the exact failed run/source.' }
    # Read this original string without ConvertFrom-Json's date coercion.
    $document = [Text.Json.JsonDocument]::Parse([string]$file.text)
    try {
        $start = $document.RootElement.GetProperty('attempt_started_at_utc')
        if ($start.ValueKind -ne [Text.Json.JsonValueKind]::String) { throw 'The pinned attempt start is not an original JSON string.' }
        $attemptStarted = $start.GetString()
    } finally { $document.Dispose() }
    if ($attemptStarted.Length -gt 64 -or $attemptStarted -cnotmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{7}Z$') { throw 'The pinned attempt start is not its bounded UTC timestamp.' }
    $parsedStart = [DateTime]::MinValue
    if (-not [DateTime]::TryParseExact($attemptStarted, 'o', [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind, [ref]$parsedStart)) { throw 'The pinned attempt start is not a valid UTC timestamp.' }
    foreach ($flag in @('accepted_bytes_staged', 'source_unchanged', 'editor_launched')) {
        if ($previous[$flag] -isnot [bool] -or -not $previous[$flag]) { throw 'The exact failed session did not record staging and Editor startup.' }
    }
    foreach ($flag in @('listener_started', 'official_mcp_transport_verified', 'official_mcp_admitted', 'native_automation_verified', 'native_bob_capture_verified', 'persistent_world_mutation', 'performance_pass')) {
        if ($previous[$flag] -isnot [bool] -or $previous[$flag]) { throw 'The fixed failed session contains unsupported verification claims.' }
    }
    if ($null -ne $previous.owned_client_pid -or ($previous.owned_editor_pid -isnot [int] -and $previous.owned_editor_pid -isnot [long]) -or $previous.owned_editor_pid -le 0 -or $previous.proof_files -isnot [Collections.IDictionary]) { throw 'The recorded owned-session boundary differs from the no-client timeout.' }
    $diagnostic = [ordered]@{
        schema_version = 1; exact_sha = $ExpectedHead; previous_run = '38013644520-1'; previous_exact_sha = $previous.exact_sha
        previous_receipt = $file.identity; source_only = $true; compile_performed = $false; editor_launched = $false; listener_started = $false
        official_mcp_admitted = $false; native_automation_verified = $false; native_bob_capture_verified = $false
        status = 'READ_ONLY_NATIVE_READINESS_FAILURE_DIAGNOSTIC'; previous_error = Get-SessionSafeFailureText ([string]$previous.error)
        recorded_session = [ordered]@{}; build_records = [ordered]@{}; files = [ordered]@{}; context = [ordered]@{}; gaps = @()
    }
    $diagnostic.recorded_session['attempt_started_at_utc'] = $attemptStarted
    foreach ($field in @('editor_launched', 'owned_editor_pid', 'owned_client_pid', 'owned_editor_exit_observed', 'owned_client_exit_observed', 'listener_started', 'accepted_bytes_staged')) {
        $value = $previous[$field]
        if ($null -ne $value -and $value -isnot [bool] -and $value -isnot [int] -and $value -isnot [long]) { throw 'A recorded ownership scalar is malformed.' }
        $diagnostic.recorded_session[$field] = $value
    }
    $diagnostic.recorded_session['startup_config_overrides_count'] = @($previous.startup_config_overrides).Count
    $diagnostic.recorded_session['session_context_recorded'] = $previous.proof_files.Contains('session_context')
    $diagnostic.recorded_session['transport_context_recorded'] = $previous.proof_files.Contains('transport_context')
    $diagnostic.recorded_session['secondary_errors'] = @($previous.secondary_errors | Select-Object -First 8 | ForEach-Object { Get-SessionSafeFailureText ([string]$_) })
    $diagnostic.recorded_session['secondary_errors_truncated'] = @($previous.secondary_errors).Count -gt 8
    if ($previous.Contains('python_application_selection')) {
        $selection = $previous.python_application_selection
        if ($selection -isnot [Collections.IDictionary]) { throw 'The recorded Python selection is malformed.' }
        $diagnostic.recorded_session['python_application_selection'] = [ordered]@{}
        foreach ($field in @('selection', 'command_type', 'path')) {
            if ($selection[$field] -isnot [string]) { throw 'The recorded Python selection scalar is malformed.' }
            $diagnostic.recorded_session.python_application_selection[$field] = Get-SessionSafeFailureText $selection[$field]
        }
    }
    Write-Host ('PREVIOUS_RECORDED_SESSION ' + ($diagnostic.recorded_session | ConvertTo-Json -Depth 5 -Compress))
    foreach ($kind in @('project_build', 'plugin_build')) {
        $record = $previous[$kind]
        if ($record -isnot [Collections.IDictionary] -or -not (Test-SessionInteger $record.exit_code 0)) { throw 'The fixed prior session did not record both successful builds.' }
        $diagnostic.build_records[$kind] = [ordered]@{ exit_code = $record.exit_code; executable = Get-SessionSafeFailureText ([string]$record.executable) }
        Write-Host ('PREVIOUS_BUILD_RECORD ' + $kind + ' ' + ($diagnostic.build_records[$kind] | ConvertTo-Json -Compress))
    }
    $target = Join-Path $ArtifactRoot 'previous-accepted-session-build.json'
    Assert-SessionPlainPath $target
    $stream = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($file.bytes, 0, $file.bytes.Length) } finally { $stream.Dispose() }
    foreach ($entry in @(
        @('session-preparation.json', 'session_preparation'), @('session-context.json', 'session_context'),
        @('transport-context.json', 'transport_context'), @('native-counter.json', 'native_counter'),
        @('native-session.json', 'native_failure_receipt'), @('owned-editor.log', 'failure/owned-editor.log'),
        @('owned-editor-stdout.log', 'failure/owned-editor-stdout.log'), @('owned-editor-stderr.log', 'failure/owned-editor-stderr.log')
    )) {
        $name = $entry[0]
        $observation = [ordered]@{ status = 'ABSENT'; original_host_identity_recorded = $previous.proof_files.Contains($entry[1]) }
        $diagnostic.files[$name] = $observation
        try {
            $observed = Read-SessionFixedFailureFile $name
            if ($null -eq $observed) {
                $diagnostic.gaps += ('Retained file absent: ' + $name)
                Write-Host ('PREVIOUS_SESSION_FILE ' + $name + ' ABSENT')
                continue
            }
            $observation['status'] = 'PRESENT'
            $observation['identity'] = $observed.identity
            if ($observation.original_host_identity_recorded) {
                $expected = $previous.proof_files[$entry[1]]
                if ($expected -isnot [Collections.IDictionary] -or $expected.sha256 -cne $observed.identity.sha256 -or -not (Test-SessionInteger $expected.size_bytes $observed.identity.size_bytes) -or -not [string]::Equals([IO.Path]::GetFullPath($expected.path), $observed.identity.path, [StringComparison]::OrdinalIgnoreCase)) { throw 'The retained file differs from its pinned host identity.' }
                $observation['identity_scope'] = 'MATCHES_ORIGINAL_HOST_RECEIPT'
            } else {
                $observation['identity_scope'] = 'CURRENT_OBSERVED_RETAINED_BYTES; NO_ORIGINAL_HOST_HASH'
                $diagnostic.gaps += ('No original host hash for retained ' + $name)
            }
            if ($observed.Contains('filesystem_metadata')) { $observation['filesystem_metadata'] = $observed.filesystem_metadata }
            Write-Host ('PREVIOUS_SESSION_FILE ' + $name + ' ' + ($observation | ConvertTo-Json -Depth 4 -Compress))
            if ($name.EndsWith('.log', [StringComparison]::Ordinal)) {
                $observed['identity_scope'] = $observation.identity_scope
                $diagnostic.context[$name] = Write-SessionFixedFailureLogContext $name $observed
                continue
            }
            $json = $observed.text | ConvertFrom-Json -AsHashtable -Depth 40
            if ($json -isnot [Collections.IDictionary] -or -not (Test-SessionInteger $json.schema_version 1) -or $json.exact_sha -cne $previous.exact_sha) { throw 'The fixed retained JSON source/schema identity differs.' }
            if ($name -ceq 'transport-context.json') {
                if (-not (Test-SessionInteger $json.owned_editor_pid $previous.owned_editor_pid) -or $json.session_context_sha256 -cne $previous.proof_files.session_context.sha256) { throw 'The retained transport marker differs from its owned context.' }
            }
            if ($name -ceq 'native-session.json' -and -not (Test-SessionInteger $json.owned_editor_pid $previous.owned_editor_pid)) { throw 'The native receipt reports another Editor PID.' }
            $summary = [ordered]@{}
            foreach ($field in @('schema_version', 'exact_sha', 'status', 'owned_editor_pid', 'error', 'map_package', 'landscape_path', 'python_startup_complete', 'python_settings_class_path', 'python_remote_execution', 'body_invocation_count', 'denied_input_count', 'native_runtime_verified', 'official_mcp_transport_verified', 'native_bob_capture_verified', 'official_mcp_admitted')) {
                if (-not $json.Contains($field)) { continue }
                $value = $json[$field]
                $summary[$field] = if ($value -is [string]) { Get-SessionSafeFailureText $value } elseif ($null -eq $value -or $value -is [bool] -or $value -is [int] -or $value -is [long]) { $value } else { 'MALFORMED_SCALAR' }
            }
            if ($name -ceq 'session-context.json' -and $json.landscape -is [Collections.IDictionary]) {
                $summary['landscape'] = [ordered]@{ path = Get-SessionSafeFailureText ([string]$json.landscape.path); class_path = Get-SessionSafeFailureText ([string]$json.landscape.class_path) }
            }
            $observation['json_summary'] = $summary
            Write-Host ('PREVIOUS_SESSION_JSON ' + $name + ' ' + ($summary | ConvertTo-Json -Depth 4 -Compress))
        } catch {
            $observation['status'] = 'READ_BLOCKED'
            $observation['error'] = Get-SessionSafeFailureText $_.Exception.Message
            $observation['exception_type'] = $_.Exception.GetType().Name
            $diagnostic.gaps += ('Retained read/validation blocked: ' + $name)
            Write-Host ('PREVIOUS_SESSION_FILE ' + $name + ' ' + ($observation | ConvertTo-Json -Depth 4 -Compress))
        }
    }
    Write-SessionJson (Join-Path $ArtifactRoot 'previous-session-failure-diagnostic.json') $diagnostic
    $receipt['diagnostic_previous_run'] = '38013644520-1'
    $receipt.proof_files.previous_session_failure_diagnostic = Get-SessionFileIdentity (Join-Path $ArtifactRoot 'previous-session-failure-diagnostic.json') 1MB
    $receipt.proof_files.previous_failed_receipt = Get-SessionFileIdentity $target 1MB
    Write-Host ('PREVIOUS_SESSION_FAILURE ' + $diagnostic.previous_error)
}
function Write-SessionCurrentFailureReadback {
    if (-not $artifactOwned -or $receipt.status -cne 'BLOCKED') { return }
    $readBudget = [ordered]@{ bytes = 0 }
    $receipt['current_failure_context'] = [ordered]@{}
    $groups = @(
        @{ exited = $receipt.owned_build_exit_observed; names = @('original-project-build.log', 'original-project-build-stderr.log', 'domain-plugin-build.log', 'domain-plugin-build-stderr.log') },
        @{ exited = $receipt.owned_editor_exit_observed; names = @('owned-editor.log', 'owned-editor-stdout.log', 'owned-editor-stderr.log') },
        @{ exited = $receipt.owned_client_exit_observed; names = @('owned-client-stdout.log', 'owned-client-stderr.log') }
    )
    foreach ($group in $groups) {
        if ($group.exited -ne $true) { continue }
        foreach ($name in $group.names) {
            try {
                $file = Read-SessionFixedFailureFile $name
                if ($null -eq $file) { continue }
                $receipt.proof_files[('failure/' + $name)] = $file.identity
                $receipt.current_failure_context[$name] = Write-SessionFixedFailureLogContext $name $file
            } catch { $receipt.secondary_errors += ('Cannot read fixed current failure log: ' + $name + ' (' + $_.Exception.GetType().Name + ').') }
        }
    }
    if ($receipt.owned_editor_exit_observed -eq $true) {
        try {
            $file = Read-SessionFixedFailureFile 'native-session.json'
            if ($null -ne $file) {
                $native = $file.text | ConvertFrom-Json -AsHashtable -Depth 16
                if ($native -isnot [Collections.IDictionary]) { throw 'Fixed native failure receipt is not an object.' }
                $summary = [ordered]@{}
                foreach ($field in @('schema_version', 'exact_sha', 'status', 'owned_editor_pid', 'error')) {
                    if (-not $native.Contains($field)) { continue }
                    $value = $native[$field]
                    $summary[$field] = if ($value -is [string]) { Get-SessionSafeFailureText $value }
                        elseif ($null -eq $value -or $value -is [bool] -or $value -is [int] -or $value -is [long]) { $value }
                        else { 'MALFORMED_SCALAR' }
                }
                $receipt.proof_files.native_failure_receipt = $file.identity
                $receipt['current_native_failure'] = $summary
                Write-Host ('CURRENT_NATIVE_SESSION ' + ($summary | ConvertTo-Json -Depth 4 -Compress))
            }
        } catch { $receipt.secondary_errors += ('Cannot read fixed native failure receipt (' + $_.Exception.GetType().Name + ').') }
    }
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
    if ($DiagnosePreviousFailure) {
        Invoke-SessionPreviousFailureDiagnostic
        $receipt.status = 'PREVIOUS_SESSION_FAILURE_DIAGNOSTIC_RETAINED'
        return
    }
    # Establish fixed executable identities before expensive builds; their raw
    # bytes are checked again immediately before the owned session launch.
    Assert-SessionPlainPath $engine.UnrealEditorPath
    $receipt.owned_editor_executable = Get-SessionFileIdentity $engine.UnrealEditorPath 1GB
    $pythonCommand = Get-Command python -CommandType Application -ErrorAction Stop | Select-Object -First 1
    if ($pythonCommand -isnot [System.Management.Automation.ApplicationInfo] -or $pythonCommand.Source -isnot [string] `
        -or [string]::IsNullOrWhiteSpace($pythonCommand.Source) -or $pythonCommand.Source.Length -gt 1024) { throw 'The first resolved Python application lacks one bounded executable path.' }
    [string]$pythonExecutable = $pythonCommand.Source
    $receipt['python_application_selection'] = [ordered]@{ selection = 'FIRST_APPLICATION_IN_COMMAND_RESOLUTION_ORDER'
        command_type = [string]$pythonCommand.CommandType; path = $pythonExecutable }
    Write-Host ('SELECTED_PYTHON_APPLICATION ' + ($receipt.python_application_selection | ConvertTo-Json -Depth 3 -Compress))
    $receipt.owned_client_executable = Get-SessionFileIdentity $pythonExecutable 128MB
    & (Join-Path $RepoRoot 'scripts/ue/Read-YacsOfficialMcpRuntimeDependencies.ps1') -EngineRoot $engine.Root -ArtifactRoot $ArtifactRoot -ExpectedHead $ExpectedHead
    $sdk = Read-SessionJson (Join-Path $ArtifactRoot 'runtime-dependencies.json') 4MB
    if ($sdk.value.exact_sha -cne $ExpectedHead -or $sdk.value.source_only -isnot [bool] -or -not $sdk.value.source_only) { throw 'The observed installed SDK receipt differs from this source-bound session.' }
    $serverRows = @($sdk.value.source_files | Where-Object { $_.path.EndsWith('/ModelContextProtocolServer.cpp', [StringComparison]::Ordinal) })
    if ($serverRows.Count -ne 1 -or $serverRows[0].sha256 -cne '56e519b8a956a1d916f421781767f85a999d02b9e02f806b3594d96b96d2a104') { throw 'The actual installed official MCP Server source does not match the fixed reviewed protocol.' }
    $receipt.proof_files.runtime_dependencies = $sdk.identity
    $receipt.observed_official_server_source = $serverRows[0]
    foreach ($spec in @(
        @('ModelContextProtocol', 'Engine/Plugins/Experimental/ModelContextProtocol/ModelContextProtocol.uplugin', '74420534edcd6baafcb48e0af919d53b84891bdade7b97869b0ef485c3ea1518'),
        @('AutomationTestToolset', 'Engine/Plugins/Experimental/Toolsets/AutomationTestToolset/AutomationTestToolset.uplugin', 'ef31f3689ede040b005d6bcb7ec2886d16fac5c7c47b9aad1060c5d0fd01b78b'),
        @('ToolsetRegistry', 'Engine/Plugins/Experimental/ToolsetRegistry/ToolsetRegistry.uplugin', '2dfc01159b54daea67c62966a48b78254d1d848d84e8df48c708c7a69d3f2062'),
        @('PythonScriptPlugin', 'Engine/Plugins/Experimental/PythonScriptPlugin/PythonScriptPlugin.uplugin', $null)
    )) {
        $descriptor = Read-SessionJson (Join-Path $engine.Root $spec[1]) 64KB
        $metadata = $descriptor.value
        if ($null -ne $spec[2] -and $descriptor.identity.sha256 -cne $spec[2]) { throw 'An installed official plugin descriptor differs from its reviewed hash.' }
        if (($metadata.Version -isnot [int] -and $metadata.Version -isnot [long]) -or $metadata.Version -lt 0 `
            -or $metadata.VersionName -isnot [string] -or $metadata.VersionName.Length -gt 128 `
            -or $metadata.Modules -isnot [array] -or $metadata.Modules.Count -lt 1 -or $metadata.Modules.Count -gt 16) {
            throw 'An installed fixed plugin descriptor lacks bounded version/module metadata.'
        }
        $modules = @()
        foreach ($module in $metadata.Modules) {
            if ($module -isnot [Collections.IDictionary] -or $module.Name -cnotmatch '^[A-Za-z][A-Za-z0-9_]{0,127}$' `
                -or $module.Type -isnot [string] -or $module.Type.Length -gt 64) { throw 'A fixed installed plugin module record is malformed.' }
            $row = [ordered]@{ name = $module.Name; type = $module.Type }
            if ($module.Contains('LoadingPhase')) {
                if ($module.LoadingPhase -isnot [string] -or $module.LoadingPhase.Length -gt 64) { throw 'A fixed plugin loading phase is malformed.' }
                $row['loading_phase'] = $module.LoadingPhase
            }
            $modules += $row
        }
        $receipt.installed_plugin_descriptors[$spec[0]] = [ordered]@{ identity = $descriptor.identity
            version = $metadata.Version; version_name = $metadata.VersionName; modules = $modules; reviewed_sha256 = $spec[2] }
        Write-Host ('INSTALLED_SESSION_PLUGIN ' + $spec[0] + ' ' + ($receipt.installed_plugin_descriptors[$spec[0]] | ConvertTo-Json -Depth 6 -Compress))
    }
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
    Assert-SessionFrozenAssets
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
    if ((Get-SessionFileIdentity $engine.UnrealEditorPath 1GB).sha256 -cne $receipt.owned_editor_executable.sha256 `
        -or (Get-SessionFileIdentity $pythonExecutable 128MB).sha256 -cne $receipt.owned_client_executable.sha256) { throw 'A fixed executable changed after the accepted-session preflight.' }
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
    Write-SessionHostStage 'WAITING_CONTEXT'
    $context = Wait-SessionObject (Join-Path $proofRoot 'session-context.json') $ownedEditor
    Assert-SessionJsonFields $context.value @('schema_version', 'exact_sha', 'source_sha256', 'profile_sha256', 'profile_source_sha', 'consumer_source_sha', 'consumer_assets', 'landscape')
    if (-not (Test-SessionInteger $context.value.schema_version 1) -or $context.value.exact_sha -cne $ExpectedHead `
        -or $context.value.landscape.path -isnot [string] -or [string]::IsNullOrWhiteSpace($context.value.landscape.path)) { throw 'The actual native session context is invalid.' }
    Write-SessionHostStage 'CONTEXT_VERIFIED'
    Assert-SessionTrackedSources $SessionRoot
    Write-SessionHostStage 'TRACKED_SOURCES_VERIFIED'
    $receipt.proof_files.session_context = $context.identity
    $marker = [ordered]@{
        schema_version = 1; exact_sha = $ExpectedHead; project_root = $SessionRoot
        owned_editor_pid = $ownedEditor.Id; source_sha256 = $clientInputs.source_sha256
        session_context_sha256 = $context.identity.sha256
    }
    Write-SessionJson (Join-Path $proofRoot 'transport-context.json') $marker
    $receipt.proof_files.transport_context = Get-SessionFileIdentity (Join-Path $proofRoot 'transport-context.json') 1MB
    Write-SessionHostStage 'TRANSPORT_CONTEXT_PUBLISHED'
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
    Assert-SessionFrozenAssets -Final
    Assert-SessionStagedBinaries
    foreach ($root in @($BuildRoot, $SessionRoot, $RepoRoot)) { Assert-SessionTrackedSources $root }
    Assert-SessionNoUntrackedNativeInputs $BuildRoot
    if ((Get-SessionFileIdentity $engineManifest.path 64KB).sha256 -cne $engineManifest.sha256) { throw 'The installed engine manifest changed.' }
    if ((Get-SessionFileIdentity (Join-Path $engine.Root $serverRows[0].path) 2MB).sha256 -cne $serverRows[0].sha256) { throw 'The actual official server source changed.' }
    foreach ($descriptor in $receipt.installed_plugin_descriptors.Values) {
        if ((Get-SessionFileIdentity $descriptor.identity.path 64KB).sha256 -cne $descriptor.identity.sha256) { throw 'A fixed installed plugin descriptor changed during the session.' }
    }
    $result = Read-SessionJson (Join-Path $proofRoot 'bundle/result.json') 8MB
    if ($result.identity.sha256 -cne $receipt.bundle_files['result.json'].sha256 `
        -or $result.value.exact_sha -cne $ExpectedHead -or $result.value.role -cne 'INSPECTOR_ONLY' `
        -or $result.value.status -cne $receipt.domain_status -or $result.value.inspection_complete -isnot [bool]) { throw 'The fixed BOB finding summary does not match its authenticated result.' }
    $receipt['bob_finding_summary'] = [ordered]@{ identity = $result.identity; status = $result.value.status
        role = $result.value.role; inspection_complete = $result.value.inspection_complete }
    foreach ($field in @('sample_count', 'evaluated_sample_count', 'trace_miss_count')) {
        $value = $result.value[$field]
        if (($value -isnot [int] -and $value -isnot [long]) -or $value -lt 0) { throw 'The authenticated BOB sample counts are malformed.' }
        $receipt.bob_finding_summary[$field] = $value
    }
    Assert-SessionJsonFields $result.value.class_counts @('CONTACT_OK', 'CUT_REQUIRED', 'FILL_REQUIRED', 'STRUCTURE_REVIEW')
    foreach ($value in $result.value.class_counts.Values) {
        if (($value -isnot [int] -and $value -isnot [long]) -or $value -lt 0) { throw 'The authenticated BOB class counts are malformed.' }
    }
    $receipt.bob_finding_summary['class_counts'] = $result.value.class_counts
    foreach ($field in @('max_cut_required_m', 'max_fill_required_m', 'rms_required_adjustment_m')) {
        $value = $result.value[$field]
        if (($value -isnot [double] -and $value -isnot [int] -and $value -isnot [long]) `
            -or -not [double]::IsFinite([double]$value) -or $value -lt 0) { throw 'The authenticated BOB adjustment summary is malformed.' }
        $receipt.bob_finding_summary[$field] = $value
    }
    foreach ($flag in @('earthworks_authoring_permitted', 'geometry_repair_executed', 'road_admitted', 'eligible_for_learning')) {
        if ($result.value[$flag] -isnot [bool] -or $result.value[$flag]) { throw 'The authenticated BOB result expanded its authority.' }
        $receipt.bob_finding_summary[$flag] = $result.value[$flag]
    }
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
    $receipt['failure_script_stack_trace'] = @($_.ScriptStackTrace -split '\r?\n' | Select-Object -First 8 | ForEach-Object { Get-SessionSafeFailureText $_ })
    foreach ($line in $receipt.failure_script_stack_trace) { Write-Host ('CURRENT_SESSION_STACK ' + $line) }
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
        if ($receipt.status -ceq 'BLOCKED') {
            try { Write-SessionCurrentFailureReadback }
            catch { $receipt.secondary_errors += ('Cannot retain current failure readback (' + $_.Exception.GetType().Name + ').') }
        }
        $receiptPath = Join-Path $ArtifactRoot 'accepted-session-build.json'
        Write-SessionJson $receiptPath $receipt
        Write-Host ('SESSION_HOST_RECEIPT_IDENTITY ' + ((Get-SessionFileIdentity $receiptPath 1MB) | ConvertTo-Json -Depth 4 -Compress))
        if ($receipt.status -ceq 'ACCEPTED_SESSION_LOCAL_PROOF_VERIFIED') {
            $summary = [ordered]@{ exact_sha = $receipt.exact_sha; run = $receipt.run; attempt = $receipt.attempt; status = $receipt.status
                summary_scope = 'BOUNDED_VERIFIED_FINDINGS_AND_IDENTITIES; NOT_COMPLETE_RAW_BUNDLE_REVIEW'
                domain_status = $receipt.domain_status; bob_findings = $receipt.bob_finding_summary
                official_automation_result = $receipt.official_automation_result
                native_session = $receipt.proof_files.native_session; transport_receipt = $receipt.proof_files.transport_receipt
                native_counter = $receipt.proof_files.native_counter; bundle_files = $receipt.bundle_files
                frozen_assets = $receipt.frozen_asset_provenance; final_frozen_assets = $receipt.final_frozen_asset_provenance
                frozen_assets_unchanged = $receipt.frozen_assets_unchanged; final_persistent_inventory_sha256 = $receipt.final_persistent_inventory_sha256
                official_mcp_transport_verified = $receipt.official_mcp_transport_verified; native_automation_verified = $receipt.native_automation_verified
                native_bob_capture_verified = $receipt.native_bob_capture_verified; official_mcp_admitted = $receipt.official_mcp_admitted
                persistent_world_mutation = $receipt.persistent_world_mutation; performance_pass = $receipt.performance_pass; performance_status = $receipt.performance_status }
            $summaryJson = $summary | ConvertTo-Json -Depth 10 -Compress
            if ($summaryJson.Length -gt 16KB) { Write-Host ('VERIFIED_SESSION_SUMMARY ' + $summaryJson.Substring(0, 16KB) + '[CONSOLE_TRUNCATED]') }
            else { Write-Host ('VERIFIED_SESSION_SUMMARY ' + $summaryJson) }
        }
    }
    Write-Host ('YACS_MCP_BOB_SESSION status={0}, acceptedBytes={1}, runtimeVerified={2}.' -f $receipt.status, $receipt.accepted_bytes_staged, $receipt.official_mcp_transport_verified)
}
