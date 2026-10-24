import unreal

with open("D:/yacs/project/worldgen/houdini/sa_calobra/ue_landscape_classes.txt", "w") as f:
    for m in dir(unreal):
        if "landscape" in m.lower():
            f.write(f"{m}\n")

unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
