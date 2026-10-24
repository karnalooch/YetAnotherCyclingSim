"""Native RGB-only feather outside the actual source Working extent."""
import json,sys
from pathlib import Path
import hou,numpy as np,OpenImageIO as oi
from repair_lesson06_idmap import values,volume,lattice,digest
BASE=Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06ContextColor'
edge='--edge' in sys.argv
mirror='--mirror' in sys.argv or edge
O=BASE/('NorthEdgeRGB' if edge else 'NorthMirrorRGB' if mirror else 'NorthBoundaryRGB');O.mkdir(exist_ok=True)
name=sys.argv[1];r=json.loads((BASE/'SourceBoundaryRGB'/(name+'.json')).read_text())
assert not (O/(name+'.json')).exists()
hou.hipFile.load(str(BASE/'SourceBoundaryRGB'/(name+'.hiplc')),suppress_save_prompt=True)
obj=hou.node('/obj/CONTEXT_COLOR_ONLY')
assert all(v.intrinsicValue('volumebordertype')=='streak' for v in obj.node('STREAK_B').geometry().prims())
lat=json.loads((BASE/'sources.json').read_text())['lattice'];sx,sy,_=lat['resolution'];ox,_,oz=lat['origin']
# Native-only wider presentation blend on the north background side.
width=32.0
old=obj.node('RGB_COMPOSITE');old.setName('RETAINED_SOURCE_BOUNDARY_RGB')
box=obj.createNode('box','NORTH_WIDE_WORKING_EXTENT')
box.setParms({'sizex':sx*.5+2*width,'sizey':10000,'sizez':sy*.5+2*width,'tx':ox+(sx-1)*.25,'tz':oz-(sy-1)*.25})
zero=obj.node('COLOR_WEIGHT_ONLY').inputs()[0]
mask=obj.createNode('heightfield_maskbyobject','NORTH_COLOR_FEATHER');mask.setInput(0,zero);mask.setInput(1,box);mask.setParms({'blurmethod':'boxblur','blurradius':width,'maxdist':10000})
wide=obj.createNode('heightfield_layer','NORTH_WIDE_RGB');wide.setInput(0,old.inputs()[0]);wide.setInput(1,obj.node('STREAK_B'));wide.setInput(2,mask);wide.setParms({'layer':'r g b','mode':'replace'})
if mirror:
    # Presentation-only reflection of existing RGB, not terrain or source masks.
    # Native Transform replaces constant border streak with spatially varying RGB.
    reflected=obj.createNode('xform','NORTH_REFLECTED_RGB_ONLY')
    reflected.setInput(0,obj.node('STREAK_B'))
    if edge:
        # Owner-authorized presentation-only <=4 m Working strip. Native nodes
        # borrow RGB 4 m inward; no spatial resampling/downscaling of output.
        edgebox=obj.createNode('box','RGB_EDGE_SUPPORT')
        edgebox.setParms({'sizex':20000,'sizey':10000,'sizez':10000,'tz':oz+.25+5000})
        edgeweight=obj.createNode('heightfield_maskbyobject','RGB_EDGE_FEATHER')
        edgeweight.setInput(0,zero);edgeweight.setInput(1,edgebox)
        edgeweight.setParms({'blurmethod':'boxblur','blurradius':3.5,'maxdist':10000})
        remap=obj.createNode('heightfield_remap','RGB_EDGE_WEIGHT')
        remap.setInput(0,edgeweight)
        remap.setParms({'layer':'mask','inputmax':.25,'clampmin':1,'clampmax':1})
        shifted=obj.createNode('xform','RGB_INTERIOR_REFERENCE')
        shifted.setInput(0,obj.node('STREAK_B'));shifted.setParms({'tz':4})
        corrected=obj.createNode('heightfield_layer','WORKING_EDGE_RGB')
        corrected.setInput(0,old);corrected.setInput(1,shifted);corrected.setInput(2,remap)
        corrected.setParms({'layer':'r g b','mode':'replace'})
        rgb_only=obj.createNode('blast','EDGE_RGB_ONLY')
        rgb_only.setInput(0,corrected)
        rgb_only.setParms({'group':'@name=r @name=g @name=b','negate':True})
        reflected.setInput(0,rgb_only)
    reflected.setParms({'sz':-1,'pz':oz})
    assert {v.attribValue('name') for v in reflected.geometry().prims()}==set('rgb')
    wide.setInput(1,reflected)
selector=obj.createNode('box','NORTH_BACKGROUND_ONLY');selector.setParms({'sizex':20000,'sizey':10000,'sizez':10000,'tz':oz+.25+5000})
only=obj.createNode('heightfield_maskbyobject','NORTH_PRESENTATION_SELECTION');only.setInput(0,zero);only.setInput(1,selector);only.setParms({'blurmethod':'boxblur','blurradius':0,'maxdist':10000})
layer=obj.createNode('heightfield_layer','RGB_COMPOSITE');layer.setInput(0,old);layer.setInput(1,wide);layer.setInput(2,only);layer.setParms({'layer':'r g b','mode':'replace'})
if edge:layer.setInput(0,corrected)
g=layer.geometry();nx,ny=r['resolution']
pixels=np.rint(np.clip(np.stack([values(g,ch).reshape(ny,nx) for ch in 'rgb'],axis=-1),0,1)*255).astype(np.uint8)
origin=lattice(volume(g,'r'))['origin']
weight=values(mask.geometry(),'mask');r['transition_pixels']=int(np.count_nonzero(weight>0));r['weight_range']=[float(weight.min()),float(weight.max())];del weight
hou.hipFile.save(str(O/(name+'.hiplc')))
del g;hou.hipFile.clear(suppress_save_prompt=True)
if r['working_restored']:
    lat=json.loads((BASE/'sources.json').read_text())['lattice'];sx,sy,_=lat['resolution']
    xs=np.rint((origin[0]+np.arange(nx)*.5-lat['origin'][0])/.5).astype(int);ys=np.rint((lat['origin'][2]-(origin[2]-np.arange(ny)*.5))/.5).astype(int)
    ix=np.where((xs>=0)&(xs<sx))[0];iy=np.where((ys>8 if edge else ys>=0)&(ys<sy))[0]
    for k,ch in enumerate('rgb'):
        source=np.load(BASE/('source_'+ch+'.npy'),mmap_mode='r').reshape(sy,sx)
        expected=np.rint(np.clip(source[np.ix_(ys[iy],xs[ix])],0,1)*255).astype(np.uint8)
        pixels[iy[:,None],ix[None,:],k]=expected
        assert np.array_equal(pixels[iy[:,None],ix[None,:],k],expected)
out=O/(name+'.png');writer=oi.ImageOutput.create(str(out));writer.open(str(out),oi.ImageSpec(nx,ny,3,oi.UINT8));writer.write_image(pixels);writer.close()
for key in ['native_pixels_file','native_pixels_sha256','shared_vertex_pixels_copied','max_transport_rgb_code_delta','shared_vertex_pixels_copied']:r.pop(key,None)
r.update(file=str(out),sha256=digest(out),native_streak_channels=['r','g','b'],feather_reference='original Working source lattice',feather_expansion_m=32,feather_blur_m=32,side="north_only")
if mirror:r['extension']='Native Transform reflection of RGB only about original north edge; local presentation adaptation'
if edge:
    r['working_rgb_exception_m']=4
    r['working_restored']='EXACT_OUTSIDE_AUTHORIZED_NORTH_4M'
    r['edge_recipe']='Native RGB Transform +4m, Mask by Geometry box blur 3.5m, Remap 0..0.25 to 0..1, HeightField Layer; original caches untouched'
(O/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n')
print('THREE_CHANNEL_STREAK_READY',name,flush=True)
