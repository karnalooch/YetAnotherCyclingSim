import os
os.environ["HOUDINI_COP_MAXRES"] = "32768"
os.environ["HOUDINI_OCL_DEVICETYPE"] = "CPU"
import hou, time, psutil

proc = psutil.Process()
print("Starting probe...")

g = hou.node("/obj").createNode("geo", "PROBE_GEO")

# 1. READ DTM
dtm = g.createNode("heightfield_file", "DTM")
dtm.setParms({
    "filename": "D:/yacs/work/sa-calobra-houdini-unreal-20261016/inputs/dtm_height_float32.tif",
    "sizemethod": "divsize",
    "gridspacing": 0.5,
    "doclampmin": 0
})

xform = g.createNode("xform", "XFORM")
xform.setInput(0, dtm)
xform.setParms({"ry": 90.0})

# Test cooking base DTM
t0 = time.time()
xform.cook(force=True)
print(f"Base DTM cooked in {time.time()-t0:.2f}s, RSS MB: {proc.memory_info().rss / 1e6}")

# 2. Test Mask By Feature (slope + height)
mbf = g.createNode("heightfield_maskbyfeature", "MBF_GRASS")
mbf.setInput(0, xform)
mbf.setParms({
    "maskbyslope": 1,
    "min_slopeangle": 0.0,
    "max_slopeangle": 32.0,
    "maskbyheight": 1,
    "minheight": 8.0,
    "maxheight": 1500.0,
    "maskbyocclusion": 0
})

t0 = time.time()
mbf.cook(force=True)
print(f"MBF_GRASS cooked in {time.time()-t0:.2f}s, RSS MB: {proc.memory_info().rss / 1e6}")

# Check volume properties
geo = mbf.geometry()
for p in geo.prims():
    if isinstance(p, hou.Volume):
        print(f"  Volume: {p.attribValue('name')} min={p.volumeMin():.3f} max={p.volumeMax():.3f} res={p.resolution()}")

g.destroy()
print("Probe complete.")
