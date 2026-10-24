"""Native SideFX resampling feasibility; read-only retained terrain inputs."""
import json
from pathlib import Path
import hou
import numpy as np
from repair_lesson06_idmap import read,volume,values,lattice,digest

P=Path(__file__).resolve().parents[2]
O=P/'Saved/RuntimeProof/Lesson06ResolutionProbe'
O.mkdir(exist_ok=True)
S=P/'worldgen/houdini/sa_calobra/cache'
G=Path('D:/yacs/work/lesson06-geometry-20261018')
B=Path('D:/yacs/work/lesson04-ue-repair-20261018/transfer2')
obj=hou.node('/obj').createNode('geo','SOURCE_RESOLUTION_PROBE',run_init_scripts=False)
f=obj.createNode('file','RETAINED_CONTEXT');f.parm('file').set(str(S/'context_source.bgeo.sc'))
crop=obj.createNode('heightfield_crop','BOUNDED_64M_PROBE');crop.setInput(0,f)
crop.setParms({'sizex':64,'sizey':64,'tx':1805.25,'tz':326.25})
r=obj.createNode('heightfield_resample','RESAMPLE_TO_WORKING_SPACING');r.setInput(0,crop)
r.setParms({'fixedresample':1,'divisionmode':'size','gridspacing':.5})
filters=r.parm('filter').menuItems()
w=read(S/'source_working_05m.bgeo.sc');wv=volume(w,'height')
wl=lattice(wv);wa=values(w,'height').reshape(wv.resolution()[1],wv.resolution()[0])
xs=wl['origin'][0]+np.arange(wa.shape[1])*.5
zs=wl['origin'][2]-np.arange(wa.shape[0])*.5
ix=np.where((xs>=1777)&(xs<=1805.25))[0];iy=np.where((zs>=300)&(zs<=352))[0]
points=[wv.indexToPos((int(x),int(y),0)) for y in iy for x in ix]
reference=wa[np.ix_(iy,ix)].reshape(-1).astype(float)
report={'houdini':hou.applicationVersionString(),'owner_limit_m':2,'native_filter_menu':filters,'tests':[], 'source_sha256':{str(S/n):digest(S/n) for n in ['context_source.bgeo.sc','source_working_05m.bgeo.sc']},'ue_written':False,'masks_written':False}
for filter_name in filters:
 r.parm('filter').set(filter_name);g=r.geometry();v=volume(g,'height')
 out=np.array([v.sample(p) for p in points]);d=np.abs(out-reference);j=int(d.argmax())
 row={'filter':filter_name,'resolution':v.resolution(),'samples':len(points),'max_abs_to_working_source_m':float(d.max()),'over_2m':int(np.count_nonzero(d>2)),'worst_xyz':list(points[j]),'source_m':float(reference[j]),'resampled_context_m':float(out[j])}
 report['tests'].append(row);print(row,flush=True)

# Inspect the retained visibility transition on the actual UE Context grid.
c=read(G/'SaCalobra_Context_Valid_baseline.bgeo.sc');cv=volume(c,'height')
cv.setAllVoxelsFromString(np.load(B/'SaCalobra_Context_Valid_base.npy').astype(np.float32).tobytes())
mask=values(c,'visibility').reshape(cv.resolution()[1],cv.resolution()[0])
edge=np.zeros(mask.shape,dtype=bool)
edge[:-1]|=(mask[:-1]>.5)!=(mask[1:]>.5)
edge[:,:-1]|=(mask[:,:-1]>.5)!=(mask[:,1:]>.5)
ys,xs0=np.where(edge);positions=[cv.indexToPos((int(x),int(y),0)) for y,x in zip(ys,xs0)]
rows=[]
for tile in json.loads((B/'manifest.json').read_text())['tiles']:
 name=tile['name']
 if 'Context' in name:continue
 g=read(G/(name+'_baseline.bgeo.sc'));v=volume(g,'height')
 v.setAllVoxelsFromString(np.load(B/(name+'_base.npy')).astype(np.float32).tobytes())
 nx,ny,_=v.resolution();lo=v.indexToPos((0,ny-1,0));hi=v.indexToPos((nx-1,0,0))
 for p in positions:
  if lo[0]<=p[0]<=hi[0] and lo[2]<=p[2]<=hi[2]:
   a=float(v.sample(p));b=float(cv.sample(p))
   rows.append({'tile':name,'xyz_m':list(p),'working_source_m':a,'context_source_m':b,'gap_m':abs(a-b),'minimum_residual_if_both_move_2m':max(0,abs(a-b)-4)})
 del g,v
report['visibility_transition']={'method':'Native Houdini volume samples at Context visibility-change grid points inside Working tile extent; not a UE triangle/collision proof','samples':len(rows),'over_4m':sum(x['gap_m']>4 for x in rows),'worst':max(rows,key=lambda x:x['gap_m']) if rows else None}
report['status']='RESAMPLING_IS_NOT_SOURCE_RECONSTRUCTION'
report['native_splice_types']=[n for n in hou.sopNodeTypeCategory().nodeTypes() if 'splice' in n.lower() or 'tilesplit' in n.lower()]
(O/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
hou.hipFile.save(str(O/'native_probe.hiplc'))
print(json.dumps(report['visibility_transition']),flush=True)
