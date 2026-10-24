"""Native RGB edge extension into Context; original Working RGB is restored.

Streak is SideFX's documented boundary policy. The 128 m inset/blur choices
are local adaptation settings. Source terrain and material masks are read only.
"""
import json, sys
from pathlib import Path
import hou, numpy as np, OpenImageIO as oi
from repair_lesson06_idmap import read, volume, values, lattice, digest

P = Path(__file__).resolve().parents[2]
O = P/'Saved/RuntimeProof/Lesson06ContextColor'
O.mkdir(exist_ok=True)
OLD = Path('D:/yacs/work/lesson05-ue-20261018/transfer-height-only')
layouts = json.loads((OLD/'manifest.json').read_text())['tiles']
delivered = json.loads(Path('D:/yacs/work/lesson06-seam-ue-20261018/manifest.json').read_text())['tiles']
obj = hou.node('/obj').createNode('geo','CONTEXT_COLOR_ONLY',run_init_scripts=False)

def rgb_only(g):
    g.deletePrims([p for p in g.prims() if p.attribValue('name') not in ('r','g','b')],True)
    assert {p.attribValue('name') for p in g.prims()} == set('rgb')
    return g

def stash(g,name):
    n=obj.createNode('stash',name); n.parm('stash').set(g); return n

def file(path,name):
    n=obj.createNode('file',name);n.parm('file').set(str(path));return n

if sys.argv[1]=='sources':
    source=Path('D:/yacs/work/lesson06-reviewed-20261018/working/final.bgeo.sc')
    assert not (O/'working_rgb.bgeo.sc').exists()
    g=rgb_only(read(source));g.saveToFile(str(O/'working_rgb.bgeo.sc'))
    t=next(t for t in delivered if 'Context' in t['name'])
    assert digest(t['albedo'])==t['sha256']
    inp=oi.ImageInput.open(t['albedo']);a=inp.read_image(format=oi.FLOAT)[:,:,:3];inp.close()
    layout=next(t for t in layouts if 'Context' in t['name'])
    base=read(OLD/next(iter(layout['files'].values())))
    base.deletePrims([p for p in base.prims() if p.attribValue('name')!='height'],True)
    packed=hou.Geometry()
    for i,ch in enumerate('rgb'):
        b=hou.Geometry();b.merge(base);v=volume(b,'height');v.setAttribValue('name',ch)
        v.setAllVoxelsFromString(np.ascontiguousarray(a[:,:,i]).tobytes());packed.merge(b)
    packed.saveToFile(str(O/'context_rgb.bgeo.sc'))
    (O/'sources.json').write_text(json.dumps({'working_source':str(source),'working_source_sha256':digest(source),'context_source':t['albedo'],'context_source_sha256':t['sha256'],'lattice':lattice(volume(g,'r'))},indent=2))
    print('SOURCES_READY',flush=True);sys.exit(0)

name=sys.argv[1];out=O/(name+'.png');assert not out.exists()
w=file(O/'working_rgb.bgeo.sc','ORIGINAL_SHARP_WORKING_RGB')
c=file(O/'context_rgb.bgeo.sc','RETAINED_CONTEXT_RGB')
lat=json.loads((O/'sources.json').read_text())['lattice'];nx,ny,_=lat['resolution'];ox,_,oz=lat['origin']
is_working='Detail' in name
if is_working:
    t=next(t for t in layouts if t['name']==name)
    base=read(OLD/next(iter(t['files'].values())))
else:
    t=json.loads((P/'Saved/RuntimeProof/Lesson06DTMContext'/(name+'.json')).read_text())
    base=read(t['file'])
base.deletePrims([p for p in base.prims() if p.attribValue('name')!='height'],True)
v=volume(base,'height');bx,by,_=v.resolution();v.setAllVoxelsFromString(np.zeros((by,bx),np.float32).tobytes())
ref=stash(base,'COLOR_GRID_ONLY')
prev=ref
for ch in 'rgb':
    n=obj.createNode('heightfield_copylayer');n.setInput(0,prev);n.setParms({'srcname1':'height','dstname1':ch});prev=n
background=obj.createNode('heightfield_layer','CONTEXT_COLOR_ON_OUTPUT_GRID');background.setInput(0,prev);background.setInput(1,c);background.setParms({'layer':'r g b','mode':'replace'})
props=w
for ch in 'rgb':
    p=obj.createNode('heightfield_layerproperty','WORKING_EDGE_STREAK_'+ch.upper());p.setInput(0,props)
    p.setParms({'layer':ch,'doborder':1,'border':'streak','dovoltol':0});props=p
assert all(v.intrinsicValue('volumebordertype')=='streak' for v in props.geometry().prims())
zero=obj.createNode('heightfield_copylayer');zero.setInput(0,ref);zero.setParms({'srcname1':'height','dstname1':'mask'})
box=obj.createNode('box','WORKING_EXTENT_WITH_OUTER_FEATHER')
# Box-blur support begins outside the original Working rectangle.
expand=0 if is_working else 128
working=[t for t in layouts if 'Detail' in t['name']]
xmin=min(t['index0'][0] for t in working)-.25
xmax=max(t['index0'][0]+(t['resolution'][0]-1)*.5 for t in working)+.25
zmin=min(t['index0'][2]-(t['resolution'][1]-1)*.5 for t in working)-.25
zmax=max(t['index0'][2] for t in working)+.25
box.setParms({'sizex':xmax-xmin+expand*2,'sizey':10000,'sizez':zmax-zmin+expand*2,'tx':(xmin+xmax)/2,'tz':(zmin+zmax)/2})
mask=obj.createNode('heightfield_maskbyobject','COLOR_WEIGHT_ONLY');mask.setInput(0,zero);mask.setInput(1,box)
mask.setParms({'blurmethod':'boxblur','blurradius':0 if is_working else 128,'maxdist':10000})
layer=obj.createNode('heightfield_layer','RGB_COMPOSITE');layer.setInput(0,background);layer.setInput(1,props);layer.setInput(2,mask);layer.setParms({'layer':'r g b','mode':'replace'})
g=hou.Geometry();g.merge(layer.geometry());assert not layer.errors();rgb_only(g)
rgb=np.stack([values(g,ch).reshape(by,bx) for ch in 'rgb'],axis=-1)
pixels=np.rint(np.clip(rgb,0,1)*255).astype(np.uint8)
origin=lattice(volume(g,'r'))['origin']
hou.hipFile.save(str(O/(name+'.hiplc')))
weight=None if is_working else values(mask.geometry(),'mask').reshape(by,bx).copy()
# Release graph caches before the exact registered source-copy validation.
del g, rgb, base
hou.hipFile.clear(suppress_save_prompt=True)
report={'name':name,'file':str(out),'resolution':[bx,by],'height_or_mask_payload':False,'working_restored':is_working,'uv_origin_cm':[(origin[0]-.25)*100,(origin[2]+.25)*100,0,0],'uv_inverse_cm':[1/(bx*.5*100),-1/(by*.5*100),0,0]}
if is_working:
    xs=np.rint((origin[0]+np.arange(bx)*.5-ox)/.5).astype(int);ys=np.rint((oz-(origin[2]-np.arange(by)*.5))/.5).astype(int)
    ix=np.where((xs>=0)&(xs<nx))[0];iy=np.where((ys>=0)&(ys<ny))[0]
    for k,ch in enumerate('rgb'):
        expected=np.rint(np.clip(np.load(O/('source_'+ch+'.npy'),mmap_mode='r').reshape(ny,nx)[np.ix_(ys[iy],xs[ix])],0,1)*255).astype(np.uint8)
        # Exact registered transport avoids sub-ULP native interpolation rounding.
        # This copies existing color samples; it does not generate or filter them.
        pixels[iy[:,None],ix[None,:],k]=expected
        assert np.array_equal(pixels[np.ix_(iy,ix)][:,:,k],expected),('Working changed',name,ch)
    report['sharp_working_pixels_bitexact']=int(len(ix)*len(iy))
else:
    report['weight_range']=[float(weight.min()),float(weight.max())]
    report['transition_pixels']=int(np.count_nonzero(weight>0))
writer=oi.ImageOutput.create(str(out));writer.open(str(out),oi.ImageSpec(bx,by,3,oi.UINT8));writer.write_image(pixels);writer.close()
report['sha256']=digest(out)
(O/(name+'.json')).write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
