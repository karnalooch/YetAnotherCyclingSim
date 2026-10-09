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
    [string] $ExpectedHead,
    # Fixed retained run only; no caller-supplied paths or runtime operation.
    [switch] $DiagnosePreviousFailure
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
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { $hash = [Convert]::ToHexString($algorithm.ComputeHash($stream)).ToLowerInvariant() }
    finally { $algorithm.Dispose(); $stream.Dispose() }
    return [ordered]@{
        path = [IO.Path]::GetFullPath($Path)
        size_bytes = $entry.Length
        # Stream hashing also produces a real SHA256 for empty redirected logs.
        sha256 = $hash
    }
}
function Get-ProbeOwnedRedirectLogIdentity {
    param([Parameter(Mandatory)][ValidateSet('input-boundary-stdout.log', 'input-boundary-stderr.log')][string] $Name)
    if ($receipt.owned_editor_exit_observed -ne $true -or $receipt.owned_editor_pid -isnot [int] -or $receipt.owned_editor_pid -le 0) {
        throw 'Redirected log retention requires the observed exit of this invocation owned Editor.'
    }
    $path = Join-Path $ArtifactRoot $Name
    Assert-ProbePlainPath $path
    $before = Get-Item -LiteralPath $path -Force
    if ($before.PSIsContainer -or $before.Length -gt 2MB) { throw 'Owned redirected log is not a bounded regular file.' }
    $writeTicks = $before.LastWriteTimeUtc.Ticks
    # PowerShell may retain its redirect writer after the child has exited.
    # Sharing that handle permits reading only; byte/time drift still blocks.
    $stream = [IO.FileStream]::new($path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try {
        $buffer = [byte[]]::new(2MB + 1)
        $count = 0
        while (($chunk = $stream.Read($buffer, $count, $buffer.Length - $count)) -gt 0) {
            $count += $chunk
            if ($count -gt 2MB) { throw 'Owned redirected log grew beyond its 2 MiB read bound.' }
        }
        $bytes = [byte[]]::new($count)
        [Array]::Copy($buffer, $bytes, $count)
    }
    finally { $stream.Dispose() }
    Assert-ProbePlainPath $path
    $after = Get-Item -LiteralPath $path -Force
    if ($count -ne $before.Length -or $count -ne $after.Length -or $writeTicks -ne $after.LastWriteTimeUtc.Ticks) {
        throw 'Owned redirected log changed during its retained read.'
    }
    return [ordered]@{
        path = [IO.Path]::GetFullPath($path); size_bytes = $count; last_write_ticks = $writeTicks
        sha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
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
function Invoke-ProbePreviousFailureDiagnostic {
    $previousRoot = 'D:\yacs\runner\_work\YetAnotherCyclingSim\YetAnotherCyclingSim\_official-mcp-native-probe\Saved\RuntimeProof\OfficialMcpNativeProbe\38001987773-1'
    if (-not [string]::Equals([IO.Path]::GetFullPath((Join-Path $RepoRoot 'Saved/RuntimeProof/OfficialMcpNativeProbe/38001987773-1')), $previousRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Previous-failure diagnostic requires the exact retained runner checkout.'
    }
    Assert-ProbePlainPath $previousRoot
    $diagnostic = [ordered]@{
        schema_version = 1; exact_sha = $ExpectedHead; previous_run = '38001987773-1'
        previous_exact_sha = '3e8eee60e4a7d37d61a653f0b52f7dcb09196276'
        previous_package_root = 'D:\yacs\runner\_work\b384\38001987773-1\p'
        status = 'READ_ONLY_DIAGNOSTIC'; files = [ordered]@{}; gaps = @()
        editor_context = @(); editor_context_truncated = $false; automation_summary = $null; accepted_summary = $null
        previous_sdk_receipt_exists = $false; previous_sdk_summary = $null; previous_reflection_receipt_exists = $false
        previous_reflection_marker = $null; previous_reflection_sources = @(); previous_reflection_mismatch_fields = @()
        python_settings_candidates = @(); source_discovery_complete = $true
        read_bytes = 0; source_only = $true; compile_performed = $false
        editor_launched = $false; official_mcp_admitted = $false
        native_input_boundary_verified = $false; native_bob_capture_verified = $false
        persistent_world_mutation = $false; performance_pass = $false
        performance_status = 'DEFERRED_AFTER_M3'
    }
    function Read-ProbeDiagnosticFile {
        param([string] $Path, [long] $Limit)
        Assert-ProbePlainPath $Path
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
        $entry = Get-Item -LiteralPath $Path -Force
        if ($entry.Length -gt $Limit -or $diagnostic.read_bytes + $entry.Length -gt 16MB) {
            throw 'Fixed diagnostic evidence exceeded its per-file or 16 MiB total read bound.'
        }
        $originalWriteTicks = $entry.LastWriteTimeUtc.Ticks
        $stream = [IO.File]::OpenRead($Path)
        try {
            $buffer = [byte[]]::new([int]$Limit + 1)
            $count = 0
            while (($chunk = $stream.Read($buffer, $count, $buffer.Length - $count)) -gt 0) {
                $count += $chunk
                if ($count -gt $Limit) { throw 'Fixed diagnostic evidence grew beyond its read bound.' }
            }
            $bytes = [byte[]]::new($count)
            [Array]::Copy($buffer, $bytes, $count)
        }
        finally { $stream.Dispose() }
        $afterEntry = Get-Item -LiteralPath $Path -Force
        if ($count -ne $entry.Length -or $count -ne $afterEntry.Length -or $originalWriteTicks -ne $afterEntry.LastWriteTimeUtc.Ticks) {
            throw 'Fixed retained diagnostic evidence changed during its read.'
        }
        $identity = [ordered]@{
            path = [IO.Path]::GetFullPath($Path); size_bytes = $count
            sha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
        }
        $diagnostic.read_bytes += $count
        return @{ identity = $identity; bytes = $bytes; text = [Text.Encoding]::UTF8.GetString($bytes) }
    }
    function Get-ProbeSafeDiagnosticText {
        param([string] $Text, [int] $MaximumCharacters = 1024)
        $safe = [regex]::Replace($Text, '(?i)https?://\S+', '[URL_REDACTED]')
        $safe = [regex]::Replace($safe, '(?i)\b(?:authorization|bearer|token|signature|sig)\s*[:=]\s*\S+', '[SECRET_FIELD_REDACTED]')
        if ($safe.Length -gt $MaximumCharacters) { return $safe.Substring(0, $MaximumCharacters) + '[TRUNCATED]' }
        return $safe
    }
    function Write-ProbeDiagnosticSummary {
        param([string] $Label, $Value)
        Write-Host ($Label + ' ' + (Get-ProbeSafeDiagnosticText ($Value | ConvertTo-Json -Depth 10 -Compress) 8192))
    }
    # The prior marker is authenticated before any expected hash is used.
    # It never selects paths: exactly these five original proof inputs are read.
    $previousHost = 'D:\yacs\runner\_work\b384\38001987773-1\p\HostProject'
    $markerFile = Read-ProbeDiagnosticFile (Join-Path $previousHost '.yacs-mcp-native-reflection-proof.json') 64KB
    if ($null -eq $markerFile) { $diagnostic.gaps += 'Previous reflection marker is absent.' }
    else {
        if ($markerFile.identity.sha256 -cne 'd14a1235acdf610ff733965e188417d28e74c216b882b6456346d21b11c9d587') {
            throw 'Previous reflection marker differs from its exact original receipt SHA256.'
        }
        $marker = $markerFile.text | ConvertFrom-Json -AsHashtable -Depth 16
        $markerFields = @('schema_version', 'exact_sha', 'host_project_root', 'artifact_root', 'script_sha256',
            'public_header_sha256', 'plugin_descriptor_sha256', 'host_project_descriptor_sha256', 'host_engine_config_sha256')
        if ($marker -isnot [Collections.IDictionary] -or $marker.Count -ne $markerFields.Count) {
            throw 'Previous reflection marker is outside its fixed object contract.'
        }
        foreach ($field in $markerFields) {
            if (-not $marker.Contains($field)) { throw 'Previous reflection marker is missing a fixed field.' }
        }
        if ($marker['schema_version'] -isnot [long] -and $marker['schema_version'] -isnot [int]) { throw 'Previous reflection marker has an invalid schema type.' }
        if ($marker['schema_version'] -ne 1 -or $marker['exact_sha'] -cne $diagnostic.previous_exact_sha `
            -or -not [string]::Equals([IO.Path]::GetFullPath([string]$marker['host_project_root']), $previousHost, [StringComparison]::OrdinalIgnoreCase) `
            -or -not [string]::Equals([IO.Path]::GetFullPath([string]$marker['artifact_root']), $previousRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Previous reflection marker disagrees with the exact retained run context.'
        }
        $diagnostic.files.reflection_marker = $markerFile.identity
        $diagnostic.previous_reflection_marker = $marker
        Write-ProbeDiagnosticSummary 'PREVIOUS_REFLECTION_MARKER' $marker
        $readbackRoot = Join-Path $ArtifactRoot 'Previous38001987773/Reflection'
        Assert-ProbePlainPath $readbackRoot
        if (Test-Path -LiteralPath $readbackRoot) { throw 'Previous reflection diagnostic destination already exists.' }
        New-Item -ItemType Directory -Path $readbackRoot | Out-Null
        [IO.File]::WriteAllBytes((Join-Path $readbackRoot 'reflection-marker.json'), $markerFile.bytes)
        $sourcePaths = [ordered]@{
            script_sha256 = @{ path = (Join-Path $RepoRoot 'scripts/ue/probe_official_mcp_bob_reflection.py'); original = 'eb15de2ae7a425115d2bf217170b3c01e6688b709eeb69e319f381482cafc2ce' }
            public_header_sha256 = @{ path = (Join-Path $previousHost 'Plugins/YacsBobInspection/Source/YacsBobInspection/Public/YacsBobLandscapeHit.h'); original = '244ff4f617b6156481888b5f3f2acd07e1ead35f627903bcca62780b44b8476d' }
            plugin_descriptor_sha256 = @{ path = (Join-Path $previousHost 'Plugins/YacsBobInspection/YacsBobInspection.uplugin'); original = '8c46c7ddbe8cd132f8704c4c169cf16b1872c37a4cd8c3d27e908cff324e55eb' }
            host_project_descriptor_sha256 = @{ path = (Join-Path $previousHost 'HostProject.uproject'); original = '324d12350939f3cbb1d34451c7e0dfbaa84195e44c4fb2c382d6842c30f091ce' }
            host_engine_config_sha256 = @{ path = (Join-Path $previousHost 'Config/DefaultEngine.ini'); original = '495794932485e78086387812d946099d0993934796475dd2743bf48115b10aa0' }
        }
        foreach ($field in $sourcePaths.Keys) {
            if ($marker[$field] -isnot [string] -or $marker[$field] -cnotmatch '^[0-9a-f]{64}$') { throw 'Previous reflection marker has an invalid source hash.' }
            $source = $sourcePaths[$field]
            $file = Read-ProbeDiagnosticFile $source.path 64KB
            if ($null -eq $file) { $diagnostic.gaps += "Previous reflection input $field is absent."; continue }
            $currentScriptChanged = $field -ceq 'script_sha256' -and $file.identity.sha256 -cne $source.original
            $matches = $file.identity.sha256 -ceq $marker[$field]
            $row = [ordered]@{
                field = $field; identity = $file.identity; marker_expected_sha256 = $marker[$field]
                original_receipt_sha256 = $source.original; marker_matches_original_receipt = ($marker[$field] -ceq $source.original)
                matches_marker = $matches; original_run_comparable = (-not $currentScriptChanged)
                comparison_status = if ($currentScriptChanged) { 'CURRENT_CHECKOUT_CHANGED' } elseif ($matches) { 'MATCH' } else { 'MISMATCH' }
            }
            if (-not $matches -and -not $currentScriptChanged) { $diagnostic.previous_reflection_mismatch_fields += $field }
            $diagnostic.files["reflection_source/$field"] = $file.identity
            $diagnostic.previous_reflection_sources += $row
            Write-ProbeDiagnosticSummary 'PREVIOUS_REFLECTION_SOURCE' $row
            if ($field -ceq 'host_engine_config_sha256') {
                # These 469 retained bytes are the sole observed drift. Read
                # no additional file and reveal no credentials or URL values.
                if ($file.identity.size_bytes -ne 469 -or $file.identity.sha256 -cne 'a090175a44123f56df2d6432a5cf2fa45f9aaab3d33df5fdab51d901a77551b8') {
                    throw 'Prior generated config differs from its exact diagnosed post-startup bytes.'
                }
                $configContext = @()
                $configLines = $file.text -split '\r?\n'
                foreach ($line in ($configLines | Select-Object -First 32)) {
                    $safeLine = if ($line -match '(?i)^\s*[^;#\[]*(?:token|secret|password|credential|api.?key|authorization)\s*=') { '[SECRET_CONFIG_VALUE_REDACTED]' }
                        else { Get-ProbeSafeDiagnosticText $line 512 }
                    $configContext += $safeLine
                }
                $diagnostic['previous_generated_engine_config_context'] = $configContext
                $diagnostic['previous_generated_engine_config_context_truncated'] = $configLines.Count -gt 32
                Write-ProbeDiagnosticSummary 'PREVIOUS_GENERATED_ENGINE_CONFIG' $configContext
            }
        }
        Write-ProbeJson (Join-Path $readbackRoot 'source-identities.json') $diagnostic.previous_reflection_sources
    }
    foreach ($name in @('input-boundary-editor.log', 'input-boundary-stdout.log', 'input-boundary-stderr.log')) {
        $file = Read-ProbeDiagnosticFile (Join-Path $previousRoot $name) 2MB
        if ($null -eq $file) { $diagnostic.gaps += "Missing retained $name"; continue }
        $diagnostic.files[$name] = $file.identity
        if ($name -ceq 'input-boundary-editor.log' -and ($file.identity.sha256 -cne '36b269882449b17ede1b03fcc79aa8a7a1aa154d966e581334f79f96b08bf026' -or $file.identity.size_bytes -ne 293469)) {
            throw 'Retained Editor log differs from the exact previous-run SHA256/length.'
        }
        $lines = $file.text -split '\r?\n'
        $selected = [Collections.Generic.SortedSet[int]]::new()
        if ($name -ceq 'input-boundary-editor.log') {
            # Preserve the causal shutdown/assertion tail before other contexts.
            for ($line = [Math]::Max(0, $lines.Length - 80); $line -lt $lines.Length; $line++) { [void]$selected.Add($line) }
        }
        foreach ($pattern in @('(?i)LogPython:.*(?:Error|Fatal)|Traceback|Exception|ScriptError|probe_official_mcp_bob_reflection',
            '(?i)fatal|assertion|error:|Test failed|Failed to load|Missing.*module',
            '(?i)InputBoundary|YacsBobInspection|AutomationTest|Test Started|Test Completed|LogExit:|LogLoad:.*Entry')) {
            for ($index = 0; $index -lt $lines.Length; $index++) {
                if ($lines[$index] -match $pattern) {
                    for ($line = [Math]::Max(0, $index - 2); $line -le [Math]::Min($index + 2, $lines.Length - 1); $line++) {
                        if ($selected.Count -lt 160) { [void]$selected.Add($line) }
                        elseif (-not $selected.Contains($line)) { $diagnostic.editor_context_truncated = $true }
                    }
                }
            }
        }
        foreach ($line in $selected) {
            if ($diagnostic.editor_context.Count -ge 200) { $diagnostic.editor_context_truncated = $true; break }
            if ($lines[$line] -match '(?i)command\s*line|authorization|bearer\s') { continue }
            $text = Get-ProbeSafeDiagnosticText ('{0}:{1}: {2}' -f $name, ($line + 1), $lines[$line])
            $diagnostic.editor_context += $text
            Write-Host $text
        }
    }
    # Read old receipts only if actually present; missing SDK output is a gap,
    # never inferred success from the fact that the independent build passed.
    foreach ($name in @('runtime-dependencies.json', 'native-python-reflection.json')) {
        $path = Join-Path $previousRoot $name
        Assert-ProbePlainPath $path
        $exists = Test-Path -LiteralPath $path -PathType Leaf
        if ($name -ceq 'runtime-dependencies.json') { $diagnostic.previous_sdk_receipt_exists = $exists }
        else { $diagnostic.previous_reflection_receipt_exists = $exists }
        Write-ProbeDiagnosticSummary 'PREVIOUS_RECEIPT_PRESENCE' @{ path = $name; exists = $exists }
        if (-not $exists) { $diagnostic.gaps += "Previous $name is absent."; continue }
        $file = Read-ProbeDiagnosticFile $path 2MB
        $diagnostic.files[$name] = $file.identity
        $value = $file.text.TrimStart([char]0xFEFF) | ConvertFrom-Json -AsHashtable -Depth 64
        $summary = [ordered]@{ path = $name }
        foreach ($field in @('status', 'exact_sha', 'reflection_verified', 'source_unchanged', 'error', 'python_remote_execution')) {
            if ($value.Contains($field)) {
                $scalar = $value[$field]
                $summary[$field] = if ($scalar -is [string]) { Get-ProbeSafeDiagnosticText $scalar }
                    elseif ($null -eq $scalar -or $scalar -is [bool] -or $scalar -is [int] -or $scalar -is [long]) { $scalar }
                    else { 'MALFORMED_SCALAR' }
            }
        }
        if ($name -ceq 'runtime-dependencies.json') { $diagnostic.previous_sdk_summary = $summary }
        Write-ProbeDiagnosticSummary 'PREVIOUS_RECEIPT_SUMMARY' $summary
    }
    $indexFile = Read-ProbeDiagnosticFile (Join-Path $previousRoot 'InputBoundaryReport/index.json') 2MB
    if ($null -eq $indexFile) { $diagnostic.gaps += 'Previous Automation index.json is absent.' }
    else {
        $diagnostic.files.automation_index = $indexFile.identity
        $index = $indexFile.text.TrimStart([char]0xFEFF) | ConvertFrom-Json -AsHashtable -Depth 64
        $summary = [ordered]@{}
        foreach ($field in @('succeeded', 'succeededWithWarnings', 'failed', 'notRun', 'inProcess')) {
            $summary[$field] = if (Test-ProbeNonnegativeInteger $index[$field]) { $index[$field] } else { 'MALFORMED_COUNTER' }
        }
        $summary.tests = @()
        foreach ($test in @($index['tests'] | Select-Object -First 8)) {
            $row = [ordered]@{
                fullTestPath = Get-ProbeSafeDiagnosticText ([string]$test['fullTestPath']) 256
                state = Get-ProbeSafeDiagnosticText ([string]$test['state']) 64
                errors = if (Test-ProbeNonnegativeInteger $test['errors']) { $test['errors'] } else { 'MALFORMED_COUNTER' }
                warnings = if (Test-ProbeNonnegativeInteger $test['warnings']) { $test['warnings'] } else { 'MALFORMED_COUNTER' }
                error_events = @()
            }
            foreach ($event in @($test['entries'] | Where-Object { $_['event']['type'] -ceq 'Error' } | Select-Object -First 8)) {
                $row.error_events += Get-ProbeSafeDiagnosticText ([string]$event['event']['message'])
            }
            $summary.tests += $row
        }
        $diagnostic.automation_summary = $summary
        Write-ProbeDiagnosticSummary 'PREVIOUS_AUTOMATION' $summary
    }
    $acceptedFile = Read-ProbeDiagnosticFile (Join-Path $previousRoot 'Accepted363/accepted-read.json') 2MB
    if ($null -eq $acceptedFile) { $diagnostic.gaps += 'Previous accepted-read.json is absent.' }
    else {
        $diagnostic.files.accepted_read = $acceptedFile.identity
        $accepted = $acceptedFile.text.TrimStart([char]0xFEFF) | ConvertFrom-Json -AsHashtable -Depth 64
        $summary = [ordered]@{}
        foreach ($field in @('status', 'source_exact_sha', 'artifact_id', 'zip_verified', 'downloaded_zip_sha256', 'error', 'error_code', 'local_exception_type', 'retained_metadata_path', 'retained_metadata_observed_bytes')) {
            if ($accepted.Contains($field)) {
                $value = $accepted[$field]
                $summary[$field] = if ($value -is [string]) { Get-ProbeSafeDiagnosticText $value }
                    elseif ($null -eq $value -or $value -is [bool] -or $value -is [int] -or $value -is [long]) { $value }
                    else { 'MALFORMED_SCALAR' }
            }
        }
        $diagnostic.accepted_summary = $summary
        Write-ProbeDiagnosticSummary 'PREVIOUS_ACCEPTED' $summary
        if ($accepted['zip_verified'] -ne $true -or $accepted['downloaded_zip_sha256'] -cne '3f65958a52cd476bbf268eea7cb884ada06206e15b3fd00286162848e0bece9c') {
            throw 'Previous accepted JSON readback lacks the pinned ZIP identity.'
        }
        $pinnedJsonHashes = [ordered]@{
            'saved-material-consumer/consumer-manifest.json' = '0eff084ad7bad97200e8947c47f5480ebb504b928769ab1bc36609de6ef777fb'
            'saved-material-consumer/delivery-package-manifest.json' = 'd8e7dfe050d952f8c0bbc236f1effe15ccc9a48b578277fb4b4c4817d8c122c8'
            'saved-material-consumer/reload-receipt.json' = '2e4025d7b56f60bc5f8f13c3e16390b4ae4bcff915ba680a14c64b8fe3190aae'
            'saved-material-consumer/fresh-render-receipt.json' = '60a5bccd95ea78f58a910c25f293db12eb124429e281b8a96d590558f45cc356'
            'checkout-restoration.json' = '6e15ef090fc94d694e35aba9ca3dac78ddc7c581d495d9f23cf1a7f772da7c34'
            'checkout-restoration-post-material.json' = '41c473d3e90fe3f7c72ec1baec741d8356c7e5e00f6e2cc56a7c5611837265a0'
        }
        foreach ($name in $pinnedJsonHashes.Keys) {
            $jsonFile = Read-ProbeDiagnosticFile (Join-Path $previousRoot "Accepted363/json/$name") 2MB
            if ($null -eq $jsonFile) { $diagnostic.gaps += "Missing previously extracted $name"; continue }
            $rows = @($accepted['selected_json'] | Where-Object { $_['path'] -ceq $name })
            if ($rows.Count -ne 1 -or $rows[0]['archive_sha256'] -cne $jsonFile.identity.sha256 -or $jsonFile.identity.sha256 -cne $pinnedJsonHashes[$name]) {
                throw 'Previously extracted accepted JSON differs from its pinned ZIP read receipt.'
            }
            $diagnostic.files["accepted_json/$name"] = $jsonFile.identity
            $target = Join-Path $ArtifactRoot "Previous38001987773/Accepted363/json/$name"
            Assert-ProbePlainPath $target
            New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
            if (Test-Path -LiteralPath $target) { throw 'Previous JSON diagnostic readback target already exists.' }
            [IO.File]::WriteAllBytes($target, $jsonFile.bytes)
            $value = $jsonFile.text.TrimStart([char]0xFEFF) | ConvertFrom-Json -AsHashtable -Depth 64
            $metadata = [ordered]@{ path = $name }
            foreach ($field in @('status', 'exact_sha', 'map_package', 'map_sha256', 'canonical_map_package', 'canonical_map_sha256',
                'component_count', 'fresh_process', 'geometry_mutation', 'geometry_snapshot_sha256', 'material_recipe_sha256',
                'expected_material_parent', 'expected_material_instance', 'source_proof', 'initial_receipt_sha256')) {
                if ($value.Contains($field)) { $metadata[$field] = $value[$field] }
            }
            Write-ProbeDiagnosticSummary 'PREVIOUS_ACCEPTED_METADATA' $metadata
        }
        # Stat the same five frozen metadata names only; never read a large
        # capture JSON or retry the download to establish the old 2 MiB gate.
        $diagnostic['accepted_retained_metadata_stats'] = @()
        $frozenProofRoot = 'D:\yacs\work\proofs\sa-calobra-whole-map\94827365ef8e83e52717bb21f9d6efa921aa2d1e\37954100285-1'
        foreach ($name in @('whole-map-master-receipt.json', 'generated-assets-verification.json', 'native-proof-verification.json',
            'capture/whole-map-prep/whole-map-prep-receipt.json', 'whole-map-prep/surface-prep-manifest.json')) {
            $metadataPath = Join-Path $frozenProofRoot $name
            Assert-ProbePlainPath $metadataPath
            $metadataStat = [ordered]@{ path = $metadataPath; exists = (Test-Path -LiteralPath $metadataPath -PathType Leaf); read_performed = $false; observed_size_bytes = $null; exceeds_prior_2mib_limit = $null }
            if ($metadataStat.exists) {
                $metadataStat.observed_size_bytes = (Get-Item -LiteralPath $metadataPath -Force).Length
                $metadataStat.exceeds_prior_2mib_limit = $metadataStat.observed_size_bytes -gt 2MB
            }
            $diagnostic.accepted_retained_metadata_stats += $metadataStat
            Write-ProbeDiagnosticSummary 'PREVIOUS_ACCEPTED_METADATA_STAT' $metadataStat
        }
    }
    # Discover only this exact basename beneath the already known Python plugin
    # Source root. No engine walk or source execution; bounded 512 entries/depth6.
    $sourceRoot = Join-Path $engine.Root 'Engine/Plugins/Experimental/PythonScriptPlugin/Source'
    Assert-ProbePlainPath $sourceRoot
    if (-not (Test-Path -LiteralPath $sourceRoot -PathType Container)) { $diagnostic.gaps += 'Confirmed Python plugin Source directory is absent.' }
    else {
        $queue = [Collections.Generic.Queue[object]]::new()
        $queue.Enqueue(@{ path = $sourceRoot; depth = 0 })
        $entries = 0
        while ($queue.Count -gt 0) {
            $directory = $queue.Dequeue()
            foreach ($entryPath in [IO.Directory]::EnumerateFileSystemEntries($directory.path)) {
                $entries++
                if ($entries -gt 512) { $diagnostic.source_discovery_complete = $false; break }
                $item = Get-Item -LiteralPath $entryPath -Force
                if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { $diagnostic.source_discovery_complete = $false; continue }
                if ($item.PSIsContainer) {
                    if ($directory.depth -lt 6) { $queue.Enqueue(@{ path = $item.FullName; depth = $directory.depth + 1 }) }
                    else { $diagnostic.source_discovery_complete = $false }
                }
                elseif ($item.Name -ceq 'PythonScriptPluginSettings.h') {
                    if ($diagnostic.python_settings_candidates.Count -ge 2) { throw 'Fixed Python settings basename has more than two bounded candidates.' }
                    $header = Read-ProbeDiagnosticFile $item.FullName 256KB
                    $context = @()
                    $lines = $header.text -split '\r?\n'
                    $numbers = [Collections.Generic.SortedSet[int]]::new()
                    for ($index = 0; $index -lt $lines.Length; $index++) {
                        if ($lines[$index] -match '\b(?:UCLASS|UPythonScriptPluginSettings|bRemoteExecution)\b|^\s*public\s*:') {
                            for ($line = [Math]::Max(0, $index - 4); $line -le [Math]::Min($index + 8, $lines.Length - 1); $line++) {
                                if ($numbers.Count -lt 60) { [void]$numbers.Add($line) }
                            }
                        }
                    }
                    foreach ($line in $numbers) { $context += Get-ProbeSafeDiagnosticText ('{0}: {1}' -f ($line + 1), $lines[$line]) }
                    $diagnostic.python_settings_candidates += @{ identity = $header.identity; context = $context }
                    Write-Host ('PYTHON_SETTINGS_SOURCE ' + ($header.identity | ConvertTo-Json -Compress))
                    foreach ($line in $context) { Write-Host $line }
                }
            }
            if ($entries -gt 512) { break }
        }
        if (-not $diagnostic.source_discovery_complete) { $diagnostic.gaps += 'Python settings basename inventory hit a depth/entry/link boundary.' }
        if ($diagnostic.python_settings_candidates.Count -eq 0) { $diagnostic.gaps += 'Fixed PythonScriptPluginSettings.h basename not found within the bounded Source inventory.' }
    }
    Write-ProbeJson (Join-Path $ArtifactRoot 'previous-failure-diagnostic.json') $diagnostic
    $receipt['diagnostic_previous_run'] = '38001987773-1'
    $receipt.proof_files.previous_failure_diagnostic = Get-ProbeFileIdentity (Join-Path $ArtifactRoot 'previous-failure-diagnostic.json')
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
    owned_editor_exit_observed = $false
    owned_editor_timed_out = $false
    proof_files = [ordered]@{}
    host_project_plugin_list = @()
    disabled_engine_plugins = @()
    disabled_engine_plugin_identity = $null
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
    secondary_errors = @()
    secondary_error_details = @()
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
    if ($DiagnosePreviousFailure) {
        Invoke-ProbePreviousFailureDiagnostic
        Assert-ProbeIdleHost
        # Same bounded reader now includes the approved fixed Core ini parser,
        # needed to establish early settings without editing tracked Config.
        & (Join-Path $PSScriptRoot 'Read-YacsOfficialMcpRuntimeDependencies.ps1') -EngineRoot $engine.Root -ArtifactRoot $ArtifactRoot -ExpectedHead $ExpectedHead
        $receipt.status = 'PREVIOUS_FAILURE_DIAGNOSTIC_RETAINED'
        return
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

    # This exact installed descriptor establishes the plugin name responsible
    # for the diagnosed generated-Config write. Disable it only in this launch.
    $afsPath = Join-Path $engine.Root 'Engine/Plugins/Runtime/AndroidFileServer/AndroidFileServer.uplugin'
    Assert-ProbePlainPath $afsPath
    $afsEntry = Get-Item -LiteralPath $afsPath -Force
    if ($afsEntry.PSIsContainer -or $afsEntry.Name -cne 'AndroidFileServer.uplugin' -or $afsEntry.Length -gt 64KB) {
        throw 'The fixed AndroidFileServer descriptor is not a bounded regular file.'
    }
    $afsWriteTicks = $afsEntry.LastWriteTimeUtc.Ticks
    $afsStream = [IO.File]::OpenRead($afsPath)
    try {
        $afsBuffer = [byte[]]::new(64KB + 1)
        $afsCount = 0
        while (($chunk = $afsStream.Read($afsBuffer, $afsCount, $afsBuffer.Length - $afsCount)) -gt 0) {
            $afsCount += $chunk
            if ($afsCount -gt 64KB) { throw 'The fixed AndroidFileServer descriptor grew beyond its read bound.' }
        }
        $afsBytes = [byte[]]::new($afsCount)
        [Array]::Copy($afsBuffer, $afsBytes, $afsCount)
    }
    finally { $afsStream.Dispose() }
    $afsAfter = Get-Item -LiteralPath $afsPath -Force
    if ($afsCount -ne $afsEntry.Length -or $afsCount -ne $afsAfter.Length -or $afsWriteTicks -ne $afsAfter.LastWriteTimeUtc.Ticks) {
        throw 'The fixed AndroidFileServer descriptor changed during read.'
    }
    $afsDescriptor = [Text.Encoding]::UTF8.GetString($afsBytes).TrimStart([char]0xFEFF) | ConvertFrom-Json -AsHashtable -Depth 16
    if ($afsDescriptor -isnot [Collections.IDictionary] -or -not $afsDescriptor.Contains('Modules') `
        -or $afsDescriptor['Modules'] -isnot [array] -or $afsDescriptor['Modules'].Count -gt 16) {
        throw 'The fixed AndroidFileServer descriptor has no bounded module declaration.'
    }
    $afsModules = @($afsDescriptor['Modules'] | ForEach-Object { $_['Name'] })
    if ('AndroidFileServerEditor' -cnotin $afsModules -or @($afsModules | Where-Object { $_ -isnot [string] -or $_ -cnotmatch '^[A-Za-z_][A-Za-z0-9_]*$' }).Count) {
        throw 'The actual descriptor does not establish the diagnosed AndroidFileServerEditor module.'
    }
    $receipt.disabled_engine_plugins = @('AndroidFileServer')
    $receipt.disabled_engine_plugin_identity = [ordered]@{
        path = $afsPath; size_bytes = $afsCount; modules = $afsModules
        sha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($afsBytes)).ToLowerInvariant()
    }

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
    # Exact installed path/hash observed by read-only diagnostic 37998743610.
    $settingsPath = Join-Path $engine.Root 'Engine/Plugins/Experimental/PythonScriptPlugin/Source/PythonScriptPlugin/Private/PythonScriptPluginSettings.h'
    $settingsExpectedSha = '6c5f68a3945759234a9b38a98ac7d1369a91982f9d36c433eb2e518e79ebb5f2'
    $settingsEvidence = [ordered]@{
        schema_version = 1; exact_sha = $ExpectedHead; path = $settingsPath
        status = 'UNESTABLISHED'; source_sha256 = $null; expected_source_sha256 = $settingsExpectedSha
        source_diagnostic_run = '37998743610'; config_engine = $false
        public_config_remote_execution = $false; context = @(); error = $null
        official_mcp_admitted = $false; persistent_world_mutation = $false
    }
    try {
        Assert-ProbePlainPath $settingsPath
        if (-not (Test-Path -LiteralPath $settingsPath -PathType Leaf)) { throw 'Fixed Python settings header is absent.' }
        $settingsIdentity = Get-ProbeFileIdentity $settingsPath
        if ($settingsIdentity.size_bytes -gt 256KB) { throw 'Fixed Python settings header exceeds 256 KiB.' }
        $settingsEvidence.source_sha256 = $settingsIdentity.sha256
        if ($settingsIdentity.sha256 -cne $settingsExpectedSha) {
            throw 'Installed Python settings source differs from the exact diagnostic SHA256.'
        }
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
        '-DisablePlugins=AndroidFileServer',
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
    if ($null -eq $ownedEditor.ExitCode -or $ownedEditor.ExitCode -ne 0) { throw "The owned bare HostProject Editor did not exit successfully (exit=$($ownedEditor.ExitCode))." }
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
                if (-not $ownedEditor.WaitForExit(10000)) {
                    $receipt.secondary_errors += 'Owned Editor did not exit after bounded termination.'
                    if (-not $receipt.error) { $receipt.error = $receipt.secondary_errors[-1] }
                    $receipt.status = 'BLOCKED'
                }
            }
            $receipt.owned_editor_exit_observed = $ownedEditor.HasExited
            if ($receipt.owned_editor_exit_observed -and $null -eq $receipt.owned_editor_exit_code) {
                $receipt.owned_editor_exit_code = $ownedEditor.ExitCode
            }
        }
        catch {
            $receipt.secondary_errors += 'Cannot terminate the owned isolated Editor handle.'
            if (-not $receipt.error) { $receipt.error = $receipt.secondary_errors[-1] }
            $receipt.status = 'BLOCKED'
        }
        finally { $ownedEditor.Dispose() }
    }
    foreach ($name in @('native-plugin-build.log', 'input-boundary-editor.log', 'input-boundary-stdout.log', 'input-boundary-stderr.log', 'python-runtime-settings.json', 'runtime-dependencies.json')) {
        $path = Join-Path $ArtifactRoot $name
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            try {
                $receipt.proof_files[$name] = if ($name -cin @('input-boundary-stdout.log', 'input-boundary-stderr.log')) {
                    Get-ProbeOwnedRedirectLogIdentity $name
                }
                else { Get-ProbeFileIdentity $path }
            }
            catch {
                $receipt.secondary_errors += "Cannot retain native proof output identity: $name ($($_.Exception.GetType().Name))."
                $baseError = $_.Exception.GetBaseException()
                $receipt.secondary_error_details += [ordered]@{
                    output = $name; exception_type = $_.Exception.GetType().FullName
                    inner_exception_type = $baseError.GetType().FullName; hresult = $baseError.HResult.ToString('X8')
                }
                $receipt.status = 'BLOCKED'
                if (-not $receipt.error) { $receipt.error = $receipt.secondary_errors[-1] }
            }
        }
    }
    foreach ($name in @('input-boundary-stdout.log', 'input-boundary-stderr.log')) {
        if (-not $receipt.proof_files.Contains($name)) { continue }
        try {
            $identity = $receipt.proof_files[$name]
            Assert-ProbePlainPath $identity.path
            $entry = Get-Item -LiteralPath $identity.path -Force
            if ($entry.PSIsContainer -or $entry.Length -ne $identity.size_bytes -or $entry.LastWriteTimeUtc.Ticks -ne $identity.last_write_ticks) {
                throw 'Owned redirected log changed before receipt persistence.'
            }
        }
        catch {
            $receipt.secondary_errors += "Owned redirected log final recheck failed: $name."
            $receipt.status = 'BLOCKED'
            if (-not $receipt.error) { $receipt.error = $receipt.secondary_errors[-1] }
        }
    }
    $json = $receipt | ConvertTo-Json -Depth 20
    [IO.File]::WriteAllText((Join-Path $ArtifactRoot 'native-plugin-build.json'), $json, [Text.UTF8Encoding]::new($false))
    Write-Host $json
    if ($receipt.status -ceq 'BLOCKED') { throw $receipt.error }
}
