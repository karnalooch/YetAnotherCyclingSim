import os
os.environ["HOUDINI_COP_MAXRES"] = "32768"
os.environ["HOUDINI_OCL_DEVICETYPE"] = "CPU"
import hou, time, psutil

proc = psutil.Process()
print("Starting slump & occlusion probe on 16000x16000...")

g = hou.node("/obj").createNode("geo", "PROBE_SLUMP")

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

# Mask by slope for slump
mbf = g.createNode("heightfield_maskbyfeature", "SLUMP_SOURCE")
mbf.setInput(0, xform)
mbf.setParms({
    "maskbyslope": 1,
    "min_slopeangle": 35.0,
    "max_slopeangle": 90.0,
    "maskbyheight": 0,
    "maskbyocclusion": 0
})

# Slump node
slump = g.createNode("heightfield_slump", "SLUMP")
slump.setInput(0, mbf)
slump.setParms({
    "iterations": 20,
    "repose_angle": 30.0,
    "doerosion": 0,
    "add_to_bedrock": 0,
    "flow_enable": 0,
    "materiallayer": "mask",
    "bedrocklayer": "height"
})

t0 = time.time()
print("Cooking slump (20 iterations)...")
slump.cook(force=True)
print(f"Slump cooked in {time.time()-t0:.2f}s, RSS MB: {proc.memory_info().rss / 1e6}")

# Check volume properties
geo = slump.geometry()
for p in geo.prims():
    if isinstance(p, hou.Volume):
        print(f"  Volume: {p.attribValue('name')} min={p.volumeMin():.3f} max={p.volumeMax():.3f} res={p.resolution()}")

g.destroy()
print("Probe complete.")
