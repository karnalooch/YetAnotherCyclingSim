import hou

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda"]:
    hou.hda.installFile(f"{project_dir}/otls/{hda}")

hda_def = hou.nodeType(hou.sopNodeTypeCategory(), "PE_Load_Landscape::2").definition()
ptg = hda_def.parmTemplateGroup()

for p in ptg.parmTemplates():
    print(f"{p.name()} ({p.type().name()}): {p.label()}")

# Check where mode and input7 are
print("\nEntries inside folder1:")
folder1 = ptg.find("folder1")
if folder1:
    for sp in folder1.parmTemplates():
        print(f"  {sp.name()} ({sp.type().name()}): {sp.label()}")
