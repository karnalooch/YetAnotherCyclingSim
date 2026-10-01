"""Prepare the current rider viewport with Epic's native loading barrier.

Editor proof only: do not alter height data, LOD policy, materials or assets.
Texture telemetry is evidence, not a terrain quality acceptance decision.
"""
from __future__ import annotations

import json
from pathlib import Path
import time


def _height_textures(api, landscape) -> list[dict]:
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
    rows = []
    for texture in textures:
        row = json.loads(api.YacsTextureAuditLibrary.describe_texture(texture))
        if "error" in row:
            raise RuntimeError(f"Native capture texture readback failed: {row['error']}")
        rows.append(row)
    return rows


def prepare_capture(api, landscape, location, rotation, output: Path) -> dict:
    """Prime the already-selected camera, finish loading, and preserve readbacks."""
    report = {
        "schema_version": 1,
        "status": "STARTED",
        "native_loading_barrier": "AutomationLibrary.finish_loading_before_screenshot",
        "saved_to_map": False,
        "height_edits_applied": False,
        "terrain_quality_accepted": False,
        "telemetry_stage": "immediately before screenshot task submission",
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
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
        report["status"] = "NATIVE_LOADING_COMPLETED"
        return report
    except Exception as exc:
        report["status"] = "FAILED"
        report["error"] = str(exc)
        raise
    finally:
        report["duration_seconds"] = round(time.monotonic() - started, 6)
        (output / "capture-readiness.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
