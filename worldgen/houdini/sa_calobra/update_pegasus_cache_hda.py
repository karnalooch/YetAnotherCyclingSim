import hou

project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
hda_path = f"{project_dir}/otls/sop_PE_Cache_Landscape.hda"
hou.hda.installFile(hda_path)

hda_def = hou.nodeType(hou.sopNodeTypeCategory(), "PE_Cache_Landscape").definition()
ptg = hda_def.parmTemplateGroup()

btn_exec = ptg.find("execute")
callback_code = """import traceback
log_path = "D:/yacs/project/worldgen/houdini/sa_calobra/cache_button_debug.txt"
with open(log_path, "w") as f:
    f.write("=== EXECUTE CALLBACK CALLED ===\\n")
    try:
        node = hou.pwd()
        f.write(f"Node: {node.path()}\\n")
        file_path = node.parm("file").eval()
        f.write(f"file_path: {file_path}\\n")
        
        # Check UNREAL_INPUTS
        u = node.node("UNREAL_INPUTS")
        f.write(f"UNREAL_INPUTS node: {u}\\n")
        if u:
            f.write(f"UNREAL_INPUTS errors: {u.errors()}\\n")
            f.write(f"UNREAL_INPUTS warnings: {u.warnings()}\\n")
            u_geo = u.geometry()
            f.write(f"UNREAL_INPUTS geo: {u_geo}\\n")
            if u_geo:
                f.write(f"UNREAL_INPUTS prims count: {len(u_geo.prims())}\\n")
                for p in u_geo.prims():
                    f.write(f"  Prim: type={p.type().name()}, num={p.number()}\\n")
                    for a in p.intrinsicValueDict():
                        if "name" in a or "volume" in a:
                            f.write(f"    intrinsic {a}: {p.intrinsicValue(a)}\\n")
                    if p.type() == hou.primType.Volume:
                        f.write(f"    volume name: {p.attribValue('name') if u_geo.findPrimAttrib('name') else 'no name attr'}\\n")
        
        # Check blast1
        b1 = node.node("blast1")
        if b1:
            f.write(f"blast1 errors: {b1.errors()}\\n")
            b_geo = b1.geometry()
            if b_geo:
                f.write(f"blast1 prims count: {len(b_geo.prims())}\\n")
                for p in b_geo.prims():
                    f.write(f"  blast1 prim name: {p.attribValue('name') if b_geo.findPrimAttrib('name') else 'none'}\\n")
        
        # Check Layer1_Manual
        l1 = node.node("Layer1_Manual")
        f.write(f"Layer1_Manual node: {l1}\\n")
        if l1:
            f.write(f"Layer1_Manual errors: {l1.errors()}\\n")
            f.write(f"Layer1_Manual warnings: {l1.warnings()}\\n")
            geo = l1.geometry()
            if geo:
                f.write(f"Layer1_Manual Prims count: {len(geo.prims())}\\n")
                geo.saveToFile(file_path)
                f.write(f"SUCCESS: saved to {file_path}\\n")
            else:
                f.write("Layer1_Manual geometry is None!\\n")
    except Exception as e:
        f.write(f"EXCEPTION: {traceback.format_exc()}\\n")
"""
btn_exec.setScriptCallback(callback_code)
btn_exec.setScriptCallbackLanguage(hou.scriptLanguage.Python)
ptg.replace("execute", btn_exec)

hda_def.setParmTemplateGroup(ptg)
hda_def.save(hda_path)
print("Successfully updated PE_Cache_Landscape HDA definition!")
