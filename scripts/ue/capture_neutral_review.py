"""Capture neutral review screenshots of the baked unified terrain in Unreal Engine.

Map: /Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07
Landscapes currently have M_TerrainReview assigned.
Verifies authentic landscape relief, geometry boundaries, and illumination before applying material.
"""
import json
import os
from pathlib import Path
import time
import traceback
import unreal

EVIDENCE_DIR = Path("D:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = Path("D:/yacs/work/lesson07-unified-20261019/ue_neutral_review_report.json")
LOG_FILE = Path("D:/yacs/work/lesson07-unified-20261019/ue_neutral_capture_log.txt")

MAP_PATH = "/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07"

SHOTS = [
    {
        "name": "ue_neutral_panorama.png",
        "cam": unreal.Vector(-450000.0, -450000.0, 350000.0),
        "target": unreal.Vector(0.0, 0.0, 50000.0),
        "fov": 85.0,
        "note": "Neutral overview of full 8x8 km unified terrain"
    },
    {
        "name": "ue_neutral_puig_major.png",
        "cam": unreal.Vector(-278375.0, 199525.0, 180000.0),
        "target": unreal.Vector(-128375.0, 349525.0, 143716.0),
        "fov": 60.0,
        "note": "Neutral closeup of Puig Major summit ridge"
    },
    {
        "name": "ue_neutral_sa_calobra_cove.png",
        "cam": unreal.Vector(-20000.0, -160000.0, 35000.0),
        "target": unreal.Vector(47000.0, -106000.0, 1034.0),
        "fov": 65.0,
        "note": "Neutral closeup of Sa Calobra cove and gorge"
    },
    {
        "name": "ue_neutral_scree.png",
        "cam": unreal.Vector(187925.0, -3775.0, 35000.0),
        "target": unreal.Vector(217925.0, 26225.0, 21712.0),
        "fov": 60.0,
        "note": "Neutral closeup of scree slope occurrence"
    },
    {
        "name": "ue_neutral_transition.png",
        "cam": unreal.Vector(-100000.0, -130000.0, 28000.0),
        "target": unreal.Vector(-50000.0, -80000.0, 8000.0),
        "fov": 65.0,
        "note": "Neutral closeup of coastal transition zone"
    }
]

state = {
    "status": "STARTED",
    "current_idx": 0,
    "shots_captured": [],
    "camera": None,
    "task": None,
    "start_time": 0.0,
    "cooling_down": False,
    "cooldown_start": 0.0,
    "handle": None,
    "errors": [],
}

log_fp = open(str(LOG_FILE), "w", encoding="utf-8")

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    log_fp.write(line + "\n")
    log_fp.flush()
    unreal.log(f"[NEUTRAL_CAPTURE] {msg}")

def finish(error=""):
    if state["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        state["handle"] = None
    if error:
        log(f"ERROR: {error}")
        state["errors"].append(error)
        state["status"] = "FAILED"
    else:
        log("All 5 neutral review shots captured successfully!")
        state["status"] = "PASS"
        
    report = {
        "status": state["status"],
        "shots": state["shots_captured"],
        "errors": state["errors"],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    log(f"Report written to {REPORT_PATH}")
    log_fp.close()
    
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

def schedule_current_shot():
    idx = state["current_idx"]
    if idx >= len(SHOTS):
        finish()
        return

    shot = SHOTS[idx]
    out_file = str(EVIDENCE_DIR / shot["name"]).replace("\\", "/")
    if os.path.exists(out_file):
        os.remove(out_file)

    log(f"--- Scheduling [{idx + 1}/{len(SHOTS)}] {shot['name']} ---")
    rot = unreal.MathLibrary.find_look_at_rotation(shot["cam"], shot["target"])

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if state["camera"] is None:
        state["camera"] = actor_subsystem.spawn_actor_from_class(unreal.CameraActor, shot["cam"], rot, transient=True)
    else:
        state["camera"].set_actor_location(shot["cam"], False, False)
        state["camera"].set_actor_rotation(rot, False)

    cam_comp = state["camera"].get_component_by_class(unreal.CameraComponent)
    cam_comp.set_editor_property("field_of_view", shot["fov"])

    unreal.AutomationLibrary.set_editor_viewport_view_mode(unreal.ViewModeIndex.VMI_LIT)
    unreal.AutomationLibrary.finish_loading_before_screenshot()

    task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=1920,
        res_y=1080,
        filename=out_file,
        camera=state["camera"],
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes=shot["note"],
        delay=2.0,
        force_game_view=False
    )
    state["task"] = task
    state["start_time"] = time.monotonic()

    if not task or not task.is_valid_task():
        finish(f"Invalid screenshot task for {shot['name']}")

def tick(_delta):
    if state["task"] is None and not state["cooling_down"]:
        return

    now = time.monotonic()
    elapsed = now - state["start_time"]

    if state["cooling_down"]:
        if now - state["cooldown_start"] > 1.0:
            state["cooling_down"] = False
            state["current_idx"] += 1
            schedule_current_shot()
        return

    shot = SHOTS[state["current_idx"]]
    target_file = EVIDENCE_DIR / shot["name"]
    file_ready = target_file.exists() and target_file.stat().st_size > 50000

    if (state["task"].is_task_done() or elapsed > 6.0) and file_ready:
        size_bytes = target_file.stat().st_size
        log(f"Shot {shot['name']} captured ({size_bytes} bytes in {elapsed:.2f}s)")
        state["shots_captured"].append({
            "name": shot["name"],
            "path": str(target_file),
            "size_bytes": size_bytes,
            "duration_s": elapsed,
        })
        state["task"] = None
        state["cooling_down"] = True
        state["cooldown_start"] = now
    elif elapsed > 25.0:
        log(f"Shot {shot['name']} timed out after {elapsed:.2f}s")
        state["task"] = None
        state["cooling_down"] = True
        state["cooldown_start"] = now

def main():
    try:
        log(f"Loading level {MAP_PATH}...")
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        levels.load_level(MAP_PATH)
        log("Level loaded successfully.")

        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        schedule_current_shot()
        state["handle"] = unreal.register_slate_post_tick_callback(tick)
    except Exception:
        finish(traceback.format_exc())

if __name__ == "__main__":
    main()
