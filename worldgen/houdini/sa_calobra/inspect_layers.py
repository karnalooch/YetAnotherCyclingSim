import hou

layers_dir = "D:/yacs/project/worldgen/houdini/sa_calobra/Pegasus/Landscape/Landscape Heightfield Layers"
files = {
    "Source": f"{layers_dir}/Pegasus_Landscape_Later_1_Source.bgeo.sc",
    "Manual": f"{layers_dir}/Pegasus_Landscape_Layer_2_Manual_Edits.bgeo.sc",
    "Procedural": f"{layers_dir}/Pegasus_Landscape_Layer_3_Procedural_Detail.bgeo.sc"
}

for name, fpath in files.items():
    print(f"\n=== LAYER: {name} ===")
    geo = hou.Geometry()
    try:
        geo.loadFromFile(fpath)
        print(f"File: {fpath}")
        print(f"Prims: {len(geo.prims())}")
        for p in geo.prims():
            if p.type() == hou.primType.Volume:
                vname = p.attribValue('name')
                res = p.resolution()
                bounds = p.boundingBox()
                print(f"  Volume '{vname}': res={res}, min={p.volumeMin():.4f}, max={p.volumeMax():.4f}, bounds={bounds.minvec()} -> {bounds.maxvec()}")
    except Exception as e:
        print(f"Error loading {fpath}: {e}")
