"""Fixed, trusted BOB capture body for the bounded official MCP checkpoint.

This module registers no tool, starts no server and accepts no operation input.
A future trusted host harness supplies the fixed session context and retained
profile. Its native registration, test orchestration and official transport
proof remain separate. Offline fixtures are synthetic, never native admission.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import math
from pathlib import Path
import stat
import time
from typing import Any

from scripts import committed_git_blobs as committed_git
from scripts.worldgen import bob_mcp_inspection as adapter


ROOT = Path(__file__).resolve().parents[2]
OPERATION = "scripts/ue/official_mcp_bob_operation.py"
COMMITTED_GIT_READER = "scripts/committed_git_blobs.py"
SESSION_DIR = "Saved/RuntimeProof/OfficialMcpBob"
PROFILE_SHA256 = "c0ca612dd5af5a311d1917e41d66f44aa83a9d40eed5e9e784432e06e2a52253"
PROFILE_SOURCE_SHA = "c5573b3cf545c51ce83ad1fb0a5ca3111f5ad7f6"
CONSUMER_SOURCE_SHA = "94827365ef8e83e52717bb21f9d6efa921aa2d1e"
MAP_PACKAGE = "/Game/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview"
MAP_FILE = "Content/" + MAP_PACKAGE.removeprefix("/Game/") + ".umap"
CANONICAL_MAP_FILE = "Content/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.umap"
CANONICAL_MAP_SHA256 = "276d1621fa083850f6d603b6d115b01b74c9a92c182254d15302e786abfbf29c"
LANDSCAPE_CLASS = "/Script/Landscape.Landscape"
GEOMETRY_VIEW = "road-geometry-inspection-before"
BASE_SOURCE_PATHS = tuple(dict.fromkeys((*adapter.SOURCE_PATHS, OPERATION, COMMITTED_GIT_READER,
    "scripts/geometry/smooth_road_ribbon.py", "scripts/geometry/curved_road_plan.py",
    "scripts/geometry/road_cut_limits.py", "scripts/geometry/road_single_bend.py",
    "scripts/geometry/road_surface_profile.py", "scripts/geometry/road_edge_roles.py",
    "scripts/geometry/road_width_profile.py", "scripts/geometry/road_transition.py")))
PLUGIN_PREFIX = "Plugins/YacsBobInspection/"
PLUGIN_REQUIRED = {
    PLUGIN_PREFIX + "YacsBobInspection.uplugin",
    PLUGIN_PREFIX + "Source/YacsBobInspection/YacsBobInspection.Build.cs",
    PLUGIN_PREFIX + "Source/YacsBobInspection/Private/YacsBobLandscapeHit.cpp",
    PLUGIN_PREFIX + "Source/YacsBobInspection/Public/YacsBobLandscapeHit.h",
}
CONTEXT_FIELDS = {"schema_version", "exact_sha", "source_sha256", "profile_sha256",
                  "profile_source_sha", "consumer_source_sha", "consumer_assets", "landscape"}
MAX_ASSET_BYTES = 1024 * 1024 * 1024
MAX_PERSISTENT_FILES = 20000
MAX_PERSISTENT_BYTES = 10 * MAX_ASSET_BYTES


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _safe_path(root: Path, relative: str) -> Path:
    """Reject aliases on every existing ancestor, including Windows junctions."""
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or ":" in relative or "\x00" in relative or Path(relative).is_absolute()
            or any(part in {"", ".", ".."} for part in relative.split("/"))):
        raise ValueError("path is outside the fixed operation root")
    candidate = root / relative
    for path in (candidate, *candidate.parents):
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise ValueError("symlink/reparse paths are not admitted")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError("path escapes the fixed operation root")
    return candidate


def _read_fixed(relative: str, expected: str | None = None) -> bytes:
    path = _safe_path(ROOT, relative)
    if expected is None:
        before = path.stat()
        if before.st_size > adapter.MAX_INPUT_BYTES:
            raise ValueError("fixed input exceeds the bounded input size")
        with path.open("rb") as stream:
            raw = stream.read(adapter.MAX_INPUT_BYTES + 1)
        if len(raw) > adapter.MAX_INPUT_BYTES:
            raise ValueError("fixed input exceeds the bounded input size")
        after = path.stat()
        identity = lambda value: (value.st_dev, value.st_ino, value.st_size,
                                  value.st_mtime_ns, value.st_ctime_ns)
        if identity(before) != identity(after) or len(raw) != before.st_size:
            raise ValueError("fixed input changed while being read")
        expected = _digest(raw)
    return adapter._read_bound_file(ROOT, relative, expected)[1]


def _asset_identity(relative: str, *, read_limit: int = MAX_ASSET_BYTES) -> dict[str, Any]:
    path = _safe_path(ROOT, relative)
    before = path.stat()
    bound = min(read_limit, MAX_ASSET_BYTES)
    if not stat.S_ISREG(before.st_mode) or before.st_size > bound:
        raise ValueError("persistent file is missing or exceeds its bound")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            size += len(block)
            if size > bound:
                raise ValueError("persistent file exceeds its read bound")
            digest.update(block)
    after = path.stat()
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size,
                              value.st_mtime_ns, value.st_ctime_ns)
    if identity(before) != identity(after) or size != before.st_size:
        raise ValueError("persistent file changed while being read")
    return {"path": relative, "size_bytes": size, "sha256": digest.hexdigest()}


def _source_inventory(exact_sha: str) -> tuple[str, ...]:
    paths = adapter._git(ROOT, "ls-tree", "-r", "--name-only", exact_sha,
                         "--", PLUGIN_PREFIX).decode().splitlines()
    if (not PLUGIN_REQUIRED.issubset(paths) or len(paths) > 128
            or any(not path.startswith(PLUGIN_PREFIX) for path in paths)):
        raise ValueError("committed native plugin source inventory is unavailable")
    return tuple(dict.fromkeys((*BASE_SOURCE_PATHS, *paths)))


def _sources(context: dict[str, Any]) -> dict[str, bytes]:
    exact_sha = context["exact_sha"]
    if (not isinstance(exact_sha, str) or not adapter.SHA40.fullmatch(exact_sha)
            or adapter._git(ROOT, "rev-parse", "HEAD").decode().strip() != exact_sha):
        raise ValueError("operation exact_sha differs from current HEAD")
    if adapter._git(ROOT, "status", "--porcelain", "--untracked-files=no").strip():
        raise ValueError("operation requires unchanged tracked files")
    expected = context["source_sha256"]
    adapter._fields(expected, set(_source_inventory(exact_sha)), "operation source_sha256")
    if _digest(Path(__file__).read_bytes()) != expected[OPERATION]:
        raise ValueError("executing operation source hash mismatch")
    if Path(committed_git.__file__).resolve() != _safe_path(ROOT, COMMITTED_GIT_READER).resolve():
        raise ValueError("executing committed Git reader belongs to another checkout")
    _read_fixed(COMMITTED_GIT_READER, expected[COMMITTED_GIT_READER])
    domain = adapter._sources(ROOT, exact_sha,
                               {path: expected[path] for path in adapter.SOURCE_PATHS})
    committed = committed_git._read_exact_blobs(
        ROOT, exact_sha, tuple(expected), blob_limit=adapter.MAX_INPUT_BYTES,
        total_limit=adapter.MAX_INPUT_BYTES, timeout_seconds=10,
        path_validator=_safe_path,
    )
    for relative in expected:
        raw = _read_fixed(relative, expected[relative])
        if raw != committed[relative]:
            raise ValueError(f"operation source differs from exact_sha: {relative}")
        domain[relative] = raw
    return domain


def _consumer_assets(context: dict[str, Any]) -> None:
    assets = context["consumer_assets"]
    if not isinstance(assets, list) or not 3 <= len(assets) <= 256:
        raise ValueError("accepted consumer asset inventory is missing or exceeds its bound")
    names = set()
    for asset in assets:
        adapter._fields(asset, {"path", "sha256", "size_bytes"}, "consumer asset")
        relative = asset["path"]
        if (not isinstance(relative, str) or not relative.startswith("Content/")
                or Path(relative).suffix not in {".umap", ".uasset", ".uexp", ".ubulk", ".uptnl"}
                or relative.casefold() in names or type(asset["size_bytes"]) is not int
                or not 0 < asset["size_bytes"] <= MAX_ASSET_BYTES
                or not isinstance(asset["sha256"], str) or not adapter.SHA256.fullmatch(asset["sha256"])):
            raise ValueError("accepted consumer asset identity is invalid or duplicated")
        actual = _asset_identity(relative)
        if actual != asset:
            raise ValueError("accepted consumer asset bytes differ")
        with _safe_path(ROOT, relative).open("rb") as stream:
            if stream.read(64).startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise ValueError("accepted consumer requires materialized asset bytes")
        names.add(relative.casefold())
    generated = "Content/Generated/YACS/SaCalobra/WholeMapPreparation/"
    mandatory = {MAP_FILE, generated + "M_SaCalobraWholeMapPreparation.uasset",
                 generated + "MI_SaCalobraWholeMapPreparation.uasset"}
    if not {name.casefold() for name in mandatory}.issubset(names):
        raise ValueError("accepted consumer map and material packages are missing")
    if _asset_identity(CANONICAL_MAP_FILE)["sha256"] != CANONICAL_MAP_SHA256:
        raise ValueError("immutable canonical source map differs")


def _persistent_snapshot() -> list[dict[str, Any]]:
    files = ["YetAnotherCyclingSim.uproject"]
    entry_count = 1
    for directory in ("Content", "Config"):
        pending = [_safe_path(ROOT, directory)]
        while pending:
            current = pending.pop()
            if not current.is_dir():
                raise ValueError("persistent project directory is missing")
            for child in current.iterdir():
                entry_count += 1
                if entry_count > MAX_PERSISTENT_FILES:
                    raise ValueError("persistent project inventory exceeds its entry bound")
                relative = child.relative_to(ROOT).as_posix()
                _safe_path(ROOT, relative)
                if child.is_dir():
                    pending.append(child)
                elif child.is_file():
                    files.append(relative)
                else:
                    raise ValueError("unsupported persistent project entry")
    inventory = []
    total = 0
    for relative in sorted(files):
        if _safe_path(ROOT, relative).stat().st_size > MAX_PERSISTENT_BYTES - total:
            raise ValueError("persistent project inventory exceeds its byte bound")
        item = _asset_identity(relative, read_limit=MAX_PERSISTENT_BYTES - total)
        inventory.append(item)
        total += item["size_bytes"]
    return inventory


def _checked_module(name: str, sources: dict[str, bytes]):
    module = importlib.import_module(name)
    relative = name.replace(".", "/") + ".py"
    if _digest(Path(module.__file__).read_bytes()) != _digest(sources[relative]):
        raise ValueError("executing capture/builder source hash mismatch")
    if hasattr(module, "ROOT") and Path(module.ROOT).resolve() != ROOT.resolve():
        raise ValueError("executing capture module belongs to another repository")
    return module


def _scene(api, context: dict[str, Any]):
    actual = Path(api.Paths.convert_relative_path_to_full(api.Paths.project_dir())).resolve()
    if actual != ROOT.resolve() or str(actual).replace("\\", "/").casefold().rstrip("/") == "d:/yacs/project":
        raise ValueError("BOB operation requires its exact isolated YACS project")
    for name in ("get_dirty_map_packages", "get_dirty_content_packages"):
        read_dirty = getattr(api.EditorLoadingAndSavingUtils, name, None)
        if not callable(read_dirty) or read_dirty():
            raise ValueError("BOB operation requires a non-dirty map and content")
    library = getattr(api, "YacsBobLandscapeHitLibrary", None)
    read_identity = getattr(library, "inspect_accepted_checkpoint_identity", None)
    if not callable(read_identity):
        raise ValueError("native stopped-checkpoint identity helper is unavailable")
    identity = read_identity()
    field = identity.get_editor_property
    expected = context["landscape"]
    if (field("accepted") is not True or field("status") != "CHECKPOINT_IDENTITY"
            or field("error") != "" or field("map_package") != MAP_PACKAGE
            or field("actor_path") != expected["path"]
            or field("actor_class_path") != expected["class_path"]):
        raise ValueError("native stopped-checkpoint identity was rejected or differs")
    world = api.get_editor_subsystem(api.UnrealEditorSubsystem).get_editor_world()
    if world is None or world.get_path_name().split(".")[0] != MAP_PACKAGE:
        raise ValueError("BOB operation has the wrong current map")
    landscapes = list(api.GameplayStatics.get_all_actors_of_class(world, api.Landscape))
    if len(landscapes) != 1 or landscapes[0] != field("hit_actor"):
        raise ValueError("BOB operation requires the exact single native Landscape")
    landscape = landscapes[0]
    if (landscape.get_path_name() != expected["path"]
            or landscape.get_class().get_path_name() != LANDSCAPE_CLASS):
        raise ValueError("BOB Landscape object binding differs")

    def numeric(value):
        if hasattr(value, "to_tuple"):
            return [numeric(item) for item in value.to_tuple()]
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("non-finite native actor transform")
        return number

    actors = list(api.get_editor_subsystem(api.EditorActorSubsystem).get_all_level_actors())
    paths = [actor.get_path_name() for actor in actors]
    if (landscape not in actors or any(not isinstance(path, str) or not path for path in paths)
            or len(set(paths)) != len(paths)):
        raise ValueError("native scene actor inventory is missing or ambiguous")
    snapshot = {"map_package": MAP_PACKAGE, "landscape": dict(expected),
                "actors": sorted((actor.get_path_name(), numeric(actor.get_actor_transform()))
                                 for actor in actors)}
    return world, landscape, snapshot


def _write_exclusive(relative: str, value: Any) -> bytes:
    raw = adapter.canonical_json_bytes(value)
    if len(raw) > adapter.MAX_INPUT_BYTES:
        raise ValueError("capture evidence exceeds its bounded output size")
    path = _safe_path(ROOT, SESSION_DIR + "/bundle/" + relative)
    with path.open("xb") as stream:
        stream.write(raw)
    adapter._read_bound_file(ROOT, SESSION_DIR + "/bundle/" + relative, _digest(raw))
    return raw


def capture_and_inspect() -> dict[str, Any]:
    """Capture the fixed accepted checkpoint and delegate the actual BOB inspector.

    The trusted context has exactly ``CONTEXT_FIELDS``. Its consumer source SHA
    remains the frozen #363 input provenance, independently of the operation's
    current HEAD. Its asset rows come from that accepted inventory; the future
    harness owns admission of the retained manifest before staging this context.
    This body writes only exclusive evidence files below its fixed ignored Saved
    directory. It does not certify native registration, tests or MCP transport.
    """
    started = time.monotonic()
    context_relative = SESSION_DIR + "/session-context.json"
    context_raw = _read_fixed(context_relative)
    context = adapter._json(context_raw)
    adapter._fields(context, CONTEXT_FIELDS, "trusted BOB session context")
    if (type(context["schema_version"]) is not int or context["schema_version"] != 1
            or context["profile_sha256"] != PROFILE_SHA256
            or context["profile_source_sha"] != PROFILE_SOURCE_SHA
            or context["consumer_source_sha"] != CONSUMER_SOURCE_SHA):
        raise ValueError("trusted BOB input provenance differs")
    adapter._fields(context["landscape"], {"path", "class_path"}, "trusted Landscape identity")
    if (context["landscape"]["class_path"] != LANDSCAPE_CLASS
            or not isinstance(context["landscape"]["path"], str)
            or not context["landscape"]["path"].startswith(MAP_PACKAGE + ".")):
        raise ValueError("trusted Landscape identity is outside the fixed map")
    sources = _sources(context)
    print("YACS_MCP_BOB_OPERATION SOURCE_BOUNDARY_INITIAL "
          f"elapsed={time.monotonic() - started:.6f}")
    profile_raw = _read_fixed(SESSION_DIR + "/profile.json", PROFILE_SHA256)
    profile = adapter._json(profile_raw)
    if not isinstance(profile, dict) or profile.get("exact_sha") != PROFILE_SOURCE_SHA:
        raise ValueError("retained profile source SHA differs; do not rewrite provenance")
    _consumer_assets(context)
    adapter._git(ROOT, "check-ignore", "--no-index", "--quiet", "--",
                 SESSION_DIR + "/bundle/receipt.json")
    bundle_root = _safe_path(ROOT, SESSION_DIR + "/bundle")
    if bundle_root.exists():
        raise ValueError("fixed BOB bundle already exists; preserve its evidence")
    builder = _checked_module("scripts.geometry.smooth_road_ribbon", sources)
    producer = _checked_module("scripts.ue.bob_road_earthworks_cut", sources)
    vertices, _triangles, metadata = builder.build_smooth_road_ribbon(profile)
    import unreal
    world, landscape, scene_before = _scene(unreal, context)
    persistent_before = _persistent_snapshot()
    # Large map byte inventories can take time. Refresh the trusted boundary
    # after that read, immediately before reserving evidence and measuring.
    _sources(context)
    print("YACS_MCP_BOB_OPERATION SOURCE_BOUNDARY_BEFORE_MEASUREMENT "
          f"elapsed={time.monotonic() - started:.6f}")
    _read_fixed(context_relative, _digest(context_raw))
    _read_fixed(SESSION_DIR + "/profile.json", PROFILE_SHA256)
    refreshed = _scene(unreal, context)
    if refreshed[1] != landscape or refreshed[2] != scene_before:
        raise ValueError("native scene changed before BOB measurement")
    bundle_root.mkdir()
    captures = []

    def sink(*, samples, inspection):
        if captures:
            raise ValueError("fixed BOB capture sink was invoked more than once")
        captures.append((deepcopy(samples), deepcopy(inspection)))

    arguments = adapter._policy_arguments(sources)
    direct = producer.measure_smooth_terrain_fit(
        world, profile, vertices, metadata, exact_sha=context["exact_sha"],
        contact_band_max_m=arguments["contact_band_max_m"],
        geometry_inspection_view=GEOMETRY_VIEW, landscape=landscape, sample_sink=sink,
    )
    print("YACS_MCP_BOB_OPERATION NATIVE_MEASUREMENT_COMPLETE "
          f"elapsed={time.monotonic() - started:.6f}")
    if len(captures) != 1 or captures[0][1] != direct:
        raise ValueError("native capture did not retain exactly one real direct inspection")
    samples = captures[0][0]
    _scene_after = _scene(unreal, context)
    if _scene_after[1] != landscape or _scene_after[2] != scene_before:
        raise ValueError("native scene changed during BOB inspection")
    domain_hashes = {path: context["source_sha256"][path] for path in adapter.SOURCE_PATHS}
    envelope = {"schema_version": 1, "exact_sha": context["exact_sha"],
                "region_id": "sa_calobra", "producer": adapter.NATIVE_PRODUCER,
                "sample_source": adapter.NATIVE_SAMPLE_SOURCE,
                "geometry_inspection_view": GEOMETRY_VIEW,
                "source_sha256": domain_hashes, "samples": samples}
    sample_raw = _write_exclusive("native-samples.json", envelope)
    delegated = adapter.inspect_bob_request({
        "exact_sha": context["exact_sha"], "native_samples_path": "native-samples.json",
        "native_samples_sha256": _digest(sample_raw), "source_sha256": domain_hashes,
    }, evidence_root=bundle_root, repository_root=ROOT)
    print("YACS_MCP_BOB_OPERATION DOMAIN_DELEGATION_COMPLETE "
          f"elapsed={time.monotonic() - started:.6f}")
    if delegated["result"] != direct:
        raise ValueError("native producer inspection differs from delegated BOB result")
    _consumer_assets(context)
    persistent_after = _persistent_snapshot()
    if persistent_after != persistent_before or _scene(unreal, context)[2] != scene_before:
        raise ValueError("persistent project or native scene changed during BOB operation")
    print("YACS_MCP_BOB_OPERATION PERSISTENT_CONSERVATION_COMPLETE "
          f"elapsed={time.monotonic() - started:.6f}")
    _sources(context)
    print("YACS_MCP_BOB_OPERATION SOURCE_BOUNDARY_FINAL "
          f"elapsed={time.monotonic() - started:.6f}")
    _read_fixed(context_relative, _digest(context_raw))
    _read_fixed(SESSION_DIR + "/profile.json", PROFILE_SHA256)
    _read_fixed(SESSION_DIR + "/bundle/native-samples.json", _digest(sample_raw))
    capture = {
        "schema_version": 1, "exact_sha": context["exact_sha"],
        "scope": "BOB_CAPTURE_AND_DOMAIN_COMPARISON; HOST_ADMISSION_PENDING",
        "context_sha256": _digest(context_raw), "source_sha256": dict(context["source_sha256"]),
        "profile": {"sha256": PROFILE_SHA256, "source_exact_sha": PROFILE_SOURCE_SHA},
        "consumer": {"source_exact_sha": CONSUMER_SOURCE_SHA,
                     "asset_inventory_sha256": _digest(adapter.canonical_json_bytes(context["consumer_assets"]))},
        "scene": scene_before, "sample_count": len(samples),
        "native_sample_sha256": _digest(sample_raw), "direct_invocation_matches": True,
        "persistent_inventory_sha256": _digest(adapter.canonical_json_bytes(persistent_before)),
        "persistent_files_unchanged": True, "scene_snapshot_unchanged": True,
        "native_capture_verified": False, "official_mcp_verified": False,
        "persistent_content_verified": False, **{flag: False for flag in adapter.FALSE_FLAGS},
    }
    _write_exclusive("direct-inspection.json", direct)
    _write_exclusive("result.json", delegated["result"])
    _write_exclusive("proof.json", delegated["proof"])
    _write_exclusive("capture-proof.json", capture)
    # Publish the receipt only after source, input, scene and content checks.
    _write_exclusive("receipt.json", delegated["receipt"])
    print("YACS_MCP_BOB_OPERATION COMPLETE "
          f"elapsed={time.monotonic() - started:.6f}")
    return {**delegated, "capture": capture}
