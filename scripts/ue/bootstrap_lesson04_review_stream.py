"""Bootstrap and camera controller for Lesson 04 Unreal Review Level Editor Stream.

Runs inside Unreal Editor 5.8 during the PixelStreaming2 review session.
Sets initial camera to FULL_WORKING and provides slate tick file-based camera control.
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

import unreal

MANIFEST_PATH = Path(r"D:\yacs\project\Saved\RuntimeProof\lesson04_camera_manifest.json")
COMMAND_PATH = Path(r"D:\yacs\project\Saved\RuntimeProof\lesson04_camera_command.json")
STATE_PATH = Path(r"D:\yacs\project\Saved\RuntimeProof\lesson04_camera_state.json")
READY_PATH = Path(r"D:\yacs\project\Saved\RuntimeProof\lesson04_stream_ready.json")

CAMERAS = {
    "FULL_WORKING": {
        "location": [-598300.0, -277680.0, 470600.0],
        "target": [1700.0, 68730.0, 35000.0],
        "desc": "Full working corridor Ma-2141 bounds overview",
    },
    "FULL_CONTEXT": {
        "location": [-1177330.0, -679730.0, 705670.0],
        "target": [0.0, 0.0, 30000.0],
        "desc": "Full 8x8 km context terrain overview",
    },
    "CLIFF_CLOSEUP": {
        "location": [14900.0, -78600.0, 40220.0],
        "target": [22400.0, -71100.0, 35720.0],
        "desc": "Limestone cliff crags closeup",
    },
    "CLIFF_TRANSITION": {
        "location": [3500.0, -56500.0, 46000.0],
        "target": [8000.0, -52000.0, 43000.0],
        "desc": "Cliff to grass smooth transition boundary",
    },
    "SAND_COASTAL": {
        "location": [-6275.0, -144975.0, 400.0],
        "target": [-4775.0, -143175.0, 65.0],
        "desc": "Coastal beach sand cove at sea level",
    },
    "GRASS_GROUND": {
        "location": [-5500.0, -55500.0, 45000.0],
        "target": [0.0, -50000.0, 41500.0],
        "desc": "Grass and ground with simplex noise distortion and tint",
    },
    "ROAD_CORRIDOR": {
        "location": [-40450.0, 46550.0, 41240.0],
        "target": [-32450.0, 54550.0, 36240.0],
        "desc": "Ma-2141 road corridor canyon landscape",
    },
}

_LAST_COMMAND_ID = None
_LAST_CHECK_TIME = 0.0
_SLATE_TICK_HANDLE = None


def apply_camera(camera_name: str) -> dict:
    if camera_name not in CAMERAS:
        raise ValueError(f"Unknown camera preset: {camera_name}")

    preset = CAMERAS[camera_name]
    loc = unreal.Vector(*preset["location"])
    target = unreal.Vector(*preset["target"])
    rot = unreal.MathLibrary.find_look_at_rotation(loc, target)

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    editor.set_level_viewport_camera_info(loc, rot)

    read_loc, read_rot = editor.get_level_viewport_camera_info()
    state = {
        "status": "CAMERA_APPLIED",
        "camera": camera_name,
        "description": preset["desc"],
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "applied_location": [read_loc.x, read_loc.y, read_loc.z],
        "applied_rotation": [read_rot.pitch, read_rot.yaw, read_rot.roll],
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_PATH.with_suffix(".json.tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    temp.replace(STATE_PATH)
    unreal.log(f"LESSON04_CAMERA: Switched to {camera_name}")
    return state


def on_slate_post_tick(delta_seconds: float):
    global _LAST_COMMAND_ID, _LAST_CHECK_TIME
    now = time.time()
    if now - _LAST_CHECK_TIME < 0.25:
        return
    _LAST_CHECK_TIME = now

    if not COMMAND_PATH.exists():
        return

    try:
        data = json.loads(COMMAND_PATH.read_text(encoding="utf-8"))
        cmd_id = data.get("command_id")
        camera_name = data.get("camera")
        if cmd_id and cmd_id != _LAST_COMMAND_ID and camera_name:
            _LAST_COMMAND_ID = cmd_id
            apply_camera(camera_name)
    except Exception as e:
        unreal.log_error(f"LESSON04_CAMERA_ERROR: {e}")


def main():
    global _SLATE_TICK_HANDLE
    unreal.log("LESSON04_STREAM_BOOTSTRAP: Initializing...")

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    unreal.log(f"LESSON04_STREAM_BOOTSTRAP: Editor world loaded: {world.get_path_name() if world else 'None'}")

    # Set initial camera to FULL_WORKING
    apply_camera("FULL_WORKING")

    # Register tick callback for camera switching
    _SLATE_TICK_HANDLE = unreal.register_slate_post_tick_callback(on_slate_post_tick)

    # Signal ready
    ready_data = {
        "status": "STREAM_BOOTSTRAP_READY",
        "initial_camera": "FULL_WORKING",
        "editor_pid": os.getpid(),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    READY_PATH.parent.mkdir(parents=True, exist_ok=True)
    READY_PATH.write_text(json.dumps(ready_data, indent=2), encoding="utf-8")

    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    unreal.log("LESSON04_STREAM_BOOTSTRAP: Ready and listening for camera commands.")


if __name__ == "__main__":
    main()
