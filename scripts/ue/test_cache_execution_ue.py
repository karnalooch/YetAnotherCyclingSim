import unreal, sys

print("=== TESTING PE_CACHE_LANDSCAPE ASYNC COOK ===")
asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
target = [l for l in landscapes if "Detail_0_0" in l.get_actor_label()][0]

cache_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Cache_Landscape.sop_PE_Cache_Landscape")
api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
api.create_session()

settings = unreal.HoudiniPublicAPISettings()
settings.enable_auto_cook = False
settings.enable_auto_bake = False

wrapper = api.instantiate(cache_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)
print(f"Wrapper: {wrapper}")

# Set input 0 to target landscape
inp0 = wrapper.get_input_at_index(0)
inp0.set_input_objects([target])
print(f"Input objects: {inp0.get_input_objects()}")

test_cache_file = "D:/yacs/project/worldgen/houdini/sa_calobra/cache/test_ue_cache_manual.bgeo.sc"
wrapper.set_string_parameter_value("file", test_cache_file)
print(f"Set file param to: {test_cache_file}")

state = {"done": False, "ticks": 0, "cooked": False}
unreal.EditorPythonScripting.set_keep_python_script_alive(True)

def on_post_cook(w, success):
    print(f"\n>>> ON_POST_COOK: success={success}, last_error={w.get_last_error_message()} <<<")
    state["cooked"] = True
    print("Triggering execute button ('Cache Manual Edits')...")
    res = w.trigger_button_parameter("execute")
    print(f"trigger_button_parameter('execute') result: {res}")
    # Give it 10 ticks then finish
    state["done_after_ticks"] = 15

def on_post_processing(w):
    print(f"\n>>> ON_POST_PROCESSING: outputs={w.get_num_outputs()} <<<")

wrapper.on_post_cook_delegate.add_callable(on_post_cook)
wrapper.on_post_processing_delegate.add_callable(on_post_processing)

res = wrapper.recook()
print(f"wrapper.recook() returned: {res}")

def tick(delta_seconds):
    state["ticks"] += 1
    if "done_after_ticks" in state:
        state["done_after_ticks"] -= 1
        if state["done_after_ticks"] <= 0 and not state["done"]:
            state["done"] = True
            print("Finished caching test! Cleaning up...")
            wrapper.delete_instantiated_asset()
            unreal.unregister_slate_post_tick_callback(tick_handle)
            unreal.EditorPythonScripting.set_keep_python_script_alive(False)
            unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
    elif state["ticks"] > 600: # Timeout after ~10 seconds at 60fps
        print("Timeout waiting for cook!")
        state["done"] = True
        wrapper.delete_instantiated_asset()
        unreal.unregister_slate_post_tick_callback(tick_handle)
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

tick_handle = unreal.register_slate_post_tick_callback(tick)
