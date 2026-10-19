import hou

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda"]:
    hou.hda.installFile(f"{project_dir}/otls/{hda}")

stage = hou.node("/obj").createNode("geo").createNode("PE_Load_Landscape::2")
ac1 = stage.node("attribcreate1")
print("ac1 string1:", ac1.parm("string1").unexpandedString())
print("ac1 name1:", ac1.parm("name1").unexpandedString())

# Check all attribcreates in PE_Load_Landscape::2
for c in stage.children():
    if "attribcreate" in c.type().name():
        print(f"\n{c.name()}:")
        for p in c.parms():
            if p.name().startswith("name") or p.name().startswith("string") or p.name().startswith("value"):
                try:
                    print(f"  {p.name()} = {p.eval()} ({p.unexpandedString()})")
                except Exception:
                    pass
