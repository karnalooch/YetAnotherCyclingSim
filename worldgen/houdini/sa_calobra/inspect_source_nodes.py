import hou

hou.hipFile.load("worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson06_Reviewed.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
geo = hou.node("/obj/SA_CALOBRA")

nodes_to_inspect = [
    "SOURCE_VALIDITY", "SOURCE_CACHE", "CONTEXT_SOURCE_CACHE", "TRANSFER_MASK_TO_SOURCE_GRID",
    "BUILD_CONTEXT_GRID", "BUILD_CONTEXT_VALIDITY", "CONTEXT_SOURCE_BUILD_CACHE"
]

for name in nodes_to_inspect:
    n = geo.node(name)
    if n:
        print(f"=== Node {name} ({n.type().name()}) ===")
        for p in n.parms():
            if not p.isAtDefault() or p.name() in ['filename', 'file', 'sizemethod', 'gridspacing', 'size', 'sampling', 'rows', 'cols']:
                print(f"  {p.name()} = {p.eval()}")
