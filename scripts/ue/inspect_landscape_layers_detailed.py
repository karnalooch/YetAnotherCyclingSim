import unreal

asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]

out = []
out.append(f"Found {len(landscapes)} landscapes:")
for ls in landscapes:
    out.append(f"\n--- Landscape: {ls.get_actor_label()} ---")
    out.append(f"Class: {ls.get_class().get_name()}")
    
    # Check edit layers
    try:
        layers = ls.get_edit_layers()
        out.append(f"get_edit_layers count: {len(layers)}")
        for i, l in enumerate(layers):
            out.append(f"  Layer {i}: {l.get_name()}, class={l.get_class().get_name()}")
    except Exception as e:
        out.append(f"get_edit_layers error: {e}")

    try:
        layers_bp = ls.get_edit_layers_bp()
        out.append(f"get_edit_layers_bp: {layers_bp}")
    except Exception as e:
        out.append(f"get_edit_layers_bp error: {e}")

# Check all Landscape Blueprint / Python methods related to edit layer
ls0 = landscapes[0]
out.append("\n=== Landscape edit layer methods ===")
for m in dir(ls0):
    if any(k in m.lower() for k in ["layer", "create", "add", "edit"]):
        out.append(f"  {m}")

# Check LandscapeBlueprintLibrary / LandscapeEditLayerSubsystem or similar
out.append("\n=== Subsystems / Libraries ===")
for cls_name in dir(unreal):
    if "landscape" in cls_name.lower():
        cls = getattr(unreal, cls_name)
        if isinstance(cls, type):
            out.append(f"Class: {cls_name}")

result_text = "\n".join(out)
with open("D:/yacs/project/worldgen/houdini/sa_calobra/ue_landscape_inspect_result.txt", "w") as f:
    f.write(result_text)

print("Wrote inspection results to D:/yacs/project/worldgen/houdini/sa_calobra/ue_landscape_inspect_result.txt")
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
