import hou

project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
fpath = f"{project_dir}/Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Later_1_Source.bgeo.sc"
geo = hou.Geometry()
geo.loadFromFile(fpath)

prim = [p for p in geo.prims() if p.attribValue("name") == "height"][0]
res = prim.resolution()
bbox = prim.boundingBox()
size = bbox.sizevec()
pos = bbox.center()
print("=== HOUDINI HEIGHTFIELD ===")
print(f"Resolution: {res}")
print(f"BBox: {bbox.minvec()} -> {bbox.maxvec()}")
print(f"Size: {size}")
print(f"Center: {pos}")
print(f"Voxel size: x={size[0]/res[0]:.4f}, z={size[2]/res[1]:.4f}")

# Check SA_CALOBRA source nodes
hip_file = f"{project_dir}/SaCalobra_Pegasus_Lesson02.hiplc"
hou.hipFile.load(hip_file, suppress_save_prompt=True, ignore_load_warnings=True)
crop = hou.node("/obj/SA_CALOBRA/CROP_WORKING_BOUNDS")
if crop:
    print("\nCROP_WORKING_BOUNDS parms:")
    for p in crop.parms():
        if any(k in p.name() for k in ["size", "center", "min", "max"]):
            print(f"  {p.name()} = {p.eval()}")
