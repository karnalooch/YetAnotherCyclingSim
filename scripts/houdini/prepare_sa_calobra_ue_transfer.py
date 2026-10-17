"""Native SideFX transfer of the verified Sa Calobra caches into UE tile sizes.

No terrain synthesis: HeightField Crop / Layer / Mask by Object / Attribute Create.
References: SideFX Houdini 22 Unreal Landscape Basics, Outputs and Public API.
"""
import pathlib, sys, json, time, hashlib
import hou
import numpy as np

root=pathlib.Path(sys.argv[1]); out=root/'unreal_transfer';out.mkdir(exist_ok=True)
hou.hipFile.load(str(root/'SaCalobra_Pegasus.hiplc'),suppress_save_prompt=True)
hou.hscript('compproject -m 16384 16384')
hou.setUpdateMode(hou.updateMode.AutoUpdate)

def event(s,**kw):print(json.dumps({'stage':s,**kw}),flush=True)
def node(parent,t,n,inputs=(),p=None):
 a=parent.createNode(t,n,exact_type_name=True)
 for i,v in enumerate(inputs):a.setInput(i,v)
 if p:a.setParms(p)
 return a
def heightonly(parent,n,inp):
 return node(parent,'blast',n,[inp],{'group':'@name=height','negate':1})
def attr(parent,n,inp,values):
 a=node(parent,'attribcreate::2.0',n,[inp],{'numattr':len(values)})
 for i,(key,value) in enumerate(values.items(),1):
  a.parm('name'+str(i)).set(key);a.parm('class'+str(i)).set(1)
  a.parm('type'+str(i)).set(3 if isinstance(value,str) else 1 if isinstance(value,int) else 0)
  a.parm(('string' if isinstance(value,str) else 'value')+str(i)+('' if isinstance(value,str) else 'v1')).set(value)
 return a

geo=hou.node('/obj').createNode('geo','UNREAL_NATIVE_TRANSFER',run_init_scripts=False)
src=node(geo,'object_merge','FULL_REAL_DTM',p={'objpath1':'/obj/PEGASUS_DETAIL_SOURCE/GEOGRAPHIC_AXES'})
delta=node(geo,'object_merge','VERIFIED_GENTLE_DELTA',p={'objpath1':'/obj/SA_CALOBRA/DETAIL_DELTA'})
delta=heightonly(geo,'DELTA_HEIGHT_ONLY',delta)
base=heightonly(geo,'SOURCE_HEIGHT_ONLY',src)

# Bounds are on the original half-metre vertex lattice. Four tiles share edge
# samples. The padding beyond the working crop comes from the original DTM.
x0,z0=-1900.25,-1800.25
width,depth=1905.0,2540.0
all_bounds=(x0,z0,x0+2*width,z0+2*depth)
manifest={'source_hip':str(root/'SaCalobra_Pegasus.hiplc'),'tiles':[],
 'detail_source_sha256':'44aadb58f7a5027bc0573027e459bccce4f0440182a124251db619a02c6e18d7',
 'detail_spacing_m':.5,'units':'metres','epsg':25831,
 'origin_easting':483650,'origin_northing':4409899.5,
 'height_min_m':-5.,'height_max_m':1500.,
 'method':'SideFX HeightField Crop, HeightField Layer Add of verified delta, native HDA output via Houdini Engine',
 'references':['https://www.sidefx.com/docs/houdini/unreal/landscape/basics.html','https://www.sidefx.com/docs/houdini/unreal/landscape/outputs.html'],
 'adaptations':['4 native 3811 x 5081 tiles, 127 quads/section, 2 sections/component, unchanged 0.5 m lattice','Background cropped to 2017 x 2017 on its original 3.90625 m lattice; rectangle hidden beneath detailed tiles']}
mat='/Game/Worlds/SaCalobra_Houdini_20261016/Materials/M_TerrainReview.M_TerrainReview'

def finish(inp,name,index,section,sections):
 a=attr(geo,name+'_ATTRIBUTES',inp,{
  'unreal_output_name':name,'unreal_bake_name':name,
  'unreal_bake_folder':'/Game/Worlds/SaCalobra_Houdini_20261016/Baked',
  'unreal_landscape_section_size':section,'unreal_landscape_sections_per_component':sections,
  'unreal_landscape_layer_min':-5.0,'unreal_landscape_layer_max':1500.0,
  'unreal_landscape_editlayer_name':'Houdini_Source_Pegasus_Gentle',
  'unreal_material':mat,'unreal_hole_material':mat,
  'unreal_uproperty_tag_source':'SaCalobra_DTM_Pegasus_Gentle_20261016'})
 event('cook',name=name)
 a.cook(force=True)
 if a.errors():raise RuntimeError(a.errors())
 g=a.geometry();p=next(p for p in g.prims() if p.attribValue('name')=='height')
 arr=np.frombuffer(p.allVoxelsAsString(),np.float32)
 filename=name+'.bgeo.sc';g.saveToFile(str(out/filename))
 data={'index':index,'name':name,'file':filename,'resolution':p.resolution(),
  'index0':tuple(p.indexToPos((0,0,0))),'index_x':tuple(p.indexToPos((1,0,0))),'index_y':tuple(p.indexToPos((0,1,0))),
  'bounds':{'min':tuple(p.boundingBox().minvec()),'max':tuple(p.boundingBox().maxvec())},
  'height_sha256':hashlib.sha256(arr.tobytes()).hexdigest(),'min':float(arr.min()),'max':float(arr.max())}
 manifest['tiles'].append(data);event('saved',**data)
 return a

for iy in range(2):
 for ix in range(2):
  n=f'SaCalobra_Detail_{ix}_{iy}';cx=x0+(ix+.5)*width;cz=z0+(iy+.5)*depth
  crop=node(geo,'heightfield_crop',n+'_CROP',[base],{'cropmode':0,'sizex':width-.01,'sizey':depth-.01,'tx':cx,'tz':cz})
  add=node(geo,'heightfield_layer',n+'_GENTLE_DETAIL',[crop,delta],{'layer':'height','mode':1})
  a=finish(add,n,iy*2+ix,127,2)
  assert a.geometry().prims()[0].resolution()==(3811,5081,1)

context=node(geo,'file','CONTEXT_CACHE',p={'file':'$HIP/cache/context_preview.bgeo.sc'})
step=3.90625
# Odd 2017-grid crop, with centre selected on the existing lattice.
cc=node(geo,'heightfield_crop','CONTEXT_2017',[context],{'cropmode':2,'sizex':2016*step-.01,'sizey':2016*step-.01,'tx':step/2,'tz':step/2})
validity=node(geo,'heightfield_copylayer','CONTEXT_VALIDITY_MASK',[cc],{'srcname1':'Alpha','dstname1':'visibility'})
nodata=node(geo,'heightfield_remap','CONTEXT_NO_DATA_HOLES',[validity],{'layer':'visibility','masklayer':'','inputmin':0,'inputmax':1,'outputmin':1,'outputmax':0,'clampmin':1,'clampmax':1})
box=node(geo,'box','DETAILED_TERRAIN_FOOTPRINT',p={'sizex':width*2-2*step,'sizey':4000,'sizez':depth*2-2*step,'tx':x0+width,'ty':500,'tz':z0+depth})
vis=node(geo,'heightfield_maskbyobject','BACKGROUND_VISIBILITY',[nodata,box],{'masklayer':'visibility','maxdist':10000,'combine':5})
vis=node(geo,'blast','CONTEXT_EXPORT_LAYERS',[vis],{'group':'@name=height @name=visibility','negate':1})
ctx=finish(vis,'SaCalobra_Context',4,63,2)
assert ctx.geometry().prims()[0].resolution()==(2017,2017,1)

# A cached native HDA is the delivery boundary, matching Pegasus' cached workflow.
# No custom import algorithm runs in Unreal.
container=hou.node('/obj').createNode('subnet','SaCalobra_Terrain_Transfer')
output_geo=container.createNode('geo','terrain',run_init_scripts=False)
f=node(output_geo,'file','NATIVE_CACHED_HEIGHTFIELD',p={'file':str(out/manifest['tiles'][0]['file'])})
o=node(output_geo,'output','OUTPUT_LANDSCAPE',[f]);o.setDisplayFlag(True);o.setRenderFlag(True)
hda=container.createDigitalAsset(name='yacs::sa_calobra_terrain_transfer::1.1',hda_file_name=str(out/'SaCalobra_Terrain_Transfer_v2.hdalc'),description='Sa Calobra - verified Houdini terrain transfer',min_num_inputs=0,max_num_inputs=0)
ptg=hda.parmTemplateGroup();ptg.append(hou.StringParmTemplate('terrain_cache','Native terrain cache',1,default_value=(str(out/manifest['tiles'][0]['file']),),string_type=hou.stringParmType.FileReference));hda.type().definition().setParmTemplateGroup(ptg)
f.parm('file').setExpression('chs("../../terrain_cache")',hou.exprLanguage.Hscript)
hda.type().definition().updateFromNode(hda)
hda.type().definition().setParmTemplateGroup(ptg)
hda.matchCurrentDefinition()
assert hda.parm('terrain_cache') is not None
geo.setDisplayFlag(False)
hou.hipFile.save(str(root/'SaCalobra_Unreal_Transfer.hiplc'))
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
event('complete',hda=str(out/'SaCalobra_Terrain_Transfer_v2.hdalc'))
