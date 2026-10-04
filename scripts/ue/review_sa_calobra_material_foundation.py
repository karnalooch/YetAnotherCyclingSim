"""Move only the live viewport for reproducible, reversible material review."""

import builtins
import hashlib
import json
import runpy
import time
from pathlib import Path

import unreal

REPO = Path(__file__).resolve().parents[2]


def review(index=4, restore=False):
    foundation = runpy.run_path(
        str(REPO / "scripts/ue/sa_calobra_material_foundation.py")
    )
    config = foundation["load_workspace"]()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world.get_path_name().split(".")[0] != config["map"]:
        raise RuntimeError("Wrong map; review will not load another map")
    if not unreal.SystemLibrary.get_engine_version().startswith("5.8.2-56702186"):
        raise RuntimeError("Unverified engine version")
    current = editor.get_level_viewport_camera_info()
    if current is None:
        raise RuntimeError("No active level viewport")
    if restore:
        previous = getattr(builtins, "_yacs_2b_review_camera", None)
        if previous is None or previous[0] != world.get_path_name():
            raise RuntimeError("No matching original review camera")
        editor.set_level_viewport_camera_info(*previous[1])
        del builtins._yacs_2b_review_camera
        return
    if type(index) is not int or not 0 <= index < 9:
        raise ValueError("Review index must be 0 through 8")
    landscapes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if len(landscapes) != 1:
        raise RuntimeError("Expected one frozen Landscape")
    map_file = REPO / "Content" / (config["map"].removeprefix("/Game/") + ".umap")
    before = foundation["scene_snapshot"](world, landscapes[0], map_file)
    target = before["traces"][index][0]
    location = [target[0] - 3000, target[1] - 4000, target[2] + 2000]
    hit = unreal.SystemLibrary.line_trace_single(
        world,
        unreal.Vector(location[0], location[1], 150000),
        unreal.Vector(location[0], location[1], 0),
        unreal.TraceTypeQuery.ECC_VISIBILITY,
        True,
        [],
        unreal.DrawDebugTrace.NONE,
        True,
    )
    heights = [
        float(point.z)
        for point in (() if hit is None else hit.to_tuple())
        if all(hasattr(point, axis) for axis in ("x", "y", "z"))
        and abs(point.x - location[0]) < 0.1
        and abs(point.y - location[1]) < 0.1
        and 0 < point.z < 150000
    ]
    if not heights:
        raise RuntimeError("Camera ground trace missed")
    location[2] = max(location[2], max(heights) + 2000)
    rotation = unreal.MathLibrary.find_look_at_rotation(
        unreal.Vector(*location), unreal.Vector(*target)
    )
    if not hasattr(builtins, "_yacs_2b_review_camera"):
        builtins._yacs_2b_review_camera = (world.get_path_name(), current)
    editor.set_level_viewport_camera_info(unreal.Vector(*location), rotation)
    unreal.AutomationLibrary.finish_loading_before_screenshot()
    if foundation["scene_snapshot"](world, landscapes[0], map_file) != before:
        raise RuntimeError("Frozen scene changed during camera review")
    actual = editor.get_level_viewport_camera_info()
    if actual is None or any(
        abs(getattr(actual[0], axis) - wanted) > 0.1
        for axis, wanted in zip(("x", "y", "z"), location, strict=True)
    ):
        raise RuntimeError("Viewport camera did not update")
    report = {
        "index": index,
        "target_cm": target,
        "location_cm": location,
        "rotation_deg": {
            axis: float(getattr(rotation, axis)) for axis in ("pitch", "yaw", "roll")
        },
        "geometry_unchanged": True,
        "material": landscapes[0]
        .get_editor_property("landscape_material")
        .get_path_name(),
        "map_saved": False,
        "visual_acceptance": "PENDING_OWNER_REVIEW",
        "scope": "One of nine distributed ground views; additional road/rider review required",
    }
    (Path(config["work"]) / f"2b-material-review-{index}.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf8"
    )
    return report


def capture_ground_views(output):
    """Capture the distributed views serially using native editor tasks."""
    output = Path(output)
    if output.exists():
        raise RuntimeError("Existing review evidence must not be overwritten")
    if getattr(builtins, "_yacs_2b_capture", None):
        raise RuntimeError("A material capture is already active")
    output.mkdir(parents=True)
    engine_log = REPO / "Saved/Logs/YetAnotherCyclingSim.log"
    log_offset = engine_log.stat().st_size if engine_log.is_file() else None
    state = {"index": 0, "task": None, "busy": False, "handle": None, "captures": []}
    builtins._yacs_2b_capture = state

    def finish(error=None):
        if state["handle"] is not None:
            unreal.unregister_slate_post_tick_callback(state["handle"])
        diagnostics = None
        if log_offset is not None and engine_log.is_file():
            with engine_log.open("rb") as stream:
                stream.seek(log_offset)
                lines = stream.read().decode("utf8", errors="replace").splitlines()
            diagnostics = [
                line for line in lines if "Error:" in line or "EnsureFailed:" in line
            ]
        report = {
            "status": "FAILED"
            if error
            else "CAPTURED_WITH_ENGINE_ERRORS"
            if diagnostics
            else "CAPTURED_DIAGNOSTICS_UNAVAILABLE"
            if diagnostics is None
            else "GROUND_VIEWS_CAPTURED",
            "error": str(error) if error else None,
            "engine_errors": diagnostics,
            "captures": state["captures"],
            "map_saved": False,
            "geometry_modified": False,
            "visual_acceptance": "PENDING_OWNER_REVIEW",
            "performance": "NOT_MEASURED",
            "capture_script_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
            "scope": "Nine distributed ground views; overview and road/rider review remain separate",
        }
        (output / "capture-report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf8"
        )
        del builtins._yacs_2b_capture
        if error:
            unreal.log_error("YACS 2B capture failed: " + str(error))
        else:
            unreal.log(
                "YACS 2B ground captures complete; visual acceptance pending; inspect engine_errors"
            )

    def tick(_delta):
        if state["busy"]:
            return
        state["busy"] = True
        try:
            if state["task"] is not None:
                if time.monotonic() - state["started"] > 90:
                    raise RuntimeError(
                        "Native screenshot task timed out after 90 seconds"
                    )
                if not state["task"].is_task_done():
                    return
                path = output / f"ground-{state['index']}.png"
                if not path.is_file() or path.stat().st_size < 100000:
                    raise RuntimeError("Screenshot task completed without a usable PNG")
                state["captures"].append(
                    {
                        "view": state["view"],
                        "path": path.name,
                        "size_bytes": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )
                state["index"] += 1
                state["task"] = None
            if state["index"] == 9:
                finish()
                return
            state["view"] = review(state["index"])
            state["started"] = time.monotonic()
            state["task"] = unreal.AutomationLibrary.take_high_res_screenshot(
                res_x=1920,
                res_y=1080,
                filename=str(output / f"ground-{state['index']}.png"),
                delay=3.0,
                force_game_view=True,
            )
            if not state["task"] or not state["task"].is_valid_task():
                raise RuntimeError("Native screenshot task is invalid")
        except Exception as exc:
            finish(exc)
        finally:
            state["busy"] = False

    state["handle"] = unreal.register_slate_post_tick_callback(tick)
