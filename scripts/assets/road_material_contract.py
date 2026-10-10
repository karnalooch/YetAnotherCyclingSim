"""Read-only source contract for aged_mountain_asphalt/dry_varied.

This verifies retained producer receipts and their bytes, including a separately
authenticated two-run record. It never renders, imports Unreal assets, or grants
visual admission.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import struct
from pathlib import Path, PureWindowsPath
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "worldgen/materials/material_forge/families.json"
FAMILY = "aged_mountain_asphalt"
VARIANT = "dry_varied"
SEED = 101
GENERATOR_VERSION = 5
STATUS = "MAP_CHECKS_PASS_UE_REVIEW_PENDING"
PARAMETERS = {
    "brightness": 0.31,
    "surface_a": 0.48,
    "surface_b": 0.90,
    "roughness": 0.94,
    "normal_strength": 0.24,
}
SURFACE_FIELD_SHA256 = "fe84f44f23e941d0e7df6b5d9129365b933c7eef4fe5faa3fd5fd83bd8054d71"
COLOR_CODE_SHA256 = "25366bc901d287ed1fd71da1072daf494da06fb35a6c69cf0ed2880f419b8af6"
COLOR_OUTPUT_SHA256 = "fc98416854b24483554e1bfa391504924ce1c779aa228200631a96e68f01b10d"
ROUGHNESS_EXPRESSION = (
    "clamp(0.940000+0.055000*($variation($uv)-0.5)"
    "+0.018000*$crack($uv)-0.012000*$pore($uv),0.90,0.99)"
)
AO_EXPRESSION = "clamp(1.0-0.090000*$crack($uv)-0.025000*$pore($uv),0.0,1.0)"
MASKS = {"R": "cracks", "G": "patches", "B": "binder_micro_variation"}
SUFFIXES = {
    "BaseColor": "BaseColor.png",
    "Normal_DX": "Normal_DX.png",
    "ORM": "ORM.png",
    "Height": "Height.exr",
    "DetailMasks": "DetailMasks.png",
}
MM_SOURCE = "4d29a815489866aae483281cf44b2cfe48d3cc3e"
GODOT_SOURCE = "ed1daf0bf001b61586d9930840f2f1394092c079"
MAX_MAP_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_JSON_BYTES = 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
IDENTITY_FIELDS = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
_WINDOWS = os.name == "nt"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _number(value: Any, expected: float | None, label: str) -> float:
    _require(type(value) in (int, float), f"Non-numeric {label}")
    _require(math.isfinite(value), f"Non-finite {label}")
    if expected is not None:
        _require(value == expected, f"Unexpected {label}")
    return float(value)


def _digest(value: Any, label: str) -> str:
    _require(
        isinstance(value, str) and bool(SHA256.fullmatch(value)), f"Invalid {label}"
    )
    return value


def _safe_path(path: Path, *, directory: bool = False) -> os.stat_result:
    _require(".." not in path.parts, "Source path contains parent traversal")
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        _require(
            not stat.S_ISLNK(info.st_mode)
            and not getattr(info, "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT,
            "Source path contains a symlink or reparse point",
        )
        if item != path or directory:
            _require(stat.S_ISDIR(info.st_mode), "Source ancestor is not a directory")
        else:
            _require(stat.S_ISREG(info.st_mode), "Source input is not a regular file")
    return info


def _identity(info: os.stat_result) -> tuple[int, ...]:
    return tuple(getattr(info, name) for name in IDENTITY_FIELDS)


def _assert_identity(
    expected: tuple[int, ...], observed: tuple[int, ...], message: str
) -> None:
    if expected == observed:
        return
    differing_fields = [
        {"field": field, "expected": before, "observed": after}
        for field, before, after in zip(
            IDENTITY_FIELDS[: len(expected)], expected, observed, strict=True
        )
        if before != after
    ]
    detail = json.dumps(differing_fields, separators=(",", ":"))
    # Only fixed field names and OS integers; never include source paths/content.
    if len(detail.encode("utf-8")) > 1800:
        detail = '[{"diagnostic_truncated":true}]'
    raise ValueError(message + "; differing_fields=" + detail)


def _assert_path_handle(
    path_info: os.stat_result, handle_info: os.stat_result, message: str
) -> None:
    _require(stat.S_ISREG(handle_info.st_mode), "Opened source is not a regular file")
    path_identity = _identity(path_info)
    handle_identity = _identity(handle_info)
    # CPython 3.12/3.13 Windows lstat returns creation time in st_ctime,
    # while fstat returns FILE_BASIC_INFO.ChangeTime (Python/fileutils.c).
    # Compare ctime within each view below; device/inode/size/mtime remain exact.
    if _WINDOWS:
        path_identity = path_identity[:-1]
        handle_identity = handle_identity[:-1]
    _assert_identity(path_identity, handle_identity, message)


def _read(
    path: Path, limit: int, budget: list[int]
) -> tuple[bytes, dict[str, Any], tuple[int, ...]]:
    before = _safe_path(path)
    _require(
        0 < before.st_size <= limit, "Source input exceeds its nonempty byte bound"
    )
    _require(
        budget[0] + before.st_size <= MAX_TOTAL_BYTES, "Source byte budget exceeded"
    )
    with path.open("rb") as stream:
        handle_before = os.fstat(stream.fileno())
        _assert_path_handle(before, handle_before, "Source changed before read")
        raw = stream.read(before.st_size)
        handle_after = os.fstat(stream.fileno())
        _assert_identity(
            _identity(handle_before),
            _identity(handle_after),
            "Source changed during read",
        )
    _require(len(raw) == before.st_size, "Source changed size during read")
    after = _safe_path(path)
    _assert_identity(_identity(before), _identity(after), "Source changed after read")
    _assert_path_handle(after, handle_after, "Source changed after read")
    budget[0] += len(raw)
    return (
        raw,
        {"size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
        _identity(before),
    )


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for name, value in pairs:
        _require(name not in result, "Duplicate source JSON field")
        result[name] = value
    return result


def _json(raw: bytes) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"Non-finite source JSON constant: {value}")

    value = json.loads(
        raw, object_pairs_hook=_unique_pairs, parse_constant=reject_constant
    )
    _require(isinstance(value, dict), "Source JSON must be an object")
    return value


def _ownership(document: dict[str, Any]) -> None:
    _require(
        document.get("semantic_owner") == "PCG/PCGEx", "Semantic ownership changed"
    )
    _require(
        document.get("world_semantics_generated") is False,
        "Source claims world semantics",
    )
    _require(
        document.get("normal_convention") == "DirectX",
        "DirectX normal contract required",
    )
    _require(
        document.get("local_mask_channels") == MASKS,
        "Material-local mask contract changed",
    )


def _catalog(data: dict[str, Any]) -> None:
    _require(
        type(data.get("schema_version")) is int and data["schema_version"] == 1,
        "Unexpected catalog schema",
    )
    _require(
        type(data.get("output_resolution")) is int
        and data["output_resolution"] == 2048,
        "Catalog resolution changed",
    )
    _require(
        data.get("normal_convention") == "DirectX"
        and data.get("semantic_owner") == "PCG/PCGEx",
        "Catalog ownership/normal contract changed",
    )
    families = [row for row in data.get("families", []) if row.get("id") == FAMILY]
    _require(len(families) == 1, "Catalog must contain one asphalt family")
    family = families[0]
    _number(family.get("tile_metres"), 4, "catalog tile_metres")
    _require(
        family.get("semantic_owner") == "PCG/PCGEx"
        and family.get("local_masks") == MASKS,
        "Catalog asphalt ownership changed",
    )
    variants = [row for row in family.get("variants", []) if row.get("id") == VARIANT]
    _require(len(variants) == 1, "Catalog must contain one dry_varied variant")
    variant = variants[0]
    _require(
        type(variant.get("seed")) is int and variant["seed"] == SEED,
        "Catalog seed changed",
    )
    for name, expected in PARAMETERS.items():
        _number(variant.get(name), expected, "catalog " + name)
    _require(
        not variant.get("refinement") and not variant.get("landscape"),
        "Unexpected dry_varied refinement",
    )


def _engine(engine: Any) -> None:
    _require(isinstance(engine, dict), "Missing native decoder engine")
    for name, expected in {"major": 4, "minor": 7, "patch": 2}.items():
        _require(
            type(engine.get(name)) is int and engine[name] == expected,
            "Godot version changed",
        )
    _require(
        engine.get("hash") == GODOT_SOURCE
        and engine.get("status") == "stable"
        and engine.get("build") == "official",
        "Godot producer pin changed",
    )


def _graph(graph: dict[str, Any]) -> None:
    _require(
        type(graph.get("seed_int")) is int and graph["seed_int"] == SEED,
        "Graph seed changed",
    )
    rows = graph.get("nodes")
    _require(
        isinstance(rows, list) and all(isinstance(row, dict) for row in rows),
        "Invalid graph nodes",
    )
    nodes = {row.get("name"): row for row in rows}
    _require(len(nodes) == len(rows), "Duplicate graph node")
    for node_name, expected in {
        "Limestone_Form": {"seed": SEED, "fractures": 0.48, "pores": 0.90},
        "Limestone_Color": {"brightness": 0.31},
        "Height_Normal": {"strength": 0.24},
    }.items():
        for name, value in expected.items():
            _number(nodes[node_name]["parameters"].get(name), value, "graph " + name)
    # Match actual shader text, not a variant label or editable scalar alone.
    # This includes periodic helpers and the coarse/middle/micro field recipe.
    for actual, expected, label in (
        (
            nodes["Limestone_Form"]["shader_model"].get("global"),
            SURFACE_FIELD_SHA256,
            "surface field",
        ),
        (
            nodes["Limestone_Color"]["shader_model"].get("code"),
            COLOR_CODE_SHA256,
            "colour recipe",
        ),
        (
            nodes["Limestone_Color"]["shader_model"]["outputs"][0].get("rgb"),
            COLOR_OUTPUT_SHA256,
            "colour output",
        ),
    ):
        _require(
            isinstance(actual, str)
            and hashlib.sha256(actual.encode("utf-8")).hexdigest() == expected,
            "Graph " + label + " changed",
        )
    response = nodes["Limestone_Response"]["shader_model"]["outputs"]
    _require(
        isinstance(response, list)
        and len(response) >= 2
        and response[0].get("f") == ROUGHNESS_EXPRESSION
        and response[1].get("f") == AO_EXPRESSION,
        "Graph roughness recipe changed",
    )


def _dry_statistics(value: Any) -> dict[str, float]:
    _require(
        isinstance(value, dict)
        and set(value) == {
            "roughness_min", "roughness_max", "roughness_mean", "roughness_std",
            "basecolor_luma_std", "basecolor_25cm_luma_std",
            "patch_coverage_fraction", "normal_xy_rms",
        },
        "Missing dry asphalt source statistics",
    )
    stats = {key: _number(item, None, "dry asphalt " + key) for key, item in value.items()}
    _require(
        0.90 - 1 / 255 <= stats["roughness_min"]
        <= stats["roughness_mean"] <= stats["roughness_max"] <= 0.99 + 1 / 255
        and 0.003 <= stats["roughness_std"] <= 0.05,
        "Dry asphalt roughness statistics failed",
    )
    _require(
        0.012 <= stats["basecolor_luma_std"] <= 0.5
        and 0.008 <= stats["basecolor_25cm_luma_std"] <= stats["basecolor_luma_std"]
        and 0.02 <= stats["patch_coverage_fraction"] <= 0.40
        and 0 < stats["normal_xy_rms"] <= 1,
        "Dry asphalt variation statistics failed",
    )
    return stats


def check_asphalt_source(
    directory: Path, catalog_path: Path = DEFAULT_CATALOG
) -> dict[str, Any]:
    """Return bounded retained-source evidence, or ValueError; perform no writes.

    The input is a variant directory, with only the literal members below read.
    An optional catalog supports offline fixtures; it cannot change the recipe.
    Retained receipts are assertions of the producer, not current native proof.
    """
    try:
        return _check_asphalt_source(
            Path(directory).absolute(), Path(catalog_path).absolute()
        )
    except (
        OSError,
        AttributeError,
        KeyError,
        TypeError,
        OverflowError,
        RecursionError,
        UnicodeError,
    ) as exc:
        raise ValueError("Invalid or unreadable asphalt source bundle") from exc


def _check_asphalt_source(root: Path, catalog_path: Path) -> dict[str, Any]:
    _safe_path(root, directory=True)
    budget = [0]
    receipts = {}
    documents = {}
    stable_inputs = {}
    catalog_raw, receipts["catalog"], stable_inputs[catalog_path] = _read(
        catalog_path, MAX_JSON_BYTES, budget
    )
    _catalog(_json(catalog_raw))
    for relative in (
        "provenance.json",
        "validation.json",
        "render-receipt.json",
        "export/YACS_Material_native-check.json",
        "Material.ptex",
    ):
        raw, receipts[relative], stable_inputs[root / relative] = _read(
            root / relative, MAX_JSON_BYTES, budget
        )
        documents[relative] = _json(raw)
    provenance = documents["provenance.json"]
    validation = documents["validation.json"]
    render = documents["render-receipt.json"]
    native = documents["export/YACS_Material_native-check.json"]
    for document in (provenance, validation):
        _require(
            document.get("family") == FAMILY and document.get("variant") == VARIANT,
            "Source family/variant mismatch",
        )
        _require(
            document.get("status") == STATUS, "Source is not CPU-checked for review"
        )
        _ownership(document)
    _require(
        type(provenance.get("seed")) is int and provenance["seed"] == SEED,
        "Source seed changed",
    )
    _number(provenance.get("tile_metres"), 4, "source tile_metres")
    parameters = provenance.get("parameters")
    _require(
        isinstance(parameters, dict)
        and set(parameters) == set(PARAMETERS) | {"refinement", "landscape"},
        "Source parameters changed",
    )
    for name, expected in PARAMETERS.items():
        _number(parameters.get(name), expected, "source " + name)
    _require(
        parameters["refinement"] == {} and parameters["landscape"] == {},
        "Unexpected source refinement",
    )
    _require(
        provenance.get("generator") == "yacs-material-forge"
        and type(provenance.get("generator_version")) is int
        and provenance["generator_version"] == GENERATOR_VERSION,
        "Source generator changed",
    )
    _require(
        provenance.get("graph") == "Material.ptex"
        and provenance.get("recipe") == "scripts/assets/material_forge.py",
        "Unexpected source graph/recipe path",
    )
    graph_sha = receipts["Material.ptex"]["sha256"]
    _require(
        _digest(provenance.get("graph_sha256"), "graph digest") == graph_sha,
        "Source graph hash mismatch",
    )
    _graph(documents["Material.ptex"])
    _require(
        provenance.get("expected_maps") == list(SUFFIXES.values()),
        "Unexpected source map inventory",
    )
    _require(
        provenance.get("render_receipt") == "render-receipt.json",
        "Unexpected render receipt path",
    )
    upstreams = provenance.get("upstreams", {})
    _require(
        upstreams.get("material_maker", {}).get("validated_source_commit") == MM_SOURCE
        and upstreams.get("godot", {}).get("commit") == GODOT_SOURCE,
        "Source upstream pin changed",
    )
    _require(
        provenance.get("license") == "MIT"
        and provenance.get("notice") == "MATERIAL_MAKER_LICENSE.txt",
        "Source license contract changed",
    )
    (
        _,
        receipts["MATERIAL_MAKER_LICENSE.txt"],
        stable_inputs[root / "MATERIAL_MAKER_LICENSE.txt"],
    ) = _read(root / "MATERIAL_MAKER_LICENSE.txt", 64 * 1024, budget)
    _require(
        validation.get("geometry_changed") is False
        and validation.get("visual_accepted") is False
        and validation.get("performance_accepted") is False,
        "Source receipt claims unsupported admission",
    )
    dry_statistics = _dry_statistics(validation.get("dry_asphalt_statistics"))
    error = _number(
        validation.get("normal_length_error_p99"), None, "normal length error"
    )
    _require(0 <= error <= 0.03, "CPU normal length check failed")
    _require(native.get("valid") is True, "Native decode receipt is not valid")
    _engine(native.get("engine"))
    maps = validation.get("maps")
    images = native.get("images")
    _require(
        isinstance(maps, dict) and set(maps) == set(SUFFIXES),
        "CPU map inventory changed",
    )
    _require(
        isinstance(images, dict) and set(images) == set(SUFFIXES.values()),
        "Native map inventory changed",
    )
    evidence_maps = {}
    for channel, suffix in SUFFIXES.items():
        relative = "export/YACS_Material_" + suffix
        entry = maps[channel]
        _require(
            isinstance(entry, dict) and entry.get("path") == relative,
            "Unexpected map path: " + channel,
        )
        raw, identity, stable_inputs[root / relative] = _read(
            root / relative, MAX_MAP_BYTES, budget
        )
        _require(
            _digest(entry.get("sha256"), "CPU map digest") == identity["sha256"],
            "Map changed after CPU validation: " + channel,
        )
        image = images[suffix]
        _require(
            isinstance(image, dict)
            and type(image.get("width")) is int
            and type(image.get("height")) is int
            and image["width"] == image["height"] == 2048,
            "Native resolution mismatch: " + channel,
        )
        _require(
            _digest(image.get("sha256"), "native map digest") == identity["sha256"],
            "Native map hash mismatch: " + channel,
        )
        if channel == "Height":
            _require(raw[:4] == b"\x76\x2f\x31\x01", "Height is not EXR")
        else:
            _require(
                entry.get("size") == [2048, 2048], "CPU resolution mismatch: " + channel
            )
            _require(
                raw[:8] == b"\x89PNG\r\n\x1a\n"
                and raw[12:16] == b"IHDR"
                and len(raw) >= 24
                and struct.unpack(">II", raw[16:24]) == (2048, 2048),
                "PNG resolution/header mismatch: " + channel,
            )
            for axis in ("x", "y"):
                wrap = _number(entry.get("wrap_step_" + axis), None, "wrap step")
                interior = _number(
                    entry.get("interior_step_" + axis), None, "interior step"
                )
                _require(
                    0 <= wrap <= max(0.02, interior * 4) and interior >= 0,
                    "CPU tiling check failed",
                )
        evidence_maps[channel] = {
            "relative_path": relative,
            **identity,
            "width": 2048,
            "height": 2048,
        }
    _require(
        render.get("producer") == "Material Maker source runtime under pinned Godot"
        and render.get("source_commit") == MM_SOURCE,
        "Render producer pin changed",
    )
    _require(
        type(render.get("exit_code")) is int
        and render["exit_code"] == 0
        and render.get("status") == STATUS,
        "Render receipt did not succeed",
    )
    _require(
        render.get("graph_sha256") == graph_sha
        and render.get("validation_sha256") == receipts["validation.json"]["sha256"],
        "Render receipt content mismatch",
    )
    _require(render.get("engine") == native["engine"], "Render/native engine mismatch")
    _digest(render.get("godot_sha256"), "producer-reported Godot digest")
    _digest(
        render.get("source_class_cache_sha256"), "producer-reported class cache digest"
    )
    _require(
        type(render.get("source_imported_file_count")) is int
        and render["source_imported_file_count"] > 0,
        "Source cache was not primed",
    )
    command = render.get("command")
    _require(
        isinstance(command, list)
        and len(command) == 9
        and all(isinstance(x, str) and 0 < len(x) <= 4096 for x in command),
        "Unexpected retained render command",
    )
    _require(
        command[1] == "--path"
        and command[3] == "--script"
        and command[5] == "--"
        and command[8] == "2048"
        and PureWindowsPath(command[6]).name == "Material.ptex"
        and PureWindowsPath(command[7]).name == "YACS_Material"
        and PureWindowsPath(command[4]).name == "render_material_forge.gd",
        "Unexpected retained render invocation",
    )
    for path, before in stable_inputs.items():
        _assert_identity(
            before,
            _identity(_safe_path(path)),
            "Source changed before contract completion",
        )
    result = {
        "schema_version": 1,
        "status": "ROAD_ASPHALT_SOURCE_CONTRACT_VERIFIED",
        "family": FAMILY,
        "variant": VARIANT,
        "seed": SEED,
        "tile_metres": 4,
        "tile_size_cm": 400,
        "parameters": dict(PARAMETERS),
        "dry_asphalt_statistics": dry_statistics,
        "maps": evidence_maps,
        "retained_receipts": receipts,
        "total_read_bytes": budget[0],
        "producer_source_commit": MM_SOURCE,
        "godot_source_commit": GODOT_SOURCE,
        "producer_reported_godot_sha256": render["godot_sha256"],
        "producer_binary_independently_verified": False,
        "native_decode_scope": "RETAINED_PRODUCER_RECEIPT",
        "normal_convention": "DirectX",
        "semantic_owner": "PCG/PCGEx",
        "world_semantics_generated": False,
        "geometry_changed": False,
        "height_displacement_used": False,
        "read_only": True,
        "two_run_replay_verified": False,
        "unreal_verified": False,
        "visual_status": "PENDING_FINAL_M3",
        "visual_accepted": False,
        "performance_pass": False,
    }
    encoded = json.dumps(
        result, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    _require(len(encoded) <= 16 * 1024, "Source receipt exceeds output bound")
    result["source_receipt_sha256"] = hashlib.sha256(encoded).hexdigest()
    return result


def check_asphalt_replay(
    proof_root: Path,
    expected_receipt_sha256: str,
    expected_source_head: str,
    expected_source_fingerprint: str,
) -> dict[str, Any]:
    """Authenticate retained two-run bytes with a trusted caller's source gate.

    The caller supplies the approved raw receipt digest and unchanged current
    Forge fingerprint. Source HEAD belongs to that producer, not this reader's
    execution. No producer binary is independently authenticated here.
    """
    try:
        return _check_asphalt_replay(
            Path(proof_root).absolute(),
            _digest(expected_receipt_sha256, "expected receipt digest"),
            expected_source_head,
            _digest(expected_source_fingerprint, "expected source fingerprint"),
        )
    except (
        OSError,
        AttributeError,
        KeyError,
        TypeError,
        OverflowError,
        RecursionError,
        UnicodeError,
    ) as exc:
        raise ValueError("Invalid or unreadable asphalt replay bundle") from exc


def _check_asphalt_replay(
    root: Path, expected_digest: str, source_head: str, source_fingerprint: str
) -> dict[str, Any]:
    _require(
        isinstance(source_head, str) and bool(SHA1.fullmatch(source_head)),
        "Invalid expected source HEAD",
    )
    _safe_path(root, directory=True)
    budget = [0]
    receipt_path = root / "source-proof.json"
    raw, receipt_identity, receipt_stat = _read(receipt_path, MAX_JSON_BYTES, budget)
    _require(
        receipt_identity["sha256"] == expected_digest,
        "Replay receipt authentication failed",
    )
    receipt = _json(raw)
    _require(
        set(receipt)
        == {
            "schema_version",
            "issue",
            "exact_sha",
            "run",
            "attempt",
            "status",
            "source_fingerprint",
            "runs",
            "godot_sha256",
            "material_maker_sha256",
            "tool_archive_hashes_verified",
            "source_commit",
            "primed_source_identity",
            "two_run_graph_and_map_bytes_equal",
            "rendered_variant_count",
            "unreal_consumption_verified",
            "world_mutation",
            "human_visual_status",
            "performance_status",
            "performance_pass",
        },
        "Unexpected replay receipt fields",
    )
    for name, expected in {
        "schema_version": 1,
        "issue": 364,
        "rendered_variant_count": 2,
    }.items():
        _require(
            type(receipt[name]) is int and receipt[name] == expected,
            "Unexpected replay " + name,
        )
    _require(
        receipt["status"] == "ROAD_ASPHALT_SOURCE_DETERMINISM_PASS",
        "Replay producer did not pass",
    )
    _require(receipt["exact_sha"] == source_head, "Replay source HEAD mismatch")
    _require(
        receipt["source_fingerprint"] == source_fingerprint,
        "Replay source fingerprint mismatch",
    )
    _require(
        receipt["source_commit"] == MM_SOURCE, "Replay producer source pin changed"
    )
    _require(
        all(
            isinstance(receipt[name], str)
            and bool(re.fullmatch(r"[0-9]{1,20}", receipt[name]))
            for name in ("run", "attempt")
        ),
        "Invalid replay workflow identity",
    )
    for name, expected in {
        "tool_archive_hashes_verified": True,
        "two_run_graph_and_map_bytes_equal": True,
        "unreal_consumption_verified": False,
        "world_mutation": False,
        "performance_pass": False,
    }.items():
        _require(receipt[name] is expected, "Unsupported replay claim: " + name)
    _require(
        receipt["human_visual_status"] == "PENDING_FINAL_M3"
        and receipt["performance_status"] == "DEFERRED_AFTER_M3",
        "Replay review/performance scope changed",
    )
    _digest(receipt["godot_sha256"], "replay Godot digest")
    _digest(receipt["material_maker_sha256"], "replay Material Maker digest")
    primed = receipt["primed_source_identity"]
    _require(
        isinstance(primed, dict)
        and set(primed)
        == {"source_commit", "program_inputs_unchanged", "primed_icon_imports"},
        "Invalid primed-source attestation",
    )
    _require(
        primed["source_commit"] == MM_SOURCE
        and primed["program_inputs_unchanged"] is True,
        "Replay producer source was not unchanged",
    )
    imports = primed["primed_icon_imports"]
    _require(
        isinstance(imports, dict) and 0 < len(imports) <= 32,
        "Invalid primed import attestation",
    )
    for name, entry in imports.items():
        _require(
            isinstance(name, str)
            and len(name) <= 256
            and isinstance(entry, dict)
            and set(entry) == {"source_blob_id", "sha256"},
            "Invalid primed import identity",
        )
        _require(
            isinstance(entry["source_blob_id"], str)
            and bool(SHA1.fullmatch(entry["source_blob_id"])),
            "Invalid primed import blob",
        )
        _digest(entry["sha256"], "primed import digest")
    runs = receipt["runs"]
    _require(isinstance(runs, list) and len(runs) == 2, "Replay needs exactly two runs")
    stable = {receipt_path: receipt_stat}
    # Preflight the complete fixed read set before either source checker runs.
    # Each checker reads the catalog once; charge both reads to the shared cap.
    expected_bytes = budget[0]
    for run in ("run-a", "run-b"):
        directory = root / run / FAMILY / VARIANT
        inputs = [(DEFAULT_CATALOG, MAX_JSON_BYTES)]
        inputs += [
            (directory / name, MAX_JSON_BYTES)
            for name in (
                "Material.ptex",
                "provenance.json",
                "validation.json",
                "render-receipt.json",
                "export/YACS_Material_native-check.json",
            )
        ]
        inputs.append((directory / "MATERIAL_MAKER_LICENSE.txt", 64 * 1024))
        inputs += [
            (directory / ("export/YACS_Material_" + suffix), MAX_MAP_BYTES)
            for suffix in SUFFIXES.values()
        ]
        for path, limit in inputs:
            info = _safe_path(path)
            _require(
                0 < info.st_size <= limit,
                "Replay input exceeds its nonempty byte bound",
            )
            expected_bytes += info.st_size
            _require(
                expected_bytes <= MAX_TOTAL_BYTES, "Replay source byte budget exceeded"
            )
            stable[path] = _identity(info)
    checked_runs = []
    for label, row in zip(("run-a", "run-b"), runs, strict=True):
        _require(
            isinstance(row, dict)
            and set(row)
            == {
                "run",
                "directory",
                "fingerprint",
                "source",
                "graph_sha256",
                "map_sha256",
            },
            "Unexpected replay run fields",
        )
        relative = label + "/" + FAMILY + "/" + VARIANT
        _require(
            row["run"] == label
            and row["directory"] in (relative, relative.replace("/", "\\")),
            "Unexpected replay run directory/order",
        )
        _digest(row["fingerprint"], "replay graph fingerprint")
        checked = check_asphalt_source(root / label / FAMILY / VARIANT)
        _require(
            row["source"] == checked,
            "Retained source receipt differs from current checked bytes: " + label,
        )
        graph_sha = checked["retained_receipts"]["Material.ptex"]["sha256"]
        map_sha = {name: entry["sha256"] for name, entry in checked["maps"].items()}
        _require(
            row["graph_sha256"] == graph_sha and row["map_sha256"] == map_sha,
            "Replay run graph/map bindings differ: " + label,
        )
        _require(
            checked["producer_reported_godot_sha256"] == receipt["godot_sha256"],
            "Replay Godot attestation differs from render",
        )
        checked_runs.append(
            {
                "run": label,
                "directory": relative,
                "fingerprint": row["fingerprint"],
                "source": checked,
                "graph_sha256": graph_sha,
                "map_sha256": map_sha,
            }
        )
    _require(
        all(
            checked_runs[0][name] == checked_runs[1][name]
            for name in ("fingerprint", "graph_sha256", "map_sha256")
        ),
        "Retained two-run graph/map bytes differ",
    )
    actual_bytes = budget[0] + sum(
        row["source"]["total_read_bytes"] for row in checked_runs
    )
    _require(actual_bytes == expected_bytes, "Replay read inventory changed")
    for path, before in stable.items():
        _assert_identity(
            before,
            _identity(_safe_path(path)),
            "Replay source changed before completion",
        )
    result = {
        "schema_version": 1,
        "status": "ROAD_ASPHALT_REPLAY_RECEIPT_VERIFIED",
        "source_head": source_head,
        "source_fingerprint": source_fingerprint,
        "source_fingerprint_gate_scope": "TRUSTED_CALLER_SUPPLIED_CURRENT_FORGE_FINGERPRINT",
        "original_workflow_run": receipt["run"],
        "original_workflow_attempt": receipt["attempt"],
        "authenticated_source_receipt": receipt_identity,
        "producer_attestation_authenticated": True,
        "producer_reported_tool_archive_hashes_verified": True,
        "producer_program_inputs_unchanged_attested": True,
        "producer_binary_independently_verified": False,
        "retained_two_run_graph_and_map_bytes_equal": True,
        "renders_executed_by_reader": False,
        "runs": checked_runs,
        "total_read_bytes": actual_bytes,
        "read_only": True,
        "unreal_verified": False,
        "world_mutation": False,
        "geometry_changed": False,
        "height_displacement_used": False,
        "human_visual_status": "PENDING_FINAL_M3",
        "performance_status": "DEFERRED_AFTER_M3",
        "performance_pass": False,
    }
    encoded = json.dumps(
        result, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    _require(len(encoded) <= 32 * 1024, "Replay evidence exceeds output bound")
    result["replay_receipt_sha256"] = hashlib.sha256(encoded).hexdigest()
    return result
