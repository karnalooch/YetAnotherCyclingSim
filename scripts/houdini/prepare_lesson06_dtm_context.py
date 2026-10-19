"""Import registered DTM windows with native HeightField File, then H22 pack.

No previous lesson is cooked. NumPy supplies lossless transport, nearest sample
lookup for the retained binary visibility mask, and exhaustive source checks.
"""
import hashlib,json,sys
from pathlib import Path
import hou,numpy as np
from repair_lesson06_idmap import read,volume,values,lattice,digest
from lesson04_height_encoding import height_codes,h22_transport
P=Path(__file__).resolve().parents[2];O=P/'Saved/RuntimeProof/Lesson06DTMContext'
m=json.loads((O/'windows.json').read_text());index=int(sys.argv[1]);t=m['tiles'][index];name=t['name']
obj=hou.node('/obj').createNode('geo',name,run_init_scripts=False)
f=obj.createNode('heightfield_file','ORIGINAL_DTM_WINDOW');f.setParms({'filename':str(O/(name+'.tif')),'sizemethod':'divsize','gridspacing':.5,'doclampmin':0})
x=obj.createNode('xform','GEOGRAPHIC_AXES');x.setInput(0,f)
x.setParms({'ry':90,'tx':t['x0']+(t['nx']-1)*.25,'tz':t['zmax']-(t['ny']-1)*.25})
g=hou.Geometry();g.merge(x.geometry());v=volume(g,'height');lat=lattice(v)
assert v.resolution()==(t['nx'],t['ny'],1)
np.testing.assert_allclose(lat['origin'],[t['x0'],0,t['zmax']],atol=.001,rtol=0)
np.testing.assert_allclose(lat['x'],[.5,0,0],atol=.001,rtol=0)
np.testing.assert_allclose(lat['y'],[0,0,-.5],atol=.001,rtol=0)
src=np.load(O/(name+'_source.npy'));assert np.array_equal(values(g,'height').reshape(src.shape),src)
g.deletePrims([q for q in g.prims() if q.attribValue('name')!='height'],True)
q=height_codes(src,585.9375)
decoded=(q.astype(np.float64)-32768)*585.9375/12800
error=float(np.abs(decoded-src).max());assert error<.023
v=volume(g,'height');v.setAllVoxelsFromString(h22_transport(q,585.9375).tobytes())
# Retain the original visibility data; sample its binary ownership on the new
# registered grid. Outside the original Context extent remains hidden.
c=read(P/'Saved/RuntimeProof/Lesson06GeometryRemote/final/SaCalobra_Context_Valid.bgeo.sc');cv=volume(c,'visibility');cl=lattice(cv)
ca=values(c,'visibility').reshape(cv.resolution()[1],cv.resolution()[0])
xs=t['x0']+np.arange(t['nx'])*.5;zs=t['zmax']-np.arange(t['ny'])*.5
cx=np.floor((xs-cl['origin'][0])/cl['x'][0]+.5).astype(int)
cy=np.floor((zs-cl['origin'][2])/cl['y'][2]+.5).astype(int)
vis=ca[np.ix_(np.clip(cy,0,ca.shape[0]-1),np.clip(cx,0,ca.shape[1]-1))].copy()
vis[(cy<0)|(cy>=ca.shape[0]),:]=1;vis[:,(cx<0)|(cx>=ca.shape[1])]=1
vis[np.load(O/(name+'_valid.npy'))==0]=1
assert set(np.unique(vis)).issubset({0.,1.})
vg=hou.Geometry();vg.merge(g);pv=volume(vg,'height');pv.setAttribValue('name','visibility');pv.setAllVoxelsFromString(vis.astype(np.float32).tobytes());g.merge(vg)
attrs={'unreal_output_name':name,'unreal_bake_name':name,'unreal_landscape_output_mode':0,'unreal_landscape_section_size':127,'unreal_landscape_sections_per_component':2,'unreal_landscape_layer_min':-1500.,'unreal_landscape_layer_max':1500.,'unreal_landscape_editlayer_name':'DTM_Original_05m','unreal_material':'/Game/Generated/YACS/Lesson06Seam_20261018/Materials/MI_SaCalobra_Context_Valid.MI_SaCalobra_Context_Valid','unreal_hole_material':'/Game/Generated/YACS/Lesson06Seam_20261018/Materials/MI_SaCalobra_Context_Valid.MI_SaCalobra_Context_Valid','unreal_bake_folder':'/Game/Generated/YACS/Lesson06DTMContext_20261018/Baked'}
for key,val in attrs.items():
 a=g.findPrimAttrib(key) or g.addAttrib(hou.attribType.Prim,key,val)
 for prim in g.prims():prim.setAttribValue(a,val)
# The plugin's exact attribute is unreal_material_hole (not unreal_hole_material).
a=g.addAttrib(hou.attribType.Prim,'unreal_material_hole',attrs['unreal_hole_material'])
for prim in g.prims():prim.setAttribValue(a,attrs['unreal_hole_material'])
out=O/(name+'.bgeo.sc');g.saveToFile(str(out))
re=read(out);assert volume(re,'height').allVoxelsAsString()==volume(g,'height').allVoxelsAsString()
assert volume(re,'visibility').allVoxelsAsString()==volume(g,'visibility').allVoxelsAsString()
t.update(status='PREPARED_SOURCE_EXACT',file=str(out),sha256=digest(out),expected_codes_sha256=hashlib.sha256(q.tobytes()).hexdigest(),visibility_sha256=hashlib.sha256(vis.astype(np.float32).tobytes()).hexdigest(),max_source_delta_m=error,native_source_delta_m=0.,visible_samples=int(np.count_nonzero(vis==0)),lattice=lat)
(O/(name+'.json')).write_text(json.dumps(t,indent=2)+'\n')
hou.hipFile.save(str(O/(name+'.hiplc')))
print(json.dumps(t),flush=True)
