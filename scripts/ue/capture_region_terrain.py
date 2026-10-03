"""Capture accepted Sa Calobra terrain and the native-contact Ma-2141 road.

BOB cuts terrain above asphalt and builds simple vertical visual support.
The builder never saves the map or modifies Base_DTM.
"""

from __future__ import annotations

import array
import json
import os
import sys
import time
import traceback
from pathlib import Path

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
_road_objects = None
_world = None
_bob_inspection_status = "NOT_LOADED"
_cut_patch = None
_cut_report = None
_support_objects = None
_network_context = None
_network_objects = None
_extreme_objects = None
_atmosphere_objects = None
_atmosphere_proof = None
_mode_reasserted = False
_scheduling = False


def height(x_cm, y_cm):
    data = array.array("H")
    data.frombytes((_root / "Prepared/terrain.r16").read_bytes())
    if sys.byteorder != "little":
        data.byteswap()
    column, row = round(x_cm / 50), round(y_cm / 50)
    if not (0 <= row < 4033 and 0 <= column < 4033):
        raise RuntimeError("Diagnostic camera sample outside native terrain")
    encoded = data[row * 4033 + column]
    return (encoded - 32768) * _manifest["scale_z"] / 128 + _manifest["location_z_cm"]


def finish(error=""):
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    keep_open = not error and os.environ.get("YACS_KEEP_EDITOR_OPEN") == "1"
    terrain_fit = (
        _road_objects[2].get("terrain_fit")
        if _road_objects
        and len(_road_objects) >= 3
        and isinstance(_road_objects[2], dict)
        else None
    )
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
        "road_status": "INFERRED_CONTACT_TRIAL" if _road_objects else "NOT_SPAWNED",
        "final_road_status": "NOT_ADMITTED",
        "bob_mode": "INSPECTOR_PLUS_TRANSIENT_CUT_AND_VERTICAL_SUPPORT",
        "bob_inspection_status": _bob_inspection_status,
        "builder_lesson_status": (
            _cut_report.get("status") if _cut_report else "NOT_EXECUTED"
        ),
        "builder_map_saved": False,
        "vertical_support_proof": ("bob-vertical-support-proof.json" if _support_objects else None),
        "bob_road_earthworks_cut_proof": (
            "bob-road-earthworks-cut-proof.json" if _cut_report else None
        ),
        "bob_cut_patch_modified_vertex_count": (
            _cut_report.get("patch_modified_vertex_count") if _cut_report else None
        ),
        "bob_cut_before_count": (
            _cut_report.get("before", {}).get("class_counts", {}).get("CUT_REQUIRED")
            if _cut_report else None
        ),
        "bob_cut_after_count": (
            _cut_report.get("after", {}).get("class_counts", {}).get("CUT_REQUIRED")
            if _cut_report else None
        ),
        "road_geometry_inspection_required": True,
        "road_geometry_inspection_views": [
            "road-geometry-inspection-before",
            "road-geometry-inspection-after",
        ],
        "road_terrain_fit_status": (
            terrain_fit.get("status") if terrain_fit else "NOT_MEASURED"
        ),
        "road_terrain_fit_inspection_complete": (
            terrain_fit.get("inspection_complete", False)
            if terrain_fit
            else False
        ),
        "road_terrain_fit_proof": (
            "ma2141-road-terrain-fit-proof.json" if terrain_fit else None
        ),
        "atmosphere": _atmosphere_proof,
        "editor_handoff_requested": keep_open,
        "editor_handoff_map": _manifest["map_package"] if keep_open else None,
        "editor_handoff_view": _views[-1]["name"] if keep_open and _views else None,
    }
    (_root / "terrain-capture-proof.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    if error:
        unreal.log_error("[RegionTerrainCapture] " + error)
    elif keep_open:
        unreal.log(
            "[RegionTerrainCapture] PASS; leaving Editor open on "
            + result["editor_handoff_view"]
        )
    unreal.EditorPythonScripting.set_keep_python_script_alive(keep_open)


def _apply_capture_view_mode(view):
    """Apply and verify the requested editor diagnostic mode for one capture."""
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    road_component = None
    if _road_objects:
        road_component = _road_objects[0].get_component_by_class(
            unreal.DynamicMeshComponent
        )

    if view.get("geometry_inspection") is True:
        if road_component is None:
            raise RuntimeError("Geometry inspection requires spawned road geometry")
        unreal.AutomationLibrary.set_editor_viewport_view_mode(
            unreal.ViewModeIndex.VMI_CLAY
        )
        unreal.AutomationLibrary.set_editor_active_viewport_wireframe_opacity(1.0)
        unreal.SystemLibrary.execute_console_command(_world, "ShowFlag.MeshEdges 1")
        unreal.SystemLibrary.execute_console_command(
            _world, "ShowFlag.SelectionOutline 1"
        )

        # Selection outlines are editor UI and are not guaranteed to survive a
        # high-res camera capture. DynamicMesh's explicit wireframe pass is real
        # rendered geometry, so the diagnostic overlay is preserved in evidence.
        road_component.set_enable_wireframe_render_pass(True)
        road_component.set_editor_property("explicit_show_wireframe", True)
        road_component.set_editor_property(
            "wireframe_color",
            unreal.LinearColor(0.0, 1.0, 1.0, 1.0),
        )
        road_component.set_view_mode_overrides_enabled(True)
        actors.set_selected_level_actors([_road_objects[0]])

        actual = unreal.AutomationLibrary.get_editor_active_viewport_view_mode()
        if actual != unreal.ViewModeIndex.VMI_CLAY:
            raise RuntimeError("Geometry Inspection Clay view mode did not activate")
        opacity = (
            unreal.AutomationLibrary.get_editor_active_viewport_wireframe_opacity()
        )
        if opacity < 0.99:
            raise RuntimeError("Geometry Inspection wireframe opacity did not activate")
        if road_component.get_enable_wireframe_render_pass() is not True:
            raise RuntimeError("Road explicit wireframe render pass did not activate")
        return

    if road_component is not None:
        road_component.set_enable_wireframe_render_pass(False)
        road_component.set_editor_property("explicit_show_wireframe", False)
    unreal.AutomationLibrary.set_editor_viewport_view_mode(
        unreal.ViewModeIndex.VMI_LIT
    )
    unreal.SystemLibrary.execute_console_command(_world, "ShowFlag.MeshEdges 0")
    actors.clear_actor_selection_set()


def schedule():
    global _task, _started, _road_objects, _cut_patch, _scheduling
    global _mode_reasserted, _network_context, _network_objects, _extreme_objects
    # Geometry creation can pump Slate and re-enter this tick callback while the
    # previous screenshot task is still marked done. Fence the whole transition.
    _scheduling = True
    _task = None
    _mode_reasserted = False
    try:
        if _index == 2:
            sys.path.insert(
                0,
                str(
                    Path(
                        unreal.Paths.convert_relative_path_to_full(
                            unreal.Paths.project_dir()
                        )
                    )
                    / "scripts/ue"
                ),
            )
            from ma2141_road_preview import spawn_trial

            _road_objects = spawn_trial(
                _world, _root, os.environ["YACS_TERRAIN_SHA"]
            )
        if _index == 3:
            if not _road_objects or len(_road_objects) < 4:
                raise RuntimeError("BOB CUT patch is missing road trial context")
            from bob_road_earthworks_cut import apply_cut_patch

            _cut_patch = apply_cut_patch(
                _world,
                _root,
                os.environ["YACS_TERRAIN_SHA"],
                _road_objects[3]["pre_fit"],
            )
        if _index == 5:
            from scripts.ue.current_landscape_roads import start
            _network_context = start(_world, _root, os.environ["YACS_TERRAIN_SHA"])
        if _index == 6:
            from scripts.ue.current_landscape_roads import finish as finish_network
            _network_objects = finish_network(_world, _root, os.environ["YACS_TERRAIN_SHA"], _network_context)
        if _views[_index]["name"] == "network-extreme-cut":
            from scripts.ue.current_landscape_roads import spawn_extreme_cut_diagnostic

            _extreme_objects = spawn_extreme_cut_diagnostic(
                _world, _network_context
            )
        view = _views[_index]
        _apply_capture_view_mode(view)
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
            comparison_notes="Sa Calobra terrain / inferred pavement contact trial",
            delay=5.0,
            force_game_view=view.get("force_game_view", True),
        )
        if not _task or not _task.is_valid_task():
            raise RuntimeError("Invalid terrain screenshot task")
        _started = time.monotonic()
    finally:
        _scheduling = False


def tick(_delta):
    global _index, _mode_reasserted, _scheduling
    if _scheduling or _task is None:
        return
    try:
        view = _views[_index]
        elapsed = time.monotonic() - _started
        if (
            view.get("geometry_inspection") is True
            and not _mode_reasserted
            and elapsed >= 2.0
        ):
            # Procedural Landscape evaluation can reset the editor viewport mode
            # after the patch is registered. Reassert Clay after that update but
            # before the 5 s high-res screenshot delay expires.
            _apply_capture_view_mode(view)
            _mode_reasserted = True
        if elapsed > 120:
            finish("Screenshot task/file readiness timeout: " + _views[_index]["name"])
        elif _task.is_task_done():
            global _cut_report, _support_objects
            path = _root / (view["name"] + ".png")
            if not path.is_file() or path.stat().st_size < 100000:
                # A completed automation task can precede the PNG write. Keep
                # the existing size requirement and bounded timeout.
                return
            actual_viewmode = (
                unreal.AutomationLibrary.get_editor_active_viewport_view_mode()
            )
            expected_viewmode = (
                unreal.ViewModeIndex.VMI_CLAY
                if view.get("geometry_inspection") is True
                else unreal.ViewModeIndex.VMI_LIT
            )
            if actual_viewmode != expected_viewmode:
                raise RuntimeError(
                    "Capture viewport mode drifted before evidence acceptance: "
                    + view["name"]
                )
            actual_viewmode_name = (
                "VMI_CLAY"
                if actual_viewmode == unreal.ViewModeIndex.VMI_CLAY
                else "VMI_LIT"
            )
            if view.get("verify_cut_after") is True and _cut_report is None:
                from bob_road_earthworks_cut import (
                    finalize_cut_proof,
                    measure_smooth_terrain_fit,
                )

                _scheduling = True
                try:
                    context = _road_objects[3]
                    post_fit = measure_smooth_terrain_fit(
                        _world,
                        context["profile"],
                        context["smooth_vertices"],
                        context["smooth_meta"],
                        exact_sha=os.environ["YACS_TERRAIN_SHA"],
                        contact_band_max_m=context["pavement_thickness_m"],
                        geometry_inspection_view="road-geometry-inspection-after",
                    )
                    (_root / "ma2141-road-terrain-fit-after-cut-proof.json").write_text(
                        json.dumps(post_fit, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    _cut_report = finalize_cut_proof(
                        _root,
                        os.environ["YACS_TERRAIN_SHA"],
                        _cut_patch,
                        context["pre_fit"],
                        post_fit,
                        reject_on_failure=False,
                    )
                    from scripts.ue.bob_vertical_support_preview import spawn_support
                    _support_objects = spawn_support(
                        _world, _root, os.environ["YACS_TERRAIN_SHA"], context
                    )
                finally:
                    _scheduling = False
            _proofs.append(
                {
                    **view,
                    "screenshot": str(path),
                    "size_bytes": path.stat().st_size,
                    "resolution": [3840, 2160],
                    "viewmode": view.get(
                        "viewmode", "lit-with-neutral-engine-material"
                    ),
                    "actual_viewmode": actual_viewmode_name,
                    "geometry_inspection": view.get(
                        "geometry_inspection", False
                    ),
                    "inspection_mode": view.get("inspection_mode"),
                    "mesh_edges": view.get("mesh_edges", False),
                    "road_selected": view.get("road_selected", False),
                    "explicit_road_wireframe": view.get(
                        "explicit_road_wireframe", False
                    ),
                    "wireframe_color_rgba": view.get("wireframe_color_rgba"),
                    "force_game_view": view.get("force_game_view", True),
                    "fov_deg": 74,
                    "fog": _atmosphere_proof is not None,
                    "shadows": False,
                }
            )
            _index += 1
            if _index == len(_views):
                finish()
            else:
                schedule()
    except Exception:  # noqa: BLE001 - report callback failure in proof
        finish(traceback.format_exc())


def main():
    global _manifest, _root, _camera, _views, _handle, _world
    global _bob_inspection_status, _atmosphere_objects, _atmosphere_proof
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
    profile = json.loads(
        (_root / "ma2141-profile-candidate.json").read_text(encoding="utf-8")
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
    _bob_inspection_status = inspection["status"]

    world = unreal.EditorLoadingAndSavingUtils.load_map(_manifest["map_package"])
    _world = world
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
    neutral = unreal.load_asset("/Engine/BasicShapes/BasicShapeMaterial")
    if not neutral:
        raise RuntimeError("Engine neutral basic-shape material unavailable")
    landscapes[0].set_editor_property("landscape_material", neutral)
    for component in landscapes[0].get_components_by_class(unreal.LandscapeComponent):
        component.set_forced_lod(0)
        component.set_lod_bias(0)
    for command in [
        "viewmode lit",
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
    sky_component = sky.get_component_by_class(unreal.SkyLightComponent)
    sky_component.set_intensity(0.8)
    project = Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    )
    sys.path.insert(0, str(project))
    sys.path.insert(0, str(project / "scripts/ue"))
    from sa_calobra_atmosphere import spawn_mediterranean_atmosphere
    _atmosphere_objects, _atmosphere_proof = spawn_mediterranean_atmosphere(
        actors, light, sky_component
    )
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
    alignment = json.loads((_root / "ma2141-native-alignment.json").read_text(encoding="utf-8"))
    network = json.loads((_root / "Network/network.json").read_text(encoding="utf-8"))
    from scripts.geometry.network_visual_preview import overview_camera
    full_camera = overview_camera(network["full_preview"])
    extreme = network.get("extreme_cut_case")
    if not isinstance(extreme, dict):
        raise RuntimeError("Extreme network CUT case is missing")
    extreme_cut = extreme["cut_depth"]
    extreme_x_cm = extreme_cut["peak_local_xy_m"][0] * 100
    extreme_y_cm = extreme_cut["peak_local_xy_m"][1] * 100
    extreme_top_cm = extreme_cut["peak_base_height_m"] * 100
    extreme_bottom_cm = extreme_cut["peak_target_height_m"] * 100
    points = alignment["points_ue_cm"]
    def at_station(s):
        p = min(points, key=lambda p: abs(p["station_m"]-s))
        return [p["x_cm"],p["y_cm"],p["z_cm"]]
    focus = at_station(150)
    moderate = at_station(65)
    start, target = at_station(120), at_station(130)
    _views.extend([
        {
            "name": "road-geometry-inspection-before",
            "location": [focus[0]-9000,focus[1]+9000,focus[2]+13000],
            "target": focus,
            "viewmode": "geometry-inspection-clay-wireframe",
            "geometry_inspection": True,
            "inspection_mode": "VMI_CLAY",
            "mesh_edges": True,
            "road_selected": True,
            "explicit_road_wireframe": True,
            "wireframe_color_rgba": [0.0, 1.0, 1.0, 1.0],
            "force_game_view": False,
            "earthworks_state": "BEFORE_CUT",
        },
        {
            "name": "road-geometry-inspection-after",
            "location": [focus[0]-9000,focus[1]+9000,focus[2]+13000],
            "target": focus,
            "viewmode": "geometry-inspection-clay-wireframe",
            "geometry_inspection": True,
            "inspection_mode": "VMI_CLAY",
            "mesh_edges": True,
            "road_selected": True,
            "explicit_road_wireframe": True,
            "wireframe_color_rgba": [0.0, 1.0, 1.0, 1.0],
            "force_game_view": False,
            "earthworks_state": "AFTER_CUT",
            "verify_cut_after": True,
        },
        {
            "name": "road-geometry-inspection-support",
            "location": [focus[0]-9000,focus[1]+9000,focus[2]+13000],
            "target": focus,
            "viewmode": "geometry-inspection-clay-wireframe",
            "geometry_inspection": True,
            "inspection_mode": "VMI_CLAY",
            "mesh_edges": True,
            "road_selected": True,
            "explicit_road_wireframe": True,
            "wireframe_color_rgba": [0.0, 1.0, 1.0, 1.0],
            "force_game_view": False,
            "earthworks_state": "CUT_AND_VERTICAL_SUPPORT",
        },
        {
            "name": "road-curved-edges-plan",
            "location": [focus[0], focus[1], focus[2]+16000],
            "target": focus,
        },
        {
            "name": "road-curved-edges-moderate",
            "location": [moderate[0], moderate[1], moderate[2]+5500],
            "target": moderate,
        },
        {
            "name": "road-contact-overview",
            "location": [focus[0]-9000,focus[1]+9000,focus[2]+13000],
            "target": focus,
        },
        {
            "name": "network-current-landscape-overview",
            "location": [v * 100 for v in full_camera["location_m"]],
            "target": [v * 100 for v in full_camera["target_m"]],
            "full_source_context": True,
            "full_context_fingerprint": network["full_preview_proof"]["fingerprint"],
            "source_location_marker": "amber",
            "rejected_pavement": "red",
            "road_admitted": False,
        },
        {
            "name": "network-extreme-cut",
            "location": [
                extreme_x_cm - 6000,
                extreme_y_cm + 6000,
                extreme_top_cm + 5000,
            ],
            "target": [
                extreme_x_cm,
                extreme_y_cm,
                (extreme_top_cm + extreme_bottom_cm) / 2,
            ],
            "extreme_case_id": extreme["id"],
            "required_cut_m": extreme_cut["max_cut_m"],
            "profile_fit_status": extreme["height_profile_fit"]["status"],
            "diagnostic_colors": {
                "rejected_asphalt": "red",
                "least_bad_lateral_diagnostic": "cyan",
                "deepest_cut_marker": "yellow",
            },
            "least_bad_lateral_shift_m": extreme["lateral_sweep"][
                "best_candidate"
            ]["shift_m"],
            "street_view_url": extreme["review"]["street_view_url"],
            "anomaly_classification": extreme["review"]["classification"],
            "geometry_repair_executed": False,
            "height_change_applied": False,
            "lateral_change_applied": False,
        },
        {
            "name": "road-contact-rider",
            "location": [start[0],start[1],start[2]+170],
            "target": [target[0],target[1],target[2]+170],
        },
    ])
    _camera = actors.spawn_actor_from_class(
        unreal.CameraActor, unreal.Vector(), unreal.Rotator(), transient=True
    )
    _camera.set_actor_label("YACS owner handoff - road-contact-rider")
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
