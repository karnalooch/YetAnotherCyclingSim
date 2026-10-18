"""Pack exact Lesson05 code increments and native-resampled global colour tiles."""
import argparse
import hashlib
import json
from pathlib import Path
import hou
import numpy as np
import OpenImageIO as oi
from lesson04_height_encoding import height_codes, additive_codes, h22_transport, north_first_uv
from prepare_lesson04_ue_repair import height, values, copy_registered

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--lesson05-root',type=Path,required=True)
ap.add_argument('--lesson04-transfer',type=Path,required=True)
ap.add_argument('--tile-root',type=Path,required=True)
ap.add_argument('--output-root',type=Path,required=True)
a=ap.parse_args();out=a.output_root.resolve()
assert not out.exists();out.mkdir(parents=True)
assert hou.applicationVersionString()=='22.0.466'
hou.setUpdateMode(hou.updateMode.AutoUpdate)
g=hou.node('/obj').createNode('geo','LESSON05_TRANSFER')
def node(t,name,first=None,**p):
 n=g.createNode(t,name)
 if first is not None:n.setInput(0,first)
 n.setParms(p);return n
def layer(gg,name):return next(p for p in gg.prims() if isinstance(p,hou.Volume) and p.attribValue('name')==name)
def arr(gg,name):
 p=layer(gg,name);return np.frombuffer(p.allVoxelsAsString(),np.float32).reshape(p.resolution()[1],p.resolution()[0])
def digest(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
old=json.loads((a.lesson04_transfer/'manifest.json').read_text())
scale=old['scale_z']; layername='Lesson05_Increment'
report={'houdini_version':hou.applicationVersionString(),'target_map':'/Game/Generated/YACS/Lesson05_20261018/L_SaCalobra_Lesson05','output_mode':1,'height_only':True,'scale_z':scale,'quantization_step_m':scale/12800.0,'origin_z_cm':0,'delta_layer':layername,'composition':'q05 - q04 on retained verified Lesson04 layers','tiles':[],'native_readback':'NOT_RUN','source_sha256':{}}
sources={}
for area in ['working','context']:
 p=a.lesson05_root/area/'final.bgeo.sc';report['source_sha256'][str(p)]=digest(p)
 sources[area]=node('file',area.upper(),file=str(p))
edges=[]
for tile in old['tiles']:
 name=tile['name'];print('PACK',name,flush=True)
 f=node('file',name,file=str(a.tile_root/(name+'.bgeo.sc')))
 fg=f.geometry();sg=sources['context' if 'Context' in name else 'working'].geometry()
 fa=copy_registered(fg,sg)
 before=np.load(a.lesson04_transfer/(name+'_expected.npy'))
 q=additive_codes(before,fa,scale);codes=height_codes(fa,scale)
 np.save(out/(name+'_expected.npy'),fa)
 np.save(out/(name+'_lesson04.npy'),before)
 native=hou.Geometry();native.merge(fg)
 # Visibility belongs to retained source layers. H22 clear on visibility clears height.
 native.deletePrims([p for p in native.prims() if p.attribValue('name')!='height'],True)
 height(native).setAllVoxelsFromString(h22_transport(q,scale).tobytes())
 for key,val in {'unreal_output_name':name,'unreal_landscape_output_mode':1,'unreal_landscape_editlayer_name':layername,'unreal_landscape_editlayer_clear':1,'unreal_landscape_editlayer_type':1,'unreal_bake_folder':'/Game/Generated/YACS/Lesson05_20261018/Baked'}.items():
  attrib=native.findPrimAttrib(key) or native.addAttrib(hou.attribType.Prim,key,val)
  for p in native.prims():p.setAttribValue(attrib,val)
 payload=out/(name+'_Lesson05_Increment.bgeo.sc');native.saveToFile(str(payload));native.clear()
 # Native HeightField Layer resamples the Context colour into the padded tile.
 # Registered Working colour overwrites its exact overlap without interpolation.
 color=f
 for channel in ['r','g','b']:
  color=node('heightfield_copylayer','CREATE_'+channel,color,srcname1='height',dstname1=channel)
  c=node('heightfield_layer','CONTEXT_'+channel,color,mode='replace',layer=channel)
  c.setInput(1,sources['context']);color=c
 cg=color.geometry();rgb=np.stack([arr(cg,ch) for ch in ['r','g','b']],axis=-1).copy()
 src=height(sg);dst=height(fg)
 dx=dst.indexToPos((1,0,0))[0]-dst.indexToPos((0,0,0))[0]
 origin=dst.indexToPos((0,0,0));so=src.indexToPos((0,0,0))
 col=int(round((origin[0]-so[0])/dx));row=int(round((so[2]-origin[2])/dx))
 shape=arr(sg,'r').shape
 r0,r1=max(0,row),min(shape[0],row+rgb.shape[0]);c0,c1=max(0,col),min(shape[1],col+rgb.shape[1])
 for i,ch in enumerate(['r','g','b']):rgb[r0-row:r1-row,c0-col:c1-col,i]=arr(sg,ch)[r0:r1,c0:c1]
 assert np.isfinite(rgb).all()
 image=out/(name+'_Albedo.png');o=oi.ImageOutput.create(str(image));o.open(str(image),oi.ImageSpec(rgb.shape[1],rgb.shape[0],3,oi.UINT8));o.write_image(np.uint8(np.rint(np.clip(rgb,0,1)*255)));o.close()
 entry=dict(tile);entry.update(files={layername:payload.name},file_sha256={layername:digest(payload)},albedo=image.name,albedo_sha256=digest(image),expected_codes_sha256=hashlib.sha256(codes.tobytes()).hexdigest(),min_m=float(fa.min()),max_m=float(fa.max()),changed_codes_from_l04=int(np.count_nonzero(codes!=height_codes(before,scale))))
 report['tiles'].append(entry)
 if 'Context' not in name:edges.append([fa[0].copy(),fa[-1].copy(),fa[:,0].copy(),fa[:,-1].copy()])
 # Release native colour stages between tiles; keep shared source readers.
 for n in reversed(list(g.children())):
  if n not in sources.values():n.destroy()
err=[np.max(np.abs(edges[0][3]-edges[1][2])),np.max(np.abs(edges[2][3]-edges[3][2])),np.max(np.abs(edges[2][1]-edges[0][0])),np.max(np.abs(edges[3][1]-edges[1][0]))]
assert max(err)==0,err
report['prepared_full_edge_errors_m']=[float(v) for v in err]
for p,h in report['source_sha256'].items():assert digest(Path(p))==h
(out/'manifest.json').write_text(json.dumps(report,indent=2));print(json.dumps({'edges':report['prepared_full_edge_errors_m'],'tiles':len(report['tiles'])}),flush=True)
