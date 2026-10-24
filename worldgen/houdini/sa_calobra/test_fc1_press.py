import hou, os

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda"]:
    hou.hda.installFile(f"{project_dir}/otls/{hda}")

geo = hou.node("/obj").createNode("geo")
hf = geo.createNode("heightfield")
stage = geo.createNode("PE_Cache_Landscape")
stage.setInput(0, hf)

target_file = "D:/yacs/project/worldgen/houdini/sa_calobra/cache/test_press_button.bgeo.sc"
stage.parm("file").set(target_file)
fc1 = stage.node("filecache1")
print(f"fc1 file evaluates to: {fc1.parm('file').eval()}")

print("Pressing execute on fc1...")
fc1.parm("execute").pressButton()
print("Done pressing execute.")

exists = os.path.exists(target_file)
print("File exists on disk:", exists)
if exists:
    size = os.path.getsize(target_file)
    print(f"File size: {size} bytes")
    os.remove(target_file)
