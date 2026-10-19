from pathlib import Path
import OpenImageIO as oi
import hou

dtm_path = Path("D:/yacs/work/sa-calobra-houdini-unreal-20261016/inputs/dtm_height_float32.tif")
val_path = Path("D:/yacs/work/sa-calobra-houdini-unreal-20261016/inputs/dtm_validity.tif")

f = oi.ImageInput.open(str(dtm_path))
if f:
    spec = f.spec()
    print("=== DTM Raster Metadata (OIIO) ===")
    print("Width, Height, Channels:", spec.width, spec.height, spec.nchannels)
    print("Format:", spec.format)
    f.close()

f = oi.ImageInput.open(str(val_path))
if f:
    spec = f.spec()
    print("=== Validity Raster Metadata (OIIO) ===")
    print("Width, Height, Channels:", spec.width, spec.height, spec.nchannels)
    f.close()

# Let's inspect Houdini SOURCE_CACHE
hou.hipFile.load("worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson06_Reviewed.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
geo = hou.node("/obj/SA_CALOBRA")
sc = geo.node("SOURCE_CACHE").geometry()
csc = geo.node("CONTEXT_SOURCE_CACHE").geometry()

def get_vol_info(g, name):
    for p in g.prims():
        if isinstance(p, hou.Volume) and p.attribValue("name") == name:
            res = p.resolution()
            bb = p.boundingBox()
            o = p.indexToPos((0,0,0))
            vx = p.indexToPos((1,0,0)) - o
            vy = p.indexToPos((0,1,0)) - o
            return {"res": res, "bbox_min": list(bb.minvec()), "bbox_max": list(bb.maxvec()), "origin": list(o), "vx": list(vx), "vy": list(vy)}
    return None

print("=== Houdini Working SOURCE_CACHE (height) ===")
print(get_vol_info(sc, "height"))
print("=== Houdini Context CONTEXT_SOURCE_CACHE (height) ===")
print(get_vol_info(csc, "height"))
