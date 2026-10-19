import unreal

print("=== INSPECTING PE_CACHE_LANDSCAPE WRAPPER ===")
asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
print(f"Found {len(landscapes)} landscapes:")
for ls in landscapes:
    print(f"  {ls.get_actor_label()}")

cache_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Cache_Landscape.sop_PE_Cache_Landscape")
print(f"Loaded Cache Asset: {cache_asset}")

api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
api.create_session()

settings = unreal.HoudiniPublicAPISettings()
settings.enable_auto_cook = False
settings.enable_auto_bake = False

wrapper = api.instantiate(cache_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)
print(f"Instantiated wrapper: {wrapper}")

if wrapper:
    print("\n--- Wrapper Parameter Names ---")
    for p in wrapper.get_parameter_names():
        val = wrapper.get_float_parameter_value(p) or wrapper.get_string_parameter_value(p) or wrapper.get_integer_parameter_value(p)
        print(f"  param: {p} = {val}")
    
    print("\n--- Wrapper Input Names / Info ---")
    # Let's inspect input methods on wrapper
    input_methods = [m for m in dir(wrapper) if "input" in m.lower()]
    for im in input_methods:
        print(f"  wrapper.{im}")
    
    # Try calling get_num_inputs
    try:
        num_inputs = wrapper.get_num_inputs()
        print(f"  Num inputs: {num_inputs}")
        for i in range(num_inputs):
            print(f"    input {i} name: {wrapper.get_input_name(i)}")
    except Exception as e:
        print(f"  Error reading inputs: {e}")

    wrapper.delete_instantiated_asset()
