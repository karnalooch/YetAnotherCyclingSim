"""All restored UE samples must equal the previously admitted native baseline."""
import json,hashlib
from pathlib import Path
from repair_lesson06_idmap import read,volume,lattice
P=Path(__file__).resolve().parents[2];BASE=P/'Saved/RuntimeProof/Lesson06DTMContext';O=P/'Saved/RuntimeProof/Lesson06ContextColor/recovery'
rows=[]
for stage,baseline in [('dtm_recovery_readback','dtm_readback_final'),('dtm_recovery_originals','dtm_readback_originals')]:
    assert (O/stage/'complete.json').exists()
    inventory=json.loads((O/stage/'inventory.json').read_text())
    assert len(inventory)==(22 if stage=='dtm_recovery_readback' else 5)
    for actor in inventory:
        name=actor['name'];a=read(BASE/baseline/(name+'.bgeo.sc'));b=read(O/stage/(name+'.bgeo.sc'))
        labels={p.attribValue('name') for p in a.prims()};assert labels=={p.attribValue('name') for p in b.prims()}
        for label in labels:
            x,y=volume(a,label),volume(b,label)
            assert lattice(x)==lattice(y),(name,label,'lattice')
            assert x.allVoxelsAsString()==y.allVoxelsAsString(),(name,label,'values')
        nx,ny,nz=volume(b,'height').resolution()
        rows.append({'name':name,'height_samples':nx*ny*nz,'volumes':sorted(labels),'status':'BIT_EXACT'})
        print('EXACT_NATIVE_RECOVERY',name,flush=True)
        del a,b,x,y
sources=json.loads((BASE/'source_retention_current.json').read_text())['files']
for file,expected in sources.items():
    with open(file,'rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==expected,file
original=json.loads((BASE/'whole_dtm_verification.json').read_text())
report={'status':'PASS_EXACT_NATIVE_RECOVERY','actors':rows,'source_cache_hashes':sources,'dtm_maximum_m':original['maximum_source_delta_m'],'dtm_samples':sum(r['height_samples'] for r in rows if r['name']!='SaCalobra_Context_Valid'),'derivation':'Restored native height and mask volumes are bit-exact to the exhaustive DTM-admitted baseline, so its bounds carry over.'}
(O/'native_verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'],flush=True)
