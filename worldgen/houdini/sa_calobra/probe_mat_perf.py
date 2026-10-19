import os
os.environ["HOUDINI_COP_MAXRES"] = "32768"
os.environ["HOUDINI_OCL_DEVICETYPE"] = "CPU"
import hou, time, psutil
from pathlib import Path

proc = psutil.Process()
print("Starting PE_heightfield_material probe on 16000x16000...")

root = Path("worldgen/houdini/sa_calobra").resolve()
hou.hda.installFile(str(root / "otls/sop_PE_heightfield_material.1.0.hda"))

g = hou.node("/obj").createNode("geo", "PROBE_MAT")

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

# Mask grass
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

tex_dir = root / "inputs/textures"
mat = g.createNode("PE_heightfield_material::1.0", "MAT_GRASS")
mat.setInput(0, xform)
mat.setInput(1, mbf)
mat.setParms({
    "filename1": str(tex_dir / "SaCalobra_Grass_BaseColor.png"),
    "filename2": str(tex_dir / "SaCalobra_Grass_Roughness.png"),
    "filename3": str(tex_dir / "tlonbisya_4K_Displacement.exr"),
    "size": 12.0,
    "heightscale": 0.0,
    "use_mask": 1,
    "srcname1": "mask",
    "input2": "2",
    "use_distort": 1,
    "noisetype": "simplex",
    "amp": 3.5,
    "element_size": 15.0,
    "rough": 0.5,
    "maxoctave": 3
})

t0 = time.time()
print("Cooking MAT_GRASS on 16000x16000...")
mat.cook(force=True)
print(f"MAT_GRASS cooked in {time.time()-t0:.2f}s, RSS MB: {proc.memory_info().rss / 1e6}")

geo = mat.geometry()
for p in geo.prims():
    if isinstance(p, hou.Volume):
        print(f"  Volume: {p.attribValue('name')} min={p.volumeMin():.3f} max={p.volumeMax():.3f} res={p.resolution()}")

g.destroy()
print("Probe complete.")
