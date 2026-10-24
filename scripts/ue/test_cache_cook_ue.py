import unreal

print("=== TESTING EDIT LAYERS & PE_CACHE COOK ===")
asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]

for ls in landscapes:
    print(f"\nLandscape: {ls.get_actor_label()}")
    layers = ls.get_edit_layers_bp()
    print(f"  get_edit_layers_bp: {len(layers)} layers")
    for lyr in layers:
        print(f"    Layer object: {lyr.get_name()}, class={lyr.get_class().get_name()}")
        # Inspect properties and methods of edit layer
        for m in dir(lyr):
            if not m.startswith("_"):
                try:
                    val = getattr(lyr, m)
                    if not callable(val):
                        print(f"      prop {m} = {val}")
                except Exception:
                    pass

cache_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Cache_Landscape.sop_PE_Cache_Landscape")
api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
api.create_session()

settings = unreal.HoudiniPublicAPISettings()
settings.enable_auto_cook = False
settings.enable_auto_bake = False

wrapper = api.instantiate(cache_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)
print(f"\nInstantiated wrapper: {wrapper}")
inp0 = wrapper.get_input_at_index(0)
print(f"Input 0: {inp0}")
if inp0:
    res = inp0.set_input_objects([landscapes[0]])
    print(f"inp0.set_input_objects result: {res}")
    objs = inp0.get_input_objects()
    print(f"inp0.get_input_objects: {objs}")

wrapper.delete_instantiated_asset()
