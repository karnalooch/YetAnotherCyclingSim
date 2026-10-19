import hou

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
hda_path = f"{project_dir}/otls/sop_PE_Load_Landscape.2.hda"
hou.hda.installFile(hda_path)

geo = hou.node("/obj").createNode("geo")
node = geo.createNode("PE_Load_Landscape::2")
node.allowEditingOfContents()

# In attribcreate1:
ac1 = node.node("attribcreate1")
expr = '`ifs(strcmp(chs("../output_name"), "") == 0, "Landscape", chs("../output_name"))`'
ac1.parm("string1").set(expr)
print("Set ac1 string1 to:", ac1.parm("string1").unexpandedString())

node.type().definition().updateFromNode(node)
print("Updated HDA definition from node!")
geo.destroy()
