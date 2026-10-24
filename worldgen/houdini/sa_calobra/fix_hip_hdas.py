import hou, os

project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
otls_dir = f"{project_dir}/otls"
hip_file = f"{project_dir}/SaCalobra_Pegasus_Lesson02.hiplc"

# Install SideFX Labs
hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")

# Install project HDAs
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda", "sop_PE_Heightfield_Layers_to_ID.2.0.hda", "sop_PE_heightfield_material.1.0.hda"]:
    hda_path = f"{otls_dir}/{hda}"
    if os.path.exists(hda_path):
        hou.hda.installFile(hda_path, force_use_assets=True)
        print("Installed:", hda_path)

hou.hipFile.load(hip_file, suppress_save_prompt=True, ignore_load_warnings=True)

# Check installed files and uninstall any non-project HDA
for f in hou.hda.loadedFiles():
    if "OneDrive" in f or "sa-calobra-houdini-unreal" in f:
        print("Uninstalling rogue HDA path:", f)
        try:
            hou.hda.uninstallFile(f)
        except Exception as e:
            print("  error uninstalling:", e)

# Reinstall project HDAs to ensure they take precedence
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda", "sop_PE_Heightfield_Layers_to_ID.2.0.hda", "sop_PE_heightfield_material.1.0.hda"]:
    hda_path = f"{otls_dir}/{hda}"
    if os.path.exists(hda_path):
        hou.hda.installFile(hda_path, force_use_assets=True)

overview = hou.node("/obj/PEGASUS_PIPELINE_OVERVIEW")
u_load = overview.node("Unreal_Load_Landscape")
h_load = overview.node("Houdini_Load_Landscape")

u_load.matchCurrentDefinition()
h_load.matchCurrentDefinition()

print("\n--- After matchCurrentDefinition ---")
print("u_load def path:", u_load.type().definition().libraryFilePath())
print("u_load has output_name:", u_load.parm("output_name") is not None)
print("h_load def path:", h_load.type().definition().libraryFilePath())
print("h_load has output_name:", h_load.parm("output_name") is not None)

# Set portable dir paths
for node in [u_load, h_load]:
    p_dir = node.parm("dir")
    if p_dir:
        p_dir.set("$HIP")
        print(f"Set {node.name()} dir to:", p_dir.unexpandedString())

hou.hipFile.save()
print("\nSaved HIP file successfully!")
