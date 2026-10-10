"""Copy the pinned #364 saved consumer into a new, independent review project.

This host utility starts no Unreal process, server, build or network operation.
The source checkpoint is 1ef46dacedba, not the current material-authoring HEAD.
A failed copy leaves an incomplete new directory without a readiness receipt;
it never repairs, overwrites or removes an existing project. Synthetic fixtures
must explicitly opt in and cannot produce a native readiness status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time

from scripts import committed_git_blobs as committed_git
from scripts.ci.official_mcp_bob_session import _identity, _read_json, _safe_path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SHA = "1ef46dacedba5ed1fc909422529be41808d3dbe4"
RUN_TOKEN = "38084733503-1"
SOURCE_ROOT = Path(
    r"D:\yacs\runner\_work\YetAnotherCyclingSim\YetAnotherCyclingSim\rm-38084733503-1"
)
REVIEW_ROOT = Path(r"D:\yacs\work\level-editor-review")
EVIDENCE_RELATIVE = "Saved/RuntimeProof/RoadMaterialBaseline/" + RUN_TOKEN
CHECKED_EVIDENCE = (
    "docs/experiments/sa-calobra-road-shoulder-window0112-20261010/candidate"
)
MAP_PACKAGE = "/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview"
MAP_FILE = "Content/" + MAP_PACKAGE.removeprefix("/Game/") + ".umap"
MAP_SHA256 = "35d485005f123e5648f675d6f91209630c163bddf92d55f6c5b640d55917732d"
NATIVE_BUILD_ID = "55116800"
RECEIPT_NAME = "level-editor-review-preparation.json"
FILE_LIMIT = 512 * 1024 * 1024
JSON_LIMIT = 2 * 1024 * 1024
TOTAL_LIMIT = 2 * 1024 * 1024 * 1024
FILE_COUNT_LIMIT = 384
MIN_FREE_BYTES = 5 * 1024 * 1024 * 1024
CHUNK_BYTES = 4 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SESSION_NAME = re.compile(RUNTIME_SHA[:12] + r"-[A-Za-z0-9][A-Za-z0-9_-]{0,47}\Z")

# The checked-in raw evidence and fresh native evidence must both match these
# immutable artifact bytes before any JSON document is parsed or followed.
PINNED_METADATA = {
    "host-receipt.json": ("41f7c1f90ef44dc0dcde840d75be019566d174958450360c12753c4add01be2c", 21402),
    "saved-road-host-receipt.json": ("3c0b99e1af7f2066b6229f7c333530ae69d0ae73f3b69b74b54cddeeb0d7db4d", 4183),
    "road-asphalt-saved-manifest.json": ("ccd13145400c756e5d27efd332f84fe87001a8e1e4fe00e08df00997310e5cbd", 22701),
    "road-asphalt-saved-reloaded.json": ("5d1b146f27b71cd5d580e1dad17ed1e0a79776ec9a2ecaac8d921d140a8d904c", 1252),
    "session-preparation.json": ("4c544a40aff62a3d847c2929780243d4436c314f579042031448a6ea6c576a4d", 50978),
}

# Exact unsmudged Git blobs at RUNTIME_SHA; verified equal to the launcher
# checkout when this checkpoint adapter was authored. Copy only these files,
# never Content/Python, Saved configuration, startup scripts or whole plugins.
PINNED_PROJECT_FILES = {
    "YetAnotherCyclingSim.uproject": ("09fbd6cd85fbdd299a3e37cfb65658e1210183878516599c90b783acc1d8099b", 1152),
    "Plugins/RoadForge/RoadForge.uplugin": ("c17cf8f8cfc6f7a63c4f8076d0856e5e64b488514d6df4008d0d6d205d20cfb0", 792),
    "Config/DefaultEditor.ini": ("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", 0),
    "Config/DefaultEngine.ini": ("d94045cbb0c78e0fde92d17f37651a11a94cc7c2b4bbd4a46382ac91ee5adb4b", 2877),
    "Config/DefaultGame.ini": ("0f03bfd8cbc106209bcf02a4499c62b823ba755cab9ccb6b0110ddd31197fb87", 344),
    "Config/DefaultInput.ini": ("5900681ae1def11edf4fe55966ede4b98c65e6b6a8937e0c49a19e35ab2ce926", 8941),
}
MODULE_CLOSURES = {
    "Binaries/Win64/UnrealEditor.modules": {
        "YetAnotherCyclingSim": "UnrealEditor-YetAnotherCyclingSim.dll",
        "YetAnotherCyclingSimEditor": "UnrealEditor-YetAnotherCyclingSimEditor.dll",
    },
    "Plugins/RoadForge/Binaries/Win64/UnrealEditor.modules": {
        "RoadForge": "UnrealEditor-RoadForge.dll",
    },
}
BINARY_PATHS = set(MODULE_CLOSURES) | {
    str(Path(manifest).parent / filename).replace("\\", "/")
    for manifest, modules in MODULE_CLOSURES.items() for filename in modules.values()
}
PNG_DEPENDENCIES = {
    "worldgen/materials/visual_fill/" + name + ".png"
    for name in ("inference-kind", "material-weights", "sample-availability")
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _path(root, relative):
    _require(isinstance(relative, str) and len(relative) <= 512,
             "invalid snapshot relative path")
    for part in relative.split("/"):
        _require(not any(ord(c) < 32 or c in '<>"|?*' for c in part)
                 and not part.endswith((".", " "))
                 and not re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part),
                 "Windows path alias is not admitted")
    return _safe_path(root, relative)


def _stamp(path):
    _safe_path(path.parent, path.name)
    value = path.stat()
    _require(stat.S_ISREG(value.st_mode), "snapshot input is not a regular file")
    return (value.st_dev, value.st_ino, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def _file_identity(path, limit=FILE_LIMIT):
    # Reuse the existing nonempty-file guard. The pinned DefaultEditor.ini is
    # legitimately empty, so authenticate that special shape without weakening
    # the shared asset/evidence guard.
    before = _stamp(path)
    if before[2]:
        return _identity(path, limit)
    with path.open("rb") as reader:
        _require(reader.read(1) == b"", "empty input changed during read")
    _require(_stamp(path) == before, "empty input changed during read")
    return {"sha256": hashlib.sha256(b"").hexdigest(), "size_bytes": 0}


def _expected(row, *, allow_empty=False):
    _require(isinstance(row, dict) and isinstance(row.get("sha256"), str)
             and SHA256.fullmatch(row["sha256"]) is not None
             and type(row.get("size_bytes")) is int
             and (0 if allow_empty else 1) <= row["size_bytes"] <= FILE_LIMIT,
             "invalid or unbounded snapshot file identity")
    return {key: row[key] for key in ("sha256", "size_bytes")}


def _anchor(pair):
    return {"sha256": pair[0], "size_bytes": pair[1]}


def _same_path(value, expected):
    return (isinstance(value, str)
            and value.replace("\\", "/").casefold()
            == str(expected).replace("\\", "/").casefold())


def _metadata(source_root, checked_root, anchors):
    _require(set(anchors) == set(PINNED_METADATA), "metadata anchor set differs")
    native_root = _path(source_root, EVIDENCE_RELATIVE)
    paths = {}
    # Authenticate the entire anchor set before parsing any metadata.
    for name, pair in anchors.items():
        for base in (checked_root, native_root):
            path = _path(base, name)
            _require(_identity(path, JSON_LIMIT) == _anchor(pair),
                     "checked-in/native evidence differs from immutable anchor: " + name)
        paths[name] = _path(native_root, name)
    return {name: _read_json(path, anchors[name]) for name, path in paths.items()}


def _validate_metadata(documents, source_root, anchors, map_sha256):
    for name, document in documents.items():
        _require(document.get("schema_version") == 1
                 and document.get("exact_sha") == RUNTIME_SHA
                 and (name == "session-preparation.json" or document.get("issue") == 364),
                 "saved checkpoint source identity differs")
    host = documents["host-receipt.json"]
    saved = documents["saved-road-host-receipt.json"]
    manifest = documents["road-asphalt-saved-manifest.json"]
    reload = documents["road-asphalt-saved-reloaded.json"]
    preparation = documents["session-preparation.json"]
    _require(host.get("run_token") == RUN_TOKEN
             and host.get("status") == "ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE"
             and host.get("reader_pass") is True and host.get("error") is None
             and host.get("owned_editor_exit_observed") is True
             and host.get("owned_editor_exit_code") == 0
             and host.get("native_engine_build_id") == NATIVE_BUILD_ID
             and _same_path(host.get("project_root"), source_root)
             and _same_path(host.get("proof_root"), source_root / EVIDENCE_RELATIVE),
             "native baseline host receipt is not the pinned successful checkpoint")
    _require(saved.get("run_token") == RUN_TOKEN
             and saved.get("status") == "ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_HOST_PASS"
             and saved.get("native_baseline_authenticated") is True
             and saved.get("saved_derived_consumer") is True
             and saved.get("fresh_reload_verified") is True
             and saved.get("original_map_saved") is False
             and saved.get("original_landscape_mutated") is False
             and saved.get("error") is None,
             "saved consumer host proof is not complete")
    _require(preparation.get("status") == "ACCEPTED_CONSUMER_BYTES_STAGED"
             and manifest.get("status") == "SAVED_ROAD_ASPHALT_CONSUMER_PREPARED"
             and manifest.get("map_package") == MAP_PACKAGE
             and manifest.get("map_file") == MAP_FILE
             and manifest.get("map_saved") is True
             and manifest.get("canonical_saved") is False
             and manifest.get("source_scene_mutated") is False
             and manifest.get("staging_sha256") == anchors["session-preparation.json"][0],
             "saved consumer/staging receipt graph differs")
    _require(reload.get("status") == "ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_PASS"
             and reload.get("fresh_process") is True
             and reload.get("new_saved_asset_bytes_unchanged") is True
             and reload.get("source_scene_mutated") is False
             and reload.get("map_package") == MAP_PACKAGE
             and reload.get("map_sha256") == map_sha256
             and reload.get("saved_manifest_sha256") == anchors["road-asphalt-saved-manifest.json"][0]
             and reload.get("evidence_manifest_sha256") == anchors["road-asphalt-saved-manifest.json"][0],
             "saved consumer fresh-reload identity differs")
    for document, key, filename in (
        (host, "session_preparation", "session-preparation.json"),
        (saved, "saved_manifest", "road-asphalt-saved-manifest.json"),
        (saved, "fresh_reload", "road-asphalt-saved-reloaded.json"),
    ):
        row = document.get("proof_files", {}).get(key)
        _require(_expected(row) == _anchor(anchors[filename])
                 and _same_path(row.get("path"), source_root / EVIDENCE_RELATIVE / filename),
                 "native host evidence link differs: " + key)


def _copy_plan(documents, source_root, project_root, project_anchors, anchors, map_sha256):
    rows, aliases, duplicate_count = {}, {}, 0

    def add(relative, expected, origin, source_relative, role):
        nonlocal duplicate_count
        _path(origin, source_relative)
        _path(source_root, relative)  # validates the destination spelling too
        key = relative.casefold()
        _require(key not in aliases or aliases[key] == relative,
                 "case-aliased duplicate snapshot path")
        aliases[key] = relative
        if relative in rows:
            _require(rows[relative]["identity"] == expected
                     and rows[relative]["source"] == _path(origin, source_relative),
                     "conflicting duplicate snapshot path: " + relative)
            rows[relative]["roles"].append(role)
            duplicate_count += 1
            return
        rows[relative] = {"path": relative, "identity": expected,
                          "source": _path(origin, source_relative), "roles": [role]}
        _require(len(rows) <= FILE_COUNT_LIMIT, "snapshot file count exceeds bound")

    preparation = documents["session-preparation.json"]
    manifest = documents["road-asphalt-saved-manifest.json"]
    for role, candidates in (
        ("source_dependency", preparation.get("source_dependencies")),
        ("consumer_asset", preparation.get("consumer_assets")),
        ("saved_road_asset", manifest.get("assets")),
    ):
        _require(isinstance(candidates, list) and 0 < len(candidates) <= FILE_COUNT_LIMIT,
                 "invalid bounded asset inventory")
        group_names = set()
        for row in candidates:
            expected = _expected(row)
            relative = row.get("path")
            _path(source_root, relative)
            _require((relative.startswith("Content/")
                      and Path(relative).suffix in {".uasset", ".umap"})
                     or relative in PNG_DEPENDENCIES, "unexpected non-asset dependency")
            _require(relative not in group_names, "duplicate within one asset inventory")
            group_names.add(relative)
            if role == "saved_road_asset":
                _require(relative.startswith("Content/Generated/YACS/RoadAsphaltConsumer/")
                         and row.get("storage") == "packages/" + relative,
                         "saved consumer storage path differs")
            add(relative, expected, source_root, relative, role)
    _require(MAP_FILE in rows and rows[MAP_FILE]["identity"]["sha256"] == map_sha256,
             "pinned review map is absent or differs")
    binaries = documents["host-receipt.json"].get("binary_provenance")
    _require(isinstance(binaries, list) and len(binaries) == len(BINARY_PATHS)
             and {row.get("relative") for row in binaries if isinstance(row, dict)} == BINARY_PATHS,
             "native binary closure differs")
    for row in binaries:
        relative = row["relative"]
        expected = _expected(row.get("copied_identity"))
        _require(_expected(row.get("original_identity")) == expected
                 and row.get("native_engine_build_id") == NATIVE_BUILD_ID
                 and _same_path(row["copied_identity"].get("path"), source_root / relative),
                 "native binary provenance differs")
        add(relative, expected, source_root, relative, "native_binary")
    for relative, closure in MODULE_CLOSURES.items():
        row = rows[relative]
        pair = (row["identity"]["sha256"], row["identity"]["size_bytes"])
        module = _read_json(row["source"], pair)
        _require(module.get("BuildId") == NATIVE_BUILD_ID and module.get("Modules") == closure,
                 "native module manifest closure/build identity differs")
    _require(set(project_anchors) == set(PINNED_PROJECT_FILES), "project source file set differs")
    for relative, pair in project_anchors.items():
        expected = _expected(_anchor(pair), allow_empty=True)
        add(relative, expected, project_root, relative, "pinned_git_project_source")
    for name, pair in anchors.items():
        add("ReviewEvidence/" + name, _anchor(pair), source_root,
            EVIDENCE_RELATIVE + "/" + name, "authenticated_checkpoint_evidence")
    return list(rows.values()), duplicate_count


def _copy_verified(row, destination):
    source = row["source"]
    expected = row["identity"]
    _require(_stamp(source) == row["source_stamp"], "source changed before copy")
    target = _path(destination, row["path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    _path(destination, row["path"])
    digest, count = hashlib.sha256(), 0
    with source.open("rb") as reader, target.open("xb") as writer:
        opened = os.fstat(reader.fileno())
        _require((opened.st_dev, opened.st_ino, opened.st_size,
                  opened.st_mtime_ns, opened.st_ctime_ns) == row["source_stamp"],
                 "source was replaced before opening")
        while block := reader.read(min(CHUNK_BYTES, expected["size_bytes"] + 1 - count)):
            count += len(block)
            _require(count <= expected["size_bytes"], "source exceeded its pinned copy bound")
            digest.update(block)
            writer.write(block)
        writer.flush()
        os.fsync(writer.fileno())
    _require({"sha256": digest.hexdigest(), "size_bytes": count} == expected,
             "source bytes differ from pinned copy identity: " + row["path"])
    _require(_stamp(source) == row["source_stamp"], "source changed during copy")
    _require(_file_identity(target) == expected, "independent snapshot copy differs")
    copied = target.stat()
    _require(copied.st_nlink == 1
             and (copied.st_dev, copied.st_ino) != row["source_stamp"][:2],
             "snapshot must be an independent copy, never a hardlink")
    return {"path": row["path"], "source_path": str(source),
            "snapshot_path": str(target), **expected, "roles": row["roles"]}


def prepare(destination, launcher_sha, *, source_root=SOURCE_ROOT, project_root=ROOT,
            checked_evidence_root=None, metadata_anchors=None, project_anchors=None,
            map_sha256=MAP_SHA256, synthetic=False):
    """Create one fresh snapshot; override inputs only for explicit offline fixtures."""
    source_root, project_root, destination = map(Path, (source_root, project_root, destination))
    checked_evidence_root = Path(checked_evidence_root or project_root / CHECKED_EVIDENCE)
    anchors = PINNED_METADATA if metadata_anchors is None else metadata_anchors
    project_anchors = PINNED_PROJECT_FILES if project_anchors is None else project_anchors
    _require(type(synthetic) is bool and isinstance(launcher_sha, str)
             and SHA40.fullmatch(launcher_sha) is not None, "invalid launcher identity")
    if not synthetic:
        _require(os.name == "nt" and source_root == SOURCE_ROOT and project_root == ROOT
                 and checked_evidence_root == ROOT / CHECKED_EVIDENCE
                 and anchors == PINNED_METADATA and project_anchors == PINNED_PROJECT_FILES
                 and map_sha256 == MAP_SHA256 and destination.parent == REVIEW_ROOT
                 and SESSION_NAME.fullmatch(destination.name) is not None,
                 "native CLI is restricted to the pinned host/checkpoint and a unique review path")
    _require(source_root.is_absolute() and project_root.is_absolute() and destination.is_absolute(),
             "snapshot roots must be absolute")
    _path(source_root.parent, source_root.name)
    _path(project_root.parent, project_root.name)
    _path(destination.parent, destination.name)
    _require(source_root.is_dir() and project_root.is_dir(), "snapshot source root is absent")
    _require(not destination.exists(), "existing destination cannot be reused or overwritten")
    _require(not destination.resolve().is_relative_to(source_root.resolve())
             and not destination.resolve().is_relative_to(project_root.resolve()),
             "review destination must be isolated from both source roots")
    documents = _metadata(source_root, checked_evidence_root, anchors)
    _validate_metadata(documents, source_root, anchors, map_sha256)
    rows, duplicate_count = _copy_plan(
        documents, source_root, project_root, project_anchors, anchors, map_sha256)
    total = sum(row["identity"]["size_bytes"] for row in rows)
    _require(total <= TOTAL_LIMIT, "snapshot exceeds its total byte bound")
    for row in rows:
        row["source_stamp"] = _stamp(row["source"])
        _require(row["source_stamp"][2] == row["identity"]["size_bytes"],
                 "source size differs before copying: " + row["path"])
        if "pinned_git_project_source" in row["roles"]:
            _require(_file_identity(row["source"], JSON_LIMIT) == row["identity"],
                     "project configuration differs from pinned Git source bytes")
    ancestor = destination.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    _require(shutil.disk_usage(ancestor).free >= MIN_FREE_BYTES + total + JSON_LIMIT,
             "copy would consume the required 5 GiB free disk reserve")
    destination.mkdir(parents=True, exist_ok=False)
    _path(destination.parent, destination.name)
    copied = []
    remaining = total
    for row in rows:
        _require(shutil.disk_usage(destination).free >= MIN_FREE_BYTES + remaining + JSON_LIMIT,
                 "free disk reserve changed during preparation")
        copied.append(_copy_verified(row, destination))
        remaining -= row["identity"]["size_bytes"]
    for row in rows:
        _require(_stamp(row["source"]) == row["source_stamp"],
                 "source changed before snapshot completion")
    receipt = {
        "schema_version": 1, "issue": 364, "milestone": "M3", "synthetic": synthetic,
        "status": "SYNTHETIC_SNAPSHOT_PREPARED" if synthetic else "READY_FOR_EDITOR_LAUNCH",
        "runtime_source_sha": RUNTIME_SHA, "launcher_sha": launcher_sha,
        "runtime_source_run": RUN_TOKEN, "runtime_source_root": str(source_root),
        "snapshot_root": str(destination), "project_file": str(destination / "YetAnotherCyclingSim.uproject"),
        "map_package": MAP_PACKAGE, "map_file": MAP_FILE, "map_sha256": map_sha256,
        "engine_identity": documents["host-receipt.json"].get("engine_identity"),
        "native_engine_build_id": NATIVE_BUILD_ID,
        "pinned_project_source_sha": RUNTIME_SHA,
        "evidence_anchors": {name: _anchor(pair) for name, pair in anchors.items()},
        "snapshot_files": copied, "copied_file_count": len(copied), "copied_bytes": total,
        "identical_duplicate_rows_merged": duplicate_count,
        "independent_file_copies": True, "source_files_unchanged": True,
        "unreal_launched": False, "stream_status": "NOT_STARTED", "stream_verified": False,
        "owner_visual_status": "PENDING_FINAL_M3", "performance_status": "DEFERRED_AFTER_M3",
        "performance_pass": False, "free_disk_reserve_bytes": MIN_FREE_BYTES,
    }
    raw = (json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    _require(len(raw) <= JSON_LIMIT, "snapshot receipt exceeds its bound")
    _require(shutil.disk_usage(destination).free >= MIN_FREE_BYTES + len(raw),
             "insufficient free reserve before readiness receipt")
    receipt_path = _path(destination, RECEIPT_NAME)
    with receipt_path.open("xb") as writer:
        writer.write(raw)
        writer.flush()
        os.fsync(writer.fileno())
    if shutil.disk_usage(destination).free < MIN_FREE_BYTES:
        receipt_path.unlink()  # Only our newly written readiness claim; never source bytes.
        raise ValueError("free disk reserve was lost before completion")
    return receipt


def _verify_launcher(launcher_sha):
    head = committed_git._git_bounded(
        ROOT, ("rev-parse", "--verify", "HEAD"), 128,
        deadline=time.monotonic() + 20).decode().strip()
    _require(head == launcher_sha, "launcher SHA differs from current checkout HEAD")
    paths = (
        "scripts/ue/prepare_level_editor_review.py", "scripts/ci/official_mcp_bob_session.py",
        "scripts/ue/official_mcp_bob_operation.py", "scripts/worldgen/bob_mcp_inspection.py",
        "scripts/committed_git_blobs.py",
    )
    blobs = committed_git._read_exact_blobs(
        ROOT, launcher_sha, paths, blob_limit=JSON_LIMIT, total_limit=5 * JSON_LIMIT,
        timeout_seconds=30, path_validator=_path)
    for relative, raw in blobs.items():
        _require(_identity(_path(ROOT, relative), JSON_LIMIT)
                 == {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)},
                 "executing preparation source differs from committed launcher SHA")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--launcher-sha", required=True)
    args = parser.parse_args(argv)
    _require(os.name == "nt", "native preparation is available only on the pinned Windows host")
    _require(SHA40.fullmatch(args.launcher_sha) is not None, "invalid launcher SHA")
    _verify_launcher(args.launcher_sha)
    receipt = prepare(args.destination, args.launcher_sha)
    print(json.dumps({key: receipt[key] for key in (
        "status", "runtime_source_sha", "launcher_sha", "snapshot_root", "project_file",
        "map_package", "map_sha256", "copied_file_count", "copied_bytes",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
