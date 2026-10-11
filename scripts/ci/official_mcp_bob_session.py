"""Stage only the accepted #363 bytes for the trusted, fixed #384 BOB session.

This is a host utility, never an MCP tool. It uses the existing Git LFS checkout
and missing-only workspace restorer; no Editor, server, reconstruction, save,
benchmark or new scene producer is launched. Runtime admission remains pending.
Offline fixtures must identify themselves as synthetic, not accepted evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any

from scripts import committed_git_blobs as committed_git
from scripts.assets.restore_workspace_data import restore
from scripts.ci.sa_calobra_whole_map_workflow import ASSET_ROOTS
from scripts.manage_local_workspace import load_workspace
from scripts.ue import official_mcp_bob_operation as operation


ROOT = Path(__file__).resolve().parents[2]
WINDOWS_HOST = os.name == "nt"
SOURCE_SHA = operation.CONSUMER_SOURCE_SHA
SOURCE_RUN = "37954100285"
SOURCE_ATTEMPT = 1
PROOF_RELATIVE = f"proofs/sa-calobra-whole-map/{SOURCE_SHA}/{SOURCE_RUN}-1"
PROFILE_RELATIVE = (
    "world-data/sa-calobra-working-v1/frozen-road-c5573b3-2026-10-04/"
    "ma2141-profile-candidate.json"
)
SESSION_DIR = operation.SESSION_DIR
CONSUMER_NAME = "saved-material-consumer/consumer-manifest.json"
DELIVERY_NAME = "saved-material-consumer/delivery-package-manifest.json"
RELOAD_NAME = "saved-material-consumer/reload-receipt.json"
FRESH_NAME = "saved-material-consumer/fresh-render-receipt.json"
INITIAL_NAME = "checkout-restoration.json"
POST_NAME = "checkout-restoration-post-material.json"
# Raw bytes read from artifact 11628546016 in native run 37996979223, and
# independently equal to all six files at the retained accepted host proof root.
PINNED_METADATA = {
    CONSUMER_NAME: (
        "0eff084ad7bad97200e8947c47f5480ebb504b928769ab1bc36609de6ef777fb",
        388583,
    ),
    DELIVERY_NAME: (
        "d8e7dfe050d952f8c0bbc236f1effe15ccc9a48b578277fb4b4c4817d8c122c8",
        1532,
    ),
    RELOAD_NAME: (
        "2e4025d7b56f60bc5f8f13c3e16390b4ae4bcff915ba680a14c64b8fe3190aae",
        595,
    ),
    FRESH_NAME: (
        "60a5bccd95ea78f58a910c25f293db12eb124429e281b8a96d590558f45cc356",
        6163,
    ),
    INITIAL_NAME: (
        "6e15ef090fc94d694e35aba9ca3dac78ddc7c581d495d9f23cf1a7f772da7c34",
        345,
    ),
    POST_NAME: (
        "41c473d3e90fe3f7c72ec1baec741d8356c7e5e00f6e2cc56a7c5611837265a0",
        447,
    ),
}
# Derived from the actual immutable frozen948 tree, in sorted path order:
# SHA256(b"\n".join(path.encode() + b" " + oid.encode() for each pointer)).
FROZEN_DEPENDENCY_COUNT = 236
FROZEN_DEPENDENCY_BYTES = 325467377
FROZEN_DEPENDENCY_SHA256 = (
    "7a81d327d8b6be0643ddb3b19dfd384be7e87585b4842a1755dc3e4b2d3d2439"
)
JSON_LIMIT = 2 * 1024 * 1024
CLIENT_UTILITY_LIMIT = 256 * 1024
PROFILE_LIMIT = operation.adapter.MAX_INPUT_BYTES
FILE_LIMIT = 512 * 1024 * 1024
TOTAL_LIMIT = 2 * 1024 * 1024 * 1024
GIT_BATCH_OBJECTS = 512
GIT_BATCH_PATH_BYTES = 1024
GIT_BATCH_BYTES = operation.adapter.MAX_INPUT_BYTES
LFS_CHECKOUT_BATCH = 16  # bounded Windows argv and deterministic native hydration
POINTER = re.compile(
    rb"version https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n\Z"
)
GENERATED_PREFIX = "Content/Generated/YACS/SaCalobra/WholeMapPreparation/"
GENERATED_PRIMARIES = {
    operation.MAP_FILE,
    GENERATED_PREFIX + "M_SaCalobraWholeMapPreparation.uasset",
    GENERATED_PREFIX + "MI_SaCalobraWholeMapPreparation.uasset",
    GENERATED_PREFIX + "T_WholeMapWeights.uasset",
}
LIBRARY = "Content/Generated/YACS/TextureMaterialPrep/Libraries/3d53743e48394f31beb35e4030dc8a87/"
TEXTURE_PRIMARIES = {
    LIBRARY + suffix + ".uasset"
    for role in ("DryGrass", "ForestLitter", "ExposedRock", "DryMineral", "Scree")
    for suffix in ("Sources/T_Source_" + role, "ProviderData/" + role + "/T_Normal")
}
SOURCE_PROOF_HASHES = {
    "master_receipt_sha256",
    "retained_packages_receipt_sha256",
    "native_verification_sha256",
    "capture_receipt_sha256",
    "checkout_restoration_sha256",
    "prep_manifest_sha256",
}
UTILITY_SOURCE_PATHS = (
    committed_git.SOURCE_PATH,
    "scripts/ci/official_mcp_bob_client.py",
    "scripts/ci/official_mcp_bob_session.py",
    "scripts/ue/Invoke-YacsOfficialMcpBobSession.ps1",
    "scripts/ue/bootstrap_official_mcp_bob_session.py",
    "scripts/assets/restore_workspace_data.py",
    "scripts/ci/sa_calobra_whole_map_workflow.py",
    "scripts/manage_local_workspace.py",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _safe_path(root: Path, relative: str) -> Path:
    return operation._safe_path(root, relative)


def _identity(path: Path, limit: int = FILE_LIMIT) -> dict[str, Any]:
    _safe_path(path.parent, path.name)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= limit:
        raise ValueError("accepted input is not a bounded regular file")
    digest, count = hashlib.sha256(), 0
    with path.open("rb") as stream:
        while block := stream.read(min(4 * 1024 * 1024, limit + 1 - count)):
            count += len(block)
            if count > limit:
                raise ValueError("accepted input exceeded its read bound")
            digest.update(block)
    after = path.stat()
    fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if count != before.st_size or fields(before) != fields(after):
        raise ValueError("accepted input changed during read")
    return {"sha256": digest.hexdigest(), "size_bytes": count}


def _read_json(
    path: Path, expected: tuple[str, int] | None = None, *, limit: int = JSON_LIMIT
) -> dict:
    identity = _identity(path, limit)
    if expected is not None and identity != {
        "sha256": expected[0],
        "size_bytes": expected[1],
    }:
        raise ValueError("accepted metadata differs from its immutable artifact anchor")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit or hashlib.sha256(raw).hexdigest() != identity["sha256"]:
        raise ValueError("accepted metadata changed before parsing")
    value = operation.adapter._json(raw)
    if not isinstance(value, dict):
        raise ValueError("accepted metadata must be a JSON object")
    return value


def _read_metadata(proof_root: Path) -> dict[str, dict]:
    # Authenticate every selected raw file before parsing any of them.
    paths = {name: _safe_path(proof_root, name) for name in PINNED_METADATA}
    for name, path in paths.items():
        digest, size = PINNED_METADATA[name]
        if _identity(path, JSON_LIMIT) != {"sha256": digest, "size_bytes": size}:
            raise ValueError(
                "accepted metadata differs from its immutable artifact anchor"
            )
    return {
        name: _read_json(path, PINNED_METADATA[name]) for name, path in paths.items()
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_metadata(
    documents: dict[str, dict],
) -> tuple[dict, list[dict], list[dict]]:
    consumer, delivery = documents[CONSUMER_NAME], documents[DELIVERY_NAME]
    parent = GENERATED_PREFIX.removeprefix("Content/")
    parent = "/Game/" + parent + "M_SaCalobraWholeMapPreparation"
    _require(
        consumer.get("schema_version") == 1
        and consumer.get("status") == "SAVED_MATERIAL_CONSUMER_PREPARED"
        and consumer.get("exact_sha") == SOURCE_SHA
        and consumer.get("map_package") == operation.MAP_PACKAGE
        and consumer.get("canonical_map_package")
        == "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
        and consumer.get("canonical_map_sha256") == operation.CANONICAL_MAP_SHA256
        and consumer.get("terrain_sha256") == operation.CANONICAL_MAP_SHA256
        and consumer.get("terrain_identity_kind") == "immutable_canonical_accepted_map"
        and consumer.get("component_count") == 1024
        and consumer.get("geometry_mutation") is False
        and consumer.get("canonical_map_saved") is False
        and consumer.get("expected_material_parent") == parent
        and consumer.get("expected_material_instance")
        == parent.replace("/M_SaCalobra", "/MI_SaCalobra"),
        "accepted saved consumer contract differs",
    )
    for key in (
        "producer_sha256_lf",
        "geometry_snapshot_sha256",
        "material_recipe_sha256",
    ):
        _require(
            isinstance(consumer.get(key), str)
            and operation.adapter.SHA256.fullmatch(consumer[key]) is not None,
            "accepted consumer source/geometry identity is missing",
        )
    _require(
        hashlib.sha256(_canonical(consumer.get("geometry_snapshot"))).hexdigest()
        == consumer["geometry_snapshot_sha256"],
        "accepted geometry snapshot hash differs",
    )
    source = consumer.get("source_proof")
    _require(
        isinstance(source, dict)
        and set(source) == {"exact_sha", *SOURCE_PROOF_HASHES}
        and source.get("exact_sha") == SOURCE_SHA,
        "accepted source receipt graph differs",
    )
    for key in SOURCE_PROOF_HASHES:
        _require(
            isinstance(source[key], str)
            and operation.adapter.SHA256.fullmatch(source[key]) is not None,
            "accepted source receipt hash is invalid",
        )
    _require(
        source["checkout_restoration_sha256"] == PINNED_METADATA[INITIAL_NAME][0]
        and consumer.get("fresh_render_receipt")
        == {
            "path": "fresh-render-receipt.json",
            "sha256": PINNED_METADATA[FRESH_NAME][0],
        },
        "accepted fresh-render or conservation graph differs",
    )
    for name, phase in ((INITIAL_NAME, "initial"), (POST_NAME, "post-material")):
        receipt = documents[name]
        _require(
            receipt.get("schema_version") == 1
            and receipt.get("exact_sha") == SOURCE_SHA
            and receipt.get("status") == "PASS"
            and receipt.get("audit_phase") == phase
            and receipt.get("map_sha256") == operation.CANONICAL_MAP_SHA256
            and receipt.get("errors") == []
            and all(
                receipt.get(key) is True
                for key in (
                    "tracked_checkout_unchanged",
                    "retained_source_unchanged",
                    "prepared_bundle_unchanged",
                )
            ),
            "accepted conservation receipt failed",
        )
    _require(
        documents[POST_NAME].get("initial_receipt_sha256")
        == PINNED_METADATA[INITIAL_NAME][0],
        "post-material conservation does not bind the initial receipt",
    )
    for name, status in (
        (RELOAD_NAME, "SAVED_MATERIAL_CONSUMER_RELOADED"),
        (FRESH_NAME, "SAVED_MATERIAL_CONSUMER_RENDERED"),
    ):
        receipt = documents[name]
        _require(
            receipt.get("status") == status
            and receipt.get("exact_sha") == SOURCE_SHA
            and receipt.get("map_package") == operation.MAP_PACKAGE
            and receipt.get("map_sha256") == consumer.get("map_sha256")
            and receipt.get("expected_material_parent") == parent
            and receipt.get("component_count") == 1024
            and receipt.get("fresh_process") is True
            and receipt.get("material_reapplied") is False
            and receipt.get("geometry_mutation") is False,
            "accepted saved reopening receipt differs",
        )
    _require(
        documents[FRESH_NAME].get("saved_assets_unchanged") is True
        and documents[FRESH_NAME].get("capture_settings_restored") is True,
        "accepted fresh render lacks unchanged saved assets",
    )
    assets = consumer.get("assets")
    _require(
        isinstance(assets, list) and 14 <= len(assets) <= 256,
        "accepted consumer inventory is missing",
    )
    names, generated, stripped, total = set(), [], [], 0
    primaries = GENERATED_PRIMARIES | TEXTURE_PRIMARIES
    families = {path.rsplit(".", 1)[0]: path for path in primaries}
    for row in assets:
        _require(
            isinstance(row, dict)
            and set(row) <= {"path", "sha256", "size_bytes", "storage"}
            and {"path", "sha256", "size_bytes"} <= set(row),
            "accepted consumer asset fields differ",
        )
        path = row["path"]
        _require(
            isinstance(path, str) and path.casefold() not in names,
            "accepted consumer inventory is duplicated",
        )
        _safe_path(ROOT, path)
        family = next(
            (
                primary
                for stem, primary in families.items()
                if path.startswith(stem + ".")
            ),
            None,
        )
        _require(
            family is not None
            and (
                path == family
                or path[len(family.rsplit(".", 1)[0]) :]
                in {".uexp", ".ubulk", ".uptnl", ".m.ubulk"}
            ),
            "consumer asset exceeds its fixed package families",
        )
        _require(
            type(row["size_bytes"]) is int
            and 0 < row["size_bytes"] <= FILE_LIMIT
            and isinstance(row["sha256"], str)
            and operation.adapter.SHA256.fullmatch(row["sha256"]) is not None,
            "accepted consumer asset identity is invalid",
        )
        total += row["size_bytes"]
        _require(
            total <= TOTAL_LIMIT, "accepted consumer inventory exceeds its byte bound"
        )
        if family in GENERATED_PRIMARIES:
            _require(
                row.get("storage")
                == {
                    "asset": "packages/" + Path(path).name,
                    "release": "isolated saved material consumer",
                },
                "accepted delivery storage exceeds its fixed scope",
            )
            generated.append(row)
        else:
            _require(
                "storage" not in row,
                "tracked texture cannot use arbitrary delivery storage",
            )
        stripped.append({key: row[key] for key in ("path", "sha256", "size_bytes")})
        names.add(path.casefold())
    _require(
        primaries <= {row["path"] for row in assets}
        and next(row["sha256"] for row in assets if row["path"] == operation.MAP_FILE)
        == consumer.get("map_sha256"),
        "accepted primary map/material/texture inventory differs",
    )
    _require(
        delivery.get("schema_version") == 1
        and set(delivery) == {"schema_version", "files"}
        and delivery.get("files") == generated,
        "delivery manifest differs from accepted consumer subset",
    )
    return consumer, generated, stripped


def _git(*args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    return result.stdout


def _git_bounded(
    args: tuple[str, ...], output_limit: int, *, request: bytes = b"", deadline: float
) -> bytes:
    return committed_git._git_bounded(
        ROOT, args, output_limit, request=request, deadline=deadline
    )


def _git_blob_inventory(exact_sha: str, paths: tuple[str, ...]) -> dict[str, str]:
    return committed_git._git_blob_inventory(
        ROOT, exact_sha, paths, path_validator=_safe_path, timeout_seconds=120
    )


def _git_blobs(inventory: dict[str, str], *, blob_limit: int) -> dict[str, bytes]:
    _require(
        0 < blob_limit <= JSON_LIMIT,
        "committed Git blob inventory exceeds its bound",
    )
    return committed_git._git_blobs(
        ROOT,
        inventory,
        blob_limit=blob_limit,
        total_limit=GIT_BATCH_BYTES,
        timeout_seconds=120,
        path_validator=_safe_path,
    )


def _assert_isolated_root() -> None:
    _require(WINDOWS_HOST, "session staging requires the trusted Windows host")
    _safe_path(ROOT, "YetAnotherCyclingSim.uproject")
    _require(
        ROOT.resolve() == Path(__file__).resolve().parents[2],
        "session utility belongs to another checkout",
    )
    _require(
        operation.ROOT.resolve() == ROOT.resolve()
        and operation.adapter.ROOT.resolve() == ROOT.resolve(),
        "session domain modules belong to another checkout",
    )
    normalized = str(ROOT.resolve()).replace("\\", "/").casefold().rstrip("/")
    _require(
        normalized != "d:/yacs/project"
        and not normalized.startswith("d:/yacs/project/"),
        "session staging refuses the live project",
    )


def _workspace() -> dict:
    workspace_root = Path("D:/yacs")
    config_path = _safe_path(workspace_root, "workspace.json")
    before = _identity(config_path, JSON_LIMIT)
    raw_config = _read_json(config_path)
    _require(
        raw_config.get("schema_version") == 1, "canonical workspace schema differs"
    )
    # The existing resolver returns resolved paths. Inspect their original
    # configured ancestors first so that a junction cannot disappear there.
    for key in ("work", "data", "cache"):
        _require(
            isinstance(raw_config.get(key), str), "canonical workspace path is missing"
        )
        _safe_path(workspace_root, Path(raw_config[key]).as_posix())
    config = load_workspace(config_path)
    _require(
        _identity(config_path, JSON_LIMIT) == before,
        "canonical workspace configuration changed during resolution",
    )
    _require(
        Path(config["root"]).resolve() == workspace_root.resolve(),
        "canonical workspace root differs",
    )
    for key in ("work", "data", "cache"):
        path = Path(config[key])
        _safe_path(path.parent, path.name)
    return config


def _source_dependency_inventory(exact_sha: str) -> list[dict]:
    inventory = _git_blob_inventory(exact_sha, ASSET_ROOTS)
    _require(
        len(inventory) == FROZEN_DEPENDENCY_COUNT,
        "frozen scene dependency inventory differs",
    )
    blobs = _git_blobs(inventory, blob_limit=512)
    rows, witnesses = [], []
    for path in sorted(inventory):
        _safe_path(ROOT, path)
        raw = blobs[path]
        match = POINTER.fullmatch(raw)
        _require(
            match is not None, "frozen scene dependency is not a committed LFS pointer"
        )
        row = {"path": path, "sha256": match[1].decode(), "size_bytes": int(match[2])}
        _require(
            0 < row["size_bytes"] <= FILE_LIMIT,
            "frozen scene dependency exceeds its bound",
        )
        rows.append(row)
        witnesses.append(path.encode() + b" " + match[1])
    _require(
        sum(row["size_bytes"] for row in rows) == FROZEN_DEPENDENCY_BYTES
        and hashlib.sha256(b"\n".join(witnesses)).hexdigest()
        == FROZEN_DEPENDENCY_SHA256,
        "execution HEAD changed the frozen source dependency set",
    )
    _require(
        next(
            row["sha256"] for row in rows if row["path"] == operation.CANONICAL_MAP_FILE
        )
        == operation.CANONICAL_MAP_SHA256,
        "canonical accepted map identity differs",
    )
    return rows


def _verify_rows(root: Path, rows: list[dict]) -> None:
    for row in rows:
        observed = _identity(_safe_path(root, row["path"]))
        expected = {key: row[key] for key in ("sha256", "size_bytes")}
        _require(
            observed == expected,
            "accepted asset bytes differ: "
            f"{row['path']} (expected_size={expected['size_bytes']}, "
            f"observed_size={observed['size_bytes']}, "
            f"expected_sha256={expected['sha256']}, "
            f"observed_sha256={observed['sha256']})",
        )


def _assert_package_members(root: Path, rows: list[dict]) -> None:
    expected = {row["path"] for row in rows}
    for row in rows:
        path = _safe_path(root, row["path"])
        if path.suffix not in {".uasset", ".umap"} or not path.parent.exists():
            continue
        count = 0
        for member in path.parent.glob(path.stem + ".*"):
            count += 1
            _require(count <= 256, "package family inventory exceeds its bound")
            relative = member.relative_to(root).as_posix()
            _safe_path(root, relative)
            _require(
                member.is_file() and relative in expected,
                "unrecorded package family member; never repair or replace it",
            )


def _hydrate_dependencies(rows: list[dict], cache: Path) -> None:
    pending = []
    for row in rows:
        target = _safe_path(ROOT, row["path"])
        if target.exists():
            if target.stat().st_size <= 1024:
                raw = target.read_bytes()
                if raw == _git("show", "HEAD:" + row["path"]):
                    pending.append(row)
                    continue
            _require(
                _identity(target)
                == {key: row[key] for key in ("sha256", "size_bytes")},
                "existing frozen dependency differs; never overwrite owner bytes",
            )
        else:
            pending.append(row)
    # Validate every needed cache object before checkout can write any file.
    for row in pending:
        oid = row["sha256"]
        cached = _safe_path(cache, f"objects/{oid[:2]}/{oid[2:4]}/{oid}")
        _require(
            _identity(cached) == {key: row[key] for key in ("sha256", "size_bytes")},
            "accepted LFS cache object is missing or corrupt",
        )
    if pending:
        # Windows Actions runs with isolated Git global/system configuration.
        # Unlike synthetic fixtures, fresh actions/checkout repositories do not
        # inherit any LFS filter installation. Bootstrap only this throwaway
        # repository after every cache object has passed its SHA/size preflight.
        # Keep automatic smudging disabled: only the fixed pinned paths below
        # may be hydrated from the authenticated offline object store.
        _git("lfs", "install", "--local", "--skip-smudge")
        for start in range(0, len(pending), LFS_CHECKOUT_BATCH):
            batch = pending[start : start + LFS_CHECKOUT_BATCH]
            _git(
                "-c",
                "lfs.storage=" + str(cache),
                "lfs",
                "checkout",
                "--",
                *(row["path"] for row in batch),
            )
            _verify_rows(ROOT, batch)
    _verify_rows(ROOT, rows)


def _sources(exact_sha: str, *, include_utilities: bool = False) -> dict[str, str]:
    _require(
        isinstance(exact_sha, str)
        and operation.adapter.SHA40.fullmatch(exact_sha) is not None
        and _git("rev-parse", "HEAD").decode().strip() == exact_sha,
        "session execution SHA differs from HEAD",
    )
    _require(
        not _git("status", "--porcelain", "--untracked-files=no").strip(),
        "session staging requires unchanged tracked files",
    )
    inventory = operation._source_inventory(exact_sha)
    paths = tuple(dict.fromkeys((*inventory, *UTILITY_SOURCE_PATHS)))
    tree = _git_blob_inventory(exact_sha, paths)
    _require(set(tree) == set(paths), "committed session source inventory differs")
    blobs = _git_blobs(tree, blob_limit=JSON_LIMIT)
    _require(
        _safe_path(ROOT, committed_git.SOURCE_PATH).resolve()
        == Path(committed_git.__file__).resolve(),
        "executing committed Git helper differs from the pinned source",
    )
    hashes = {}
    for relative in paths:
        path = _safe_path(ROOT, relative)
        identity = _identity(path, JSON_LIMIT)
        with path.open("rb") as stream:
            raw = stream.read(JSON_LIMIT + 1)
        _require(
            len(raw) <= JSON_LIMIT and raw == blobs[relative],
            "executing session source differs from committed HEAD",
        )
        if include_utilities and relative in UTILITY_SOURCE_PATHS:
            _require(
                len(raw) <= CLIENT_UTILITY_LIMIT,
                "trusted client utility exceeds its existing byte bound",
            )
        _require(
            hashlib.sha256(raw).hexdigest() == identity["sha256"],
            "session source changed during read",
        )
        if relative in inventory or include_utilities:
            hashes[relative] = hashlib.sha256(raw).hexdigest()
    return hashes


def _write_exclusive(relative: str, value: Any) -> None:
    path = _safe_path(ROOT, SESSION_DIR + "/" + relative)
    raw = _canonical(value)
    _require(len(raw) <= JSON_LIMIT, "session evidence exceeds its fixed bound")
    with path.open("xb") as stream:
        stream.write(raw)


def stage_accepted_consumer(*, exact_sha: str) -> dict:
    """Prepare accepted bytes in this isolated checkout, before any MCP activation."""
    _assert_isolated_root()
    sources = _sources(exact_sha)
    config = _workspace()
    proof_root = _safe_path(Path(config["work"]), PROOF_RELATIVE)
    documents = _read_metadata(proof_root)
    consumer, generated, assets = _validate_metadata(documents)
    dependencies = _source_dependency_inventory(exact_sha)
    dependency_by_path = {row["path"]: row for row in dependencies}
    for row in assets:
        if row["path"] not in GENERATED_PRIMARIES and not row["path"].startswith(
            GENERATED_PREFIX
        ):
            _require(
                dependency_by_path.get(row["path"]) == row,
                "accepted texture differs from frozen committed dependency",
            )
    consumer_root = _safe_path(proof_root, "saved-material-consumer")
    for row in generated:
        expected = {key: row[key] for key in ("sha256", "size_bytes")}
        _require(
            _identity(_safe_path(consumer_root, row["storage"]["asset"])) == expected,
            "retained accepted delivery package differs",
        )
    _assert_package_members(ROOT, assets)
    _assert_package_members(ROOT, dependencies)
    # Verify all existing generated targets before any hydration/restoration.
    restore({"schema_version": 1, "files": generated}, consumer_root, ROOT, apply=False)
    profile = _safe_path(Path(config["data"]), PROFILE_RELATIVE)
    profile_identity = _identity(profile, PROFILE_LIMIT)
    _require(
        profile_identity["sha256"] == operation.PROFILE_SHA256
        and _read_json(profile, limit=PROFILE_LIMIT).get("exact_sha")
        == operation.PROFILE_SOURCE_SHA,
        "retained road profile identity differs; do not rewrite provenance",
    )
    session = _safe_path(ROOT, SESSION_DIR)
    _require(not session.exists(), "fixed session evidence already exists; preserve it")
    _git(
        "check-ignore",
        "--no-index",
        "--quiet",
        "--",
        SESSION_DIR + "/session-preparation.json",
    )
    session.mkdir(parents=True)
    receipt = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "consumer_source_sha": SOURCE_SHA,
        "consumer_source_run": SOURCE_RUN,
        "consumer_source_attempt": SOURCE_ATTEMPT,
        "status": "PREPARATION_PENDING",
        "source_sha256": sources,
        "metadata_anchors": {
            name: {"sha256": pin[0], "size_bytes": pin[1]}
            for name, pin in PINNED_METADATA.items()
        },
        "consumer_assets": assets,
        "source_dependencies": dependencies,
        "native_runtime_verified": False,
        "official_mcp_admitted": False,
        "persistent_world_mutation": False,
        "performance_pass": False,
        "performance_status": "DEFERRED_AFTER_M3",
        "context_written": False,
    }
    try:
        cache = _safe_path(Path(config["cache"]), "git-lfs/YetAnotherCyclingSim")
        _hydrate_dependencies(dependencies, cache)
        receipt["restoration"] = restore(
            {"schema_version": 1, "files": generated}, consumer_root, ROOT, apply=True
        )
        _verify_rows(ROOT, assets)
        _verify_rows(ROOT, dependencies)
        for row in generated:
            _require(
                _identity(_safe_path(consumer_root, row["storage"]["asset"]))
                == {key: row[key] for key in ("sha256", "size_bytes")},
                "retained delivery source changed during staging",
            )
        _assert_package_members(ROOT, assets)
        _assert_package_members(ROOT, dependencies)
        _read_metadata(proof_root)
        _require(
            _sources(exact_sha) == sources, "session source changed during staging"
        )
        _require(
            _identity(profile, PROFILE_LIMIT) == profile_identity,
            "retained profile changed during staging",
        )
        with (
            profile.open("rb") as source,
            _safe_path(ROOT, SESSION_DIR + "/profile.json").open("xb") as destination,
        ):
            destination.write(source.read(PROFILE_LIMIT + 1))
        _require(
            _identity(_safe_path(ROOT, SESSION_DIR + "/profile.json"), PROFILE_LIMIT)
            == profile_identity,
            "copied retained profile differs",
        )
        receipt["profile_sha256"] = profile_identity["sha256"]
        receipt["status"] = "ACCEPTED_CONSUMER_BYTES_STAGED"
    except Exception:
        receipt["status"] = "PREPARATION_BLOCKED"
        raise
    finally:
        _write_exclusive("session-preparation.json", receipt)
    return receipt


def prepare_native_session_context() -> dict:
    """Bind actual native identity after the trusted harness loads the fixed map.

    This function never loads a map, changes a setting, registers a toolset or
    starts a server. Any rejection leaves session-context.json unpublished.
    """
    _assert_isolated_root()
    staged = _read_json(_safe_path(ROOT, SESSION_DIR + "/session-preparation.json"))
    exact_sha = staged.get("exact_sha")
    sources = _sources(exact_sha)
    _require(
        staged.get("status") == "ACCEPTED_CONSUMER_BYTES_STAGED"
        and staged.get("consumer_source_sha") == SOURCE_SHA
        and staged.get("source_sha256") == sources
        and staged.get("native_runtime_verified") is False
        and staged.get("official_mcp_admitted") is False,
        "trusted session preparation is missing or stale",
    )
    config = _workspace()
    proof_root = _safe_path(Path(config["work"]), PROOF_RELATIVE)
    documents = _read_metadata(proof_root)
    consumer, _generated, assets = _validate_metadata(documents)
    dependencies = _source_dependency_inventory(exact_sha)
    _verify_rows(ROOT, dependencies)
    _verify_rows(ROOT, assets)
    _assert_package_members(ROOT, assets)
    _assert_package_members(ROOT, dependencies)
    _require(
        staged.get("consumer_assets") == assets
        and staged.get("source_dependencies") == dependencies,
        "staged source or consumer inventory changed",
    )
    _require(
        _identity(_safe_path(ROOT, SESSION_DIR + "/profile.json"), PROFILE_LIMIT)[
            "sha256"
        ]
        == operation.PROFILE_SHA256,
        "fixed retained profile changed",
    )
    _require(
        not _safe_path(ROOT, SESSION_DIR + "/session-context.json").exists()
        and not _safe_path(ROOT, SESSION_DIR + "/bundle").exists(),
        "fixed session context/output already exists",
    )
    import unreal

    actual_project = Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    ).resolve()
    _require(
        actual_project == ROOT.resolve(),
        "native context requires the exact isolated project",
    )
    library = getattr(unreal, "YacsBobLandscapeHitLibrary", None)
    read = getattr(library, "inspect_accepted_checkpoint_identity", None)
    _require(callable(read), "native fixed checkpoint helper is unavailable")
    observed = read()
    field = observed.get_editor_property
    _require(
        field("accepted") is True
        and field("status") == "CHECKPOINT_IDENTITY"
        and field("error") == ""
        and field("map_package") == operation.MAP_PACKAGE,
        "native stopped checkpoint identity rejected",
    )
    actor = field("hit_actor")
    _require(
        actor is not None
        and actor.get_path_name() == field("actor_path")
        and actor.get_class().get_path_name()
        == field("actor_class_path")
        == operation.LANDSCAPE_CLASS,
        "native checkpoint Actor binding differs",
    )
    context = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "source_sha256": sources,
        "profile_sha256": operation.PROFILE_SHA256,
        "profile_source_sha": operation.PROFILE_SOURCE_SHA,
        "consumer_source_sha": SOURCE_SHA,
        "consumer_assets": assets,
        "landscape": {
            "path": field("actor_path"),
            "class_path": field("actor_class_path"),
        },
    }
    _world, landscape, scene = operation._scene(unreal, context)
    _require(landscape == actor, "native Landscape differs from actual scene")
    # The accepted snapshot uses a normalized scene/world prefix after save-as.
    world_object = (
        operation.MAP_PACKAGE + "." + operation.MAP_PACKAGE.rsplit("/", 1)[-1]
    )
    actual_actors = [
        [path.replace(world_object + ":", "<scene>.<world>:"), transform]
        for path, transform in scene["actors"]
    ]
    _require(
        actual_actors == consumer["geometry_snapshot"].get("actors"),
        "opened scene Actor census/transforms differ from accepted saved checkpoint",
    )
    _require(
        len(landscape.get_components_by_class(unreal.LandscapeComponent)) == 1024,
        "opened accepted Landscape component count differs",
    )
    _verify_rows(ROOT, dependencies)
    _verify_rows(ROOT, assets)
    _assert_package_members(ROOT, assets)
    _assert_package_members(ROOT, dependencies)
    _read_metadata(proof_root)
    _require(
        _sources(exact_sha) == sources
        and operation._scene(unreal, context)[2] == scene,
        "native session boundary changed before context publication",
    )
    _require(
        _identity(_safe_path(ROOT, SESSION_DIR + "/profile.json"), PROFILE_LIMIT)[
            "sha256"
        ]
        == operation.PROFILE_SHA256,
        "fixed retained profile changed before context publication",
    )
    _write_exclusive("session-context.json", context)
    return context


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-sha", required=True)
    args = parser.parse_args()
    receipt = stage_accepted_consumer(exact_sha=args.exact_sha)
    summary = {
        key: receipt[key]
        for key in (
            "status",
            "exact_sha",
            "consumer_source_sha",
            "native_runtime_verified",
            "official_mcp_admitted",
            "persistent_world_mutation",
            "performance_pass",
            "context_written",
        )
    }
    summary["consumer_asset_count"] = len(receipt["consumer_assets"])
    summary["source_dependency_count"] = len(receipt["source_dependencies"])
    print("YACS_BOB_SESSION_PREPARATION " + json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
