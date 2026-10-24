import hou

hda_cache_path = "D:/yacs/project/worldgen/houdini/sa_calobra/otls/sop_PE_Cache_Landscape.hda"
hda_load_path = "D:/yacs/project/worldgen/houdini/sa_calobra/otls/sop_PE_Load_Landscape.2.hda"

hou.hda.installFile(hda_cache_path)
hou.hda.installFile(hda_load_path)

print("=== PE_Cache_Landscape INSPECTION ===")
def_cache = hou.nodeType(hou.sopNodeTypeCategory(), "PE_Cache_Landscape").definition()
print("Parameters of PE_Cache_Landscape:")
for pt in def_cache.parmTemplateGroup().parmTemplates():
    print(f"  {pt.name()} ({pt.type().name()}): {pt.label()}")

# Create a dummy node to inspect children
stage = hou.node("/obj").createNode("geo").createNode("PE_Cache_Landscape")
print("\nInternal nodes of PE_Cache_Landscape:")
for child in stage.children():
    print(f"  {child.name()} ({child.type().name()})")
    if child.type().name() in ["rop_geometry", "geometry"]:
        for p in child.parms():
            if "sopoutput" in p.name() or "execute" in p.name():
                print(f"    {p.name()} = {p.rawValue()}")

print("\n=== PE_Load_Landscape::2 INSPECTION ===")
def_load = hou.nodeType(hou.sopNodeTypeCategory(), "PE_Load_Landscape::2").definition()
print("Parameters of PE_Load_Landscape::2:")
for pt in def_load.parmTemplateGroup().parmTemplates():
    print(f"  {pt.name()} ({pt.type().name()}): {pt.label()}")

stage2 = hou.node("/obj").createNode("geo").createNode("PE_Load_Landscape::2")
print("\nInternal nodes of PE_Load_Landscape::2:")
for child in stage2.children():
    print(f"  {child.name()} ({child.type().name()})")
