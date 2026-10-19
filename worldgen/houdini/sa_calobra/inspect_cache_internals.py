import hou

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda"]:
    hou.hda.installFile(f"{project_dir}/otls/{hda}")

stage = hou.node("/obj").createNode("geo").createNode("PE_Cache_Landscape")

print("=== PE_Cache_Landscape Internal Nodes ===")
for c in stage.children():
    inputs = [i.name() if i else "None" for i in c.inputs()]
    print(f"\nNode: {c.name()} ({c.type().name()}), Inputs: {inputs}")
    for p in c.parms():
        try:
            val = p.eval()
            raw = p.unexpandedString()
            if any(k in p.name() for k in ["group", "sopoutput", "file", "execute", "input", "operation", "source", "name"]):
                print(f"  {p.name()} = {val} (raw: {raw})")
        except Exception:
            pass
