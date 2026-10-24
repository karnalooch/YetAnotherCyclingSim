import unreal

asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
target = [l for l in landscapes if "Detail_0_0" in l.get_actor_label()][0]

lyr0 = target.get_edit_layers_bp()[0]

out = []
out.append(f"Class: {lyr0.get_class().get_name()}")
out.append(f"Name: {lyr0.get_name()}")
out.append(f"Name BP: {lyr0.get_name_bp()}")

for p in ["name", "layer_name", "guid", "b_locked", "b_is_visible", "alpha"]:
    try:
        val = lyr0.get_editor_property(p)
        out.append(f"prop {p} = {val}")
    except Exception as e:
        out.append(f"prop {p} err: {e}")

# Check all fields in struct or object
for f in dir(lyr0):
    if not f.startswith("_"):
        try:
            val = getattr(lyr0, f)
            out.append(f"field {f} = {val}")
        except Exception:
            pass

with open("D:/yacs/project/worldgen/houdini/sa_calobra/lyr0_props.txt", "w") as f:
    f.write("\n".join(out))

unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
