"""Read-only source attribution on the complete rectangular Working perimeter."""
import json
from pathlib import Path
import numpy as np
from repair_lesson06_idmap import read, values, digest, NAMES

root=Path('D:/yacs/work/lesson06-reviewed-20261018')
out=Path('D:/yacs/work/lesson06-seam-20261018');out.mkdir(exist_ok=True)
w=json.loads((root/'working/repair.json').read_text())['lattice']
c=json.loads((root/'context/repair.json').read_text())['lattice']
nx,ny,_=w['resolution']
ix=np.concatenate([np.arange(nx),np.arange(nx),np.zeros(ny),np.full(ny,nx-1)]).astype(int)
iy=np.concatenate([np.zeros(nx),np.full(nx,ny-1),np.arange(ny),np.arange(ny)]).astype(int)
cx=np.rint((w['origin'][0]+ix*w['x'][0]-c['origin'][0])/c['x'][0]).astype(int)
cy=np.rint((w['origin'][2]+iy*w['y'][2]-c['origin'][2])/c['y'][2]).astype(int)
report={'samples':len(ix),'mask_differences':{},'source_hashes':{}}
for name in NAMES:
    file=name.replace(' ','_')+'_mask.bgeo.sc'
    wa=values(read(root/'working'/file),'mask').reshape(ny,nx)[iy,ix]
    ca=values(read(root/'context'/file),'mask').reshape(2048,2048)[cy,cx]
    report['mask_differences'][name]={'threshold_disagreements':int(np.count_nonzero((wa>=.5)!=(ca>=.5))),'mean_abs_delta':float(np.mean(np.abs(wa-ca))),'max_abs_delta':float(np.max(np.abs(wa-ca)))}
    for area in ['working','context']:report['source_hashes'][str(root/area/file)]=digest(root/area/file)
    print(name,report['mask_differences'][name],flush=True)
for area in ['working','context']:
    geo=read(root/area/'final.bgeo.sc')
    arrays={n:values(geo,n).reshape((ny,nx) if area=='working' else (2048,2048))[(iy,ix) if area=='working' else (cy,cx)] for n in ['id','r','g','b','roughness','height']}
    if area=='working':wa=arrays
    else:ca=arrays
    report['source_hashes'][str(root/area/'final.bgeo.sc')]=digest(root/area/'final.bgeo.sc')
report['perimeter_deltas']={n:{'mean_abs':float(np.mean(np.abs(wa[n]-ca[n]))),'max_abs':float(np.max(np.abs(wa[n]-ca[n])))} for n in wa}
report['id_disagree']=int(np.count_nonzero(wa['id']!=ca['id']))
(out/'source_attribution.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['perimeter_deltas'],indent=2),flush=True)
