import hou

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda", "sop_PE_Heightfield_Layers_to_ID.2.0.hda", "sop_PE_heightfield_material.1.0.hda"]:
    hou.hda.installFile(f"{project_dir}/otls/{hda}")

hip_file = f"{project_dir}/SaCalobra_Pegasus_Lesson02.hiplc"
hou.hipFile.load(hip_file, suppress_save_prompt=True, ignore_load_warnings=True)

overview = hou.node("/obj/PEGASUS_PIPELINE_OVERVIEW")
u_load = overview.node("Unreal_Load_Landscape")

ac1 = u_load.node("attribcreate1")
for p in ac1.parms():
    if p.name().startswith("string") or p.name().startswith("name"):
        print(f"ac1 {p.name()} = {p.unexpandedString()} -> {p.eval()}")

# Check all internal nodes that reference parent parameters ch("..")
print("\nInternal nodes referencing parent parms:")
for c in u_load.children():
    for p in c.parms():
        try:
            raw = p.unexpandedString()
            if ".." in raw:
                print(f"  {c.name()}.{p.name()} = {raw}")
        except Exception:
            pass
