import hou

project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
hip_file = f"{project_dir}/SaCalobra_Pegasus_Lesson02.hiplc"
hou.hipFile.load(hip_file, suppress_save_prompt=True, ignore_load_warnings=True)

overview = hou.node("/obj/PEGASUS_PIPELINE_OVERVIEW")
print("=== PEGASUS_PIPELINE_OVERVIEW NODES ===")
for c in overview.children():
    inputs = [i.name() if i else "None" for i in c.inputs()]
    print(f"Node: {c.name()} ({c.type().name()}), Inputs: {inputs}")

sa = hou.node("/obj/SA_CALOBRA")
if sa:
    print("\n=== SA_CALOBRA NODES ===")
    for c in sa.children():
        inputs = [i.name() if i else "None" for i in c.inputs()]
        print(f"Node: {c.name()} ({c.type().name()}), Inputs: {inputs}")
