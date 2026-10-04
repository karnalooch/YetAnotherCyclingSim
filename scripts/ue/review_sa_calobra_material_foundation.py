"""Move only the live viewport for reproducible, reversible material review."""

import builtins
import json
import runpy
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
        "map_saved": False,
        "visual_acceptance": "PENDING_OWNER_REVIEW",
        "scope": "One of nine distributed ground views; additional road/rider review required",
    }
    (Path(config["work"]) / f"2b-material-review-{index}.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf8"
    )
    return report
