"""Exact duplicate-vertex RGB transport; no filtering, heights or masks."""
import json,hashlib,sys
from pathlib import Path
import numpy as np
from PIL import Image
O=Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06ContextColor'
if '--source-boundary' in sys.argv:O=O/'SourceBoundaryRGB'
elif '--rgb-streak-fix' in sys.argv:O=O/'StreakRGB'
rows=[json.loads(f.read_text()) for f in sorted(O.glob('SaCalobra_*.json'))]
assert len(rows)==16
images={r['name']:np.array(Image.open(r['file']).convert('RGB')) for r in rows}
allowed={r['name']:np.zeros(images[r['name']].shape[:2],bool) for r in rows}
for i,a in enumerate(rows):
    ax=a['uv_origin_cm'][0]/100+.25;az=a['uv_origin_cm'][1]/100-.25;anx,any_=a['resolution']
    for b in rows[i+1:]:
        bx=b['uv_origin_cm'][0]/100+.25;bz=b['uv_origin_cm'][1]/100-.25;bnx,bny=b['resolution']
        x0=max(ax,bx);x1=min(ax+(anx-1)*.5,bx+(bnx-1)*.5);z0=max(az-(any_-1)*.5,bz-(bny-1)*.5);z1=min(az,bz)
        if x1<x0 or z1<z0:continue
        ia=int(round((x0-ax)*2));ib=int(round((x0-bx)*2));ja=int(round((az-z1)*2));jb=int(round((bz-z1)*2));w=int(round((x1-x0)*2))+1;h=int(round((z1-z0)*2))+1
        assert w==1 or h==1,'Only shared perimeter pixels may be copied'
        images[b['name']][jb:jb+h,ib:ib+w]=images[a['name']][ja:ja+h,ia:ia+w]
        allowed[b['name']][jb:jb+h,ib:ib+w]=True
for r in rows:
    assert 'native_pixels_file' not in r
    original=np.array(Image.open(r['file']).convert('RGB'));a=images[r['name']]
    changed=np.any(a!=original,axis=-1);assert not np.any(changed & ~allowed[r['name']])
    # Working comes first and its source pixels must remain untouched.
    if r['working_restored']:assert not changed.any()
    r['native_pixels_file']=r['file'];r['native_pixels_sha256']=r['sha256']
    r['shared_vertex_pixels_copied']=int(changed.sum())
    r['max_transport_rgb_code_delta']=int(np.abs(a.astype(np.int16)-original.astype(np.int16)).max())
    path=O/(r['name']+'_Shared.png');assert not path.exists();Image.fromarray(a).save(path)
    r['file']=str(path)
    with path.open('rb') as f:r['sha256']=hashlib.file_digest(f,'sha256').hexdigest()
    (O/(r['name']+'.json')).write_text(json.dumps(r,indent=2)+'\n')
    print(r['name'],r['shared_vertex_pixels_copied'],r['max_transport_rgb_code_delta'])
