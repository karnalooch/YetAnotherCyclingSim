"""Run a presentation-only 100 W ride-through over the active SP638 hairpin.

This stage is intentionally diagnostic. It reuses the transient B.4.8 road-first
asphalt/shoulder geometry plus the conformed Landscape created by
stage3g_capture_sp638_local_corridor.py in the same R4.1 editor session. It does
not promote SP638 visual geometry to physics authority.

The rider pace uses the Python reference cycling model with the prototype rider
fixture and the local 3D spline grade. The camera starts 100 m before the
selected hairpin with a rolling 2.5 m/s initial speed and holds 100 W / 90 rpm.
Frame-time samples come from the live editor viewport ride. After the live pass,
the stage captures fixed 1920x1080 Lighting Only review frames at known offsets.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
import traceback

import unreal


REPO_ROOT = Path(__file__).resolve().parents[2]
PHYSICS_SRC = REPO_ROOT / "physics_reference" / "src"
if str(PHYSICS_SRC) not in sys.path:
    sys.path.insert(0, str(PHYSICS_SRC))

from cycling_physics.model import (  # noqa: E402
    Environment,
    RiderInput,
    RiderParameters,
    SimulationState,
    step_simulation,
)


PROOF_ENV = "YACS_SP638_RIDE_THROUGH_PROOF"
FRAME_ROOT_ENV = "YACS_SP638_RIDE_THROUGH_FRAME_ROOT"
CSV_ENV = "YACS_SP638_RIDE_THROUGH_CSV"
SESSION_MANAGED_ENV = "YACS_R4_1_EDITOR_SESSION_MANAGED"

POWER_W = 100.0
CADENCE_RPM = 90.0
INITIAL_SPEED_MPS = 2.5
FIXED_STEP_S = 0.05
START_BEFORE_HAIRPIN_M = 100.0
END_AFTER_HAIRPIN_M = 20.0
LOOK_AHEAD_M = 15.0
EYE_HEIGHT_CM = 160.0
FOV_DEG = 76.0
LIVE_RIDE_TIMEOUT_S = 120.0
CAPTURE_TIMEOUT_S = 30.0
MIN_CAPTURE_BYTES = 50_000
CAPTURE_RES_X = 1920
CAPTURE_RES_Y = 1080
CAPTURE_OFFSETS_M = (-100.0, -75.0, -50.0, -25.0, 0.0, 20.0, 40.0)

_tick_handle = None
_task = None
_phase = "ride"
_started_at = 0.0
_capture_started_at = 0.0
_capture_index = 0
_spline = None
_world = None
_level_editor = None
_viewport_key = None
_focus_cm = 0.0
_ride_start_cm = 0.0
_ride_end_cm = 0.0
_accumulator_s = 0.0
_state = SimulationState(
    speed_mps=INITIAL_SPEED_MPS,
    distance_m=0.0,
    elapsed_time_s=0.0,
)
_frame_ms: list[float] = []
_capture_records: list[dict[str, object]] = []
_proof_path: Path | None = None
_frame_root: Path | None = None
_csv_path: Path | None = None


def _release_python_script() -> None:
    if os.environ.get(SESSION_MANAGED_ENV, "").strip() != "1":
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def _dot(a: unreal.Vector, b: unreal.Vector) -> float:
    return float(a.x * b.x + a.y * b.y + a.z * b.z)


def _choose_hairpin_distance(spline: unreal.SplineComponent) -> float:
    length = float(spline.get_spline_length())
    if length < 25000.0:
        raise RuntimeError(f"SP638 ride-through spline is too short: {length:.1f} cm")

    half_window_cm = 2500.0
    step_cm = 2500.0
    margin_cm = 5000.0
    best_distance = margin_cm
    best_score = -1.0
    distance = margin_cm
    while distance <= length - margin_cm:
        before = spline.get_direction_at_distance_along_spline(
            max(0.0, distance - half_window_cm),
            unreal.SplineCoordinateSpace.WORLD,
        )
        after = spline.get_direction_at_distance_along_spline(
            min(length, distance + half_window_cm),
            unreal.SplineCoordinateSpace.WORLD,
        )
        score = 1.0 - max(-1.0, min(1.0, _dot(before, after)))
        if score > best_score:
            best_score = score
            best_distance = distance
        distance += step_cm
    return best_distance


def _find_active_sp638_spline() -> unreal.SplineComponent:
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    candidates: list[unreal.SplineComponent] = []
    for actor in actor_subsystem.get_all_level_actors():
        for spline in actor.get_components_by_class(unreal.SplineComponent):
            if int(spline.get_number_of_spline_points()) >= 50:
                candidates.append(spline)
    if len(candidates) != 1:
        raise RuntimeError(
            "ride-through expected exactly one SP638 spline with >=50 points, "
            f"found {len(candidates)}"
        )
    return candidates[0]


def _require_transient_geometry() -> None:
    required = {
        "SP638_LocalCorridor_LeftShoulder",
        "SP638_LocalCorridor_RightShoulder",
        "SP638_LocalCorridor_Asphalt",
    }
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    labels = {actor.get_actor_label() for actor in actor_subsystem.get_all_level_actors()}
    missing = sorted(required - labels)
    if missing:
        raise RuntimeError(
            "ride-through must run after the local-corridor visual proof; "
            f"missing transient actors: {missing}"
        )


def _grade_at(distance_cm: float) -> float:
    assert _spline is not None
    direction = _spline.get_direction_at_distance_along_spline(
        max(0.0, min(float(_spline.get_spline_length()), distance_cm)),
        unreal.SplineCoordinateSpace.WORLD,
    )
    horizontal = math.hypot(float(direction.x), float(direction.y))
    if horizontal <= 1e-9:
        return 0.0
    return float(direction.z) / horizontal


def _set_camera(distance_cm: float) -> None:
    assert _spline is not None
    assert _level_editor is not None
    assert _viewport_key is not None

    spline_length = float(_spline.get_spline_length())
    distance_cm = max(0.0, min(spline_length, distance_cm))
    target_cm = max(0.0, min(spline_length, distance_cm + LOOK_AHEAD_M * 100.0))

    location = _spline.get_location_at_distance_along_spline(
        distance_cm,
        unreal.SplineCoordinateSpace.WORLD,
    )
    target = _spline.get_location_at_distance_along_spline(
        target_cm,
        unreal.SplineCoordinateSpace.WORLD,
    )
    camera_location = unreal.Vector(
        float(location.x),
        float(location.y),
        float(location.z) + EYE_HEIGHT_CM,
    )
    camera_target = unreal.Vector(
        float(target.x),
        float(target.y),
        float(target.z) + 80.0,
    )
    rotation = unreal.MathLibrary.find_look_at_rotation(camera_location, camera_target)
    _level_editor.set_level_viewport_camera_info(
        camera_location,
        rotation,
        _viewport_key,
    )
    _level_editor.set_level_viewport_fov(FOV_DEG, _viewport_key)
    _level_editor.editor_invalidate_viewports()


def _capture_path(index: int) -> Path:
    assert _frame_root is not None
    offset = CAPTURE_OFFSETS_M[index]
    token = f"m{abs(int(offset)):03d}" if offset < 0 else f"p{int(offset):03d}"
    return _frame_root / f"ride_{index:02d}_{token}.png"


def _capture_ready(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size >= MIN_CAPTURE_BYTES
    except OSError:
        return False


def _schedule_capture(index: int) -> None:
    global _task, _capture_started_at, _phase
    assert _level_editor is not None

    offset_m = CAPTURE_OFFSETS_M[index]
    distance_cm = _focus_cm + offset_m * 100.0
    _set_camera(distance_cm)

    unreal.AutomationLibrary.set_editor_viewport_view_mode(
        unreal.ViewModeIndex.VMI_LIGHTING_ONLY
    )
    unreal.AutomationLibrary.set_editor_active_viewport_view_mode(
        unreal.ViewModeIndex.VMI_LIGHTING_ONLY
    )
    path = _capture_path(index)
    path.unlink(missing_ok=True)

    _task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=CAPTURE_RES_X,
        res_y=CAPTURE_RES_Y,
        filename=str(path),
        camera=None,
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes=(
            "SP638 B.4.6 human ride-through reference "
            f"offset={offset_m:+.0f}m power={POWER_W:.0f}W"
        ),
        delay=0.5,
        force_game_view=False,
    )
    if not _task or not _task.is_valid_task():
        raise RuntimeError(f"invalid screenshot task for ride frame {index}")

    _phase = "capture"
    _capture_started_at = time.monotonic()


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    index = int(math.floor(q * (len(ordered) - 1)))
    return ordered[index]


def _write_csv() -> None:
    assert _csv_path is not None
    _csv_path.parent.mkdir(parents=True, exist_ok=True)
    with _csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sample", "frame_ms"])
        for index, value in enumerate(_frame_ms):
            writer.writerow([index, f"{value:.6f}"])


def _finish(success: bool, error: str = "") -> None:
    global _tick_handle
    if _tick_handle is not None:
        unreal.unregister_slate_post_tick_callback(_tick_handle)
        _tick_handle = None

    if success:
        assert _proof_path is not None
        assert _csv_path is not None
        if not _frame_ms:
            raise RuntimeError("ride-through produced no frame-time samples")

        _write_csv()
        frame_budget_ms = 1000.0 / 60.0
        over_budget = sum(1 for value in _frame_ms if value > frame_budget_ms)
        average_ms = statistics.fmean(_frame_ms)
        payload = {
            "schema_version": 1,
            "sp638_local_corridor_ride_through": "PASS",
            "presentation_only": True,
            "authoritative_sp638_physics": False,
            "pace_source": "python_reference_physics_plus_local_visual_spline_grade",
            "power_w": POWER_W,
            "cadence_rpm": CADENCE_RPM,
            "initial_speed_mps": INITIAL_SPEED_MPS,
            "start_before_hairpin_m": START_BEFORE_HAIRPIN_M,
            "end_after_hairpin_m": END_AFTER_HAIRPIN_M,
            "hairpin_distance_m": _focus_cm / 100.0,
            "ride_start_distance_m": _ride_start_cm / 100.0,
            "ride_end_distance_m": _ride_end_cm / 100.0,
            "simulated_elapsed_s": _state.elapsed_time_s,
            "simulated_distance_m": _state.distance_m,
            "final_speed_mps": _state.speed_mps,
            "viewport": {
                "window_launch_resolution": [1920, 1080],
                "review_frame_resolution": [CAPTURE_RES_X, CAPTURE_RES_Y],
                "viewmode": "lightingonly",
                "fov_deg": FOV_DEG,
            },
            "frame_time": {
                "sample_count": len(_frame_ms),
                "average_ms": average_ms,
                "p50_ms": _percentile(_frame_ms, 0.50),
                "p95_ms": _percentile(_frame_ms, 0.95),
                "p99_ms": _percentile(_frame_ms, 0.99),
                "max_ms": max(_frame_ms),
                "average_fps": 1000.0 / average_ms if average_ms > 0.0 else None,
                "target_60fps_budget_ms": frame_budget_ms,
                "over_budget_count": over_budget,
                "over_budget_ratio": over_budget / len(_frame_ms),
                "note": (
                    "Editor viewport diagnostic, not the canonical Stage 3G "
                    "game performance gate; screenshot capture frames are excluded."
                ),
            },
            "frame_csv": str(_csv_path),
            "review_frames": _capture_records,
            "error": "",
        }
        _proof_path.parent.mkdir(parents=True, exist_ok=True)
        _proof_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        unreal.log(
            "[YacsSp638RideThrough] PASS: "
            f"samples={len(_frame_ms)} p95={payload['frame_time']['p95_ms']:.3f}ms "
            f"frames={len(_capture_records)}"
        )
    elif error:
        unreal.log_error(f"[YacsSp638RideThrough] FAILURE: {error}")

    _release_python_script()


def _tick(delta_time: float) -> None:
    global _accumulator_s, _state, _capture_index, _phase

    try:
        if _phase == "ride":
            dt = float(delta_time)
            if math.isfinite(dt) and dt > 0.0:
                _frame_ms.append(dt * 1000.0)
                _accumulator_s += min(dt, 0.25)

            while _accumulator_s >= FIXED_STEP_S:
                absolute_cm = _ride_start_cm + _state.distance_m * 100.0
                grade = _grade_at(absolute_cm)
                environment = Environment(
                    grade_decimal=grade,
                    wind_speed_mps=0.0,
                    air_density_kg_m3=1.225,
                    surface_wetness=0.0,
                    rolling_resistance_multiplier=1.0,
                    grip_multiplier=1.0,
                )
                rider = RiderParameters(
                    rider_mass_kg=75.0,
                    bike_mass_kg=8.5,
                    cda_m2=0.32,
                    rolling_resistance_coefficient=0.004,
                    drivetrain_efficiency=0.97,
                )
                rider_input = RiderInput(
                    power_w=POWER_W,
                    cadence_rpm=CADENCE_RPM,
                )
                _state = step_simulation(
                    rider,
                    environment,
                    rider_input,
                    _state,
                    FIXED_STEP_S,
                )
                _accumulator_s -= FIXED_STEP_S

            absolute_cm = _ride_start_cm + _state.distance_m * 100.0
            _set_camera(min(absolute_cm, _ride_end_cm))

            if absolute_cm >= _ride_end_cm:
                _capture_index = 0
                _schedule_capture(_capture_index)
                return

            if time.monotonic() - _started_at > LIVE_RIDE_TIMEOUT_S:
                if absolute_cm < _focus_cm:
                    raise TimeoutError(
                        "100 W ride did not reach the hairpin within "
                        f"{LIVE_RIDE_TIMEOUT_S:.0f}s; reached "
                        f"{(absolute_cm - _focus_cm) / 100.0:+.1f} m relative to hairpin"
                    )
                _capture_index = 0
                _schedule_capture(_capture_index)
                return
            return

        if _phase == "capture":
            assert _task is not None
            path = _capture_path(_capture_index)
            elapsed = time.monotonic() - _capture_started_at
            if not _task.is_task_done():
                if elapsed > CAPTURE_TIMEOUT_S:
                    raise TimeoutError(
                        f"ride frame {_capture_index} screenshot task timed out"
                    )
                return
            if not _capture_ready(path):
                if elapsed > CAPTURE_TIMEOUT_S:
                    raise TimeoutError(
                        f"ride frame {_capture_index} PNG did not flush"
                    )
                return

            offset_m = CAPTURE_OFFSETS_M[_capture_index]
            _capture_records.append(
                {
                    "offset_from_hairpin_m": offset_m,
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
            _capture_index += 1
            if _capture_index >= len(CAPTURE_OFFSETS_M):
                _phase = "done"
                _finish(True)
                return
            _schedule_capture(_capture_index)
            return

    except BaseException as exc:
        _phase = "failed"
        _finish(False, str(exc))
        unreal.log_error(traceback.format_exc())


def main() -> None:
    global _tick_handle, _started_at, _spline, _world, _level_editor
    global _viewport_key, _focus_cm, _ride_start_cm, _ride_end_cm
    global _proof_path, _frame_root, _csv_path

    proof_value = os.environ.get(PROOF_ENV, "").strip()
    frame_root_value = os.environ.get(FRAME_ROOT_ENV, "").strip()
    csv_value = os.environ.get(CSV_ENV, "").strip()
    if not proof_value or not frame_root_value or not csv_value:
        raise RuntimeError(
            f"{PROOF_ENV}, {FRAME_ROOT_ENV} and {CSV_ENV} are required"
        )

    _proof_path = Path(proof_value)
    _frame_root = Path(frame_root_value)
    _csv_path = Path(csv_value)
    _frame_root.mkdir(parents=True, exist_ok=True)
    _proof_path.unlink(missing_ok=True)
    _csv_path.unlink(missing_ok=True)

    editor_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    _world = editor_subsystem.get_editor_world()
    if _world is None:
        raise RuntimeError("editor world is unavailable for ride-through")

    _require_transient_geometry()
    _spline = _find_active_sp638_spline()
    _focus_cm = _choose_hairpin_distance(_spline)
    spline_length = float(_spline.get_spline_length())
    _ride_start_cm = max(0.0, _focus_cm - START_BEFORE_HAIRPIN_M * 100.0)
    _ride_end_cm = min(
        spline_length,
        _focus_cm + END_AFTER_HAIRPIN_M * 100.0,
    )
    if _ride_start_cm >= _focus_cm or _ride_end_cm <= _focus_cm:
        raise RuntimeError("ride-through cannot bracket the selected hairpin")

    _level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    _viewport_key = _level_editor.get_active_viewport_config_key()
    if str(_viewport_key) in {"", "None"}:
        keys = list(_level_editor.get_viewport_config_keys())
        if not keys:
            raise RuntimeError("no Level Editor viewport is available")
        _viewport_key = keys[0]

    _level_editor.editor_set_game_view(True, _viewport_key)
    unreal.AutomationLibrary.set_editor_viewport_view_mode(
        unreal.ViewModeIndex.VMI_LIGHTING_ONLY
    )
    unreal.AutomationLibrary.set_editor_active_viewport_view_mode(
        unreal.ViewModeIndex.VMI_LIGHTING_ONLY
    )
    _set_camera(_ride_start_cm)

    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    _started_at = time.monotonic()
    _tick_handle = unreal.register_slate_post_tick_callback(_tick)
    unreal.log(
        "[YacsSp638RideThrough] START: "
        f"hairpin={_focus_cm / 100.0:.1f}m "
        f"start={_ride_start_cm / 100.0:.1f}m "
        f"end={_ride_end_cm / 100.0:.1f}m "
        f"power={POWER_W:.0f}W initial_speed={INITIAL_SPEED_MPS:.1f}m/s"
    )


try:
    main()
except Exception as exc:
    unreal.log_error(f"[YacsSp638RideThrough] FAILURE: {exc}")
    unreal.log_error(traceback.format_exc())
    _release_python_script()
    raise
