"""Native SideFX height-only transition from retained current-UE readback.

NumPy decodes/encodes the already calibrated transport and checks invariants;
HeightField Mask by Geometry and HeightField Layer author the transition.
"""
import argparse
import hashlib
import json
from pathlib import Path
import hou
import numpy as np
from repair_lesson06_idmap import read, volume, values, lattice, digest, geometry
from lesson04_height_encoding import decode_h22_readback, height_codes, additive_codes, h22_transport

PROJECT = Path(__file__).resolve().parents[2]
ROOT = Path('D:/yacs/work/lesson06-geometry-20261018')
BEFORE = PROJECT/'Saved/RuntimeProof/Lesson06GeometryRemote/before'
OLD = Path('D:/yacs/work/lesson05-ue-20261018/transfer-height-only')
HIP = PROJECT/'worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson06_Geometry.hiplc'
SCALE = 585.9375
LAYER = 'Lesson06_Boundary_Transition'
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--verify', action='store_true')
a = ap.parse_args()
assert hou.applicationVersionString() == '22.0.466'
assert (BEFORE/'complete.json').exists()
old = json.loads((OLD/'manifest.json').read_text())
ROOT.mkdir(exist_ok=True)
hou.setUpdateMode(hou.updateMode.Manual)
hou.hipFile.load(str(HIP if a.verify else PROJECT/'worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson06_Seam.hiplc'), suppress_save_prompt=True)
if a.verify:
    g = hou.node('/obj/LESSON06_GEOMETRY')
else:
    assert not HIP.exists() and not (ROOT/'manifest.json').exists()
    g = hou.node('/obj').createNode('geo', 'LESSON06_GEOMETRY')
    for n in g.children(): n.destroy()
hou.setUpdateMode(hou.updateMode.AutoUpdate)

def node(typ, name, inputs=(), parms=None):
    if a.verify: return g.node(name)
    n = g.createNode(typ, name)
    for i, src in enumerate(inputs): n.setInput(i, src)
    if parms: n.setParms(parms)
    return n

def file(name, path): return node('file', name, parms={'file': str(path)})

report = {'status': 'PREPARING', 'houdini_version': hou.applicationVersionString(),
          'target_map': old['target_map'], 'output_mode': 1, 'height_only': True,
          'scale_z': SCALE, 'quantization_step_m': SCALE/12800, 'delta_layer': LAYER,
          'fresh_replay': a.verify, 'source_hashes': {}, 'tiles': [],
          'band': {'inner_rectangle_inset_from_native_working_m': 64, 'native_boxblur_radius_m': 32,
                   'extent': 'Outside the inset rectangle, including existing UE padding; Context unchanged',
                   'parameter_authority': 'Local candidate tuning, not SideFX tutorial constants'}}

# Convert H22 native readback units to actual metres, retaining all mask bytes.
for tile in old['tiles']:
    name = tile['name']; path = BEFORE/(name+'.bgeo.sc')
    report['source_hashes'][str(path)] = digest(path)
    dst = ROOT/(name+'_baseline.bgeo.sc')
    if not a.verify:
        assert not dst.exists()
        baseline = read(path)
        codes, metres = decode_h22_readback(values(baseline, 'height'), SCALE)
        assert hashlib.sha256(codes.tobytes()).hexdigest() == tile['expected_codes_sha256'], name
        volume(baseline, 'height').setAllVoxelsFromString(metres.astype(np.float32).tobytes())
        baseline.saveToFile(str(dst))
        del baseline, codes, metres
context = file('CONTEXT_UNCHANGED', ROOT/'SaCalobra_Context_Valid_baseline.bgeo.sc')
lat = json.loads((Path('D:/yacs/work/lesson06-reviewed-20261018/working/repair.json')).read_text())['lattice']
nx, ny, _ = lat['resolution']; ox, _, oz = lat['origin']
sx, sz = nx*.5, ny*.5
box = node('box', 'UNCHANGED_WORKING_CORE', parms={'sizex': sx-128, 'sizey':10000, 'sizez':sz-128,
    'tx':ox+(nx-1)*.25, 'tz':oz-(ny-1)*.25})
edges = []
for tile in old['tiles']:
    name = tile['name']; print('PREPARE', name, flush=True)
    base = file(name+'_SOURCE', ROOT/(name+'_baseline.bgeo.sc'))
    bg = geometry(base); original = values(bg,'height').copy()
    if 'Context' in name:
        final = bg
        weight = np.zeros_like(original)
        producer = base
    else:
        maskbase = node('heightfield_copylayer', name+'_MASK_COPY', [base], {'srcname1':'height','dstname1':'mask'})
        band = node('heightfield_maskbyobject', name+'_BAND', [maskbase,box], {'invertmask':1,'blurmethod':'boxblur','blurradius':32,'maxdist':10000})
        mask = node('blast', name+'_BAND_ONLY', [band], {'group':'@name=mask','negate':1})
        producer = node('heightfield_layer', name+'_HEIGHT_TRANSITION', [base,context,mask], {'layer':'height','mode':'replace','masklayer':'mask'})
        final = geometry(producer)
        weight = values(geometry(mask),'mask').copy()
        np.save(ROOT/(name+'_band.npy'), weight)
    target = ROOT/(name+'_final.bgeo.sc')
    if a.verify:
        cached = read(target)
        for p in final.prims():
            assert p.allVoxelsAsString() == volume(cached,p.attribValue('name')).allVoxelsAsString(), (name,p.attribValue('name'))
        del cached
    else:
        final.saveToFile(str(target))
    result = values(final,'height').copy()
    core = weight == 0
    assert np.array_equal(result[core], original[core]), ('outside band',name)
    for p in bg.prims():
        if p.attribValue('name') != 'height':
            assert p.allVoxelsAsString() == volume(final,p.attribValue('name')).allVoxelsAsString(), (name,'mask')
    row = dict(tile)
    delta = result.astype(np.float64)-original
    row.update(producer=producer.path(), final_cache_sha256=digest(target),
               band_samples=int(np.count_nonzero(~core)), changed_samples=int(np.count_nonzero(delta)),
               outside_band='BIT_EXACT', original_masks='BIT_EXACT',
               delta_min_m=float(delta.min()),delta_max_m=float(delta.max()),delta_max_abs_m=float(np.abs(delta).max()),
               delta_mean_abs_within_band_m=float(np.abs(delta[~core]).mean()) if (~core).any() else 0,
               files={},file_sha256={})
    shape=(tile['resolution'][1],tile['resolution'][0])
    np.save(ROOT/(name+'_expected.npy'), result.reshape(shape))
    codes=height_codes(result,SCALE)
    row['expected_codes_sha256']=hashlib.sha256(codes.tobytes()).hexdigest()
    if 'Context' not in name:
        native=hou.Geometry(); native.merge(final)
        native.deletePrims([p for p in native.prims() if p.attribValue('name')!='height'],True)
        volume(native,'height').setAllVoxelsFromString(h22_transport(additive_codes(original,result,SCALE),SCALE).tobytes())
        attrs={'unreal_output_name':name,'unreal_landscape_output_mode':1,
               'unreal_landscape_editlayer_name':LAYER,'unreal_landscape_editlayer_clear':1,
               'unreal_landscape_editlayer_type':1,'unreal_landscape_layer_min':-1500.0,
               'unreal_landscape_layer_max':1500.0,'unreal_bake_folder':'/Game/Generated/YACS/Lesson06Geometry_20261018/Baked'}
        for key,val in attrs.items():
            attr=native.findPrimAttrib(key) or native.addAttrib(hou.attribType.Prim,key,val)
            for p in native.prims():p.setAttribValue(attr,val)
        payload=ROOT/(name+'_increment.bgeo.sc')
        if not a.verify:native.saveToFile(str(payload))
        row['files']={LAYER:payload.name};row['file_sha256']={LAYER:digest(payload)}
        arr=codes.reshape(shape)
        edges.append([arr[0].copy(),arr[-1].copy(),arr[:,0].copy(),arr[:,-1].copy()])
        del native
    report['tiles'].append(row)
    del bg, final, original, result, delta, weight, codes
errors=[np.count_nonzero(edges[0][3]!=edges[1][2]),np.count_nonzero(edges[2][3]!=edges[3][2]),np.count_nonzero(edges[2][1]!=edges[0][0]),np.count_nonzero(edges[3][1]!=edges[1][0])]
report['shared_edge_code_mismatches']=list(map(int,errors))
assert max(errors)==0, errors
if not a.verify:
    g.layoutChildren();g.setComment('Separate owner-authorized height transition only. Original source caches and masks retained. Native SideFX mask and height Layer. No L02-05 cook.')
    hou.hipFile.save(str(HIP))
report['hip_sha256']=digest(HIP)
for path,sha in report['source_hashes'].items():assert digest(path)==sha
report['status']='NATIVE_GEOMETRY_PASS'
(ROOT/('reopen.json' if a.verify else 'manifest.json')).write_text(json.dumps(report,indent=2)+'\n')
print(report['status'],report['shared_edge_code_mismatches'],flush=True)
