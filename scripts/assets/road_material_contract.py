"""Read-only source contract for the first aged_mountain_asphalt/base canary.

This verifies retained producer receipts and their bytes. It never renders,
imports Unreal assets, establishes two-run replay, or grants visual admission.
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
VARIANT = "base"
STATUS = "MAP_CHECKS_PASS_UE_REVIEW_PENDING"
PARAMETERS = {
    "brightness": 0.3,
    "surface_a": 0.62,
    "surface_b": 0.22,
    "roughness": 0.82,
    "normal_strength": 0.48,
}
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
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


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
        _require(
            _identity(os.fstat(stream.fileno())) == _identity(before),
            "Source changed before read",
        )
        raw = stream.read(before.st_size)
        _require(
            _identity(os.fstat(stream.fileno())) == _identity(before),
            "Source changed during read",
        )
    _require(len(raw) == before.st_size, "Source changed size during read")
    _require(
        _identity(_safe_path(path)) == _identity(before), "Source changed after read"
    )
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
    _require(len(variants) == 1, "Catalog must contain one base variant")
    base = variants[0]
    _require(
        type(base.get("seed")) is int and base["seed"] == 101, "Catalog seed changed"
    )
    for name, expected in PARAMETERS.items():
        _number(base.get(name), expected, "catalog " + name)
    _require(
        not base.get("refinement") and not base.get("landscape"),
        "Unexpected base refinement",
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
        type(graph.get("seed_int")) is int and graph["seed_int"] == 101,
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
        "Limestone_Form": {"seed": 101, "fractures": 0.62, "pores": 0.22},
        "Limestone_Color": {"brightness": 0.3},
        "Height_Normal": {"strength": 0.48},
    }.items():
        for name, value in expected.items():
            _number(nodes[node_name]["parameters"].get(name), value, "graph " + name)
    response = nodes["Limestone_Response"]["shader_model"]["outputs"]
    _require(
        isinstance(response, list)
        and len(response) >= 1
        and response[0].get("f")
        == "clamp(0.820000+0.070000*$variation($uv)+0.030000*$crack($uv)-0.060000*$pore($uv),0.0,1.0)",
        "Graph roughness recipe changed",
    )


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
        type(provenance.get("seed")) is int and provenance["seed"] == 101,
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
        and provenance["generator_version"] == 4,
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
        _require(
            _identity(_safe_path(path)) == before,
            "Source changed before contract completion",
        )
    result = {
        "schema_version": 1,
        "status": "ROAD_ASPHALT_SOURCE_CONTRACT_VERIFIED",
        "family": FAMILY,
        "variant": VARIANT,
        "seed": 101,
        "tile_metres": 4,
        "tile_size_cm": 400,
        "parameters": dict(PARAMETERS),
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
