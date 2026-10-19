import hou

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda"]:
    hou.hda.installFile(f"{project_dir}/otls/{hda}")

hip_file = f"{project_dir}/SaCalobra_Pegasus_Lesson02.hiplc"
hou.hipFile.load(hip_file, suppress_save_prompt=True, ignore_load_warnings=True)

overview = hou.node("/obj/PEGASUS_PIPELINE_OVERVIEW")
u_load = overview.node("Unreal_Load_Landscape")

for layer_idx, layer_name in [(0, "Layer 1 Source"), (1, "Layer 2 Manual"), (2, "Layer 3 Procedural")]:
    u_load.parm("input7").set(layer_idx)
    u_load.cook(force=True)
    geo = u_load.geometry()
    h_prim = [p for p in geo.prims() if p.attribValue("name") == "height"][0]
    edit_layer = geo.findPrimAttrib("unreal_landscape_editlayer_name")
    el_val = h_prim.attribValue("unreal_landscape_editlayer_name") if edit_layer else "None"
    mode_val = h_prim.attribValue("unreal_landscape_output_mode") if geo.findPrimAttrib("unreal_landscape_output_mode") else "None"
    print(f"input7={layer_idx} ({layer_name}):")
    print(f"  unreal_landscape_editlayer_name = {el_val}")
    print(f"  unreal_landscape_output_mode = {mode_val}")
    print(f"  height min={h_prim.volumeMin():.4f}, max={h_prim.volumeMax():.4f}")
