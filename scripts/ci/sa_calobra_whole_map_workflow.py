"""Bounded input and evidence checks for the owner-only whole-map material lane.

This adapter never grants visual or performance admission. It reads configured
retained sources, keeps their original bytes, and binds a fresh native capture to
the exact checkout and the CPU-prepared full-grid material inputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import shutil
import struct
import subprocess
from pathlib import Path, PurePosixPath

from scripts.assets.run_sa_calobra_detail_pilot import (
    CAPTURE,
    FRAMES,
    MESH,
    RECEIPT,
)
from scripts.assets.run_sa_calobra_detail_pilot import (
    verify_native as verify_retained_native,
)
from scripts.proof.retain_sa_calobra_tpp_survey import no_link

ROOT = Path(__file__).resolve().parents[2]
MAP = "Content/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.umap"
MAP_SHA256 = "276d1621fa083850f6d603b6d115b01b74c9a92c182254d15302e786abfbf29c"
LIBRARY = "Content/Generated/YACS/TextureMaterialPrep/Libraries/3d53743e48394f31beb35e4030dc8a87"
ASSET_ROOTS = (
    MAP,
    "Content/Worlds/SaCalobra/CheckpointMaterials",
    "Content/Worlds/SaCalobra/CheckpointEarthworks",
    "Content/Generated/YACS/MaskReview/M_MaskReview_1.uasset",
    "Content/Generated/YACS/MaskReview/T_MaskReview_1.uasset",
    LIBRARY,
    "Content/Generated/YACS/TextureMaterialPrep/Runs/C414EA4B402723D66FCB689E49EEB02D/BaseColor.uasset",
    "Content/Generated/YACS/TextureMaterialPrep/Runs/94406E0247C9822CFD006CAB8B20545E/BaseColor.uasset",
    "worldgen/materials/visual_fill/material-weights.png",
    "worldgen/materials/visual_fill/sample-availability.png",
    "worldgen/materials/visual_fill/inference-kind.png",
)
NATIVE_FIXED = (
    ("terrain-erosion-mesh/combined-mesh.json", "source/combined-mesh.json", MESH),
    (
        "terrain-erosion-mesh/component230-cliff-visual-receipt.json",
        "source/component230-cliff-visual-receipt.json",
        RECEIPT,
    ),
    (
        "local-cliff-smoothing/local-cliff-smoothing-mesh.json",
        "source-reference/local-cliff-smoothing-mesh.json",
        "9ed6c9179d2df04117fcc8992224061f942d42a03a714a4a75177c43728b1cd5",
    ),
    (
        "local-cliff-smoothing/component230-cliff-visual-receipt.json",
        "source-reference/component230-cliff-visual-receipt.json",
        "c9494905cbb51f5622e3a414c862eb86d21a261063d6b5adc357ee74ac2a2742",
    ),
    (
        "plan/component230-cliff-visual-plan.json",
        "plan/component230-cliff-visual-plan.json",
        "41768c7680ddea2304f9968d4b2947bf65e1164ffacfa45f74dcefad955b5359",
    ),
)
PILOT = "docs/experiments/sa-calobra-component230-detail-pilot-20261008"
PINNED_COMMITTED = (
    (
        PILOT + "/annotations.json",
        "annotations.json",
        "0a7703e960d6762d7721dafe0d646c74d889c6ff25c4b115b06129992a7586e8",
    ),
    (
        PILOT + "/pilot/triangle-bands.json",
        "pilot/triangle-bands.json",
        "6ec02a0e3dac9756923d29c8b603c0c1d79db411d06f3a20bb30956e11390953",
    ),
    (
        PILOT + "/pilot/manifest.json",
        "pilot/manifest.json",
        "804842ef0893df0d4822caa458ca68b658bf6d9481ef64db5237dde00ec97718",
    ),
    (
        "docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv",
        "frames.csv",
        FRAMES,
    ),
)
COMMITTED_EVIDENCE = (
    (
        PILOT + "/pilot/triangle-bands.json",
        "6ec02a0e3dac9756923d29c8b603c0c1d79db411d06f3a20bb30956e11390953",
        321818,
    ),
    (
        PILOT + "/pilot/manifest.json",
        "804842ef0893df0d4822caa458ca68b658bf6d9481ef64db5237dde00ec97718",
        2377,
    ),
    (
        "docs/experiments/sa-calobra-material-repair-20261006/evidence/native-projection.json",
        "49b0c3e57b07d266b828985dcacde6e4347ec8f7b393b2d4ef266d80d463bced",
        89152,
    ),
)
MASTER_PACKAGE = "/Game/Generated/YACS/SaCalobra/WholeMapPreparation"
MASTER = MASTER_PACKAGE + "/M_SaCalobraWholeMapPreparation"
INSTANCE = MASTER_PACKAGE + "/MI_SaCalobraWholeMapPreparation"
TARGETED_VIEWS = (
    "ground-0-0",
    "ground-1-1",
    "window-0023-forward-00000",
    "overview-north",
)
NEAR_VIEWS = ("near-landscape-1", "near-landscape-2", "near-landscape-3")
FAR_VIEWS = ("window-0181-forward-00004", "window-0077-reverse-00000")
SURVEY_FILE = "docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv"
NEAR_INPUTS = {
    "material-weights.png": "af16fc7c43ec8a3a3b2e000fe716232a3229fe0ac6b4e9708baae5842ef99f6c",
    "sample-availability.png": "9c9906268977a8f49ba20c194cecb101e8bb8c25c44b51ee30f66e7e88a7522a",
    "inference-kind.png": "cc3bc3490878c5a96c20586cd28b0cd3cc812c5506ae97a7110c59e6ed3a3176",
    "exclusion-reasons.png": "f1adb0c0e8fc3fecba53cfaf033f9d33c0784ab4c7f0ecb0d661629d3b35494e",
    "exclusion-reasons.tif": "c74bde6ae8589304fe3d52f4e1e20801b0fe5647de6ffbc268c9b2ca65eaa941",
}
NEAR_TARGETS = (
    (
        1961,
        96,
        (244, 0, 4, 0),
        "low_vegetation_appearance",
        "7f43e4a3d3152ab7114223b7b171c939c7d63d680a85b1f357d61b020a664869",
    ),
    (
        2048,
        121,
        (71, 162, 8, 0),
        "forest_litter_appearance",
        "23f3f4b09b7a73e1a25903fcacf83ce58aae637bf3b5f8daf951b30e822e23dc",
    ),
    (
        2048,
        1408,
        (19, 0, 94, 0),
        "mineral_rock_mixture",
        "f5acdf97f56515ff8d38d1e8991feeaf9238dbd7ddb24aee9d5d873262db0e28",
    ),
)
PREPARED_VIEWS = (
    tuple(f"ground-{x}-{y}" for x in range(3) for y in range(3))
    + (
        "window-0021-forward-00005",
        "window-0023-forward-00000",
        "dominant-wall",
        "overview-north",
        "overview-south",
        "seam-close",
        "seam-distant",
    )
    + NEAR_VIEWS
    + FAR_VIEWS
)
CAPTURE_PAIRS = (
    tuple((name, "baseline") for name in TARGETED_VIEWS + NEAR_VIEWS + FAR_VIEWS)
    + tuple((name, "prepared") for name in PREPARED_VIEWS)
    + tuple((name, "domains") for name in TARGETED_VIEWS)
    + tuple((name, "checker") for name in TARGETED_VIEWS + NEAR_VIEWS)
    + (("ground-1-1", "normal-near"), ("ground-1-1", "normal-far"))
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def read_bytes(path, limit=32 * 1024 * 1024):
    path = Path(path)
    for parent in (path, *path.parents):
        no_link(parent)
    require(
        path.is_file() and 0 < path.stat().st_size <= limit,
        "Missing or oversized bounded file: " + str(path),
    )
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    require(0 < len(data) <= limit, "Bounded file grew while reading: " + str(path))
    return data


def read_json(path, limit=4 * 1024 * 1024):
    value = json.loads(read_bytes(path, limit).decode("utf-8-sig"))
    require(isinstance(value, dict), "Expected JSON object: " + str(path))
    return value


def write_json(path, value):
    path = Path(path)
    require(not path.exists(), "Refusing to replace evidence: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
            "utf-8"
        )
    )


def relative_file(root, relative):
    require(
        isinstance(relative, str) and "\\" not in relative, "Non-POSIX evidence path"
    )
    pure = PurePosixPath(relative)
    require(
        not pure.is_absolute()
        and pure.parts
        and all(part not in ("", ".", "..") for part in pure.parts),
        "Unsafe evidence path",
    )
    require(pure.as_posix() == relative, "Non-canonical evidence path")
    path = Path(root) / pure
    for parent in (path, *path.parents):
        try:
            no_link(parent)
        except FileNotFoundError:
            # Output leaves may not exist yet. Existing ancestors and broken
            # symlinks are still checked before any directory or file creation.
            pass
    return path


def file_row(path, relative=None, limit=512 * 1024 * 1024):
    path = Path(path)
    for parent in (path, *path.parents):
        no_link(parent)
    require(
        path.is_file() and 0 < path.stat().st_size <= limit,
        "Missing or oversized proof dependency: " + str(path),
    )
    size, hashed = 0, hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            require(size <= limit, "Proof dependency grew beyond limit")
            hashed.update(block)
    return {
        "path": relative or path.name,
        "sha256": hashed.hexdigest(),
        "size_bytes": size,
    }


def verify_row(root, row, limit=32 * 1024 * 1024):
    require(isinstance(row, dict), "Invalid file inventory row")
    actual = file_row(relative_file(root, row.get("path")), row["path"], limit)
    require(
        all(actual[key] == row.get(key) for key in actual),
        "Artifact byte identity mismatch: " + row["path"],
    )
    return actual


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def exact_head(repo, expected):
    require(
        isinstance(expected, str) and re.fullmatch("[0-9a-f]{40}", expected),
        "Exact lowercase Git SHA required",
    )
    require(
        git(repo, "rev-parse", "HEAD").decode().strip() == expected,
        "Checkout exact head changed",
    )


def committed(repo, head, path, expected):
    spec = head + ":" + path
    size = int(git(repo, "cat-file", "-s", spec))
    require(0 < size < 32 * 1024 * 1024, "Unbounded committed source")
    data = git(repo, "cat-file", "blob", spec)
    require(
        len(data) == size and digest(data) == expected,
        "Pinned committed source changed: " + path,
    )
    return data


def refresh_committed_evidence(repo, head):
    """Restore three raw Git blobs after the isolated checkout is sanitized.

    Git can retain a former CRLF worktree and index stat data after a -text
    attribute migration. Validate every pinned blob and destination before
    writing, then refresh only those index entries without changing its tree.
    Callers retain the normal global clean-checkout gate.
    """
    repo = Path(repo)
    exact_head(repo, head)
    sources = []
    for relative, expected, size in COMMITTED_EVIDENCE:
        data = committed(repo, head, relative, expected)
        require(len(data) == size, "Pinned committed size changed: " + relative)
        sources.append((relative, data))

    head_tree = git(repo, "rev-parse", head + "^{tree}").decode().strip()
    index_before = git(repo, "write-tree").decode().strip()
    require(
        index_before == head_tree, "Pre-existing staged changes block evidence refresh"
    )

    prepared = []
    for relative, data in sources:
        path = relative_file(repo, relative)
        before = read_bytes(path)
        prepared.append((relative, data, before))

    rows = []
    for relative, data, before in prepared:
        path = relative_file(repo, relative)
        rewritten = before != data
        if rewritten:
            path.write_bytes(data)
        after = read_bytes(path)
        require(
            len(after) == len(data) and digest(after) == digest(data),
            "Committed evidence readback failed: " + relative,
        )
        rows.append(
            {
                "path": relative,
                "rewritten": rewritten,
                "before": {"size_bytes": len(before), "sha256": digest(before)},
                "after": {"size_bytes": len(after), "sha256": digest(after)},
            }
        )

    # Reconcile cached CRLF sizes even on a retry whose raw bytes are already
    # correct. The fixed path list and tree checks forbid staged content changes.
    git(repo, "add", "--", *(relative for relative, _ in sources))
    index_after = git(repo, "write-tree").decode().strip()
    require(index_after == head_tree, "Evidence index refresh changed the staged tree")
    for relative, data in sources:
        after = read_bytes(relative_file(repo, relative))
        require(
            len(after) == len(data) and digest(after) == digest(data),
            "Evidence bytes changed during index refresh: " + relative,
        )
    exact_head(repo, head)
    return {
        "status": "COMMITTED_EVIDENCE_REFRESHED",
        "exact_sha": head,
        "rewritten_files": sum(row["rewritten"] for row in rows),
        "head_tree": head_tree,
        "index_tree_before": index_before,
        "index_tree_after": index_after,
        "index_refreshed_files": len(sources),
        "files": rows,
    }


def prepare_native(repo, source, root, head):
    """Copy only retained v8 donors; the old candidate is validation-only."""
    from scripts.assets.prepare_sa_calobra_detail_treatment import prepare

    exact_head(repo, head)
    source, root = Path(source), Path(root)
    bundle = root / "native-input"
    require(not bundle.exists(), "Native input bundle already exists")
    retained = read_json(source / ".yacs-retention/manifest.json", 16 * 1024 * 1024)
    require(
        retained.get("status") == "LOCAL_RETAINED"
        and retained.get("exact_sha") == CAPTURE
        and retained.get("run_id") == 37800814004
        and retained.get("attempt") == 1
        and retained.get("source_preserved") is True
        and retained.get("destination_verified") is True,
        "Completed retained source identity is required",
    )
    rows = retained.get("inventory", {}).get("files", [])
    require(
        rows and len({row["path"] for row in rows}) == len(rows),
        "Duplicate or absent retained source inventory",
    )
    inventory = {row["path"]: row for row in rows}
    entries, records = {}, []
    for relative, destination, sha in NATIVE_FIXED:
        row = inventory.get(relative, {})
        require(row.get("sha256") == sha, "Retained native source hash changed")
        verify_row(source, row)
        entries[destination] = read_bytes(source / relative)
        records.append({key: row[key] for key in ("path", "sha256", "size_bytes")})
    verify_retained_native(
        json.loads(entries["source/component230-cliff-visual-receipt.json"])
    )
    for relative, destination, sha in PINNED_COMMITTED:
        entries[destination] = committed(repo, head, relative, sha)
    frames = {
        row["frame_id"]: row
        for row in csv.DictReader(
            io.StringIO(entries["frames.csv"].decode("utf-8-sig"))
        )
    }
    ids = [row["frame_id"] for row in json.loads(entries["annotations.json"])["frames"]]
    require(
        ids == ["window-0021-forward-00005", "window-0023-forward-00000"],
        "Fixed annotated camera identity changed",
    )
    for frame_id in ids:
        row = frames[frame_id]
        require(
            row["file"] == "frames/" + frame_id + ".png",
            "Unexpected original frame path",
        )
        relative = "terrain-erosion-mesh/tpp-survey/" + row["file"]
        retained_row = inventory.get(relative, {})
        require(
            retained_row.get("sha256") == row["sha256"]
            and retained_row.get("size_bytes") == int(row["size_bytes"]),
            "Retained camera frame identity changed",
        )
        verify_row(source, retained_row)
        data = read_bytes(source / relative)
        require(
            data[:8] == b"\x89PNG\r\n\x1a\n"
            and struct.unpack(">II", data[16:24]) == (1280, 720),
            "Original camera image dimensions changed",
        )
        entries["source/" + frame_id + ".png"] = data
        records.append(
            {key: retained_row[key] for key in ("path", "sha256", "size_bytes")}
        )
    pilot = json.loads(entries["pilot/manifest.json"])
    require(
        pilot["mesh_sha256"] == MESH
        and pilot["frames_csv_sha256"] == FRAMES
        and pilot["annotations_sha256"] == digest(entries["annotations.json"]),
        "Published selection source binding changed",
    )
    bundle.mkdir()
    for name, data in entries.items():
        output = relative_file(bundle, name)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
    prepare(
        bundle / "source/combined-mesh.json",
        bundle / "pilot/triangle-bands.json",
        bundle / "treatment",
    )
    receipt = {
        "schema_version": 1,
        "status": "FIXED_RETAINED_SOURCE_VERIFIED",
        "exact_sha": head,
        "source_capture_sha": CAPTURE,
        "source_run_id": 37800814004,
        "source_attempt": 1,
        "source_root": str(source),
        "source_files": records,
        "bundle_files": [
            file_row(path, path.relative_to(bundle).as_posix())
            for path in sorted(bundle.rglob("*"))
            if path.is_file()
        ],
        "candidate_purpose": "Native helper validation only; no detail trial mode is authorized by this lane",
        "detail_trial_applied": False,
        "whole_archive_downloaded": False,
        "source_regenerated": False,
    }
    write_json(root / "native-source-verification.json", receipt)
    return receipt


def verify_assets(repo, root, head):
    exact_head(repo, head)
    paths = git(repo, "ls-files", "--", *ASSET_ROOTS).decode().splitlines()
    require(
        MAP in paths and len(paths) >= 230,
        "Accepted map dependency inventory is incomplete",
    )
    rows = []
    for path in paths:
        pointer = git(repo, "cat-file", "blob", head + ":" + path)
        match = re.fullmatch(
            rb"version https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n",
            pointer,
        )
        require(
            match is not None,
            "Accepted native dependency is not a tracked LFS object: " + path,
        )
        row = {"path": path, "sha256": match[1].decode(), "size_bytes": int(match[2])}
        verify_row(repo, row, 512 * 1024 * 1024)
        rows.append(row)
    require(
        next(row["sha256"] for row in rows if row["path"] == MAP) == MAP_SHA256,
        "Accepted map source identity changed",
    )
    receipt = {
        "schema_version": 1,
        "status": "TRACKED_NATIVE_ASSETS_VERIFIED",
        "exact_sha": head,
        "map_sha256": MAP_SHA256,
        "files": rows,
    }
    write_json(Path(root) / "native-assets-verification.json", receipt)
    return receipt


def verify_prepared(bundle):
    """Rebind actual payloads after preparation and again after native capture."""
    from scripts.assets.prepare_sa_calobra_whole_map_surface_prep import (
        EXCLUSION_REASONS,
        GRID,
        PILOT_MASK,
        PLACEMENT_MANIFEST,
        SOURCE_FINGERPRINT,
        SOURCE_PRODUCTS,
        WORLD_MAPPING,
    )

    bundle = Path(bundle)
    manifest = read_json(bundle / "surface-prep-manifest.json")
    require(
        manifest.get("status") == "WHOLE_MAP_MATERIAL_PREPARATION_CANDIDATE",
        "Whole-map source preparation did not pass",
    )
    fingerprint = digest(
        canonical(
            {key: value for key, value in manifest.items() if key != "fingerprint"}
        )
    )
    require(
        fingerprint == manifest.get("fingerprint"),
        "Prepared manifest fingerprint changed",
    )
    require(
        manifest.get("geometry_mutation") is False
        and manifest.get("current_cover_admitted") is False
        and manifest.get("production_planting") == "NOT_ADMITTED"
        and manifest.get("performance_admission") == "NOT_MEASURED",
        "Prepared candidate admission scope changed",
    )
    require(
        manifest.get("expected_landscape_component_count") == 1024
        and all(
            manifest.get("grid", {}).get(key) == value for key, value in GRID.items()
        )
        and manifest.get("world_mapping") == WORLD_MAPPING,
        "Whole-map grid inventory changed",
    )
    rows = manifest.get("outputs", [])
    require(
        len(rows) == 9 and len({row["path"] for row in rows}) == len(rows),
        "Prepared output inventory changed",
    )
    outputs = {row["path"]: verify_row(bundle, row) for row in rows}
    present = {
        path.relative_to(bundle).as_posix()
        for path in bundle.rglob("*")
        if path.is_file()
    }
    require(
        present == set(outputs) | {"surface-prep-manifest.json"},
        "Prepared bundle contains unregistered files",
    )
    sources = manifest.get("sources", {})
    require(
        set(sources)
        == {
            "material_weights",
            "sample_availability",
            "inference_kind",
            "material_manifest",
            "placement_manifest",
            "exclusion_reasons",
            "component230_mask",
        },
        "Prepared source roles changed",
    )
    for row in sources.values():
        actual = verify_row(bundle, row)
        require(
            outputs.get(row["path"]) == actual,
            "Prepared source is absent from complete output inventory",
        )
    pins = {
        **SOURCE_PRODUCTS,
        "placement_manifest": PLACEMENT_MANIFEST,
        "exclusion_reasons": EXCLUSION_REASONS,
        "component230_mask": PILOT_MASK,
    }
    for name, pin in pins.items():
        require(
            all(sources[name].get(key) == pin[key] for key in ("sha256", "size_bytes")),
            "Prepared source differs from pinned source: " + name,
        )
    material_source = read_json(bundle / sources["material_manifest"]["path"])
    require(
        material_source.get("fingerprint") == SOURCE_FINGERPRINT
        and digest(
            canonical(
                {
                    key: value
                    for key, value in material_source.items()
                    if key != "fingerprint"
                }
            )
        )
        == SOURCE_FINGERPRINT,
        "Original material manifest fingerprint changed",
    )
    require(
        digest(canonical(manifest.get("recipe"))) == manifest.get("recipe_sha256"),
        "Prepared recipe identity changed",
    )
    producer = ROOT / "scripts/assets/prepare_sa_calobra_whole_map_surface_prep.py"
    require(
        manifest.get("producer_file") == producer.relative_to(ROOT).as_posix()
        and manifest.get("producer_sha256_lf")
        == digest(producer.read_bytes().replace(b"\r\n", b"\n")),
        "Prepared producer identity changed",
    )
    return manifest, {
        "surface-prep-manifest.json": file_row(bundle / "surface-prep-manifest.json"),
        **outputs,
    }


def bind_prepared(root, placement):
    from scripts.assets.prepare_sa_calobra_whole_map_surface_prep import (
        EXCLUSION_REASONS,
        PLACEMENT_MANIFEST,
    )

    root, placement = Path(root), Path(placement)
    manifest, outputs = verify_prepared(root / "whole-map-prep")
    files = [
        verify_row(placement, pin) for pin in (PLACEMENT_MANIFEST, EXCLUSION_REASONS)
    ]
    receipt = {
        "schema_version": 1,
        "status": "WHOLE_MAP_SOURCE_BYTES_VERIFIED",
        "surface_manifest_fingerprint": manifest["fingerprint"],
        "prepared_files": list(outputs.values()),
        "placement_root": str(placement),
        "placement_files": files,
    }
    write_json(root / "surface-source-verification.json", receipt)
    return receipt


def object_path(package):
    return package + "." + package.rsplit("/", 1)[1]


def asset_path(repo, package):
    require(
        isinstance(package, str)
        and package.startswith("/Game/")
        and "." not in package,
        "Invalid native package path",
    )
    return relative_file(repo, "Content/" + package.removeprefix("/Game/") + ".uasset")


def verify_package_files(repo, row):
    """Require every emitted package member, including optional bulk sidecars."""
    repo = Path(repo)
    primary = asset_path(repo, row["asset"])
    require(
        primary.relative_to(repo).as_posix() == row.get("file"),
        "Generated material package mapping changed",
    )
    members = row.get("package_files", [])
    require(
        isinstance(members, list)
        and 1 <= len(members) <= 5
        and len({item.get("file") for item in members}) == len(members),
        "Generated package member inventory is missing or duplicated",
    )
    expected = set()
    result = []
    for item in members:
        path = relative_file(repo, item.get("file"))
        require(
            path.parent == primary.parent
            and path.name.startswith(primary.stem + ".")
            and path.name[len(primary.stem) :]
            in (".uasset", ".uexp", ".ubulk", ".uptnl", ".m.ubulk"),
            "Unexpected generated package sidecar",
        )
        expected.add(path.name)
        actual = verify_row(
            repo,
            {
                "path": item["file"],
                "sha256": item.get("sha256"),
                "size_bytes": item.get("size_bytes"),
            },
            512 * 1024 * 1024,
        )
        result.append(actual)
    require(
        {
            path.name
            for path in primary.parent.glob(primary.stem + ".*")
            if path.is_file()
        }
        == expected,
        "Generated package sidecar inventory is incomplete",
    )
    primary_row = next((item for item in result if item["path"] == row["file"]), None)
    require(
        primary_row is not None
        and primary_row["sha256"] == row.get("sha256")
        and primary_row["size_bytes"] == row.get("size_bytes"),
        "Generated package primary member identity changed",
    )
    return result


def retain_master(repo, root, head):
    repo, root = Path(repo), Path(root)
    exact_head(repo, head)
    master = read_json(root / "whole-map-master-receipt.json")
    require(
        master.get("status") == "WHOLE_MAP_FIXED_MASTER_SAVED"
        and master.get("exact_sha") == head,
        "Cannot retain an unverified or stale material bootstrap",
    )
    rows = master.get("generated_assets", [])
    require(
        len(rows) == 3
        and {row.get("asset") for row in rows}
        == {MASTER, INSTANCE, MASTER_PACKAGE + "/T_WholeMapWeights"},
        "Unexpected generated package scope",
    )
    destination = root / "generated-assets"
    require(not destination.exists(), "Refusing to replace retained material packages")
    destination.mkdir()
    files = []
    for row in rows:
        for original in verify_package_files(repo, row):
            source = repo / original["path"]
            target = destination / source.name
            require(not target.exists(), "Duplicate retained package member")
            shutil.copyfile(source, target)
            retained = file_row(target, target.relative_to(root).as_posix())
            require(
                retained["sha256"] == original["sha256"]
                and retained["size_bytes"] == original["size_bytes"],
                "Retained package bytes differ from generated material",
            )
            files.append(
                dict(retained, asset=row["asset"], source_file=original["path"])
            )
    receipt = {
        "schema_version": 1,
        "status": "GENERATED_MATERIAL_PACKAGES_RETAINED",
        "exact_sha": head,
        "master_receipt_sha256": file_row(root / "whole-map-master-receipt.json")[
            "sha256"
        ],
        "files": files,
        "source_preserved": True,
        "destination_verified": True,
    }
    write_json(root / "generated-assets-verification.json", receipt)
    return receipt


def verify_memory_checkpoints(checkpoints, expected):
    require(
        isinstance(checkpoints, list)
        and [row.get("stage") for row in checkpoints] == [row[0] for row in expected],
        "Required memory checkpoints are missing or reordered",
    )
    for row, (stage, physical, commit) in zip(checkpoints, expected):
        require(
            row.get("status") == "PASS"
            and row.get("minimum_free_physical_gib") == physical
            and row.get("minimum_free_commit_gib") == commit,
            "Established memory gate thresholds changed",
        )
        for name, limit in (("free_physical", physical), ("free_commit", commit)):
            value = row.get("memory", {}).get(name)
            require(
                type(value) in (int, float)
                and math.isfinite(value)
                and value >= limit * 1024**3,
                "Insufficient memory was admitted at " + stage,
            )


def verify_material_bindings(proof, bindings):
    require(
        bindings.get("status") == "ALL_NATIVE_ROOTS_MATCH"
        and bindings.get("component_count") == 1024
        and bindings.get("expected_component_count") == 1024
        and bindings.get("includes_hidden_component230") is True
        and bindings.get("verified_again_after_captures") is True,
        "Whole-map native binding summary is incomplete",
    )
    require(
        bindings.get("expected_root_material") == object_path(MASTER)
        and bindings.get("assigned_instance") == object_path(INSTANCE),
        "Wrong native master or assigned instance",
    )
    require(
        bindings.get("file") == "landscape-material-bindings.json",
        "Unexpected native binding evidence path",
    )
    payload = read_bytes(relative_file(proof, bindings["file"]), 8 * 1024 * 1024)
    require(
        digest(payload) == bindings.get("sha256"), "Native binding file hash changed"
    )
    rows = json.loads(payload)
    require(
        isinstance(rows, list) and len(rows) == 1024,
        "Actual native material inventory is not 1024 components",
    )
    names = set()
    for row in rows:
        name = row.get("component", "")
        require(
            isinstance(name, str)
            and name.startswith("/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.")
            and name not in names,
            "Duplicate or unrelated native component",
        )
        names.add(name)
        require(
            row.get("all_instances_match") is True
            and row.get("override_is_none") is True
            and row.get("expected_material") == object_path(MASTER)
            and row.get("assigned_instance") == object_path(INSTANCE),
            "Native Landscape parent chain or override mismatch",
        )
        counts = [
            row.get(key)
            for key in (
                "MaterialInstances",
                "MaterialInstancesDynamic",
                "render_instance_count",
            )
        ]
        require(
            all(
                type(value) in (int, float)
                and math.isfinite(value)
                and int(value) == value
                and value >= 0
                for value in counts
            )
            and counts[0] > 0
            and counts[2] > 0
            and counts[0] + counts[1] == counts[2],
            "Native rendered instance arrays are missing or inconsistent",
        )
    require(
        any(name.endswith("LandscapeComponent_230") for name in names),
        "Hidden source component230 was omitted",
    )
    return names


def decode_near_windows(data):
    """Read all 289 cells per target from the current prepared raster bytes."""
    from PIL import Image
    from rasterio.io import MemoryFile
    from rasterio.windows import Window

    windows = [[] for _ in NEAR_TARGETS]
    modes = (
        ("material-weights.png", "RGBA"),
        ("sample-availability.png", "L"),
        ("inference-kind.png", "L"),
        ("exclusion-reasons.png", "L"),
    )
    for name, mode in modes:
        with Image.open(io.BytesIO(data[name])) as raster:
            require(
                raster.format == "PNG"
                and raster.mode == mode
                and raster.size == (4033, 4033),
                "Near source raster format/grid changed: " + name,
            )
            for target, parts in zip(NEAR_TARGETS, windows):
                row, column = target[:2]
                parts.append(
                    raster.crop((column - 8, row - 8, column + 9, row + 9)).tobytes()
                )
    with MemoryFile(data["exclusion-reasons.tif"]) as memory, memory.open() as raster:
        require(
            raster.count == 1
            and raster.dtypes == ("uint16",)
            and raster.width == raster.height == 4033
            and raster.crs is not None
            and raster.crs.to_epsg() == 25831
            and tuple(raster.transform)[:6] == (0.5, 0, 483000, 0, -0.5, 4409516.5)
            and raster.nodata == 65535,
            "Near source exclusion georeferencing or uint16 contract changed",
        )
        for target, parts in zip(NEAR_TARGETS, windows):
            row, column = target[:2]
            reasons = raster.read(1, window=Window(column - 8, row - 8, 17, 17))
            require(
                reasons.shape == (17, 17)
                and bool((reasons == 0).all())
                and reasons.astype("uint8").tobytes() == parts[3],
                "Near source TIFF/PNG exclusion window is not entirely zero",
            )
    probes = []
    for target, parts in zip(NEAR_TARGETS, windows):
        row, column, _, role, _ = target
        weights, availability, inference, reasons = parts
        require(
            len(weights) == 289 * 4
            and availability == bytes([255]) * 289
            and inference == reasons == bytes(289),
            "Near source requires availability255/inference0/exclusion0 over the full17x17 window",
        )
        probes.append(
            {
                "row": row,
                "column": column,
                "pixel_window": [column - 8, row - 8, 17, 17],
                "xy_cm": [column * 50, row * 50],
                "center_rgba": list(weights[144 * 4 : 145 * 4]),
                "purpose_role": role,
                "physical_demand_band": "UNASSIGNED",
                "input_sha256": {name: digest(raw) for name, raw in data.items()},
                "halo_data_sha256": dict(
                    zip(
                        (
                            "material_weights_rgba8",
                            "availability_l8",
                            "inference_l8",
                            "exclusion_reasons_l8",
                        ),
                        map(digest, parts),
                    )
                ),
                "support": {
                    "cells": 289,
                    "availability255_cells": 289,
                    "inference0_cells": 289,
                    "exclusion0_cells": 289,
                    "basis": "Pinned raster identity and independently decoded CPU windows",
                },
            }
        )
    return probes


def read_near_probes(bundle, products):
    """Pin the same bytes that are decoded; no producer summary can admit a halo."""
    data = {}
    for name, expected in NEAR_INPUTS.items():
        raw = read_bytes(relative_file(bundle, name))
        require(
            digest(raw) == expected
            and products.get(name)
            == {"path": name, "sha256": expected, "size_bytes": len(raw)},
            "Near source byte identity differs from the current prepared bundle: "
            + name,
        )
        data[name] = raw
    probes = decode_near_windows(data)
    for probe, (_, _, rgba, _, halo_sha) in zip(probes, NEAR_TARGETS):
        require(
            probe["center_rgba"] == list(rgba)
            and probe["halo_data_sha256"]["material_weights_rgba8"] == halo_sha,
            "Near material target differs from its independently audited source window",
        )
    return probes


def read_original_survey_views(path):
    """Resolve B/C observations from the retained raw Git blob, not the live checkout."""
    data = read_bytes(path, 4 * 1024 * 1024)
    require(digest(data) == FRAMES, "Pinned original survey CSV byte identity changed")
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    views = {}
    for name, index, card, band in (
        (FAR_VIEWS[0], 661, "SC-P04", "B"),
        (FAR_VIEWS[1], 1088, "SC-P06", "C"),
    ):
        matches = [row for row in rows if row.get("frame_id") == name]
        require(
            len(matches) == 1 and int(matches[0]["index"]) == index,
            "Pinned B/C observation identity changed",
        )
        row = matches[0]
        require(
            float(row["fov_deg"]) == 76
            and [int(row[key]) for key in ("width_px", "height_px")] == [1280, 720]
            and row["file"] == "frames/" + name + ".png"
            and re.fullmatch("[0-9a-f]{64}", row["sha256"]),
            "Pinned B/C observation camera contract changed",
        )
        views[name] = {
            "camera": json.loads(row["camera_location_cm"]),
            "target": json.loads(row["target_cm"]),
            "fov": float(row["fov_deg"]),
            "survey_source": {
                "file": SURVEY_FILE,
                "sha256": FRAMES,
                "frame_id": name,
                "index": index,
                "original_png_sha256": row["sha256"],
                "original_resolution": [1280, 720],
                "review_card": card,
                "proposal_band": band,
                "physical_surface_registered": False,
            },
        }
    return views


def finite_vector(value):
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(
            type(number) in (int, float) and math.isfinite(number) for number in value
        )
    )


def verify_near_trace(trace, start, end):
    require(isinstance(trace, dict), "Near Landscape trace metadata is missing")
    require(
        all(finite_vector(trace.get(key)) for key in ("start_cm", "end_cm", "hit_cm"))
        and trace["start_cm"] == start
        and trace["end_cm"] == end
        and "owner_excluded_control_hit_cm" in trace
        and trace["owner_excluded_control_hit_cm"] is None,
        "Near Landscape trace endpoints or owner-excluded control changed",
    )
    hit = trace["hit_cm"]
    direction = [b - a for a, b in zip(start, end)]
    squared = sum(value * value for value in direction)
    require(squared > 0, "Near Landscape trace has no length")
    parameter = sum((p - a) * d for p, a, d in zip(hit, start, direction)) / squared
    residual = sum(
        (p - a - parameter * d) ** 2 for p, a, d in zip(hit, start, direction)
    )
    require(
        1e-6 < parameter < 1 - 1e-6 and residual <= 1.0,
        "Near Landscape hit is not an interior point on the recorded native trace",
    )
    return hit


def verify_near_view(frame, source, owner):
    require(
        frame.get("kind") == "source_grid_landscape_near"
        and frame.get("source_probe") == source,
        "Near Landscape source probe differs from decoded prepared inputs",
    )
    probe = frame.get("landscape_probe", {})
    actors, ignored = probe.get("world_actor_paths"), probe.get("ignored_actor_paths")
    require(
        isinstance(owner, str)
        and owner
        and probe.get("owner_path") == owner
        and isinstance(actors, list)
        and actors
        and all(isinstance(path, str) and path for path in actors)
        and actors == sorted(set(actors))
        and owner in actors
        and ignored == [path for path in actors if path != owner],
        "Near Landscape collision owner or ignored actor inventory changed",
    )
    require(
        probe.get("nominal_camera_offset_cm") == [100, 0, 250]
        and probe.get("rendered_pixel_depth_verified") is False,
        "Near Landscape range recipe or collision-versus-rendered-depth scope changed",
    )
    x, y = source["xy_cm"]
    target = verify_near_trace(
        probe.get("target_trace"), [x, y, 150000], [x, y, -150000]
    )
    eye_ground = verify_near_trace(
        probe.get("eye_ground_trace"), [x + 100, y, 150000], [x + 100, y, -150000]
    )
    camera = [x + 100, y, max(target[2] + 250, eye_ground[2] + 150)]
    distance = math.dist(camera, target)
    require(
        frame.get("target") == target
        and target[:2] == [x, y]
        and eye_ground[:2] == [x + 100, y]
        and frame.get("camera") == camera
        and frame.get("fov") == 60.0
        and 100 <= distance <= 500,
        "Near Landscape target/camera no longer has the source-bound1..5m placement",
    )
    end = [value + 25 * (value - eye) / distance for value, eye in zip(target, camera)]
    hit = verify_near_trace(probe.get("aim_trace"), camera, end)
    hit_distance = math.dist(camera, hit)
    require(
        100 <= hit_distance <= 500
        and all(abs(hit[axis] - value) <= 400 for axis, value in enumerate((x, y))),
        "Near Landscape aim hit leaves the1..5m range or audited17x17 source window",
    )
    for key, expected in (
        ("camera_clearance_cm", camera[2] - eye_ground[2]),
        ("target_distance_cm", distance),
        ("hit_distance_cm", hit_distance),
    ):
        actual = probe.get(key)
        require(
            type(actual) in (int, float)
            and math.isfinite(actual)
            and abs(actual - expected) <= 1e-6,
            "Near Landscape native distance readback changed: " + key,
        )
    return probe


def verify_capture_plan(report, pilot, near_probes, survey_views):
    plan, captures = report.get("capture_plan", []), report.get("captures", [])
    require(
        isinstance(near_probes, list)
        and len(near_probes) == 3
        and tuple(survey_views) == FAR_VIEWS,
        "Independently verified near/B/C source coverage is missing",
    )
    for rows, label in ((plan, "plan"), (captures, "captures")):
        require(
            isinstance(rows, list)
            and tuple((row.get("frame_id"), row.get("mode")) for row in rows)
            == CAPTURE_PAIRS,
            "Whole-map ordered " + label + " inventory changed",
        )
    require(
        digest(canonical(plan)) == report.get("capture_plan_sha256"),
        "Capture plan hash changed",
    )
    near = dict(zip(NEAR_VIEWS, near_probes))
    native_probes = report.get("near_landscape_probes", [])
    require(
        isinstance(native_probes, list)
        and [row.get("frame_id") for row in native_probes] == list(NEAR_VIEWS),
        "Native near Landscape probe inventory is incomplete",
    )
    owner = report.get("source_scene", {}).get("landscape_actor_path")
    poses = {}
    for frame, capture in zip(plan, captures):
        identity = frame["frame_id"]
        camera, target, fov = frame.get("camera"), frame.get("target"), frame.get("fov")
        for vector in (camera, target, capture.get("camera_rotation_deg")):
            require(
                isinstance(vector, list)
                and len(vector) == 3
                and all(
                    type(value) in (float, int) and math.isfinite(value)
                    for value in vector
                ),
                "Invalid native camera vector",
            )
        require(
            type(fov) in (int, float) and math.isfinite(fov) and 1 < fov < 179,
            "Invalid native camera field of view",
        )
        pose = {"camera": camera, "target": target, "fov": fov}
        require(
            identity not in poses or poses[identity] == pose,
            "Matched capture pose changed between material modes",
        )
        poses[identity] = pose
        require(
            capture.get("camera_location_cm") == camera
            and capture.get("target_cm") == target
            and capture.get("fov_deg") == fov
            and capture.get("resolution") == [1920, 1080]
            and frame.get("resolution") == [1920, 1080],
            "Captured camera differs from admitted plan",
        )
        require(
            capture.get("kind") == frame.get("kind")
            and capture.get("viewmode") == "lit"
            and capture.get("dynamic_shadows") is True,
            "Whole-map lighting mode or view purpose changed",
        )
        distance = math.dist(camera, target)
        require(
            type(capture.get("target_distance_cm")) in (int, float)
            and abs(capture["target_distance_cm"] - distance) <= 1e-6,
            "Native camera distance evidence changed",
        )
        if identity in near:
            probe = verify_near_view(frame, near[identity], owner)
            require(
                capture.get("source_probe") == near[identity]
                and capture.get("landscape_probe") == probe
                and native_probes[NEAR_VIEWS.index(identity)]
                == {
                    "frame_id": identity,
                    "source_probe": near[identity],
                    "landscape_probe": probe,
                },
                "Near source/trace evidence changed between native probe, plan and admitted capture",
            )
        if identity in survey_views:
            original = survey_views[identity]
            require(
                pose == {key: original[key] for key in ("camera", "target", "fov")}
                and frame.get("kind") == "pinned_original_survey"
                and frame.get("survey_source") == original["survey_source"]
                and capture.get("survey_source") == original["survey_source"],
                "Pinned original B/C survey pose or provenance changed",
            )
    require(
        all(
            row["landscape_probe"]["world_actor_paths"]
            == native_probes[0]["landscape_probe"]["world_actor_paths"]
            for row in native_probes
        ),
        "Native near Landscape probes use different actor inventories",
    )
    for frame in pilot["frames"]:
        require(
            poses.get(frame["frame_id"])
            == {key: frame[key] for key in ("camera", "target", "fov")},
            "Pinned rider pose changed",
        )
    for x, x_cm in enumerate((25000, 100000, 175000)):
        for y, y_cm in enumerate((25000, 100000, 175000)):
            pose = poses[f"ground-{x}-{y}"]
            require(
                pose["target"][:2] == [x_cm, y_cm]
                and pose["camera"][:2] == [x_cm - 3000, y_cm - 4000],
                "Distributed whole-grid target coverage changed",
            )
    seam = report.get("source_scene", {}).get("seam_probe", {})
    require(
        seam.get("original_source_delta_cm") == 0
        and seam.get("defect_admitted") is False
        and seam.get("boundary_xy_cm") == [37800, 44100, 44100, 50400],
        "Retained seam probe scope changed",
    )
    for name, scale in (("seam-close", 1), ("seam-distant", 8)):
        pose = poses[name]
        require(
            pose["target"] == seam.get("target_cm")
            and all(
                abs(pose["camera"][axis] - pose["target"][axis] - scale * offset) < 1e-6
                for axis, offset in enumerate((1800, 1200))
            ),
            "Close and distant seam views no longer target the same exact boundary",
        )
    return captures


def verify_capture_files(proof, captures):
    from PIL import Image

    files = []
    for capture in captures:
        relative = "frames/" + capture["frame_id"] + "-" + capture["mode"] + ".png"
        require(capture.get("file") == relative, "Unexpected admitted frame path")
        path = relative_file(proof, relative)
        row = verify_row(
            proof,
            {
                "path": relative,
                "sha256": capture.get("sha256"),
                "size_bytes": capture.get("size_bytes"),
            },
            24 * 1024 * 1024,
        )
        require(row["size_bytes"] >= 10000, "Invalid bounded native screenshot")
        with Image.open(path) as picture:
            require(
                picture.format == "PNG" and picture.size == (1920, 1080),
                "Native screenshot dimensions or format changed",
            )
            picture.verify()
        readiness = capture.get("readiness", {})
        expected = (
            "readiness/"
            + capture["frame_id"]
            + "-"
            + capture["mode"]
            + "/capture-readiness.json"
        )
        require(
            readiness.get("file") == expected
            and readiness.get("status") == "NATIVE_LOADING_AND_MIPS_READY",
            "Capture loading barrier is incomplete",
        )
        data = read_bytes(relative_file(proof, expected), 4 * 1024 * 1024)
        require(
            digest(data) == readiness.get("sha256"),
            "Capture readiness byte binding changed",
        )
        detail = json.loads(data)
        require(
            detail.get("status") == "NATIVE_LOADING_AND_MIPS_READY"
            and detail.get("height_mip_lease_requested") is True
            and detail.get("saved_to_map") is False
            and detail.get("height_edits_applied") is False,
            "Capture readiness did not preserve source geometry",
        )
        textures = detail.get("textures_after", [])
        require(
            textures
            and all(
                row.get("is_default_texture") is False
                and row.get("is_compiling") is False
                and type(row.get("mips")) in (int, float)
                and row["mips"] > 0
                and row.get("resident_mips") == row["mips"]
                for row in textures
            ),
            "Native Landscape height texture readiness failed",
        )
        files.extend((row, file_row(relative_file(proof, expected), expected)))
    actual = {
        path.relative_to(proof).as_posix()
        for path in (Path(proof) / "frames").glob("*")
        if path.is_file()
    }
    require(
        actual == {capture["file"] for capture in captures},
        "Unregistered primary capture files exist",
    )
    return files


def verify_normal_response(proof, report):
    from scripts.ue.capture_sa_calobra_whole_map_prep import paired_normal_response
    from scripts.ue.sa_calobra_detail_capture import decode_png

    pair = [
        next(row for row in report["captures"] if row["mode"] == mode)
        for mode in ("normal-near", "normal-far")
    ]
    response = paired_normal_response(
        *(decode_png(relative_file(proof, row["file"]), (1920, 1080)) for row in pair)
    )
    response["files"] = [{"file": row["file"], "sha256": row["sha256"]} for row in pair]
    require(
        response == report.get("near_far_material_response"),
        "Rendered near/far shading observation is absent or differs from admitted PNGs",
    )
    return response


def verify_native_evidence(repo, root, head):
    from scripts.ue.capture_sa_calobra_whole_map_prep import mode_parameters
    from scripts.ue.sa_calobra_whole_map_prep import (
        SCALARS,
        near_detail_factor,
        rendering_recipe,
    )

    repo, root = Path(repo), Path(root)
    exact_head(repo, head)
    manifest, products = verify_prepared(root / "whole-map-prep")
    surface = read_json(root / "surface-source-verification.json")
    require(
        surface.get("status") == "WHOLE_MAP_SOURCE_BYTES_VERIFIED"
        and surface.get("surface_manifest_fingerprint") == manifest["fingerprint"]
        and {row["path"]: row for row in surface.get("prepared_files", [])} == products,
        "Prepared material source changed after preflight",
    )
    proof = root / "capture/whole-map-prep"
    report = read_json(proof / "whole-map-prep-receipt.json", 8 * 1024 * 1024)
    require(
        report.get("status") == "WHOLE_MAP_PREPARATION_PASS"
        and report.get("exact_sha") == head
        and report.get("capture_complete") is True
        and report.get("fresh_process_master_verified") is True
        and report.get("error") is None,
        "Whole-map native proof did not complete at exact HEAD: "
        + json.dumps(
            {
                "status": report.get("status"),
                "exact_sha": report.get("exact_sha"),
                "capture_complete": report.get("capture_complete"),
                "capture_count": len(report.get("captures", [])),
                "native_error": report.get("error"),
            }
        ),
    )
    expected_hashes = {
        path: row["sha256"]
        for path, row in products.items()
        if path != "surface-prep-manifest.json"
    }
    require(
        report.get("inputs_sha256") == expected_hashes
        and report.get("prep_manifest_sha256")
        == products["surface-prep-manifest.json"]["sha256"],
        "Rendered full-grid input hash binding failed",
    )
    for key in (
        "native_trial_applied",
        "geometry_changed_by_preparation",
        "saved_to_map",
        "shader_cost_reduction_claimed",
    ):
        require(
            report.get(key) is False,
            "Native preparation exceeded its declared scope: " + key,
        )
    require(
        report.get("visual_acceptance") == "PENDING_OWNER"
        and report.get("performance_acceptance") == "NOT_MEASURED",
        "Preparation incorrectly claims final visual/performance acceptance",
    )
    source = report.get("source_scene", {})
    require(
        source.get("map") == "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
        and source.get("map_sha256") == MAP_SHA256
        and source.get("cliff_recipe") == "rounded-limestone-reshape-v8"
        and source.get("retained_source_capture_sha") == CAPTURE
        and source.get("other_scene_actors_retained") is True,
        "Accepted native source scene identity changed",
    )
    require(
        file_row(repo / MAP)["sha256"] == MAP_SHA256, "Native source map bytes changed"
    )

    master = read_json(root / "whole-map-master-receipt.json")
    require(
        master.get("status") == "WHOLE_MAP_FIXED_MASTER_SAVED"
        and master.get("exact_sha") == head
        and master.get("master") == MASTER
        and master.get("instance") == INSTANCE
        and master.get("prep_manifest_sha256") == report["prep_manifest_sha256"]
        and report.get("master_receipt_sha256")
        == file_row(root / "whole-map-master-receipt.json")["sha256"],
        "Fresh fixed master receipt binding failed",
    )
    recipe = rendering_recipe()
    require(
        master.get("rendering_recipe") == recipe
        and report.get("rendering_recipe") == recipe
        and master.get("rendering_recipe_sha256") == digest(canonical(recipe))
        and recipe.get("scalar_defaults") == SCALARS
        and recipe.get("shader_cost_reduction_claimed") is False,
        "Rendered material recipe changed",
    )
    require(
        master.get("map_loaded") is False
        and master.get("map_saved") is False
        and master.get("geometry_changed") is False,
        "Master bootstrap unexpectedly loaded or mutated the scene",
    )
    bootstrap = master.get("bootstrap_world", {})
    require(
        bootstrap.get("package") == "/Engine/Maps/Entry"
        and bootstrap.get("landscape_actor_count") == 0
        and bootstrap.get("landscape_component_count") == 0
        and bootstrap.get("isolated") is True
        and master.get("working_map_loaded") is False
        and master.get("engine_entry_map_loaded") is True,
        "Master bootstrap did not verify an empty engine Entry world",
    )
    api = read_json(root / "native-api-evidence.json")
    require(
        api.get("status") == "INSTALLED_PRIMARY_API_SOURCE_VERIFIED"
        and api.get("exact_sha") == head
        and api.get("engine_version") == "5.8.2-56702186"
        and api.get("startup_map") == "/Engine/Maps/Entry"
        and re.fullmatch("[0-9a-f]{64}", api.get("startup_map_sha256", "")),
        "Installed Entry map and material API evidence is incomplete",
    )
    verify_memory_checkpoints(
        master.get("memory_checkpoints"), (("before_preparation", 8, 12),)
    )
    verify_memory_checkpoints(
        report.get("memory_checkpoints"),
        (("before_preparation", 8, 12), ("before_all1024_binding", 6, 8)),
    )
    drain = master.get("compile_drain", {})
    require(
        drain.get("ok") is True
        and drain.get("remaining_after") == 0
        and drain.get("shader_jobs_after") == 0,
        "Fixed master compilation is incomplete",
    )
    textures = master.get("texture_readbacks", [])
    require(
        len(textures) == 11
        and all(
            row.get("is_default_texture") is False and row.get("is_compiling") is False
            for row in textures
        ),
        "Fixed master texture readback detected fallback",
    )
    generated = master.get("generated_assets", [])
    require(
        len(generated) == 3
        and {row.get("asset") for row in generated}
        == {MASTER, INSTANCE, MASTER_PACKAGE + "/T_WholeMapWeights"},
        "Unexpected generated package scope",
    )
    package_members = {
        member["path"]: dict(member, asset=row["asset"])
        for row in generated
        for member in verify_package_files(repo, row)
    }
    retained = read_json(root / "generated-assets-verification.json")
    require(
        retained.get("status") == "GENERATED_MATERIAL_PACKAGES_RETAINED"
        and retained.get("exact_sha") == head
        and retained.get("master_receipt_sha256") == report["master_receipt_sha256"]
        and retained.get("source_preserved") is True
        and retained.get("destination_verified") is True,
        "Reusable saved material package evidence is missing",
    )
    retained_rows = retained.get("files", [])
    require(
        len(retained_rows) == len(package_members)
        and len({row.get("path") for row in retained_rows}) == len(retained_rows)
        and {row.get("source_file") for row in retained_rows} == set(package_members),
        "Retained material package inventory changed",
    )
    for row in retained_rows:
        actual = verify_row(root, row, 512 * 1024 * 1024)
        original = package_members[row["source_file"]]
        require(
            actual["sha256"] == original["sha256"]
            and actual["size_bytes"] == original["size_bytes"]
            and row.get("asset") == original["asset"],
            "Reusable material packages differ from the captured master",
        )
    assets = {
        row["path"]: row
        for row in read_json(root / "native-assets-verification.json")["files"]
    }
    source_assets = master.get("source_assets", {})
    require(
        set(source_assets)
        == {"DryGrass", "ForestLitter", "ExposedRock", "DryMineral", "Scree"},
        "Material source role inventory changed",
    )
    for role, channels in source_assets.items():
        require(
            set(channels) == {"BaseColor", "Normal"},
            "Material source channel inventory changed",
        )
        for channel, row in channels.items():
            suffix = (
                "Sources/T_Source_" + role
                if channel == "BaseColor"
                else "ProviderData/" + role + "/T_Normal"
            )
            relative = LIBRARY + "/" + suffix + ".uasset"
            require(
                row
                == {
                    "asset": "/Game/"
                    + relative.removeprefix("Content/").removesuffix(".uasset"),
                    "file": relative,
                    "sha256": assets[relative]["sha256"],
                    "size_bytes": assets[relative]["size_bytes"],
                },
                "Native material source differs from committed asset inventory",
            )
            verify_row(repo, assets[relative], 512 * 1024 * 1024)

    native_bundle = root / "native-input"
    source_binding = read_json(root / "native-source-verification.json")
    require(
        source_binding.get("status") == "FIXED_RETAINED_SOURCE_VERIFIED"
        and source_binding.get("exact_sha") == head,
        "Native donor binding is missing",
    )
    for row in source_binding["bundle_files"]:
        verify_row(native_bundle, row)
    paths = {
        "source": "source/combined-mesh.json",
        "mask": "pilot/triangle-bands.json",
        "pilot": "pilot/manifest.json",
        "trial": "treatment/treatment-mesh.json",
        "manifest": "treatment/treatment-manifest.json",
    }
    native_hashes = {
        key: file_row(native_bundle / path)["sha256"] for key, path in paths.items()
    }
    require(
        report.get("native_inputs_sha256") == native_hashes
        and native_hashes["source"] == MESH,
        "Rendered v8 donor hash binding failed",
    )
    vertices = read_json(native_bundle / paths["source"], 32 * 1024 * 1024)[
        "vertices_cm"
    ]
    edge = [row for row in vertices if abs(row[4] - 44100.0) < 1e-6]
    require(edge, "Retained v8 east boundary is missing")
    seam = min(edge, key=lambda row: (abs(row[5] - 47250.0), row[0]))
    require(
        source.get("seam_probe", {}).get("source_vertex_id") == seam[0]
        and source["seam_probe"].get("target_cm") == seam[4:7]
        and seam[1:4] == seam[4:7],
        "Seam camera target differs from the unchanged retained source vertex",
    )
    candidate = read_json(native_bundle / paths["manifest"])
    native = report.get("native_source", {})
    require(
        native.get("status") == "DETAIL_NATIVE_SOURCE_VERIFIED"
        and native.get("source_mesh_sha256") == MESH
        and native.get("native_attributes_retained") is True
        and native.get("candidate_validated_but_not_applied") is True,
        "Native v8 source or preserved attributes were not verified",
    )
    for key in (
        "vertex_count",
        "triangle_count",
        "protected_face_count",
        "selected_face_count",
        "changed_vertex_count",
    ):
        require(
            type(candidate.get(key)) is int
            and candidate[key] > 0
            and native.get(key) == candidate[key],
            "Native v8 source inventory differs: " + key,
        )
    require(
        native.get("source_row_map_file") == "source-row-native-triangle-map.json",
        "Native source row-map path changed",
    )
    mapping_data = read_bytes(proof / native["source_row_map_file"])
    require(
        digest(mapping_data) == native.get("source_row_map_sha256"),
        "Native source row-map bytes changed",
    )
    mapping = json.loads(mapping_data)
    require(
        len(mapping) == 58216
        and len(set(mapping)) == 58216
        and all(type(value) is int and value >= 0 for value in mapping),
        "Native source mapping omits or repeats source faces",
    )
    modes = report.get("native_modes", [])
    require(
        tuple((row.get("frame_id"), row.get("landscape_mode")) for row in modes)
        == CAPTURE_PAIRS,
        "Native baseline guard was omitted for a capture",
    )
    for mode in modes:
        require(
            mode.get("status") == "DETAIL_NATIVE_MODE_APPLIED"
            and mode.get("mode") == "baseline"
            and mode.get("changed_vertices") == 0
            and mode.get("recomputed_normal_elements") == 0
            and mode.get("outside_or_shared_normal_max_delta") == 0
            and mode.get("native_uvs_unchanged") is True
            and mode.get("topology_unchanged") is True
            and mode.get("every_source_face_rendered_once") is True,
            "Whole-map preparation changed accepted native v8",
        )
    require(
        report.get("native_restore")
        == {
            "status": "DETAIL_NATIVE_RESTORED",
            "complete_native_snapshot_restored": True,
        },
        "Native complete snapshot restoration failed",
    )

    components = verify_material_bindings(proof, report.get("bindings", {}))
    require(
        {name.rsplit(".", 1)[0] for name in components}
        == {source.get("landscape_actor_path")},
        "Near probe owner differs from the1024 material-bound Landscape components",
    )
    environment = report.get("capture_environment", {})
    require(
        environment.get("restored") is True
        and environment.get("restore_errors") == []
        and environment.get("adaptive_during_capture") is True
        and environment.get("global_force_lod_during_capture") == -1
        and environment.get("component_auto_lod_count") == 1024
        and environment.get("geometry_lod_cost_measured") is False
        and set(environment.get("component_forced_lod_before", {})) == components,
        "Whole-map adaptive LOD or exact settings restoration failed",
    )
    cleanup = report.get("cleanup", {})
    require(
        cleanup.get("status") == "RESTORED"
        and all(
            cleanup.get(key) is True
            for key in (
                "source_map_hash_unchanged",
                "source_scene_snapshot_unchanged",
                "landscape_materials_restored",
                "capture_environment_restored",
            )
        )
        and report.get("separate_mesh_materials_preserved") is True,
        "Whole-map scene or material restoration failed",
    )
    near_probes = read_near_probes(root / "whole-map-prep", products)
    survey_views = read_original_survey_views(native_bundle / "frames.csv")
    captures = verify_capture_plan(
        report, read_json(native_bundle / paths["pilot"]), near_probes, survey_views
    )
    for capture in captures:
        require(
            capture.get("material_parameters") == mode_parameters(capture["mode"])
            and capture.get("automatic_target_detail_factor")
            == near_detail_factor(capture["target_distance_cm"]),
            "Independent distance-detail control changed",
        )
    files = verify_capture_files(proof, captures)
    from scripts.ci.sa_calobra_whole_map_visual_review import audit_near_views

    visual_review = audit_near_views(proof, captures, NEAR_VIEWS)
    visual_review_path = root / "whole-map-visual-anomaly-review.json"
    write_json(visual_review_path, visual_review)
    from scripts.ue.sa_calobra_whole_map_witness import audit_witnesses

    require(
        report.get("diagnostic_complete") is True,
        "Bounded same-camera visual witness is incomplete",
    )
    witness = audit_witnesses(proof, captures, report.get("diagnostic_captures", []))
    witness_file = root / "whole-map-normal-shadow-witness.json"
    write_json(witness_file, witness)
    response = verify_normal_response(proof, report)
    parent = read_json(
        root / "capture/component230-cliff-visual-receipt.json", 8 * 1024 * 1024
    )
    require(
        parent.get("status") == "COMPONENT230_CLIFF_VISUAL_PASS"
        and parent.get("exact_sha") == head
        and all(
            parent.get(key) is False
            for key in (
                "map_saved",
                "assets_saved",
                "canonical_landscape_mutation",
                "selector_policy_mutation",
            )
        ),
        "Owning source scene cleanup failed",
    )
    terrain = parent.get("terrain_erosion_trial", {})
    require(
        terrain.get("restored") is True
        and terrain.get("source_heightfield_unchanged") is True
        and terrain.get("terrain_import_performed") is False
        and terrain.get("derived_heightfield_modified") is False
        and terrain.get("mesh_export", {}).get("shape_profile")
        == "rounded-limestone-reshape-v8",
        "Owning source terrain restoration failed",
    )
    receipt = {
        "schema_version": 1,
        "status": "WHOLE_MAP_EVIDENCE_VERIFIED",
        "exact_sha": head,
        "surface_manifest_sha256": report["prep_manifest_sha256"],
        "surface_manifest_fingerprint": manifest["fingerprint"],
        "component_count": len(components),
        "primary_frame_count": len(captures),
        "diagnostic_witness": {
            "file": "whole-map-normal-shadow-witness.json",
            "sha256": digest(read_bytes(witness_file)),
            "frame_count": witness["frame_count"],
            "status": witness["status"],
            "visual_acceptance": "PENDING_OWNER",
        },
        "near_landscape_source_windows_verified": len(near_probes),
        "near_landscape_collision_range_cm": [100, 500],
        "near_landscape_rendered_pixel_depth_verified": False,
        "visual_anomaly_review": {
            "status": visual_review["status"],
            "flagged_views": visual_review["flagged_views"],
            "file": "whole-map-visual-anomaly-review.json",
            "sha256": digest(read_bytes(visual_review_path)),
            "visual_acceptance": "PENDING_OWNER",
        },
        "original_survey_csv_sha256": FRAMES,
        "original_survey_frame_ids": list(survey_views),
        "near_far_material_response": response,
        "native_trial_applied": False,
        "files": files,
        "visual_acceptance": "PENDING_OWNER",
        "performance_acceptance": "NOT_MEASURED",
        "checkout_conservation_gate": "Separate mandatory checkout-restoration.json",
    }
    write_json(root / "native-proof-verification.json", receipt)
    return receipt


def restore(repo, root, head):
    """Verify canonical bytes and retained source conservation even after failure."""
    repo, root = Path(repo), Path(root)
    errors = []
    try:
        exact_head(repo, head)
        dirty = (
            git(repo, "status", "--porcelain=v1", "--untracked-files=no")
            .decode()
            .splitlines()
        )
        require(not dirty, "Tracked checkout was mutated: " + "; ".join(dirty))
        untracked = (
            git(repo, "ls-files", "--others", "--exclude-standard")
            .decode()
            .splitlines()
        )
        require(
            all(
                path.startswith("Content/Generated/YACS/SaCalobra/WholeMapPreparation/")
                for path in untracked
            ),
            "Unexpected generated file outside isolated material package scope",
        )
        assets = read_json(root / "native-assets-verification.json")
        require(
            assets.get("exact_sha") == head
            and assets.get("status") == "TRACKED_NATIVE_ASSETS_VERIFIED",
            "Original native asset binding is missing",
        )
        for row in assets["files"]:
            verify_row(repo, row, 512 * 1024 * 1024)
        source = read_json(root / "native-source-verification.json")
        require(
            source.get("exact_sha") == head
            and source.get("status") == "FIXED_RETAINED_SOURCE_VERIFIED",
            "Original retained source binding is missing",
        )
        for row in source["source_files"]:
            verify_row(Path(source["source_root"]), row)
        for row in source["bundle_files"]:
            verify_row(root / "native-input", row)
        verify_prepared(root / "whole-map-prep")
        surface = read_json(root / "surface-source-verification.json")
        require(
            surface.get("status") == "WHOLE_MAP_SOURCE_BYTES_VERIFIED",
            "Original surface source binding is missing",
        )
        for row in surface["placement_files"]:
            verify_row(Path(surface["placement_root"]), row)
        for row in surface["prepared_files"]:
            verify_row(root / "whole-map-prep", row)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        errors.append(str(error))
    receipt = {
        "schema_version": 1,
        "exact_sha": head,
        "status": "PASS" if not errors else "FAIL",
        "map_sha256": MAP_SHA256,
        "tracked_checkout_unchanged": not errors,
        "retained_source_unchanged": not errors,
        "prepared_bundle_unchanged": not errors,
        "errors": errors,
    }
    write_json(root / "checkout-restoration.json", receipt)
    require(
        not errors,
        "Whole-map source/checkout conservation failed: " + "; ".join(errors),
    )
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "refresh-committed",
            "prepare-native",
            "verify-assets",
            "verify-prepared",
            "retain-master",
            "verify-native",
            "restore",
        ),
    )
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--exact-sha")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--placement", type=Path)
    args = parser.parse_args()
    if args.action == "refresh-committed":
        result = refresh_committed_evidence(args.repo, args.exact_sha)
    elif args.action == "prepare-native":
        require(args.source is not None, "Retained source root is required")
        result = prepare_native(args.repo, args.source, args.root, args.exact_sha)
    elif args.action == "verify-assets":
        result = verify_assets(args.repo, args.root, args.exact_sha)
    elif args.action == "verify-prepared":
        if args.placement is not None:
            result = bind_prepared(args.root, args.placement)
        else:
            manifest, _ = verify_prepared(args.root / "whole-map-prep")
            result = {
                "status": manifest["status"],
                "fingerprint": manifest["fingerprint"],
            }
    elif args.action == "verify-native":
        result = verify_native_evidence(args.repo, args.root, args.exact_sha)
    elif args.action == "retain-master":
        result = retain_master(args.repo, args.root, args.exact_sha)
    else:
        result = restore(args.repo, args.root, args.exact_sha)
    print(
        json.dumps(
            result
            if args.action == "refresh-committed"
            else {
                key: result[key]
                for key in ("status", "exact_sha", "fingerprint")
                if key in result
            }
        )
    )


if __name__ == "__main__":
    main()
