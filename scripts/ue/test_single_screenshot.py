import unreal
import os
import time

log_path = "D:/yacs/project/worldgen/houdini/sa_calobra/test_screenshot_py.log"
with open(log_path, "w") as f:
    f.write("=== START TEST_SINGLE_SCREENSHOT ===\n")

def log(msg):
    with open(log_path, "a") as f:
        f.write(str(msg) + "\n")
    unreal.log(str(msg))

_task = None
_handle = None
_start_time = 0.0
_camera = None

def finish():
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    log("Quitting editor...")
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

def tick(_delta):
    global _task, _start_time
    if _task is None:
        return
    
    elapsed = time.monotonic() - _start_time
    if _task.is_task_done():
        log(f"Screenshot task completed in {elapsed:.2f} seconds!")
        finish()
    elif elapsed > 30.0:
        log(f"Screenshot task timed out after {elapsed:.2f} seconds!")
        finish()

try:
    asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
    map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    level_subsystem.load_level(map_path)
    log("Level loaded.")

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    
    # Spawn camera for overview
    cam_loc = unreal.Vector(-95000.0, -250000.0, 180000.0)
    target_loc = unreal.Vector(0.0, 74000.0, 40000.0)
    cam_rot = unreal.MathLibrary.find_look_at_rotation(cam_loc, target_loc)
    
    _camera = actor_subsystem.spawn_actor_from_class(unreal.CameraActor, cam_loc, cam_rot, transient=True)
    _camera.get_component_by_class(unreal.CameraComponent).set_editor_property("field_of_view", 80.0)
    
    unreal.AutomationLibrary.set_editor_viewport_view_mode(unreal.ViewModeIndex.VMI_LIT)
    unreal.AutomationLibrary.finish_loading_before_screenshot()

    out_file = "D:/yacs/project/worldgen/houdini/sa_calobra/evidence/test_ue_shot.png"
    if os.path.exists(out_file):
        os.remove(out_file)

    log(f"Scheduling screenshot to {out_file}...")
    _task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=1920,
        res_y=1080,
        filename=out_file,
        camera=_camera,
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes="Test overview",
        delay=2.0,
        force_game_view=False
    )

    if not _task or not _task.is_valid_task():
        log("ERROR: Invalid screenshot task!")
        finish()
    else:
        log("Task valid, registering tick callback...")
        _start_time = time.monotonic()
        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        _handle = unreal.register_slate_post_tick_callback(tick)

except Exception as e:
    import traceback
    log(f"EXCEPTION: {traceback.format_exc()}")
    finish()
