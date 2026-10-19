import unreal

doc = []
doc.append("=== HoudiniPublicAPIInputWrapper ===")
for m in dir(unreal.HoudiniPublicAPIInputWrapper):
    if not m.startswith("_"):
        doc.append(f"  {m}")

with open("D:/yacs/project/worldgen/houdini/sa_calobra/input_wrapper_api.txt", "w") as f:
    f.write("\n".join(doc))

unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
