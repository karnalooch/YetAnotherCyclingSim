import hou

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda"]:
    hou.hda.installFile(f"{project_dir}/otls/{hda}")

hip_file = f"{project_dir}/SaCalobra_Pegasus_Lesson02.hiplc"
hou.hipFile.load(hip_file, suppress_save_prompt=True, ignore_load_warnings=True)

overview = hou.node("/obj/PEGASUS_PIPELINE_OVERVIEW")
h_load = overview.node("Houdini_Load_Landscape")

configs = [
    ("Source Only", 1, 0, 0),
    ("Source + Manual", 1, 1, 0),
    ("Source + Manual + Procedural", 1, 1, 1)
]

for name, l1, l2, l3 in configs:
    h_load.parm("input4").set(l1)
    h_load.parm("input5").set(l2)
    h_load.parm("input6").set(l3)
    h_load.cook(force=True)
    geo = h_load.geometry()
    h_prim = [p for p in geo.prims() if p.attribValue("name") == "height"][0]
    print(f"Config '{name}' (toggles: {l1}, {l2}, {l3}):")
    print(f"  height min={h_prim.volumeMin():.4f}, max={h_prim.volumeMax():.4f}, avg={h_prim.volumeAverage():.4f}")
