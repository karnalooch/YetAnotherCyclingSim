"""Native SideFX color-only feather from retained delivered color maps.

Original height/mask caches are read-only. Output payloads are RGB PNGs only.
128 m inset/blur is a YACS preview setting, not a SideFX tutorial constant.
"""
import json,sys
from pathlib import Path
import hou,numpy as np,OpenImageIO as oi
from repair_lesson06_idmap import read,volume,values,digest,lattice
P=Path(__file__).resolve().parents[2];O=P/'Saved/RuntimeProof/Lesson06MaterialSampling'
O.mkdir(exist_ok=True)
old=Path('D:/yacs/work/lesson05-ue-20261018/transfer-height-only')
layout=json.loads((old/'manifest.json').read_text())['tiles']
delivered=json.loads(Path('D:/yacs/work/lesson06-seam-ue-20261018/manifest.json').read_text())['tiles']
index=int(sys.argv[1]);tile=delivered[index];assert 'Detail' in tile['name']
out=O/(tile['name']+'_Color.png');assert not out.exists()
geo=hou.node('/obj').createNode('geo','L06_COLOR_SAMPLING',run_init_scripts=False)

def color_input(t,label):
    image=Path(t['albedo']);assert digest(image)==t['sha256']
    inp=oi.ImageInput.open(str(image));rgb=inp.read_image(format=oi.FLOAT)[:,:,:3];inp.close()
    source=next(x for x in layout if x['name']==t['name'])
    base=read(old/next(iter(source['files'].values())))
    base.deletePrims([p for p in base.prims() if p.attribValue('name')!='height'],True)
    h=volume(base,'height');h.setAllVoxelsFromString(np.zeros(rgb.shape[:2],np.float32).tobytes())
    packed=hou.Geometry()
    for i,ch in enumerate('rgb'):
        g=hou.Geometry();g.merge(base);v=volume(g,'height');v.setAttribValue('name',ch)
        v.setAllVoxelsFromString(np.ascontiguousarray(rgb[:,:,i]).tobytes());packed.merge(g)
    f=geo.createNode('stash',label);f.parm('stash').set(packed)
    return f,base,rgb

w,base,rgb=color_input(tile,'RETAINED_WORKING_RGB')
c,_,_=color_input(next(t for t in delivered if 'Context' in t['name']),'RETAINED_CONTEXT_RGB')
flat=geo.createNode('stash','COLOR_WEIGHT_REFERENCE_ONLY');flat.parm('stash').set(base)
zero_mask=geo.createNode('heightfield_copylayer','NEW_COLOR_WEIGHT_ONLY');zero_mask.setInput(0,flat)
zero_mask.setParms({'srcname1':'height','dstname1':'mask'})
lat=json.loads(Path('D:/yacs/work/lesson06-seam-20261018/repair.json').read_text())['lattice']
nx,ny,_=lat['resolution'];ox,_,oz=lat['origin'];sx=nx*.5;sz=ny*.5
box=geo.createNode('box','INNER_WORKING_COLOR_REGION')
box.setParms({'sizex':sx-256,'sizey':10000,'sizez':sz-256,'tx':ox+(nx-1)*.25,'tz':oz-(ny-1)*.25})
mask=geo.createNode('heightfield_maskbyobject','COLOR_ONLY_FALLOFF')
mask.setInput(0,zero_mask);mask.setInput(1,box)
mask.setParms({'invertmask':1,'blurmethod':'boxblur','blurradius':128,'maxdist':10000})
layer=geo.createNode('heightfield_layer','RGB_ONLY_COMPOSITE')
layer.setInput(0,w);layer.setInput(1,c);layer.setInput(2,mask)
layer.setParms({'layer':'r g b','mode':'replace','masklayer':'mask'})
g=layer.geometry();assert not layer.errors(),layer.errors()
assert {p.attribValue('name') for p in g.prims()}==set('rgb')
result=np.stack([values(g,ch).reshape(rgb.shape[:2]) for ch in 'rgb'],axis=-1)
weight=values(mask.geometry(),'mask').reshape(rgb.shape[:2]);core=weight==0
np.testing.assert_array_equal(result[core],rgb[core])
pixels=np.rint(np.clip(result,0,1)*255).astype(np.uint8)
writer=oi.ImageOutput.create(str(out));writer.open(str(out),oi.ImageSpec(pixels.shape[1],pixels.shape[0],3,oi.UINT8));writer.write_image(pixels);writer.close()
inp=oi.ImageInput.open(str(out));check=inp.read_image(format=oi.UINT8);inp.close();assert np.array_equal(check,pixels)
report={'name':tile['name'],'status':'PREPARED_RGB_ONLY','file':str(out),'sha256':digest(out),'source_sha256':tile['sha256'],
        'resolution':tile['resolution'],'unchanged_core_pixels':int(core.sum()),'changed_pixels':int(np.any(pixels!=np.rint(rgb*255).astype(np.uint8),axis=-1).sum()),
        'native_nodes':['heightfield_maskbyobject','heightfield_layer'],'inset_m':128,'blur_radius_m':128,'height_or_source_mask_output':False}
(O/(tile['name']+'_Color.json')).write_text(json.dumps(report,indent=2))
hou.hipFile.save(str(O/(tile['name']+'_Color.hiplc')))
print(json.dumps(report),flush=True)
