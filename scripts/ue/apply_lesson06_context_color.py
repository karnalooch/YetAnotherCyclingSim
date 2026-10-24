"""Install prepared RGB only in the existing editor; keep all terrain payloads."""
import json, os, hashlib, runpy
from pathlib import Path
import unreal

P=Path(unreal.Paths.project_dir()).resolve();O=P/'Saved/RuntimeProof/Lesson06ContextColor'
rgb_streak_fix=globals().get('rgb_streak_fix',False)
source_boundary_fix=globals().get('source_boundary_fix',False)
north_boundary_fix=globals().get('north_boundary_fix',False)
north_mirror_fix=globals().get('north_mirror_fix',False)
north_edge_fix=globals().get('north_edge_fix',False)
north_fill_fix=globals().get('north_fill_fix',False)
north_spot_fix=globals().get('north_spot_fix',False)
if north_spot_fix:O=O/'NorthPadRGB'
elif north_fill_fix:O=O/'NorthFillRGB'
elif north_edge_fix:O=O/'NorthEdgeRGB'
elif north_mirror_fix:O=O/'NorthMirrorRGB'
elif north_boundary_fix:O=O/'NorthBoundaryRGB'
elif source_boundary_fix:O=O/'SourceBoundaryRGB'
elif rgb_streak_fix:O=O/'StreakRGB'
memory=runpy.run_path(str(Path(__file__).with_name('lesson06_memory_guard.py')))
assert os.getpid()==json.loads((P/'Saved/RuntimeProof/Lesson06SeamRemote/ready.json').read_text())['pid']
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_path_name().split('.')[0]=='/Game/Generated/YACS/Lesson05_20261018/L_SaCalobra_Lesson05'
assert not (O/'applied.json').exists()
manifest=json.loads((O/'manifest.json').read_text());assert manifest['status']=='VERIFIED_RGB_ONLY'
if north_edge_fix or north_fill_fix or north_spot_fix:
    assert manifest['working_rgb_exception_m']==4
    assert manifest['working_outside_exception']=='BIT_EXACT'
    assert manifest['max_edge_code_delta']==0
    assert all(t['working_rgb_max_changed_depth_m']<=4 for t in manifest['tiles'])
actors={a.get_actor_label():a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(a,unreal.LandscapeProxy)}
assert len(actors)==27
expected_context={'SaCalobra_DTM_Context_'+str(i).zfill(2) for i in range(22)}
assert expected_context.issubset(actors),'Restore and verify the previous 22-tile session before material handoff'
before=snapshot();(O/'before.json').write_text(json.dumps(before,indent=2))
dest='/Game/Generated/YACS/Lesson06ContextColor_20261018'
if north_spot_fix:dest+='_NorthPadRGB'
elif north_fill_fix:dest+='_NorthFillRGB'
elif north_edge_fix:dest+='_NorthEdgeRGB'
elif north_mirror_fix:dest+='_NorthMirrorRGB'
elif north_boundary_fix:dest+='_NorthBoundaryRGB'
elif source_boundary_fix:dest+='_SourceBoundaryRGB'
elif rgb_streak_fix:dest+='_RGB'
prepared=[];changes=[]
for r in manifest['tiles']:
    memory['require_headroom']()
    with open(r['file'],'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['sha256']
    assert r['height_or_mask_payload'] is False
    name=r['name'];a=actors[name];old=a.get_editor_property('landscape_material')
    source=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(old,'AlbedoTexture')
    assert not unreal.EditorAssetLibrary.does_asset_exist(dest+'/MI_'+name)
    task=unreal.AssetImportTask();task.filename=r['file'];task.destination_path=dest;task.destination_name='T_'+name;task.automated=True;task.save=False
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex=unreal.load_asset(dest+'/T_'+name);assert tex
    for prop in ['srgb','compression_settings','mip_gen_settings','filter','address_x','address_y','lod_group','max_texture_size','never_stream']:
        tex.set_editor_property(prop,source.get_editor_property(prop))
    assert [tex.blueprint_get_size_x(),tex.blueprint_get_size_y()]==r['resolution']
    assert unreal.EditorAssetLibrary.save_loaded_asset(tex)
    mi=unreal.EditorAssetLibrary.duplicate_asset(old.get_path_name().split('.')[0],dest+'/MI_'+name);assert mi
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(mi,'AlbedoTexture',tex)
    for param,key in [('OriginCm','uv_origin_cm'),('InvSizeCm','uv_inverse_cm')]:
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mi,param,unreal.LinearColor(*r[key]))
    unreal.MaterialEditingLibrary.update_material_instance(mi)
    assert unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(mi,'AlbedoTexture')==tex
    for param,key in [('OriginCm','uv_origin_cm'),('InvSizeCm','uv_inverse_cm')]:
        value=unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(mi,param)
        for actual,expected in zip([value.r,value.g,value.b,value.a],r[key]):
            assert abs(actual-expected)<=max(1e-12,abs(expected)*1e-6),(name,param,actual,expected)
    assert unreal.EditorAssetLibrary.save_loaded_asset(mi)
    export=unreal.AssetExportTask();export.object=tex;export.filename=str(O/(name+'_native.png'));export.automated=True;export.prompt=False;export.replace_identical=False;export.exporter=unreal.TextureExporterPNG()
    assert unreal.Exporter.run_asset_export_task(export)
    prepared.append((a,mi));(O/'progress.json').write_text(json.dumps({'prepared':[a.get_actor_label() for a,_ in prepared],'status':'PREPARING'}))
try:
    for a,mi in prepared:
        changes.append((a,a.get_editor_property('landscape_material'),a.get_editor_property('landscape_hole_material')))
        a.set_editor_property('landscape_material',mi);a.set_editor_property('landscape_hole_material',mi)
    after=snapshot();previous={r['name']:r for r in before['actors']};names={r['name'] for r in manifest['tiles']}
    for a in after['actors']:
        b=previous[a['name']]
        assert a['transform'].split('{rotation:')[1]==b['transform'].split('{rotation:')[1]
        for k in ['path','layers','components','parent']:assert a[k]==b[k],(a['name'],k)
        if a['name'] not in names:
            assert {k:v for k,v in a.items() if k!='transform'}=={k:v for k,v in b.items() if k!='transform'}
    (O/'after.json').write_text(json.dumps(after,indent=2))
    (O/'applied.json').write_text(json.dumps({'status':'APPLIED_RGB_ONLY','pid':os.getpid(),'map_saved':False,'actors':sorted(names),'rollback':{a.get_actor_label():m.get_path_name() for a,m,_ in changes}},indent=2))
    unreal.SystemLibrary.collect_garbage()
except Exception:
    for a,m,h in changes:a.set_editor_property('landscape_material',m);a.set_editor_property('landscape_hole_material',h)
    raise
