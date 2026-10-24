import hou

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda", "sop_PE_Heightfield_Layers_to_ID.2.0.hda", "sop_PE_heightfield_material.1.0.hda"]:
    hou.hda.installFile(f"{project_dir}/otls/{hda}")

hip_file = f"{project_dir}/SaCalobra_Pegasus_Lesson02.hiplc"
hou.hipFile.load(hip_file, suppress_save_prompt=True, ignore_load_warnings=True)

overview = hou.node("/obj/PEGASUS_PIPELINE_OVERVIEW")
u_load = overview.node("Unreal_Load_Landscape")
print("=== All parameters on Unreal_Load_Landscape ===")
for p in u_load.parms():
    try:
        print(f"  {p.name()} ({p.parmTemplate().type().name()}): {p.eval()}")
    except Exception as e:
        print(f"  {p.name()}: error {e}")

print("\n=== Cooking Unreal_Load_Landscape ===")
u_load.cook(force=True)
geo = u_load.geometry()
print("Primitives count:", len(geo.prims()))
for prim in geo.prims():
    if prim.type() == hou.primType.Volume:
        print(f"Volume: {prim.attribValue('name')}, min={prim.volumeMin():.3f}, max={prim.volumeMax():.3f}")

print("\nDetail attributes:")
for a in geo.globalAttribs():
    val = geo.attribValue(a.name())
    print(f"  {a.name()} = {val}")

print("\nPrim attributes:")
for a in geo.primAttribs():
    print(f"  prim attrib: {a.name()}")
    for prim in geo.prims():
        if prim.type() == hou.primType.Volume:
            print(f"    prim {prim.attribValue('name')}: {prim.attribValue(a.name())}")
