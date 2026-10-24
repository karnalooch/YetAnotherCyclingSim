import unreal
import os
import time

log_file_path = "D:/yacs/project/worldgen/houdini/sa_calobra/evidence/shots_4_5_log.txt"
with open(log_file_path, "w") as f:
    f.write("=== CAPTURING SHOTS 04 AND 05 ===\n")

def log(msg):
    with open(log_file_path, "a") as f:
        f.write(str(msg) + "\n")
    unreal.log(str(msg))

asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"
evidence_dir = "D:/yacs/project/worldgen/houdini/sa_calobra/evidence"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
target = [l for l in landscapes if "Detail_0_0" in l.get_actor_label()][0]
log(f"Target Landscape: {target.get_actor_label()}")
layers = [l.get_name_bp() for l in target.get_edit_layers_bp()]
log(f"Current layers on {target.get_actor_label()}: {layers}")

# First shot to capture: 05_reverted_clean_baseline.png (since map is currently in reverted clean baseline state)
# Camera matches shot 02 (close-up of the sculpt area at (-95000, -53000))
shot5_file = f"{evidence_dir}/05_reverted_clean_baseline.png"
shot4_file = f"{evidence_dir}/04_unreal_procedural_update.png"

_camera = None
_step = 0
_task = None
_start_time = 0.0
_handle = None

def schedule_shot_05():
    global _camera, _task, _start_time, _step
    _step = 5
    log("\n--- Scheduling 05_reverted_clean_baseline.png ---")
    if os.path.exists(shot5_file):
        os.remove(shot5_file)

    cam_loc = unreal.Vector(-95000.0 + 8000.0, -53000.0 - 8000.0, 24150.0 + 4000.0)
    target_loc = unreal.Vector(-95000.0, -53000.0, 24150.0)
    rot = unreal.MathLibrary.find_look_at_rotation(cam_loc, target_loc)

    if _camera is None:
        _camera = actor_subsystem.spawn_actor_from_class(unreal.CameraActor, cam_loc, rot, transient=True)
    else:
        _camera.set_actor_location(cam_loc, False, False)
        _camera.set_actor_rotation(rot, False)

    _camera.get_component_by_class(unreal.CameraComponent).set_editor_property("field_of_view", 65.0)
    unreal.AutomationLibrary.set_editor_viewport_view_mode(unreal.ViewModeIndex.VMI_LIT)
    unreal.AutomationLibrary.finish_loading_before_screenshot()

    _task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=1920,
        res_y=1080,
        filename=shot5_file,
        camera=_camera,
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes="Reverted Clean Baseline",
        delay=2.0,
        force_game_view=False
    )
    _start_time = time.monotonic()

def schedule_shot_04():
    global _camera, _task, _start_time, _step
    _step = 4
    log("\n--- Scheduling 04_unreal_procedural_update.png ---")
    if os.path.exists(shot4_file):
        os.remove(shot4_file)

    # Medium view showing procedural detail ridge and coexisting layers on SaCalobra_Detail_0_0
    cam_loc = unreal.Vector(-95000.0 - 15000.0, -53000.0 - 25000.0, 24150.0 + 12000.0)
    target_loc = unreal.Vector(-95000.0, -53000.0, 24150.0)
    rot = unreal.MathLibrary.find_look_at_rotation(cam_loc, target_loc)

    _camera.set_actor_location(cam_loc, False, False)
    _camera.set_actor_rotation(rot, False)
    _camera.get_component_by_class(unreal.CameraComponent).set_editor_property("field_of_view", 75.0)
    unreal.AutomationLibrary.set_editor_viewport_view_mode(unreal.ViewModeIndex.VMI_LIT)
    unreal.AutomationLibrary.finish_loading_before_screenshot()

    _task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=1920,
        res_y=1080,
        filename=shot4_file,
        camera=_camera,
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes="Procedural Update Layer View",
        delay=2.0,
        force_game_view=False
    )
    _start_time = time.monotonic()

def finish():
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    log("Screenshots 04 and 05 complete! Quitting editor...")
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

_cooling_down = False
_cooldown_start = 0.0

def tick(_delta):
    global _task, _start_time, _step, _cooling_down, _cooldown_start
    if _task is None:
        return

    now = time.monotonic()
    elapsed = now - _start_time

    if _cooling_down:
        if now - _cooldown_start > 1.5:
            _cooling_down = False
            if _step == 5:
                schedule_shot_04()
            elif _step == 4:
                finish()
        return

    # Check if task is done and file exists on disk
    if _step == 5:
        target_file = shot5_file
    else:
        target_file = shot4_file

    file_ready = os.path.exists(target_file) and os.path.getsize(target_file) > 100000
    if (_task.is_task_done() or elapsed > 8.0) and file_ready:
        log(f"Shot {_step} captured and verified on disk! Size: {os.path.getsize(target_file)} bytes in {elapsed:.2f}s")
        _task = None
        _cooling_down = True
        _cooldown_start = now
    elif elapsed > 30.0:
        log(f"Shot {_step} timed out after {elapsed:.2f}s!")
        _task = None
        _cooling_down = True
        _cooldown_start = now

unreal.EditorPythonScripting.set_keep_python_script_alive(True)
schedule_shot_05()
_handle = unreal.register_slate_post_tick_callback(tick)
