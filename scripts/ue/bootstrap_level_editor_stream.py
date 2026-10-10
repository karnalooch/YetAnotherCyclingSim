"""Identify the owner-requested viewport session and set its initial road view.

Runs only inside the prepared disposable project. It changes the viewport camera,
does not author or save any asset, and never claims a received browser frame.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import traceback

import unreal


RUNTIME_SHA = "1ef46dacedba5ed1fc909422529be41808d3dbe4"
MAP_PACKAGE = "/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview"
MAP_SHA256 = "35d485005f123e5648f675d6f91209630c163bddf92d55f6c5b640d55917732d"
# Existing survey window-0112-forward-00001; no new scene/camera asset is created.
CAMERA = (56912.43746055451, 53090.5078449409, 46766.459277036185)
TARGET = (58088.73631673153, 52542.60698992016, 46508.19271952782)
SURVEY_SHA256 = "15e0a2350c613bf52bfb1354192043ca0c6cd785493c59e7721305b67de099a3"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    destination = Path(os.environ["YACS_LEVEL_EDITOR_REVIEW_ROOT"])
    require(
        destination.parent == Path(r"D:\yacs\work\level-editor-review")
        and re.fullmatch(RUNTIME_SHA[:12] + r"-[A-Za-z0-9][A-Za-z0-9_-]{0,47}", destination.name),
        "Viewport bootstrap destination differs from the fixed review root",
    )
    require(destination.resolve() == destination, "Review project path is redirected")
    actual_project = Path(unreal.Paths.project_dir()).resolve()
    require(actual_project == destination, "Unreal opened a different project")
    output = destination / "Saved/LevelEditorStream/scene.json"
    require(not output.exists(), "Viewport scene receipt already exists")
    receipt = {
        "schema_version": 1,
        "status": "BLOCKED",
        "runtime_source_sha": RUNTIME_SHA,
        "launcher_sha": os.environ["YACS_LEVEL_EDITOR_LAUNCHER_SHA"],
        "editor_pid": os.getpid(),
        "project_root": str(actual_project),
        "map_package": MAP_PACKAGE,
        "received_browser_frame": False,
        "owner_visual_status": "PENDING_FINAL_M3",
        "performance_status": "DEFERRED_AFTER_M3",
        "performance_pass": False,
        "map_or_assets_saved": False,
    }
    try:
        prep_raw = (destination / "level-editor-review-preparation.json").read_bytes()
        require(
            hashlib.sha256(prep_raw).hexdigest()
            == os.environ["YACS_LEVEL_EDITOR_PREPARATION_SHA256"],
            "Prepared snapshot receipt changed before the Editor opened it",
        )
        preparation = json.loads(prep_raw)
        require(
            preparation["status"] == "READY_FOR_EDITOR_LAUNCH"
            and preparation["runtime_source_sha"] == RUNTIME_SHA
            and preparation["launcher_sha"] == receipt["launcher_sha"],
            "Snapshot is not the expected verified runtime/launcher pair",
        )
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        require(world is not None, "No editor world is loaded")
        actual_map = world.get_path_name().split(".", 1)[0]
        require(actual_map == MAP_PACKAGE, "The loaded map is not the retained road consumer")
        map_path = destination / ("Content/" + MAP_PACKAGE.removeprefix("/Game/") + ".umap")
        require(hashlib.sha256(map_path.read_bytes()).hexdigest() == MAP_SHA256,
                "Saved review map bytes differ from the verified checkpoint")
        source = unreal.SystemLibrary.get_console_variable_string_value("PixelStreaming2.Editor.Source")
        autostart = unreal.SystemLibrary.get_console_variable_int_value("PixelStreaming2.Editor.StartOnLaunch")
        remote = unreal.SystemLibrary.get_console_variable_int_value("PixelStreaming2.Editor.UseRemoteSignallingServer")
        require(source == "LevelEditorViewport", "Stream source is not LevelEditorViewport")
        require(autostart == 1 and remote == 0, "Local automatic viewport streaming is not configured")
        location = unreal.Vector(*CAMERA)
        rotation = unreal.MathLibrary.find_look_at_rotation(location, unreal.Vector(*TARGET))
        editor.set_level_viewport_camera_info(location, rotation)
        actual_location, actual_rotation = editor.get_level_viewport_camera_info()
        require(
            all(abs(getattr(actual_location, field) - value) < 1.0
                for field, value in zip(("x", "y", "z"), CAMERA)),
            "Initial road viewport camera did not read back",
        )
        receipt.update({
            "status": "VIEWPORT_SCENE_READY",
            "engine_version": unreal.SystemLibrary.get_engine_version(),
            "stream_source": source,
            "start_on_launch": bool(autostart),
            "remote_signalling_server": bool(remote),
            "map_sha256": MAP_SHA256,
            "initial_camera_source": "window-0112-forward-00001",
            "initial_camera_source_sha256": SURVEY_SHA256,
            "initial_camera_location_cm": [actual_location.x, actual_location.y, actual_location.z],
            "initial_camera_rotation_deg": [actual_rotation.pitch, actual_rotation.yaw, actual_rotation.roll],
        })
        # -ExecutePythonScript otherwise exits after its script has completed.
        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    except Exception:
        receipt["error"] = traceback.format_exc()
        raise
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".json.tmp")
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.rename(output)
        unreal.log("YACS_LEVEL_EDITOR_SCENE " + json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
