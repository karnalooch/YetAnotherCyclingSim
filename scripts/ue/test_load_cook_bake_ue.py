import unreal, sys

log_file = open("D:/yacs/project/worldgen/houdini/sa_calobra/load_bake_log.txt", "w")
def log(msg):
    log_file.write(str(msg) + "\n")
    log_file.flush()
    unreal.log(str(msg))

log("=== TESTING PE_LOAD_LANDSCAPE COOK IN UNREAL ===")
asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
target = [l for l in landscapes if "Detail_0_0" in l.get_actor_label()][0]

log(f"Target Landscape: {target.get_actor_label()}")
log(f"Initial edit layers: {target.get_edit_layers_bp()}")

api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
api.create_session()
log(f"API session valid: {api.is_session_valid()}")

load_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Load_Landscape_2.sop_PE_Load_Landscape_2")
settings = unreal.HoudiniPublicAPISettings()
settings.enable_auto_cook = False
settings.enable_auto_bake = False

wrapper = api.instantiate(load_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)
log(f"Instantiated wrapper: {wrapper}")

project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
wrapper.set_string_parameter_value("dir", project_dir)
wrapper.set_int_parameter_value("environment", 0) # Unreal
wrapper.set_int_parameter_value("mode", 1) # Update Existing
wrapper.set_int_parameter_value("input7", 1) # Layer1_Manual
wrapper.set_string_parameter_value("output_name", target.get_actor_label())

state = {"ticks": 0, "cooked": False, "baked": False, "done": False}
unreal.EditorPythonScripting.set_keep_python_script_alive(True)

def on_post_cook(w, success):
    log(f"\n>>> ON_POST_COOK: success={success}, err={w.get_last_error_message()} <<<")
    state["cooked"] = True
    log(f"Outputs count: {w.get_num_outputs()}")
    log("Calling bake()...")
    bake_res = w.bake()
    log(f"bake() result: {bake_res}")
    state["done_ticks"] = 30

def on_post_bake(w, success):
    log(f"\n>>> ON_POST_BAKE: success={success} <<<")
    state["baked"] = True

wrapper.on_post_cook_delegate.add_callable(on_post_cook)
wrapper.on_post_bake_delegate.add_callable(on_post_bake)

res = wrapper.recook()
log(f"recook() returned: {res}")

def tick(delta_seconds):
    state["ticks"] += 1
    if "done_ticks" in state:
        state["done_ticks"] -= 1
        if state["done_ticks"] <= 0 and not state["done"]:
            state["done"] = True
            log("\nFinal check of target edit layers:")
            log(f"Edit layers: {target.get_edit_layers_bp()}")
            wrapper.delete_instantiated_asset()
            unreal.unregister_slate_post_tick_callback(tick_handle)
            unreal.EditorPythonScripting.set_keep_python_script_alive(False)
            log("Closing log and quitting.")
            log_file.close()
            unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
    elif state["ticks"] > 900: # ~15 seconds timeout
        log("Timeout waiting for cook/bake!")
        state["done"] = True
        wrapper.delete_instantiated_asset()
        unreal.unregister_slate_post_tick_callback(tick_handle)
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        log_file.close()
        unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

tick_handle = unreal.register_slate_post_tick_callback(tick)
