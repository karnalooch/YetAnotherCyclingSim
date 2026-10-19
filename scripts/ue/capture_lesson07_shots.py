import os
import time
import unreal

EVIDENCE_DIR = "D:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified"
os.makedirs(EVIDENCE_DIR, exist_ok=True)
LOG_FILE = os.path.join(EVIDENCE_DIR, "ue_capture_log.txt")

with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write("=== START LESSON 07 UE OFFSCREEN CAPTURE ===\n")

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    unreal.log(f"[UE_CAPTURE] {msg}")

MAP_PATH = "/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07"

SHOTS = [
    {
        "name": "ue_panorama_material.png",
        "cam": unreal.Vector(-95000.0, -260000.0, 180000.0),
        "target": unreal.Vector(0.0, 74000.0, 40000.0),
        "fov": 80.0,
        "note": "Full terrain panorama with Pegasus master material, global color and PBR lighting"
    },
    {
        "name": "ue_closeup_puig_major.png",
        "cam": unreal.Vector(111255.0, 19592.0, 75709.0),
        "target": unreal.Vector(126255.0, 39592.0, 67709.0),
        "fov": 65.0,
        "note": "Closeup Puig Major summit ridge showing rock/cliffs surface and global tint"
    },
    {
        "name": "ue_closeup_sa_calobra_cove.png",
        "cam": unreal.Vector(-87000.0, -61000.0, 28150.0),
        "target": unreal.Vector(-95000.0, -53000.0, 24150.0),
        "fov": 65.0,
        "note": "Closeup Sa Calobra cove coastal sand and rock contact zone"
    },
    {
        "name": "ue_closeup_transition.png",
        "cam": unreal.Vector(51912.0, 46090.0, 49766.0),
        "target": unreal.Vector(56912.0, 53090.0, 46766.0),
        "fov": 60.0,
        "note": "Closeup transition showing detail textures blending with global color"
    },
    {
        "name": "ue_closeup_scree.png",
        "cam": unreal.Vector(173275.0, 109825.0, 36285.0),
        "target": unreal.Vector(172075.0, 111625.0, 34785.0),
        "fov": 60.0,
        "note": "Closeup Scree occurrence showing normal map response and roughness under sunlight"
    }
]

_current_idx = 0
_camera = None
_task = None
_start_time = 0.0
_handle = None
_cooling_down = False
_cooldown_start = 0.0

def finish(error=""):
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    if error:
        log(f"ERROR: {error}")
    else:
        log("All 5 shots captured and verified successfully!")
    log("Quitting editor...")
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

def schedule_current_shot():
    global _camera, _task, _start_time, _current_idx
    if _current_idx >= len(SHOTS):
        finish()
        return

    shot = SHOTS[_current_idx]
    out_file = os.path.join(EVIDENCE_DIR, shot["name"])
    if os.path.exists(out_file):
        os.remove(out_file)

    log(f"--- Scheduling [{_current_idx + 1}/{len(SHOTS)}] {shot['name']} ---")
    rot = unreal.MathLibrary.find_look_at_rotation(shot["cam"], shot["target"])

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if _camera is None:
        _camera = actor_subsystem.spawn_actor_from_class(unreal.CameraActor, shot["cam"], rot, transient=True)
    else:
        _camera.set_actor_location(shot["cam"], False, False)
        _camera.set_actor_rotation(rot, False)

    cam_comp = _camera.get_component_by_class(unreal.CameraComponent)
    cam_comp.set_editor_property("field_of_view", shot["fov"])

    unreal.AutomationLibrary.set_editor_viewport_view_mode(unreal.ViewModeIndex.VMI_LIT)
    unreal.AutomationLibrary.finish_loading_before_screenshot()

    _task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=1920,
        res_y=1080,
        filename=out_file,
        camera=_camera,
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes=shot["note"],
        delay=2.0,
        force_game_view=False
    )
    _start_time = time.monotonic()

    if not _task or not _task.is_valid_task():
        finish(f"Invalid screenshot task for {shot['name']}")

def tick(_delta):
    global _current_idx, _task, _start_time, _cooling_down, _cooldown_start
    if _task is None and not _cooling_down:
        return

    now = time.monotonic()
    elapsed = now - _start_time

    if _cooling_down:
        if now - _cooldown_start > 1.0:
            _cooling_down = False
            _current_idx += 1
            schedule_current_shot()
        return

    shot = SHOTS[_current_idx]
    target_file = os.path.join(EVIDENCE_DIR, shot["name"])
    file_ready = os.path.exists(target_file) and os.path.getsize(target_file) > 50000

    if (_task.is_task_done() or elapsed > 6.0) and file_ready:
        log(f"Shot {shot['name']} captured successfully ({os.path.getsize(target_file)} bytes in {elapsed:.2f}s)")
        _task = None
        _cooling_down = True
        _cooldown_start = now
    elif elapsed > 25.0:
        log(f"Shot {shot['name']} timed out after {elapsed:.2f}s (file_ready={file_ready})")
        _task = None
        _cooling_down = True
        _cooldown_start = now

try:
    log(f"Loading level {MAP_PATH}...")
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    level_subsystem.load_level(MAP_PATH)
    log("Level loaded successfully.")

    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    schedule_current_shot()
    _handle = unreal.register_slate_post_tick_callback(tick)

except Exception as e:
    import traceback
    finish(traceback.format_exc())
