"""Read every native height against retained registered Source+neutral Manual."""
import json,sys
from pathlib import Path
import numpy as np
from prepare_lesson04_ue_repair import copy_registered
from repair_lesson06_idmap import read,values,volume,lattice
from lesson04_height_encoding import decode_h22_readback,height_codes
p=Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06GeometryRemote'
stage=sys.argv[1] if len(sys.argv)>1 else 'disabled'
root=Path('D:/yacs/work/lesson04-ue-repair-20261018/transfer2')
m=json.loads((root/'manifest.json').read_text())
r={'stage':stage,'tiles':[],'limit_m':2.0}
source=Path(__file__).resolve().parents[2]/'worldgen/houdini/sa_calobra'
working=read(source/'cache/source_working_05m.bgeo.sc')
context=read(source/'cache/context_source.bgeo.sc')
manual=read(source/'Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Layer_2_Manual_Edits.bgeo.sc')
assert np.max(np.abs(values(manual,'height')))==0,'Manual must be neutral'
import hashlib
r['source_hashes']={}
for path,expected in m['input_sha256'].items():
    with Path(path).open('rb') as f: actual_hash=hashlib.file_digest(f,'sha256').hexdigest()
    assert actual_hash==expected,path
    r['source_hashes'][path]=actual_hash
for t in m['tiles']:
    name=t['name'];g=read(p/stage/(name+'.bgeo.sc'))
    codes,actual=decode_h22_readback(values(g,'height'),585.9375)
    base=np.load(root/(name+'_base.npy')).reshape(-1)
    original=read(Path('D:/yacs/work/sa-calobra-houdini-unreal-20261016/unreal_transfer')/(name+'.bgeo.sc'))
    registered=copy_registered(original,context if 'Context' in name else working).reshape(-1)
    assert np.array_equal(base,registered),(name,'Source baseline mismatch')
    del original,registered
    delta=actual.reshape(-1)-base
    row={'name':name,'source_baseline':'BIT_EXACT_REGISTERED_SOURCE_WITH_ORIGINAL_PADDING','samples':int(base.size),'max_abs_source_delta_m':float(np.abs(delta).max()),'above_2m':int(np.count_nonzero(np.abs(delta)>2)),'source_code_mismatches':int(np.count_nonzero(codes.reshape(-1)!=height_codes(base,585.9375)))}
    if stage!='disabled':
        old=read(p/'disabled'/(name+'.bgeo.sc'))
        row['masks']={}
        for q in old.prims():
            label=q.attribValue('name')
            if label=='height':continue
            other=volume(g,label)
            assert lattice(q)==lattice(other) and q.allVoxelsAsString()==other.allVoxelsAsString(),(name,label)
            row['masks'][label]='BIT_EXACT'
    r['tiles'].append(row);print(row,flush=True)
    del g,actual,codes,base,delta
r['maximum_m']=max(t['max_abs_source_delta_m'] for t in r['tiles'])
r['total_samples']=sum(t['samples'] for t in r['tiles'])
r['status']='PASS' if r['maximum_m']<=2 else 'FAIL'
(p/('global_'+stage+'.json')).write_text(json.dumps(r,indent=2)+'\n')
print(r['status'],r['maximum_m'],flush=True)
