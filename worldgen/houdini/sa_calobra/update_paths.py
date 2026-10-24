import hou

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda", "sop_PE_Heightfield_Layers_to_ID.2.0.hda", "sop_PE_heightfield_material.1.0.hda"]:
    hou.hda.installFile(f"{project_dir}/otls/{hda}")

hip_file = f"{project_dir}/SaCalobra_Pegasus_Lesson02.hiplc"
hou.hipFile.load(hip_file, suppress_save_prompt=True, ignore_load_warnings=True)

print("HIP loaded. $HIP is:", hou.hscriptExpression("$HIP"))

# Inspect PEGASUS_PIPELINE_OVERVIEW nodes
overview = hou.node("/obj/PEGASUS_PIPELINE_OVERVIEW")
if overview:
    for child in overview.children():
        print(f"Overview node: {child.name()} ({child.type().name()})")
        for p in child.parms():
            if p.parmTemplate().type() == hou.parmTemplateType.String:
                val = p.unexpandedString()
                if "yacs" in val or "work" in val or "dir" in p.name() or "file" in p.name():
                    print(f"  {p.name()} = {val}")

# Update paths to use $HIP
h_load = overview.node("Houdini_Load_Landscape")
if h_load:
    h_load.parm("dir").set("$HIP")
    print("Updated Houdini_Load_Landscape dir -> $HIP (evals to:", h_load.parm("dir").eval(), ")")

u_load = overview.node("Unreal_Load_Landscape")
if u_load:
    u_load.parm("dir").set("$HIP")
    print("Updated Unreal_Load_Landscape dir -> $HIP (evals to:", u_load.parm("dir").eval(), ")")

u_cache = overview.node("Unreal_Cache_Landscape")
if u_cache:
    u_cache.parm("file").set("$HIP/Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Layer_2_Manual_Edits.bgeo.sc")
    u_cache.parm("file2").set("$HIP/Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Layers.bgeo.sc")
    print("Updated Unreal_Cache_Landscape file ->", u_cache.parm("file").eval())

# Check SA_CALOBRA filecaches
sa = hou.node("/obj/SA_CALOBRA")
if sa:
    for c in sa.children():
        if c.type().name() in ["filecache", "filecache::2.0", "file"]:
            for p in c.parms():
                if p.name() in ["file", "basedir"]:
                    print(f"  SA_CALOBRA {c.name()}.{p.name()} = {p.unexpandedString()} -> {p.eval()}")

# Save updated HIP
hou.hipFile.save(hip_file)
print("Saved updated HIP to:", hip_file)

# Cook test
h_load.cook(force=True)
print("Houdini_Load_Landscape errors:", h_load.errors())
p = [p for p in h_load.geometry().prims() if p.attribValue('name') == 'height'][0]
print(f"Cooked heightfield volume: min={p.volumeMin():.4f}, max={p.volumeMax():.4f}, avg={p.volumeAverage():.4f}")

