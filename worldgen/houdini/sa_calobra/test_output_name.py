import hou

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
hou.hda.installFile(f"{project_dir}/otls/sop_PE_Load_Landscape.2.hda")

geo = hou.node("/obj").createNode("geo")
node = geo.createNode("PE_Load_Landscape::2")
node.parm("environment").set(0) # Unreal
node.parm("dir").set(project_dir)
node.parm("mode").set(1)

# Default: should evaluate to Landscape
node.cook(force=True)
p_out = node.geometry().prims()[0].attribValue("unreal_output_name")
print("Default unreal_output_name:", p_out)

# Set to SaCalobra_Detail_0_0
node.parm("output_name").set("SaCalobra_Detail_0_0")
node.cook(force=True)
p_out2 = node.geometry().prims()[0].attribValue("unreal_output_name")
print("Custom unreal_output_name:", p_out2)
