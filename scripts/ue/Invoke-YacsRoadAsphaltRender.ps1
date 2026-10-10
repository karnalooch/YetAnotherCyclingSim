#requires -Version 7.4
<# Technical GPU-only road review after exact-SHA saved/reloaded consumer PASS. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string] $ExpectedHead,
    [Parameter(Mandatory)][ValidatePattern('^[1-9][0-9]{0,19}-[1-9][0-9]{0,5}$')][string] $RunToken,
    [string] $WorkspaceConfig = 'D:\yacs\workspace.json',
    [string] $RepoRoot = (Join-Path $PSScriptRoot '../..')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'GPU asphalt review requires an owned Windows runner.' }
$root = $null
$proof = $null
$renderProcess = $null
$receipt = [ordered]@{
    schema_version = 1; issue = 364; exact_sha = $ExpectedHead
    run_token = $RunToken; status = 'PREFLIGHT_PENDING'
    authenticated_saved_and_reloaded = $false
    original_map_mutated = $false; geometry_mutated = $false
    native_lit_frames_retained = $false; verified_frame_count = 0
    gpu_shader_compilation_admitted = $false
    road_pixel_visibility_admitted = $false
    owner_visual_status = 'PENDING_FINAL_M3'
    performance_status = 'DEFERRED_AFTER_M3'; performance_pass = $false
    editor_pid = $null; editor_exit_code = $null
    editor_exit_observed = $false; stopped_on_failure = $false
    max_editor_seconds = 480
    program_executable = $null; source_receipts = [ordered]@{}
    evidence = [ordered]@{}; error = $null; secondary_errors = @()
}

function Assert-PlainPath {
    param([string] $Path)
    if (-not [IO.Path]::IsPathFullyQualified($Path) -or $Path -match '[\x00\r\n"]') {
        throw 'Road review paths must be absolute and plain.'
    }
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        try { $attrs = [IO.File]::GetAttributes($cursor) }
        catch [IO.FileNotFoundException] { $attrs = $null }
        catch [IO.DirectoryNotFoundException] { $attrs = $null }
        if ($null -ne $attrs -and ($attrs -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Road visual review cannot traverse symbolic/reparse paths.'
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}

function File-Identity {
    param([string] $Path, [long] $Limit = 64MB, [switch] $AllowEmpty)
    Assert-PlainPath $Path
    $before = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ($before.PSIsContainer -or $before.Length -gt $Limit -or
        ($before.Length -eq 0 -and -not $AllowEmpty)) {
        throw 'Road review expected a bounded regular file.'
    }
    $hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    $after = Get-Item -LiteralPath $Path -Force
    if ($before.Length -ne $after.Length -or
        $before.LastWriteTimeUtc.Ticks -ne $after.LastWriteTimeUtc.Ticks) {
        throw 'Road review source changed during hash read.'
    }
    return [ordered]@{ path = [IO.Path]::GetFullPath($Path)
        sha256 = $hash; size_bytes = $before.Length }
}

function Assert-Identity {
    param($Original, [long] $Limit = 64MB)
    $actual = File-Identity $Original.path $Limit
    if ($Original.sha256 -cne $actual.sha256 -or
        $Original.size_bytes -ne $actual.size_bytes) {
        throw 'Authenticated road evidence changed after GPU process.'
    }
}

function Log-Identity {
    param([string] $Path)
    for ($i = 1; $i -le 40; $i++) {
        try { return File-Identity $Path 64MB -AllowEmpty }
        catch {
            $inner = $_.Exception
            $locked = $false
            while ($inner) {
                if ($inner -is [IO.IOException] -and
                    $inner.HResult -in @(-2147024864, -2147024863)) {
                    $locked = $true
                    break
                }
                $inner = $inner.InnerException
            }
            if (-not $locked -or $i -eq 40) { throw }
            Start-Sleep -Milliseconds 250
        }
    }
}

function Read-PinnedJson {
    param([string] $Path)
    $identity = File-Identity $Path 2MB
    $value = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -AsHashtable -Depth 40
    Assert-Identity $identity 2MB
    if ($value -isnot [Collections.IDictionary]) {
        throw 'Road review pinned receipt is not a JSON object.'
    }
    return [ordered]@{ identity = $identity; value = $value }
}

function Write-ExclusiveReceipt {
    param([string] $Path, $Value)
    Assert-PlainPath $Path
    $raw = [Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 35))
    if ($raw.Length -gt 2MB) { throw 'GPU road host receipt exceeds fixed bound.' }
    $file = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $file.Write($raw, 0, $raw.Length) } finally { $file.Dispose() }
}

function Require-IdleHost {
    $state = & (Join-Path $root 'scripts/runner/Get-YacsUnrealHostState.ps1')
    if ($state.status -cne 'IDLE') {
        throw ('GPU road preview must yield to existing local Editor: ' + $state.status)
    }
}

function Require-ExactSource {
    param([string] $Relative)
    $committed = @(& git -C $root rev-parse ($ExpectedHead + ':' + $Relative))
    $working = @(& git -C $root hash-object --no-filters -- (Join-Path $root $Relative))
    if ($LASTEXITCODE -ne 0 -or $committed.Count -ne 1 -or
        $working.Count -ne 1 -or $committed[0] -cne $working[0]) {
        throw ('Road GPU executable differs from committed exact SHA: ' + $Relative)
    }
}

try {
    $root = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\', '/')
    Assert-PlainPath $root
    Assert-PlainPath $WorkspaceConfig
    if (-not $env:GITHUB_WORKSPACE -or
        $RunToken -cne ($env:GITHUB_RUN_ID + '-' + $env:GITHUB_RUN_ATTEMPT) -or
        -not [string]::Equals(
            $root,
            (Join-Path ([IO.Path]::GetFullPath($env:GITHUB_WORKSPACE).TrimEnd('\', '/')) ('rm-' + $RunToken)),
            [StringComparison]::OrdinalIgnoreCase
        ) -or
        -not [string]::Equals($WorkspaceConfig, 'D:\yacs\workspace.json',
                             [StringComparison]::OrdinalIgnoreCase)) {
        throw 'GPU road review must use exact shared-host isolated run checkout.'
    }
    $head = @(& git -C $root rev-parse HEAD)
    if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1 -or $head[0] -cne $ExpectedHead) {
        throw 'GPU road review exact Git HEAD differs.'
    }
    & git -C $root diff --quiet HEAD -- . ':(exclude)Content/**'
    if ($LASTEXITCODE -ne 0) { throw 'GPU road review tracked source is modified.' }
    foreach ($relative in @(
        'scripts/ue/Invoke-YacsRoadAsphaltRender.ps1',
        'scripts/ue/road_asphalt_gpu_review.py',
        'scripts/ue/road_asphalt_saved_consumer.py',
        'scripts/proof/sa_calobra_shoulder_contact.py',
        'docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv'
    )) { Require-ExactSource $relative }
    $proof = Join-Path $root ('Saved/RuntimeProof/RoadMaterialBaseline/' + $RunToken)
    Assert-PlainPath $proof
    $readHost = Read-PinnedJson (Join-Path $proof 'host-receipt.json')
    $savedHost = Read-PinnedJson (Join-Path $proof 'saved-road-host-receipt.json')
    $savedReceipt = Read-PinnedJson (Join-Path $proof 'road-asphalt-saved-prepared.json')
    $reopenReceipt = Read-PinnedJson (Join-Path $proof 'road-asphalt-saved-reloaded.json')
    if ($readHost.value.status -cne 'ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE' -or
        $readHost.value.exact_sha -cne $ExpectedHead -or
        $savedHost.value.status -cne 'ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_HOST_PASS' -or
        $savedHost.value.exact_sha -cne $ExpectedHead -or
        $savedHost.value.saved_derived_consumer -isnot [bool] -or
        -not $savedHost.value.saved_derived_consumer -or
        $savedHost.value.fresh_reload_verified -isnot [bool] -or
        -not $savedHost.value.fresh_reload_verified -or
        $savedHost.value.original_map_saved -isnot [bool] -or $savedHost.value.original_map_saved -or
        $savedHost.value.original_landscape_mutated -isnot [bool] -or
        $savedHost.value.original_landscape_mutated -or
        $savedHost.value.proof_files.saved_prepared.sha256 -cne $savedReceipt.identity.sha256 -or
        $savedHost.value.proof_files.fresh_reload.sha256 -cne $reopenReceipt.identity.sha256 -or
        $reopenReceipt.value.status -cne 'ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_PASS' -or
        $reopenReceipt.value.exact_sha -cne $ExpectedHead -or
        $reopenReceipt.value.road_material_reapplied -isnot [bool] -or
        $reopenReceipt.value.road_material_reapplied -or
        $reopenReceipt.value.performance_pass -isnot [bool] -or
        $reopenReceipt.value.performance_pass) {
        throw 'Native road source and saved/reloaded materials are not admitted.'
    }
    $receipt.source_receipts.baseline = $readHost.identity
    $receipt.source_receipts.saved_host = $savedHost.identity
    $receipt.source_receipts.saved_prepared = $savedReceipt.identity
    $receipt.source_receipts.fresh_reload = $reopenReceipt.identity
    $receipt.authenticated_saved_and_reloaded = $true
    $cmdPath = [string] $readHost.value.proof_files.editor_executable.path
    $cmdIdentity = File-Identity $cmdPath 1GB
    if ($cmdIdentity.sha256 -cne $readHost.value.proof_files.editor_executable.sha256 -or
        -not $cmdPath.EndsWith('UnrealEditor-Cmd.exe', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Cannot bind GPU Editor to the approved Unreal commandline engine.'
    }
    $gui = Join-Path (Split-Path -Parent $cmdPath) 'UnrealEditor.exe'
    $program = File-Identity $gui 1GB
    $receipt.program_executable = $program
    foreach ($row in $readHost.value.binary_provenance) {
        Assert-Identity $row.copied_identity 512MB
    }
    Require-IdleHost
    $script = Join-Path $root 'scripts/ue/road_asphalt_gpu_review.py'
    $arguments = @(
        ('"' + (Join-Path $root 'YetAnotherCyclingSim.uproject') + '"'),
        '/Engine/Maps/Entry',
        '-DisablePlugins=ModelContextProtocol,Wingman,AndroidFileServer',
        '-RenderOffscreen', '-norhithread',
        '-Unattended', '-NoPause', '-NoSplash', '-NoSound',
        '-NoLiveCoding', '-NoVSync', '-NoP4', '-ScriptErrorsAreFatal',
        '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
        ('-ExecutePythonScript="' + $script + '"'),
        ('-AbsLog="' + (Join-Path $proof 'road-asphalt-gpu-editor.log') + '"')
    )
    $stdout = Join-Path $proof 'road-asphalt-gpu-stdout.log'
    $stderr = Join-Path $proof 'road-asphalt-gpu-stderr.log'
    foreach ($path in @($stdout, $stderr)) {
        Assert-PlainPath $path
        if (Test-Path -LiteralPath $path) {
            throw 'GPU road review cannot overwrite existing process log.'
        }
    }
    $receipt.status = 'GPU_RENDER_RUNNING'
    $renderProcess = Start-Process -FilePath $gui -ArgumentList $arguments `
        -WorkingDirectory $root -PassThru -NoNewWindow `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
        -Environment @{
            YACS_ROAD_SAVED_RUN_TOKEN = $RunToken
            YACS_ROAD_MATERIAL_EXPECTED_HEAD = $ExpectedHead
            YACS_ROAD_MATERIAL_PREPARATION_SHA256 = [string] $readHost.value.proof_files.session_preparation.sha256
            YACS_WORKSPACE_CONFIG = $WorkspaceConfig
            YACS_OWNER_HANDOFF = ''; PYTHONPATH = ''; PYTHONHOME = ''
            YACS_MCP_BOB_PROJECT_ROOT = ''; YACS_MCP_BOB_EXPECTED_HEAD = ''
        }
    $receipt.editor_pid = $renderProcess.Id
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while (-not $renderProcess.WaitForExit(200)) {
        if ($watch.Elapsed.TotalSeconds -gt 480) {
            throw 'Owned GPU road review exceeded strict 480 second host deadline.'
        }
    }
    $renderProcess.WaitForExit()
    $receipt.editor_exit_observed = $true
    $receipt.editor_exit_code = $renderProcess.ExitCode
    $receipt.editor_seconds = $watch.Elapsed.TotalSeconds
    if ($renderProcess.ExitCode -ne 0) {
        throw 'GPU Unreal review exited nonzero; no render acceptance.'
    }
    $review = Read-PinnedJson (Join-Path $proof 'road-asphalt-lit-review.json')
    $data = $review.value
    if ($data.status -cne 'ROAD_ASPHALT_LIT_REVIEW_FRAMES_RETAINED' -or
        $data.schema_version -ne 1 -or $data.issue -ne 364 -or
        $data.exact_sha -cne $ExpectedHead -or
        $data.run_token -cne $RunToken -or
        $data.frame_count -ne 4 -or $data.expected_frame_count -ne 4 -or
        $data.camera_csv_sha256 -cne '15e0a2350c613bf52bfb1354192043ca0c6cd785493c59e7721305b67de099a3' -or
        $data.native_lit_frames_retained -isnot [bool] -or
        -not $data.native_lit_frames_retained -or
        $data.transient_dirty_package_audit.no_original_or_content_package_dirty -isnot [bool] -or
        -not $data.transient_dirty_package_audit.no_original_or_content_package_dirty -or
        $data.transient_dirty_package_audit.dirty_derived_package_saved -isnot [bool] -or
        $data.transient_dirty_package_audit.dirty_derived_package_saved -or
        $data.transient_dirty_package_audit.dirty_content_count -ne 0 -or
        $data.gpu_shutdown_quiescence_seconds -ne 10.0 -or
        $data.sources_and_saved_assets_unchanged -isnot [bool] -or
        -not $data.sources_and_saved_assets_unchanged -or
        $data.owner_visual_status -cne 'PENDING_FINAL_M3' -or
        $data.road_pixel_visibility_admitted -isnot [bool] -or
        $data.road_pixel_visibility_admitted -or
        $data.performance_pass -isnot [bool] -or $data.performance_pass -or
        $data.frames.Count -ne 4) {
        throw 'Native road-facing lit screenshot proof is incomplete or overstated.'
    }
    $expectedIds = @(
        'window-0112-forward-00001', 'window-0112-forward-00002',
        'window-0112-reverse-00001', 'window-0112-reverse-00002'
    )
    for ($i = 0; $i -lt 4; $i++) {
        $frame = $data.frames[$i]
        $expectedFile = 'road-asphalt-lit-review/frames/' + $expectedIds[$i] + '.png'
        if ($frame.frame_id -cne $expectedIds[$i] -or
            $frame.file -cne $expectedFile -or
            $frame.width -ne 1280 -or $frame.height -ne 720 -or
            $frame.unique_sampled_rgb -lt 12 -or
            $frame.visual_quality_reviewed -isnot [bool] -or $frame.visual_quality_reviewed -or
            $frame.render_mode -cne 'lit') {
            throw ('Road screenshot content/phase differs: ' + $expectedIds[$i])
        }
        $file = File-Identity (Join-Path $proof ($frame.file.Replace('/', '\'))) 16MB
        if ($file.sha256 -cne $frame.sha256 -or
            $file.size_bytes -ne $frame.size_bytes) {
            throw ('Native road screenshot hash changed: ' + $expectedIds[$i])
        }
        $receipt.evidence[$expectedIds[$i]] = $file
    }
    $receipt.evidence.render_receipt = $review.identity
    foreach ($original in @($readHost.identity, $savedHost.identity, $savedReceipt.identity,
                            $reopenReceipt.identity)) { Assert-Identity $original 2MB }
    Assert-Identity $program 1GB
    Require-IdleHost
    $receipt.verified_frame_count = 4
    $receipt.native_lit_frames_retained = $true
    $receipt.status = 'ROAD_ASPHALT_GPU_LIT_REVIEW_HOST_PASS'
}
catch {
    $receipt.status = 'FAILED'
    $receipt.error = $_.Exception.Message
    throw
}
finally {
    if ($null -ne $renderProcess) {
        try {
            if (-not $renderProcess.HasExited) {
                $renderProcess.Kill()
                if (-not $renderProcess.WaitForExit(10000)) {
                    throw 'Owned Unreal GPU review process failed to stop.'
                }
                $receipt.stopped_on_failure = $true
            }
            $receipt.editor_exit_observed = $true
            $receipt.editor_exit_code = $renderProcess.ExitCode
        }
        catch { $receipt.secondary_errors += $_.Exception.Message }
        finally { $renderProcess.Dispose() }
    }
    if ($proof -and (Test-Path -LiteralPath $proof -PathType Container)) {
        foreach ($name in @(
            'road-asphalt-gpu-editor.log',
            'road-asphalt-gpu-stdout.log',
            'road-asphalt-gpu-stderr.log'
        )) {
            $path = Join-Path $proof $name
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                try { $receipt.evidence[$name] = Log-Identity $path }
                catch { $receipt.secondary_errors += $_.Exception.Message }
            }
            elseif ($receipt.editor_pid) {
                $receipt.secondary_errors += ('Missing GPU Editor output log: ' + $name)
            }
        }
        if ($receipt.secondary_errors.Count -gt 0) {
            $receipt.status = 'FAILED'
            $receipt.native_lit_frames_retained = $false
            $receipt.error = 'GPU review process/log teardown did not complete.'
        }
        try {
            Write-ExclusiveReceipt (Join-Path $proof 'road-asphalt-gpu-host-receipt.json') $receipt
        }
        catch {
            if ($null -eq $receipt.error) { throw }
            Write-Warning 'Unable to retain GPU host receipt after a prior failure.'
        }
    }
}
if ($receipt.status -cne 'ROAD_ASPHALT_GPU_LIT_REVIEW_HOST_PASS' -or
    -not $receipt.native_lit_frames_retained) {
    throw 'Road GPU technical evidence failed the independent native host gate.'
}
Write-Host 'ROAD_ASPHALT_GPU_LIT_REVIEW_HOST_PASS; four lit road-facing frames, owner visual and FPS pending.'
