"""Prepare the current rider viewport with Epic's native loading barrier.

Editor proof only: do not alter height data, LOD policy, materials or assets.
Texture telemetry is evidence, not a terrain quality acceptance decision.
"""
from __future__ import annotations

import json
from pathlib import Path
import time


# The capture task has a 90-second deadline. This transient request gives it
# 30 seconds of margin, expires automatically, and is never serialized.
HEIGHT_MIP_LEASE_SECONDS = 120.0


def _height_texture_objects(api, landscape) -> list:
    prefix = landscape.get_path_name().split(".", 1)[0] + "."
    textures = sorted(
        (
            texture
            for texture in api.ObjectIterator(api.Texture2D)
            if texture.get_path_name().startswith(prefix)
            and texture.get_editor_property("lod_group")
            == api.TextureGroup.TEXTUREGROUP_TERRAIN_HEIGHTMAP
        ),
        key=lambda texture: texture.get_path_name(),
    )
    if not textures:
        raise RuntimeError("No map-owned Landscape height textures for capture readback")
    return textures


def _height_textures(api, landscape) -> list[dict]:
    rows = []
    for texture in _height_texture_objects(api, landscape):
        row = json.loads(api.YacsTextureAuditLibrary.describe_texture(texture))
        if "error" in row:
            raise RuntimeError(f"Native capture texture readback failed: {row['error']}")
        rows.append(row)
    return rows


def prepare_capture(
    api, landscape, location, rotation, output: Path, *, request_height_mips: bool = False
) -> dict:
    """Prime the already-selected camera, finish loading, and preserve readbacks."""
    report = {
        "schema_version": 2,
        "status": "STARTED",
        "native_loading_barrier": "AutomationLibrary.finish_loading_before_screenshot",
        "saved_to_map": False,
        "height_edits_applied": False,
        "terrain_quality_accepted": False,
        "height_mip_lease_requested": request_height_mips,
        "height_mip_lease_seconds": HEIGHT_MIP_LEASE_SECONDS if request_height_mips else 0.0,
        "telemetry_stage": "immediately before screenshot task submission",
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    leased = []
    try:
        viewport = api.get_editor_subsystem(api.UnrealEditorSubsystem)
        if viewport is None or viewport.get_level_viewport_camera_info() is None:
            raise RuntimeError("Landscape capture requires an active level viewport")
        report["textures_before"] = _height_textures(api, landscape)
        viewport.set_level_viewport_camera_info(location, rotation)
        report["viewport_primed_at_rider_camera"] = True
        api.AutomationLibrary.finish_loading_before_screenshot()
        report["native_loading_barrier_completed"] = True
        report["textures_after"] = _height_textures(api, landscape)
        if any(
            row["is_default_texture"] or row["is_compiling"]
            for row in report["textures_after"]
        ):
            raise RuntimeError("Landscape height textures are not ready after loading barrier")
        if request_height_mips:
            report["textures_before_mip_request"] = report["textures_after"]
            for texture in _height_texture_objects(api, landscape):
                metadata = json.loads(api.YacsTextureAuditLibrary.describe_texture(texture))
                if metadata["mips"] > 1:
                    # Only map-owned heightmaps, not material/foliage textures.
                    leased.append(texture)
                    texture.set_force_mip_levels_to_be_resident(HEIGHT_MIP_LEASE_SECONDS, 0)
            report["mip_residency_request_count"] = len(leased)
            if not leased:
                raise RuntimeError("No mipmapped Landscape height textures for residency experiment")
            api.AutomationLibrary.finish_loading_before_screenshot()
            report["textures_after"] = _height_textures(api, landscape)
            if any(
                row["is_default_texture"] or row["is_compiling"]
                or row["mips"] <= 0 or row["resident_mips"] != row["mips"]
                for row in report["textures_after"]
            ):
                raise RuntimeError("Requested native Landscape height mips are not fully resident")
        report["status"] = (
            "NATIVE_LOADING_AND_MIPS_READY" if request_height_mips else "NATIVE_LOADING_COMPLETED"
        )
        return report
    except Exception as exc:
        report["status"] = "FAILED"
        report["error"] = str(exc)
        for texture in leased:
            try:
                texture.set_force_mip_levels_to_be_resident(0.0, 0)
            except Exception as cleanup_error:
                report.setdefault("lease_cleanup_errors", []).append(str(cleanup_error))
        raise
    finally:
        report["duration_seconds"] = round(time.monotonic() - started, 6)
        (output / "capture-readiness.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
