"""Capture isolated native terrain using the established UE screenshot task pattern.

Diagnostic only: no road, material camouflage or gameplay/performance acceptance.
"""

from __future__ import annotations

import array
import json
import os
from pathlib import Path
import sys
import time
import traceback

import unreal

_manifest = {}
_root = None
_camera = None
_task = None
_handle = None
_started = 0.0
_index = 0
_views = []
_proofs = []


def height(x_cm, y_cm):
    data = array.array("H")
    data.frombytes((_root / "Prepared/terrain.r16").read_bytes())
    if sys.byteorder != "little":
        data.byteswap()
    column, row = int(round(x_cm / 50)), int(round(y_cm / 50))
    if not (0 <= row < 4033 and 0 <= column < 4033):
        raise RuntimeError("Diagnostic camera sample outside native terrain")
    encoded = data[row * 4033 + column]
    return (encoded - 32768) * _manifest["scale_z"] / 128 + _manifest["location_z_cm"]


def finish(error=""):
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    result = {
        "schema_version": 1,
        "exact_sha": os.environ["YACS_TERRAIN_SHA"],
        "region_id": "sa_calobra",
        "map": _manifest["map_package"],
        "technical_capture_status": "FAIL" if error else "PASS",
        "error": error,
        "captures": _proofs,
        "human_visual_status": "PENDING",
        "performance_status": "PENDING",
        "road_status": "NOT_AUTHORED",
    }
    (_root / "terrain-capture-proof.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    if error:
        unreal.log_error("[RegionTerrainCapture] " + error)
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def schedule():
    global _task, _started
    view = _views[_index]
    location, target = unreal.Vector(*view["location"]), unreal.Vector(*view["target"])
    _camera.set_actor_location(location, False, False)
    _camera.set_actor_rotation(
        unreal.MathLibrary.find_look_at_rotation(location, target), False
    )
    path = _root / (view["name"] + ".png")
    if path.exists():
        raise RuntimeError("Screenshot already exists; never overwrite evidence")
    _task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=3840,
        res_y=2160,
        filename=str(path),
        camera=_camera,
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes="Sa Calobra native terrain-only diagnostic",
        delay=5.0,
        force_game_view=True,
    )
    if not _task or not _task.is_valid_task():
        raise RuntimeError("Invalid terrain screenshot task")
    _started = time.monotonic()


def tick(_delta):
    global _index
    try:
        if time.monotonic() - _started > 120:
            finish("Screenshot task timeout")
        elif _task.is_task_done():
            view = _views[_index]
            path = _root / (view["name"] + ".png")
            if not path.is_file() or path.stat().st_size < 100000:
                finish("Screenshot task produced no usable PNG")
                return
            _proofs.append(
                {
                    **view,
                    "screenshot": str(path),
                    "size_bytes": path.stat().st_size,
                    "resolution": [3840, 2160],
                    "viewmode": "lightingonly",
                    "fov_deg": 74,
                    "fog": False,
                    "shadows": False,
                }
            )
            _index += 1
            if _index == len(_views):
                finish()
            else:
                schedule()
    except Exception:
        finish(traceback.format_exc())


def main():
    global _manifest, _root, _camera, _views, _handle
    _root = Path(os.environ["YACS_TERRAIN_CAPTURE_ROOT"])
    _manifest = json.loads(
        (_root / "Prepared/terrain-import.json").read_text(encoding="utf-8")
    )
    if (
        _manifest["region_id"] != "sa_calobra"
        or _manifest["map_package"]
        != "/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline"
    ):
        raise RuntimeError("Unadmitted terrain capture identity")
    world = unreal.EditorLoadingAndSavingUtils.load_map(_manifest["map_package"])
    if not world:
        raise RuntimeError("Could not load imported native terrain map")
    landscapes = list(
        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    )
    if (
        len(landscapes) != 1
        or len(landscapes[0].get_components_by_class(unreal.LandscapeComponent)) != 1024
    ):
        raise RuntimeError("Imported terrain topology mismatch")
    for component in landscapes[0].get_components_by_class(unreal.LandscapeComponent):
        component.set_forced_lod(0)
        component.set_lod_bias(0)
    for command in [
        "viewmode lightingonly",
        "r.AntiAliasingMethod 1",
        "r.PostProcessAAQuality 6",
        "r.ScreenPercentage 100",
        "r.RayTracing.Geometry.Landscape.LODBias -1",
    ]:
        unreal.SystemLibrary.execute_console_command(world, command)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    sun = actors.spawn_actor_from_class(
        unreal.DirectionalLight,
        unreal.Vector(0, 0, 300000),
        unreal.Rotator(pitch=-33, yaw=-48, roll=0),
        transient=True,
    )
    light = sun.get_component_by_class(unreal.DirectionalLightComponent)
    light.set_intensity(8)
    light.set_cast_shadows(False)
    sky = actors.spawn_actor_from_class(
        unreal.SkyLight, unreal.Vector(0, 0, 300000), unreal.Rotator(), transient=True
    )
    sky.get_component_by_class(unreal.SkyLightComponent).set_intensity(0.8)
    center = [100800.0, 100800.0]
    _views = [
        {
            "name": "terrain-overview",
            "location": [-35000, center[1], _manifest["elevation_max_m"] * 100 + 90000],
            "target": [*center, height(*center)],
        },
        {
            "name": "terrain-near-ground",
            "location": [125000, 85000, height(125000, 85000) + 170],
            "target": [127000, 87000, height(127000, 87000) + 170],
        },
    ]
    _camera = actors.spawn_actor_from_class(
        unreal.CameraActor, unreal.Vector(), unreal.Rotator(), transient=True
    )
    _camera.get_component_by_class(unreal.CameraComponent).set_editor_property(
        "field_of_view", 74.0
    )
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    schedule()
    _handle = unreal.register_slate_post_tick_callback(tick)


try:
    main()
except Exception:
    if _root is not None:
        finish(traceback.format_exc())
    raise
