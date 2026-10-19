import unreal

log_file = open("D:/yacs/project/worldgen/houdini/sa_calobra/button_test_log.txt", "w")
def log(msg):
    log_file.write(str(msg) + "\n")
    log_file.flush()
    unreal.log(str(msg))

log("=== TESTING TRIGGER_BUTTON_PARAMETER IN HOUDINI ENGINE ===")
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

inp0 = wrapper.get_input_at_index(0)
inp0.set_input_objects([target])

test_all_layers = "D:/yacs/project/worldgen/houdini/sa_calobra/cache/test_unreal_all_inputs.bgeo.sc"
wrapper.set_string_parameter_value("file2", test_all_layers)

log("Processing component synchronous...")
wrapper.process_component_synchronous()

log("Triggering execute2 button ('Save All Layers')...")
res = wrapper.trigger_button_parameter("execute2")
log(f"trigger_button_parameter returned: {res}")

wrapper.process_component_synchronous()
log(f"Post-execute2 last_error: '{wrapper.get_last_error_message()}'")

wrapper.delete_instantiated_asset()
log("Done!")
log_file.close()

unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
