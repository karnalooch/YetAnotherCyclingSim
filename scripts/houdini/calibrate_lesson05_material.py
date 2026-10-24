"""Lesson05 diagnostic candidate. Consult LESSON05_FULL_LANDSCAPE.md before replay."""
import argparse
import pathlib
parser = argparse.ArgumentParser(description='Bounded Lesson05 diagnostic replay; no UE import or production acceptance.')
parser.add_argument('--source-root', type=pathlib.Path, required=True)
parser.add_argument('--output-root', type=pathlib.Path, required=True)
parser.add_argument('--material-root', type=pathlib.Path, required=True)
args = parser.parse_args()
import hou, OpenImageIO as oi, numpy as np, pathlib, json, hashlib
out = args.output_root
out.mkdir(parents=True, exist_ok=False)
src = args.material_root / 'export'
if not src.exists():
    src = next(args.material_root.rglob('YACS_Material_Height.exr')).parent

def read(p):
    i = oi.ImageInput.open(str(p))
    a = i.read_image(format=oi.FLOAT)
    i.close()
    return a

def write(p, a):
    a = np.ascontiguousarray(a, dtype=np.float32)
    if a.ndim == 2:
        a = a[:, :, None]
    o = oi.ImageOutput.create(str(p))
    o.open(str(p), oi.ImageSpec(a.shape[1], a.shape[0], a.shape[2], oi.FLOAT))
    o.write_image(a)
    o.close()
hou.setUpdateMode(hou.updateMode.AutoUpdate)
hou.hda.installFile(str(args.source_root / 'otls/sop_PE_heightfield_material.1.0.hda'))
g = hou.node('/obj').createNode('geo', 'CALIBRATION')
hf = g.createNode('heightfield')
hf.setParms({'sizex': 8, 'sizey': 8, 'gridspacing': 0.5})
m = g.createNode('PE_heightfield_material::1.0')
m.setInput(0, hf)
m.setParms({'size': 4, 'use_distort': 0, 'use_mask': 0, 'heightscale': 1})
rows = []
for value in [0, 0.47, 0.5, 0.75, 1]:
    p = out / f'constant_{value}.exr'
    write(p, np.full((16, 16, 3), value))
    m.setParms({'filename1': str(p), 'filename2': str(p), 'filename3': str(p)})
    m.cook(force=True)
    geo = m.geometry()
    row = {'input': value, 'layers': {}}
    for v in geo.prims():
        a = np.frombuffer(v.allVoxelsAsString(), dtype=np.float32)
        row['layers'][v.attribValue('name')] = [float(a.min()), float(a.max())]
    assert abs(row['layers']['height'][0] - (2 * value - 1)) < 1e-06
    rows.append(row)
    print(row, flush=True)
height = read(src / 'YACS_Material_Height.exr')
write(out / 'Height_Pegasus.exr', height + 0.03)
orm = read(src / 'YACS_Material_ORM.png')
write(out / 'Roughness_Pegasus.exr', orm[:, :, 1])
color = read(src / 'YACS_Material_BaseColor.png')[:, :, :3]
linear = np.where(color <= 0.04045, color / 12.92, ((color + 0.055) / 1.055) ** 2.4)
write(out / 'BaseColor_linear_Pegasus.exr', linear)
m.setParms({'filename1': str(out / 'BaseColor_linear_Pegasus.exr'), 'filename2': str(out / 'Roughness_Pegasus.exr'), 'filename3': str(out / 'Height_Pegasus.exr'), 'heightscale': 0})
m.cook(force=True)
geo = m.geometry()
h = next((p for p in geo.prims() if p.attribValue('name') == 'height'))
assert np.count_nonzero(np.frombuffer(h.allVoxelsAsString(), dtype=np.float32)) == 0
hou.hipFile.save(str(out / 'Material_calibration.hiplc'))
(out / 'calibration.json').write_text(json.dumps({'controls': rows, 'height_adapter': 'H + 0.03; HDA output = scale*(2*H_adapter-1)', 'roughness': 'ORM green, linear float EXR', 'basecolor': 'sRGB decode to linear float EXR', 'zero_height_control': True}, indent=2))
