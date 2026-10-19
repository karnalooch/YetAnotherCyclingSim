"""Live height-only L06 layer import with the proven native H22 adapter.

Never save/reload the map, change materials or masks, or restart the editor.
The new layer is separate from all retained L02-05 layers.
"""
import json
import hashlib
import os
import time
import traceback
from pathlib import Path
import unreal

raise RuntimeError('REJECTED payload: source-relative heights exceed owner 2 m global limit; do not import.')

PROJECT=Path(unreal.Paths.project_dir()).resolve()
transfer=Path('D:/yacs/work/lesson06-geometry-20261018')
proof=PROJECT/'Saved/RuntimeProof/Lesson06GeometryRemote/apply'
assert not proof.exists(), 'Do not repeat a live layer import'
manifest=json.loads((transfer/'manifest.json').read_text())
replay=json.loads((transfer/'reopen.json').read_text())
assert manifest['status']==replay['status']=='NATIVE_GEOMETRY_PASS'
assert manifest['hip_sha256']==replay['hip_sha256']
assert manifest['height_only'] and manifest['output_mode']==1
assert not any(manifest['shared_edge_code_mismatches'])
MAP=manifest['target_map']; LAYER=manifest['delta_layer']
ROOT='/Game/Generated/YACS/Lesson06Geometry_20261018'
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert os.getpid()==31408 and unreal.SystemLibrary.get_engine_version().startswith('5.8.2-')
targets={a.get_actor_label():a for a in actors.get_all_level_actors() if isinstance(a,unreal.LandscapeProxy)}
assert set(targets)=={t['name'] for t in manifest['tiles']}
before=snapshot()
assert editor.get_editor_world().get_path_name().split('.')[0]==MAP
source_map=PROJECT/('Content/'+MAP.removeprefix('/Game/')+'.umap')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
map_hash=sha(source_map)
asset=unreal.load_asset('/Game/Worlds/SaCalobra_Houdini_20261016/Houdini/SaCalobra_Terrain_Transfer_v2')
assert asset
api=unreal.HoudiniPublicAPIBlueprintLib.get_api()
assert api.is_session_valid()
pending=[]
for tile in manifest['tiles']:
    actor=targets[tile['name']]
    assert actor.get_actor_scale3d().z==manifest['scale_z']
    assert abs(actor.get_actor_location().z)<0.001
    assert LAYER not in [str(l.get_name_bp()) for l in actor.get_edit_layers_bp()]
    for layer,filename in tile['files'].items():
        assert layer==LAYER and 'Context' not in tile['name']
        assert sha(transfer/filename)==tile['file_sha256'][layer]
        pending.append((tile,layer))
assert len(pending)==4
proof.mkdir()
(proof/'before_scene.json').write_text(json.dumps(before,indent=2))
state={'status':'READY','pid':os.getpid(),'completed':[],'map_saved':False,'restart':False,'masks_imported':False,'map_sha256_before':map_hash}
wrapper=None;current=None;processed=False;baked=None;phase='next';busy=False;wait_ticks=0
deadline=time.monotonic()+1800
def record(status,**fields):
    state.update(status=status,**fields)
    (proof/'apply.json').write_text(json.dumps(state,indent=2))
def require_isolated():
    assert editor.get_editor_world().get_path_name().split('.')[0]==MAP
def on_processed(w):
    global processed
    processed=True
def on_baked(w,success):
    global baked
    baked=bool(success)
def run_import(tile,layer):
    global wrapper,current,processed,baked,phase
    require_isolated();record('IMPORTING',tile=tile['name'],layer=layer)
    settings=unreal.HoudiniPublicAPISettings()
    settings.enable_auto_cook=False;settings.enable_auto_bake=False
    settings.bake_directory_path=ROOT+'/Baked'
    wrapper=api.instantiate(asset,unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT,settings)
    assert wrapper
    wrapper.process_component_synchronous()
    assert wrapper.set_string_parameter_value('terrain_cache',(transfer/tile['files'][layer]).as_posix())
    current=(tile,layer);processed=False;baked=None
    wrapper.on_post_processing_delegate.add_callable(on_processed)
    wrapper.on_post_bake_delegate.add_callable(on_baked)
    assert wrapper.recook(),wrapper.get_last_error_message()
    phase='cook'
def finish():
    global phase,settle_until
    for name,a in targets.items():
        if 'Context' not in name:assert unreal.CyclingLandscapeEarthworksLibrary.finish_road_earthworks_batch(a)
    phase='settle';settle_until=time.monotonic()+20
def verify_bindings():
    after=snapshot();old={a['name']:a for a in before['actors']}
    for row in after['actors']:
        previous=old[row['name']]
        for key in ['path','material','albedo','uv','parent','components']:
            assert row[key]==previous[key],(row['name'],key)
        assert row['transform'].split('{rotation:')[1]==previous['transform'].split('{rotation:')[1]
        assert all(x in row['layers'] for x in previous['layers'])
        assert set(row['layers'])-set(previous['layers'])==({LAYER} if 'Context' not in row['name'] else set())
    assert sha(source_map)==map_hash
    (proof/'after_scene.json').write_text(json.dumps(after,indent=2))
    record('APPLIED_ACTIVE_UNSAVED',map_sha256_after=sha(source_map),native_readback='PENDING')
def tick(dt):
    global busy,wait_ticks,phase,wrapper
    if busy:return
    if wait_ticks:wait_ticks-=1;return
    busy=True
    try:
        require_isolated();assert time.monotonic()<deadline
        if phase=='next':
            if pending:run_import(*pending.pop(0))
            else:finish()
        elif phase=='cook' and processed:
            assert wrapper.get_num_outputs()>0
            phase='bake'
            assert wrapper.bake_all_outputs_with_settings(unreal.HoudiniEngineBakeOption.TO_ACTOR,replace_previous_bake=False,remove_temp_outputs_on_success=True)
        elif phase=='bake' and baked is not None:
            assert baked
            tile,layer=current
            assert layer in [str(l.get_name_bp()) for l in targets[tile['name']].get_edit_layers_bp()]
            assert wrapper.delete_instantiated_asset()
            wrapper=None
            state['completed'].append(tile['name']);record('BAKED')
            phase='next';wait_ticks=30
        elif phase=='settle' and time.monotonic()>=settle_until:
            verify_bindings();unreal.unregister_slate_post_tick_callback(handle)
    except Exception:
        # Preserve evidence and remove this operation's height contribution only.
        error=traceback.format_exc();rollback={}
        for name,actor in targets.items():
            if LAYER in [str(l.get_name_bp()) for l in actor.get_edit_layers_bp()]:
                rollback[name]=bool(unreal.CyclingLandscapeEarthworksLibrary.clear_manual_layer(actor,LAYER))
        record('ERROR',error=error,rollback_height_contribution=rollback)
        unreal.unregister_slate_post_tick_callback(handle)
    finally:busy=False
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
handle=unreal.register_slate_post_tick_callback(tick)
record('READY_FOR_NATIVE_IMPORT')
