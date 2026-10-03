"""Prepare the interactive Sa Calobra owner handoff in a normal Unreal Editor.

This module is started from the guarded project Content/Python/init_unreal.py. It keeps
BOB inspection plus one bounded transient cut-only builder, loads the accepted Base_DTM map, spawns the verified
native-contact road preview plus deterministic diagnostic sun/sky lighting,
positions the primary editor viewport at the rider view, writes a small proof,
and never saves the map.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

import unreal

MAP_PACKAGE = "/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline"

_handle = None
_started = 0.0
_done = False
_kept_objects = None


def _write_proof(
    root,
    exact_sha,
    status,
    error="",
    lighting=None,
    cut_patch_applied=False,
    vertical_support_built=False,
):
    payload = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "status": status,
        "error": error,
        "map": MAP_PACKAGE,
        "view": "road-contact-rider",
        "viewmode": lighting.get("viewmode") if lighting else None,
        "lighting_status": lighting.get("status") if lighting else "NOT_VERIFIED",
        "directional_light_intensity": (
            lighting.get("directional_light_intensity") if lighting else None
        ),
        "skylight_intensity": lighting.get("skylight_intensity") if lighting else None,
        "atmosphere_status": (
            lighting.get("atmosphere_status") if lighting else "NOT_VERIFIED"
        ),
        "atmosphere_preset": (
            lighting.get("atmosphere_preset") if lighting else None
        ),
        "bob_mode": "INSPECTOR_PLUS_TRANSIENT_CUT_AND_VERTICAL_SUPPORT",
        "cut_patch_applied": cut_patch_applied,
        "vertical_support_built": vertical_support_built,
        "cut_patch_layer": "Road_Earthworks" if cut_patch_applied else None,
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
        "ShowFlag.Lighting 1",
        "r.AntiAliasingMethod 1",
        "r.PostProcessAAQuality 6",
        "r.ScreenPercentage 100",
        "r.RayTracing.Geometry.Landscape.LODBias -1",
    ):
        unreal.SystemLibrary.execute_console_command(world, command)

    unreal.AutomationLibrary.set_editor_viewport_view_mode(
        unreal.ViewModeIndex.VMI_LIT
    )
    if (
        unreal.AutomationLibrary.get_editor_active_viewport_view_mode()
        != unreal.ViewModeIndex.VMI_LIT
    ):
        raise RuntimeError("Owner handoff did not enter VMI_LIT")

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    sun = actors.spawn_actor_from_class(
        unreal.DirectionalLight,
        unreal.Vector(0, 0, 300000),
        unreal.Rotator(pitch=-33, yaw=-48, roll=0),
        transient=True,
    )
    if not sun:
        raise RuntimeError("Owner handoff failed to spawn diagnostic sun")
    sun_component = sun.get_component_by_class(unreal.DirectionalLightComponent)
    if not sun_component:
        raise RuntimeError("Owner handoff diagnostic sun has no light component")
    sun_component.set_intensity(8.0)
    sun_component.set_cast_shadows(False)

    sky = actors.spawn_actor_from_class(
        unreal.SkyLight,
        unreal.Vector(0, 0, 300000),
        unreal.Rotator(),
        transient=True,
    )
    if not sky:
        raise RuntimeError("Owner handoff failed to spawn diagnostic skylight")
    sky_component = sky.get_component_by_class(unreal.SkyLightComponent)
    if not sky_component:
        raise RuntimeError("Owner handoff diagnostic skylight has no light component")
    sky_component.set_intensity(0.8)

    from scripts.ue.sa_calobra_atmosphere import spawn_mediterranean_atmosphere
    atmosphere_objects, atmosphere_proof = spawn_mediterranean_atmosphere(
        actors, sun_component, sky_component
    )

    lighting = {
        "status": "PASS",
        "viewmode": "VMI_LIT",
        "directional_light_intensity": 8.0,
        "skylight_intensity": 0.8,
        "atmosphere_status": atmosphere_proof["status"],
        "atmosphere_preset": atmosphere_proof["preset"],
    }

    project = Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    )
    sys.path.insert(0, str(project / "scripts/ue"))
    from bob_road_earthworks_cut import apply_cut_patch
    from ma2141_road_preview import spawn_trial

    road = spawn_trial(world, root, exact_sha)
    if len(road) < 4:
        raise RuntimeError("Owner handoff road trial is missing BOB CUT context")
    apply_cut_patch(world, root, exact_sha, road[3]["pre_fit"])
    from scripts.ue.current_landscape_roads import start as start_network
    network = start_network(world, root, exact_sha)

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

    # Support is constructed on a later editor tick after Landscape evaluation.
    def finish_support(_delta):
        global _kept_objects
        if time.monotonic() - support_started < 5.0:
            return
        unreal.unregister_slate_post_tick_callback(support_handle)
        try:
            from scripts.ue.bob_vertical_support_preview import spawn_support
            support = spawn_support(world, root, exact_sha, road[3])
            from scripts.ue.current_landscape_roads import finish as finish_network
            network_objects = finish_network(world, root, exact_sha, network)
            _kept_objects = (
                road, sun, sky, atmosphere_objects, support, network_objects
            )
            _write_proof(root, exact_sha, "PASS", lighting=lighting,
                         cut_patch_applied=True, vertical_support_built=True)
            unreal.log("[OwnerHandoff] CUT + vertical support ready in Lit mode")
        except Exception:  # noqa: BLE001 - report callback failure in proof
            _write_proof(root, exact_sha, "FAIL", error=traceback.format_exc())
            unreal.log_error(traceback.format_exc())

    support_started = time.monotonic()
    support_handle = unreal.register_slate_post_tick_callback(finish_support)
    _kept_objects = (road, sun, sky, atmosphere_objects)



def _tick(_delta):
    global _handle, _done
    if _done or time.monotonic() - _started < 2.0:
        return
    _done = True
    try:
        _configure()
    except Exception:  # noqa: BLE001 - report callback failure in proof
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
