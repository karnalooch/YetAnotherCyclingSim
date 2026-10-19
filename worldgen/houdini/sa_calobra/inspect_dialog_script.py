import hou

hou.hda.installFile("D:/yacs/project/worldgen/houdini/sa_calobra/otls/sop_PE_Cache_Landscape.hda")
hda_def = hou.nodeType(hou.sopNodeTypeCategory(), "PE_Cache_Landscape").definition()

dialog_script = hda_def.sections()["DialogScript"].contents()
print("=== DialogScript ===")
print(dialog_script[:2000])
