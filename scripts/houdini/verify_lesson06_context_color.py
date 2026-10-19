"""Fresh graph replay, exact Working source transport and shared RGB edge checks."""
import json,sys
from pathlib import Path
import hou, numpy as np, OpenImageIO as oi
from repair_lesson06_idmap import values,volume,lattice,digest

O=Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06ContextColor'
SOURCE=O
if '--source-boundary' in sys.argv:O=O/'SourceBoundaryRGB'
elif '--rgb-streak-fix' in sys.argv:O=O/'StreakRGB'
rows=[];images={}
for file in sorted(O.glob('SaCalobra_*.json')):
    r=json.loads(file.read_text());assert digest(r['file'])==r['sha256']
    hou.hipFile.load(str(O/(r['name']+'.hiplc')),suppress_save_prompt=True)
    obj=hou.node('/obj/CONTEXT_COLOR_ONLY')
    if '--rgb-streak-fix' in sys.argv or '--source-boundary' in sys.argv:
        assert all(v.intrinsicValue('volumebordertype')=='streak' for v in obj.node('STREAK_B').geometry().prims())
    g=obj.node('RGB_COMPOSITE').geometry()
    nx,ny=r['resolution'];rgb=np.rint(np.clip(np.stack([values(g,ch).reshape(ny,nx) for ch in 'rgb'],axis=-1),0,1)*255).astype(np.uint8)
    native=r.get('native_pixels_file',r['file'])
    assert digest(native)==r.get('native_pixels_sha256',r['sha256'])
    inp=oi.ImageInput.open(native);pixels=inp.read_image(format=oi.UINT8);inp.close()
    origin=lattice(volume(g,'r'))['origin']
    del g
    hou.hipFile.clear(suppress_save_prompt=True)
    if r['working_restored']:
        lat=json.loads((SOURCE/'sources.json').read_text())['lattice'];sx,sy,_=lat['resolution']
        xs=np.rint((origin[0]+np.arange(nx)*.5-lat['origin'][0])/.5).astype(int);ys=np.rint((lat['origin'][2]-(origin[2]-np.arange(ny)*.5))/.5).astype(int)
        ix=np.where((xs>=0)&(xs<sx))[0];iy=np.where((ys>=0)&(ys<sy))[0]
        for k,ch in enumerate('rgb'):
            expected=np.rint(np.clip(np.load(SOURCE/('source_'+ch+'.npy'),mmap_mode='r').reshape(sy,sx)[np.ix_(ys[iy],xs[ix])],0,1)*255).astype(np.uint8)
            assert np.array_equal(pixels[iy[:,None],ix[None,:],k],expected)
            rgb[iy[:,None],ix[None,:],k]=expected
    assert np.array_equal(rgb,pixels),r['name']
    rows.append(r)
    del pixels,rgb
    print('FRESH_REPLAY_PASS',r['name'],flush=True)
assert len(rows)==16,len(rows)
# Shared geometric vertices must select the same RGB sample. A one-code bound
# allows float32 native world-coordinate sampling and final 8-bit quantization.
edges=[]
def load_pixels(r):
    inp=oi.ImageInput.open(r['file']);a=inp.read_image(format=oi.UINT8);inp.close();return a
for i,a in enumerate(rows):
    aa=load_pixels(a)
    ax=a['uv_origin_cm'][0]/100+.25;az=a['uv_origin_cm'][1]/100-.25;anx,any_=a['resolution']
    for b in rows[i+1:]:
        bx=b['uv_origin_cm'][0]/100+.25;bz=b['uv_origin_cm'][1]/100-.25;bnx,bny=b['resolution']
        x0=max(ax,bx);x1=min(ax+(anx-1)*.5,bx+(bnx-1)*.5);z0=max(az-(any_-1)*.5,bz-(bny-1)*.5);z1=min(az,bz)
        if x1<x0 or z1<z0:continue
        bb=load_pixels(b)
        ia=int(round((x0-ax)*2));ib=int(round((x0-bx)*2));ja=int(round((az-z1)*2));jb=int(round((bz-z1)*2));w=int(round((x1-x0)*2))+1;h=int(round((z1-z0)*2))+1
        delta=int(np.abs(aa[ja:ja+h,ia:ia+w].astype(np.int16)-bb[jb:jb+h,ib:ib+w].astype(np.int16)).max())
        edges.append({'a':a['name'],'b':b['name'],'samples':w*h,'max_rgb_code_delta':delta})
        assert delta==0,(a['name'],b['name'],delta)
previous_names={r['name'] for r in json.loads((SOURCE/'StreakRGB/manifest.json').read_text())['tiles']} if '--source-boundary' in sys.argv else set()
active=[r for r in rows if r['working_restored'] or r['transition_pixels']>0 or r['name'] in previous_names]
report={'status':'VERIFIED_RGB_ONLY','tiles':active,'unchanged_context_not_deployed':[r['name'] for r in rows if r not in active],'fresh_reopen':'BIT_EXACT_AFTER_REGISTERED_TRANSPORT','shared_edges':edges,'max_edge_code_delta':max(r['max_rgb_code_delta'] for r in edges)}
(O/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('VERIFIED',len(rows),'tiles',flush=True)
