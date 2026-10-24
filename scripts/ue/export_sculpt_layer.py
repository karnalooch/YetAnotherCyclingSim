import unreal
import os

asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
target = [l for l in landscapes if "Detail_0_0" in l.get_actor_label()][0]

existing_layers = [l.get_name_bp() for l in target.get_edit_layers_bp()]
api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
api.create_session()

# Apply sculpt mound
sculpt_center = unreal.Vector(-95000.0, -53000.0, 24150.0)
radius_cm = 4000.0 # 40 meters
delta_cm = 450.0 # +4.5 meters
sculpt_ok = unreal.CyclingLandscapeEarthworksLibrary.apply_manual_sculpt_mound(
    target, "Layer1_Manual", sculpt_center, radius_cm, delta_cm
)
print(f"apply_manual_sculpt_mound: {sculpt_ok}")

# Cache to SCULPT.bgeo.sc
cache_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Cache_Landscape.sop_PE_Cache_Landscape")
settings_cache = unreal.HoudiniPublicAPISettings()
settings_cache.enable_auto_cook = False
settings_cache.enable_auto_bake = False
wrapper_cache = api.instantiate(cache_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings_cache)

inp0 = wrapper_cache.get_input_at_index(0)
inp0.set_editor_property("export_height_data_per_edit_layer", True)
inp0.set_input_objects([target])
wrapper_cache.set_input_at_index(0, inp0)

out_file = f"{project_dir}/Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Layer_2_Manual_Edits.SCULPT.bgeo.sc"
wrapper_cache.set_string_parameter_value("file", out_file)
wrapper_cache.recook()
wrapper_cache.process_component_synchronous()
wrapper_cache.trigger_button_parameter("execute")
wrapper_cache.process_component_synchronous()
wrapper_cache.delete_instantiated_asset()

print("SCULPT export complete! Exists:", os.path.exists(out_file), "Size:", os.path.getsize(out_file) if os.path.exists(out_file) else 0)

# Clear manual layer in the session so map stays clean
unreal.CyclingLandscapeEarthworksLibrary.clear_manual_layer(target, "Layer1_Manual")
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
