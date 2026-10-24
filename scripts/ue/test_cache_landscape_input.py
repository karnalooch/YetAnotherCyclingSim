import unreal

print("=== TESTING PE_CACHE_LANDSCAPE INPUT SETUP ===")
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
api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
api.create_session()

settings = unreal.HoudiniPublicAPISettings()
settings.enable_auto_cook = False
settings.enable_auto_bake = False

wrapper = api.instantiate(cache_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)
print(f"Wrapper: {wrapper}")
num_node_inputs = wrapper.get_num_node_inputs()
print(f"Num node inputs: {num_node_inputs}")

# Check input parameters
input_params = wrapper.get_input_parameters()
print(f"Input parameters: {input_params}")

# Inspect input object at index 0
inp0 = wrapper.get_input_at_index(0)
print(f"Input 0 wrapper: {inp0}")
if inp0:
    for m in dir(inp0):
        if not m.startswith("_"):
            print(f"  inp0.{m}")

# Try setting landscape to input 0
target_landscape = [l for l in landscapes if "Detail_0_0" in l.get_actor_label()][0]
print(f"Target landscape: {target_landscape.get_actor_label()}")
res = wrapper.set_input_at_index(0, target_landscape)
print(f"set_input_at_index(0, target_landscape) result: {res}")

wrapper.delete_instantiated_asset()
