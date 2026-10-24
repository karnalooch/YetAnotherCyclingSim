"""Execute Pegasus lesson 05 on a continuous retained landscape, in bounded stages.

Native nodes own all masks, transport and shading. Stage files bound memory while
the owner UE stream runs. No source cache, HDA, or Lesson04 HIP is overwritten.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import hou
import numpy as np

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--source-root', type=Path, required=True)
ap.add_argument('--output-root', type=Path, required=True)
ap.add_argument('--corpus', type=Path, required=True)
ap.add_argument('--forge-root', type=Path, required=True)
ap.add_argument('--adapter-root', type=Path, required=True)
ap.add_argument('--reuse-root', type=Path, help='Retained unchanged stages for an incremental tail repair')
ap.add_argument('--checkpoint-input', type=Path, help='Retained HIP providing the original Lesson04 cliff mask')
ap.add_argument('--area', choices=['working', 'context'], default='working')
ap.add_argument('--stage', choices=['source','slump','pockets','transport','material','cliff_tint','scree_tint','occlusion','curvature','verify'], required=True)
args = ap.parse_args()
root, out = args.source_root.resolve(), args.output_root.resolve() / args.area
assert root != out and root not in out.parents, 'Keep outputs outside retained source tree'
assert hou.applicationVersionString() == '22.0.466', 'Revalidate node bindings for this version'
out.mkdir(parents=True, exist_ok=True)
assert not (out / ('final.bgeo.sc' if args.stage == 'verify' else args.stage + '.bgeo.sc')).exists(), 'Refuse stage overwrite: use a new output root'
if args.reuse_root:
    retained = args.reuse_root.resolve()
    assert out != retained and retained not in out.parents, 'Keep correction outputs outside retained stages'
assert os.environ.get('HOUDINI_OCL_DEVICETYPE') == 'CPU', 'Reserve GPU for UE stream'
if args.checkpoint_input:
    hou.setUpdateMode(hou.updateMode.Manual)
    hou.hipFile.load(str(args.checkpoint_input), suppress_save_prompt=True, ignore_load_warnings=True)
hou.setUpdateMode(hou.updateMode.AutoUpdate)
for name in ['material.1.0', 'tint.1.0']:
    hou.hda.installFile(str(root / 'otls' / f'sop_PE_heightfield_{name}.hda'))
slump_hda = next(args.corpus.rglob('sop_PE_heightfield_layerslump.hda'))
hou.hda.installFile(str(slump_hda))
g = hou.node('/obj').createNode('geo', f'LESSON05_{args.area.upper()}_{args.stage.upper()}')

def node(kind, name, first=None, **parms):
    n = g.createNode(kind, name)
    if first is not None:
        n.setInput(0, first)
    n.setParms(parms)
    return n

def load(stage):
    path = out / (stage + '.bgeo.sc')
    if not path.exists() and args.reuse_root:
        path = args.reuse_root / args.area / (stage + '.bgeo.sc')
    n = node('file', 'CACHE_' + stage.upper(), file=str(path))
    if stage == 'source':
        n = node('heightfield_copylayer', 'INITIALIZE_MASK', n, srcname1='height', dstname1='mask')
    return n

def geo(n):
    try:
        n.cook(force=True)
    except hou.Error:
        print([(c.path(),c.errors()) for c in [n]+list(n.allSubChildren()) if c.errors()], flush=True)
        raise
    assert not n.errors(), n.errors()
    return n.geometry()

def volume(geometry, name):
    return next(p for p in geometry.prims() if isinstance(p, hou.Volume) and p.attribValue('name') == name)

def values(geometry, name):
    return np.frombuffer(volume(geometry, name).allVoxelsAsString(), np.float32)

def stats(a):
    assert np.isfinite(a).all()
    return dict(min=float(a.min()), max=float(a.max()), mean=float(a.mean(dtype=np.float64)), count=a.size)

def ramp(n, parm, points, vals):
    n.parm(parm).set(hou.Ramp([hou.rampBasis.Linear] * len(points), points, vals))

def tint(first, mask, name, strength, color=None, colors=None):
    # Original HDA labels: srcname1 = Ramp Layer, ramp_mask = Mask.
    # Constant tints require the latter; ramp grading deliberately has no mask.
    n = node('PE_heightfield_tint::1.0', name, first, strength=strength, use_ramp=int(colors is not None), srcname1='mask', ramp_mask='mask' if colors is None else '')
    n.setInput(1, mask)
    if color is not None:
        n.parmTuple('tint').set(color)
    if colors is not None:
        ramp(n, 'tint_ramp', [0, .5, 1], colors)
    return n

baseline = root / 'cache' / ('lesson04_working_material_05m.bgeo.sc' if args.area == 'working' else 'lesson04_context_material.bgeo.sc')
receipt = dict(stage=args.stage, area=args.area, houdini=hou.applicationVersionString(), opencl='CPU')
print('START', args.area, args.stage, flush=True)

if args.stage == 'source':
    f = node('file', 'RETAINED_LESSON04', file=str(baseline))
    result = node('blast', 'MASK_INPUT_LAYERS', f, group='@name=height @name=Alpha', negate=1)
elif args.stage == 'slump':
    f = load('source')
    s = node('heightfield_maskbyfeature', 'SCREE_SOURCE_SLOPE', f, maskbyslope=1, min_slopeangle=35, max_slopeangle=90, maskbyheight=0, maskbyocclusion=0)
    ramp(s, 'sloperamp', [0,.15,1], [0,1,1])
    result = node('heightfield_slump', 'SCREE_DOWNHILL', s, iterations=20, repose_angle=30, doerosion=0, add_to_bedrock=0, flow_enable=0, materiallayer='mask', bedrocklayer='height')
elif args.stage == 'pockets':
    f = load('source')
    result = node('heightfield_maskbyfeature', 'LOCAL_POCKETS', f, maskbyslope=0, maskbyheight=0, maskbyocclusion=1, viewdistance=5)
    ramp(result, 'ramp', [0,1], [1,0])
elif args.stage == 'transport':
    f = load('slump'); p = load('pockets')
    maximum = json.loads((out / 'slump.json').read_text())['mask']['max']
    rem = node('heightfield_remap', 'MEASURED_SLUMP_RANGE', f, layer='mask', inputmin=0, inputmax=maximum, outputmin=0, outputmax=1)
    cp = node('heightfield_copylayer', 'POCKETS_LAYER', p, srcname1='mask', dstname1='pockets')
    ls = node('PE_heightfield_layerslump', 'PEGASUS_POCKET_TRANSPORT', rem, srcname1='mask', srcname2='pockets', input=1, iterations=20)
    ls.setInput(1, cp)
    maximum = float(values(geo(ls), 'mask').max())
    receipt['raw_transport_max'] = maximum
    r = node('heightfield_remap', 'MEASURED_SPARSE_REMAP', ls, layer='mask', inputmin=0, inputmax=maximum, outputmin=0, outputmax=1)
    ramp(r, 'remap', [0,.05,.4,1], [0,0,.45,1])
    result = node('volumewrangle', 'VALID_DRY_WORKING_SUPPORT', r, snippet='if (@height <= 0 || @Alpha <= 0) @mask=0;')
elif args.stage == 'material':
    f = node('file', 'RETAINED_LESSON04', file=str(baseline)); mask = load('transport')
    basecolor = next(args.forge_root.rglob('YACS_Material_BaseColor.png'))
    result = node('PE_heightfield_material::1.0', 'FORGE_SCREE', f, filename1=str(basecolor), filename2=str(args.adapter_root/'Roughness_Pegasus.exr'), filename3=str(args.adapter_root/'Height_Pegasus.exr'), size=4, heightscale=.1, use_mask=1, srcname1='mask', use_distort=0)
    result.setInput(1, mask)
    receipt['height_scale_candidate_m'] = .1
elif args.stage in ['cliff_tint', 'scree_tint']:
    f = load('material' if args.stage == 'cliff_tint' else 'cliff_tint')
    if args.stage == 'cliff_tint':
        assert args.checkpoint_input, 'Original Lesson04 cliff mask requires --checkpoint-input'
        original = hou.node('/obj/SA_CALOBRA/' + args.area.upper() + '_MASK_CLIFF')
        assert original is not None, 'Missing original Lesson04 cliff mask'
        mask = node('object_merge', 'RETAINED_CLIFF_MASK', objpath1=original.path(), xformtype=0)
        result = tint(f, mask, 'CLIFF_TINT', .15, color=(.94,.96,1))
    else:
        result = tint(f, load('transport'), 'SCREE_TINT', .2, color=(1,.98,.95))
elif args.stage == 'occlusion':
    f = load('scree_tint')
    if args.reuse_root:
        mask = node('file', 'RETAINED_BROAD_EXPOSURE', file=str(args.reuse_root/args.area/'occlusion.bgeo.sc'))
    else:
        mask = node('heightfield_maskbyfeature', 'BROAD_EXPOSURE', load('source'), maskbyslope=0, maskbyheight=0, maskbyocclusion=1, viewdistance=25)
    result = tint(f, mask, 'EXPOSURE_TINT', .2, colors=[(1,1,1),(.93,.95,.92),(1,1,1)])
elif args.stage == 'curvature':
    f = load('occlusion')
    if args.reuse_root:
        mask = node('file', 'RETAINED_CURVATURE_MASK', file=str(args.reuse_root/args.area/'curvature.bgeo.sc'))
        receipt['computed_curvature_range'] = json.loads((args.reuse_root/args.area/'curvature.json').read_text())['computed_curvature_range']
    else:
        mask = node('heightfield_maskbyfeature', 'CURVATURE_MASK', load('source'), maskbyslope=0, maskbyheight=0, maskbyocclusion=0, maskbycurvature=1)
        mask.parm('computercurvature').pressButton()
        receipt['computed_curvature_range'] = mask.parm('max_curvature').eval()
    assert float(values(geo(mask),'mask').max()) > 0, 'Curvature mask must be nonblank'
    result = tint(f, mask, 'CURVATURE_TINT', .1, colors=[(1,1,1),(1.02,1.02,1.02),(1.05,1.05,1.05)])
else:
    f = node('file', 'BASELINE', file=str(baseline)); result = load('curvature')

raw = geo(result)
if args.stage in ['cliff_tint', 'occlusion', 'curvature']:
    name = {'cliff_tint': 'cliff', 'occlusion': 'broad_occlusion', 'curvature': 'curvature'}[args.stage]
    mask_geo = hou.Geometry(); mask_geo.merge(geo(mask))
    mask_geo.deletePrims([p for p in mask_geo.prims() if p.attribValue('name') != 'mask'])
    volume(mask_geo, 'mask').setAttribValue('name', name)
    mask_geo.saveToFile(str(out / (name + '_mask.bgeo.sc')))
receipt['height'] = stats(values(raw, 'height'))
receipt['resolution'] = list(volume(raw, 'height').resolution())
receipt['origin'] = list(volume(raw, 'height').indexToPos((0,0,0)))
try:
    receipt['mask'] = stats(values(raw, 'mask'))
except StopIteration:
    pass
if args.stage in ['slump','pockets','transport']:
    source = geo(load('source'))
    receipt['height_changed_samples'] = int(np.count_nonzero(values(raw,'height') != values(source,'height')))
    assert receipt['height_changed_samples'] == 0
if args.stage == 'verify':
    base = geo(f); delta = values(raw,'height').astype(np.float64)-values(base,'height')
    receipt['delta_l05_m'] = stats(delta)
    receipt['delta_l05_abs_p95_m'] = float(np.percentile(np.abs(delta),95))
    mask = values(geo(load('transport')), 'mask')
    receipt['outside_mask_raw_max_m'] = float(np.max(np.abs(delta[mask==0])))
    # Exact registered transfer, not an extra terrain generator: remove native
    # blend roundoff outside the authored support while retaining HDA values inside.
    final = hou.Geometry(); final.merge(raw)
    h = values(raw,'height').copy(); h[mask==0] = values(base,'height')[mask==0]
    volume(final,'height').setAllVoxelsFromString(h.tobytes())
    assert not (out/'final.bgeo.sc').exists(), 'Refuse final cache overwrite'
    # Preserve the authored scree mask as a separate named layer in the output.
    mg = hou.Geometry(); mg.merge(geo(load('transport')))
    mg.deletePrims([p for p in mg.prims() if p.attribValue('name') != 'mask'])
    volume(mg,'mask').setAttribValue('name','scree')
    final.merge(mg)
    for name in ['cliff', 'broad_occlusion', 'curvature', 'pockets']:
        path = out / (name + '_mask.bgeo.sc')
        if name == 'pockets':
            layer_geo = hou.Geometry(); layer_geo.merge(geo(load('pockets')))
            layer_geo.deletePrims([p for p in layer_geo.prims() if p.attribValue('name') != 'mask'])
            volume(layer_geo, 'mask').setAttribValue('name', name)
        else:
            assert path.is_file(), 'Missing retained output mask: ' + str(path)
            layer_geo = hou.Geometry(); layer_geo.loadFromFile(str(path))
        assert volume(layer_geo, name).resolution() == volume(final, 'height').resolution()
        for index in [(0,0,0), (1,0,0), (0,1,0)]:
            assert volume(layer_geo, name).indexToPos(index) == volume(final, 'height').indexToPos(index)
        final.merge(layer_geo)
    final.saveToFile(str(out/'final.bgeo.sc'))
    delta = h.astype(np.float64)-values(base,'height')
    receipt['final_delta_l05_m'] = stats(delta)
    receipt['scree_coverage_positive'] = float(np.mean(mask>0))
    receipt['scree_coverage_gt_01'] = float(np.mean(mask>.1))
    receipt['final_changed_samples'] = int(np.count_nonzero(delta))
    receipt['final_delta_abs_p95_m'] = float(np.percentile(np.abs(delta),95))
    receipt['outside_mask_final_max_m'] = float(np.max(np.abs(delta[mask==0])))
    np.save(out/'delta_l05.npy', delta.astype(np.float32))
else:
    target = out/(args.stage+'.bgeo.sc')
    assert not target.exists(), 'Refuse stage overwrite: use a new output root'
    raw.saveToFile(str(target))
g.layoutChildren()
g.saveItemsToFile(tuple(g.children()),str(out/(args.stage+'.cpio')))
(out/(args.stage+'.json')).write_text(json.dumps(receipt,indent=2))
print('DONE',json.dumps(receipt),flush=True)
