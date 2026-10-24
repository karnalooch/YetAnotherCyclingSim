"""Lesson05 diagnostic candidate. Consult LESSON05_HOUDINI_PROTOTYPE.md before replay."""
import argparse
import pathlib
parser = argparse.ArgumentParser(description='Bounded Lesson05 diagnostic replay; no UE import or production acceptance.')
parser.add_argument('--source-root', type=pathlib.Path, required=True)
parser.add_argument('--output-root', type=pathlib.Path, required=True)
args = parser.parse_args()
import hou, numpy as np, pathlib, json
out = args.output_root
root = args.source_root
hou.setUpdateMode(hou.updateMode.AutoUpdate)
g = hou.node('/obj').createNode('geo', 'LESSON05_PATCH')

def node(t, name, inp=None, **p):
    n = g.createNode(t, name)
    if inp:
        n.setInput(0, inp)
    n.setParms(p)
    return n

def arrays(n):
    n.cook(force=True)
    if n.errors():
        raise RuntimeError(n.errors())
    return {v.attribValue('name'): np.frombuffer(v.allVoxelsAsString(), np.float32).copy() for v in n.geometry().prims() if isinstance(v, hou.Volume)}
cache = out / 'patch_600m.bgeo.sc'
if not cache.exists():
    f = node('file', 'READ_ONLY_LESSON04', file=str(root / 'cache/lesson04_working_material_05m.bgeo.sc'))
    c = node('heightfield_crop', 'EXTRACT_REGISTERED_PATCH', f, sizex=600, sizey=600, tx=0, ty=1000)
    print('Loading retained cache and cropping', flush=True)
    c.cook(force=True)
    assert not c.errors(), c.errors()
    c.geometry().saveToFile(str(cache))
    f.destroy()
    c.destroy()
f = node('file', 'LESSON04_PATCH_CACHE', file=str(cache))
a = arrays(f)
print('Patch layers/range', [(k, len(v), float(v.min()), float(v.max())) for k, v in a.items()], flush=True)
s = node('heightfield_maskbyfeature', 'SCREE_SOURCE_SLOPE', f, maskbyslope=1, min_slopeangle=35, max_slopeangle=90, maskbyheight=0, maskbyocclusion=0)
sl = node('heightfield_slump', 'SCREE_TRANSPORT_MASK_ONLY', s, iterations=20, repose_angle=30, doerosion=0, add_to_bedrock=0, flow_enable=0, materiallayer='mask', bedrocklayer='height')
b = arrays(sl)
assert np.array_equal(a['height'], b['height'])
print('Slump PASS height unchanged', float(b['mask'].min()), float(b['mask'].max()), flush=True)
r = node('heightfield_remap', 'SCREE_REMAP_MEASURED', sl, layer='mask', inputmin=0, inputmax=float(b['mask'].max()), outputmin=0, outputmax=1)
arrays(r)
r.geometry().saveToFile(str(out / 'scree_transport_patch.bgeo.sc'))
g.layoutChildren()
hou.hipFile.save(str(out / 'Scree_patch_prototype.hiplc'))
(out / 'prototype.json').write_text(json.dumps({'status': 'transport prototype only; pocket stage pending', 'center_xz': [0, 1000], 'extent_m': 600, 'samples': len(a['height']), 'height_minmax': [float(a['height'].min()), float(a['height'].max())], 'height_changed_samples': int(np.count_nonzero(a['height'] != b['height'])), 'mask_max': float(b['mask'].max()), 'iterations': 20, 'repose_degrees': 30}, indent=2))
