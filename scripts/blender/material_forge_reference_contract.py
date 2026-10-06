"""Pure-Python admission contract for Blender Material Forge reference renders."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_STATUS = "MAP_CHECKS_PASS_UE_REVIEW_PENDING"
EXPECTED_NORMAL = "DirectX"
EXPECTED_SEMANTIC_OWNER = "PCG/PCGEx"
REQUIRED_CHANNELS = ("BaseColor", "Normal_DX", "ORM")

VIEW_PLAN = (
    {
        "name": "context_split",
        "location": (0.0, -9.8, 6.8),
        "target": (0.0, 0.0, 0.0),
        "lens_mm": 50.0,
    },
    {
        "name": "grazing_split",
        "location": (0.0, -8.0, 1.25),
        "target": (0.0, 0.0, 0.08),
        "lens_mm": 58.0,
    },
    {
        "name": "rock_close",
        "location": (-2.15, -4.8, 2.3),
        "target": (-2.15, 0.0, 0.0),
        "lens_mm": 62.0,
    },
    {
        "name": "soil_close",
        "location": (2.15, -4.8, 2.3),
        "target": (2.15, 0.0, 0.0),
        "lens_mm": 62.0,
    },
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _resolve_map(
    directory: Path,
    validation: dict[str, Any],
    channel: str,
) -> dict[str, Any]:
    entry = validation.get("maps", {}).get(channel)
    if not isinstance(entry, dict):
        raise ValueError(f"Material Forge validation is missing {channel}")
    relative = Path(str(entry.get("path", "")))
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe Material Forge map path for {channel}")
    root = directory.resolve(strict=True)
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"Material Forge map escaped variant root: {channel}")
    digest = sha256_file(path)
    expected = str(entry.get("sha256", "")).lower()
    if digest != expected:
        raise ValueError(f"Material Forge map hash mismatch: {channel}")
    return {
        "path": str(path),
        "sha256": digest,
    }


def load_variant(
    directory: Path,
    *,
    expected_family: str,
    expected_variant: str,
) -> dict[str, Any]:
    root = directory.resolve(strict=True)
    validation = _json(root / "validation.json")
    provenance = _json(root / "provenance.json")

    if validation.get("status") != EXPECTED_STATUS:
        raise ValueError("Material Forge variant is not CPU-admitted for UE review")
    if validation.get("family") != expected_family:
        raise ValueError(
            f"Expected Material Forge family {expected_family}, "
            f"got {validation.get('family')}"
        )
    if validation.get("variant") != expected_variant:
        raise ValueError(
            f"Expected Material Forge variant {expected_variant}, "
            f"got {validation.get('variant')}"
        )
    if (
        provenance.get("family") != expected_family
        or provenance.get("variant") != expected_variant
    ):
        raise ValueError("Material Forge provenance identity disagrees with validation")
    if validation.get("normal_convention") != EXPECTED_NORMAL:
        raise ValueError("Blender reference proof requires DirectX normals")
    if validation.get("semantic_owner") != EXPECTED_SEMANTIC_OWNER:
        raise ValueError("Material Forge semantic owner changed")
    if validation.get("world_semantics_generated") is not False:
        raise ValueError("Material Forge reference input generated world semantics")
    if provenance.get("semantic_owner") != EXPECTED_SEMANTIC_OWNER:
        raise ValueError("Material Forge provenance semantic owner changed")
    if provenance.get("world_semantics_generated") is not False:
        raise ValueError("Material Forge provenance claims world semantics")

    tile_metres = float(provenance.get("tile_metres", 0.0))
    if not 0.25 <= tile_metres <= 32.0:
        raise ValueError(
            f"Unreasonable Material Forge physical tile size: {tile_metres}"
        )

    maps = {
        channel: _resolve_map(root, validation, channel)
        for channel in REQUIRED_CHANNELS
    }

    return {
        "directory": str(root),
        "family": expected_family,
        "variant": expected_variant,
        "tile_metres": tile_metres,
        "normal_convention": EXPECTED_NORMAL,
        "semantic_owner": EXPECTED_SEMANTIC_OWNER,
        "world_semantics_generated": False,
        "validation_sha256": sha256_file(root / "validation.json"),
        "provenance_sha256": sha256_file(root / "provenance.json"),
        "maps": maps,
    }


def build_reference_plan(
    rock_directory: Path,
    soil_directory: Path,
) -> dict[str, Any]:
    rock = load_variant(
        rock_directory,
        expected_family="regional_limestone",
        expected_variant="base",
    )
    soil = load_variant(
        soil_directory,
        expected_family="mediterranean_soil",
        expected_variant="fine",
    )
    if rock["tile_metres"] != soil["tile_metres"]:
        raise ValueError("Reference pair must use the same physical tile scale")

    payload = {
        "schema_version": 1,
        "status": "REFERENCE_PLAN_READY",
        "rock": rock,
        "soil": soil,
        "tile_metres": rock["tile_metres"],
        "views": [dict(view) for view in VIEW_PLAN],
        "height_displacement_used": False,
        "world_semantics_changed": False,
        "geometry_authority_changed": False,
        "visual_accepted": False,
        "performance_accepted": False,
    }
    payload["input_fingerprint"] = canonical_hash(payload)
    return payload
