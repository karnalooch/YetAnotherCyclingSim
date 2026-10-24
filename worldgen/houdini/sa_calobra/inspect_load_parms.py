import hou

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda"]:
    hou.hda.installFile(f"{project_dir}/otls/{hda}")

stage = hou.node("/obj").createNode("geo").createNode("PE_Load_Landscape::2")

print("=== PE_Load_Landscape::2 Parameter Labels ===")
for pt in stage.parmTemplateGroup().parmTemplates():
    print(f"{pt.name()} ({pt.type().name()}): '{pt.label()}'")
    if hasattr(pt, "menuItems"):
        print(f"   menu items: {pt.menuItems()}, labels: {pt.menuLabels()}")

# Check all parameters including nested
for p in stage.parms():
    pt = p.parmTemplate()
    if pt.type() != hou.parmTemplateType.FolderSet and pt.type() != hou.parmTemplateType.Folder:
        print(f"  {p.name()} = {p.eval()} ({pt.label()})")
