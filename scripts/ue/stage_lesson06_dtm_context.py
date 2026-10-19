"""Stage owner-authorized original-DTM Context in the existing live editor."""
import json,os,time,traceback,hashlib
from pathlib import Path
import unreal
import runpy
memory_guard=runpy.run_path(str(Path(__file__).with_name('lesson06_memory_guard.py')))
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Saved/RuntimeProof/Lesson06DTMContext'
assert os.getpid()==json.loads((P/'Saved/RuntimeProof/Lesson06SeamRemote/ready.json').read_text())['pid']
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert editor.get_editor_world().get_path_name().split('.')[0]=='/Game/Generated/YACS/Lesson05_20261018/L_SaCalobra_Lesson05'
api=unreal.HoudiniPublicAPIBlueprintLib.get_api()
if not api.is_session_valid():api.create_session()
assert api.is_session_valid()
asset=unreal.load_asset('/Game/Worlds/SaCalobra_Houdini_20261016/Houdini/SaCalobra_Terrain_Transfer_v2');assert asset
tiles=json.loads((O/'windows.json').read_text())['tiles']
recovering=operation=='dtm_recover_one'
if recovering:
 command=json.loads((P/'Saved/RuntimeProof/Lesson06SeamRemote/command.json').read_text(encoding='utf-8-sig'))
 index=command['tile_index'];assert type(index) is int and 0<=index<22
 selected=[tiles[index]]
else:selected=tiles[:1] if operation=='dtm_stage_first' else tiles[1:]
if operation=='dtm_stage_remaining':
 admission=json.loads((O/'first_tile_admission.json').read_text())
 assert admission['status']=='PASS' and admission['visibility_verified'] is True
 assert admission['payload_sha256']==json.loads((O/(tiles[0]['name']+'.json')).read_text())['sha256']
pending=[]
for t in selected:
 t=json.loads((O/(t['name']+'.json')).read_text());assert t['status']=='PREPARED_SOURCE_EXACT' and t['max_source_delta_m']<.023
 with Path(t['file']).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==t['sha256']
 assert not any(a.get_actor_label()==t['name'] for a in actors.get_all_level_actors())
 pending.append(t)
state={'status':'READY','completed':[],'pid':os.getpid(),'old_context_changed':False,'map_saved':False}
recovery_root=P/'Saved/RuntimeProof/Lesson06ContextColor/recovery';recovery_root.mkdir(exist_ok=True)
receipt=recovery_root/('stage_'+str(index).zfill(2)+'.json') if recovering else O/(operation+'.json')
assert not recovering or not receipt.exists(),'Preserve recovery receipt'
def record(status,**kwargs):
 state.update(status=status,**kwargs);receipt.write_text(json.dumps(state,indent=2))
wrapper=None;current=None;phase='next';processed=False;baked=None;busy=False
deadline=time.monotonic()+3600
def on_processed(w):
 global processed
 processed=True
def on_baked(w,ok):
 global baked
 baked=bool(ok)
def tick(dt):
 global wrapper,current,phase,processed,baked,busy
 if busy:return
 busy=True
 try:
  assert time.monotonic()<deadline
  if phase=='next':
   if not pending:
    record('STAGED_HIDDEN');unreal.unregister_slate_post_tick_callback(handle);return
   memory=memory_guard['require_headroom']()
   current=pending.pop(0);record('IMPORTING',current=current['name'],memory_before=memory,payload_sha256=current['sha256'])
   settings=unreal.HoudiniPublicAPISettings();settings.enable_auto_cook=False;settings.enable_auto_bake=False
   settings.bake_directory_path='/Game/Generated/YACS/Lesson06DTMContext_20261018/Baked'
   wrapper=api.instantiate(asset,unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT,settings);assert wrapper
   wrapper.process_component_synchronous();assert wrapper.set_string_parameter_value('terrain_cache',Path(current['file']).as_posix())
   processed=False;baked=None
   wrapper.on_post_processing_delegate.add_callable(on_processed);wrapper.on_post_bake_delegate.add_callable(on_baked)
   assert wrapper.recook();phase='cook'
  elif phase=='cook' and processed:
   assert wrapper.get_num_outputs()>0;phase='bake'
   assert wrapper.bake_all_outputs_with_settings(unreal.HoudiniEngineBakeOption.TO_ACTOR,replace_previous_bake=False,remove_temp_outputs_on_success=True)
  elif phase=='bake' and baked is not None:
   assert baked
   found=[a for a in actors.get_all_level_actors() if isinstance(a,unreal.LandscapeProxy) and a.get_actor_label()==current['name']]
   assert len(found)==1,(current['name'],[a.get_actor_label() for a in actors.get_all_level_actors() if isinstance(a,unreal.LandscapeProxy)])
   actor=found[0];actor.set_is_temporarily_hidden_in_editor(True);actor.set_actor_hidden_in_game(True)
   reference=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='SaCalobra_Context_Valid')
   actor.set_editor_property('landscape_material',reference.get_editor_property('landscape_material'))
   actor.set_editor_property('landscape_hole_material',reference.get_editor_property('landscape_hole_material'))
   assert unreal.CyclingLandscapeEarthworksLibrary.register_dtm_landscape_visibility(actor)
   assert unreal.CyclingLandscapeEarthworksLibrary.finish_road_earthworks_batch(actor)
   row={'name':current['name'],'path':actor.get_path_name(),'transform':str(actor.get_actor_transform()),'scale_z':actor.get_actor_scale3d().z,'origin_z':actor.get_actor_location().z,'layers':[str(l.get_name_bp()) for l in actor.get_edit_layers_bp()],'target_layers':[str(n) for n in actor.get_target_layer_names(True)]}
   state['completed'].append(row);record('BAKED_HIDDEN')
   assert wrapper.delete_instantiated_asset();wrapper=None
   unreal.SystemLibrary.collect_garbage()
   state['memory_after']=memory_guard['memory_status']()
   phase='next'
 except Exception:
  record('ERROR',error=traceback.format_exc());unreal.unregister_slate_post_tick_callback(handle)
 finally:busy=False
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
handle=unreal.register_slate_post_tick_callback(tick)
record('WAITING_FOR_EDITOR_TICK')
