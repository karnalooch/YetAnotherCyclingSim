import unreal
import os
import time

log_file_path = "D:/yacs/project/worldgen/houdini/sa_calobra/evidence/shot_04_log.txt"
with open(log_file_path, "w") as f:
    f.write("=== CAPTURING SHOT 04 (PROCEDURAL UPDATE) ===\n")

def log(msg):
    with open(log_file_path, "a") as f:
        f.write(str(msg) + "\n")
    unreal.log(str(msg))

asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"
evidence_dir = "D:/yacs/project/worldgen/houdini/sa_calobra/evidence"
shot4_file = f"{evidence_dir}/04_unreal_procedural_update.png"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
target = [l for l in landscapes if "Detail_0_0" in l.get_actor_label()][0]
log(f"Target Landscape: {target.get_actor_label()}")
layers = [l.get_name_bp() for l in target.get_edit_layers_bp()]
log(f"Current layers: {layers}")

if os.path.exists(shot4_file):
    os.remove(shot4_file)

# Camera viewing SaCalobra_Detail_0_0 with Procedural update
cam_loc = unreal.Vector(-95000.0 - 15000.0, -53000.0 - 25000.0, 24150.0 + 12000.0)
target_loc = unreal.Vector(-95000.0, -53000.0, 24150.0)
rot = unreal.MathLibrary.find_look_at_rotation(cam_loc, target_loc)

camera = actor_subsystem.spawn_actor_from_class(unreal.CameraActor, cam_loc, rot, transient=True)
camera.get_component_by_class(unreal.CameraComponent).set_editor_property("field_of_view", 75.0)

unreal.AutomationLibrary.set_editor_viewport_view_mode(unreal.ViewModeIndex.VMI_LIT)
unreal.AutomationLibrary.finish_loading_before_screenshot()

log(f"Taking screenshot to {shot4_file}...")
task = unreal.AutomationLibrary.take_high_res_screenshot(
    res_x=1920,
    res_y=1080,
    filename=shot4_file,
    camera=camera,
    mask_enabled=False,
    capture_hdr=False,
    comparison_tolerance=unreal.ComparisonTolerance.LOW,
    comparison_notes="Procedural Update View",
    delay=2.0,
    force_game_view=False
)

start_time = time.monotonic()
handle = None

def finish():
    global handle
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
        handle = None
    log("Quitting editor...")
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

def tick(_delta):
    elapsed = time.monotonic() - start_time
    file_ready = os.path.exists(shot4_file) and os.path.getsize(shot4_file) > 100000
    if file_ready or (task.is_task_done() and os.path.exists(shot4_file)):
        log(f"Shot 04 verified on disk! Size: {os.path.getsize(shot4_file)} bytes in {elapsed:.2f}s")
        finish()
    elif elapsed > 30.0:
        log(f"Shot 04 timed out after {elapsed:.2f}s!")
        finish()

unreal.EditorPythonScripting.set_keep_python_script_alive(True)
handle = unreal.register_slate_post_tick_callback(tick)
