"""Open and review the saved, baked terrain in a regular Unreal Editor."""
import unreal,json,pathlib,time,traceback
ROOT=pathlib.Path('D:/yacs/work/sa-calobra-houdini-unreal-20261016')
OUTPUT=pathlib.Path('C:/Users/akarn/OneDrive/Dokumenty/Codex/2026-10-16/referenced-chatgpt-conversation-this-is-an/outputs/SaCalobra_Unreal')
TRANSFER=ROOT/'unreal_transfer'
ASSET_ROOT='/Game/Worlds/SaCalobra_Houdini_20261016'
MAP=ASSET_ROOT+'/L_SaCalobra_LandscapeOnly'
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
save_after=None
def camera(location,target):
 p=unreal.Vector(*location);t=unreal.Vector(*target)
 unreal.EditorLevelLibrary.set_level_viewport_camera_info(p,unreal.MathLibrary.find_look_at_rotation(p,t))
def tick(delta):
 global save_after
 if save_after and time.time()>save_after:
  save_after=None
  assert levels.save_current_level()
  (OUTPUT/'final_map_saved.json').write_text(json.dumps({'map':MAP,'saved':True,'time':time.time()}))
handle=unreal.register_slate_post_tick_callback(tick)
actor_list=actors.get_all_level_actors()
landscapes=[a for a in actor_list if isinstance(a,unreal.LandscapeProxy)]
assert len(landscapes)==5
# A bake callback can leave a deferred-to-destroy, empty HDA actor in a saved map.
# Remove only such generated HDA instances after confirming all five baked terrains.
orphan_hdas=[a for a in actor_list if isinstance(a,unreal.HoudiniAssetActor)]
for a in orphan_hdas:assert actors.destroy_actor(a)
if orphan_hdas:save_after=time.time()+3
actor_list=actors.get_all_level_actors()
receipt={'world':world.get_path_name(),'fresh_editor_process':True,'native_landscapes':len(landscapes),'components':[len(a.get_components_by_class(unreal.LandscapeComponent)) for a in landscapes],
 'actors':[{'name':a.get_name(),'class':a.get_class().get_name()} for a in actor_list],
 'houdini_instances':sum(isinstance(a,unreal.HoudiniAssetActor) for a in actor_list),'time':time.time()}
assert len(landscapes)==5,receipt
assert receipt['houdini_instances']==0,receipt
(OUTPUT/'reopen_verification.json').write_text(json.dumps(receipt,indent=2))
samples=json.loads((TRANSFER/'source_transfer_verification.json').read_text())['height_samples']
context=next(a for a in landscapes if 'Context' in a.get_name())
checks=[]
for s in samples:
 hit=unreal.SystemLibrary.line_trace_single(world,unreal.Vector(s['x_cm'],s['y_cm'],200000),unreal.Vector(s['x_cm'],s['y_cm'],-10000),unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[context],unreal.DrawDebugTrace.NONE)
 if hit:
  data=hit.to_tuple();point=data[5];actor=data[9]
  checks.append(dict(s,hit=True,actor=actor.get_name(),actual_height_cm=point.z,error_cm=point.z-s['height_cm']))
 else:checks.append(dict(s,hit=False))
report={'samples':checks,'sample_count':len(checks),'misses':sum(not c['hit'] for c in checks),'max_abs_error_cm':max(abs(c.get('error_cm',0)) for c in checks)}
(OUTPUT/'unreal_height_verification.json').write_text(json.dumps(report,indent=2))
camera((350000,620000,500000),(0,35000,40000))
unreal.AutomationLibrary.set_editor_viewport_view_mode(unreal.ViewModeIndex.VMI_LIT)
unreal.log('SA_CALOBRA_REOPEN_VERIFIED '+str(receipt))

