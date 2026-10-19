import hou, time, os, psutil

proc = psutil.Process()
print("Initial memory MB:", proc.memory_info().rss / 1e6)

t0 = time.time()
hou.hipFile.load("worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson06_Reviewed.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
print(f"HIP loaded in {time.time()-t0:.2f}s, memory MB: {proc.memory_info().rss / 1e6}")

geo = hou.node("/obj/PEGASUS_DETAIL_SOURCE")
dtm_node = geo.node("READ_REAL_DTM")
print("dtm_node filename:", dtm_node.parm("filename").eval())
t0 = time.time()
g = dtm_node.geometry()
print(f"READ_REAL_DTM cooked in {time.time()-t0:.2f}s, memory MB: {proc.memory_info().rss / 1e6}")
for p in g.prims():
    if isinstance(p, hou.Volume):
        print(f"  Volume {p.attribValue('name')} res={p.resolution()}")

geo_axes = geo.node("GEOGRAPHIC_AXES")
t0 = time.time()
g_axes = geo_axes.geometry()
print(f"GEOGRAPHIC_AXES cooked in {time.time()-t0:.2f}s, memory MB: {proc.memory_info().rss / 1e6}")
for p in g_axes.prims():
    if isinstance(p, hou.Volume):
        print(f"  Volume {p.attribValue('name')} res={p.resolution()} origin={p.indexToPos((0,0,0))}")
