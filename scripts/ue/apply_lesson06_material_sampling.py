"""Apply only derived RGB textures through new material instances; preserve sources."""
import json,os,hashlib
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Saved/RuntimeProof/Lesson06MaterialSampling'
assert os.getpid()==11820
assert not (O/'applied.json').exists(),'Preserve completed evidence'
names=['SaCalobra_Detail_0_0','SaCalobra_Detail_1_0','SaCalobra_Detail_0_1','SaCalobra_Detail_1_1']
actors={a.get_actor_label():a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(a,unreal.LandscapeProxy)}
assert len(actors)==27 and all(n in actors for n in names)
before=snapshot()
if not (O/'before.json').exists():(O/'before.json').write_text(json.dumps(before,indent=2))
dest='/Game/Generated/YACS/Lesson06MaterialSampling_20261018';changes=[]
try:
 for name in names:
    r=json.loads((O/(name+'_Color.json')).read_text());assert r['status']=='PREPARED_RGB_ONLY' and r['height_or_source_mask_output'] is False
    with Path(r['file']).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['sha256']
    a=actors[name];old=a.get_editor_property('landscape_material');hole=a.get_editor_property('landscape_hole_material')
    source=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(old,'AlbedoTexture')
    target=dest+'/MI_'+name
    if unreal.EditorAssetLibrary.does_asset_exist(target):
        mi=unreal.load_asset(target)
        tex=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(mi,'AlbedoTexture')
        assert tex.get_path_name().split('.')[0]==dest+'/T_'+name
        assert [tex.blueprint_get_size_x(),tex.blueprint_get_size_y()]==r['resolution']
        changes.append((a,old,hole));a.set_editor_property('landscape_material',mi);a.set_editor_property('landscape_hole_material',mi)
        continue
    task=unreal.AssetImportTask();task.filename=r['file'];task.destination_path=dest;task.destination_name='T_'+name;task.automated=True;task.save=False
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex=unreal.load_asset(dest+'/T_'+name);assert tex
    for prop in ['srgb','compression_settings','mip_gen_settings','filter','address_x','address_y','lod_group','max_texture_size','never_stream']:
        tex.set_editor_property(prop,source.get_editor_property(prop))
    assert [tex.blueprint_get_size_x(),tex.blueprint_get_size_y()]==r['resolution']
    assert unreal.EditorAssetLibrary.save_loaded_asset(tex)
    mi=unreal.EditorAssetLibrary.duplicate_asset(old.get_path_name().split('.')[0],target);assert mi
    unreal.MaterialEditingLibrary.set_material_instance_parameter_override(mi,'AlbedoTexture',True)
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(mi,'AlbedoTexture',tex)
    unreal.MaterialEditingLibrary.update_material_instance(mi)
    assert unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(mi,'AlbedoTexture')==tex
    assert unreal.EditorAssetLibrary.save_loaded_asset(mi)
    changes.append((a,old,hole));a.set_editor_property('landscape_material',mi);a.set_editor_property('landscape_hole_material',mi)
 after=snapshot();old_by={a['name']:a for a in before['actors']}
 for a in after['actors']:
    b=old_by[a['name']]
    # str(Transform) includes a temporary Python wrapper address, not scene data.
    assert a['transform'].split('{rotation:')[1]==b['transform'].split('{rotation:')[1],a['name']
    for k in ['path','layers','uv','components','parent']:assert a[k]==b[k],(a['name'],k)
    if a['name'] not in names:
        assert {k:v for k,v in a.items() if k!='transform'}=={k:v for k,v in b.items() if k!='transform'},a['name']
 (O/'after.json').write_text(json.dumps(after,indent=2))
 (O/'applied.json').write_text(json.dumps({'status':'APPLIED_RGB_ONLY','pid':os.getpid(),'actors':names,'map_saved':False,'rollback':{a.get_actor_label():old.get_path_name() for a,old,_ in changes}},indent=2))
except Exception:
 for a,old,hole in changes:a.set_editor_property('landscape_material',old);a.set_editor_property('landscape_hole_material',hole)
 raise
