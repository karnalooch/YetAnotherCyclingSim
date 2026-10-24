import unreal
import os

log_file_path = "D:/yacs/project/worldgen/houdini/sa_calobra/test_cache_with_plugins_log.txt"
with open(log_file_path, "w") as f:
    f.write("=== START TEST_CACHE_WITH_PLUGINS ===\n")

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
    existing_layers = [l.get_name_bp() for l in target.get_edit_layers_bp()]
    log(f"Existing edit layers: {existing_layers}")

    api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
    api.create_session()

    # Step 1: Ensure Layer1_Manual exists
    if "Layer1_Manual" not in existing_layers:
        log("Creating Layer1_Manual via sop_PE_Load_Landscape_2 bake...")
        load_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Load_Landscape_2.sop_PE_Load_Landscape_2")
        settings_load = unreal.HoudiniPublicAPISettings()
        settings_load.enable_auto_cook = False
        settings_load.enable_auto_bake = False
        wrapper_load = api.instantiate(load_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings_load)
        
        project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
        wrapper_load.set_string_parameter_value("dir", project_dir)
        wrapper_load.set_int_parameter_value("environment", 0) # Unreal
        wrapper_load.set_int_parameter_value("mode", 1) # Update Existing
        wrapper_load.set_int_parameter_value("input7", 1) # Layer1_Manual
        wrapper_load.set_string_parameter_value("output_name", target.get_actor_label())
        
        wrapper_load.recook()
        wrapper_load.process_component_synchronous()
        wrapper_load.bake_all_outputs()
        wrapper_load.process_component_synchronous()
        wrapper_load.delete_instantiated_asset()
        log(f"Layers after load bake: {[l.get_name_bp() for l in target.get_edit_layers_bp()]}")

    # Step 2: Apply manual sculpt mound
    sculpt_center = unreal.Vector(-95000.0, -53000.0, 30000.0)
    radius_cm = 4000.0 # 40 meters
    delta_cm = 450.0 # +4.5 meters
    log(f"Applying sculpt mound at {sculpt_center} (r={radius_cm/100:.1f}m, delta=+{delta_cm/100:.1f}m)...")
    sculpt_ok = unreal.CyclingLandscapeEarthworksLibrary.apply_manual_sculpt_mound(
        target,
        "Layer1_Manual",
        sculpt_center,
        radius_cm,
        delta_cm
    )
    log(f"apply_manual_sculpt_mound returned: {sculpt_ok}")

    # Step 3: Cache Manual Edits via PE_Cache_Landscape
    cache_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Cache_Landscape.sop_PE_Cache_Landscape")
    settings_cache = unreal.HoudiniPublicAPISettings()
    settings_cache.enable_auto_cook = False
    settings_cache.enable_auto_bake = False
    wrapper_cache = api.instantiate(cache_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings_cache)

    inp0 = wrapper_cache.get_input_at_index(0)
    inp0.set_editor_property("export_height_data_per_edit_layer", True)
    inp0.set_input_objects([target])
    set_inp_ok = wrapper_cache.set_input_at_index(0, inp0)
    log(f"wrapper_cache.set_input_at_index(0, inp0) returned: {set_inp_ok}")

    out_file = "D:/yacs/project/worldgen/houdini/sa_calobra/Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Layer_2_Manual_Edits.bgeo.sc"
    wrapper_cache.set_string_parameter_value("file", out_file)

    log("Recooking wrapper_cache...")
    recook_res = wrapper_cache.recook()
    log(f"wrapper_cache.recook() returned: {recook_res}")
    log("Processing wrapper_cache synchronous...")
    wrapper_cache.process_component_synchronous()
    log(f"Post-cook last_error: '{wrapper_cache.get_last_error_message()}'")

    log("Triggering button parameter 'execute'...")
    res = wrapper_cache.trigger_button_parameter("execute")
    log(f"trigger_button_parameter result: {res}")

    wrapper_cache.process_component_synchronous()
    log(f"Post-execute last_error: '{wrapper_cache.get_last_error_message()}'")

    wrapper_cache.delete_instantiated_asset()
    log("Test complete successfully!")

except Exception as e:
    import traceback
    log(f"CRITICAL ERROR: {traceback.format_exc()}")

unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
