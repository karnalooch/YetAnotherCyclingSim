import unreal

log_file = open("D:/yacs/project/worldgen/houdini/sa_calobra/cache_layer1_test_log.txt", "w")
def log(msg):
    log_file.write(str(msg) + "\n")
    log_file.flush()
    unreal.log(str(msg))

log("=== TESTING PE_CACHE_LANDSCAPE WITH LAYER1_MANUAL ===")
asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
target = [l for l in landscapes if "Detail_0_0" in l.get_actor_label()][0]

log(f"Target: {target.get_actor_label()}")
log(f"Edit layers: {[l.get_name_bp() for l in target.get_edit_layers_bp()]}")

cache_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Cache_Landscape.sop_PE_Cache_Landscape")
api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
api.create_session()

settings = unreal.HoudiniPublicAPISettings()
settings.enable_auto_cook = False
settings.enable_auto_bake = False

wrapper = api.instantiate(cache_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)

inp0 = wrapper.get_input_at_index(0)
inp0.set_editor_property("export_height_data_per_edit_layer", True)
inp0.set_input_objects([target])

test_manual_file = "D:/yacs/project/worldgen/houdini/sa_calobra/cache/test_exported_manual.bgeo.sc"
wrapper.set_string_parameter_value("file", test_manual_file)

log("Processing component synchronous...")
wrapper.process_component_synchronous()
log(f"Post-cook last_error: '{wrapper.get_last_error_message()}'")

log("Triggering execute button ('Cache Manual Edits')...")
res = wrapper.trigger_button_parameter("execute")
log(f"trigger_button_parameter returned: {res}")

wrapper.process_component_synchronous()
log(f"Post-execute last_error: '{wrapper.get_last_error_message()}'")

wrapper.delete_instantiated_asset()
log("Done!")
log_file.close()

unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
