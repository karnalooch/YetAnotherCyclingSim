import unreal

print("=== STARTING PEGASUS HDA IMPORT & WRAPPER TEST ===")
asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
api.create_session()
print(f"Houdini Session valid: {api.is_session_valid()}")

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
print(f"Imported Cache HDA paths: {task_cache.imported_object_paths}")

# Import PE_Load_Landscape
task_load = unreal.AssetImportTask()
task_load.filename = hda_load_path
task_load.destination_path = f"{asset_root}/Houdini"
task_load.automated = True
task_load.save = True
task_load.replace_existing = True
asset_tools.import_asset_tasks([task_load])
print(f"Imported Load HDA paths: {task_load.imported_object_paths}")

if task_cache.imported_object_paths:
    cache_asset = unreal.load_asset(task_cache.imported_object_paths[0])
    print(f"Cache Asset: {cache_asset}")
    settings = unreal.HoudiniPublicAPISettings()
    settings.enable_auto_cook = False
    settings.enable_auto_bake = False
    wrapper = api.instantiate(cache_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_ACTOR, settings)
    print(f"Cache Wrapper: {wrapper}")
    if wrapper:
        print("Wrapper methods:")
        for m in dir(wrapper):
            if not m.startswith("_"):
                print(f"  {m}")
        wrapper.delete_instantiated_asset()
