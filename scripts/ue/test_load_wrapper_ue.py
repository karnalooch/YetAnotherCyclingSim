import unreal

print("=== TESTING PE_LOAD_LANDSCAPE WRAPPER IN UNREAL ===")
asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

load_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Load_Landscape_2.sop_PE_Load_Landscape_2")
print(f"Loaded Asset: {load_asset}")

api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
api.create_session()
print(f"Session valid: {api.is_session_valid()}")

settings = unreal.HoudiniPublicAPISettings()
settings.enable_auto_cook = False
settings.enable_auto_bake = False

wrapper = api.instantiate(load_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)
print(f"Instantiated wrapper: {wrapper}")

if wrapper:
    print("\nParameters:")
    for p in ["environment", "mode", "input7", "dir"]:
        val = wrapper.get_string_parameter_value(p) or wrapper.get_int_parameter_value(p)
        print(f"  {p} = {val}")
    
    wrapper.delete_instantiated_asset()
    print("Cleaned up wrapper.")
