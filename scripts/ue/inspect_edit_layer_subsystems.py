import unreal

out = []

# Search for any functions with 'layer' in name across common libraries
for cls_name in dir(unreal):
    cls = getattr(unreal, cls_name)
    if "library" in cls_name.lower() or "subsystem" in cls_name.lower() or "util" in cls_name.lower():
        for m in dir(cls):
            if "layer" in m.lower():
                out.append(f"{cls_name}.{m}")

# Inspect the existing edit layer on SaCalobra_Detail_0_0
asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"
level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
ls0 = [l for l in landscapes if "Detail_0_0" in l.get_actor_label()][0]

layers_bp = ls0.get_edit_layers_bp()
out.append(f"\nls0 layers_bp: {layers_bp}")
if layers_bp:
    lyr0 = layers_bp[0]
    out.append(f"lyr0 type: {type(lyr0)}, class: {lyr0.get_class().get_name()}")
    out.append(f"lyr0 name: {lyr0.get_name()}")
    out.append(f"lyr0 get_name_bp(): {lyr0.get_name_bp()}")
    for p in dir(lyr0):
        if not p.startswith("_"):
            try:
                val = getattr(lyr0, p)
                if not callable(val):
                    out.append(f"  prop: {p} = {val}")
            except Exception:
                pass

with open("D:/yacs/project/worldgen/houdini/sa_calobra/inspect_edit_layer_subsystems.txt", "w") as f:
    f.write("\n".join(out))

print("Wrote inspect_edit_layer_subsystems.txt")
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
