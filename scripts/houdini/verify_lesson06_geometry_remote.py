"""Full-domain native UE readback: height codes, masks and bounded changes."""
import hashlib
import json
from pathlib import Path
import numpy as np
from repair_lesson06_idmap import read, values, volume, lattice, digest
from lesson04_height_encoding import decode_h22_readback, height_codes

PROJECT=Path(__file__).resolve().parents[2]
PROOF=PROJECT/'Saved/RuntimeProof/Lesson06GeometryRemote'
ROOT=Path('D:/yacs/work/lesson06-geometry-20261018')
manifest=json.loads((ROOT/'manifest.json').read_text())
assert (PROOF/'after/complete.json').exists()
report={'status':'IN_PROGRESS','tiles':[],'source_retention':{},'merge':False,'restart':False}
edges=[]
for tile in manifest['tiles']:
    name=tile['name'];print('VERIFY',name,flush=True)
    before=read(PROOF/'before'/(name+'.bgeo.sc'))
    after=read(PROOF/'after'/(name+'.bgeo.sc'))
    bp=volume(before,'height');ap=volume(after,'height')
    assert lattice(bp)==lattice(ap),(name,'lattice')
    old_codes,old=decode_h22_readback(values(before,'height'),manifest['scale_z'])
    codes,actual=decode_h22_readback(values(after,'height'),manifest['scale_z'])
    assert hashlib.sha256(codes.tobytes()).hexdigest()==tile['expected_codes_sha256'],(name,'height code mismatch')
    row={'name':name,'samples':int(codes.size),'all_expected_codes_match':True,'masks':{}}
    assert {p.attribValue('name') for p in before.prims()}=={p.attribValue('name') for p in after.prims()}
    for p in before.prims():
        label=p.attribValue('name')
        if label=='height':continue
        q=volume(after,label)
        assert lattice(p)==lattice(q) and p.allVoxelsAsString()==q.allVoxelsAsString(),(name,label)
        row['masks'][label]='BIT_EXACT'
    band=np.load(ROOT/(name+'_band.npy'),mmap_mode='r')>0 if 'Context' not in name else np.zeros(codes.size,dtype=bool)
    assert np.array_equal(codes[~band],old_codes[~band]),(name,'outside band')
    row['outside_band']='BIT_EXACT'
    row['changed_height_codes']=int(np.count_nonzero(codes!=old_codes))
    row['max_abs_delta_m']=float(np.max(np.abs(actual-old)))
    row['native_export_sha256']=digest(PROOF/'after'/(name+'.bgeo.sc'))
    if 'Context' not in name:
        arr=codes.reshape(tile['resolution'][1],tile['resolution'][0])
        edges.append([arr[0].copy(),arr[-1].copy(),arr[:,0].copy(),arr[:,-1].copy()])
    report['tiles'].append(row)
    del before,after,bp,ap,old_codes,old,codes,actual,band
errors=[np.count_nonzero(edges[0][3]!=edges[1][2]),np.count_nonzero(edges[2][3]!=edges[3][2]),np.count_nonzero(edges[2][1]!=edges[0][0]),np.count_nonzero(edges[3][1]!=edges[1][0])]
assert max(errors)==0,errors
report['shared_edge_code_mismatches']=list(map(int,errors))
source=json.loads((PROJECT/'docs/tooling/sidefx/lesson06-seam-reviewed-20261018.json').read_text())
for path,expected in source['source_attribution']['source_hashes'].items():
    assert digest(path)==expected,path
    report['source_retention'][path]=expected
report['total_samples']=sum(t['samples'] for t in report['tiles'])
report['status']='NATIVE_UE_GEOMETRY_PASS'
(PROOF/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'],report['total_samples'],flush=True)
