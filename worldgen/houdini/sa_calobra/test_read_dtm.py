import os
os.environ["HOUDINI_COP_MAXRES"] = "32768"
import hou, time

hou.hipFile.load("worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson06_Reviewed.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
node = hou.node("/obj/PEGASUS_DETAIL_SOURCE/READ_REAL_DTM")
node.parm("filename").set("D:/yacs/work/sa-calobra-houdini-unreal-20261016/inputs/dtm_height_float32.tif")

t0 = time.time()
print("Cooking READ_REAL_DTM with HOUDINI_COP_MAXRES=32768...")
node.cook(force=True)
print(f"Cooked in {time.time()-t0:.2f}s, errors: {node.errors()}")
g = node.geometry()
print("Geometry:", g)
if g:
    for p in g.prims():
        if isinstance(p, hou.Volume):
            print(f"  Volume: {p.attribValue('name')} res={p.resolution()} bounds min={p.boundingBox().minvec()} max={p.boundingBox().maxvec()}")
