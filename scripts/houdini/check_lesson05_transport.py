"""Check original Pegasus Layer Slump direction on a retained diagnostic crop.

This does not replace full-domain caches or establish whole-area acceptance.
"""
import argparse
import json
from pathlib import Path

import hou
import numpy as np

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--checkpoint', type=Path, required=True)
ap.add_argument('--retained-root', type=Path, required=True)
ap.add_argument('--output-root', type=Path, required=True)
a = ap.parse_args()
hou.setUpdateMode(hou.updateMode.Manual)
hou.hipFile.load(str(a.checkpoint), suppress_save_prompt=True, ignore_load_warnings=True)
g = hou.node('/obj').createNode('geo', 'DIRECTION_CONTROL_ONLY')
preview = np.load(a.retained_root/'working/preview_scree.npy')
y, x = np.unravel_index(np.argmax(preview), preview.shape)
center = (-1771.25 + int(x)*4, 3144.25 - int(y)*4)


def node(kind, name, first=None, **parms):
    n = g.createNode(kind, name)
    if first is not None:
        n.setInput(0, first)
    n.setParms(parms)
    return n


def array(n, layer):
    n.cook(force=True)
    assert not n.errors(), n.errors()
    v = next(p for p in n.geometry().prims() if p.attribValue('name') == layer)
    return np.frombuffer(v.allVoxelsAsString(), np.float32).copy().reshape(v.resolution()[1], v.resolution()[0])


inputs = []
for stage in ['slump', 'pockets']:
    f = node('file', stage.upper(), file=str(a.retained_root/'working'/(stage+'.bgeo.sc')))
    inputs.append(node('heightfield_crop', stage.upper()+'_CROP', f, sizex=400, sizey=400, tx=center[0], ty=center[1]))
maximum = json.loads((a.retained_root/'working/slump.json').read_text())['mask']['max']
remap = node('heightfield_remap', 'ORIGINAL_RANGE', inputs[0], layer='mask', inputmin=0, inputmax=maximum, outputmin=0, outputmax=1)
cp = node('heightfield_copylayer', 'POCKETS', inputs[1], srcname1='mask', dstname1='pockets')
slump = node('PE_heightfield_layerslump', 'ORIGINAL_LAYER_SLUMP', remap, srcname1='mask', srcname2='pockets', iterations=20, input=1)
slump.setInput(1, cp)
hou.setUpdateMode(hou.updateMode.AutoUpdate)
pockets = array(cp, 'pockets')
height = array(remap, 'height')
# Exclude the crop boundary from interpretation; this is a direction control only.
core = np.s_[100:-100, 100:-100]
receipt = {'scope': '400 m diagnostic crop; retained full Working/Context outputs unchanged', 'center_xz': center, 'cases': {}}
images = {'pockets': pockets[core]}
for name, iterations, direction in [('zero', 0, 1), ('opposite', 20, 0), ('retained', 20, 1)]:
    slump.setParms({'iterations': iterations, 'input': direction})
    mask = array(slump, 'mask')
    assert np.array_equal(height, array(slump, 'height'))
    weights = mask[core].astype(np.float64)
    receipt['cases'][name] = {'iterations': iterations, 'direction': direction,
        'weighted_pockets': float(np.sum(weights*pockets[core])/np.sum(weights)), 'height_changed_samples': 0}
    images[name] = mask[core]
receipt['accumulates_in_pockets'] = receipt['cases']['retained']['weighted_pockets'] > max(receipt['cases'][name]['weighted_pockets'] for name in ['zero', 'opposite'])
a.output_root.mkdir(parents=True, exist_ok=True)
(a.output_root/'direction_control.json').write_text(json.dumps(receipt, indent=2))
np.savez_compressed(a.output_root/'direction_control.npz', **images)
print(json.dumps(receipt), flush=True)
assert receipt['accumulates_in_pockets'], 'Retained direction did not increase pocket-weighted accumulation'
