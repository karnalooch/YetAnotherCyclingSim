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
    # Fixed GREEN readback and isolated InputBoundary unit; no caller paths or PIDs.
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
        'session-context.json', 'transport-context.json', 'native-counter.json', 'transport-receipt.json')][string] $Name)
    $limit = if ($Name -ceq 'native-session.json') { 256KB } elseif ($Name -ceq 'accepted-session-build.json') { 1MB }
        elseif ($Name -cin @('session-preparation.json', 'transport-receipt.json')) { 4MB }
        elseif ($Name -cin @('session-context.json', 'transport-context.json', 'native-counter.json')) { 1MB } else { 32MB }
    if ($DiagnosePreviousFailure) {
        if ($Name -cnotin @('accepted-session-build.json', 'session-preparation.json', 'session-context.json', 'transport-context.json', 'native-counter.json', 'native-session.json', 'transport-receipt.json', 'owned-editor.log', 'owned-editor-stdout.log', 'owned-editor-stderr.log')) { throw 'Previous failure readback covers only its ten fixed session files.' }
        $path = if ($Name.EndsWith('.json', [StringComparison]::Ordinal) -and $Name -cne 'accepted-session-build.json') {
            Join-Path 'D:\yacs\runner\_work\s384\38025560494-1\Saved\RuntimeProof\OfficialMcpBob' $Name
        } else { Join-Path 'D:\yacs\runner\_work\YetAnotherCyclingSim\YetAnotherCyclingSim\_official-mcp-native-probe\Saved\RuntimeProof\OfficialMcpBobSession\38025560494-1' $Name }
    } else {
        if ($Name -cin @('accepted-session-build.json', 'session-preparation.json', 'session-context.json', 'transport-context.json', 'native-counter.json', 'transport-receipt.json')) { throw 'Retained context receipts are read only in fixed previous-failure mode.' }
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
    $operationMilestones = [Collections.Generic.SortedSet[int]]::new()
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
        if ($lines[$index] -match '(?i)error C[0-9]+|fatal error|error LNK[0-9]+|LogPython:.*(?:Error|Fatal)|Traceback|Exception|(?:Runtime|Attribute|Type|Value|Name|Import|ModuleNotFound|Syntax)Error|Assertion failed|YACS_MCP_BOB_CLIENT_FAILURE') {
            for ($line = [Math]::Max(0, $index - 1); $line -le [Math]::Min($index + 2, $lines.Length - 1); $line++) { [void]$matched.Add($line) }
        }
        if ($lines[$index].Contains('LogYacsBobOfficialSession:')) { [void]$nativeMilestones.Add($index) }
        if ($lines[$index].Contains('YACS_MCP_BOB_OPERATION ')) { [void]$operationMilestones.Add($index) }
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
    if (-not $DiagnosePreviousFailure -and $operationMilestones.Count -gt 0) {
        $chosen = @($matched | Select-Object -First 8) + @($matched | Select-Object -Last 8) `
            + @($nativeMilestones | Select-Object -First 2) + @($nativeMilestones | Select-Object -Last 2) `
            + @($operationMilestones | Select-Object -First 2) + @($operationMilestones | Select-Object -Last 2)
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
function Read-SessionVerifiedGreenJson {
    param([string] $Path, $Expected, [long] $Limit, $Budget)
    if ($Expected -isnot [Collections.IDictionary] -or $Expected.path -isnot [string] `
        -or -not [string]::Equals([IO.Path]::GetFullPath($Expected.path), [IO.Path]::GetFullPath($Path), [StringComparison]::OrdinalIgnoreCase) `
        -or $Expected.sha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'A GREEN evidence identity is not bound to its fixed path.' }
    $remaining = 64MB - $Budget.bytes
    if ($remaining -le 0) { throw 'The fixed GREEN JSON inventory exhausts its 64MiB aggregate bound.' }
    $identity = Get-SessionFileIdentity $Path ([Math]::Min($Limit, $remaining))
    if ($identity.sha256 -cne $Expected.sha256 -or -not (Test-SessionInteger $Expected.size_bytes $identity.size_bytes)) {
        throw 'A GREEN raw evidence file differs from its authenticated original identity before parsing.'
    }
    $Budget.bytes += $identity.size_bytes
    $parsed = Read-SessionJson $Path ([Math]::Min($Limit, $remaining))
    if ($parsed.identity.sha256 -cne $identity.sha256) { throw 'A GREEN evidence file changed during its authenticated read.' }
    # Retain the authenticated raw JSON bytes for review, without serializing
    # parsed values back into a file and relabeling them as original bytes.
    $target = Join-Path $ArtifactRoot ('verified-original-' + [IO.Path]::GetFileName($Path))
    Assert-SessionPlainPath $target
    $sourceStream = [IO.File]::OpenRead($Path)
    $output = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $buffer = [byte[]]::new(8192)
        $copiedBytes = 0L
        while (($count = $sourceStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $copiedBytes += $count
            if ($copiedBytes -gt $identity.size_bytes) { throw 'A raw GREEN copy grew beyond its authenticated byte bound.' }
            $output.Write($buffer, 0, $count)
        }
    } finally { $output.Dispose(); $sourceStream.Dispose() }
    $retained = Get-SessionFileIdentity $target $identity.size_bytes
    if ($retained.sha256 -cne $identity.sha256 -or (Get-SessionFileIdentity $Path $identity.size_bytes).sha256 -cne $identity.sha256) {
        throw 'The exclusive retained raw GREEN JSON copy differs.'
    }
    $parsed['retained_raw'] = $retained
    return $parsed
}
function Add-SessionUnitProtectedIdentity {
    param($Rows, [string] $Path, $Expected, [long] $Limit = 512MB)
    if ($Rows.Contains($Path)) { return }
    if ($Rows.Count -ge 160) { throw 'The fixed unit conservation inventory exceeds 160 files.' }
    $actual = Get-SessionFileIdentity $Path $Limit
    if ($null -ne $Expected -and ($Expected -isnot [Collections.IDictionary] `
        -or -not [string]::Equals([IO.Path]::GetFullPath($Expected.path), $actual.path, [StringComparison]::OrdinalIgnoreCase) `
        -or $Expected.sha256 -cne $actual.sha256 -or -not (Test-SessionInteger $Expected.size_bytes $actual.size_bytes))) {
        throw 'A protected GREEN input differs from its original successful identity.'
    }
    $total = $actual.size_bytes
    foreach ($row in $Rows.Values) { $total += $row.size_bytes }
    if ($total -gt 2GB) { throw 'The fixed unit conservation inventory exceeds 2GiB.' }
    $Rows[$Path] = $actual
}
function Assert-SessionUnitProtectedIdentities {
    param($Rows)
    foreach ($row in $Rows.Values) {
        $actual = Get-SessionFileIdentity $row.path $row.size_bytes
        if ($actual.sha256 -cne $row.sha256 -or $actual.size_bytes -ne $row.size_bytes) { throw 'A protected GREEN or unit input changed.' }
    }
}
function Assert-SessionFiniteActorProperty {
    param($Value, [int] $Depth = 0, $Counter)
    if ($Depth -gt 8 -or $Counter.nodes -ge 128) { throw 'A captured Actor transform exceeds its fixed structural bound.' }
    $Counter.nodes++
    if ($Value -is [array]) {
        if ($Value.Count -lt 1 -or $Value.Count -gt 16) { throw 'A captured Actor property array is empty or oversized.' }
        foreach ($item in $Value) { Assert-SessionFiniteActorProperty $item ($Depth + 1) $Counter }
    } elseif (($Value -is [int] -or $Value -is [long] -or $Value -is [double] -or $Value -is [decimal]) `
        -and -not [double]::IsNaN([double]$Value) -and -not [double]::IsInfinity([double]$Value)) { $Counter.numbers++ }
    else { throw 'A captured Actor transform is not a finite numeric property array.' }
}
function Get-SessionIntegratedMainProvenance {
    $mainSha = '5272f044f230329359813135e53297fa33cf8f74'
    $parentSha = 'c9a47903e1c8bb871cd68996262a32c23923a006'
    # The Actions checkout is shallow. Fetch only these pinned objects and a
    # bounded current ancestry; never depend on persistent runner Git history.
    $gitCommand = Get-Command git -CommandType Application -ErrorAction Stop | Select-Object -First 1
    if ($gitCommand -isnot [System.Management.Automation.ApplicationInfo] -or $gitCommand.Source -isnot [string] `
        -or [string]::IsNullOrWhiteSpace($gitCommand.Source) -or $gitCommand.Source.Length -gt 1024) { throw 'The provenance fetch requires one bounded Git application path.' }
    $fetchStdout = Join-Path $ArtifactRoot 'integrated-main-fetch-stdout.log'
    $fetchStderr = Join-Path $ArtifactRoot 'integrated-main-fetch-stderr.log'
    try {
        $script:ownedValidation = Start-Process -FilePath $gitCommand.Source -WorkingDirectory $RepoRoot -PassThru -NoNewWindow `
            -ArgumentList @('-c', 'gc.auto=0', 'fetch', '--depth=16', '--no-tags', '--no-write-fetch-head', '--no-recurse-submodules',
                'origin', $ExpectedHead, $mainSha, $parentSha, '241104de320f8417c7abc4dd973ac148ed98a66d') `
            -RedirectStandardOutput $fetchStdout -RedirectStandardError $fetchStderr -Environment @{ GIT_TERMINAL_PROMPT = '0' }
        if (-not $script:ownedValidation.WaitForExit(60000)) { throw 'The fixed provenance fetch exceeded sixty seconds.' }
        $script:ownedValidation.WaitForExit()
        if ($script:ownedValidation.ExitCode -ne 0) { throw 'The fixed provenance fetch did not complete successfully.' }
        $receipt.proof_files.integrated_main_fetch_stdout = Get-SessionOwnedLogIdentity $fetchStdout $script:ownedValidation
        $receipt.proof_files.integrated_main_fetch_stderr = Get-SessionOwnedLogIdentity $fetchStderr $script:ownedValidation
    } finally { Stop-SessionOwnedProcess $script:ownedValidation 'validation' -BuildTree; $script:ownedValidation = $null }
    $paths = @('.gumball/candidates/scoped-agent-role-authority-routing.json', 'AGENTS.md', 'docs/README.md',
        'docs/ai/DECISION_LIFECYCLE.md', 'docs/ai/README.md', 'docs/ai/ROLE_REGISTRY.json', 'docs/ai/TASK_HANDOFF.md',
        'docs/ai/policies/CODE_PHYSICS_UNREAL.md', 'docs/ai/policies/DELIVERY_AND_SCOPE.md', 'docs/ai/policies/DOCS_AND_PLATFORM.md',
        'docs/ai/policies/GIT_AND_PROJECT.md', 'docs/ai/policies/M3_WORLD_OPERATIONS.md', 'docs/ai/policies/TOOLING_AND_AI_SAFETY.md',
        'docs/ai/roles/docs-governor.md', 'docs/ai/roles/physics-gameplay.md', 'docs/ai/roles/procedural-world.md',
        'docs/ai/roles/proof-qa.md', 'docs/ai/roles/road-bob.md', 'docs/ai/roles/unreal-integration.md',
        'docs/ai/roles/visual-dcc.md', 'docs/ai/roles/world-data.md', 'scripts/ci/agent_contracts.py',
        'scripts/ci/test_agent_contracts.py', 'scripts/ci/test_embark_terrain_pipeline_contract.py')
    $parent = @(& git -C $RepoRoot rev-parse ($mainSha + '^'))
    if ($LASTEXITCODE -ne 0 -or $parent.Count -ne 1 -or $parent[0] -cne $parentSha) { throw 'The integrated main parent cannot be authenticated.' }
    & git -C $RepoRoot merge-base --is-ancestor $mainSha $ExpectedHead
    if ($LASTEXITCODE -ne 0) { throw 'The pinned main commit is not an ancestor of the executing source.' }
    $delta = @(& git -C $RepoRoot diff --name-only $parent[0] $mainSha --)
    if ($LASTEXITCODE -ne 0 -or $delta.Count -ne 24 -or @(Compare-Object $paths $delta -CaseSensitive).Count -ne 0) { throw 'The integrated main delta differs from its fixed twenty-four paths.' }
    $tree = @(& git -C $RepoRoot ls-tree -r $mainSha -- @paths)
    if ($LASTEXITCODE -ne 0 -or $tree.Count -ne 24) { throw 'The integrated main Git blob inventory differs.' }
    $blobs = [ordered]@{}
    foreach ($row in $tree) {
        if ($row -cnotmatch '^100644 blob ([0-9a-f]{40})\t(.+)$') { throw 'An integrated main path is not a fixed regular Git blob.' }
        if ($Matches[2] -cnotin $paths -or $blobs.Contains($Matches[2])) { throw 'An integrated main blob path is missing or repeated.' }
        $blobs[$Matches[2]] = $Matches[1]
    }
    $currentPaths = @($paths | ForEach-Object { Join-Path $RepoRoot $_ })
    $currentIdentities = [ordered]@{}
    $identityBytes = 0L
    foreach ($relative in $paths) {
        $remaining = 64MB - $identityBytes
        if ($remaining -le 0) { throw 'The integrated main raw inputs exhaust their64MiB bound.' }
        $identity = Get-SessionFileIdentity (Join-Path $RepoRoot $relative) ([Math]::Min(16MB, $remaining))
        if (-not $receipt.tracked_source_sha256.Contains($relative) -or $receipt.tracked_source_sha256[$relative] -cne $identity.sha256) { throw 'An integrated main raw input differs from the initial tracked inventory.' }
        $currentIdentities[$relative] = $identity
        $identityBytes += $identity.size_bytes
    }
    $currentTree = @(& git -C $RepoRoot ls-tree -r $ExpectedHead -- @paths)
    if ($LASTEXITCODE -ne 0 -or $currentTree.Count -ne 24) { throw 'The executing main-path Git inventory differs.' }
    $headBlobs = [ordered]@{}
    foreach ($row in $currentTree) {
        if ($row -cnotmatch '^100644 blob ([0-9a-f]{40})\t(.+)$') { throw 'An executing main input is not a regular Git blob.' }
        if ($Matches[2] -cnotin $paths -or $headBlobs.Contains($Matches[2])) { throw 'An executing main input is missing or repeated.' }
        $headBlobs[$Matches[2]] = $Matches[1]
    }
    $currentBlobs = @(& git -C $RepoRoot hash-object --no-filters -- @currentPaths)
    if ($LASTEXITCODE -ne 0 -or $currentBlobs.Count -ne 24) { throw 'The current main-path raw Git blob inventory cannot be authenticated.' }
    $rows = [ordered]@{}
    for ($index = 0; $index -lt 24; $index++) {
        $relative = $paths[$index]
        if ($currentBlobs[$index] -cnotmatch '^[0-9a-f]{40}$') { throw 'A current main-path raw Git blob is malformed.' }
        $after = Get-SessionFileIdentity $currentIdentities[$relative].path $currentIdentities[$relative].size_bytes
        if ($after.sha256 -cne $currentIdentities[$relative].sha256 -or $after.size_bytes -ne $currentIdentities[$relative].size_bytes `
            -or $currentBlobs[$index] -cne $headBlobs[$relative]) {
            $receipt['integrated_main_identity_failure'] = [ordered]@{ relative_path = $relative; path_index = $index
                before = $currentIdentities[$relative]; after = $after; raw_git_blob = $currentBlobs[$index]; head_git_blob = $headBlobs[$relative]
                raw_bytes_unchanged = $after.sha256 -ceq $currentIdentities[$relative].sha256 -and $after.size_bytes -eq $currentIdentities[$relative].size_bytes
                raw_blob_equals_head = $currentBlobs[$index] -ceq $headBlobs[$relative] }
            $failureJson = $receipt.integrated_main_identity_failure | ConvertTo-Json -Depth 5 -Compress
            if ([Text.Encoding]::UTF8.GetByteCount($failureJson) -gt 4KB) { throw 'The main input failure metadata exceeds its4KiB bound.' }
            Write-Host ('MAIN_INPUT_IDENTITY_FAILURE ' + $failureJson)
            throw 'A bounded main raw input changed or differs from executing HEAD.'
        }
        $exception = $relative -cin @('docs/README.md', 'docs/ai/policies/M3_WORLD_OPERATIONS.md')
        if (-not $exception -and $currentBlobs[$index] -cne $blobs[$relative]) { throw 'An unmodified main-policy input differs from its pinned main blob.' }
        $rows[$relative] = [ordered]@{ main_git_blob = $blobs[$relative]; current_raw_git_blob = $currentBlobs[$index]
            current_raw_sha256 = $currentIdentities[$relative].sha256; current_identity = $currentIdentities[$relative]
            current_head_git_blob = $headBlobs[$relative]
            scope = if ($exception) { 'EXPLICIT_DOCUMENTATION_MERGE_DELTA; NOT_UNMODIFIED_MAIN_BYTES' } else { 'CURRENT_RAW_BYTES_EQUAL_PINNED_MAIN_BLOB' } }
    }
    return [ordered]@{ main_sha = $mainSha; parent_sha = $parent[0]; path_count = 24; paths = $paths; identities = $rows
        raw_input_bytes = $identityBytes; raw_input_limit_bytes = 64MB; member_limit_bytes = 16MB; ancestry_fetch_depth = 16 }
}
function Invoke-SessionVerifiedGreenReadback {
    $receipt['source_only'] = $true
    $receipt['compile_performed'] = $false
    $receipt['native_input_boundary_verified'] = $false
    $oldSha = '241104de320f8417c7abc4dd973ac148ed98a66d'
    $oldArtifact = 'D:\yacs\runner\_work\YetAnotherCyclingSim\YetAnotherCyclingSim\_official-mcp-native-probe\Saved\RuntimeProof\OfficialMcpBobSession\38027596123-1'
    $oldSession = 'D:\yacs\runner\_work\s384\38027596123-1'
    $oldPackage = 'D:\yacs\runner\_work\b384\38027596123-1-session-plugin'
    $oldProject = 'D:\yacs\runner\_work\b384\38027596123-1-session-project'
    $oldHostProject = Join-Path $oldPackage 'HostProject'
    $oldPlugin = Join-Path $oldHostProject 'Plugins/YacsBobInspection'
    $oldProof = Join-Path $oldSession 'Saved/RuntimeProof/OfficialMcpBob'
    $budget = [ordered]@{ bytes = 0L }
    $protected = [ordered]@{}
    $hostPath = Join-Path $oldArtifact 'accepted-session-build.json'
    $verifiedHostDocument = Read-SessionVerifiedGreenJson $hostPath @{
        path = $hostPath; size_bytes = 449384; sha256 = 'e42ec494ed4835a007fe5133f7379434b71088ab1d0018e88ffcec28c6500353'
    } 1MB $budget
    $h = $verifiedHostDocument.value
    if (-not (Test-SessionInteger $h.schema_version 1) -or $h.exact_sha -cne $oldSha -or $h.run -cne '38027596123' `
        -or $h.attempt -cne '1' -or $h.status -cne 'ACCEPTED_SESSION_LOCAL_PROOF_VERIFIED' `
        -or $h.build_root -cne $oldProject -or $h.session_root -cne $oldSession -or $h.plugin_package_root -cne $oldPackage `
        -or $h.engine_identity -cne $receipt.engine_identity -or $h.build_environment_identity -cne $receipt.build_environment_identity) {
        throw 'The authenticated GREEN host disagrees with its fixed source, roots, run or current engine environment.'
    }
    foreach ($flag in @('source_unchanged', 'accepted_bytes_staged', 'owned_build_exit_observed', 'editor_launched', 'listener_started',
        'official_mcp_transport_verified', 'native_automation_verified', 'native_bob_capture_verified', 'owned_editor_exit_observed',
        'owned_client_exit_observed', 'frozen_assets_unchanged')) {
        if ($h[$flag] -isnot [bool] -or -not $h[$flag]) { throw 'The GREEN host lacks a required original verification flag.' }
    }
    foreach ($flag in @('official_mcp_admitted', 'persistent_world_mutation', 'performance_pass')) {
        if ($h[$flag] -isnot [bool] -or $h[$flag]) { throw 'The GREEN host claims unsupported admission.' }
    }
    if ($h.performance_status -cne 'DEFERRED_AFTER_M3' -or -not (Test-SessionInteger $h.owned_editor_pid 42184) `
        -or -not (Test-SessionInteger $h.owned_client_pid 38260) -or -not (Test-SessionInteger $h.owned_editor_exit_code 0) `
        -or -not (Test-SessionInteger $h.owned_client_exit_code 0) -or $h.secondary_errors.Count -ne 0 `
        -or $null -ne $h.error -or $h.loopback_binding -isnot [array] -or $h.loopback_binding.Count -ne 1 `
        -or $h.loopback_binding[0].address -cne '127.0.0.1' -or -not (Test-SessionInteger $h.loopback_binding[0].port 18784) `
        -or -not (Test-SessionInteger $h.loopback_binding[0].owned_editor_pid 42184)) { throw 'The GREEN ownership, exit or listener record differs.' }
    foreach ($kind in @('project_build', 'plugin_build')) {
        if ($h[$kind] -isnot [Collections.IDictionary] -or -not (Test-SessionInteger $h[$kind].exit_code 0)) { throw 'A GREEN actual build did not succeed.' }
    }
    # This lane builds a new test binary. It never reuses the original binary
    # for changed source or relabels its historical compile fingerprint.
    $testPath = 'Plugins/YacsBobInspection/Source/YacsBobInspection/Private/Tests/YacsBobInputBoundary.spec.cpp'
    $oldTestHash = '5c55e7cf7146b0215c783b60630a2480f5f60bb21ab531af20f662b972823606'
    $newTestHash = '4c6840fc4db6f4f3585a4e6830df43bb0756a2033b3a0d083e38132c7640c82c'
    $allowedChanges = @('AGENTS.md', 'Plugins/YacsBobInspection/README.md', 'docs/ASSET_PLAN.md', 'docs/README.md',
        'docs/ROADMAP.md', 'docs/UE_MCP_WORLD_GENERATION.md', 'docs/WORLD_BUILDING_BIBLE.md',
        'docs/tooling/SA_CALOBRA_WHOLE_MAP_SURFACE_PREPARATION.md', '.gumball/candidates/native-domain-tool-input-boundary.json',
        '.github/workflows/official-unreal-mcp-native-probe.yml', 'scripts/ue/Invoke-YacsOfficialMcpBobSession.ps1', $testPath)
    $integratedMain = Get-SessionIntegratedMainProvenance
    $allowedChanges += $integratedMain.paths
    # These two immutable Git blobs differ only by the two literal LF rules.
    # Windows working .gitattributes bytes need not equal the LF Git blob.
    $oldAttributes = @(& git -C $RepoRoot ls-tree $oldSha -- .gitattributes)
    if ($LASTEXITCODE -ne 0 -or $oldAttributes.Count -ne 1 `
        -or $oldAttributes[0] -cne "100644 blob b9c496b1bbf3be643862a8d23eec8aa63c79ee4e`t.gitattributes") { throw 'The original attributes Git blob differs.' }
    $currentAttributes = @(& git -C $RepoRoot ls-tree $ExpectedHead -- .gitattributes)
    if ($LASTEXITCODE -ne 0 -or $currentAttributes.Count -ne 1 `
        -or $currentAttributes[0] -cne "100644 blob 2f0493d000243006536e3a0cc0374fed641523e2`t.gitattributes") { throw 'The attributes delta is not exactly the two admitted LF rules.' }
    $attributesDelta = [ordered]@{ path = '.gitattributes'; original_git_blob = 'b9c496b1bbf3be643862a8d23eec8aa63c79ee4e'
        current_git_blob = '2f0493d000243006536e3a0cc0374fed641523e2'; scope = 'EXACT_TWO_LINE_LF_CHECKOUT_DELTA; NOT_ORIGINAL_ATTRIBUTE_BYTES'
        added_rules = @('.gumball/candidates/scoped-agent-role-authority-routing.json text eol=lf', 'docs/ai/ROLE_REGISTRY.json text eol=lf')
        current_raw_sha256 = $receipt.tracked_source_sha256['.gitattributes'] }
    $allowedChanges += '.gitattributes'
    $changed = @(& git -C $RepoRoot diff --name-only $oldSha $ExpectedHead --)
    if ($LASTEXITCODE -ne 0 -or $changed.Count -gt $allowedChanges.Count) { throw 'Cannot establish the bounded original-to-unit source delta.' }
    foreach ($relative in $changed) {
        if ($relative -cnotin $allowedChanges) { throw 'A current compiler, Python, policy or asset input differs from the original successful source.' }
    }
    $oldTestBlob = @(& git -C $RepoRoot rev-parse ($oldSha + ':' + $testPath))
    if ($LASTEXITCODE -ne 0 -or $oldTestBlob.Count -ne 1 -or $oldTestBlob[0] -cne '2989c4e2693ab35c06555111aa240b92c503b47b' `
        -or $h.tracked_source_sha256[$testPath] -cne $oldTestHash -or $receipt.tracked_source_sha256[$testPath] -cne $newTestHash) {
        throw 'The old Git test blob or the exact new unit-only test bytes differ.'
    }
    $read = [ordered]@{}
    foreach ($row in @(@('session-preparation.json', 'session_preparation', 4MB), @('session-context.json', 'session_context', 1MB),
        @('transport-context.json', 'transport_context', 1MB), @('native-counter.json', 'native_counter', 1MB),
        @('native-session.json', 'native_session', 1MB), @('transport-receipt.json', 'transport_receipt', 4MB))) {
        $read[$row[0]] = Read-SessionVerifiedGreenJson (Join-Path $oldProof $row[0]) $h.proof_files[$row[1]] $row[2] $budget
    }
    foreach ($name in @('capture-proof.json', 'direct-inspection.json', 'native-samples.json', 'proof.json', 'receipt.json', 'result.json')) {
        $limit = if ($name -ceq 'native-samples.json') { 32MB } else { 8MB }
        $read[$name] = Read-SessionVerifiedGreenJson (Join-Path $oldProof ('bundle/' + $name)) $h.bundle_files[$name] $limit $budget
    }
    $c = $read['session-context.json'].value
    $prep = $read['session-preparation.json'].value
    $marker = $read['transport-context.json'].value
    $n = $read['native-session.json'].value
    $t = $read['transport-receipt.json'].value
    $capture = $read['capture-proof.json'].value
    $result = $read['result.json'].value
    $map = '/Game/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview'
    $tool = 'YacsBobInspection.InspectAcceptedCheckpoint'
    foreach ($file in $read.Values) {
        if (-not (Test-SessionInteger $file.value.schema_version 1) -or $file.value.exact_sha -cne $oldSha) { throw 'A GREEN JSON schema/source identity differs.' }
        Add-SessionUnitProtectedIdentity $protected $file.identity.path $file.identity $file.identity.size_bytes
    }
    Add-SessionUnitProtectedIdentity $protected $hostPath $verifiedHostDocument.identity 1MB
    Assert-SessionJsonFields $c @('schema_version', 'exact_sha', 'source_sha256', 'profile_sha256', 'profile_source_sha', 'consumer_source_sha', 'consumer_assets', 'landscape')
    Assert-SessionJsonFields $marker @('schema_version', 'exact_sha', 'project_root', 'owned_editor_pid', 'source_sha256', 'session_context_sha256')
    Assert-SessionJsonFields $read['native-counter.json'].value @('schema_version', 'exact_sha', 'body_invocation_count')
    if ($c.profile_sha256 -cne 'c0ca612dd5af5a311d1917e41d66f44aa83a9d40eed5e9e784432e06e2a52253' `
        -or $c.profile_source_sha -cne 'c5573b3cf545c51ce83ad1fb0a5ca3111f5ad7f6' -or $c.consumer_source_sha -cne '94827365ef8e83e52717bb21f9d6efa921aa2d1e' `
        -or $prep.status -cne 'ACCEPTED_CONSUMER_BYTES_STAGED' -or $prep.consumer_source_sha -cne $c.consumer_source_sha `
        -or $prep.profile_sha256 -cne $c.profile_sha256 -or $c.consumer_assets -isnot [array] -or $c.consumer_assets.Count -ne 14 `
        -or ($c.consumer_assets | ConvertTo-Json -Depth 6 -Compress) -cne ($prep.consumer_assets | ConvertTo-Json -Depth 6 -Compress) `
        -or $c.landscape.class_path -cne '/Script/Landscape.Landscape' -or $c.landscape.path -isnot [string] `
        -or -not $c.landscape.path.StartsWith($map + '.', [StringComparison]::Ordinal) `
        -or $marker.project_root -cne $oldSession -or -not (Test-SessionInteger $marker.owned_editor_pid 42184) `
        -or $marker.session_context_sha256 -cne $read['session-context.json'].identity.sha256 `
        -or -not (Test-SessionInteger $read['native-counter.json'].value.body_invocation_count 1)) { throw 'The accepted context/profile/consumer/native counter binding differs.' }
    if ($n.status -cne 'NATIVE_BODY_COMPLETED' -or $n.error -cne '' -or -not (Test-SessionInteger $n.owned_editor_pid 42184) `
        -or $n.map_package -cne $map -or $n.landscape_path -cne $c.landscape.path -or $n.operation -cne $tool `
        -or $n.python_startup_complete -isnot [bool] -or -not $n.python_startup_complete `
        -or $n.python_settings_class_path -cne '/Script/PythonScriptPlugin.PythonScriptPluginSettings' `
        -or $n.python_remote_execution -isnot [bool] -or $n.python_remote_execution `
        -or -not (Test-SessionInteger $n.body_invocation_count 1) -or -not (Test-SessionInteger $n.denied_input_count 15) `
        -or $n.bundle_hash_verification -cne 'fixed_producer_and_client; not_native_sha256') { throw 'The original native checkpoint result differs.' }
    Assert-SessionFixedAutomation $n.official_automation_result
    if ($t.status -cne 'LOCAL_TRANSPORT_AND_BOB_ARTIFACTS_VERIFIED' -or -not (Test-SessionInteger $t.owned_editor_pid 42184) `
        -or $t.official_mcp_transport_verified -isnot [bool] -or -not $t.official_mcp_transport_verified `
        -or $t.valid_call_attempted -isnot [bool] -or -not $t.valid_call_attempted -or -not (Test-SessionInteger $t.body_invocation_count 1) `
        -or $t.persistent_files_unchanged -isnot [bool] -or -not $t.persistent_files_unchanged -or $t.domain_status -cne 'REVIEW_REQUIRED' `
        -or $t.endpoint -cne 'http://127.0.0.1:18784/mcp' -or $t.requested_protocol -cne '2025-06-18' -or $t.negotiated_protocol -cne '2025-06-18' `
        -or $t.expected_server_source_sha256 -cne '56e519b8a956a1d916f421781767f85a999d02b9e02f806b3594d96b96d2a104' `
        -or $t.tool.name -cne $tool -or $t.tool.inputSchema.type -cne 'object' -or $t.tool.inputSchema.properties.Count -ne 0 `
        -or $t.tool.inputSchema.additionalProperties -isnot [bool] -or $t.tool.inputSchema.additionalProperties `
        -or -not (Test-SessionInteger $t.tool.inputSchema.maxProperties 0) -or $t.denials -isnot [array] -or $t.denials.Count -ne 22) { throw 'The original transport/inventory/protocol receipt differs.' }
    $cases = @('unknown_operation', 'unknown_scene_candidate', 'unknown_actor_candidate', 'unknown_object_candidate',
        'unknown_automation_candidate', 'unknown_dispatch_candidate', 'unknown_python_candidate', 'field', 'policy', 'evidence_root',
        'receipt_path', 'map', 'object_path', 'test', 'body', 'mixed_fields', 'null', 'array', 'scalar_string', 'scalar_number', 'scalar_boolean', 'missing_arguments')
    for ($index = 0; $index -lt 22; $index++) {
        $denial = $t.denials[$index]
        $category = if ($index -lt 7) { 'UNKNOWN_TOOL' } else { 'ARGUMENTS_REJECTED' }
        if ($denial.case -cne $cases[$index] -or $denial.expected_category -cne $category -or $denial.explicit_error -isnot [bool] `
            -or -not $denial.explicit_error -or -not (Test-SessionInteger $denial.body_invocation_count 0)) { throw 'A GREEN denial order/category/body-zero record differs.' }
    }
    foreach ($flag in @('official_mcp_transport_verified', 'native_bob_capture_verified')) {
        if ($n[$flag] -isnot [bool] -or $n[$flag]) { throw 'The native receipt promoted a host-owned proof flag.' }
    }
    if ($prep.native_runtime_verified -isnot [bool] -or $prep.native_runtime_verified -or $prep.persistent_world_mutation -isnot [bool] `
        -or $prep.persistent_world_mutation) { throw 'The preparation claimed native or persistent admission.' }
    foreach ($value in @($n, $prep)) {
        foreach ($flag in @('official_mcp_admitted', 'performance_pass')) {
            if ($value[$flag] -isnot [bool] -or $value[$flag]) { throw 'A domain or native receipt claimed unsupported admission.' }
        }
    }
    foreach ($flag in @('official_mcp_admitted', 'native_automation_verified', 'persistent_world_mutation', 'performance_pass')) {
        if ($t[$flag] -isnot [bool] -or $t[$flag]) { throw 'The transport readback claimed unsupported admission.' }
    }
    if ($capture.consumer.asset_inventory_sha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'The consumer capture inventory hash is malformed.' }
    if ($capture.scope -cne 'BOB_CAPTURE_AND_DOMAIN_COMPARISON; HOST_ADMISSION_PENDING' -or $capture.context_sha256 -cne $read['session-context.json'].identity.sha256 `
        -or $capture.profile.sha256 -cne $c.profile_sha256 -or $capture.profile.source_exact_sha -cne $c.profile_source_sha `
        -or $capture.consumer.source_exact_sha -cne $c.consumer_source_sha -or $capture.scene.map_package -cne $map `
        -or $capture.scene.landscape.path -cne $c.landscape.path -or $capture.scene.landscape.class_path -cne $c.landscape.class_path `
        -or $capture.persistent_inventory_sha256 -cne $h.final_persistent_inventory_sha256 `
        -or $capture.native_sample_sha256 -cne $read['native-samples.json'].identity.sha256 -or -not (Test-SessionInteger $capture.sample_count 60025)) { throw 'The GREEN capture context/input/conservation binding differs.' }
    foreach ($flag in @('direct_invocation_matches', 'persistent_files_unchanged', 'scene_snapshot_unchanged')) {
        if ($capture[$flag] -isnot [bool] -or -not $capture[$flag]) { throw 'The capture lacks its original equality/conservation evidence.' }
    }
    foreach ($flag in @('native_capture_verified', 'official_mcp_verified', 'persistent_content_verified',
        'earthworks_authoring_permitted', 'geometry_repair_executed', 'road_admitted', 'eligible_for_learning')) {
        if ($capture[$flag] -isnot [bool] -or $capture[$flag]) { throw 'The capture claimed unsupported authority.' }
    }
    if ($capture.scene.actors -isnot [array] -or $capture.scene.actors.Count -lt 1 -or $capture.scene.actors.Count -gt 20000) { throw 'The captured Actor census is missing or oversized.' }
    $actors = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($actor in $capture.scene.actors) {
        if ($actor -isnot [array] -or $actor.Count -ne 2 -or $actor[0] -isnot [string] -or $actor[0].Length -gt 1024 `
            -or -not $actor[0].StartsWith($map + '.', [StringComparison]::Ordinal) -or -not $actors.Add($actor[0]) -or $actor[1] -isnot [array]) { throw 'A captured Actor identity/property row differs.' }
        $counter = [ordered]@{ nodes = 0; numbers = 0 }
        Assert-SessionFiniteActorProperty $actor[1] 0 $counter
        if ($counter.numbers -lt 1) { throw 'A captured Actor transform has no numeric property.' }
    }
    if (-not $actors.Contains($c.landscape.path)) { throw 'The unique guarded native Landscape is absent from the capture census.' }
    if ($result.role -cne 'INSPECTOR_ONLY' -or $result.status -cne 'REVIEW_REQUIRED' -or $result.inspection_complete -isnot [bool] `
        -or -not $result.inspection_complete -or -not (Test-SessionInteger $result.sample_count 60025) `
        -or -not (Test-SessionInteger $result.evaluated_sample_count 60025) -or -not (Test-SessionInteger $result.trace_miss_count 0) `
        -or $read['direct-inspection.json'].identity.sha256 -cne $read['result.json'].identity.sha256) { throw 'The original domain result/equality differs.' }
    foreach ($flag in @('earthworks_authoring_permitted', 'geometry_repair_executed', 'road_admitted', 'eligible_for_learning')) {
        if ($result[$flag] -isnot [bool] -or $result[$flag]) { throw 'The domain result claimed authoring or engineering authority.' }
    }
    foreach ($name in @('capture-proof.json', 'direct-inspection.json', 'native-samples.json', 'proof.json', 'receipt.json', 'result.json')) {
        $row = $t.bundle[$name]
        if ($row.path -cne ('Saved/RuntimeProof/OfficialMcpBob/bundle/' + $name) -or $row.sha256 -cne $read[$name].identity.sha256 `
            -or -not (Test-SessionInteger $row.size_bytes $read[$name].identity.size_bytes)) { throw 'The original transport packet bundle identity differs.' }
    }
    $proof = $read['proof.json'].value
    $samples = $read['native-samples.json'].value
    if (-not [string]::Equals([IO.Path]::GetFullPath($proof.input.path), [IO.Path]::GetFullPath((Join-Path $oldProof 'bundle/native-samples.json')), [StringComparison]::OrdinalIgnoreCase) `
        -or $proof.input.sha256 -cne $read['native-samples.json'].identity.sha256 -or -not (Test-SessionInteger $proof.input.size_bytes $read['native-samples.json'].identity.size_bytes) `
        -or $proof.output.sha256 -cne $read['result.json'].identity.sha256 -or $proof.direct_invocation_sha256 -cne $read['result.json'].identity.sha256 `
        -or $samples.samples -isnot [array] -or $samples.samples.Count -ne 60025) { throw 'The actual domain proof input/output/direct byte links differ.' }
    foreach ($flag in @('direct_invocation_matches', 'input_bytes_unchanged', 'source_bytes_unchanged')) {
        if ($proof[$flag] -isnot [bool] -or -not $proof[$flag]) { throw 'The domain proof lacks original equality/conservation evidence.' }
    }
    $bobReceipt = $read['receipt.json'].value
    foreach ($flag in @('native_capture_verified', 'official_mcp_verified', 'persistent_content_verified',
        'earthworks_authoring_permitted', 'geometry_repair_executed', 'road_admitted', 'eligible_for_learning')) {
        if ($bobReceipt[$flag] -isnot [bool] -or $bobReceipt[$flag]) { throw 'The domain receipt claimed unsupported admission.' }
    }
    if ($bobReceipt.result.sha256 -cne $read['result.json'].identity.sha256 -or $bobReceipt.proof.sha256 -cne $read['proof.json'].identity.sha256) { throw 'The original domain receipt links differ.' }
    foreach ($pair in @(@($c.source_sha256, $capture.source_sha256), @($c.source_sha256, $prep.source_sha256), @($marker.source_sha256, $t.source_sha256), @($marker.source_sha256, $h.client_source_sha256))) {
        if ($pair[0] -isnot [Collections.IDictionary] -or $pair[1] -isnot [Collections.IDictionary] -or $pair[0].Count -lt 3 `
            -or $pair[0].Count -gt 64 -or $pair[0].Count -ne $pair[1].Count) { throw 'A GREEN source closure is missing or oversized.' }
        foreach ($relative in $pair[0].Keys) {
            if ($pair[0][$relative] -cne $pair[1][$relative] -or $h.tracked_source_sha256[$relative] -cne $pair[0][$relative] `
                -or $relative -cnotmatch '^(?:scripts/(?:ue|ci|worldgen|geometry|assets)/[A-Za-z0-9_/.-]+\.(?:py|ps1)|scripts/(?:committed_git_blobs|manage_local_workspace)\.py|worldgen/terrain/adaptive_terrain_policy\.json|Plugins/YacsBobInspection/(?:Source/[A-Za-z0-9_/.-]+|YacsBobInspection\.uplugin|README\.md))$' `
                -or $relative -cmatch '(^|/)\.\.?(/|$)' -or $pair[0][$relative] -cnotmatch '^[0-9a-f]{64}$') { throw 'A GREEN source path/hash differs from committed inputs.' }
            $path = Join-Path $oldSession $relative
            $identity = Get-SessionFileIdentity $path 16MB
            if ($identity.sha256 -cne $pair[0][$relative]) { throw 'Actual retained GREEN source bytes differ.' }
            Add-SessionUnitProtectedIdentity $protected $path $identity 16MB
            if ($relative -cnotin @($testPath, 'Plugins/YacsBobInspection/README.md', 'scripts/ue/Invoke-YacsOfficialMcpBobSession.ps1') `
                -and $receipt.tracked_source_sha256[$relative] -cne $pair[0][$relative]) { throw 'Current runtime source differs from the authenticated original closure.' }
        }
    }
    $oldHead = @(& git -C $oldSession rev-parse HEAD)
    if ($LASTEXITCODE -ne 0 -or $oldHead.Count -ne 1 -or $oldHead[0] -cne $oldSha) { throw 'The retained GREEN checkout has a different HEAD.' }
    $profilePath = Join-Path $oldProof 'profile.json'
    $profileIdentity = Get-SessionFileIdentity $profilePath 32MB
    if ($profileIdentity.sha256 -cne $c.profile_sha256) { throw 'The retained fixed profile differs.' }
    Add-SessionUnitProtectedIdentity $protected $profilePath $profileIdentity 32MB
    $runtime = Read-SessionVerifiedGreenJson (Join-Path $oldArtifact 'runtime-dependencies.json') $h.proof_files.runtime_dependencies 4MB $budget
    Add-SessionUnitProtectedIdentity $protected $runtime.identity.path $runtime.identity 4MB
    if ($runtime.value.exact_sha -cne $oldSha -or $runtime.value.source_only -isnot [bool] -or -not $runtime.value.source_only `
        -or $runtime.value.source_files -isnot [array] -or $runtime.value.source_files.Count -ne 30) { throw 'The historical installed SDK source inventory differs.' }
    foreach ($row in $runtime.value.source_files) {
        if ($row.path -isnot [string] -or -not $row.path.StartsWith('Engine/', [StringComparison]::Ordinal) `
            -or $row.path -cmatch '(^|/)\.\.?(/|$)|[\\:\x00]' -or $row.sha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'An installed SDK source row has an unsafe path.' }
        $path = Join-Path $engine.Root $row.path
        $identity = Get-SessionFileIdentity $path 2MB
        if ($identity.sha256 -cne $row.sha256) { throw 'Current installed API source differs from the GREEN SDK source observation.' }
        Add-SessionUnitProtectedIdentity $protected $path $identity 2MB
    }
    Add-SessionUnitProtectedIdentity $protected (Join-Path $engine.Root 'Engine/Binaries/Win64/UnrealEditor.modules') $h.installed_engine_module_manifest 64KB
    $engineModules = Read-SessionJson (Join-Path $engine.Root 'Engine/Binaries/Win64/UnrealEditor.modules') 64KB
    if ($engineModules.value.BuildId -cne $h.installed_engine_build_id) { throw 'The current installed engine BuildId differs from GREEN compilation.' }
    foreach ($spec in @(@('ModelContextProtocol', 'Engine/Plugins/Experimental/ModelContextProtocol'),
        @('AutomationTestToolset', 'Engine/Plugins/Experimental/Toolsets/AutomationTestToolset'), @('ToolsetRegistry', 'Engine/Plugins/Experimental/ToolsetRegistry'),
        @('PythonScriptPlugin', 'Engine/Plugins/Experimental/PythonScriptPlugin'))) {
        Add-SessionUnitProtectedIdentity $protected (Join-Path $engine.Root ($spec[1] + '/' + $spec[0] + '.uplugin')) $h.installed_plugin_descriptors[$spec[0]].identity 64KB
    }
    $sdkLibraries = [ordered]@{}
    foreach ($spec in @(@('ModelContextProtocol', 'Engine/Plugins/Experimental/ModelContextProtocol'),
        @('AutomationTestToolset', 'Engine/Plugins/Experimental/Toolsets/AutomationTestToolset'), @('ToolsetRegistry', 'Engine/Plugins/Experimental/ToolsetRegistry'))) {
        $manifestPath = Join-Path $engine.Root ($spec[1] + '/Binaries/Win64/UnrealEditor.modules')
        $manifest = Read-SessionJson $manifestPath 64KB
        $dllName = 'UnrealEditor-' + $spec[0] + '.dll'
        if ($manifest.value.BuildId -cne $h.installed_engine_build_id -or $manifest.value.Modules[$spec[0]] -cne $dllName) { throw 'A current installed SDK module does not match the successful engine BuildId.' }
        $dllPath = Join-Path $engine.Root ($spec[1] + '/Binaries/Win64/' + $dllName)
        Add-SessionUnitProtectedIdentity $protected $manifestPath $manifest.identity 64KB
        Add-SessionUnitProtectedIdentity $protected $dllPath $null 512MB
        $sdkLibraries[$spec[0]] = [ordered]@{ scope = 'CURRENT_OBSERVED_INSTALLED_BYTES; NOT_HISTORICAL_DLL_HASH'
            manifest = $manifest.identity; binary = $protected[$dllPath] }
    }
    $expectedCompiled = [ordered]@{}
    foreach ($relative in @('Binaries/Win64/UnrealEditor.modules', 'Binaries/Win64/UnrealEditor-YetAnotherCyclingSim.dll',
        'Binaries/Win64/UnrealEditor-YetAnotherCyclingSimEditor.dll', 'Plugins/RoadForge/Binaries/Win64/UnrealEditor.modules',
        'Plugins/RoadForge/Binaries/Win64/UnrealEditor-RoadForge.dll')) {
        $expectedCompiled[(Join-Path $oldProject $relative)] = $relative
        $expectedCompiled[(Join-Path $oldSession $relative)] = $relative
    }
    foreach ($relative in @('Binaries/Win64/UnrealEditor.modules', 'Binaries/Win64/UnrealEditor-YacsBobInspection.dll')) {
        $expectedCompiled[(Join-Path $oldPlugin $relative)] = $relative
        $expectedCompiled[(Join-Path $oldSession ('Plugins/YacsBobInspection/' + $relative))] = 'Plugins/YacsBobInspection/' + $relative
    }
    $seenCompiled = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($row in @($h.binary_provenance + $h.staged_binary_provenance)) {
        $path = [IO.Path]::GetFullPath($row.identity.path)
        if (-not $expectedCompiled.Contains($path) -or $row.relative -cne $expectedCompiled[$path] -or -not $seenCompiled.Add($path)) { throw 'A GREEN compiled-output identity escapes its fixed closure.' }
        Add-SessionUnitProtectedIdentity $protected $path $row.identity 512MB
    }
    if ($h.binary_provenance.Count -ne 7 -or $h.staged_binary_provenance.Count -ne 7) { throw 'The historical seven-file original/staged compiled closure differs.' }
    $bobRows = @(Get-SessionModuleClosure $oldPlugin 'Binaries/Win64/UnrealEditor.modules' @{ YacsBobInspection = 'UnrealEditor-YacsBobInspection.dll' } $h.installed_engine_build_id)
    foreach ($row in $bobRows) {
        if (-not $protected.Contains($row.identity.path) -or $protected[$row.identity.path].sha256 -cne $row.identity.sha256) { throw 'The unit Bob binary/module closure lacks its historical build identity.' }
    }
    $prefix = 'Plugins/YacsBobInspection/'
    $nativePaths = @($receipt.tracked_source_sha256.Keys | Where-Object { $_ -ceq ($prefix + 'YacsBobInspection.uplugin') -or $_.StartsWith($prefix + 'Source/', [StringComparison]::Ordinal) })
    if ($nativePaths.Count -ne 12) { throw 'The current tracked native plugin inventory differs from the fixed twelve-input closure.' }
    $oldNativePaths = @($h.tracked_source_sha256.Keys | Where-Object { $_ -ceq ($prefix + 'YacsBobInspection.uplugin') -or $_.StartsWith($prefix + 'Source/', [StringComparison]::Ordinal) })
    if ($oldNativePaths.Count -ne $nativePaths.Count) { throw 'Current native plugin inventory differs from successful compilation.' }
    foreach ($relative in $nativePaths) {
        if ($relative -cne $testPath -and $h.tracked_source_sha256[$relative] -cne $receipt.tracked_source_sha256[$relative]) { throw 'A current native runtime input differs from successful compilation.' }
        $path = Join-Path $oldPlugin $relative.Substring($prefix.Length)
        $identity = Get-SessionFileIdentity $path 16MB
        if ($identity.sha256 -cne $h.tracked_source_sha256[$relative]) { throw 'Actual old compiled native source differs from its tracked inventory.' }
        if ($relative -ceq $testPath) {
            $actualOldBlob = @(& git -C $RepoRoot hash-object -- $path)
            if ($LASTEXITCODE -ne 0 -or $actualOldBlob.Count -ne 1 -or $actualOldBlob[0] -cne $oldTestBlob[0] `
                -or $identity.sha256 -cne $oldTestHash) { throw 'The actual old compiled test source lacks its independently pinned Git blob.' }
        }
        Add-SessionUnitProtectedIdentity $protected $path $identity 16MB
    }
    $descriptor = Read-SessionJson (Join-Path $oldHostProject 'HostProject.uproject') 64KB
    if (-not (Test-SessionInteger $descriptor.value.FileVersion 3) -or ($descriptor.value.Contains('Modules') -and @($descriptor.value.Modules).Count -ne 0) `
        -or $descriptor.value.Plugins -isnot [array] -or $descriptor.value.Plugins.Count -ne 1 `
        -or $descriptor.value.Plugins[0].Name -cne 'YacsBobInspection' -or $descriptor.value.Plugins[0].Enabled -isnot [bool] `
        -or -not $descriptor.value.Plugins[0].Enabled) { throw 'The current generated HostProject descriptor is not the fixed content-free Bob host.' }
    foreach ($field in $descriptor.value.Keys) {
        if ($field -cnotin @('FileVersion', 'Plugins', 'Modules', 'EngineAssociation', 'Category', 'Description')) { throw 'The generated unit descriptor contains an unsupported field.' }
    }
    Assert-SessionJsonFields $descriptor.value.Plugins[0] @('Name', 'Enabled')
    Add-SessionUnitProtectedIdentity $protected $descriptor.identity.path $descriptor.identity 64KB
    $diagnostic = [ordered]@{ schema_version = 1; exact_sha = $ExpectedHead; status = 'VERIFIED_GREEN_RECEIPTS_READ_BACK'
        scope = 'CURRENT_SOURCE_ONLY_READBACK_OF_AUTHENTICATED_ORIGINAL_SUCCESS; NOT_A_NEW_MCP_SESSION'
        source_only = $true; compile_performed = $false; editor_launched = $false; listener_started = $false
        official_mcp_transport_verified = $false; native_automation_verified = $false; native_bob_capture_verified = $false
        official_mcp_admitted = $false; persistent_world_mutation = $false; performance_pass = $false
        original_run = '38027596123-1'; original_exact_sha = $oldSha; original_host = $verifiedHostDocument.identity
        original_source_fingerprints = $h.source_fingerprints; current_unit_source_fingerprints = $receipt.source_fingerprints
        integrated_main_provenance = $integratedMain
        attributes_checkout_delta = $attributesDelta
        current_unit_test_delta = [ordered]@{ scope = 'CURRENT_UNIT_TEST_ONLY_DELTA; NOT_ORIGINAL_BINARY_PROOF'; path = $testPath
            original_sha256 = $oldTestHash; original_git_blob = $oldTestBlob[0]; current_sha256 = $newTestHash; current_exact_sha = $ExpectedHead
            unchanged_native_runtime_input_count = 11; original_to_current_changed_paths = $changed }
        original_verified_flags = [ordered]@{ official_mcp_transport_verified = $h.official_mcp_transport_verified
            native_automation_verified = $h.native_automation_verified; native_bob_capture_verified = $h.native_bob_capture_verified }
        original_owned_editor_pid = $h.owned_editor_pid; original_owned_client_pid = $h.owned_client_pid
        original_owned_editor_exit_code = $h.owned_editor_exit_code; original_owned_client_exit_code = $h.owned_client_exit_code
        original_loopback_binding = $h.loopback_binding; original_official_automation_result = $n.official_automation_result
        original_denials = $t.denials; original_tool = $t.tool; original_negotiated_protocol = $t.negotiated_protocol
        original_context_landscape = $c.landscape; original_actor_count = $actors.Count; original_actor_property_read = 'HASH_BOUND_CAPTURE_FINITE_TRANSFORM_ARRAY'
        original_landscape_transform = @($capture.scene.actors | Where-Object { $_[0] -ceq $c.landscape.path })[0][1]
        original_inspector_findings = [ordered]@{ status = $result.status; role = $result.role; inspection_complete = $result.inspection_complete
            evaluated_sample_count = $result.evaluated_sample_count; trace_miss_count = $result.trace_miss_count; class_counts = $result.class_counts
            max_cut_required_m = $result.max_cut_required_m; max_fill_required_m = $result.max_fill_required_m
            rms_required_adjustment_m = $result.rms_required_adjustment_m; earthworks_authoring_permitted = $result.earthworks_authoring_permitted
            geometry_repair_executed = $result.geometry_repair_executed; road_admitted = $result.road_admitted; eligible_for_learning = $result.eligible_for_learning }
        original_capture = $read['capture-proof.json'].identity; original_result = $read['result.json'].identity
        original_domain_status = $result.status; original_inspector_role = $result.role; original_sample_count = $result.sample_count
        generated_host_descriptor = [ordered]@{ scope = 'CURRENT_OBSERVED_GENERATED_DESCRIPTOR; NO_ORIGINAL_HOST_HASH'; identity = $descriptor.identity }
        current_sdk_libraries = $sdkLibraries; protected_input_count = $protected.Count
        original_profile = $capture.profile; original_consumer = $capture.consumer; original_consumer_asset_count = $c.consumer_assets.Count
        original_evidence = [ordered]@{}; retained_raw_evidence = [ordered]@{}
        proof_limits = @('Original wire messages and denial texts were not retained in these receipts.',
            'One wire tools/list is retained; later native census is a separate in-process check.',
            'No independently retained shutdown ACK or historical listener-absent Boolean is invented.',
            'Current installed SDK DLL hashes and generated HostProject descriptor are not original historical byte anchors.') }
    foreach ($name in $read.Keys) {
        $diagnostic.original_evidence[$name] = $read[$name].identity
        $diagnostic.retained_raw_evidence[$name] = $read[$name].retained_raw
    }
    $diagnostic.retained_raw_evidence['accepted-session-build.json'] = $verifiedHostDocument.retained_raw
    $diagnostic.retained_raw_evidence['runtime-dependencies.json'] = $runtime.retained_raw
    foreach ($row in $diagnostic.retained_raw_evidence.Values) { Add-SessionUnitProtectedIdentity $protected $row.path $row $row.size_bytes }
    $diagnostic.protected_input_count = $protected.Count
    $target = Join-Path $ArtifactRoot 'verified-session-readback.json'
    Write-SessionJson $target $diagnostic
    $receipt.proof_files.verified_session_readback = Get-SessionFileIdentity $target 1MB
    Add-SessionUnitProtectedIdentity $protected $target $receipt.proof_files.verified_session_readback 1MB
    $receipt['source_only'] = $true
    $receipt['compile_performed'] = $false
    $receipt['verified_original_run'] = '38027596123-1'
    $console = [ordered]@{ original_host = $diagnostic.original_host; original_exact_sha = $oldSha; scope = $diagnostic.scope
        original_owned_editor_pid = $h.owned_editor_pid; original_owned_client_pid = $h.owned_client_pid
        original_owned_editor_exit_code = $h.owned_editor_exit_code; original_owned_client_exit_code = $h.owned_client_exit_code
        original_tool = $t.tool; original_negotiated_protocol = $t.negotiated_protocol; original_denials = $t.denials
        original_context_landscape = $c.landscape; original_actor_count = $actors.Count; original_landscape_transform = $diagnostic.original_landscape_transform
        original_official_automation_result = $n.official_automation_result; original_inspector_findings = $diagnostic.original_inspector_findings
        proof_limits = $diagnostic.proof_limits; readback = $receipt.proof_files.verified_session_readback }
    $consoleJson = $console | ConvertTo-Json -Depth 8 -Compress
    if ($consoleJson.Length -gt 16KB) { throw 'The fixed GREEN console summary exceeds its 16KiB bound.' }
    Write-Host ('VERIFIED_GREEN_READBACK ' + $consoleJson)
    return [ordered]@{ protected = $protected; descriptor = $descriptor; native_paths = $nativePaths; bob_rows = $bobRows
        old_plugin = $oldPlugin; old_source_sha = $oldSha; old_host_identity = $verifiedHostDocument.identity
        engine_build_id = $h.installed_engine_build_id; unit_test_delta = $diagnostic.current_unit_test_delta }
}
function Read-SessionFixedFailedUnitBytes {
    param([ValidateSet('accepted-session-build.json', 'input-boundary-unit.json', 'input-boundary-editor.log',
        'input-boundary-editor-stdout.log', 'input-boundary-editor-stderr.log')][string] $Name, $Expected, $Budget, [switch] $ObservedLog)
    $root = 'D:\yacs\runner\_work\YetAnotherCyclingSim\YetAnotherCyclingSim\_official-mcp-native-probe\Saved\RuntimeProof\OfficialMcpBobSession\38035299343-1'
    $path = Join-Path $root $Name
    $isLog = $Name.EndsWith('.log', [StringComparison]::Ordinal)
    if ($ObservedLog -and -not $isLog) { throw 'Only the three fixed owned logs allow qualified current-byte observation.' }
    if ($Expected -isnot [Collections.IDictionary] -or $Expected.path -isnot [string] `
        -or -not [string]::Equals([IO.Path]::GetFullPath($Expected.path), [IO.Path]::GetFullPath($path), [StringComparison]::OrdinalIgnoreCase) `
        -or $Expected.sha256 -cnotmatch '^[0-9a-f]{64}$' -or ($Expected.size_bytes -isnot [int] -and $Expected.size_bytes -isnot [long]) `
        -or $Expected.size_bytes -lt 0 -or (-not $isLog -and $Expected.size_bytes -eq 0)) { throw 'The fixed failed-unit identity lacks its authenticated path, size or hash.' }
    $limit = if ($isLog) { 32MB } else { 1MB }
    if ($Expected.size_bytes -gt $limit) { throw 'The original failed-unit identity exceeds its fixed member bound.' }
    $remaining = 64MB - $Budget.bytes
    if ($remaining -le 0) { throw 'The fixed failed-unit raw inventory exhausts its 64MiB budget.' }
    Assert-SessionPlainPath $path
    $before = Get-Item -LiteralPath $path -Force
    if ($before.PSIsContainer -or $before.Length -gt [Math]::Min($limit, $remaining) -or (-not $isLog -and $before.Length -eq 0)) { throw 'A fixed failed-unit file exceeds its regular-file or byte bound.' }
    $size = $before.Length
    $ticks = $before.LastWriteTimeUtc.Ticks
    $stream = [IO.FileStream]::new($path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try {
        $buffer = [byte[]]::new([int]$size + 1)
        $count = 0
        while (($part = $stream.Read($buffer, $count, $buffer.Length - $count)) -gt 0) { $count += $part }
    } finally { $stream.Dispose() }
    Assert-SessionPlainPath $path
    $after = Get-Item -LiteralPath $path -Force
    if ($count -ne $size -or $after.Length -ne $size -or $after.LastWriteTimeUtc.Ticks -ne $ticks) { throw 'Fixed failed-unit bytes changed during bounded retention.' }
    $bytes = [byte[]]::new($count)
    [Array]::Copy($buffer, $bytes, $count)
    $identity = [ordered]@{ path = [IO.Path]::GetFullPath($path); size_bytes = $count
        sha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant() }
    $matchesOriginal = $identity.sha256 -ceq $Expected.sha256 -and $identity.size_bytes -eq $Expected.size_bytes
    if (-not $ObservedLog -and -not $matchesOriginal) { throw 'Strict failed-unit raw bytes differ before JSON parsing.' }
    $Budget.bytes += $count
    $scope = if ($matchesOriginal) { 'ORIGINAL_FAILED_UNIT_HASH_ANCHORED_BYTES' } else { 'CURRENT_OBSERVED_RETAINED_FAILED_UNIT_PATH_BYTES; NOT_ORIGINAL_HASH_MATCH' }
    $target = Join-Path $ArtifactRoot ('unit-failure-' + $Name)
    Assert-SessionPlainPath $target
    $output = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $output.Write($bytes, 0, $bytes.Length) } finally { $output.Dispose() }
    $retained = if ($count -gt 0) { Get-SessionFileIdentity $target $count } else {
        $empty = Get-Item -LiteralPath $target -Force
        if ($empty.PSIsContainer -or $empty.Length -ne 0) { throw 'The exclusive empty-log copy differs.' }
        [ordered]@{ path = [IO.Path]::GetFullPath($target); size_bytes = 0; sha256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' }
    }
    if ($retained.sha256 -cne $identity.sha256) { throw 'The exclusive failed-unit raw copy differs.' }
    return [ordered]@{ identity = $identity; expected_original_identity = $Expected; retained_raw = $retained
        matches_original_identity = $matchesOriginal; identity_scope = $scope; bytes = $bytes }
}
function Invoke-SessionFixedFailedUnitReadback {
    $receipt['source_only'] = $true
    $receipt['compile_performed'] = $false
    $receipt['native_input_boundary_verified'] = $false
    $sourceSha = '0ee5eaf39e0d673fee061f7e33372710278d50be'
    $oldRoot = 'D:\yacs\runner\_work\YetAnotherCyclingSim\YetAnotherCyclingSim\_official-mcp-native-probe\Saved\RuntimeProof\OfficialMcpBobSession\38035299343-1'
    $budget = [ordered]@{ bytes = 0L }
    $hostFile = Read-SessionFixedFailedUnitBytes 'accepted-session-build.json' @{
        path = (Join-Path $oldRoot 'accepted-session-build.json'); size_bytes = 423398
        sha256 = 'f59ecce8855fffc8c4965925cf4f162b3c475b57f491529e8da2ca1765b91a0c' } $budget
    $failedHost = [Text.Encoding]::UTF8.GetString($hostFile.bytes) | ConvertFrom-Json -AsHashtable -Depth 40
    if ($failedHost -isnot [Collections.IDictionary] -or -not (Test-SessionInteger $failedHost.schema_version 1) `
        -or $failedHost.exact_sha -cne $sourceSha -or $failedHost.run -cne '38035299343' -or $failedHost.attempt -cne '1' `
        -or $failedHost.status -cne 'BLOCKED' -or -not (Test-SessionInteger $failedHost.owned_editor_pid 6252)) { throw 'The strict failed host differs from its fixed source/run/status/PID.' }
    $expectedUnit = $failedHost.proof_files.input_boundary_unit
    if ($expectedUnit.sha256 -cne '28c1401dab3962a035e9b8bc75ecd738616e85f0c31cb1a4360852405dbc1757' `
        -or -not (Test-SessionInteger $expectedUnit.size_bytes 16347)) { throw 'The failed host lacks the independently pinned unit identity.' }
    $unitFile = Read-SessionFixedFailedUnitBytes 'input-boundary-unit.json' $expectedUnit $budget
    $failedUnit = [Text.Encoding]::UTF8.GetString($unitFile.bytes) | ConvertFrom-Json -AsHashtable -Depth 40
    if ($failedUnit -isnot [Collections.IDictionary] -or -not (Test-SessionInteger $failedUnit.schema_version 1) `
        -or $failedUnit.exact_sha -cne $sourceSha -or $failedUnit.status -cne 'INPUT_BOUNDARY_BLOCKED' `
        -or $failedUnit.unit_root -cne 'D:\yacs\runner\_work\b384\38035299343-1-input-boundary' `
        -or $failedUnit.map -cne '/Engine/Maps/Entry' -or $failedUnit.test -cne 'YacsBobInspection.InputBoundary' `
        -or -not (Test-SessionInteger $failedUnit.owned_editor_pid 6252) -or -not (Test-SessionInteger $failedUnit.owned_editor_exit_code -1) `
        -or $failedUnit.owned_editor_exit_observed -isnot [bool] -or -not $failedUnit.owned_editor_exit_observed `
        -or $failedUnit.native_input_boundary_verified -isnot [bool] -or $failedUnit.native_input_boundary_verified) { throw 'The strict failed unit differs from its actual blocked invocation.' }
    $diagnostic = [ordered]@{ schema_version = 1; exact_sha = $ExpectedHead; status = 'FAILED_UNIT_STARTUP_READBACK_RETAINED'
        source_only = $true; compile_performed = $false; editor_launched = $false; native_input_boundary_verified = $false
        official_mcp_transport_verified = $false; native_automation_verified = $false; native_bob_capture_verified = $false
        official_mcp_admitted = $false; persistent_world_mutation = $false; performance_pass = $false
        original_run = '38035299343-1'; original_exact_sha = $sourceSha; original_host = $hostFile.identity; original_unit = $unitFile.identity
        retained_original_host = $hostFile.retained_raw; retained_original_unit = $unitFile.retained_raw
        original_owned_editor_pid = $failedUnit.owned_editor_pid; original_owned_editor_exit_code = $failedUnit.owned_editor_exit_code
        original_owned_endpoints = $failedUnit.observed_owned_endpoints; original_unit_error = Get-SessionSafeFailureText $failedUnit.error
        original_unit_verified = $false; original_report_parsed = $null -ne $failedUnit.report
        original_mcp_absence_info = $failedUnit.mcp_absence_info; original_conservation_verified = $failedUnit.protected_inputs_unchanged
        raw_evidence_limit_bytes = 64MB; logs = [ordered]@{}; proof_limits = @('Port19315 remains unadmitted; actual plugin descriptor and opt-out are unverified.',
            'Changed retained log bytes are current path observations, not original process-ownership evidence.',
            'No report or native Info proof is manufactured from startup logs.') }
    $patterns = [ordered]@{ port19315 = '19315'; loco = '(?i)Loco'; http = '(?i)HTTP|HttpServer|listen|bind|socket|TCP'; mcp = '(?i)ModelContextProtocol|MCP|YacsBob';
        messaging = '(?i)messag'; rider = '(?i)Rider'; remote = '(?i)remote'; python = '(?i)Python';
        automation = '(?i)Automation'; startup_error = '(?i)LogInit:|Error|Fatal|Exception|Traceback' }
    foreach ($name in @('input-boundary-editor.log', 'input-boundary-editor-stdout.log', 'input-boundary-editor-stderr.log')) {
        $file = Read-SessionFixedFailedUnitBytes $name $failedUnit.logs[$name] $budget -ObservedLog
        $lines = [Text.Encoding]::UTF8.GetString($file.bytes) -split '\r?\n'
        $categories = [ordered]@{}
        foreach ($category in $patterns.Keys) { $categories[$category] = [Collections.Generic.List[int]]::new() }
        for ($index = 0; $index -lt $lines.Length; $index++) {
            if ($lines[$index] -match '(?i)\bCommand\s*Line\s*[:=]') { continue }
            foreach ($category in $patterns.Keys) { if ($lines[$index] -match $patterns[$category]) { $categories[$category].Add($index) } }
        }
        $selected = [Collections.Generic.HashSet[int]]::new()
        $context = @()
        $counts = [ordered]@{}
        $contextTruncated = $false
        foreach ($category in $patterns.Keys) {
            $categoryMatches = $categories[$category]
            $counts[$category] = $categoryMatches.Count
            $candidates = if ($category -ceq 'port19315') { @($categoryMatches | Select-Object -First 2) + @($categoryMatches | Select-Object -Last 2) }
                elseif ($category -ceq 'loco') { @($categoryMatches | Select-Object -First 4) + @($categoryMatches | Select-Object -Last 2) }
                else { @($categoryMatches | Select-Object -First 1) + @($categoryMatches | Select-Object -Last 1) }
            foreach ($index in $candidates) {
                if ($selected.Contains($index)) { continue }
                if ($context.Count -ge 32) { $contextTruncated = $true; continue }
                $safe = if ($lines[$index] -match '(?i)authorization|bearer|token|secret|password|credential|api.?key|signature') { '[SENSITIVE_LOG_ROW_REDACTED]' }
                    else { Get-SessionSafeFailureText $lines[$index] }
                if ([Text.Encoding]::UTF8.GetByteCount($safe) -gt 1024) { $contextTruncated = $true; continue }
                $row = [ordered]@{ line = $index + 1; category = $category; text = $safe; identity_scope = $file.identity_scope }
                $candidate = $context + @($row)
                if ([Text.Encoding]::UTF8.GetByteCount((ConvertTo-Json -InputObject $candidate -Depth 5 -Compress)) -gt 8KB) { $contextTruncated = $true; continue }
                [void]$selected.Add($index)
                $context = $candidate
            }
        }
        $diagnostic.logs[$name] = [ordered]@{ expected_original_identity = $file.expected_original_identity; identity = $file.identity
            retained_raw = $file.retained_raw; identity_scope = $file.identity_scope; matches_original_identity = $file.matches_original_identity
            category_match_counts = $counts; context = $context; context_line_limit = 32; context_json_limit_bytes = 8KB
            context_json_bytes = [Text.Encoding]::UTF8.GetByteCount((ConvertTo-Json -InputObject $context -Depth 5 -Compress))
            context_selection_truncated = $contextTruncated; line_utf8_limit_bytes = 1024; contexts_are_partial = $true }
    }
    $diagnostic['raw_evidence_bytes'] = $budget.bytes
    $target = Join-Path $ArtifactRoot 'failed-unit-startup-readback.json'
    Write-SessionJson $target $diagnostic
    $receipt.proof_files.failed_unit_startup_readback = Get-SessionFileIdentity $target 1MB
    $console = [ordered]@{ diagnostic = $diagnostic; identity = $receipt.proof_files.failed_unit_startup_readback }
    $consoleJson = $console | ConvertTo-Json -Depth 12 -Compress
    if ([Text.Encoding]::UTF8.GetByteCount($consoleJson) -gt 48KB) { throw 'The fixed failed-unit console evidence exceeds its48KiB bound.' }
    Write-Host ('FAILED_UNIT_STARTUP_READBACK ' + $consoleJson)
}
function Get-SessionUnitOwnedListeners {
    param([int] $OwnedPid)
    if (-not (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) { throw 'The unit owned-PID listener check is unavailable.' }
    return @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object OwningProcess -eq $OwnedPid)
}
function Add-SessionFreshUnitIdentity {
    param($Rows, [string] $Path, $Expected, [long] $Limit = 16MB)
    if ($Rows.Contains($Path)) { return }
    if ($Rows.Count -ge 64) { throw 'The fresh unit conservation inventory exceeds 64 files.' }
    $total = 0L
    foreach ($row in $Rows.Values) { $total += $row.size_bytes }
    $remaining = 256MB - $total
    if ($remaining -le 0) { throw 'The fresh unit conservation inventory exhausts 256MiB.' }
    $actual = Get-SessionFileIdentity $Path ([Math]::Min($Limit, $remaining))
    if ($null -ne $Expected -and ($Expected.sha256 -cne $actual.sha256 `
        -or -not (Test-SessionInteger $Expected.size_bytes $actual.size_bytes))) { throw 'A fresh unit input differs from its fixed source identity.' }
    $Rows[$Path] = $actual
}
function Build-SessionFreshInputBoundaryPlugin {
    param($Green, $Unit, $Protected)
    $inputPlugin = Join-Path $ArtifactRoot 'UnitInputPlugin/YacsBobInspection'
    $package = Join-Path 'D:\yacs\runner\_work\b384' ($runIdentity + '-input-boundary-plugin')
    $prefix = 'Plugins/YacsBobInspection/'
    foreach ($path in @($inputPlugin, $package)) {
        Assert-SessionPlainPath $path
        if (Test-Path -LiteralPath $path) { throw 'The fresh unit build refuses an existing producer root.' }
    }
    $actionExample = Join-Path $package 'HostProject/Plugins/YacsBobInspection/Intermediate/Build/Win64/x64/UnrealEditor/Development/YacsBobInspection/Module.YacsBobInspection.cpp.obj.rsp'
    if ($actionExample.Length -ge 240) { throw 'The fresh unit package exceeds the established UBT action path bound.' }
    $inputRows = [ordered]@{}
    foreach ($relative in $Green.native_paths) {
        $source = Join-Path $RepoRoot $relative
        $identity = Get-SessionFileIdentity $source 16MB
        if ($identity.sha256 -cne $receipt.tracked_source_sha256[$relative]) { throw 'A current tracked unit build input differs.' }
        $target = Join-Path $inputPlugin $relative.Substring($prefix.Length)
        Assert-SessionPlainPath $target
        New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
        $readStream = [IO.File]::OpenRead($source)
        $writeStream = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try {
            $buffer = [byte[]]::new(8192)
            $total = 0L
            while (($count = $readStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $total += $count
                if ($total -gt $identity.size_bytes) { throw 'A tracked unit build input grew during exclusive copy.' }
                $writeStream.Write($buffer, 0, $count)
            }
        } finally { $writeStream.Dispose(); $readStream.Dispose() }
        Add-SessionFreshUnitIdentity $Protected $target $identity 16MB
        $inputRows[$relative.Substring($prefix.Length)] = $Protected[$target]
    }
    $Unit['prebuild_input_inventory'] = Assert-SessionFreshUnitInputs $inputPlugin $inputRows 12
    Assert-YacsDiskReserve -Path $package | ForEach-Object { Write-Host $_ }
    Assert-SessionUnitProtectedIdentities $Green.protected
    Assert-SessionTrackedSources $RepoRoot
    $Unit['compile_attempted'] = $true
    $Unit['plugin_build'] = Invoke-SessionBuildProcess $engine.UATPath @('BuildPlugin',
        ('-Plugin="' + (Join-Path $inputPlugin 'YacsBobInspection.uplugin') + '"'), ('-Package="' + $package + '"'),
        '-TargetPlatforms=Win64', '-StrictIncludes', '-NoDeleteHostProject') (Join-Path $engine.Root 'Engine/Build/BatchFiles') 'input-boundary-plugin-build'
    $Unit['owned_build_exit_observed'] = $true
    $Unit['owned_build_exit_code'] = $Unit.plugin_build.exit_code
    $Unit.compile_performed = $true
    $receipt['compile_performed'] = $true
    $Unit['compile_scope'] = 'FRESH_TRACKED_BOB_BUILDPLUGIN_ONLY; NO_PROJECT_REBUILD; NOT_ORIGINAL_241_BINARY'
    $Unit['current_source_fingerprints'] = $receipt.source_fingerprints
    $Unit['current_unit_test_delta'] = $Green.unit_test_delta
    $Unit['plugin_package_root'] = $package
    $Unit['planned_plugin_action_path_length'] = $actionExample.Length
    $pluginRoot = Join-Path $package 'HostProject/Plugins/YacsBobInspection'
    $copies = @()
    foreach ($relative in $Green.native_paths) {
        foreach ($root in @($inputPlugin, $pluginRoot)) {
            $path = Join-Path $root $relative.Substring($prefix.Length)
            $expected = @{ sha256 = $receipt.tracked_source_sha256[$relative]; size_bytes = $Protected[(Join-Path $inputPlugin $relative.Substring($prefix.Length))].size_bytes }
            Add-SessionFreshUnitIdentity $Protected $path $expected 16MB
            $actual = Get-SessionFileIdentity $path $expected.size_bytes
            if ($actual.sha256 -cne $expected.sha256 -or $actual.size_bytes -ne $expected.size_bytes) { throw 'Actual newly compiled unit source differs from tracked input.' }
        }
        $copies += [ordered]@{ relative = $relative; identity = $Protected[(Join-Path $pluginRoot $relative.Substring($prefix.Length))] }
    }
    $descriptor = Read-SessionJson (Join-Path $package 'HostProject/HostProject.uproject') 64KB
    if (-not (Test-SessionInteger $descriptor.value.FileVersion 3) -or ($descriptor.value.Contains('Modules') -and @($descriptor.value.Modules).Count -ne 0) `
        -or $descriptor.value.Plugins -isnot [array] -or $descriptor.value.Plugins.Count -ne 1 `
        -or $descriptor.value.Plugins[0].Name -cne 'YacsBobInspection' -or $descriptor.value.Plugins[0].Enabled -isnot [bool] `
        -or -not $descriptor.value.Plugins[0].Enabled) { throw 'The newly generated unit descriptor is not the fixed content-free host.' }
    foreach ($field in $descriptor.value.Keys) {
        if ($field -cnotin @('FileVersion', 'Plugins', 'Modules', 'EngineAssociation', 'Category', 'Description')) { throw 'The new unit descriptor contains an unsupported field.' }
    }
    Assert-SessionJsonFields $descriptor.value.Plugins[0] @('Name', 'Enabled')
    Add-SessionFreshUnitIdentity $Protected $descriptor.identity.path $descriptor.identity 64KB
    $copies += [ordered]@{ relative = 'HostProject.uproject'; identity = $descriptor.identity }
    $manifest = Read-SessionJson (Join-Path $pluginRoot 'Binaries/Win64/UnrealEditor.modules') 64KB
    if ($manifest.value.BuildId -cne $Green.engine_build_id -or $manifest.value.Modules -isnot [Collections.IDictionary] `
        -or $manifest.value.Modules.Count -ne 1 -or $manifest.value.Modules.YacsBobInspection -cne 'UnrealEditor-YacsBobInspection.dll') { throw 'The freshly built unit module manifest differs from its installed engine and fixed module.' }
    Add-SessionFreshUnitIdentity $Protected $manifest.identity.path $manifest.identity 64KB
    $newDll = Join-Path $pluginRoot 'Binaries/Win64/UnrealEditor-YacsBobInspection.dll'
    Add-SessionFreshUnitIdentity $Protected $newDll $null 64MB
    $moduleRows = @([ordered]@{ relative = 'Binaries/Win64/UnrealEditor.modules'; identity = $manifest.identity
        build_id = $manifest.value.BuildId; modules = $manifest.value.Modules },
        [ordered]@{ relative = 'Binaries/Win64/UnrealEditor-YacsBobInspection.dll'; identity = $Protected[$newDll] })
    foreach ($row in $moduleRows) {
        Add-SessionFreshUnitIdentity $Protected $row.identity.path $row.identity 64MB
        $copies += [ordered]@{ relative = ('Plugins/YacsBobInspection/' + $row.relative); identity = $row.identity }
    }
    if ($copies.Count -ne 15) { throw 'The fresh compiled unit input closure differs from fifteen files.' }
    $Unit['binary_provenance'] = $moduleRows
    $Unit['tracked_native_source_sha256'] = [ordered]@{}
    foreach ($relative in $Green.native_paths) { $Unit.tracked_native_source_sha256[$relative] = $receipt.tracked_source_sha256[$relative] }
    Assert-SessionUnitProtectedIdentities $Protected
    Assert-SessionUnitProtectedIdentities $Green.protected
    Assert-SessionTrackedSources $RepoRoot
    return $copies
}
function Assert-SessionFreshUnitInputs {
    param([string] $Root, $ExpectedFiles, [ValidateSet(12, 15)][int] $ExpectedCount = 15)
    # BuildPlugin receives twelve tracked inputs; the unit launches only its
    # fresh fifteen-file copy. Historical Saved descriptors are evidence.
    if ($ExpectedFiles.Count -ne $ExpectedCount) { throw 'The fixed unit copy inventory differs from its fixed producer or launch closure.' }
    Assert-SessionPlainPath $Root
    $rootPath = [IO.Path]::GetFullPath($Root)
    $rootPrefix = $rootPath.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $allowedFiles = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    $allowedDirectories = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    [void]$allowedDirectories.Add('')
    foreach ($relative in $ExpectedFiles.Keys) {
        if ($relative -isnot [string] -or $relative -cnotmatch '^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$' `
            -or $relative.Split('/') -ccontains '..' -or -not $allowedFiles.Add($relative)) { throw 'A fixed copied unit path is malformed or duplicated.' }
        $expectedPath = [IO.Path]::GetFullPath((Join-Path $rootPath $relative))
        if (-not $expectedPath.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase) `
            -or $ExpectedFiles[$relative].path -cne $expectedPath) { throw 'A fixed copied unit identity escapes its fresh root.' }
        $parent = $relative
        while ($parent.Contains('/')) {
            $parent = $parent.Substring(0, $parent.LastIndexOf('/'))
            [void]$allowedDirectories.Add($parent)
        }
    }
    $pending = [Collections.Generic.Stack[object]]::new()
    $pending.Push([ordered]@{ path = $rootPath; depth = 0 })
    $directories = [ordered]@{}
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    $entries = 0
    $inventoryTimer = [Diagnostics.Stopwatch]::StartNew()
    while ($pending.Count -gt 0) {
        if ($inventoryTimer.Elapsed.TotalSeconds -ge 30) { throw 'The fixed unit input inventory exceeded its 30 second bound.' }
        $directory = $pending.Pop()
        Assert-SessionPlainPath $directory.path
        $before = Get-Item -LiteralPath $directory.path -Force
        if (-not $before.PSIsContainer) { throw 'A fixed unit parent is not a regular directory.' }
        $directories[$directory.path] = $before.LastWriteTimeUtc.Ticks
        $children = [IO.Directory]::EnumerateFileSystemEntries($directory.path).GetEnumerator()
        try {
            while ($children.MoveNext()) {
                $path = [string]$children.Current
                $entries++
                if ($entries -gt 128 -or $inventoryTimer.Elapsed.TotalSeconds -ge 30) { throw 'The fixed unit input traversal exceeds its entry or time bound.' }
                Assert-SessionPlainPath $path
                $fullPath = [IO.Path]::GetFullPath($path)
                if (-not $fullPath.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'The fixed unit traversal escaped its root.' }
                $relative = [IO.Path]::GetRelativePath($rootPath, $fullPath).Replace('\', '/')
                $item = Get-Item -LiteralPath $fullPath -Force
                if ($item.PSIsContainer) {
                    if (-not $allowedDirectories.Contains($relative) -or $directory.depth -ge 16) { throw 'The fresh unit contains an unexpected or excessively deep directory.' }
                    $pending.Push([ordered]@{ path = $fullPath; depth = $directory.depth + 1 })
                } else {
                    if (-not $allowedFiles.Contains($relative) -or -not $seen.Add($relative)) { throw 'The fresh unit contains an unknown or duplicate file.' }
                    $expected = $ExpectedFiles[$relative]
                    $actual = Get-SessionFileIdentity $fullPath $expected.size_bytes
                    if ($actual.size_bytes -ne $expected.size_bytes -or $actual.sha256 -cne $expected.sha256) { throw 'A fresh unit input differs from its authenticated copy.' }
                }
            }
        } finally { $children.Dispose() }
    }
    foreach ($path in $directories.Keys) {
        Assert-SessionPlainPath $path
        $after = Get-Item -LiteralPath $path -Force
        if (-not $after.PSIsContainer -or $after.LastWriteTimeUtc.Ticks -ne $directories[$path]) { throw 'A fresh unit directory changed during input inventory.' }
    }
    if ($inventoryTimer.Elapsed.TotalSeconds -ge 30 -or $seen.Count -ne $ExpectedCount -or $directories.Count -ne $allowedDirectories.Count) { throw 'The fresh unit input inventory is incomplete or exceeded its deadline.' }
    return [ordered]@{ file_count = $seen.Count; directory_count = $directories.Count; entry_count = $entries
        maximum_entries = 128; maximum_depth = 16; deadline_seconds = 30; elapsed_seconds = $inventoryTimer.Elapsed.TotalSeconds
        scope = 'EXACT_FRESH_UNIT_COPIED_INPUTS'; copied_hashes_unchanged = $true }
}
function Invoke-SessionInputBoundaryUnit {
    param($Green)
    $unitRoot = Join-Path 'D:\yacs\runner\_work\b384' ($runIdentity + '-input-boundary')
    $reportRoot = Join-Path $ArtifactRoot 'input-boundary-report'
    $unit = [ordered]@{ schema_version = 1; exact_sha = $ExpectedHead; status = 'INPUT_BOUNDARY_PENDING'; source_only = $false
        editor_launched = $false; compile_performed = $false; native_input_boundary_verified = $false
        official_mcp_transport_verified = $false; native_automation_verified = $false; native_bob_capture_verified = $false
        official_mcp_admitted = $false; persistent_world_mutation = $false; performance_pass = $false
        original_run = '38027596123-1'; original_compiled_sha = $Green.old_source_sha; original_host = $Green.old_host_identity
        unit_root = $unitRoot; map = '/Engine/Maps/Entry'; test = 'YacsBobInspection.InputBoundary'
        deadline_seconds = 180; owned_editor_pid = $null; owned_editor_exit_code = $null; owned_editor_exit_observed = $false
        listener_samples = 0; listener_samples_while_alive = 0; maximum_owned_listeners = 0; owned_listeners_after_exit = $null
        observed_owned_endpoints = @(); trace_control_attributed = $false; mcp_absence_info = [ordered]@{}
        protected_inputs_unchanged = $false; copied_inputs = [ordered]@{}; prelaunch_input_inventory = $null
        logs = [ordered]@{}; build_failure_logs = [ordered]@{}; preparation_elapsed_seconds = $null
        compile_attempted = $false; owned_build_pid = $null; owned_build_exit_observed = $false; owned_build_exit_code = $null
        report = $null; report_summary = $null; error = $null }
    $timer = $null
    $preparationTimer = [Diagnostics.Stopwatch]::StartNew()
    try {
        Assert-SessionPlainPath $unitRoot
        if (Test-Path -LiteralPath $unitRoot) { throw 'The fixed unit root already exists; preserve it.' }
        Assert-SessionIdleHost
        Assert-SessionUnitProtectedIdentities $Green.protected
        $freshProtected = [ordered]@{}
        $copyRows = @(Build-SessionFreshInputBoundaryPlugin $Green $unit $freshProtected)
        New-Item -ItemType Directory -Path $unitRoot | Out-Null
        foreach ($row in $copyRows) {
            $target = Join-Path $unitRoot $row.relative
            Assert-SessionPlainPath $target
            if (Test-Path -LiteralPath $target) { throw 'The fixed unit refuses to replace a copied input.' }
            New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
            $sourceStream = [IO.File]::OpenRead($row.identity.path)
            $output = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
            try {
                $buffer = [byte[]]::new(8192)
                $copiedBytes = 0L
                while (($count = $sourceStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $copiedBytes += $count
                    if ($copiedBytes -gt $row.identity.size_bytes) { throw 'A unit input grew beyond its authenticated copy bound.' }
                    $output.Write($buffer, 0, $count)
                }
            } finally { $output.Dispose(); $sourceStream.Dispose() }
            $copied = Get-SessionFileIdentity $target $row.identity.size_bytes
            if ($copied.sha256 -cne $row.identity.sha256 -or $copied.size_bytes -ne $row.identity.size_bytes) { throw 'A fixed unit input copy differs.' }
            $unit.copied_inputs[$row.relative] = $copied
            Add-SessionFreshUnitIdentity $freshProtected $target $copied $copied.size_bytes
        }
        $entry = Join-Path $engine.Root 'Engine/Content/Maps/Entry.umap'
        Add-SessionUnitProtectedIdentity $Green.protected $entry $null 32MB
        $executable = Join-Path $engine.Root 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
        Add-SessionUnitProtectedIdentity $Green.protected $executable $null 1GB
        $unit['owned_editor_executable'] = $Green.protected[$executable]
        $unit['entry_map_identity'] = $Green.protected[$entry]
        $controlPath = Join-Path $engine.Root 'Engine/Source/Runtime/TraceLog/Private/Trace/Control.cpp'
        Add-SessionFreshUnitIdentity $freshProtected $controlPath @{
            size_bytes = 9043; sha256 = '238e6ac9fb9320f3a1050abd91438ff663c43ae7ccfd98edbea264ba98de77fd' } 4MB
        $unit['trace_control_source'] = [ordered]@{ scope = 'CURRENT_INSTALLED_SOURCE; KNOWN_TRACE_CONTROL_PORT_1985'; identity = $freshProtected[$controlPath] }
        $unit['startup_config_overrides'] = @('-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
            '-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]:bAutoStartServer=False')
        New-Item -ItemType Directory -Path $reportRoot | Out-Null
        $preparationTimer.Stop()
        $unit.preparation_elapsed_seconds = $preparationTimer.Elapsed.TotalSeconds
        $timer = [Diagnostics.Stopwatch]::StartNew()
        Assert-SessionIdleHost
        Assert-SessionUnitProtectedIdentities $Green.protected
        Assert-SessionUnitProtectedIdentities $freshProtected
        $unit['prelaunch_input_inventory'] = Assert-SessionFreshUnitInputs $unitRoot $unit.copied_inputs
        $arguments = @(('"' + (Join-Path $unitRoot 'HostProject.uproject') + '"'), '/Engine/Maps/Entry',
            '-Unattended', '-NoPause', '-NullRHI', '-NoSplash', '-NoSound', '-NoLiveCoding', '-log', '-DisablePlugins=AndroidFileServer',
            '-EnablePlugins=YacsBobInspection,ModelContextProtocol', ('-AbsLog="' + (Join-Path $ArtifactRoot 'input-boundary-editor.log') + '"'),
            ('-ReportExportPath="' + $reportRoot + '"'), '-execcmds="Automation RunTests YacsBobInspection.InputBoundary;Quit"') + $unit.startup_config_overrides
        # No official-proof opt-in, ExecutePythonScript, trusted marker or BOB producer.
        $script:ownedEditor = Start-Process -FilePath $executable -ArgumentList $arguments -WorkingDirectory $unitRoot `
            -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $ArtifactRoot 'input-boundary-editor-stdout.log') `
            -RedirectStandardError (Join-Path $ArtifactRoot 'input-boundary-editor-stderr.log') -Environment @{
                YACS_MCP_BOB_PROJECT_ROOT = ''; YACS_MCP_BOB_EXPECTED_HEAD = ''; YACS_MCP_BOB_OWNED_EDITOR_PID = ''
                YACS_OWNER_HANDOFF = ''; PYTHONPATH = ''; PYTHONHOME = '' }
        $unit.editor_launched = $true
        $unit.owned_editor_pid = $script:ownedEditor.Id
        $receipt.editor_launched = $true
        $receipt.owned_editor_pid = $script:ownedEditor.Id
        while ($true) {
            $aliveBefore = -not $script:ownedEditor.HasExited
            $listeners = @(Get-SessionUnitOwnedListeners $script:ownedEditor.Id)
            $unit.listener_samples++
            if ($aliveBefore -and -not $script:ownedEditor.HasExited) { $unit.listener_samples_while_alive++ }
            $unit.maximum_owned_listeners = [Math]::Max($unit.maximum_owned_listeners, $listeners.Count)
            foreach ($listener in $listeners) {
                if ($unit.observed_owned_endpoints.Count -ge 16) { throw 'The unit owned endpoint evidence exceeds sixteen rows.' }
                [Net.IPAddress]$address = $null
                if ($listener.OwningProcess -ne $unit.owned_editor_pid -or $listener.LocalAddress -isnot [string] `
                    -or $listener.LocalAddress.Length -gt 64 -or -not [Net.IPAddress]::TryParse($listener.LocalAddress, [ref]$address)) { throw 'An owned unit TCP endpoint has malformed PID/address metadata.' }
                $endpoint = [ordered]@{ owned_editor_pid = [int]$listener.OwningProcess; address = $listener.LocalAddress; port = [int]$listener.LocalPort }
                $existing = @($unit.observed_owned_endpoints | Where-Object { $_.address -ceq $endpoint.address -and $_.port -eq $endpoint.port })
                if ($existing.Count -eq 0) { $unit.observed_owned_endpoints += $endpoint }
            }
            if ($listeners.Count -gt 1 -or ($listeners.Count -eq 1 -and $listeners[0].LocalPort -ne 1985)) { throw 'The fixed unit owns an unknown or multiple TCP listener; no unit proof is admitted.' }
            if ($script:ownedEditor.WaitForExit(200)) { break }
            if ($timer.Elapsed.TotalSeconds -ge 180) { throw 'The fixed InputBoundary Editor exceeded its 180 second deadline.' }
        }
        $script:ownedEditor.WaitForExit()
        $unit.owned_editor_exit_code = $script:ownedEditor.ExitCode
        $unit.owned_editor_exit_observed = $true
        $unit.owned_listeners_after_exit = @(Get-SessionUnitOwnedListeners $script:ownedEditor.Id).Count
        $unit['owned_editor_elapsed_seconds'] = $timer.Elapsed.TotalSeconds
        if ($unit.listener_samples_while_alive -lt 1 -or $timer.Elapsed.TotalSeconds -gt 180 -or $unit.owned_editor_exit_code -ne 0 -or $unit.owned_listeners_after_exit -ne 0) { throw 'The fixed unit lacked a clean bounded exit and owned-listener absence.' }
        $report = Read-SessionJson (Join-Path $reportRoot 'index.json') 8MB
        $index = $report.value
        if ($index.tests -isnot [array] -or $index.tests.Count -ne 1 -or -not (Test-SessionInteger $index.succeeded 1)) { throw 'The InputBoundary report did not finish exactly one successful test.' }
        foreach ($field in @('succeededWithWarnings', 'failed', 'notRun', 'inProcess')) {
            if (-not (Test-SessionInteger $index[$field] 0)) { throw 'The InputBoundary report contains warnings, failure or unfinished tests.' }
        }
        $test = $index.tests[0]
        if ($test.fullTestPath -cne 'YacsBobInspection.InputBoundary' -or $test.state -cne 'Success' `
            -or -not (Test-SessionInteger $test.errors 0) -or -not (Test-SessionInteger $test.warnings 0) -or $test.entries -isnot [array]) { throw 'The exact InputBoundary test did not pass without errors and warnings.' }
        $eventCounts = [ordered]@{}
        $absence = [ordered]@{}
        if ($test.entries.Count -gt 10000) { throw 'The fixed unit report event count exceeds its bound.' }
        foreach ($entry in $test.entries) {
            if ($entry -isnot [Collections.IDictionary] -or $entry.event -isnot [Collections.IDictionary] `
                -or $entry.event.type -isnot [string] -or $entry.event.type -cnotmatch '^[A-Za-z]{1,32}$' -or $entry.event.type -cin @('Error', 'Warning')) { throw 'The InputBoundary report contains a malformed, error or warning event.' }
            if (-not $eventCounts.Contains($entry.event.type)) {
                if ($eventCounts.Count -ge 16) { throw 'The fixed unit report event type count exceeds its bound.' }
                $eventCounts[$entry.event.type] = 0
            }
            $eventCounts[$entry.event.type]++
            $message = $entry.event.message
            if ($message -is [string] -and $message.StartsWith('YacsBobInspection.InputBoundary.McpAbsence', [StringComparison]::Ordinal)) {
                if ($entry.event.type -cne 'Info' -or $message -cnotmatch '^YacsBobInspection[.]InputBoundary[.]McpAbsence phase=(before|after) module_loaded=true server_absent=true auto_start_disabled=true trusted_opt_in_absent=true factory_session_absent=true$') { throw 'A native MCP absence event lacks its exact all-true Info contract.' }
                $phase = if ($message.Contains('phase=before ')) { 'before' } else { 'after' }
                if ($absence.Contains($phase)) { throw 'The unit report duplicates a native MCP absence phase.' }
                $absence[$phase] = $message
            }
        }
        if ($absence.Count -ne 2 -or -not $absence.Contains('before') -or -not $absence.Contains('after')) { throw 'The unit report lacks both actual native MCP absence observations.' }
        $unit.mcp_absence_info = $absence
        $unit.report_summary = [ordered]@{ succeeded = $index.succeeded; succeededWithWarnings = $index.succeededWithWarnings
            failed = $index.failed; notRun = $index.notRun; inProcess = $index.inProcess; fullTestPath = $test.fullTestPath
            state = $test.state; errors = $test.errors; warnings = $test.warnings; entry_event_type_counts = $eventCounts }
        $unit.report = $report.identity
        Add-SessionFreshUnitIdentity $freshProtected $report.identity.path $report.identity 8MB
        Assert-SessionUnitProtectedIdentities $Green.protected
        Assert-SessionUnitProtectedIdentities $freshProtected
        Assert-SessionTrackedSources $RepoRoot
        if ((Get-SessionFileIdentity $report.identity.path 8MB).sha256 -cne $report.identity.sha256) { throw 'The unit report changed during verification.' }
        $unit['protected_input_identities'] = $Green.protected
        $unit.protected_inputs_unchanged = $true
        foreach ($name in @('input-boundary-editor.log', 'input-boundary-editor-stdout.log', 'input-boundary-editor-stderr.log')) {
            $unit.logs[$name] = Get-SessionOwnedLogIdentity (Join-Path $ArtifactRoot $name) $script:ownedEditor
        }
        $absLog = Get-SessionOwnedLogIdentity (Join-Path $ArtifactRoot 'input-boundary-editor.log') $script:ownedEditor -IncludeText
        $traceRows = @($absLog.text -split "`n" | Where-Object { $_ -cmatch 'LogTrace: Display: Control listening on port [0-9]+\s*$' })
        if ($traceRows.Count -gt 1 -or ($traceRows.Count -eq 1 -and ($traceRows[0] -cnotmatch 'LogTrace: Display: Control listening on port 1985\s*$' `
            -or [Text.Encoding]::UTF8.GetByteCount($traceRows[0]) -gt 1024))) { throw 'The owned unit log records an unsupported or unbounded Trace control startup.' }
        if ($unit.observed_owned_endpoints.Count -gt 0) {
            if ($unit.observed_owned_endpoints.Count -ne 1 -or $unit.observed_owned_endpoints[0].port -ne 1985 `
                -or $traceRows.Count -ne 1 -or $traceRows[0] -cnotmatch 'LogTrace: Display: Control listening on port 1985\s*$') { throw 'The owned Trace endpoint lacks its exact owned-log and installed-source attribution.' }
            $unit.trace_control_attributed = $true
            $unit['trace_control_startup_row'] = $traceRows[0].Trim()
        }
        if ($absLog.sha256 -cne $unit.logs['input-boundary-editor.log'].sha256) { throw 'The owned Trace attribution log changed.' }
        $unit['tcp_proof_scope'] = 'AT_MOST_ONE_SOURCE_AND_OWNED_LOG_ATTRIBUTED_TRACE_CONTROL_1985_ENDPOINT; OTHER_LISTENERS_REJECTED; ZERO_AFTER_EXIT'
        foreach ($identity in $unit.logs.Values) {
            if ($identity.size_bytes -gt 0) { Add-SessionFreshUnitIdentity $freshProtected $identity.path $identity 32MB }
        }
        Assert-SessionUnitProtectedIdentities $Green.protected
        Assert-SessionUnitProtectedIdentities $freshProtected
        $unit['fresh_unit_identities'] = $freshProtected
        if ($unit.logs.Count -ne 3 -or $receipt.secondary_errors.Count -ne 0) { throw 'The fixed unit lacks complete owned logs or has a secondary failure.' }
        $unit.native_input_boundary_verified = $true
        $unit.status = 'INPUT_BOUNDARY_VERIFIED'
    } catch { $unit.error = Get-SessionSafeFailureText $_.Exception.Message; $unit.status = 'INPUT_BOUNDARY_BLOCKED'; throw }
    finally {
        if ($null -ne $script:ownedBuild) {
            # This lane owns only these fresh BuildPlugin logs. Read failure
            # excerpts after the observed exit, never while a compiler writes.
            try {
                $unit.owned_build_pid = $script:ownedBuild.Id
                if (-not $script:ownedBuild.HasExited) { $script:ownedBuild.Kill($true) }
                if (-not $script:ownedBuild.WaitForExit(10000) -or -not $script:ownedBuild.HasExited) { throw 'The owned unit build-tree exit was not observed within ten seconds.' }
                $script:ownedBuild.WaitForExit()
                $unit['owned_build_exit_code'] = $script:ownedBuild.ExitCode
                $unit['owned_build_exit_observed'] = $true
                $receipt.owned_build_exit_observed = $true
                foreach ($name in @('input-boundary-plugin-build.log', 'input-boundary-plugin-build-stderr.log')) {
                    $log = Get-SessionOwnedLogIdentity (Join-Path $ArtifactRoot $name) $script:ownedBuild -IncludeText
                    $matchesFound = [Collections.Generic.List[string]]::new()
                    $matchCount = 0
                    foreach ($line in ($log.text -split '\r?\n')) {
                        if ($line -match '(?i)error C[0-9]+|fatal error|error LNK[0-9]+|Exception|BUILD FAILED|AutomationTool exiting|ExitCode=') {
                            $matchCount++
                            $safe = Get-SessionSafeFailureText $line
                            if ($matchesFound.Count -lt 12 -and [Text.Encoding]::UTF8.GetByteCount($safe) -le 1024) {
                                $selected = $matchesFound.ToArray() + @($safe)
                                if ([Text.Encoding]::UTF8.GetByteCount((ConvertTo-Json -InputObject $selected -Compress)) -le 4KB) { $matchesFound.Add($safe) }
                            }
                        }
                    }
                    $unit.build_failure_logs[$name] = [ordered]@{ identity = [ordered]@{ path = $log.path; size_bytes = $log.size_bytes; sha256 = $log.sha256 }
                        error_context = $matchesFound.ToArray(); context_limit = 12; line_utf8_limit_bytes = 1024; log_limit_bytes = 32MB
                        context_json_limit_bytes = 4KB; matching_line_count = $matchCount; context_truncated = $matchCount -gt $matchesFound.Count }
                }
            } catch { $receipt.secondary_errors += 'Cannot observe or retain fixed exited unit-build failure logs.' }
            finally { Stop-SessionOwnedProcess $script:ownedBuild 'build' -BuildTree; $script:ownedBuild = $null }
        }
        if ($null -ne $script:ownedEditor) {
            if (-not $script:ownedEditor.HasExited) {
                try { $script:ownedEditor.Kill(); [void]$script:ownedEditor.WaitForExit(10000) }
                catch { $receipt.secondary_errors += 'Cannot observe fixed unit owned Editor cleanup.' }
            }
            if ($script:ownedEditor.HasExited) {
                $unit.owned_editor_exit_observed = $true
                $unit.owned_editor_exit_code = $script:ownedEditor.ExitCode
                foreach ($name in @('input-boundary-editor.log', 'input-boundary-editor-stdout.log', 'input-boundary-editor-stderr.log')) {
                    try { if (-not $unit.logs.Contains($name)) { $unit.logs[$name] = Get-SessionOwnedLogIdentity (Join-Path $ArtifactRoot $name) $script:ownedEditor } }
                    catch { $receipt.secondary_errors += 'Cannot retain one fixed unit owned log.' }
                }
            }
            Stop-SessionOwnedProcess $script:ownedEditor 'editor'
            $script:ownedEditor = $null
        }
        $cleanupBlocked = $unit.status -ceq 'INPUT_BOUNDARY_VERIFIED' -and $receipt.secondary_errors.Count -ne 0
        if ($cleanupBlocked) {
            $unit.status = 'INPUT_BOUNDARY_BLOCKED'
            $unit.native_input_boundary_verified = $false
            $unit.error = 'The fixed unit has an owned cleanup or log-retention failure.'
        }
        if ($preparationTimer.IsRunning) { $preparationTimer.Stop(); $unit.preparation_elapsed_seconds = $preparationTimer.Elapsed.TotalSeconds }
        $unit['elapsed_seconds'] = if ($null -eq $timer) { 0 } else { $timer.Elapsed.TotalSeconds }
        $path = Join-Path $ArtifactRoot 'input-boundary-unit.json'
        Write-SessionJson $path $unit
        $receipt.proof_files.input_boundary_unit = Get-SessionFileIdentity $path 1MB
        $receipt['native_input_boundary_verified'] = $unit.native_input_boundary_verified
        $console = [ordered]@{}
        foreach ($field in @('schema_version', 'exact_sha', 'status', 'source_only', 'editor_launched', 'compile_performed', 'native_input_boundary_verified',
            'official_mcp_transport_verified', 'native_automation_verified', 'native_bob_capture_verified', 'official_mcp_admitted',
            'persistent_world_mutation', 'performance_pass', 'original_run', 'original_compiled_sha', 'original_host', 'unit_root', 'map', 'test',
            'deadline_seconds', 'owned_editor_pid', 'owned_editor_exit_code', 'owned_editor_exit_observed', 'listener_samples', 'listener_samples_while_alive',
            'maximum_owned_listeners', 'owned_listeners_after_exit', 'observed_owned_endpoints', 'trace_control_attributed', 'mcp_absence_info',
            'protected_inputs_unchanged', 'prelaunch_input_inventory', 'preparation_elapsed_seconds', 'compile_attempted', 'owned_build_pid', 'owned_build_exit_observed', 'owned_build_exit_code',
            'build_failure_logs', 'report', 'report_summary', 'error', 'elapsed_seconds')) {
            $console[$field] = $unit[$field]
        }
        foreach ($field in @('compile_scope', 'plugin_build', 'binary_provenance', 'current_unit_test_delta', 'trace_control_source', 'tcp_proof_scope')) {
            if ($unit.Contains($field)) { $console[$field] = $unit[$field] }
        }
        $console['unit_receipt'] = $receipt.proof_files.input_boundary_unit
        $consoleJson = $console | ConvertTo-Json -Depth 6 -Compress
        if ($consoleJson.Length -gt 16KB) { throw 'The fixed unit console summary exceeds its 16KiB bound.' }
        Write-Host ('INPUT_BOUNDARY_UNIT ' + $consoleJson)
        if ($cleanupBlocked) { throw 'The fixed unit has a secondary cleanup failure; no verification is admitted.' }
    }
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
        $verifiedGreen = Invoke-SessionVerifiedGreenReadback
        & (Join-Path $RepoRoot 'scripts/ue/Read-YacsOfficialMcpRuntimeDependencies.ps1') -EngineRoot $engine.Root -ArtifactRoot $ArtifactRoot -ExpectedHead $ExpectedHead
        $currentSdk = Read-SessionJson (Join-Path $ArtifactRoot 'runtime-dependencies.json') 4MB
        if (-not (Test-SessionInteger $currentSdk.value.schema_version 1) -or $currentSdk.value.exact_sha -cne $ExpectedHead `
            -or $currentSdk.value.source_only -isnot [bool] -or -not $currentSdk.value.source_only) { throw 'The current diagnostic SDK observation differs from its executing source.' }
        foreach ($flag in @('official_mcp_transport_verified', 'official_mcp_admitted', 'argument_policy_parity_verified',
            'local_only_binding_verified', 'existing_project_test_verified', 'native_bob_capture_verified', 'persistent_world_mutation')) {
            if ($currentSdk.value[$flag] -isnot [bool] -or $currentSdk.value[$flag]) { throw 'A current source-only observation claimed runtime verification.' }
        }
        $receipt.proof_files.current_runtime_dependencies = $currentSdk.identity
        $receipt['current_sdk_observation'] = [ordered]@{ scope = 'CURRENT_SOURCE_ONLY_OBSERVATION; NOT_HISTORICAL_RUNTIME_PROOF'
            exact_sha = $ExpectedHead; source_only = $true; identity = $currentSdk.identity }
        Write-Host ('CURRENT_DIAGNOSTIC_SDK_OBSERVATION ' + ($receipt.current_sdk_observation | ConvertTo-Json -Depth 4 -Compress))
        Invoke-SessionFixedFailedUnitReadback
        $receipt.status = 'FAILED_UNIT_STARTUP_READBACK_RETAINED'
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
    $bundleBytes = 0L
    foreach ($name in $bundleNames) {
        $relative = 'Saved/RuntimeProof/OfficialMcpBob/bundle/' + $name
        $memberLimit = if ($name -ceq 'native-samples.json') { 32MB } else { 8MB }
        $remaining = 64MB - $bundleBytes
        if ($remaining -le 0) { throw 'The six fixed bundle files exhaust their 64MiB aggregate bound.' }
        $identity = Get-SessionFileIdentity (Join-Path $SessionRoot $relative) ([Math]::Min($memberLimit, $remaining))
        $bundleBytes += $identity.size_bytes
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
        if ($receipt.status -ceq 'BLOCKED' -and -not $DiagnosePreviousFailure) {
            # The fixed diagnostic/unit branch owns its separate raw readback
            # and unit receipt; never relabel an old failure as this attempt.
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
