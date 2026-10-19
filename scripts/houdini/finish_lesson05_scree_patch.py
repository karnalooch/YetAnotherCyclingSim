"""Lesson05 diagnostic candidate. Consult LESSON05_HOUDINI_PROTOTYPE.md before replay."""
import argparse
import pathlib
parser = argparse.ArgumentParser(description='Bounded Lesson05 diagnostic replay; no UE import or production acceptance.')
parser.add_argument('--source-root', type=pathlib.Path, required=True)
parser.add_argument('--output-root', type=pathlib.Path, required=True)
parser.add_argument('--corpus', type=pathlib.Path, required=True)
parser.add_argument('--checkpoint', type=pathlib.Path, required=True)
args = parser.parse_args()
import hou, numpy as np, pathlib, json, hashlib
out = args.output_root
root = args.source_root
corpus = args.corpus
assert args.checkpoint.parent.resolve() == root.resolve(), 'Keep baseline HIP-relative inputs valid'
assert not args.checkpoint.exists(), 'Refuse checkpoint overwrite'
hda = next(corpus.rglob('sop_PE_heightfield_layerslump.hda'))
hou.hda.installFile(str(hda))
hou.hda.installFile(str(root / 'otls/sop_PE_heightfield_material.1.0.hda'))
hou.hipFile.load(str(out / 'Scree_patch_prototype.hiplc'), suppress_save_prompt=True, ignore_load_warnings=True)
hou.hda.installFile(str(hda))
hou.hda.installFile(str(root / 'otls/sop_PE_heightfield_material.1.0.hda'))
hou.setUpdateMode(hou.updateMode.AutoUpdate)
g = hou.node('/obj/LESSON05_PATCH')
f = g.node('LESSON04_PATCH_CACHE')
r = g.node('SCREE_REMAP_MEASURED')

def node(t, name, inp, **p):
    n = g.createNode(t, name)
    n.setInput(0, inp)
    n.setParms(p)
    return n

def vals(n):
    n.cook(force=True)
    assert not n.errors(), n.errors()
    return {v.attribValue('name'): np.frombuffer(v.allVoxelsAsString(), np.float32).copy().reshape(v.resolution()[1], v.resolution()[0]) for v in n.geometry().prims() if isinstance(v, hou.Volume)}
p = node('heightfield_maskbyfeature', 'POCKET_OCCLUSION', f, maskbyslope=0, maskbyheight=0, maskbyocclusion=1, viewdistance=5)
cp = node('heightfield_copylayer', 'COPY_POCKETS', p, srcname1='mask', dstname1='pockets')
ls = node('PE_heightfield_layerslump', 'PEGASUS_POCKET_TRANSPORT', r, srcname1='mask', srcname2='pockets', input=1, iterations=20)
ls.setInput(1, cp)
a = vals(f)
b = vals(ls)
assert np.array_equal(a['height'], b['height'])
mx = float(b['mask'].max())
assert mx > 0
rm = node('heightfield_remap', 'POCKET_REMAP_MEASURED', ls, layer='mask', inputmin=0, inputmax=mx, outputmin=0, outputmax=1)
ex = node('volumewrangle', 'WORKING_WATER_EXCLUSION', rm, snippet='if (@height <= 0 || @Alpha <= 0) @mask = 0;')
mat = node('PE_heightfield_material::1.0', 'FORGE_SCREE_ZERO_HEIGHT_CONTROL', f, filename1=str(out / 'BaseColor_linear_Pegasus.exr'), filename2=str(out / 'Roughness_Pegasus.exr'), filename3=str(out / 'Height_Pegasus.exr'), size=4, heightscale=0, use_mask=1, srcname1='mask', use_distort=0)
mat.setInput(1, ex)
final = vals(mat)
delta = final['height'] - a['height']
print('ZERO HEIGHT DELTA', float(np.max(np.abs(delta))), int(np.count_nonzero(delta)), flush=True)
mask = vals(ex)['mask']
np.save(out / 'mask.npy', mask)
np.save(out / 'height.npy', a['height'])
mat.geometry().saveToFile(str(out / 'scree_material_zero_height.bgeo.sc'))
g.layoutChildren()
g.saveItemsToFile(tuple(g.children()), str(out / 'patch_nodes.cpio'))
receipt = {'status': 'small-patch candidate, not full Lesson05 acceptance', 'samples': mask.size, 'shape': list(mask.shape), 'mask_minmax': [float(mask.min()), float(mask.max())], 'coverage_gt_0_1': float(np.mean(mask > 0.1)), 'height_changed_samples': int(np.count_nonzero(a['height'] != final['height'])), 'pocket_raw_max': mx, 'height_scale': 0, 'zero_height_control': 'FAIL exact equality', 'zero_height_max_abs_m': float(np.max(np.abs(delta))), 'halo_convergence': 'NOT_RUN', 'direction_control': 'tutorial inverted setting; independent pocket-vs-peak validation pending', 'hda_sha256': hashlib.sha256(hda.read_bytes()).hexdigest()}
hou.hipFile.save(str(out / 'Scree_patch_material.hiplc'))
hou.setUpdateMode(hou.updateMode.Manual)
baseline = root / 'SaCalobra_Pegasus_Lesson04.hiplc'
before = hashlib.sha256(baseline.read_bytes()).hexdigest()
hou.hipFile.load(str(baseline), suppress_save_prompt=True, ignore_load_warnings=True)
hou.hda.installFile(str(hda))
new = hou.node('/obj').createNode('geo', 'LESSON05_PATCH_PROTOTYPE')
new.loadItemsFromFile(str(out / 'patch_nodes.cpio'))
new.setDisplayFlag(False)
target = args.checkpoint
hou.hipFile.save(str(target))
assert hashlib.sha256(baseline.read_bytes()).hexdigest() == before
receipt.update({'baseline_sha256': before, 'hip': str(target), 'hip_sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
(out / 'patch_receipt.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt), flush=True)
