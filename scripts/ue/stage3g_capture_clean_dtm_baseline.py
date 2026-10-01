"""Create, persist, reload and render a clean DTM-only Landscape in a new map."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
MAP = "/Game/Prototype/Maps/L_PassoGiauTerrainRecovery"
OUTPUT = Path(os.environ["YACS_CLEAN_BASELINE_OUTPUT"])
OUTPUT.mkdir(parents=True, exist_ok=True)
REPORT = {
    "schema_version": 1,
    "status": "STARTED",
    "map": MAP,
    "earthworks_applied": False,
    "local_skin_created": False,
    "source_map_modified": False,
    "terrain_quality_accepted": False,
}
task = None
handle = None
started = 0.0


def finish(success: bool, error: str = "") -> None:
    global handle
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
        handle = None
    REPORT["status"] = "PASS" if success else "FAIL"
    if error:
        REPORT["error"] = error
    png = OUTPUT / "clean_baseline_rider.png"
    if success:
        data = png.read_bytes()
        REPORT["screenshot_sha256"] = hashlib.sha256(data).hexdigest()
        REPORT["screenshot_base64"] = base64.b64encode(data).decode("ascii")
    (OUTPUT / "clean_baseline_proof.json").write_text(
        json.dumps(REPORT, indent=2) + "\n", encoding="utf-8"
    )
    unreal.log(f"[YacsCleanBaseline] {'PASS' if success else 'FAIL'}: {error}")
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def tick(_delta: float) -> None:
    if task.is_task_done():
        png = OUTPUT / "clean_baseline_rider.png"
        finish(png.is_file() and png.stat().st_size > 100000, "")
    elif time.monotonic() - started > 90:
        finish(False, "clean baseline screenshot timed out")


def verify(landscape, heightmap: Path, phase: str) -> None:
    result = json.loads(
        unreal.YacsLandscapeRecoveryLibrary.verify_baseline_heights(
            landscape, str(heightmap)
        )
    )
    REPORT[phase] = result
    if result.get("status") != "PASS" or result.get("sample_count") != 4033 * 4033:
        raise RuntimeError(f"Clean DTM height readback failed ({phase}): {result}")


def main() -> None:
    global task, handle, started
    metadata_path = (
        ROOT
        / "ExternalAssets/Terrain/PassoGiau/PreparedNearField/full_dtm_baseline.json"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    heightmap = metadata_path.parent / metadata["binary"]["file"]
    binary = heightmap.read_bytes()
    if (
        len(binary) != 4033 * 4033 * 2
        or hashlib.sha256(binary).hexdigest() != metadata["binary"]["sha256"]
    ):
        raise RuntimeError("Clean baseline R16 transport integrity failed")
    REPORT["source"] = metadata
    source_map = ROOT / "Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap"
    source_hash = hashlib.sha256(source_map.read_bytes()).hexdigest()
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    phase = os.environ["YACS_CLEAN_BASELINE_PHASE"]
    proof_path = OUTPUT / "clean_baseline_proof.json"
    if phase == "import":
        if unreal.EditorAssetLibrary.does_asset_exist(MAP):
            raise RuntimeError("Recovery map exists; retain it before another import")
        if not levels.new_level(MAP, is_partitioned_world=False):
            raise RuntimeError("Could not create separate recovery map")
        world = unreal.get_editor_subsystem(
            unreal.UnrealEditorSubsystem
        ).get_editor_world()
        transform = metadata["transform"]
        scale = unreal.Vector(
            transform["scale_x_cm_per_vertex"],
            transform["scale_y_cm_per_vertex"],
            transform["scale_z"],
        )
        location = unreal.Vector(
            0, 0, transform["location_z_cm_for_sea_level_preservation"]
        )
        landscape = unreal.YacsLandscapeRecoveryLibrary.import_clean_baseline(
            world, str(heightmap), scale, location
        )
        if landscape is None:
            raise RuntimeError("Native clean Landscape import failed")
        verify(landscape, heightmap, "after_import")
        if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
            raise RuntimeError("Recovery map save failed")
        if hashlib.sha256(source_map.read_bytes()).hexdigest() != source_hash:
            raise RuntimeError("Original map changed during clean import")
        REPORT.update(
            status="IMPORTED_PENDING_RELOAD",
            source_map_sha256=source_hash,
            import_process_id=os.getpid(),
            exact_sha=os.environ["YACS_CLEAN_BASELINE_SHA"],
        )
        proof_path.write_text(json.dumps(REPORT, indent=2) + "\n", encoding="utf-8")
        unreal.log("[YacsCleanBaseline] IMPORTED_PENDING_RELOAD")
        return
    if phase != "verify":
        raise RuntimeError("Unknown clean baseline phase")
    previous = json.loads(proof_path.read_text(encoding="utf-8"))
    if (
        previous["status"] != "IMPORTED_PENDING_RELOAD"
        or previous["exact_sha"] != os.environ["YACS_CLEAN_BASELINE_SHA"]
        or previous["import_process_id"] == os.getpid()
        or previous["source_map_sha256"] != source_hash
    ):
        raise RuntimeError("Fresh-process reload provenance check failed")
    REPORT.update(previous)
    REPORT["reload_process_id"] = os.getpid()
    if not levels.load_level(MAP):
        raise RuntimeError("Recovery map reload failed")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    landscapes = [
        actor
        for actor in actors.get_all_level_actors()
        if isinstance(actor, unreal.Landscape)
    ]
    if len(landscapes) != 1:
        raise RuntimeError("Recovery map must contain exactly one Landscape")
    landscape = landscapes[0]
    verify(landscape, heightmap, "after_save_reload")
    REPORT["persisted_recovery_map"] = True
    components = landscape.get_components_by_class(unreal.LandscapeComponent)
    if len(components) != 1024:
        raise RuntimeError(
            f"Unexpected clean Landscape topology: {len(components)} components"
        )
    for component in components:
        component.set_editor_property("forced_lod", 0)
    landscape.set_editor_property(
        "landscape_material",
        unreal.load_asset("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"),
    )

    # Use the exact camera frame computed by the ordinary A diagnostic. This
    # script runs after A, so no independent focus selection can drift.
    reference = json.loads(
        (OUTPUT.parent / "A/surface_ownership_a_proof.json").read_text(encoding="utf-8")
    )
    frame = reference["camera_frame"]
    camera_location = unreal.Vector(*reference["camera_location_cm"])
    camera_rotation = unreal.Rotator(
        pitch=reference["camera_rotation_deg"][0],
        yaw=reference["camera_rotation_deg"][1],
        roll=reference["camera_rotation_deg"][2],
    )
    camera = actors.spawn_actor_from_class(
        unreal.CameraActor, camera_location, camera_rotation, transient=True
    )
    camera.get_component_by_class(unreal.CameraComponent).set_editor_property(
        "field_of_view", 76.0
    )
    sun = actors.spawn_actor_from_class(
        unreal.DirectionalLight,
        camera_location + unreal.Vector(0, 0, 200000),
        unreal.Rotator(pitch=-32, yaw=-55, roll=0),
        transient=True,
    )
    light = sun.get_component_by_class(unreal.DirectionalLightComponent)
    light.set_intensity(5.0)
    light.set_cast_shadows(False)
    sky = actors.spawn_actor_from_class(
        unreal.SkyLight, camera_location, unreal.Rotator(), transient=True
    )
    sky.get_component_by_class(unreal.SkyLightComponent).set_intensity(1.0)
    actors.spawn_actor_from_class(
        unreal.SkyAtmosphere, unreal.Vector(), unreal.Rotator(), transient=True
    )
    fog = actors.spawn_actor_from_class(
        unreal.ExponentialHeightFog, camera_location, unreal.Rotator(), transient=True
    )
    fog_component = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fog_component.set_editor_property("fog_density", 0.00018)
    fog_component.set_editor_property("fog_height_falloff", 0.22)
    fog_component.set_editor_property("fog_max_opacity", 0.16)
    for command in [
        "viewmode lit",
        "r.AntiAliasingMethod 1",
        "r.PostProcessAAQuality 6",
        "r.ScreenPercentage 100",
        "r.RayTracing.Geometry.Landscape.LODBias -1",
    ]:
        unreal.SystemLibrary.execute_console_command(world, command)
    REPORT["camera_frame"] = frame
    REPORT["camera_location_cm"] = reference["camera_location_cm"]
    REPORT["camera_rotation_deg"] = reference["camera_rotation_deg"]
    from scripts.ue.prepare_landscape_capture import prepare_capture

    REPORT["capture_preparation"] = prepare_capture(
        unreal,
        landscape,
        camera_location,
        camera_rotation,
        OUTPUT,
        request_height_mips=True,
    )
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    task = unreal.AutomationLibrary.take_high_res_screenshot(
        3840,
        2160,
        str(OUTPUT / "clean_baseline_rider.png"),
        camera=camera,
        delay=3.0,
        force_game_view=True,
    )
    if not task or not task.is_valid_task():
        raise RuntimeError("Invalid clean baseline screenshot task")
    started = time.monotonic()
    handle = unreal.register_slate_post_tick_callback(tick)


try:
    main()
except Exception as exc:
    unreal.log_error(traceback.format_exc())
    finish(False, str(exc))
    raise
