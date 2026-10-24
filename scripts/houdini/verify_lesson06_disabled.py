"""Confirm live layer disable restored every exported height/mask sample."""
import json
import sys
from pathlib import Path
from repair_lesson06_idmap import read,volume,lattice

p=Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06GeometryRemote'
stage=sys.argv[1] if len(sys.argv)>1 else 'disabled'
assert (p/stage/'complete.json').exists()
names=[r['name'] for r in json.loads((p/'before/inventory.json').read_text())]
r={'status':'VERIFYING','tiles':[],'total_height_samples':0}
for name in names:
    before=read(p/'before'/(name+'.bgeo.sc'))
    now=read(p/stage/(name+'.bgeo.sc'))
    row={'name':name,'volumes':{}}
    assert {q.attribValue('name') for q in before.prims()}=={q.attribValue('name') for q in now.prims()}
    for q in before.prims():
        label=q.attribValue('name');other=volume(now,label)
        assert lattice(q)==lattice(other)
        assert q.allVoxelsAsString()==other.allVoxelsAsString(),(name,label)
        row['volumes'][label]='BIT_EXACT'
        if label=='height':
            nx,ny,nz=q.resolution();r['total_height_samples']+=nx*ny*nz
    r['tiles'].append(row)
    print('RESTORED',name,flush=True)
r['status']='PRE_TRANSITION_HEIGHTS_AND_MASKS_RESTORED'
(p/(stage+'_verification.json')).write_text(json.dumps(r,indent=2)+'\n')
print(r['status'],r['total_height_samples'],flush=True)
