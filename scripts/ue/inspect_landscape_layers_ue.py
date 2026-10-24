import unreal

print("=== INSPECTING LANDSCAPE EDIT LAYERS IN UNREAL ===")
asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]

for ls in landscapes:
    print(f"\nLandscape: {ls.get_actor_label()} ({ls.get_name()})")
    try:
        layers = ls.get_edit_layers()
        print(f"  Total edit layers: {len(layers)}")
        for i, lyr in enumerate(layers):
            print(f"    Layer {i}: {lyr.get_name()}, class={lyr.get_class().get_name()}")
            for p in ["layer_name", "name", "b_is_visible", "b_locked", "alpha"]:
                try:
                    val = lyr.get_editor_property(p)
                    print(f"      {p} = {val}")
                except Exception:
                    pass
    except Exception as e:
        print(f"  get_edit_layers error: {e}")

# Check methods on Landscape to create edit layers
ls0 = landscapes[0]
print("\nMethods on Landscape matching 'layer':")
for m in dir(ls0):
    if "layer" in m.lower():
        print(f"  {m}")
