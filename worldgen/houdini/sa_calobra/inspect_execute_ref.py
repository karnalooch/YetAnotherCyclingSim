import hou

hou.hda.installFile("D:/yacs/project/worldgen/houdini/sa_calobra/otls/sop_PE_Cache_Landscape.hda")
stage = hou.node("/obj").createNode("geo").createNode("PE_Cache_Landscape")
fc1 = stage.node("filecache1")

print("filecache1 parms referencing parent:")
for p in fc1.parms():
    try:
        raw = p.unexpandedString()
        if ".." in raw:
            print(f"  {p.name()} = {raw}")
    except Exception:
        pass

# Check if there are any other nodes in PE_Cache_Landscape referencing execute
print("\nAll nodes in PE_Cache_Landscape referencing execute:")
for c in stage.children():
    for p in c.parms():
        try:
            raw = p.unexpandedString()
            if "execute" in raw or "execute" in p.name():
                print(f"  {c.name()}.{p.name()} = {raw} (eval: {p.eval()})")
        except Exception:
            pass
