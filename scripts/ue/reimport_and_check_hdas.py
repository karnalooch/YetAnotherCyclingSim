import unreal

print("=== RE-IMPORTING PEGASUS HDAS IN UNREAL ===")
asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

hda_cache_path = "D:/yacs/project/worldgen/houdini/sa_calobra/otls/sop_PE_Cache_Landscape.hda"
hda_load_path = "D:/yacs/project/worldgen/houdini/sa_calobra/otls/sop_PE_Load_Landscape.2.hda"

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

# Import PE_Cache_Landscape
task_cache = unreal.AssetImportTask()
task_cache.filename = hda_cache_path
task_cache.destination_path = f"{asset_root}/Houdini"
task_cache.automated = True
task_cache.save = True
task_cache.replace_existing = True
asset_tools.import_asset_tasks([task_cache])

# Import PE_Load_Landscape
task_load = unreal.AssetImportTask()
task_load.filename = hda_load_path
task_load.destination_path = f"{asset_root}/Houdini"
task_load.automated = True
task_load.save = True
task_load.replace_existing = True
asset_tools.import_asset_tasks([task_load])

api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
api.create_session()

load_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Load_Landscape_2.sop_PE_Load_Landscape_2")
cache_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Cache_Landscape.sop_PE_Cache_Landscape")

settings = unreal.HoudiniPublicAPISettings()
settings.enable_auto_cook = False
settings.enable_auto_bake = False

w_load = api.instantiate(load_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)
w_cache = api.instantiate(cache_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)

out = []
out.append("=== Load Landscape Parms ===")
for p in ["output_name", "mode", "input7", "dir", "environment"]:
    val = w_load.get_string_parameter_value(p) or w_load.get_int_parameter_value(p)
    out.append(f"  {p} = {val}")

out.append("\n=== Cache Landscape Parms ===")
for p in ["file", "file2", "execute", "execute2"]:
    val = w_cache.get_string_parameter_value(p) or w_cache.get_int_parameter_value(p)
    out.append(f"  {p} = {val}")

w_load.delete_instantiated_asset()
w_cache.delete_instantiated_asset()

with open("D:/yacs/project/worldgen/houdini/sa_calobra/reimport_check.txt", "w") as f:
    f.write("\n".join(out))

print("Reimport check complete!")
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
