"""Fresh-process whole-grid measurements for the saved Lesson05 checkpoint."""
import argparse
import hashlib
import json
from pathlib import Path
import hou
import numpy as np

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--source-root',type=Path,required=True)
ap.add_argument('--output-root',type=Path,required=True)
ap.add_argument('--checkpoint',type=Path,required=True)
ap.add_argument('--area',choices=['working','context'],required=True)
ap.add_argument('--previous-root',type=Path,help='Unchanged Lesson05 geometry/mask checkpoint to compare')
a=ap.parse_args()
hou.setUpdateMode(hou.updateMode.Manual)
hou.hipFile.load(str(a.checkpoint),suppress_save_prompt=True,ignore_load_warnings=True)
hou.setUpdateMode(hou.updateMode.AutoUpdate)
g=hou.node('/obj').createNode('geo','MEASUREMENT_ONLY')
def file(path,name):
 n=g.createNode('file',name);n.parm('file').set(str(path));return n
def geom(n):
 n.cook(force=True);assert not n.errors(),n.errors();return n.geometry()
def vol(gg,name='height'):
 return next(p for p in gg.prims() if isinstance(p,hou.Volume) and p.attribValue('name')==name)
def data(gg,name='height'):
 return np.frombuffer(vol(gg,name).allVoxelsAsString(),np.float32)
def stats(arr):
 assert np.isfinite(arr).all()
 return {'min':float(arr.min()),'max':float(arr.max()),'mean':float(arr.mean(dtype=np.float64))}
final_node=hou.node('/obj/LESSON05_'+a.area.upper()+'/FINAL_CACHE')
final=geom(final_node)
original=a.source_root/'cache'/('lesson04_working_material_05m.bgeo.sc' if a.area=='working' else 'lesson04_context_material.bgeo.sc')
base=geom(file(original,'LESSON04'))
assert vol(final).resolution()==vol(base).resolution()
for idx in [(0,0,0),(1,0,0),(0,1,0)]:assert vol(final).indexToPos(idx)==vol(base).indexToPos(idx)
h=data(final).copy();l04=data(base).copy();mask=data(final,'scree').copy()
delta=h.astype(np.float64)-l04
assert np.max(np.abs(delta[mask==0]))==0
receipt={'area':a.area,'fresh_hip_read':True,'samples':h.size,'resolution':list(vol(final).resolution()),'origin':list(vol(final).indexToPos((0,0,0))),'delta_l05':stats(delta),'outside_scree_delta_max_m':0,'mask':stats(mask),'colors':{n:stats(data(final,n)) for n in ['r','g','b','roughness']}}
rebuilt_node=hou.node('/obj/LESSON05_'+a.area.upper()+'/CURVATURE/CURVATURE_TINT')
rebuilt=geom(rebuilt_node)
receipt['fresh_native_tail_rebuild']={n:int(np.count_nonzero(data(rebuilt,n)!=data(final,n))) for n in ['height','r','g','b','roughness']}
assert all(v==0 for v in receipt['fresh_native_tail_rebuild'].values()), 'Fresh native tail differs'
del rebuilt
rebuilt_node.parent().destroy()
shape=(vol(final).resolution()[1],vol(final).resolution()[0])
np.save(a.output_root/a.area/'preview_height.npy',h.reshape(shape)[::8,::8])
np.save(a.output_root/a.area/'preview_scree.npy',mask.reshape(shape)[::8,::8])
np.save(a.output_root/a.area/'preview_rgb.npy',np.stack([data(final,n).reshape(shape)[::8,::8] for n in ['r','g','b']],axis=-1))
if a.previous_root:
 required=['scree','cliff','pockets','broad_occlusion','curvature']
 receipt['retained_masks']={n:stats(data(final,n)) for n in required}
 for n in required:
  np.save(a.output_root/a.area/('preview_'+n+'.npy'),data(final,n).reshape(shape)[::8,::8])
 np.save(a.output_root/a.area/'preview_l04_height.npy',l04.reshape(shape)[::8,::8])
 np.save(a.output_root/a.area/'preview_l04_rgb.npy',np.stack([data(base,n).reshape(shape)[::8,::8] for n in ['r','g','b']],axis=-1))
 # Full-resolution crops supplement the whole-domain overview, never replace it.
 coarse=mask.reshape(shape)[::8,::8].copy();coarse[:20]=0;coarse[-20:]=0;coarse[:,:20]=0;coarse[:,-20:]=0
 pocket=data(final,'pockets').reshape(shape)[::8,::8]
 review_valid=(data(final,'Alpha').reshape(shape)[::8,::8]>0)&(data(base,'r').reshape(shape)[::8,::8]>.05)
 review_valid[:20]=False;review_valid[-20:]=False;review_valid[:,:20]=False;review_valid[:,-20:]=False
 scores={'scree':coarse,'pocket':coarse*pocket,'transition':np.where(coarse>0,1-np.abs(coarse-.05),0),
         'gentle':np.where(review_valid&(coarse==0)&(l04.reshape(shape)[::8,::8]>20),1/(1+np.hypot(*np.gradient(l04.reshape(shape)[::8,::8]))),0)}
 receipt['review_locations']={}
 for label,score in scores.items():
  yy,xx=np.unravel_index(np.argmax(score),score.shape);yy=int(np.clip(yy*8,128,shape[0]-129));xx=int(np.clip(xx*8,128,shape[1]-129))
  sl=np.s_[yy-128:yy+128,xx-128:xx+128]
  np.savez_compressed(a.output_root/a.area/('review_'+label+'.npz'),
   before_h=l04.reshape(shape)[sl],after_h=h.reshape(shape)[sl],mask=mask.reshape(shape)[sl],
   pockets=data(final,'pockets').reshape(shape)[sl],
   before_rgb=np.stack([data(base,n).reshape(shape)[sl] for n in ['r','g','b']],axis=-1),
   after_rgb=np.stack([data(final,n).reshape(shape)[sl] for n in ['r','g','b']],axis=-1))
  receipt['review_locations'][label]={'index':[xx,yy],'position':list(vol(final).indexToPos((xx,yy,0)))}
 previous=hou.Geometry();previous.loadFromFile(str(a.previous_root/a.area/'final.bgeo.sc'))
 receipt['unchanged_from_previous']={n:int(np.count_nonzero(data(previous,n)!=data(final,n))) for n in ['height','scree','roughness']}
 assert all(v==0 for v in receipt['unchanged_from_previous'].values())
 receipt['color_changes_from_previous']={n:int(np.count_nonzero(data(previous,n)!=data(final,n))) for n in ['r','g','b']}
 del previous
# Free non-height channels before Source+Manual composition.
del final,base,delta,mask
for n in list(g.children()):n.destroy()
source=file(a.source_root/'cache'/('source_working_05m.bgeo.sc' if a.area=='working' else 'context_source.bgeo.sc'),'SOURCE')
if a.area=='working':
 manual=file(a.source_root/'Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Layer_2_Manual_Edits.bgeo.sc','MANUAL')
 comp=g.createNode('heightfield_layer','SOURCE_PLUS_MANUAL');comp.setInput(0,source);comp.setInput(1,manual);comp.setParms({'mode':'add','layer':'height'})
else:comp=source
source_geo=geom(comp);assert data(source_geo).size==h.size
total=h.astype(np.float64)-data(source_geo)
receipt['total_procedural_vs_source_manual_m']=stats(total)
receipt['total_abs_p95_m']=float(np.percentile(np.abs(total),95))
receipt['final_cache_sha256']=hashlib.file_digest((a.output_root/a.area/'final.bgeo.sc').open('rb'),'sha256').hexdigest()
if a.previous_root:
 receipt['constant_tint_support']={}
 for stage, before_path, mask_path, mask_name in [
  ('cliff_tint', a.previous_root/a.area/'material.bgeo.sc', a.output_root/a.area/'cliff_mask.bgeo.sc', 'cliff'),
  ('scree_tint', a.output_root/a.area/'cliff_tint.bgeo.sc', a.previous_root/a.area/'transport.bgeo.sc', 'mask')]:
  mg=hou.Geometry();mg.loadFromFile(str(mask_path));zero=data(mg,mask_name)==0;del mg
  bg=hou.Geometry();bg.loadFromFile(str(before_path))
  ag=hou.Geometry();ag.loadFromFile(str(a.output_root/a.area/(stage+'.bgeo.sc')))
  row={n:int(np.count_nonzero(data(bg,n)[zero]!=data(ag,n)[zero])) for n in ['r','g','b']}
  assert all(v==0 for v in row.values()), 'Constant tint leaked beyond its mask'
  receipt['constant_tint_support'][stage]={'outside_mask_changed_samples':row,'zero_mask_samples':int(zero.sum())}
  del bg,ag,zero
(a.output_root/a.area/'fresh_measurements.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt),flush=True)
