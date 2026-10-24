import unreal

patch = unreal.new_object(unreal.LandscapeCircleHeightPatch)
out = []
for p in dir(patch):
    if not p.startswith("_"):
        try:
            val = getattr(patch, p)
            if not callable(val):
                out.append(f"{p} = {val}")
        except Exception:
            pass

with open("D:/yacs/project/worldgen/houdini/sa_calobra/circle_patch_props.txt", "w") as f:
    f.write("\n".join(out))

unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
