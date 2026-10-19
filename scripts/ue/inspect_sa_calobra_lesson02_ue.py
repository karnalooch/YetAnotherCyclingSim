import unreal

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

map_path = "/Game/Worlds/SaCalobra_Houdini_20261016/L_SaCalobra_LandscapeOnly"
level_subsystem.load_level(map_path)

landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
print(f"\nFOUND {len(landscapes)} LANDSCAPES:")
for ls in landscapes:
    print(f"Actor: {ls.get_actor_label()} ({ls.get_name()}), Class: {ls.get_class().get_name()}")
    loc = ls.get_actor_location()
    print(f"  Location: {loc.x}, {loc.y}, {loc.z}")

# Check LandscapeBlueprintFunctionLibrary or methods
print("\nLandscape methods/props matching 'layer':")
for m in dir(unreal.LandscapeBlueprintFunctionLibrary):
    if "layer" in m.lower():
        print("  LandscapeBlueprintFunctionLibrary." + m)

for m in dir(landscapes[0]):
    if "layer" in m.lower():
        print("  Landscape." + m)

api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
print(f"\nHoudini API: {api}")
api.create_session()
print(f"Houdini Session valid: {api.is_session_valid()}")
