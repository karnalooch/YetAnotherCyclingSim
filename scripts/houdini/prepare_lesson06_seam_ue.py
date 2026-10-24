"""Pack existing verified L06 global color into retained UE tile image layouts.

No terrain generation: exact registered sample copy, using the verified L05
transport convention. Original padding and Context pixels remain unchanged.
"""
import hashlib
import json
from pathlib import Path
import hou
import numpy as np
import OpenImageIO as oi
from repair_lesson06_idmap import read,values,volume,lattice,digest

PROJECT=Path(__file__).resolve().parents[2]
SOURCE=Path('D:/yacs/work/lesson06-seam-20261018/final.bgeo.sc')
BASE=Path('D:/yacs/work/lesson05-full-20261018/working/final.bgeo.sc')
OLD=Path('D:/yacs/work/lesson05-ue-20261018/transfer-height-only')
OUT=Path('D:/yacs/work/lesson06-seam-ue-20261018')
assert not (OUT/'manifest.json').exists(),'Preserve completed transfer'
OUT.mkdir(exist_ok=True)
proof=json.loads((PROJECT/'docs/tooling/sidefx/lesson06-seam-reviewed-20261018.json').read_text())
assert digest(SOURCE)==proof['fresh_replay']['checkpoints']['final']['sha256']
old=json.loads((OLD/'manifest.json').read_text())
data={}
for key,path in [('before',BASE),('after',SOURCE)]:
    geo=read(path);lat=lattice(volume(geo,'height'));nx,ny,_=lat['resolution']
    data[key]=np.stack([np.uint8(np.rint(np.clip(values(geo,n).reshape(ny,nx),0,1)*255)) for n in ['r','g','b']],axis=-1)
    if key=='after':heights=values(geo,'height').reshape(ny,nx).copy()
    del geo
report={'status':'PREPARED_COLOR_ONLY','source_sha256':digest(SOURCE),'source':str(SOURCE),'height_or_mask_payloads':False,'tiles':[],'context':'Reviewed Context RGB; geometry and masks unchanged','idmap':'Retained in Houdini; existing UE L05 review material consumes global AlbedoTexture only. No L07 detail shader is introduced.','dependency':'Current UE colors precede the retained L05 tint correction. Transfer existing reviewed colors without rebuilding any L02-05 stage.'}
g=hou.node('/obj').createNode('geo','COLOR_TRANSFER_ONLY')
context=g.createNode('file','REVIEWED_CONTEXT');context_path=Path('D:/yacs/work/lesson06-reviewed-20261018/context/final.bgeo.sc');context.parm('file').set(str(context_path))
report['context_sha256']=digest(context_path)
for tile in old['tiles']:
    source=OLD/tile['albedo'];assert digest(source)==tile['albedo_sha256']
    inp=oi.ImageInput.open(str(source));rgb=inp.read_image(format=oi.UINT8);inp.close()
    assert list(rgb.shape[:2])==[tile['resolution'][1],tile['resolution'][0]]
    old_rgb=rgb.copy()
    reference=g.createNode('file');reference.parm('file').set(str(OLD/next(iter(tile['files'].values()))))
    previous=reference
    for ch in ['r','g','b']:
        copy=g.createNode('heightfield_copylayer');copy.setInput(0,previous);copy.setParms({'srcname1':'height','dstname1':ch});previous=copy
    layer=g.createNode('heightfield_layer');layer.setInput(0,previous);layer.setInput(1,context);layer.setParms({'layer':'r g b','mode':'replace'})
    cg=layer.geometry()
    rgb=np.stack([np.uint8(np.rint(np.clip(values(cg,ch).reshape(rgb.shape[:2]),0,1)*255)) for ch in ['r','g','b']],axis=-1)
    is_context='Context' in tile['name']
    x=int(round((tile['index0'][0]-lat['origin'][0])/.5))
    y=int(round((lat['origin'][2]-tile['index0'][2])/.5))
    x0,x1=max(0,x),min(nx,x+rgb.shape[1]);y0,y1=max(0,y),min(ny,y+rgb.shape[0])
    region=(slice(y0-y,y1-y),slice(x0-x,x1-x))
    if not is_context:
        baseline=data['before'][y0:y1,x0:x1]
        assert np.array_equal(old_rgb[region][:,:,:3],baseline),('Original source transport mismatch',tile['name'])
        rgb[region][:,:,:3]=data['after'][y0:y1,x0:x1]
    changed=np.count_nonzero(np.any(rgb!=old_rgb[:,:,:3],axis=-1))
    target=OUT/(tile['name']+'_Albedo.png')
    image=oi.ImageOutput.create(str(target));image.open(str(target),oi.ImageSpec(rgb.shape[1],rgb.shape[0],rgb.shape[2],oi.UINT8));image.write_image(rgb);image.close()
    check=oi.ImageInput.open(str(target));result=check.read_image(format=oi.UINT8);check.close();assert np.array_equal(result,rgb)
    report['tiles'].append({'name':tile['name'],'albedo':str(target),'sha256':digest(target),'resolution':tile['resolution'][:2],'uv_origin_cm':tile['uv_origin_cm'],'uv_inverse_cm':tile['uv_inverse_cm'],'changed_pixels':int(changed),'original_image_sha256':digest(source)})
    print('PACKED',tile['name'],changed,flush=True)
    for n in reversed(g.children()):
        if n!=context:n.destroy()
windows=json.loads((PROJECT/'worldgen/houdini/sa_calobra/evidence/lesson06_seam/windows.json').read_text())
cameras={}
for edge,window in windows.items():
    center=window['center_index'];ix=center if edge in ['north','south'] else (0 if edge=='west' else nx-1);iy=center if edge in ['west','east'] else (0 if edge=='north' else ny-1)
    pos=[100*(lat['origin'][0]+ix*.5),100*(lat['origin'][2]-iy*.5),100*float(heights[iy,ix])]
    cameras[edge]={'target_cm':pos,'location_cm':[pos[0],pos[1]-45000,pos[2]+50000]}
(OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
proofdir=PROJECT/'Saved/RuntimeProof/Lesson06SeamRemote';proofdir.mkdir(parents=True,exist_ok=True)
(proofdir/'cameras.json').write_text(json.dumps(cameras,indent=2))
assert digest(SOURCE)==report['source_sha256']
print('PREPARED_COLOR_ONLY',flush=True)
