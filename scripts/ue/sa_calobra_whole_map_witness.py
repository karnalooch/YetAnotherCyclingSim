"""Bounded visual witness for mode-dependent dark regions, outside the 43-frame proof."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path


WITNESS_IDS = (
    "near-landscape-2",
    "seam-close",
    "ground-1-2",
    "window-0021-forward-00005",
)
WITNESS_MODES = ("flat-normal", "no-shadows")
DARK_RGB_MAX_EXCLUSIVE = 16
POSE_KEYS = ("camera_location_cm", "target_cm", "camera_rotation_deg", "fov_deg")


def witness_steps(views):
    lookup = {row["frame_id"]: row for row in views}
    if len(lookup) != len(views) or not set(WITNESS_IDS) <= set(lookup):
        raise ValueError("Bounded visual witness camera inventory is incomplete")
    return [(lookup[name], mode) for name in WITNESS_IDS for mode in WITNESS_MODES]


def witness_parameters(mode, ordinary):
    if mode not in WITNESS_MODES:
        raise ValueError("Unknown whole-map witness mode")
    params = dict(ordinary)
    params["MicroNormalStrength"] = 0.0 if mode == "flat-normal" else 0.75
    return params


def dark_fraction(path, expected_size):
    """Image area, never terrain area; strict entire-RGB near-black screen."""
    # Unreal's embedded Python does not include Pillow. The module itself
    # must remain importable there; this decode executes only in host proof.
    from PIL import Image, ImageChops, ImageStat
    with Image.open(path) as image:
        if image.format != "PNG" or image.size != expected_size:
            raise ValueError("Witness PNG format or image dimensions changed")
        r, g, b = image.convert("RGB").split()
        strongest = ImageChops.lighter(ImageChops.lighter(r, g), b)
        dark = strongest.point(
            lambda value: 255 if value < DARK_RGB_MAX_EXCLUSIVE else 0
        )
        return round(
            ImageStat.Stat(dark).sum[0] / (255 * dark.width * dark.height), 6
        )


def audit_witnesses(proof, primary, witnesses, expected_size=(1920, 1080)):
    """Reject any missing/ambiguous witness or provenance; no fake visual PASS."""
    proof = Path(proof)
    planned = [(name, mode) for name in WITNESS_IDS for mode in WITNESS_MODES]
    if len(witnesses) != len(planned) or [
        (row.get("frame_id"), row.get("mode")) for row in witnesses
    ] != planned:
        raise ValueError("Visual witness sequence is incomplete or reordered")
    prepared = {
        row["frame_id"]: row for row in primary if row.get("mode") == "prepared"
    }
    observations = []
    for row in witnesses:
        identity, mode = row["frame_id"], row["mode"]
        base = prepared.get(identity)
        if base is None:
            raise ValueError("Visual witness has no matched primary prepared frame")
        if any(row.get(key) != base.get(key) for key in POSE_KEYS):
            raise ValueError("Visual witness changed the original camera or FOV")
        expected = f"diagnostics/{identity}-{mode}.png"
        if row.get("file") != expected:
            raise ValueError("Visual witness output path changed")
        path = proof / expected
        if not path.is_file() or path.is_symlink():
            raise ValueError("Visual witness PNG is missing or a symlink")
        data = path.read_bytes()
        if not 10000 <= len(data) <= 24 * 1024 * 1024:
            raise ValueError("Visual witness PNG byte bounds changed")
        if row.get("size_bytes") != len(data) or (
            row.get("sha256") != hashlib.sha256(data).hexdigest()
        ):
            raise ValueError("Visual witness PNG provenance differs")
        if row.get("dynamic_shadows") is not (mode != "no-shadows"):
            raise ValueError("Visual witness shadow-mode metadata differs")
        normal = row.get("material_parameters", {}).get("MicroNormalStrength")
        if not isinstance(normal, (int, float)) or not math.isfinite(normal):
            raise ValueError("Visual witness normal-strength metadata is missing")
        expected_normal = 0.0 if mode == "flat-normal" else 0.75
        if abs(normal - expected_normal) > 1e-6:
            raise ValueError("Visual witness normal-strength contract changed")
        observations.append(
            {
                "frame_id": identity,
                "mode": mode,
                "file": expected,
                "sha256": row["sha256"],
                "dark_fraction": dark_fraction(path, expected_size),
            }
        )
    expected_files = {row["file"] for row in witnesses}
    actual_files = {
        p.relative_to(proof).as_posix()
        for p in (proof / "diagnostics").glob("*")
        if p.is_file()
    }
    if actual_files != expected_files:
        raise ValueError("Unregistered or missing visual witness PNG")
    return {
        "schema_version": 1,
        "status": "VISUAL_WITNESS_CAPTURED_FOR_OWNER_REVIEW",
        "frame_count": len(witnesses),
        "camera_count": len(WITNESS_IDS),
        "observations": observations,
        "scope": (
            "Exact-pose flat micro-normal versus default lit prepared, "
            "and no-dynamic-shadows versus default lit prepared. Black pixel "
            "ratio cannot determine geometry, material node fault or pixel depth."
        ),
        "rendered_pixel_depth_verified": False,
        "material_repair_proven": False,
        "visual_acceptance": "PENDING_OWNER",
    }
