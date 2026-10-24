import hou

hou.hda.installFile("D:/yacs/project/worldgen/houdini/sa_calobra/otls/sop_PE_Cache_Landscape.hda")
hda_def = hou.nodeType(hou.sopNodeTypeCategory(), "PE_Cache_Landscape").definition()
print("Editable nodes:", hda_def.editableNodes())
