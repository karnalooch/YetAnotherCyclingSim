"""Prepare the interactive Sa Calobra owner handoff in a normal Unreal Editor.

This module is started from the guarded project Content/Python/init_unreal.py. It keeps
BOB inspector-only, loads the accepted Base_DTM map, spawns the verified
native-contact road preview, positions the primary editor viewport at the rider
view, writes a small proof, and never saves the map.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
import traceback

import unreal

MAP_PACKAGE = "/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline"

_handle = None
_started = 0.0
_done = False
_kept_objects = None


def _write_proof(root, exact_sha, status, error=""):
    payload = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "status": status,
        "error": error,
        "map": MAP_PACKAGE,
        "view": "road-contact-rider",
        "bob_mode": "INSPECTOR_ONLY",
        "map_saved": False,
    }
    (root / "owner-handoff-proof.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def _configure():
    global _kept_objects
    root = Path(os.environ["YACS_TERRAIN_CAPTURE_ROOT"])
    exact_sha = os.environ["YACS_TERRAIN_SHA"]

    profile = json.loads(
        (root / "ma2141-profile-candidate.json").read_text(encoding="utf-8")
    )
    inspection = profile.get("bob_inspection")
    if (
        not isinstance(inspection, dict)
        or inspection.get("inspection_complete") is not True
        or inspection.get("role") != "INSPECTOR_ONLY"
        or inspection.get("earthworks_authoring_permitted") is not False
        or inspection.get("geometry_repair_executed") is not False
    ):
        raise RuntimeError("BOB inspector-only contract is missing or incomplete")

    world = unreal.EditorLoadingAndSavingUtils.load_map(MAP_PACKAGE)
    if not world:
        raise RuntimeError("Could not load accepted Sa Calobra map")

    landscapes = list(
        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    )
    if (
        len(landscapes) != 1
        or len(
            landscapes[0].get_components_by_class(unreal.LandscapeComponent)
        )
        != 1024
    ):
        raise RuntimeError("Accepted Sa Calobra Landscape topology mismatch")

    neutral = unreal.load_asset("/Engine/BasicShapes/BasicShapeMaterial")
    if not neutral:
        raise RuntimeError("Neutral engine material unavailable")
    landscapes[0].set_editor_property("landscape_material", neutral)
    for component in landscapes[0].get_components_by_class(
        unreal.LandscapeComponent
    ):
        component.set_forced_lod(0)
        component.set_lod_bias(0)

    for command in (
        "viewmode lit",
        "r.AntiAliasingMethod 1",
        "r.PostProcessAAQuality 6",
        "r.ScreenPercentage 100",
        "r.RayTracing.Geometry.Landscape.LODBias -1",
    ):
        unreal.SystemLibrary.execute_console_command(world, command)

    project = Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    )
    sys.path.insert(0, str(project / "scripts/ue"))
    from ma2141_road_preview import spawn_trial

    road = spawn_trial(world, root, exact_sha)

    alignment = json.loads(
        (root / "ma2141-native-alignment.json").read_text(encoding="utf-8")
    )
    points = alignment["points_ue_cm"]

    def at_station(station_m):
        point = min(
            points,
            key=lambda item: abs(item["station_m"] - station_m),
        )
        return unreal.Vector(point["x_cm"], point["y_cm"], point["z_cm"])

    start = at_station(120)
    target = at_station(130)
    camera_location = unreal.Vector(start.x, start.y, start.z + 170)
    camera_target = unreal.Vector(target.x, target.y, target.z + 170)
    camera_rotation = unreal.MathLibrary.find_look_at_rotation(
        camera_location,
        camera_target,
    )
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    editor.set_level_viewport_camera_info(camera_location, camera_rotation)

    _kept_objects = road
    _write_proof(root, exact_sha, "PASS")
    unreal.log(
        "[OwnerHandoff] PASS; Sa Calobra + native-contact road left open "
        "at road-contact-rider."
    )


def _tick(_delta):
    global _handle, _done
    if _done or time.monotonic() - _started < 2.0:
        return
    _done = True
    try:
        _configure()
    except Exception:
        root = Path(os.environ["YACS_TERRAIN_CAPTURE_ROOT"])
        exact_sha = os.environ.get("YACS_TERRAIN_SHA", "")
        error = traceback.format_exc()
        _write_proof(root, exact_sha, "FAIL", error)
        unreal.log_error("[OwnerHandoff] " + error)
    finally:
        if _handle is not None:
            unreal.unregister_slate_post_tick_callback(_handle)
            _handle = None


def start():
    global _handle, _started
    _started = time.monotonic()
    _handle = unreal.register_slate_post_tick_callback(_tick)


start()
