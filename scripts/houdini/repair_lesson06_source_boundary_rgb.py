"""Native RGB-only feather outside the actual source Working extent."""
import json,sys
from pathlib import Path
import hou,numpy as np,OpenImageIO as oi
from repair_lesson06_idmap import values,volume,lattice,digest
BASE=Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06ContextColor'
O=BASE/'SourceBoundaryRGB';O.mkdir(exist_ok=True)
name=sys.argv[1];r=json.loads((BASE/'StreakRGB'/(name+'.json')).read_text())
assert not (O/(name+'.json')).exists()
hou.hipFile.load(str(BASE/'StreakRGB'/(name+'.hiplc')),suppress_save_prompt=True)
obj=hou.node('/obj/CONTEXT_COLOR_ONLY')
assert all(v.intrinsicValue('volumebordertype')=='streak' for v in obj.node('STREAK_B').geometry().prims())
lat=json.loads((BASE/'sources.json').read_text())['lattice'];sx,sy,_=lat['resolution'];ox,_,oz=lat['origin']
# An 8 m box expansion and blur is a local RGB presentation setting.
# All retained Working samples remain inside the full-weight region.
width=8.0
obj.node('WORKING_EXTENT_WITH_OUTER_FEATHER').setParms({'sizex':sx*.5+2*width,'sizez':sy*.5+2*width,'tx':ox+(sx-1)*.25,'tz':oz-(sy-1)*.25})
mask=obj.node('COLOR_WEIGHT_ONLY');mask.parm('blurradius').set(width)
layer=obj.node('RGB_COMPOSITE')
g=layer.geometry();nx,ny=r['resolution']
pixels=np.rint(np.clip(np.stack([values(g,ch).reshape(ny,nx) for ch in 'rgb'],axis=-1),0,1)*255).astype(np.uint8)
origin=lattice(volume(g,'r'))['origin']
weight=values(mask.geometry(),'mask');r['transition_pixels']=int(np.count_nonzero(weight>0));r['weight_range']=[float(weight.min()),float(weight.max())];del weight
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
for key in ['native_pixels_file','native_pixels_sha256','shared_vertex_pixels_copied','max_transport_rgb_code_delta','shared_vertex_pixels_copied']:r.pop(key,None)
r.update(file=str(out),sha256=digest(out),native_streak_channels=['r','g','b'],feather_reference='original Working source lattice',feather_expansion_m=8,feather_blur_m=8)
(O/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n')
print('THREE_CHANNEL_STREAK_READY',name,flush=True)
