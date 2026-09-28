"""Render a deterministic visual proof of the isolated Passo Giau Landscape."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
import traceback

import unreal


SPIKE_MAP = "/Game/Prototype/Maps/L_PassoGiauTerrainSpike"
_task = None
_tick_handle = None
_started_at = 0.0
_output_path: Path | None = None
_proof_path: Path | None = None
_camera = None


def _finish(success: bool, error: str = "") -> None:
    global _tick_handle
    if _tick_handle is not None:
        unreal.unregister_slate_post_tick_callback(_tick_handle)
        _tick_handle = None

    if success and _output_path is not None and _proof_path is not None:
        proof = {
            "schema_version": 1,
            "passo_giau_landscape_capture": "PASS",
            "map": SPIKE_MAP,
            "screenshot": str(_output_path),
            "screenshot_bytes": _output_path.stat().st_size,
            "resolution": [1920, 1080],
            "camera_location_cm": [
                float(_camera.get_actor_location().x),
                float(_camera.get_actor_location().y),
                float(_camera.get_actor_location().z),
            ],
            "camera_rotation_deg": [
                float(_camera.get_actor_rotation().pitch),
                float(_camera.get_actor_rotation().yaw),
                float(_camera.get_actor_rotation().roll),
            ],
            "visual_acceptance": "PENDING_HUMAN_REVIEW",
            "presentation_only": True,
        }
        _proof_path.parent.mkdir(parents=True, exist_ok=True)
        _proof_path.write_text(
            json.dumps(proof, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        unreal.log(
            f"[PassoGiauCapture] PASS: {_output_path} "
            f"({_output_path.stat().st_size} bytes)"
        )
    elif error:
        unreal.log_error(f"[PassoGiauCapture] FAILURE: {error}")

    # Dropping keep-alive is sufficient for -ExecutePythonScript and lets UE
    # perform editor shutdown on the next tick. Calling quit_editor() from the
    # Slate post-tick callback can race Python/Slate teardown in UE 5.8.
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def _tick(_delta_time: float) -> None:
    if _task is None:
        _finish(False, "screenshot task was not initialized")
        return

    if _task.is_task_done():
        if (
            _output_path is not None
            and _output_path.is_file()
            and _output_path.stat().st_size >= 100_000
        ):
            _finish(True)
        else:
            _finish(False, "screenshot task completed without a valid PNG")
        return

    if time.monotonic() - _started_at > 90.0:
        _finish(False, "screenshot task timed out after 90 seconds")


def main() -> None:
    global _task, _tick_handle, _started_at, _output_path, _proof_path, _camera

    output_value = os.environ.get("YACS_PASSO_GIAU_CAPTURE_PNG", "")
    proof_value = os.environ.get("YACS_PASSO_GIAU_CAPTURE_PROOF", "")
    if not output_value or not proof_value:
        raise RuntimeError(
            "YACS_PASSO_GIAU_CAPTURE_PNG and YACS_PASSO_GIAU_CAPTURE_PROOF are required"
        )

    _output_path = Path(output_value)
    _proof_path = Path(proof_value)
    _output_path.parent.mkdir(parents=True, exist_ok=True)
    _output_path.unlink(missing_ok=True)
    _proof_path.unlink(missing_ok=True)

    world = unreal.EditorLoadingAndSavingUtils.load_map(SPIKE_MAP)
    if not world:
        raise RuntimeError(f"failed to load {SPIKE_MAP}")

    landscapes = list(
        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    )
    if len(landscapes) != 1:
        raise RuntimeError(f"expected exactly one Landscape, found {len(landscapes)}")

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    sun = actor_subsystem.spawn_actor_from_class(
        unreal.DirectionalLight,
        unreal.Vector(400000.0, 400000.0, 400000.0),
        unreal.Rotator(pitch=-33.0, yaw=-48.0, roll=0.0),
        transient=True,
    )
    sun.set_actor_label("PassoGiau_ProofSun")
    sun_component = sun.get_component_by_class(unreal.DirectionalLightComponent)
    sun_component.set_intensity(8.0)

    sky = actor_subsystem.spawn_actor_from_class(
        unreal.SkyLight,
        unreal.Vector(400000.0, 400000.0, 300000.0),
        unreal.Rotator(),
        transient=True,
    )
    sky.set_actor_label("PassoGiau_ProofSky")
    sky.get_component_by_class(unreal.SkyLightComponent).set_intensity(0.8)

    atmosphere = actor_subsystem.spawn_actor_from_class(
        unreal.SkyAtmosphere,
        unreal.Vector(),
        unreal.Rotator(),
        transient=True,
    )
    atmosphere.set_actor_label("PassoGiau_ProofAtmosphere")

    fog = actor_subsystem.spawn_actor_from_class(
        unreal.ExponentialHeightFog,
        unreal.Vector(400000.0, 400000.0, 120000.0),
        unreal.Rotator(),
        transient=True,
    )
    fog.set_actor_label("PassoGiau_ProofFog")
    fog_component = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fog_component.set_editor_property("fog_density", 0.0007)
    fog_component.set_editor_property("fog_height_falloff", 0.15)
    fog_component.set_editor_property("fog_max_opacity", 0.35)

    camera_location = unreal.Vector(-180000.0, 400000.0, 335000.0)
    target = unreal.Vector(400000.0, 400000.0, 195000.0)
    camera_rotation = unreal.MathLibrary.find_look_at_rotation(camera_location, target)
    _camera = actor_subsystem.spawn_actor_from_class(
        unreal.CameraActor,
        camera_location,
        camera_rotation,
        transient=True,
    )
    _camera.set_actor_label("PassoGiau_ProofCamera")
    camera_component = _camera.get_component_by_class(unreal.CameraComponent)
    if camera_component is None:
        raise RuntimeError("spawned CameraActor has no CameraComponent")
    camera_component.set_editor_property("field_of_view", 74.0)

    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    _task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=1920,
        res_y=1080,
        filename=str(_output_path),
        camera=_camera,
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes="Stage 3G R4.1B Passo Giau isolated Landscape proof",
        delay=2.0,
        force_game_view=True,
    )
    if not _task or not _task.is_valid_task():
        raise RuntimeError("AutomationLibrary returned an invalid screenshot task")

    _started_at = time.monotonic()
    _tick_handle = unreal.register_slate_post_tick_callback(_tick)
    unreal.log(
        "[PassoGiauCapture] screenshot scheduled: "
        f"{_output_path} from camera {camera_location}"
    )


try:
    main()
except Exception as exc:
    unreal.log_error(f"[PassoGiauCapture] FAILURE: {exc}")
    unreal.log_error(traceback.format_exc())
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)
    raise
