import unreal

doc = unreal.HoudiniPublicAPIAssetWrapper.process_component_synchronous.__doc__
print("Doc:", doc)

with open("D:/yacs/project/worldgen/houdini/sa_calobra/proc_sync_doc.txt", "w") as f:
    f.write(str(doc))

unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
