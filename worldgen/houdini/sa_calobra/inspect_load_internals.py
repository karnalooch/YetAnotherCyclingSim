import hou

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda", "sop_PE_Heightfield_Layers_to_ID.2.0.hda", "sop_PE_heightfield_material.1.0.hda"]:
    hou.hda.installFile(f"{project_dir}/otls/{hda}")

hip_file = f"{project_dir}/SaCalobra_Pegasus_Lesson02.hiplc"
hou.hipFile.load(hip_file, suppress_save_prompt=True, ignore_load_warnings=True)

overview = hou.node("/obj/PEGASUS_PIPELINE_OVERVIEW")
u_load = overview.node("Unreal_Load_Landscape")

print("Children of Unreal_Load_Landscape:")
for c in u_load.children():
    print(f"  {c.name()} ({c.type().name()})")
    if "attrib" in c.type().name() or "unreal" in c.name().lower() or "switch" in c.type().name():
        for p in c.parms():
            if p.name() in ["name1", "string1", "attribname", "value", "index", "select"]:
                print(f"    {p.name()} = {p.eval()}")

# Let's inspect the wrangles or python nodes in u_load
for c in u_load.children():
    if c.type().name() in ["attribwrangle", "python", "attribcreate::2.0", "attribcreate"]:
        print(f"\nNode {c.name()}:")
        for p in c.parms():
            if p.name() in ["snippet", "python", "name1", "string1", "name2", "string2"]:
                print(f"  {p.name()}:\n{p.eval()}")
