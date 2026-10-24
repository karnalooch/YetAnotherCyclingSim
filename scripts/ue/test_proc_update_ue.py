import unreal

log_file_path = "D:/yacs/project/worldgen/houdini/sa_calobra/test_proc_update_log.txt"
with open(log_file_path, "w") as f:
    f.write("=== START TEST_PROC_UPDATE_UE ===\n")

def log(msg):
    with open(log_file_path, "a") as f:
        f.write(str(msg) + "\n")
    print(str(msg))

try:
    asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
    map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    level_subsystem.load_level(map_path)

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
    target = [l for l in landscapes if "Detail_0_0" in l.get_actor_label()][0]

    log(f"Target landscape: {target.get_actor_label()}")
    layers_before = [l.get_name_bp() for l in target.get_edit_layers_bp()]
    log(f"Edit layers before: {layers_before}")

    # Bake Layer2_Procedural via sop_PE_Load_Landscape_2
    api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
    api.create_session()

    load_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Load_Landscape_2.sop_PE_Load_Landscape_2")
    settings = unreal.HoudiniPublicAPISettings()
    settings.enable_auto_cook = False
    settings.enable_auto_bake = False
    wrapper = api.instantiate(load_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)

    project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
    wrapper.set_string_parameter_value("dir", project_dir)
    wrapper.set_int_parameter_value("environment", 0) # Unreal
    wrapper.set_int_parameter_value("mode", 1) # Update Existing
    wrapper.set_int_parameter_value("input7", 2) # Layer2_Procedural
    wrapper.set_string_parameter_value("output_name", target.get_actor_label())

    log("Cooking and baking Layer2_Procedural...")
    wrapper.recook()
    wrapper.process_component_synchronous()
    wrapper.bake_all_outputs()
    wrapper.process_component_synchronous()
    wrapper.delete_instantiated_asset()

    layers_after = [l.get_name_bp() for l in target.get_edit_layers_bp()]
    log(f"Edit layers after: {layers_after}")

    # Save the map package so the layers and edits persist
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log("Level saved successfully with coexisting layers!")

except Exception as e:
    import traceback
    log(f"CRITICAL ERROR: {traceback.format_exc()}")

unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
