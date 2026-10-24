"""Set the singular native Layer parameter separately for R, G and B."""
import json,sys
from pathlib import Path
import hou,numpy as np,OpenImageIO as oi
from repair_lesson06_idmap import values,volume,lattice,digest
BASE=Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06ContextColor'
O=BASE/'StreakRGB';O.mkdir(exist_ok=True)
name=sys.argv[1];r=json.loads((BASE/(name+'.json')).read_text())
assert not (O/(name+'.json')).exists()
hou.hipFile.load(str(BASE/(name+'.hiplc')),suppress_save_prompt=True)
obj=hou.node('/obj/CONTEXT_COLOR_ONLY');first=obj.node('WORKING_EDGE_STREAK');first.parm('layer').set('r');previous=first
for ch in 'gb':
    n=obj.createNode('heightfield_layerproperty','STREAK_'+ch.upper());n.setInput(0,previous);n.setParms({'layer':ch,'doborder':1,'border':'streak','dovoltol':0});previous=n
assert all(v.intrinsicValue('volumebordertype')=='streak' for v in previous.geometry().prims())
layer=obj.node('RGB_COMPOSITE');layer.setInput(1,previous)
g=layer.geometry();nx,ny=r['resolution']
pixels=np.rint(np.clip(np.stack([values(g,ch).reshape(ny,nx) for ch in 'rgb'],axis=-1),0,1)*255).astype(np.uint8)
origin=lattice(volume(g,'r'))['origin']
hou.hipFile.save(str(O/(name+'.hiplc')))
del g;hou.hipFile.clear(suppress_save_prompt=True)
if r['working_restored']:
    lat=json.loads((BASE/'sources.json').read_text())['lattice'];sx,sy,_=lat['resolution']
    xs=np.rint((origin[0]+np.arange(nx)*.5-lat['origin'][0])/.5).astype(int);ys=np.rint((lat['origin'][2]-(origin[2]-np.arange(ny)*.5))/.5).astype(int)
    ix=np.where((xs>=0)&(xs<sx))[0];iy=np.where((ys>=0)&(ys<sy))[0]
    for k,ch in enumerate('rgb'):
        source=np.load(BASE/('source_'+ch+'.npy'),mmap_mode='r').reshape(sy,sx)
        expected=np.rint(np.clip(source[np.ix_(ys[iy],xs[ix])],0,1)*255).astype(np.uint8)
        pixels[iy[:,None],ix[None,:],k]=expected
        assert np.array_equal(pixels[iy[:,None],ix[None,:],k],expected)
out=O/(name+'.png');writer=oi.ImageOutput.create(str(out));writer.open(str(out),oi.ImageSpec(nx,ny,3,oi.UINT8));writer.write_image(pixels);writer.close()
for key in ['native_pixels_file','native_pixels_sha256','shared_vertex_pixels_copied','max_transport_rgb_code_delta']:r.pop(key,None)
r.update(file=str(out),sha256=digest(out),native_streak_channels=['r','g','b'])
(O/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n')
print('THREE_CHANNEL_STREAK_READY',name,flush=True)
