import unreal
import os
import time
import traceback

log_file_path = "D:/yacs/project/worldgen/houdini/sa_calobra/evidence/full_cycle_log.txt"
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
with open(log_file_path, "w") as f:
    f.write("=== START LESSON 02 FULL CYCLE & EVIDENCE CAPTURE ===\n")

def log(msg):
    with open(log_file_path, "a") as f:
        f.write(str(msg) + "\n")
    unreal.log(str(msg))

asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
evidence_dir = f"{project_dir}/evidence"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
target = [l for l in landscapes if "Detail_0_0" in l.get_actor_label()][0]
log(f"Target Landscape: {target.get_actor_label()}")
existing_layers = [l.get_name_bp() for l in target.get_edit_layers_bp()]
log(f"Initial layers: {existing_layers}")

api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
api.create_session()
load_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Load_Landscape_2.sop_PE_Load_Landscape_2")

# 1. Ensure Layer1_Manual exists
if "Layer1_Manual" not in existing_layers:
    log("Baking Layer1_Manual via PE_Load_Landscape...")
    settings = unreal.HoudiniPublicAPISettings()
    settings.enable_auto_cook = False
    settings.enable_auto_bake = False
    w = api.instantiate(load_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)
    w.set_string_parameter_value("dir", project_dir)
    w.set_int_parameter_value("environment", 0)
    w.set_int_parameter_value("mode", 1)
    w.set_int_parameter_value("input7", 1) # Layer1_Manual
    w.set_string_parameter_value("output_name", target.get_actor_label())
    w.recook()
    w.process_component_synchronous()
    w.bake_all_outputs()
    w.process_component_synchronous()
    w.delete_instantiated_asset()

# 2. Ensure Layer2_Procedural exists
layers_now = [l.get_name_bp() for l in target.get_edit_layers_bp()]
if "Layer2_Procedural" not in layers_now:
    log("Baking Layer2_Procedural via PE_Load_Landscape...")
    settings = unreal.HoudiniPublicAPISettings()
    settings.enable_auto_cook = False
    settings.enable_auto_bake = False
    w = api.instantiate(load_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)
    w.set_string_parameter_value("dir", project_dir)
    w.set_int_parameter_value("environment", 0)
    w.set_int_parameter_value("mode", 1)
    w.set_int_parameter_value("input7", 2) # Layer2_Procedural
    w.set_string_parameter_value("output_name", target.get_actor_label())
    w.recook()
    w.process_component_synchronous()
    w.bake_all_outputs()
    w.process_component_synchronous()
    w.delete_instantiated_asset()

all_layers = [l.get_name_bp() for l in target.get_edit_layers_bp()]
log(f"Coexisting layers on {target.get_actor_label()}: {all_layers}")

# 3. Apply manual sculpt mound (+4.5m) to Layer1_Manual
sculpt_center = unreal.Vector(-95000.0, -53000.0, 24150.0)
radius_cm = 4000.0
delta_cm = 450.0
log(f"Applying manual sculpt mound at {sculpt_center} (r={radius_cm/100:.1f}m, delta=+{delta_cm/100:.1f}m)...")
sculpt_ok = unreal.CyclingLandscapeEarthworksLibrary.apply_manual_sculpt_mound(
    target, "Layer1_Manual", sculpt_center, radius_cm, delta_cm
)
log(f"apply_manual_sculpt_mound returned: {sculpt_ok}")

# 4. Export manual edit via original PE_Cache_Landscape
log("Exporting Layer1_Manual via original PE_Cache_Landscape...")
cache_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Cache_Landscape.sop_PE_Cache_Landscape")
settings_cache = unreal.HoudiniPublicAPISettings()
settings_cache.enable_auto_cook = False
settings_cache.enable_auto_bake = False
w_cache = api.instantiate(cache_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings_cache)

inp0 = w_cache.get_input_at_index(0)
inp0.set_editor_property("export_height_data_per_edit_layer", True)
inp0.set_input_objects([target])
w_cache.set_input_at_index(0, inp0)

out_cache_file = f"{project_dir}/Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Layer_2_Manual_Edits.bgeo.sc"
w_cache.set_string_parameter_value("file", out_cache_file)
w_cache.recook()
w_cache.process_component_synchronous()
w_cache.trigger_button_parameter("execute")
w_cache.process_component_synchronous()
w_cache.delete_instantiated_asset()
log(f"Exported cache file exists: {os.path.exists(out_cache_file)}, size: {os.path.getsize(out_cache_file)} bytes")

# Save packages so the layers and mound are preserved for rendering
unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
log("Map package saved with coexisting layers and manual mound.")

# Multi-shot capture state machine
_camera = None
_shots = [
    {
        "filename": f"{evidence_dir}/01_unreal_full_landscape.png",
        "loc": unreal.Vector(-100000.0, -280000.0, 180000.0),
        "target": unreal.Vector(0.0, 74000.0, 40000.0),
        "fov": 80.0,
        "desc": "Full Landscape Overview (4 detail tiles + context)"
    },
    {
        "filename": f"{evidence_dir}/02_unreal_manual_sculpt.png",
        "loc": unreal.Vector(-95000.0 + 8000.0, -53000.0 - 8000.0, 24150.0 + 4000.0),
        "target": unreal.Vector(-95000.0, -53000.0, 24150.0 + 450.0),
        "fov": 65.0,
        "desc": "Close-up of Manual Sculpt Mound (+4.5m) on Layer1_Manual"
    },
    {
        "filename": f"{evidence_dir}/04_unreal_procedural_update.png",
        "loc": unreal.Vector(-95000.0 - 15000.0, -53000.0 - 25000.0, 24150.0 + 12000.0),
        "target": unreal.Vector(-95000.0, -53000.0, 24150.0),
        "fov": 75.0,
        "desc": "Procedural Update with coexisting Source, Manual and Procedural layers"
    }
]

_current_shot_idx = 0
_current_task = None
_shot_start_time = 0.0
_handle = None

def schedule_next_shot():
    global _current_shot_idx, _current_task, _shot_start_time, _camera
    if _current_shot_idx >= len(_shots):
        log("All 3 active shots captured! Now reverting Layer1_Manual to clean baseline...")
        revert_and_capture_baseline()
        return

    shot = _shots[_current_shot_idx]
    log(f"\n--- Capturing shot {_current_shot_idx + 1}/{len(_shots)}: {shot['desc']} ---")
    
    if os.path.exists(shot['filename']):
        os.remove(shot['filename'])

    rot = unreal.MathLibrary.find_look_at_rotation(shot['loc'], shot['target'])
    if _camera is None:
        _camera = actor_subsystem.spawn_actor_from_class(unreal.CameraActor, shot['loc'], rot, transient=True)
    else:
        _camera.set_actor_location(shot['loc'], False, False)
        _camera.set_actor_rotation(rot, False)

    _camera.get_component_by_class(unreal.CameraComponent).set_editor_property("field_of_view", shot['fov'])
    unreal.AutomationLibrary.set_editor_viewport_view_mode(unreal.ViewModeIndex.VMI_LIT)
    unreal.AutomationLibrary.finish_loading_before_screenshot()

    _current_task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=1920,
        res_y=1080,
        filename=shot['filename'],
        camera=_camera,
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes=shot['desc'],
        delay=2.0,
        force_game_view=False
    )
    _shot_start_time = time.monotonic()

_baseline_task = None
_reverting = False

def revert_and_capture_baseline():
    global _reverting, _baseline_task, _shot_start_time, _camera
    _reverting = True
    
    # Revert the manual layer
    log("Calling clear_manual_layer on Layer1_Manual...")
    clear_ok = unreal.CyclingLandscapeEarthworksLibrary.clear_manual_layer(target, "Layer1_Manual")
    log(f"clear_manual_layer returned: {clear_ok}")

    # Save reverted package
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log("Saved dirty packages with clean neutral baseline.")

    # Frame 05 close-up matching shot 02
    shot5_file = f"{evidence_dir}/05_reverted_clean_baseline.png"
    if os.path.exists(shot5_file):
        os.remove(shot5_file)

    shot2 = _shots[1] # same pose as manual sculpt close-up
    rot = unreal.MathLibrary.find_look_at_rotation(shot2['loc'], shot2['target'])
    _camera.set_actor_location(shot2['loc'], False, False)
    _camera.set_actor_rotation(rot, False)
    _camera.get_component_by_class(unreal.CameraComponent).set_editor_property("field_of_view", shot2['fov'])
    unreal.AutomationLibrary.set_editor_viewport_view_mode(unreal.ViewModeIndex.VMI_LIT)
    unreal.AutomationLibrary.finish_loading_before_screenshot()

    log(f"Scheduling 05_reverted_clean_baseline.png...")
    _baseline_task = unreal.AutomationLibrary.take_high_res_screenshot(
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
    _shot_start_time = time.monotonic()

def finish_all():
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    log("FULL CYCLE COMPLETE! Quitting editor...")
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

def tick(_delta):
    global _current_shot_idx, _current_task, _shot_start_time, _baseline_task, _reverting
    elapsed = time.monotonic() - _shot_start_time
    
    if not _reverting:
        if _current_task and _current_task.is_task_done():
            log(f"Shot {_current_shot_idx + 1} completed in {elapsed:.2f}s!")
            _current_shot_idx += 1
            schedule_next_shot()
        elif elapsed > 30.0:
            log(f"Shot {_current_shot_idx + 1} timed out!")
            _current_shot_idx += 1
            schedule_next_shot()
    else:
        if _baseline_task and _baseline_task.is_task_done():
            log(f"Baseline shot 05 completed in {elapsed:.2f}s!")
            finish_all()
        elif elapsed > 30.0:
            log(f"Baseline shot 05 timed out!")
            finish_all()

log("Starting capture sequence...")
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
schedule_next_shot()
_handle = unreal.register_slate_post_tick_callback(tick)
