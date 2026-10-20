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
MAT_NEUTRAL = "/Game/Worlds/SaCalobra_Houdini_20261016/Materials/M_TerrainReview"
MAT_MATERIAL = "/Game/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS"

SHOTS = [
    # 1. Full Domain Panorama (Material)
    {
        "name": "ue_panorama_material.png",
        "cam": unreal.Vector(-450000.0, -500000.0, 420000.0),
        "target": unreal.Vector(0.0, 0.0, 40000.0),
        "fov": 75.0,
        "material": MAT_MATERIAL,
        "note": "Full terrain panorama with Pegasus master material, global color and PBR lighting"
    },
    # 2. Full Domain Panorama (Neutral Clay)
    {
        "name": "ue_panorama_neutral.png",
        "cam": unreal.Vector(-450000.0, -500000.0, 420000.0),
        "target": unreal.Vector(0.0, 0.0, 40000.0),
        "fov": 75.0,
        "material": MAT_NEUTRAL,
        "note": "Full terrain panorama with neutral review material"
    },
    # 3. Authentic Scree Occurrence Closeup (Material)
    {
        "name": "ue_closeup_scree.png",
        "cam": unreal.Vector(-255000.0, 178000.0, 52000.0),
        "target": unreal.Vector(-250278.0, 184595.0, 46095.0),
        "fov": 50.0,
        "material": MAT_MATERIAL,
        "note": "Closeup Scree occurrence showing normal map response and roughness under sunlight"
    },
    # 4. Authentic Scree Occurrence Closeup (Neutral Clay) - Identical camera!
    {
        "name": "ue_closeup_scree_neutral.png",
        "cam": unreal.Vector(-255000.0, 178000.0, 52000.0),
        "target": unreal.Vector(-250278.0, 184595.0, 46095.0),
        "fov": 50.0,
        "material": MAT_NEUTRAL,
        "note": "Closeup Scree occurrence neutral shading from identical camera and lighting"
    },
    # 5. Puig Major Summit Ridge
    {
        "name": "ue_closeup_puig_major.png",
        "cam": unreal.Vector(-278375.0, 199525.0, 180000.0),
        "target": unreal.Vector(-128375.0, 349525.0, 143716.0),
        "fov": 50.0,
        "material": MAT_MATERIAL,
        "note": "Closeup Puig Major summit ridge showing rock/cliffs surface and global tint"
    },
    # 6. Sa Calobra Cove Beach and Bay
    {
        "name": "ue_closeup_sa_calobra_cove.png",
        "cam": unreal.Vector(47000.0, -180000.0, 16000.0),
        "target": unreal.Vector(47000.0, -106000.0, 1034.0),
        "fov": 45.0,
        "material": MAT_MATERIAL,
        "note": "Framed closeup Sa Calobra cove beach and sea bay"
    },
    # 7. Two-class boundary transition (Scree / Cliffs)
    {
        "name": "ue_closeup_transition.png",
        "cam": unreal.Vector(-248000.0, 180000.0, 50000.0),
        "target": unreal.Vector(-249500.0, 184000.0, 46000.0),
        "fov": 40.0,
        "material": MAT_MATERIAL,
        "note": "Closeup two-class boundary between scree and cliffs detail textures"
    },
    # 8. Tile Seam Inspection across X=0 border
    {
        "name": "ue_tile_seam_check.png",
        "cam": unreal.Vector(-5000.0, -5000.0, 55000.0),
        "target": unreal.Vector(0.0, 0.0, 47350.0),
        "fov": 40.0,
        "material": MAT_MATERIAL,
        "note": "Closeup inspection across tile seam at domain center verifying continuous UV mapping and lighting"
    }
]

_current_idx = 0
_camera = None
_task = None
_start_time = 0.0
_handle = None
_cooling_down = False
_cooldown_start = 0.0
_current_mat_path = None

def set_landscape_material(mat_path):
    global _current_mat_path
    if _current_mat_path == mat_path:
        return
    log(f"Setting landscape material to {mat_path}...")
    mat_asset = unreal.EditorAssetLibrary.load_asset(mat_path)
    if not mat_asset:
        raise RuntimeError(f"Failed to load material asset: {mat_path}")
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in actor_subsystem.get_all_level_actors():
        if isinstance(a, unreal.LandscapeProxy):
            a.set_editor_property("landscape_material", mat_asset)
    _current_mat_path = mat_path

def finish(error=""):
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    # Restore Pegasus material before exit
    try:
        set_landscape_material(MAT_MATERIAL)
        unreal.EditorLevelLibrary.save_current_level()
    except Exception as e:
        log(f"Warning restoring material: {e}")

    if error:
        log(f"ERROR: {error}")
    else:
        log("All shots captured and verified successfully!")
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
    set_landscape_material(shot["material"])

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
        if now - _cooldown_start > 1.5:
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
