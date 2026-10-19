import hou

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda"]:
    hou.hda.installFile(f"{project_dir}/otls/{hda}")

stage = hou.node("/obj").createNode("geo").createNode("PE_Cache_Landscape")

l1 = stage.node("Layer1_Manual")
print("=== Layer1_Manual Parms ===")
for p in l1.parms():
    try:
        print(f"  {p.name()} = {p.eval()}")
    except Exception as e:
        print(f"  {p.name()}: {e}")

b1 = stage.node("blast1")
print("\n=== blast1 Parms ===")
for p in b1.parms():
    print(f"  {p.name()} = {p.eval()}")

fc1 = stage.node("filecache1")
print("\n=== filecache1 Parms ===")
for p in fc1.parms():
    if any(k in p.name() for k in ["load", "mode", "file", "execute"]):
        print(f"  {p.name()} = {p.eval()}")
