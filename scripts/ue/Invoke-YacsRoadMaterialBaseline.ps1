#requires -Version 7.4
<#
.SYNOPSIS
    Read the frozen #363 road/material consumer for #364 in one fresh Editor.
.DESCRIPTION
    Reuses only the active, verified normal Unreal cache with matching current
    compile/proof/environment fingerprints. No build, cache publication, cleanup,
    material authoring, save, MCP listener or rendering proof is performed.
    The existing accepted-consumer stager and fixed read-only native reader own
    asset authentication and the native pre/post inventory checks respectively.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string] $ExpectedHead,
    [Parameter(Mandatory)][ValidatePattern('^[1-9][0-9]{0,19}-[1-9][0-9]{0,5}$')][string] $RunToken,
    [string] $WorkspaceConfig = 'D:\yacs\workspace.json',
    [string] $RepoRoot = (Join-Path $PSScriptRoot '../..')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'The road material baseline requires the trusted Windows host.' }
$ownedEditor = $null
$ownedHelper = $null
$evidenceOwned = $false
$EvidenceRoot = $null
$savedWorkspaceConfig = [Environment]::GetEnvironmentVariable('YACS_WORKSPACE_CONFIG', 'Process')
$receipt = [ordered]@{
    schema_version = 1; issue = 364; exact_sha = $ExpectedHead; run_token = $RunToken
    status = 'PREPARATION_PENDING'; project_root = $null; proof_root = $null
    started_at_utc = [DateTime]::UtcNow.ToString('o'); ended_at_utc = $null
    source_fingerprints = $null; currentEnvironmentIdentity = $null; engine_identity = $null
    native_engine_build_id = $null; cache_provenance = $null; binary_provenance = @()
    helper_processes = @(); host_checks = @(); proof_files = [ordered]@{}
    owned_editor_pid = $null; owned_editor_exit_observed = $false; owned_editor_exit_code = $null
    owned_editor_stopped_on_failure = $false; editor_deadline_seconds = 420
    reader_pass = $false; read_only = $true; material_authoring_verified = $false
    persistent_world_mutation = $false; official_mcp_admitted = $false; render_verified = $false
    owner_visual_pass = $false; performance_pass = $false; performance_status = 'DEFERRED_AFTER_M3'
    error = $null; secondary_errors = @()
}

function Assert-BaselinePlainPath {
    param([Parameter(Mandatory)][string] $Path)
    if ($Path -match '[\x00\r\n"]' -or -not [IO.Path]::IsPathFullyQualified($Path)) {
        throw 'A baseline path must be an absolute plain path.'
    }
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        try { $attributes = [IO.File]::GetAttributes($cursor) }
        catch [IO.FileNotFoundException] { $attributes = $null }
        catch [IO.DirectoryNotFoundException] { $attributes = $null }
        if ($null -ne $attributes -and ($attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'The baseline refuses symlinks and junctions.'
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}
function Get-BaselineIdentity {
    param([Parameter(Mandatory)][string] $Path, [long] $Limit = 512MB, [switch] $AllowEmpty)
    Assert-BaselinePlainPath $Path
    $before = Get-Item -LiteralPath $Path -Force
    if ($before.PSIsContainer -or $before.Length -gt $Limit -or ($before.Length -eq 0 -and -not $AllowEmpty)) {
        throw 'A baseline input is not a bounded regular file.'
    }
    $length = $before.Length
    $ticks = $before.LastWriteTimeUtc.Ticks
    $stream = [IO.File]::OpenRead($Path)
    $hash = [Security.Cryptography.SHA256]::Create()
    try { $digest = [Convert]::ToHexString($hash.ComputeHash($stream)).ToLowerInvariant() }
    finally { $hash.Dispose(); $stream.Dispose() }
    $after = Get-Item -LiteralPath $Path -Force
    if ($after.Length -ne $length -or $after.LastWriteTimeUtc.Ticks -ne $ticks) {
        throw 'A baseline input changed during hashing.'
    }
    return [ordered]@{ path = [IO.Path]::GetFullPath($Path); size_bytes = $length; sha256 = $digest }
}
function Assert-BaselineIdentity {
    param($Identity, [long] $Limit = 512MB)
    $actual = Get-BaselineIdentity $Identity.path $Limit
    if ($actual.sha256 -cne $Identity.sha256 -or $actual.size_bytes -ne $Identity.size_bytes) {
        throw 'An authenticated baseline input changed.'
    }
}
function Read-BaselineJson {
    param([string] $Path, [long] $Limit = 2MB)
    $identity = Get-BaselineIdentity $Path $Limit
    $value = [IO.File]::ReadAllText($Path) | ConvertFrom-Json -AsHashtable -Depth 40
    Assert-BaselineIdentity $identity $Limit
    if ($value -isnot [Collections.IDictionary]) { throw 'A baseline JSON input must be an object.' }
    return [ordered]@{ identity = $identity; value = $value }
}
function Write-BaselineJsonExclusive {
    param([string] $Path, $Value)
    Assert-BaselinePlainPath $Path
    $bytes = [Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 40))
    if ($bytes.Length -gt 2MB) { throw 'Baseline host evidence exceeds its fixed bound.' }
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
}
function Copy-BaselineExclusive {
    param($Identity, [string] $Target, [long] $Limit = 512MB)
    Assert-BaselineIdentity $Identity $Limit
    Assert-BaselinePlainPath $Target
    if ([IO.File]::Exists($Target) -or [IO.Directory]::Exists($Target)) { throw 'The baseline cannot overwrite an existing output.' }
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Target))
    $inputStream = [IO.File]::OpenRead($Identity.path)
    try {
        $outputStream = [IO.File]::Open($Target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $inputStream.CopyTo($outputStream) } finally { $outputStream.Dispose() }
    } finally { $inputStream.Dispose() }
    $copied = Get-BaselineIdentity $Target $Limit
    if ($copied.sha256 -cne $Identity.sha256 -or $copied.size_bytes -ne $Identity.size_bytes) {
        throw 'An exclusive baseline copy differs from its verified source.'
    }
    Assert-BaselineIdentity $Identity $Limit
    return $copied
}
function Assert-BaselineIdleHost {
    $state = & (Join-Path $RepoRoot 'scripts/runner/Get-YacsUnrealHostState.ps1')
    $receipt.host_checks += [ordered]@{ status = $state.status; checked_at_utc = $state.checked_at_utc
        remote_ci_count = $state.remote_ci_count; local_or_unknown_count = $state.local_or_unknown_count }
    if ($state.status -cne 'IDLE') { throw 'The baseline yields to the existing Unreal host owner.' }
}
function Assert-BaselineSource {
    param([string] $Root, [string] $Head)
    $actual = @(& git -C $Root rev-parse HEAD)
    if ($LASTEXITCODE -ne 0 -or $actual.Count -ne 1 -or $actual[0] -cne $Head) { throw 'Baseline source HEAD differs.' }
    & git -C $Root diff --quiet HEAD -- . ':(exclude)Content/**'
    if ($LASTEXITCODE -ne 0) { throw 'Tracked baseline source/config bytes differ from HEAD.' }
    $extra = @(& git -C $Root ls-files --others -- Source ':(glob)Plugins/*/Source/**' ':(glob)Plugins/*/*.uplugin' Config Build '*.uproject')
    if ($LASTEXITCODE -ne 0 -or $extra.Count -ne 0) { throw 'Untracked native/tooling inputs cannot be certified.' }
    $extraScripts = @(& git -C $Root ls-files --others --exclude-standard -- scripts)
    if ($LASTEXITCODE -ne 0 -or $extraScripts.Count -ne 0) { throw 'Untracked script inputs cannot be certified.' }
}
function Invoke-BaselineHelper {
    param([string] $Executable, [string[]] $Arguments, [string] $Name, [int] $Seconds = 180)
    $stdout = Join-Path $EvidenceRoot ($Name + '-stdout.log')
    $stderr = Join-Path $EvidenceRoot ($Name + '-stderr.log')
    foreach ($path in @($stdout, $stderr)) {
        Assert-BaselinePlainPath $path
        if (Test-Path -LiteralPath $path) { throw 'An owned helper log already exists.' }
    }
    $script:ownedHelper = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $RepoRoot `
        -NoNewWindow -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
        -Environment @{ YACS_WORKSPACE_CONFIG = $WorkspaceConfig; GITHUB_OUTPUT = ''; PYTHONPATH = ''; PYTHONHOME = ''; YACS_OWNER_HANDOFF = '' }
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while (-not $script:ownedHelper.WaitForExit(200)) {
        if ($timer.Elapsed.TotalSeconds -ge $Seconds) { throw 'An owned baseline helper exceeded its fixed deadline.' }
    }
    $script:ownedHelper.WaitForExit()
    $exitCode = $script:ownedHelper.ExitCode
    $receipt.helper_processes += [ordered]@{ name = $Name; owned_pid = $script:ownedHelper.Id; exit_code = $exitCode
        deadline_seconds = $Seconds; elapsed_seconds = $timer.Elapsed.TotalSeconds
        stdout = Get-BaselineIdentity $stdout 16MB -AllowEmpty; stderr = Get-BaselineIdentity $stderr 16MB -AllowEmpty }
    $script:ownedHelper.Dispose()
    $script:ownedHelper = $null
    if ($exitCode -ne 0) { throw ('The fixed baseline helper failed: ' + $Name + '. See its retained logs.') }
    return $stdout
}
function Get-BaselineFingerprints {
    param([string] $Root, [string] $Name)
    $code = 'import json,sys; from scripts.ci.classify_changes import unreal_compile_fingerprint,unreal_proof_fingerprint; print(json.dumps(dict(compile=unreal_compile_fingerprint(sys.argv[1]),proof=unreal_proof_fingerprint(sys.argv[1]))))'
    $log = Invoke-BaselineHelper $python @('-c', ('"' + $code + '"'), ('"' + $Root + '"')) $Name 60
    $value = (Read-BaselineJson $log 64KB).value
    if ($value.compile -cnotmatch '^[0-9a-f]{64}$' -or $value.proof -cnotmatch '^[0-9a-f]{64}$') { throw 'Baseline source fingerprints are malformed.' }
    return $value
}
function Get-BaselineModuleClosure {
    param([string] $Root, [string] $Relative, [hashtable] $ExpectedModules, [string] $BuildId)
    $manifest = Read-BaselineJson (Join-Path $Root $Relative) 64KB
    $data = $manifest.value
    if ($data.BuildId -cne $BuildId -or $data.Modules -isnot [Collections.IDictionary] -or $data.Modules.Count -ne $ExpectedModules.Count) {
        throw 'A cached module manifest differs from the installed engine or fixed module closure.'
    }
    $rows = @([ordered]@{ relative = $Relative; source_identity = $manifest.identity })
    foreach ($name in @($ExpectedModules.Keys | Sort-Object)) {
        if ($data.Modules[$name] -cne $ExpectedModules[$name]) { throw 'A cached module maps to an unexpected DLL.' }
        $dllRelative = [IO.Path]::GetDirectoryName($Relative).Replace('\', '/') + '/' + $ExpectedModules[$name]
        $rows += [ordered]@{ relative = $dllRelative; source_identity = Get-BaselineIdentity (Join-Path $Root $dllRelative) }
    }
    return $rows
}

try {
    $RepoRoot = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\', '/')
    $WorkspaceConfig = [IO.Path]::GetFullPath($WorkspaceConfig)
    Assert-BaselinePlainPath $RepoRoot
    Assert-BaselinePlainPath $WorkspaceConfig
    if (-not [string]::Equals($WorkspaceConfig, 'D:\yacs\workspace.json', [StringComparison]::OrdinalIgnoreCase)) { throw 'The canonical workspace configuration is required.' }
    if (-not $env:GITHUB_WORKSPACE -or $RunToken -cne ($env:GITHUB_RUN_ID + '-' + $env:GITHUB_RUN_ATTEMPT)) { throw 'The exact owned Actions run/attempt is required.' }
    $workspace = [IO.Path]::GetFullPath($env:GITHUB_WORKSPACE).TrimEnd('\', '/')
    Assert-BaselinePlainPath $workspace
    if (-not $workspace.StartsWith('D:\yacs\runner\_work\', [StringComparison]::OrdinalIgnoreCase) `
        -or -not [string]::Equals($RepoRoot, (Join-Path $workspace ('rm-' + $RunToken)), [StringComparison]::OrdinalIgnoreCase) `
        -or -not [string]::Equals($RepoRoot, [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..')).TrimEnd('\', '/'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The baseline requires its own fresh runner checkout, separate from the live project and cache.'
    }
    Assert-BaselineSource $RepoRoot $ExpectedHead
    & (Join-Path $RepoRoot 'scripts/ci/Test-YacsCodeOnlyCheckout.ps1') -RepoRoot $RepoRoot
    $EvidenceRoot = Join-Path $RepoRoot ('Saved/RuntimeProof/RoadMaterialBaseline/' + $RunToken)
    Assert-BaselinePlainPath $EvidenceRoot
    if (Test-Path -LiteralPath $EvidenceRoot) { throw 'Baseline evidence already exists; preserve it.' }
    & git -C $RepoRoot check-ignore --quiet -- ($EvidenceRoot.Replace('\', '/') + '/host-receipt.json')
    if ($LASTEXITCODE -ne 0) { throw 'Baseline evidence must remain in ignored Saved output.' }
    [void][IO.Directory]::CreateDirectory($EvidenceRoot)
    $evidenceOwned = $true
    $receipt.project_root = $RepoRoot
    $receipt.proof_root = $EvidenceRoot
    if ($env:GITHUB_ENV) { ('YACS_ROAD_NATIVE_PROOF=' + $EvidenceRoot) | Out-File -LiteralPath $env:GITHUB_ENV -Append -Encoding utf8 }
    $receipt.proof_files.workspace_config = Get-BaselineIdentity $WorkspaceConfig 2MB
    $receipt.proof_files.executed_wrapper = Get-BaselineIdentity $PSCommandPath 256KB
    $reader = Join-Path $RepoRoot 'scripts/ue/read_road_material_baseline.py'
    $receipt.proof_files.executed_reader = Get-BaselineIdentity $reader 256KB
    foreach ($relative in @('scripts/ue/Invoke-YacsRoadMaterialBaseline.ps1', 'scripts/ue/read_road_material_baseline.py')) {
        $committed = @(& git -C $RepoRoot rev-parse ($ExpectedHead + ':' + $relative))
        if ($LASTEXITCODE -ne 0 -or $committed.Count -ne 1) { throw 'A fixed baseline source is absent from committed HEAD.' }
        $working = @(& git -C $RepoRoot hash-object --no-filters -- (Join-Path $RepoRoot $relative))
        if ($LASTEXITCODE -ne 0 -or $working.Count -ne 1 -or $working[0] -cne $committed[0]) { throw 'Executed baseline source differs from committed raw bytes.' }
    }
    $python = 'D:\yacs\tool-cache\material-forge\python\Scripts\python.exe'
    $receipt.proof_files.python_executable = Get-BaselineIdentity $python 128MB
    [Environment]::SetEnvironmentVariable('YACS_WORKSPACE_CONFIG', $WorkspaceConfig, 'Process')
    Assert-BaselineIdleHost
    $fingerprints = Get-BaselineFingerprints $RepoRoot 'current-fingerprints'
    $receipt.source_fingerprints = $fingerprints
    . (Join-Path $RepoRoot 'scripts/ci/Resolve-YacsUnrealBuildEnvironment.ps1')
    $environment = Resolve-YacsUnrealBuildEnvironment -ProjectPath (Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject')
    if (-not $environment -or $environment.Engine.Version -cne '5.8.2-56702186' -or $environment.Identity -cnotmatch '^[0-9a-f]{64}$') {
        throw 'Canonical Unreal 5.8.2 CL56702186/toolchain identity is required.'
    }
    $engine = $environment.Engine
    $receipt.currentEnvironmentIdentity = $environment.Identity
    $receipt.engine_identity = $engine.Identity
    $engineManifest = Read-BaselineJson (Join-Path $engine.Root 'Engine/Binaries/Win64/UnrealEditor.modules') 2MB
    if ($engineManifest.value.BuildId -isnot [string] -or -not $engineManifest.value.BuildId) { throw 'Installed engine module BuildId is missing.' }
    $receipt.native_engine_build_id = $engineManifest.value.BuildId
    $receipt.proof_files.engine_manifest = $engineManifest.identity
    $receipt.proof_files.editor_executable = Get-BaselineIdentity $engine.UnrealEditorCmdPath 1GB
    $pointer = Read-BaselineJson (Join-Path $workspace '_yacs-unreal-ci/active.json') 64KB
    if ($pointer.value.Count -ne 2 -or $pointer.value.schema_version -ne 1 -or $pointer.value.worktree -isnot [string] `
        -or $pointer.value.worktree -cnotmatch '^(_unreal-ci-warm|_unreal-build-[0-9]+-[0-9]+)$') { throw 'The active Unreal cache pointer is malformed; preserve all caches.' }
    $cacheRoot = Join-Path $workspace $pointer.value.worktree
    Assert-BaselinePlainPath $cacheRoot
    $cacheHeadOutput = @(& git -C $cacheRoot rev-parse HEAD)
    if ($LASTEXITCODE -ne 0 -or $cacheHeadOutput.Count -ne 1 -or $cacheHeadOutput[0] -cnotmatch '^[0-9a-f]{40}$') { throw 'Active cache HEAD is unavailable.' }
    $cacheHead = $cacheHeadOutput[0]
    Assert-BaselineSource $cacheRoot $cacheHead
    $state = Read-BaselineJson (Join-Path $cacheRoot 'Saved/BuildCache/UnrealCi/state.json') 64KB
    $s = $state.value
    $receipt.cache_provenance = [ordered]@{ root = $cacheRoot; actual_head = $cacheHead; original_state = $s
        pointer_identity = $pointer.identity; state_identity = $state.identity; resolver = $null }
    if ($s.SchemaVersion -ne 3 -or $s.CompilePassed -isnot [bool] -or -not $s.CompilePassed `
        -or $s.ProofPassed -isnot [bool] -or -not $s.ProofPassed -or $s.CompileHead -cnotmatch '^[0-9a-f]{40}$' `
        -or $s.ProofHead -cnotmatch '^[0-9a-f]{40}$' -or $s.ProofSummarySha256 -cnotmatch '^[0-9a-f]{64}$' `
        -or ($s.ProofSummarySizeBytes -isnot [int] -and $s.ProofSummarySizeBytes -isnot [long]) -or $s.ProofSummarySizeBytes -le 0 `
        -or $s.ProofSummarySizeBytes -gt 2MB -or $s.CompileFingerprint -cne $fingerprints.compile `
        -or $s.ProofFingerprint -cne $fingerprints.proof -or $s.EnvironmentIdentity -cne $environment.Identity `
        -or $s.EngineIdentity -cne $engine.Identity -or $s.ToolchainIdentity -cne $environment.Toolchain.Identity `
        -or -not [string]::Equals($s.EngineRoot, $engine.Root, [StringComparison]::OrdinalIgnoreCase) `
        -or $s.BuildCachePolicy -cne 'ubt-native-incremental-v1') {
        throw 'Active verified cache compile/proof/environment provenance differs; no build or cache invalidation is permitted.'
    }
    $cacheFingerprints = Get-BaselineFingerprints $cacheRoot 'cache-fingerprints'
    if ($cacheFingerprints.compile -cne $fingerprints.compile -or $cacheFingerprints.proof -cne $fingerprints.proof) { throw 'Active cache source fingerprints differ from its state/current source.' }
    $summaryPath = Join-Path $cacheRoot ('Saved/BuildCache/UnrealCi/proof-summary-' + $s.ProofSummarySha256 + '.json')
    $summary = Read-BaselineJson $summaryPath 2MB
    if ($summary.identity.sha256 -cne $s.ProofSummarySha256 -or
        $summary.identity.size_bytes -ne $s.ProofSummarySizeBytes) {
        throw 'Retained original Automation summary differs from its verified cache state.'
    }
    if ($summary.value.Head -cne $s.ProofHead -or $summary.value.ExpectedHead -cne $s.ProofHead `
        -or $summary.value.Failed -ne 0 -or $summary.value.Errors -ne 0 -or $summary.value.Discovered -le 0) { throw 'Active cache lacks its original green exact-head normal Automation summary.' }
    foreach ($row in @(@('cache-pointer.json', $pointer.identity), @('cache-state-original.json', $state.identity), @('cache-proof-summary.json', $summary.identity))) {
        $receipt.proof_files[$row[0]] = Copy-BaselineExclusive $row[1] (Join-Path $EvidenceRoot $row[0]) 2MB
    }
    $moduleRows = @(Get-BaselineModuleClosure $cacheRoot 'Binaries/Win64/UnrealEditor.modules' @{
        YetAnotherCyclingSim = 'UnrealEditor-YetAnotherCyclingSim.dll'; YetAnotherCyclingSimEditor = 'UnrealEditor-YetAnotherCyclingSimEditor.dll'
    } $engineManifest.value.BuildId)
    $moduleRows += @(Get-BaselineModuleClosure $cacheRoot 'Plugins/RoadForge/Binaries/Win64/UnrealEditor.modules' @{
        RoadForge = 'UnrealEditor-RoadForge.dll'
    } $engineManifest.value.BuildId)
    foreach ($row in $moduleRows) {
        Assert-BaselinePlainPath (Join-Path $RepoRoot $row.relative)
        if (Test-Path -LiteralPath (Join-Path $RepoRoot $row.relative)) { throw 'The fresh baseline checkout already contains a binary or module manifest.' }
    }
    # Resolve can invalidate state on a mismatch. All mismatch predicates above
    # are checked first, and only static/none with unchanged state is accepted.
    Assert-BaselineIdentity $pointer.identity 64KB
    Assert-BaselineIdentity $state.identity 64KB
    $pwsh = (Get-Command pwsh -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $resolverOutput = Join-Path $EvidenceRoot 'cache-resolver-output.txt'
    [void](Invoke-BaselineHelper $pwsh @('-NoProfile', '-File', ('"' + (Join-Path $RepoRoot 'scripts/ci/Resolve-YacsUnrealCiCache.ps1') + '"'),
        '-Action', 'Resolve', '-RepoRoot', ('"' + $cacheRoot + '"'), '-ExpectedHead', $cacheHead,
        '-ExpectedCompileFingerprint', $fingerprints.compile, '-ExpectedProofFingerprint', $fingerprints.proof,
        '-GithubOutput', ('"' + $resolverOutput + '"')) 'cache-resolver' 60)
    Assert-BaselineIdentity $state.identity 64KB
    Assert-BaselineIdentity $pointer.identity 64KB
    $resolution = Read-BaselineJson (Join-Path $cacheRoot 'Saved/RuntimeProof/CI/Unreal/cache_resolution.json') 64KB
    $r = $resolution.value
    if ($r.Mode -cne 'static' -or $r.CompileKind -cne 'none' -or $r.Head -cne $cacheHead -or $r.PreviousProofHead -cne $s.ProofHead `
        -or $r.PreviousStateInvalidated -isnot [bool] -or $r.PreviousStateInvalidated `
        -or $r.PurgeBuildCache -isnot [bool] -or $r.PurgeBuildCache -or $r.EnvironmentIdentity -cne $environment.Identity `
        -or $r.CompileFingerprint -cne $fingerprints.compile -or $r.ProofFingerprint -cne $fingerprints.proof) {
        throw 'Existing cache resolver did not authorize static reuse with unchanged state.'
    }
    $receipt.cache_provenance.resolver = $r
    $receipt.proof_files.cache_resolution = Copy-BaselineExclusive $resolution.identity (Join-Path $EvidenceRoot 'cache-resolution.json') 64KB
    foreach ($row in $moduleRows) {
        $target = Copy-BaselineExclusive $row.source_identity (Join-Path $RepoRoot $row.relative)
        $receipt.binary_provenance += [ordered]@{ relative = $row.relative; original_identity = $row.source_identity; copied_identity = $target
            original_CompileHead = $s.CompileHead; original_ProofHead = $s.ProofHead; native_engine_build_id = $engineManifest.value.BuildId }
    }
    $receipt.status = 'ACCEPTED_CONSUMER_STAGING'
    [void](Invoke-BaselineHelper $python @('-m', 'scripts.ci.official_mcp_bob_session', '--exact-sha', $ExpectedHead) 'accepted-consumer-stage' 180)
    $preparation = Read-BaselineJson (Join-Path $RepoRoot 'Saved/RuntimeProof/OfficialMcpBob/session-preparation.json') 2MB
    if ($preparation.value.exact_sha -cne $ExpectedHead -or $preparation.value.status -cne 'ACCEPTED_CONSUMER_BYTES_STAGED' `
        -or $preparation.value.native_runtime_verified -isnot [bool] -or $preparation.value.native_runtime_verified `
        -or $preparation.value.official_mcp_admitted -isnot [bool] -or $preparation.value.official_mcp_admitted) { throw 'Accepted-consumer staging did not produce an exact read-only preparation receipt.' }
    $receipt.proof_files.session_preparation = Copy-BaselineExclusive $preparation.identity (Join-Path $EvidenceRoot 'session-preparation.json') 2MB
    Assert-BaselineSource $RepoRoot $ExpectedHead
    Assert-BaselineIdleHost
    foreach ($row in $receipt.binary_provenance) { Assert-BaselineIdentity $row.copied_identity; Assert-BaselineIdentity $row.original_identity }
    foreach ($id in @($pointer.identity, $state.identity, $receipt.proof_files.workspace_config)) { Assert-BaselineIdentity $id 2MB }
    Assert-BaselineIdentity $receipt.proof_files.editor_executable 1GB
    $editorArguments = @(('"' + (Join-Path $RepoRoot 'YetAnotherCyclingSim.uproject') + '"'), '/Engine/Maps/Entry',
        '-DisablePlugins=ModelContextProtocol,Wingman,AndroidFileServer', '-unattended', '-NoSplash', '-NoSound', '-NoLiveCoding',
        '-NullRHI', '-ScriptErrorsAreFatal', '-NoPause', '-NoP4',
        '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
        ('-ExecutePythonScript="' + $reader + '"'), ('-abslog="' + (Join-Path $EvidenceRoot 'owned-editor.log') + '"'))
    $receipt.editor_arguments = $editorArguments
    $receipt.status = 'OWNED_EDITOR_READING'
    $receipt.editor_started_at_utc = [DateTime]::UtcNow.ToString('o')
    $ownedEditor = Start-Process -FilePath $engine.UnrealEditorCmdPath -ArgumentList $editorArguments -WorkingDirectory $RepoRoot `
        -NoNewWindow -PassThru -RedirectStandardOutput (Join-Path $EvidenceRoot 'owned-editor-stdout.log') `
        -RedirectStandardError (Join-Path $EvidenceRoot 'owned-editor-stderr.log') -Environment @{
            YACS_ROAD_MATERIAL_EXPECTED_HEAD = $ExpectedHead; YACS_ROAD_MATERIAL_PREPARATION_SHA256 = $preparation.identity.sha256
            YACS_ROAD_MATERIAL_PROOF_ROOT = $EvidenceRoot; YACS_WORKSPACE_CONFIG = $WorkspaceConfig
            YACS_OWNER_HANDOFF = ''; PYTHONPATH = ''; PYTHONHOME = ''; YACS_MCP_BOB_PROJECT_ROOT = ''; YACS_MCP_BOB_EXPECTED_HEAD = ''
        }
    $receipt.owned_editor_pid = $ownedEditor.Id
    $editorTimer = [Diagnostics.Stopwatch]::StartNew()
    $heartbeat = 30
    while (-not $ownedEditor.WaitForExit(200)) {
        if ($editorTimer.Elapsed.TotalSeconds -ge 420) { throw 'The owned baseline Editor exceeded its fixed 420 second deadline.' }
        if ($editorTimer.Elapsed.TotalSeconds -ge $heartbeat) {
            Write-Host ('Road material baseline heartbeat: ownedPID={0}, elapsed={1:N0}s.' -f $ownedEditor.Id, $editorTimer.Elapsed.TotalSeconds)
            $heartbeat += 30
        }
    }
    $ownedEditor.WaitForExit()
    $receipt.owned_editor_exit_observed = $true
    $receipt.owned_editor_exit_code = $ownedEditor.ExitCode
    $receipt.editor_elapsed_seconds = $editorTimer.Elapsed.TotalSeconds
    if ($ownedEditor.ExitCode -ne 0) { throw 'The fixed native road material reader failed; retain its logs.' }
    $baseline = Read-BaselineJson (Join-Path $EvidenceRoot 'road-material-baseline.json') 2MB
    $b = $baseline.value
    if ($b.schema_version -ne 1 -or $b.issue -ne 364 -or $b.status -cne 'ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE' `
        -or $b.exact_sha -cne $ExpectedHead -or $b.reader_source_sha256 -isnot [Collections.IDictionary] `
        -or $b.reader_source_sha256['scripts/ue/read_road_material_baseline.py'] -cne $receipt.proof_files.executed_reader.sha256 `
        -or -not [string]::Equals($b.project, $RepoRoot, [StringComparison]::OrdinalIgnoreCase) `
        -or -not $b.engine_version.StartsWith('5.8.2-56702186') -or $b.staging_receipt.sha256 -cne $preparation.identity.sha256 `
        -or $b.staging_receipt.size_bytes -ne $preparation.identity.size_bytes) { throw 'Native baseline receipt does not belong to this exact owned read.' }
    foreach ($flag in @('read_only', 'pre_post_inventory_equal', 'saved_asset_bytes_unchanged')) {
        if ($b[$flag] -isnot [bool] -or -not $b[$flag]) { throw 'The native reader did not preserve its read-only baseline contract.' }
    }
    foreach ($flag in @('material_authoring_verified', 'persistent_world_mutation', 'official_mcp_admitted', 'performance_pass', 'owner_visual_pass', 'full_mesh_geometry_hash_verified')) {
        if ($b[$flag] -isnot [bool] -or $b[$flag]) { throw 'A read-only baseline claimed unauthorized material/world/visual/performance verification.' }
    }
    if ($b.performance_status -cne 'DEFERRED_AFTER_M3' -or $null -ne $b.geometry_normal_uv_hash) { throw 'Baseline proof scope differs from the M3 contract.' }
    $receipt.proof_files.native_baseline = $baseline.identity
    Assert-BaselineSource $RepoRoot $ExpectedHead
    foreach ($row in $receipt.binary_provenance) { Assert-BaselineIdentity $row.original_identity; Assert-BaselineIdentity $row.copied_identity }
    foreach ($id in @($pointer.identity, $state.identity, $engineManifest.identity, $preparation.identity, $receipt.proof_files.workspace_config,
        $receipt.proof_files.executed_wrapper, $receipt.proof_files.executed_reader)) { Assert-BaselineIdentity $id 2MB }
    Assert-BaselineSource $cacheRoot $cacheHead
    $finalFingerprints = Get-BaselineFingerprints $RepoRoot 'final-current-fingerprints'
    if ($finalFingerprints.compile -cne $fingerprints.compile -or $finalFingerprints.proof -cne $fingerprints.proof) { throw 'Native read changed current compile/proof inputs.' }
    Assert-BaselineIdleHost
    $receipt.reader_pass = $true
    $receipt.status = 'ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE'
} catch {
    $receipt.status = 'FAILED'
    $receipt.error = $_.Exception.Message
    throw
} finally {
    foreach ($process in @($ownedHelper, $ownedEditor)) {
        if ($null -eq $process) { continue }
        try {
            if (-not $process.HasExited) {
                if ($process -eq $ownedHelper) { $process.Kill($true) }
                else { $process.Kill() }
                if (-not $process.WaitForExit(10000)) { throw 'The owned baseline process did not exit after its bounded stop.' }
                if ($process -eq $ownedEditor) { $receipt.owned_editor_stopped_on_failure = $true }
            }
            $process.WaitForExit()
            if ($process -eq $ownedEditor) {
                $receipt.owned_editor_exit_observed = $true
                $receipt.owned_editor_exit_code = $process.ExitCode
            }
        } catch { $receipt.secondary_errors += $_.Exception.Message }
        finally { $process.Dispose() }
    }
    [Environment]::SetEnvironmentVariable('YACS_WORKSPACE_CONFIG', $savedWorkspaceConfig, 'Process')
    if ($evidenceOwned) {
        foreach ($name in @('owned-editor.log', 'owned-editor-stdout.log', 'owned-editor-stderr.log')) {
            $path = Join-Path $EvidenceRoot $name
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                try { $receipt.proof_files[$name] = Get-BaselineIdentity $path 64MB -AllowEmpty }
                catch { $receipt.secondary_errors += $_.Exception.Message }
            }
        }
        if ($receipt.secondary_errors.Count -gt 0 -and $receipt.status -cne 'FAILED') {
            $receipt.status = 'FAILED'
            $receipt.reader_pass = $false
            $receipt.error = 'Owned baseline teardown/evidence retention failed.'
        }
        $receipt.ended_at_utc = [DateTime]::UtcNow.ToString('o')
        try { Write-BaselineJsonExclusive (Join-Path $EvidenceRoot 'host-receipt.json') $receipt }
        catch {
            if (-not $receipt.error) { throw }
            Write-Warning 'Failed to retain the host receipt; the original baseline failure remains the primary error.'
        }
    }
}
if ($receipt.status -cne 'ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE' -or -not $receipt.reader_pass) { throw 'The read-only road material baseline did not complete.' }
Write-Host 'ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE; no material authoring, rendering or performance admission.'
