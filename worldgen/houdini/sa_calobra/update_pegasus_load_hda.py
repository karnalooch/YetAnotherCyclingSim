import hou

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
hda_path = f"{project_dir}/otls/sop_PE_Load_Landscape.2.hda"
hou.hda.installFile(hda_path)

hda_def = hou.nodeType(hou.sopNodeTypeCategory(), "PE_Load_Landscape::2").definition()
ptg = hda_def.parmTemplateGroup()

# Add output_name parameter if not already present
if not ptg.find("output_name"):
    p_out = hou.StringParmTemplate("output_name", "Target Landscape Actor", 1, default_value=(["Landscape"]))
    ptg.insertBefore("mode", p_out)
    hda_def.setParmTemplateGroup(ptg)

# Now update the internal attribcreate1 node
# Create a dummy instance to update definition contents
geo = hou.node("/obj").createNode("geo")
node = geo.createNode("PE_Load_Landscape::2")
node.allowEditingOfContents()

ac1 = node.node("attribcreate1")
ac1.parm("string1").set('`ifs(strcmp(chs("../output_name"), ""), "Landscape", chs("../output_name"))`')

# Save contents back to definition
hda_def.save(hda_path, node)
geo.destroy()
print("Successfully updated PE_Load_Landscape::2 HDA definition with output_name support!")
