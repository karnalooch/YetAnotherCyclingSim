import unreal

out = []
out.append("=== LandscapeCircleHeightPatch ===")
for m in dir(unreal.LandscapeCircleHeightPatch):
    if not m.startswith("_"):
        out.append(f"  {m}")

out.append("\n=== LandscapeEditLayer ===")
for m in dir(unreal.LandscapeEditLayer):
    if not m.startswith("_"):
        out.append(f"  {m}")

out.append("\n=== LandscapeEditLayerBase ===")
for m in dir(unreal.LandscapeEditLayerBase):
    if not m.startswith("_"):
        out.append(f"  {m}")

with open("D:/yacs/project/worldgen/houdini/sa_calobra/inspect_layer_classes.txt", "w") as f:
    f.write("\n".join(out))

print("Wrote inspect_layer_classes.txt")
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
