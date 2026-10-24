"""Read-only attribution of the transition's maximum height change."""
import json
from pathlib import Path
import numpy as np
import hou
from repair_lesson06_idmap import read,volume,values,lattice
from lesson04_height_encoding import decode_h22_readback
P=Path(__file__).resolve().parents[2]
R=Path('D:/yacs/work/lesson06-geometry-20261018')
O=P/'Saved/RuntimeProof/Lesson06GeometryRemote'
m=json.loads((R/'manifest.json').read_text()); rows=[]; peak=None
wl=json.loads(Path('D:/yacs/work/lesson06-reviewed-20261018/working/repair.json').read_text())['lattice']
xmin=wl['origin'][0];xmax=xmin+(wl['resolution'][0]-1)*.5
zmax=wl['origin'][2];zmin=zmax-(wl['resolution'][1]-1)*.5
for t in m['tiles']:
 if 'Context' in t['name']:continue
 n=t['name']; b=read(R/(n+'_baseline.bgeo.sc')); a=read(R/(n+'_final.bgeo.sc'))
 shape=(t['resolution'][1],t['resolution'][0]); before=values(b,'height').reshape(shape);after=values(a,'height').reshape(shape)
 d=after.astype(np.float64)-before; y,x=np.unravel_index(np.abs(d).argmax(),shape)
 xs=t['index0'][0]+np.arange(shape[1])*.5;zs=t['index0'][2]-np.arange(shape[0])*.5
 inside=(zs[:,None]>=zmin)&(zs[:,None]<=zmax)&(xs[None,:]>=xmin)&(xs[None,:]<=xmax)
 row={'tile':n,'native_working_changed_samples':int(np.count_nonzero(d[inside])), 'native_working_max_abs_m':float(np.abs(d[inside]).max()),'above_1m':int(np.count_nonzero(np.abs(d)>1)),'above_10m':int(np.count_nonzero(np.abs(d)>10)),'above_50m':int(np.count_nonzero(np.abs(d)>50))}
 rows.append(row)
 if peak is None or abs(d[y,x])>abs(peak['delta_m']):
  pos=volume(b,'height').indexToPos((int(x),int(y),0))
  peak={'tile':n,'pixel_xy':[int(x),int(y)],'houdini_position_m':list(pos),'before_m':float(before[y,x]),'after_m':float(after[y,x]),'delta_m':float(d[y,x]),'inside_native_working':bool(inside[y,x]),'south_of_native_working_m':float(zmin-pos[2]),'band_weight':float(np.load(R/(n+'_band.npy'),mmap_mode='r').reshape(shape)[y,x])}
  k=150; ya=max(0,y-k);yb=min(shape[0],y+k+1);xa=max(0,x-k);xb=min(shape[1],x+k+1)
  np.savez_compressed(O/'peak_window.npz',before=before[ya:yb,xa:xb],after=after[ya:yb,xa:xb],delta=d[ya:yb,xa:xb],x=xs[xa:xb],z=zs[ya:yb],peak_xy=[x-xa,y-ya])
 del b,a,before,after,d,inside
pos=hou.Vector3(peak['houdini_position_m'])
for label,path in [('ue_context',R/'SaCalobra_Context_Valid_baseline.bgeo.sc'),('original_context',Path('D:/yacs/work/lesson06-reviewed-20261018/context/final.bgeo.sc'))]:
 g=read(path);v=volume(g,'height');peak[label+'_sample_m']=v.sample(pos);peak[label+'_lattice']=lattice(v)
 if label=='ue_context':
  peak['context_visibility_sample']=volume(g,'visibility').sample(pos)
  ix,iy,_=v.posToIndex(pos);x0,y0=int(np.floor(ix)),int(np.floor(iy)); arr=values(g,'height').reshape(v.resolution()[1],v.resolution()[0]);peak['context_surrounding_heights_m']=arr[y0:y0+2,x0:x0+2].tolist()
  base=Path('D:/yacs/work/lesson04-ue-repair-20261018/transfer2/SaCalobra_Context_Valid_base.npy')
  if base.exists():
   src=np.load(base,mmap_mode='r');fx=ix-x0;fy=iy-y0
   peak['context_source_manual_bilinear_m']=float((1-fy)*((1-fx)*src[y0,x0]+fx*src[y0,x0+1])+fy*((1-fx)*src[y0+1,x0]+fx*src[y0+1,x0+1]))
 del g,v
tile=next(t for t in m['tiles'] if t['name']==peak['tile']);x,y=peak['pixel_xy']
for phase in ['before','after']:
 g=read(O/phase/(peak['tile']+'.bgeo.sc'));codes,heights=decode_h22_readback(values(g,'height'),m['scale_z']);peak['ue_'+phase+'_m']=float(heights.reshape(tile['resolution'][1],tile['resolution'][0])[y,x]);del g,codes,heights
base=Path('D:/yacs/work/lesson04-ue-repair-20261018/transfer2')/(peak['tile']+'_base.npy')
if base.exists():peak['working_padding_source_manual_m']=float(np.load(base,mmap_mode='r')[y,x])
r={'status':'DEFORMATION_CONFIRMED_IN_AUTHORIZED_BAND','peak':peak,'tiles':rows,'outside_band':'Previous full native verification BIT_EXACT; not a geography acceptance','original_cache_and_masks':'Retained; changing derived surface is nevertheless real deformation'}
(O/'peak_audit.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
