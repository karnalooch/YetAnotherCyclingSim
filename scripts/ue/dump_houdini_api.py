import unreal

out = []
out.append("=== HoudiniPublicAPIAssetWrapper ===")
for m in dir(unreal.HoudiniPublicAPIAssetWrapper):
    if not m.startswith("_"):
        out.append(f"  {m}")

out.append("\n=== HoudiniAssetComponent ===")
for m in dir(unreal.HoudiniAssetComponent):
    if not m.startswith("_"):
        out.append(f"  {m}")

out.append("\n=== HoudiniAssetActor ===")
for m in dir(unreal.HoudiniAssetActor):
    if not m.startswith("_"):
        out.append(f"  {m}")

with open("D:/yacs/project/worldgen/houdini/sa_calobra/houdini_wrapper_api.txt", "w") as f:
    f.write("\n".join(out))

unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
