import unreal

asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

cache_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Cache_Landscape.sop_PE_Cache_Landscape")
api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
api.create_session()

settings = unreal.HoudiniPublicAPISettings()
settings.enable_auto_cook = False
settings.enable_auto_bake = False

wrapper = api.instantiate(cache_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)
inp0 = wrapper.get_input_at_index(0)

out = []
props = [
    "export_height_data_per_edit_layer",
    "export_paint_layers_per_edit_layer",
    "export_merged_paint_layers",
    "export_main_geometry",
    "export_colliders",
    "keep_world_transform"
]

for p in props:
    try:
        val = inp0.get_editor_property(p)
        out.append(f"{p} = {val}")
    except Exception as e:
        out.append(f"{p} error: {e}")

with open("D:/yacs/project/worldgen/houdini/sa_calobra/inp0_props.txt", "w") as f:
    f.write("\n".join(out))

wrapper.delete_instantiated_asset()
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
