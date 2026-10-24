import hou, os

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda"]:
    hou.hda.installFile(f"{project_dir}/otls/{hda}")

geo = hou.node("/obj").createNode("geo")
hf = geo.createNode("heightfield")
wrangle = geo.createNode("attribwrangle")
wrangle.setInput(0, hf)
wrangle.parm("class").set(1) # Primitives
wrangle.parm("snippet").set("s@name = 'landscapelayer_Layer1_Manual';")

stage = geo.createNode("PE_Cache_Landscape")
stage.setInput(0, wrangle)

target_file = "D:/yacs/project/worldgen/houdini/sa_calobra/cache/test_press_execute.bgeo.sc"
stage.parm("file").set(target_file)

print("Pressing execute button on stage...")
stage.parm("execute").pressButton()

exists = os.path.exists(target_file)
print("File exists on disk:", exists)
if exists:
    size = os.path.getsize(target_file)
    print(f"File size: {size} bytes")
    os.remove(target_file)
    print("Test passed! PE_Cache_Landscape execute button works perfectly.")
