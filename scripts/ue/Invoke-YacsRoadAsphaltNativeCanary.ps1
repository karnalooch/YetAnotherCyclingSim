#requires -Version 7.4
<# Native transient material-only follow-up after the admitted #364 baseline. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string] $ExpectedHead,
    [Parameter(Mandatory)][ValidatePattern('^[1-9][0-9]{0,19}-[1-9][0-9]{0,5}$')][string] $RunToken,
    [string] $WorkspaceConfig = 'D:\yacs\workspace.json',
    [string] $RepoRoot = (Join-Path $PSScriptRoot '../..')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Asphalt material canary requires the trusted Windows host.' }
$ownedEditor = $null
$root = $null
$evidence = $null
$receipt = [ordered]@{
    schema_version = 1; issue = 364; exact_sha = $ExpectedHead
    run_token = $RunToken; status = 'PREFLIGHT_PENDING'
    baseline_receipt = $null; original_scene_read_pass = $false
    original_material_source = $null; owned_editor_pid = $null
    owned_editor_exit_code = $null; owned_editor_exit_observed = $false
    owned_editor_stopped_on_failure = $false; deadline_seconds = 420
    native_canary = $null; native_material_bind_and_rollback_verified = $false
    landscape_mutated = $false; map_saved = $false
    visual_accepted = $false; shader_gpu_verified = $false
    performance_status = 'DEFERRED_AFTER_M3'; performance_pass = $false
    logs = [ordered]@{}; error = $null; secondary_errors = @()
}

function Assert-PlainPath {
    param([string] $Path)
    if (-not [IO.Path]::IsPathFullyQualified($Path) -or $Path -match '[\x00\r\n"]') {
        throw 'Asphalt native path must be absolute and plain.'
    }
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        try { $attrs = [IO.File]::GetAttributes($cursor) }
        catch [IO.FileNotFoundException] { $attrs = $null }
        catch [IO.DirectoryNotFoundException] { $attrs = $null }
        if ($null -ne $attrs -and ($attrs -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Asphalt native source/evidence cannot traverse junctions.'
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}
function Get-Identity {
    param([string] $Path, [long] $Limit = 64MB, [switch] $AllowEmpty)
    Assert-PlainPath $Path
    $before = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ($before.PSIsContainer -or $before.Length -gt $Limit -or
        ($before.Length -le 0 -and -not $AllowEmpty)) {
        throw 'Asphalt proof input is not a bounded regular file.'
    }
    $hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    $after = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ($before.Length -ne $after.Length -or
        $before.LastWriteTimeUtc.Ticks -ne $after.LastWriteTimeUtc.Ticks) {
        throw 'Asphalt proof source changed during hashing.'
    }
    return [ordered]@{ path = [IO.Path]::GetFullPath($Path)
        sha256 = $hash; size_bytes = $before.Length }
}
function Get-ClosedLogIdentity {
    param([string] $Path)
    for ($attempt = 1; $attempt -le 40; $attempt++) {
        try { return Get-Identity $Path 64MB -AllowEmpty }
        catch {
            $inner = $_.Exception
            $locked = $false
            while ($inner) {
                if ($inner -is [IO.IOException] -and
                    $inner.HResult -in @(-2147024864, -2147024863)) { $locked = $true; break }
                $inner = $inner.InnerException
            }
            if (-not $locked -or $attempt -ge 40) { throw }
            Start-Sleep -Milliseconds 250
        }
    }
}
function Require-IdleHost {
    $state = & (Join-Path $root 'scripts/runner/Get-YacsUnrealHostState.ps1')
    if ($state.status -cne 'IDLE') { throw 'Asphalt canary yields to the open local Unreal Editor.' }
}
function Require-Source {
    param([string] $Relative)
    $expected = @(& git -C $root rev-parse ($ExpectedHead + ':' + $Relative))
    $observed = @(& git -C $root hash-object --no-filters -- (Join-Path $root $Relative))
    if ($LASTEXITCODE -ne 0 -or $expected.Count -ne 1 -or
        $observed.Count -ne 1 -or $expected[0] -cne $observed[0]) {
        throw 'Exact asphalt canary source differs from committed raw bytes.'
    }
}
function Write-ExclusiveJson {
    param([string] $Path, $Value)
    Assert-PlainPath $Path
    $bytes = [Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 36))
    if ($bytes.Length -gt 2MB) { throw 'Asphalt host receipt exceeds fixed size.' }
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
}

try {
    $root = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\', '/')
    $workspace = [IO.Path]::GetFullPath($env:GITHUB_WORKSPACE).TrimEnd('\', '/')
    $WorkspaceConfig = [IO.Path]::GetFullPath($WorkspaceConfig)
    Assert-PlainPath $root
    Assert-PlainPath $WorkspaceConfig
    if (-not [string]::Equals($WorkspaceConfig, 'D:\yacs\workspace.json',
        [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Expected the canonical YACS workspace configuration.'
    }
    if (-not $env:GITHUB_WORKSPACE -or
        $RunToken -cne ($env:GITHUB_RUN_ID + '-' + $env:GITHUB_RUN_ATTEMPT) -or
        -not [string]::Equals($root, (Join-Path $workspace ('rm-' + $RunToken)),
                             [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Canary must reuse only the exact owned isolated baseline checkout.'
    }
    $actualSha = @(& git -C $root rev-parse HEAD)
    if ($LASTEXITCODE -ne 0 -or $actualSha.Count -ne 1 -or $actualSha[0] -cne $ExpectedHead) {
        throw 'Asphalt source checkout HEAD differs from requested exact SHA.'
    }
    & git -C $root diff --quiet HEAD -- . ':(exclude)Content/**'
    if ($LASTEXITCODE -ne 0) { throw 'Native asphalt source/config differs from committed HEAD.' }
    foreach ($relative in @(
        'scripts/ue/Invoke-YacsRoadAsphaltNativeCanary.ps1',
        'scripts/ue/run_road_asphalt_native_canary.py',
        'scripts/ue/road_asphalt_source_preflight.py',
        'scripts/ue/road_asphalt_slot_canary.py',
        'scripts/ue/import_material_forge_variant.py'
    )) { Require-Source $relative }
    $evidence = Join-Path $root ('Saved/RuntimeProof/RoadMaterialBaseline/' + $RunToken)
    Assert-PlainPath $evidence
    $beforeHost = Get-Identity (Join-Path $evidence 'host-receipt.json') 2MB
    $baselineHost = Get-Content -LiteralPath $beforeHost.path -Raw | ConvertFrom-Json -AsHashtable -Depth 40
    $original = Get-Identity (Join-Path $evidence 'road-material-baseline.json') 2MB
    $baseline = Get-Content -LiteralPath $original.path -Raw | ConvertFrom-Json -AsHashtable -Depth 40
    if ($baselineHost.status -cne 'ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE' -or
        $baselineHost.reader_pass -isnot [bool] -or -not $baselineHost.reader_pass -or
        $baselineHost.owned_editor_exit_observed -isnot [bool] -or -not $baselineHost.owned_editor_exit_observed -or
        $baselineHost.owned_editor_exit_code -ne 0 -or
        $baselineHost.exact_sha -cne $ExpectedHead -or
        $baselineHost.run_token -cne $RunToken -or
        $baselineHost.proof_files.native_baseline.sha256 -cne $original.sha256 -or
        $baseline.status -cne 'ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE' -or
        $baseline.exact_sha -cne $ExpectedHead -or
        $baseline.pre_post_inventory_equal -isnot [bool] -or
        -not $baseline.pre_post_inventory_equal -or
        $baseline.saved_asset_bytes_unchanged -isnot [bool] -or
        -not $baseline.saved_asset_bytes_unchanged -or
        $baseline.native_inventory.road_count -ne 1 -or
        $baseline.native_inventory.support_count -ne 186 -or
        $baseline.native_inventory.landscape.component_count -ne 1024) {
        throw 'No accepted exact-SHA read-only native road baseline for transient asphalt.'
    }
    $receipt.baseline_receipt = $original
    $receipt.original_scene_read_pass = $true
    foreach ($row in $baselineHost.binary_provenance) {
        $actual = Get-Identity $row.copied_identity.path 512MB
        if ($actual.sha256 -cne $row.copied_identity.sha256 -or
            $actual.size_bytes -ne $row.copied_identity.size_bytes) {
            throw 'Cached Editor module closure changed after the successful baseline.'
        }
    }
    $python = 'D:\yacs\tool-cache\material-forge\python\Scripts\python.exe'
    $pythonSource = Get-Identity $python 128MB
    if ($pythonSource.sha256 -cne $baselineHost.proof_files.python_executable.sha256) {
        throw 'Pinned Python changed after the accepted native baseline.'
    }
    Require-IdleHost
    $preflightPath = Join-Path $evidence 'asphalt-source-preflight.json'
    if (Test-Path -LiteralPath $preflightPath) { throw 'Canary source receipt already exists.' }
    & $python -m scripts.ue.road_asphalt_source_preflight |
        Set-Content -LiteralPath $preflightPath -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw 'The original two-render asphalt proof is unavailable or untrusted.' }
    $sourceEvidence = Get-Identity $preflightPath 32KB
    $sourceGate = Get-Content -LiteralPath $preflightPath -Raw | ConvertFrom-Json -AsHashtable
    if ($sourceGate.status -cne 'PINNED_ROAD_ASPHALT_SOURCE_READY' -or
        $sourceGate.source_receipt_sha256 -cne '3626bf85da28d63908feb9d820171dc03d9d6cc444c8f799f7048f7a8052f79c' -or
        $sourceGate.graph_sha256 -cne '6b381516854c44dc4bdeb69b69fbb2b97ecf22c228db2c09204822d7f0bc0970' -or
        $sourceGate.native_material_verified -isnot [bool] -or
        $sourceGate.native_material_verified -or $sourceGate.verified_original_runs -ne 2) {
        throw 'Original asphalt CPU proof is not admitted for transient native use.'
    }
    $receipt.original_material_source = $sourceEvidence
    # Existing baseline already authenticated the same project, saved map,
    # official engine binary and compiled plugin/module closure.
    $engine = [string] $baselineHost.proof_files.editor_executable.path
    if (-not (Test-Path -LiteralPath $engine -PathType Leaf)) {
        throw 'The baseline-approved Unreal Editor executable disappeared.'
    }
    $script = Join-Path $root 'scripts/ue/run_road_asphalt_native_canary.py'
    $nativeArgs = @(('"' + (Join-Path $root 'YetAnotherCyclingSim.uproject') + '"'),
        '/Engine/Maps/Entry', '-DisablePlugins=ModelContextProtocol,Wingman,AndroidFileServer',
        '-Unattended', '-NoPause', '-NoSplash', '-NoSound', '-NoLiveCoding', '-NoP4',
        '-NullRHI', '-ScriptErrorsAreFatal',
        '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
        ('-ExecutePythonScript="' + $script + '"'),
        ('-AbsLog="' + (Join-Path $evidence 'asphalt-editor.log') + '"'))
    $receipt.status = 'NATIVE_ASPHALT_TRIAL_RUNNING'
    $ownedEditor = Start-Process -FilePath $engine -ArgumentList $nativeArgs -WorkingDirectory $root `
        -NoNewWindow -PassThru -RedirectStandardOutput (Join-Path $evidence 'asphalt-editor-stdout.log') `
        -RedirectStandardError (Join-Path $evidence 'asphalt-editor-stderr.log') -Environment @{
            YACS_ROAD_MATERIAL_EXPECTED_HEAD = $ExpectedHead
            YACS_ROAD_MATERIAL_PREPARATION_SHA256 = [string] $baselineHost.proof_files.session_preparation.sha256
            YACS_ROAD_MATERIAL_PROOF_ROOT = $evidence
            YACS_WORKSPACE_CONFIG = $WorkspaceConfig
            YACS_OWNER_HANDOFF = ''; PYTHONPATH = ''; PYTHONHOME = ''
            YACS_MCP_BOB_PROJECT_ROOT = ''; YACS_MCP_BOB_EXPECTED_HEAD = ''
        }
    $receipt.owned_editor_pid = $ownedEditor.Id
    $stopwatch = [Diagnostics.Stopwatch]::StartNew()
    while (-not $ownedEditor.WaitForExit(200)) {
        if ($stopwatch.Elapsed.TotalSeconds -ge 420) {
            throw 'The owned asphalt canary exceeded its strict 420-second deadline.'
        }
    }
    $ownedEditor.WaitForExit()
    $receipt.owned_editor_exit_observed = $true
    $receipt.owned_editor_exit_code = $ownedEditor.ExitCode
    if ($ownedEditor.ExitCode -ne 0) { throw 'Native material import/binding failed; inspect Editor logs.' }
    $native = Get-Identity (Join-Path $evidence 'road-asphalt-canary.json') 2MB
    $payload = Get-Content -LiteralPath $native.path -Raw | ConvertFrom-Json -AsHashtable -Depth 40
    if ($payload.schema_version -ne 1 -or $payload.issue -ne 364 -or
        $payload.exact_sha -cne $ExpectedHead -or
        $payload.status -cne 'ROAD_ASPHALT_TRANSIENT_CANARY_ROLLED_BACK' -or
        $payload.staging_sha256 -cne $baselineHost.proof_files.session_preparation.sha256 -or
        $payload.all_source_assets_unchanged -isnot [bool] -or
        -not $payload.all_source_assets_unchanged -or
        $payload.native_material_bind_and_rollback_verified -isnot [bool] -or
        -not $payload.native_material_bind_and_rollback_verified -or
        $payload.result.consumer_snapshot_restored -isnot [bool] -or
        -not $payload.result.consumer_snapshot_restored -or
        $payload.map_saved -isnot [bool] -or $payload.map_saved -or
        $payload.shader_gpu_compilation_verified -isnot [bool] -or
        $payload.shader_gpu_compilation_verified -or
        $payload.saved_consumer_verified -isnot [bool] -or
        $payload.saved_consumer_verified -or
        $payload.performance_pass -isnot [bool] -or $payload.performance_pass) {
        throw 'Native asphalt rollback/result claims differ from the fixed contract.'
    }
    $receipt.native_canary = $native
    $endBaseline = Get-Identity $original.path 2MB
    $endHost = Get-Identity $beforeHost.path 2MB
    $endSource = Get-Identity $sourceEvidence.path 32KB
    if ($endBaseline.sha256 -cne $original.sha256 -or
        $endHost.sha256 -cne $beforeHost.sha256 -or
        $endSource.sha256 -cne $sourceEvidence.sha256) {
        throw 'Original read-only proof or source bridge changed during the canary.'
    }
    Require-IdleHost
    $receipt.native_material_bind_and_rollback_verified = $true
    $receipt.status = 'ROAD_ASPHALT_TRANSIENT_HOST_PASS'
}
catch {
    $receipt.status = 'FAILED'
    $receipt.error = $_.Exception.Message
    throw
}
finally {
    if ($null -ne $ownedEditor) {
        try {
            if (-not $ownedEditor.HasExited) {
                $ownedEditor.Kill()
                if (-not $ownedEditor.WaitForExit(10000)) {
                    throw 'Owned asphalt Editor failed to exit after stop.'
                }
                $receipt.owned_editor_stopped_on_failure = $true
            }
            $receipt.owned_editor_exit_observed = $true
            $receipt.owned_editor_exit_code = $ownedEditor.ExitCode
        }
        catch { $receipt.secondary_errors += $_.Exception.Message }
        finally { $ownedEditor.Dispose() }
    }
    if ($evidence -and (Test-Path -LiteralPath $evidence -PathType Container)) {
        foreach ($name in @('asphalt-editor.log', 'asphalt-editor-stdout.log', 'asphalt-editor-stderr.log')) {
            $path = Join-Path $evidence $name
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                try { $receipt.logs[$name] = Get-ClosedLogIdentity $path }
                catch { $receipt.secondary_errors += $_.Exception.Message }
            }
            elseif ($receipt.owned_editor_pid) {
                $receipt.secondary_errors += ('Missing owned asphalt editor log: ' + $name)
            }
        }
        if ($receipt.secondary_errors.Count -gt 0) {
            $receipt.status = 'FAILED'
            $receipt.native_material_bind_and_rollback_verified = $false
            $receipt.error = 'Asphalt native teardown/log retention did not complete.'
        }
        try { Write-ExclusiveJson (Join-Path $evidence 'asphalt-host-receipt.json') $receipt }
        catch {
            if ($null -eq $receipt.error) { throw }
            Write-Warning 'Could not retain host receipt; original canary failure remains.'
        }
    }
}
if ($receipt.status -cne 'ROAD_ASPHALT_TRANSIENT_HOST_PASS' -or
    -not $receipt.native_material_bind_and_rollback_verified) {
    throw 'The transient asphalt native host contract did not pass.'
}
Write-Host 'ROAD_ASPHALT_TRANSIENT_HOST_PASS; no map save, GPU shader, visual or performance admission.'
