import hou

hou.hda.installFile("D:/yacs/project/worldgen/houdini/sa_calobra/otls/sop_PE_Cache_Landscape.hda")
hda_def = hou.nodeType(hou.sopNodeTypeCategory(), "PE_Cache_Landscape").definition()

ptg = hda_def.parmTemplateGroup()
btn = ptg.find("execute")
print("Button 'execute' script callback:", btn.scriptCallback())
print("Button 'execute' script language:", btn.scriptCallbackLanguage())

btn2 = ptg.find("execute2")
print("Button 'execute2' script callback:", btn2.scriptCallback())
print("Button 'execute2' script language:", btn2.scriptCallbackLanguage())

# Also check scripts section of HDA definition
print("\nHDA Sections:")
for s in hda_def.sections():
    if "script" in s.lower() or "event" in s.lower() or "python" in s.lower() or "callback" in s.lower():
        print(f"  section: {s}")
