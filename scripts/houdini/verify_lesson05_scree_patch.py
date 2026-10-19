"""Lesson05 diagnostic candidate. Consult LESSON05_HOUDINI_PROTOTYPE.md before replay."""
import argparse
import pathlib
parser = argparse.ArgumentParser(description='Bounded Lesson05 diagnostic replay; no UE import or production acceptance.')
parser.add_argument('--source-root', type=pathlib.Path, required=True)
parser.add_argument('--output-root', type=pathlib.Path, required=True)
parser.add_argument('--checkpoint', type=pathlib.Path, required=True)
args = parser.parse_args()
import hou, numpy as np, pathlib, json
out = args.output_root
hou.setUpdateMode(hou.updateMode.Manual)
hou.hipFile.load(str(args.checkpoint), suppress_save_prompt=True, ignore_load_warnings=True)
g = hou.node('/obj/LESSON05_PATCH_PROTOTYPE')
hou.setUpdateMode(hou.updateMode.AutoUpdate)

def vals(n):
    n.cook(force=True)
    assert not n.errors(), n.errors()
    return {p.attribValue('name'): np.frombuffer(p.allVoxelsAsString(), np.float32).copy().reshape(p.resolution()[1], p.resolution()[0]) for p in n.geometry().prims() if isinstance(p, hou.Volume)}
full = vals(g.node('WORKING_WATER_EXCLUSION'))['mask']
saved = np.load(out / 'mask.npy')
assert np.array_equal(full, saved)
f = g.node('LESSON04_PATCH_CACHE')
c = g.createNode('heightfield_crop', 'HALO_TEST')
c.setInput(0, f)
c.setParms({'sizex': 450, 'sizey': 450, 'tx': 0, 'ty': 1000})
g.node('SCREE_SOURCE_SLOPE').setInput(0, c)
g.node('POCKET_OCCLUSION').setInput(0, c)
small = vals(g.node('WORKING_WATER_EXCLUSION'))['mask']

def core(a):
    y, x = a.shape
    return a[(y - 600) // 2:(y + 600) // 2, (x - 600) // 2:(x + 600) // 2]
d = core(full) - core(small)
receipt = {'fresh_reopen_mask_exact': True, 'core_shape': [600, 600], 'halo_m': [75, 150], 'mask_max_abs_difference': float(np.max(np.abs(d))), 'mask_changed_samples': int(np.count_nonzero(d)), 'larger_shape': list(full.shape), 'smaller_shape': list(small.shape), 'note': 'Fixed remap bounds across both runs. Native crop includes boundary samples.'}
(out / 'reopen_halo.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt))
