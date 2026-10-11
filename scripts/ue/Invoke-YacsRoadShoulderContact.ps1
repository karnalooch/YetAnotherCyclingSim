#requires -Version 7.4
<# Read-only Issue459 owner isolation after the same run's material GPU PASS. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string] $ExpectedHead,
    [Parameter(Mandatory)][ValidatePattern('^[1-9][0-9]{0,19}-[1-9][0-9]{0,5}$')][string] $RunToken,
    [ValidateSet('window0112', 'hairpin0081')][string] $Target = 'window0112',
    [string] $WorkspaceConfig = 'D:\yacs\workspace.json',
    [string] $RepoRoot = (Join-Path $PSScriptRoot '../..')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Shoulder contact requires the owned Windows native lane.' }
$root = $proof = $diagnostic = $inputPin = $python = $helperPin = $null
$nativeComplete = $false
$diagnosticName = if ($Target -ceq 'hairpin0081') { 'shoulder-contact-0081' } else { 'shoulder-contact' }
$hostReceiptName = $diagnosticName + '-host-receipt.json'
$frameCount = if ($Target -ceq 'hairpin0081') { 6 } else { 16 }
$receipt = [ordered]@{
    schema_version = 1; issue = 459; exact_sha = $ExpectedHead; run_token = $RunToken
    diagnostic_target = $Target
    status = 'PREFLIGHT_PENDING'; read_only = $true; geometry_mutated = $false
    original_map_mutated = $false; source_inputs_unchanged = $false
    restored_visibility_verified = $false; verified_frame_count = 0
    rendered_owner = 'PENDING_PAIRED_VISUAL_REVIEW'; owner_visual_pass = $false
    performance_status = 'DEFERRED_AFTER_M3'; performance_pass = $false
    editor_pid = $null; editor_exit_observed = $false; editor_exit_code = $null
    stopped_on_failure = $false; max_editor_seconds = 1020
    processes = @(); evidence = [ordered]@{}; error = $null; secondary_errors = @()
}

function Assert-PlainPath {
    param([string] $Path)
    if (-not [IO.Path]::IsPathFullyQualified($Path) -or $Path -match '[\x00\r\n"]') {
        throw 'Diagnostic paths must be absolute and plain.'
    }
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        try { $attrs = [IO.File]::GetAttributes($cursor) }
        catch [IO.FileNotFoundException] { $attrs = $null }
        catch [IO.DirectoryNotFoundException] { $attrs = $null }
        if ($null -ne $attrs -and ($attrs -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Diagnostic paths cannot traverse symbolic/reparse points.'
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}
function File-Identity {
    param([string] $Path, [long] $Limit = 64MB, [switch] $AllowEmpty)
    Assert-PlainPath $Path
    $before = Get-Item -LiteralPath $Path -Force
    if ($before.PSIsContainer -or $before.Length -gt $Limit -or
        ($before.Length -eq 0 -and -not $AllowEmpty)) { throw 'Unbounded diagnostic input.' }
    $hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    $after = Get-Item -LiteralPath $Path -Force
    if ($before.Length -ne $after.Length -or
        $before.LastWriteTimeUtc.Ticks -ne $after.LastWriteTimeUtc.Ticks) {
        throw 'Diagnostic input changed while reading.'
    }
    return @{ path = [IO.Path]::GetFullPath($Path); sha256 = $hash; size_bytes = $before.Length }
}
function Assert-Identity {
    param($Pin, [long] $Limit = 64MB)
    $actual = File-Identity $Pin.path $Limit
    if ($actual.sha256 -cne $Pin.sha256 -or $actual.size_bytes -ne $Pin.size_bytes) {
        throw 'Pinned diagnostic input changed.'
    }
}
function Log-Identity {
    param([string] $Path)
    for ($attempt = 1; $attempt -le 40; $attempt++) {
        try { return File-Identity $Path 64MB -AllowEmpty }
        catch {
            $errorObject = $_.Exception
            $sharing = $false
            while ($errorObject) {
                if ($errorObject -is [IO.IOException] -and $errorObject.HResult -in @(-2147024864, -2147024863)) {
                    $sharing = $true; break
                }
                $errorObject = $errorObject.InnerException
            }
            if (-not $sharing -or $attempt -eq 40) { throw }
            Start-Sleep -Milliseconds 250
        }
    }
}
function Read-PinnedJson {
    param([string] $Path)
    $pin = File-Identity $Path 2MB
    $value = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -AsHashtable -Depth 40
    Assert-Identity $pin 2MB
    if ($value -isnot [Collections.IDictionary]) { throw 'Expected a diagnostic JSON object.' }
    return @{ identity = $pin; value = $value }
}
function Write-Exclusive {
    param([string] $Path, [string] $Text)
    Assert-PlainPath $Path
    $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
    if ($bytes.Length -gt 2MB) { throw 'Diagnostic metadata exceeds its fixed bound.' }
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
}
function Require-ExactSource {
    & git -C $root diff --quiet HEAD -- . ':(exclude)Content/**'
    if ($LASTEXITCODE -ne 0) { throw 'Diagnostic tracked source differs from exact HEAD.' }
    foreach ($relative in @(
        'scripts/ue/Invoke-YacsRoadShoulderContact.ps1',
        'scripts/ue/capture_sa_calobra_shoulder_contact.py',
        'scripts/ue/sa_calobra_tpp_survey_capture.py',
        'scripts/ue/prepare_landscape_capture.py',
        'scripts/proof/sa_calobra_shoulder_contact.py',
        'scripts/proof/sa_calobra_tpp_survey.py',
        'scripts/ue/read_road_material_baseline.py',
        'scripts/ue/road_shoulder_sources.py',
        'scripts/ci/official_mcp_bob_session.py',
        'scripts/ci/Resolve-YacsUnrealEngine.ps1',
        'scripts/runner/Get-YacsUnrealHostState.ps1',
        'scripts/manage_local_workspace.py',
        'worldgen/terrain/benchmarks/sa_calobra/world_data/frozen_road_recipe_2026-10-04.json',
        'docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv'
    )) {
        $committed = @(& git -C $root rev-parse ($ExpectedHead + ':' + $relative))
        if ($LASTEXITCODE -ne 0 -or $committed.Count -ne 1) { throw 'Missing exact diagnostic source.' }
        $actual = @(& git -C $root hash-object --no-filters -- (Join-Path $root $relative))
        if ($LASTEXITCODE -ne 0 -or $actual.Count -ne 1 -or $committed[0] -cne $actual[0]) {
            throw ('Diagnostic source bytes differ from committed HEAD: ' + $relative)
        }
    }
}
function Require-IdleHost {
    $state = & (Join-Path $root 'scripts/runner/Get-YacsUnrealHostState.ps1')
    if ($state.status -cne 'IDLE') { throw ('Diagnostic yields to existing Unreal work: ' + $state.status) }
}
function Invoke-OwnedProcess {
    param([string] $Name, [string] $Program, [string[]] $Arguments, [int] $Seconds,
          [hashtable] $Environment = @{})
    $record = [ordered]@{ name = $Name; pid = $null; exit_observed = $false
        exit_code = $null; stopped_on_failure = $false; deadline_seconds = $Seconds }
    $receipt.processes += $record
    $stdout = Join-Path $diagnostic ($Name + '-stdout.log')
    $stderr = Join-Path $diagnostic ($Name + '-stderr.log')
    foreach ($path in @($stdout, $stderr)) {
        Assert-PlainPath $path
        if (Test-Path -LiteralPath $path) { throw 'Diagnostic process logs already exist.' }
    }
    $owned = $null
    try {
        $owned = Start-Process -FilePath $Program -ArgumentList $Arguments -WorkingDirectory $root `
            -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
            -Environment $Environment
        $record.pid = $owned.Id
        if ($Name -ceq 'owned-editor') { $receipt.editor_pid = $owned.Id }
        $watch = [Diagnostics.Stopwatch]::StartNew()
        while (-not $owned.WaitForExit(200)) {
            if ($watch.Elapsed.TotalSeconds -gt $Seconds) { throw ('Owned diagnostic deadline exceeded: ' + $Name) }
        }
        $owned.WaitForExit() # Drain redirected process handles before observing actual exit.
        $record.exit_observed = $true; $record.exit_code = $owned.ExitCode
        $record.elapsed_seconds = $watch.Elapsed.TotalSeconds
        if ($owned.ExitCode -ne 0) { throw ('Owned diagnostic process exited nonzero: ' + $Name) }
    }
    finally {
        if ($null -ne $owned) {
            try {
                if (-not $owned.HasExited) {
                    $record.stopped_on_failure = $true
                    $owned.Kill() # Only this Process object; never touch other sessions.
                    if (-not $owned.WaitForExit(10000)) { throw 'Owned diagnostic process did not stop.' }
                }
                $owned.WaitForExit()
                $record.exit_observed = $true; $record.exit_code = $owned.ExitCode
            }
            finally {
                if ($Name -ceq 'owned-editor') {
                    $receipt.editor_exit_observed = $record.exit_observed
                    $receipt.editor_exit_code = $record.exit_code
                    $receipt.stopped_on_failure = $record.stopped_on_failure
                }
                $owned.Dispose()
            }
        }
    }
}

# The existing staged-source reader, frozen recipe and original restoration/PNG
# verifier are reused here. This helper is retained with the proof and hash-pinned
# before either invocation; no archived consumer or geometry authoring executes.
$bridgeCode = @'
import json, re, sys
from pathlib import Path

MIB = 1024 * 1024
HEADERS = {
    "Runtime/Landscape/Classes/LandscapeComponent.h": ["SectionBaseX", "SectionBaseY", "ComponentSizeQuads", "ForcedLOD", "LODBias"],
    "Runtime/Engine/Classes/Components/SceneComponent.h": ["SetVisibility", "bVisible"],
    "Runtime/Engine/Classes/Components/PrimitiveComponent.h": ["bCastHiddenShadow"],
    "Runtime/Engine/Classes/Kismet/KismetSystemLibrary.h": ["GetComponentBounds"],
    "Runtime/GeometryFramework/Public/UDynamicMesh.h": ["GetMeshRef"],
    "Runtime/GeometryCore/Public/DynamicMesh/DynamicMesh3.h": ["TriangleIndicesItr", "IsTriangle", "GetTriangle", "GetVertex", "VertexCount", "TriangleCount"],
}
BINARY_FILES = (
    "Binaries/Win64/UnrealEditor.modules",
    "Binaries/Win64/UnrealEditor-YetAnotherCyclingSim.dll",
    "Binaries/Win64/UnrealEditor-YetAnotherCyclingSimEditor.dll",
    "Plugins/RoadForge/Binaries/Win64/UnrealEditor.modules",
    "Plugins/RoadForge/Binaries/Win64/UnrealEditor-RoadForge.dll",
)

def require(ok, message):
    if not ok:
        raise ValueError(message)

def flags(value, expected):
    for key, wanted in expected.items():
        require(value.get(key) is wanted, "Incompatible diagnostic predecessor flag: " + key)

def prior_contract(base, gpu, head, token):
    for value, status in ((base, "ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE"),
                          (gpu, "ROAD_ASPHALT_GPU_LIT_REVIEW_HOST_PASS")):
        require(value.get("schema_version") == 1 and value.get("issue") == 364
                and value.get("exact_sha") == head and value.get("run_token") == token
                and value.get("status") == status and value.get("error") is None
                and value.get("secondary_errors") == [], "Missing exact-run baseline/material GPU PASS")
    flags(base, {"reader_pass": True, "read_only": True, "persistent_world_mutation": False,
                 "owned_editor_exit_observed": True, "owned_editor_stopped_on_failure": False})
    flags(gpu, {"authenticated_saved_and_reloaded": True, "native_lit_frames_retained": True,
                "shoulder_network_material_ids_verified": True, "original_map_mutated": False,
                "geometry_mutated": False, "editor_exit_observed": True, "stopped_on_failure": False})
    require(type(base.get("owned_editor_exit_code")) is int and base["owned_editor_exit_code"] == 0
            and type(gpu.get("editor_exit_code")) is int and gpu["editor_exit_code"] == 0,
            "Predecessor must have a real observed exit zero")
    require(type(gpu.get("verified_frame_count")) is int and gpu["verified_frame_count"] > 0
            and gpu["verified_frame_count"] == gpu.get("expected_frame_count"),
            "Incomplete prior material GPU frame inventory")

def restored_window0112(prior, head, token):
    require(prior.get("status") == "SHOULDER_CONTACT_READ_ONLY_HOST_PASS"
            and prior.get("exact_sha") == head and prior.get("run_token") == token
            and prior.get("diagnostic_target", "window0112") == "window0112"
            and prior.get("verified_frame_count") == 16
            and type(prior.get("editor_exit_code")) is int and prior["editor_exit_code"] == 0
            and prior.get("error") is None and prior.get("secondary_errors") == [],
            "Hairpin isolation requires this run's restored window0112 diagnostic PASS")
    flags(prior, {"read_only": True, "geometry_mutated": False, "original_map_mutated": False,
                  "source_inputs_unchanged": True, "restored_visibility_verified": True,
                  "editor_exit_observed": True, "stopped_on_failure": False})

def identity(path, limit=512 * MIB):
    path = Path(path)
    require(path.is_absolute(), "Diagnostic input must be absolute")
    return dict(path=str(path), **session._identity(path, limit))

def same_pin(actual, expected):
    require(isinstance(expected, dict) and type(expected.get("size_bytes")) is int
            and actual["sha256"] == expected.get("sha256")
            and actual["size_bytes"] == expected["size_bytes"], "Diagnostic source pin differs")
    if "path" in expected:
        require(Path(actual["path"]) == Path(expected["path"]), "Diagnostic pin belongs to another path")

def read(path, expected=None, limit=2 * MIB):
    actual = identity(path, limit)
    if expected is not None:
        same_pin(actual, expected)
    value = session._read_json(Path(path), (actual["sha256"], actual["size_bytes"]), limit=limit)
    return value, actual

def write_once(path, value):
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    require(len(raw) <= 2 * MIB, "Diagnostic metadata exceeds fixed bound")
    session._safe_path(path.parent, path.name)
    with path.open("xb") as stream:
        stream.write(raw)
    return identity(path, 2 * MIB)

def primary_api(engine, head):
    version, version_pin = read(engine / "Engine/Build/Build.version")
    version_text = "{MajorVersion}.{MinorVersion}.{PatchVersion}-{Changelist}".format(**version)
    require(version_text == "5.8.2-56702186", "Installed diagnostic API version differs")
    rows, pins = [], [version_pin]
    for relative, symbols in HEADERS.items():
        path = engine / "Engine/Source" / relative
        actual = identity(path, 2 * MIB)
        text = path.read_text(encoding="utf-8-sig")
        same_pin(identity(path, 2 * MIB), actual)
        require(all(re.search(r"\b" + re.escape(symbol) + r"\b", text) for symbol in symbols),
                "Installed primary API symbol missing: " + relative)
        rows.append(dict(header="Engine/Source/" + relative, verified_symbols=symbols,
                         sha256=actual["sha256"], size_bytes=actual["size_bytes"]))
        pins.append(actual)
    entry = identity(engine / "Engine/Content/Maps/Entry.umap", 64 * MIB)
    pins.append(entry)
    return dict(status="INSTALLED_PRIMARY_API_SOURCE_VERIFIED", exact_sha=head,
                engine_version=version_text, build_version_sha256=version_pin["sha256"],
                headers=rows, startup_map="/Engine/Maps/Entry", startup_map_sha256=entry["sha256"]), pins

def retain_capture(source, destination, plan):
    allowed = {"shoulder-contact.json": 2 * MIB, "capture/survey.json": 2 * MIB}
    if plan.get("diagnostic_target") == "hairpin0081":
        allowed["source-cut-manifest.json"] = 32 * 1024
    for row in plan["frames"]:
        allowed["capture/frames/" + row["frame_id"] + ".png"] = 16 * MIB
        allowed["capture/readiness/" + row["frame_id"] + "/capture-readiness.json"] = 8 * MIB
    copied = []
    for relative, limit in allowed.items():
        path = session._safe_path(source, relative)
        if not path.exists():
            continue # Preserve bounded partial evidence on a failed native run.
        before = identity(path, limit)
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        require(len(raw) <= limit, "Diagnostic output grew beyond its bound")
        same_pin(identity(path, limit), before)
        target = session._safe_path(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
        actual = identity(target, limit)
        same_pin(actual, {key: before[key] for key in ("sha256", "size_bytes")})
        copied.append(dict(file=relative, sha256=actual["sha256"], size_bytes=actual["size_bytes"]))
    write_once(destination / "retained-files.json", {"original_root": str(source), "files": copied})
    return copied

def verify_readiness(root):
    survey, _ = read(root / "capture/survey.json")
    for row in survey["frames"]:
        relative = "readiness/" + row["frame_id"] + "/capture-readiness.json"
        stamp = row["native_readiness"]
        require(stamp.get("receipt") == relative, "Readiness receipt escaped its named frame")
        value, pin = read(root / "capture" / relative, limit=8 * MIB)
        require(pin["sha256"] == stamp.get("sha256")
                and value.get("status") == "NATIVE_LOADING_AND_MIPS_READY", "Native readiness hash/status differs")
        flags(value, {"height_edits_applied": False, "saved_to_map": False,
                      "height_mip_lease_requested": True, "native_loading_barrier_completed": True})
        textures = value.get("textures_after")
        require(isinstance(textures, list) and len(textures) > 0, "Missing native height mip observations")
        for texture in textures:
            flags(texture, {"is_default_texture": False, "is_compiling": False})
            require(type(texture.get("mips")) is int and texture["mips"] > 0
                    and texture.get("resident_mips") == texture["mips"], "Incomplete native height mip residency")

def retain_producer_sources(frozen, destination, expected_sources):
    """Retain the two small authenticated project producers for topology review."""
    retained = []
    for name, expected in expected_sources.items():
        source = session._safe_path(frozen, "support-consumers/" + name)
        original = identity(source, 32 * 1024)
        same_pin(original, expected)
        raw = source.read_bytes()
        same_pin(identity(source, 32 * 1024), original)
        target = session._safe_path(destination, "source-producers/" + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
        copy = identity(target, 32 * 1024)
        same_pin(copy, expected)
        retained.append(dict(original=original, retained=copy))
    return retained

def main():
    global session
    arguments = sys.argv[1:]
    require(len(arguments) in (8, 9), "Unexpected diagnostic bridge argument count")
    mode, root_text, config_text, head, token, engine_text, engine_id, input_sha = arguments[:8]
    target = arguments[8] if len(arguments) == 9 else "window0112"
    root, config, engine = Path(root_text), Path(config_text), Path(engine_text)
    sys.path.insert(0, str(root))
    from scripts.ci import official_mcp_bob_session as session
    from scripts.ue import read_road_material_baseline as baseline
    from scripts.ue import road_shoulder_sources as shoulder_sources
    from scripts.proof import sa_calobra_tpp_survey as survey, sa_calobra_shoulder_contact as contact
    from scripts.manage_local_workspace import load_workspace
    spec = contact.target_spec(target)
    session._assert_isolated_root()
    require(root == session.ROOT and root.name == "rm-" + token, "Diagnostic checkout differs")
    proof = session._safe_path(root, "Saved/RuntimeProof/RoadMaterialBaseline/" + token)
    diagnostic = session._safe_path(proof, spec["output_name"])
    inputs_path = diagnostic / "source-inputs.json"
    if mode == "complete":
        inputs, inputs_pin = read(inputs_path)
        require(inputs_pin["sha256"] == input_sha and inputs["exact_sha"] == head
                and inputs["run_token"] == token
                and inputs.get("diagnostic_target", "window0112") == target, "Diagnostic input receipt changed")
        source = Path(inputs["retained_root"])
        retained = retain_capture(source, diagnostic, inputs["plan"])
        for row in inputs["files"]:
            same_pin(identity(Path(row["path"])), row)
        report, _ = read(source / "shoulder-contact.json")
        contact.require_captured(report)
        require(report.get("plan") == inputs["plan"] and report.get("source_identity") == inputs["source_identity"]
                and report.get("primary_api_receipt_sha256") == inputs["api_receipt"]["sha256"],
                "Native diagnostic differs from independently pinned source/camera/API evidence")
        flags(report, {"geometry_consumers_executed": False})
        flags(report.get("source_scene", {}), {"lighting_modified": False})
        flags(report.get("restoration", {}), {"height_mip_leases_released": True})
        for retained_root in (source, diagnostic):
            result = contact.verify(retained_root, head, target=target)
            verify_readiness(retained_root)
        require(len(retained) == spec["retained_file_count"], "Missing original receipt, PNG or native readiness evidence")
        result.update(run_token=token, retained_file_count=len(retained), source_inputs_unchanged=True,
                      original_and_artifact_copy_verified=True, diagnostic_target=target)
        write_once(diagnostic / "verification.json", result)
        print(json.dumps(result, allow_nan=False))
        return
    require(mode == "prepare", "Unknown diagnostic bridge phase")
    files = []
    def pin(path, expected=None, limit=512 * MIB):
        actual = identity(path, limit)
        if expected is not None:
            same_pin(actual, expected)
        files.append(actual)
        return actual
    base, base_pin = read(proof / "host-receipt.json")
    gpu, gpu_pin = read(proof / "road-asphalt-gpu-host-receipt.json")
    prior_contract(base, gpu, head, token)
    require(Path(base["project_root"]) == root and Path(base["proof_root"]) == proof
            and base["engine_identity"] == engine_id, "Prior native root/engine identity differs")
    same_pin(base_pin, gpu["source_receipts"]["baseline"])
    files.extend((base_pin, gpu_pin))
    if target == "hairpin0081":
        prior, prior_pin = read(proof / "shoulder-contact-host-receipt.json")
        restored_window0112(prior, head, token)
        files.append(prior_pin)
    pin(config, base["proof_files"]["workspace_config"], 2 * MIB)
    workspace = load_workspace(config)
    require(Path(workspace["engine"]) == engine, "Installed engine differs from workspace")
    retained = session._safe_path(Path(workspace["work"]), "road-materials/" + spec["output_name"] + "/" + head + "/" + token)
    require(not retained.is_relative_to(root) and not retained.exists(), "Diagnostic output is stale or inside checkout")
    native, native_pin = read(proof / "road-material-baseline.json", base["proof_files"]["native_baseline"])
    require(native.get("status") == base["status"] and native.get("exact_sha") == head, "Native baseline differs")
    flags(native, {"read_only": True, "persistent_world_mutation": False,
                   "saved_asset_bytes_unchanged": True, "pre_post_inventory_equal": True})
    files.append(native_pin)
    render, render_pin = read(proof / "road-asphalt-lit-review.json", gpu["evidence"]["render_receipt"])
    require(render.get("status") == "ROAD_ASPHALT_LIT_REVIEW_FRAMES_RETAINED"
            and render.get("exact_sha") == head and render.get("run_token") == token, "Native material GPU receipt differs")
    flags(render, {"road_full_buffers_unchanged": True, "sources_and_saved_assets_unchanged": True,
                   "capture_readiness_verified": True, "terrain_geometry_repaired": False})
    files.append(render_pin)
    for name in ("python_executable", "editor_executable", "engine_manifest"):
        pin(Path(base["proof_files"][name]["path"]), base["proof_files"][name])
    program = pin(engine / "Engine/Binaries/Win64/UnrealEditor.exe", gpu["program_executable"])
    pin(engine / "Engine/Build/BatchFiles/Build.bat", limit=2 * MIB)
    require(Path(base["proof_files"]["editor_executable"]["path"]) == engine / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe",
            "Commandline/GUI engines differ")
    manifest, _ = read(engine / "Engine/Binaries/Win64/UnrealEditor.modules")
    build_id = manifest.get("BuildId")
    require(isinstance(build_id, str) and build_id and build_id == base["native_engine_build_id"], "Native engine BuildId differs")
    state, state_pin = read(proof / "cache-state-original.json", base["proof_files"]["cache-state-original.json"])
    require(state == base["cache_provenance"]["original_state"] and state["EngineIdentity"] == engine_id
            and state["CompileFingerprint"] == base["source_fingerprints"]["compile"]
            and state["ProofFingerprint"] == base["source_fingerprints"]["proof"], "Baseline cached binary provenance differs")
    flags(state, {"CompilePassed": True, "ProofPassed": True})
    cached, cached_pin = read(proof / "cache-proof-summary.json", base["proof_files"]["cache-proof-summary.json"])
    require(cached_pin["sha256"] == state["ProofSummarySha256"] and cached_pin["size_bytes"] == state["ProofSummarySizeBytes"]
            and cached.get("Head") == state["ProofHead"] and cached.get("Failed") == 0 and cached.get("Errors") == 0
            and cached.get("Discovered", 0) > 0 and cached.get("Passed") == cached["Discovered"]
            and "YACS.ShoulderContactNative" in cached.get("TestFilter", "").split("+"), "Missing native diagnostic binary proof")
    files.extend((state_pin, cached_pin))
    binaries = base["binary_provenance"]
    require(len(binaries) == len(BINARY_FILES) and {row["relative"] for row in binaries} == set(BINARY_FILES),
            "Unexpected diagnostic binary closure")
    for row in binaries:
        require(row["original_CompileHead"] == state["CompileHead"] and row["original_ProofHead"] == state["ProofHead"]
                and row["native_engine_build_id"] == build_id, "Diagnostic binary provenance changed")
        actual = pin(session._safe_path(root, row["relative"]), row["copied_identity"])
        same_pin(actual, {key: row["original_identity"][key] for key in ("sha256", "size_bytes")})
        if row["relative"].endswith(".modules"):
            module, _ = read(Path(actual["path"]))
            require(module.get("BuildId") == build_id, "Staged module BuildId differs")
    preparation_pin = base["proof_files"]["session_preparation"]
    pin(proof / "session-preparation.json", preparation_pin, 2 * MIB)
    staged_path, staged_pin, staged, _ = baseline.authenticated_preparation(session, head, preparation_pin["sha256"])
    require(staged["source_sha256"] == session._sources(head)
            and staged["source_dependencies"] == session._source_dependency_inventory(head), "Staged source definition changed")
    pin(staged_path, staged_pin, 2 * MIB)
    rows = staged["consumer_assets"] + staged["source_dependencies"]
    session._verify_rows(root, rows)
    session._assert_package_members(root, rows)
    for row in rows:
        pin(session._safe_path(root, row["path"]), {key: row[key] for key in ("sha256", "size_bytes")})
    frozen = session._safe_path(Path(workspace["data"]), "world-data/sa-calobra-working-v1/frozen-road-c5573b3-2026-10-04")
    source = survey.load_frozen_windows(frozen)
    recipe, recipe_pin = read(survey.REPOSITORY_RECIPE)
    files.append(recipe_pin)
    for row in recipe["inputs"]:
        pin(session._safe_path(frozen, row["path"]), {key: row[key] for key in ("sha256", "size_bytes")})
    producers = retain_producer_sources(frozen, diagnostic, shoulder_sources.PRODUCERS)
    for producer in producers:
        files.extend((producer["original"], producer["retained"]))
    local_recipe = frozen / "source-recipe.json"
    if local_recipe.exists():
        pin(local_recipe, limit=2 * MIB)
    camera = root / contact.SURVEY_FILE
    pin(camera, limit=1 * MIB)
    view_plan_path = None
    if target == "hairpin0081":
        view_plan_path = proof / "road-asphalt-expected-view-plan.json"
        pin(view_plan_path, gpu["expected_view_plan"], 2 * MIB)
        contact.cut_bounds((frozen / spec["cut_file"]).read_bytes(), target=target)
    plan = contact.diagnostic_plan(source, head, camera, target=target, view_plan_path=view_plan_path)
    api, api_pins = primary_api(engine, head)
    api["run_token"] = token
    files.extend(api_pins)
    api_pin = write_once(diagnostic / "native-api-evidence.json", api)
    files.append(api_pin)
    inputs = dict(status="SHOULDER_CONTACT_SOURCE_INPUTS_VERIFIED", exact_sha=head, run_token=token,
                  diagnostic_target=target,
                  retained_root=str(retained), frozen_root=str(frozen), files=files, plan=plan,
                  source_identity=source["source_identity"], api_receipt=api_pin,
                  retained_source_producers=producers)
    input_pin = write_once(inputs_path, inputs)
    print(json.dumps(dict(status=inputs["status"], exact_sha=head, run_token=token, inputs=input_pin,
                          diagnostic_target=target, view_plan_path=str(view_plan_path) if view_plan_path else "",
                          retained_root=str(retained), frozen_root=str(frozen), api_receipt=api_pin,
                          program_executable=program, source_input_count=len(files)), allow_nan=False))

if __name__ == "__main__":
    main()
'@

try {
    $root = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\', '/')
    Assert-PlainPath $root
    Assert-PlainPath $WorkspaceConfig
    if (-not $env:GITHUB_WORKSPACE -or $env:GITHUB_SHA -cne $ExpectedHead -or
        $RunToken -cne ($env:GITHUB_RUN_ID + '-' + $env:GITHUB_RUN_ATTEMPT) -or
        -not [string]::Equals($root, (Join-Path $env:GITHUB_WORKSPACE ('rm-' + $RunToken)), [StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals($WorkspaceConfig, 'D:\yacs\workspace.json', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Diagnostic requires the exact shared-host rm run checkout and canonical config.'
    }
    $head = @(& git -C $root rev-parse HEAD)
    if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1 -or $head[0] -cne $ExpectedHead) { throw 'Diagnostic Git HEAD differs.' }
    Require-ExactSource
    $proof = Join-Path $root ('Saved/RuntimeProof/RoadMaterialBaseline/' + $RunToken)
    Assert-PlainPath $proof
    if (-not (Test-Path -LiteralPath $proof -PathType Container) -or
        (Test-Path -LiteralPath (Join-Path $proof $hostReceiptName))) {
        throw 'Diagnostic predecessor root missing or host receipt already exists.'
    }
    $candidate = Join-Path $proof $diagnosticName
    Assert-PlainPath $candidate
    if (Test-Path -LiteralPath $candidate) { throw 'Diagnostic refuses stale output.' }
    [void][IO.Directory]::CreateDirectory($candidate)
    $diagnostic = $candidate
    $base = Read-PinnedJson (Join-Path $proof 'host-receipt.json')
    $workspace = Read-PinnedJson $WorkspaceConfig
    if ($workspace.identity.sha256 -cne $base.value.proof_files.workspace_config.sha256 -or
        $workspace.identity.size_bytes -ne $base.value.proof_files.workspace_config.size_bytes) {
        throw 'Diagnostic workspace config differs from native baseline.'
    }
    $python = File-Identity 'D:\yacs\tool-cache\material-forge\python\Scripts\python.exe' 1GB
    if ($python.sha256 -cne $base.value.proof_files.python_executable.sha256 -or
        $python.size_bytes -ne $base.value.proof_files.python_executable.size_bytes) {
        throw 'Diagnostic Python executable differs from native baseline.'
    }
    . (Join-Path $root 'scripts/ci/Resolve-YacsUnrealEngine.ps1')
    $engine = Resolve-YacsUnrealEngine -ProjectPath (Join-Path $root 'YetAnotherCyclingSim.uproject') `
        -SearchRoots @([string]$workspace.value.engine)
    if (-not $engine -or $engine.Identity -cne $base.value.engine_identity -or $engine.Version -cne '5.8.2-56702186') {
        throw 'Diagnostic engine differs from checked native baseline.'
    }
    Assert-PlainPath $engine.Root
    $helper = Join-Path $diagnostic 'bridge-validation.py'
    Write-Exclusive $helper $bridgeCode
    $helperPin = File-Identity $helper 2MB
    $common = @(('"' + $root + '"'), ('"' + $WorkspaceConfig + '"'), $ExpectedHead, $RunToken,
                ('"' + $engine.Root + '"'), ('"' + $engine.Identity + '"'))
    $childEnvironment = @{ YACS_WORKSPACE_CONFIG = $WorkspaceConfig; PYTHONPATH = ''; PYTHONHOME = ''
        YACS_OWNER_HANDOFF = ''; YACS_MCP_BOB_PROJECT_ROOT = ''; YACS_MCP_BOB_EXPECTED_HEAD = '' }
    Invoke-OwnedProcess 'source-preflight' $python.path (@('-I', '-B', ('"' + $helper + '"'), 'prepare') + $common + @('none', $Target)) 180 $childEnvironment
    $prepared = Read-PinnedJson (Join-Path $diagnostic 'source-preflight-stdout.log')
    if ($prepared.value.status -cne 'SHOULDER_CONTACT_SOURCE_INPUTS_VERIFIED' -or
        $prepared.value.exact_sha -cne $ExpectedHead -or $prepared.value.run_token -cne $RunToken -or
        $prepared.value.diagnostic_target -cne $Target) {
        throw 'Diagnostic source preparation did not pass.'
    }
    $inputPin = $prepared.value.inputs
    Assert-Identity $inputPin 2MB
    $receipt.evidence.source_inputs = $inputPin
    $receipt.evidence.primary_api = $prepared.value.api_receipt
    $receipt.program_executable = $prepared.value.program_executable
    $receipt.retained_root = $prepared.value.retained_root
    $receipt.source_input_count = $prepared.value.source_input_count
    Require-IdleHost
    $receipt.status = 'CAPTURE_RUNNING'
    $editorLog = Join-Path $diagnostic 'owned-editor.log'
    $arguments = @(
        ('"' + (Join-Path $root 'YetAnotherCyclingSim.uproject') + '"'), '/Engine/Maps/Entry',
        '-DisablePlugins=ModelContextProtocol,Wingman,AndroidFileServer', '-RenderOffscreen', '-norhithread',
        '-Unattended', '-NoPause', '-NoSplash', '-NoSound', '-NoLiveCoding', '-NoVSync', '-NoP4', '-ScriptErrorsAreFatal',
        '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
        ('-ExecutePythonScript="' + (Join-Path $root 'scripts/ue/capture_sa_calobra_shoulder_contact.py') + '"'),
        ('-AbsLog="' + $editorLog + '"')
    )
    $captureEnvironment = $childEnvironment.Clone()
    $captureEnvironment.YACS_SHOULDER_CONTACT_ROOT = [string]$prepared.value.retained_root
    $captureEnvironment.YACS_SHOULDER_CONTACT_EXACT_SHA = $ExpectedHead
    $captureEnvironment.YACS_SHOULDER_CONTACT_WORKTREE = $root
    $captureEnvironment.YACS_SHOULDER_CONTACT_API_RECEIPT = [string]$prepared.value.api_receipt.path
    $captureEnvironment.YACS_SHOULDER_CONTACT_TARGET = $Target
    $captureEnvironment.YACS_SHOULDER_CONTACT_VIEW_PLAN = [string]$prepared.value.view_plan_path
    $captureEnvironment.YACS_SA_CALOBRA_TPP_FROZEN_ROOT = [string]$prepared.value.frozen_root
    Invoke-OwnedProcess 'owned-editor' $engine.UnrealEditorPath $arguments 1020 $captureEnvironment
    $nativeComplete = $true
}
catch { $receipt.status = 'FAILED'; $receipt.error = $_.Exception.Message }
finally {
    if ($inputPin) {
        try {
            Assert-Identity $helperPin 2MB
            Assert-Identity $python 1GB
            Invoke-OwnedProcess 'source-verification' $python.path (@('-I', '-B', ('"' + $helper + '"'), 'complete') + $common + @($inputPin.sha256, $Target)) 180 $childEnvironment
            $verified = Read-PinnedJson (Join-Path $diagnostic 'source-verification-stdout.log')
            if ($verified.value.status -cne 'SHOULDER_CONTACT_EVIDENCE_VERIFIED' -or
                $verified.value.exact_sha -cne $ExpectedHead -or $verified.value.run_token -cne $RunToken -or
                $verified.value.diagnostic_target -cne $Target -or
                $verified.value.frame_count -ne $frameCount -or $verified.value.source_inputs_unchanged -isnot [bool] -or
                -not $verified.value.source_inputs_unchanged -or
                $verified.value.original_and_artifact_copy_verified -isnot [bool] -or
                -not $verified.value.original_and_artifact_copy_verified) { throw 'Native diagnostic evidence failed verification.' }
            Require-ExactSource
            Require-IdleHost
            $receipt.evidence.verification = File-Identity (Join-Path $diagnostic 'verification.json') 2MB
            $receipt.evidence.retained_files = File-Identity (Join-Path $diagnostic 'retained-files.json') 2MB
            if ($nativeComplete -and $receipt.editor_exit_observed -and $receipt.editor_exit_code -eq 0 -and -not $receipt.stopped_on_failure) {
                $receipt.source_inputs_unchanged = $true; $receipt.restored_visibility_verified = $true
                $receipt.verified_frame_count = $frameCount; $receipt.status = 'SHOULDER_CONTACT_READ_ONLY_HOST_PASS'
            }
        }
        catch { $receipt.secondary_errors += $_.Exception.Message; $receipt.status = 'FAILED' }
    }
    if ($diagnostic) {
        foreach ($name in @('source-preflight-stdout.log', 'source-preflight-stderr.log', 'owned-editor.log',
                            'owned-editor-stdout.log', 'owned-editor-stderr.log',
                            'source-verification-stdout.log', 'source-verification-stderr.log')) {
            $path = Join-Path $diagnostic $name
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                try { $receipt.evidence[$name] = Log-Identity $path }
                catch { $receipt.secondary_errors += $_.Exception.Message }
            }
            elseif ($receipt.editor_pid -and $name.StartsWith('owned-editor')) {
                $receipt.secondary_errors += ('Missing owned diagnostic log: ' + $name)
            }
        }
    }
    if ($receipt.secondary_errors.Count -gt 0) { $receipt.status = 'FAILED' }
    if ($proof -and (Test-Path -LiteralPath $proof -PathType Container)) {
        Write-Exclusive (Join-Path $proof $hostReceiptName) ($receipt | ConvertTo-Json -Depth 40)
    }
}
if ($receipt.status -cne 'SHOULDER_CONTACT_READ_ONLY_HOST_PASS') {
    throw ('Read-only shoulder contact failed: ' + $receipt.error + ' ' + ($receipt.secondary_errors -join '; '))
}
Write-Host ('SHOULDER_CONTACT_READ_ONLY_HOST_PASS: ' + $frameCount + ' restored ' + $Target + ' diagnostic frames; visual review pending.')
