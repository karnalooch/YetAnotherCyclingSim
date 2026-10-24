"""Exhaustive native UE Context source-height and visibility admission."""
import json,hashlib,sys
from pathlib import Path
import numpy as np
from repair_lesson06_idmap import read,volume,values,lattice,digest
from lesson04_height_encoding import decode_h22_readback
P=Path(__file__).resolve().parents[2];O=P/'Saved/RuntimeProof/Lesson06DTMContext'
stage=sys.argv[1];root=O/stage
assert (root/'complete.json').exists()
inventory=json.loads((root/'inventory.json').read_text())
report={'status':'VERIFYING','reference':'Original retained 0.5 m DTM for entire domain','limit_m':2.,'tiles':[]}
for actor in inventory:
 name=actor['name'];t=json.loads((O/(name+'.json')).read_text());g=read(root/(name+'.bgeo.sc'))
 p=volume(g,'height');assert p.resolution()==(t['nx'],t['ny'],1)
 lat=lattice(p)
 for key in ['origin','x','y']:np.testing.assert_allclose(lat[key],t['lattice'][key],atol=.002,rtol=0)
 assert abs(actor['location_cm'][2])<.001
 codes,actual=decode_h22_readback(values(g,'height'),actor['scale'][2])
 src=np.load(O/(name+'_source.npy')).reshape(-1)
 error=np.abs(actual-src);maximum=float(error.max())
 assert maximum<=2,(name,maximum)
 vis=values(g,'visibility');assert hashlib.sha256(vis.tobytes()).hexdigest()==t['visibility_sha256'],name
 assert actor['hole_material']==actor['material'] and actor['opacity_mask_input']!='None'
 row={'name':name,'samples':int(src.size),'maximum_source_delta_m':maximum,'above_2m':int(np.count_nonzero(error>2)),'visibility':'BIT_EXACT_DERIVED_FROM_RETAINED_MASK','scale_z':actor['scale'][2]}
 report['tiles'].append(row);print(row,flush=True)
 del g,p,actual,codes,src,error,vis
report.update(status='PASS',maximum_source_delta_m=max(t['maximum_source_delta_m'] for t in report['tiles']),samples=sum(t['samples'] for t in report['tiles']))
(O/(stage+'_verification.json')).write_text(json.dumps(report,indent=2)+'\n')
if len(inventory)==1:
 first=json.loads((O/(inventory[0]['name']+'.json')).read_text())
 (O/'first_tile_admission.json').write_text(json.dumps({'status':'PASS','visibility_verified':True,'payload_sha256':first['sha256'],'native_report':stage+'_verification.json'},indent=2))
print(report['status'],report['samples'],report['maximum_source_delta_m'],flush=True)
