"""Import native cached Houdini heightfields using SideFX's public Unreal API.

Run in an interactive Unreal Editor; uses asynchronous cook/bake delegates.
Source: official Houdini 22 Public API and bake_all_outputs_example.py workflow.
Terrain data and algorithms remain in Houdini. This file only orchestrates UE.
"""
import unreal, json, pathlib, time, traceback, math

ROOT=pathlib.Path('D:/yacs/work/sa-calobra-houdini-unreal-20261016')
TRANSFER=ROOT/'unreal_transfer'
OUTPUT=pathlib.Path('C:/Users/akarn/OneDrive/Dokumenty/Codex/2026-10-16/referenced-chatgpt-conversation-this-is-an/outputs/SaCalobra_Unreal')
ASSET_ROOT='/Game/Worlds/SaCalobra_Houdini_20261016'
MAP=ASSET_ROOT+'/L_SaCalobra_LandscapeOnly'
OUTPUT.mkdir(parents=True,exist_ok=True)
COMMANDS=ROOT/'editor_review_commands';COMMANDS.mkdir(exist_ok=True)
manifest=json.loads((TRANSFER/'manifest.json').read_text())
state={'status':'STARTING','tile':0,'map':MAP,'saved':False,'baked':[],'errors':[],'started':time.time()}
wrapper=None;asset=None;pending=None;tick_handle=None
executed=set(COMMANDS.glob('*.py'))
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
unreal.EditorPythonScripting.set_keep_python_script_alive(True)

def log(stage,**kwargs):
 state.update(status=stage,**kwargs)
 (OUTPUT/'import_status.json').write_text(json.dumps(state,indent=2,default=str))
 unreal.log('SA_CALOBRA_IMPORT '+json.dumps({'stage':stage,**kwargs},default=str))

def fail():
 e=traceback.format_exc();state['errors'].append(e);log('ERROR',error=e);unreal.log_error(e)

def camera(location,target):
 pos=unreal.Vector(*location);aim=unreal.Vector(*target)
 rot=unreal.MathLibrary.find_look_at_rotation(pos,aim)
 unreal.EditorLevelLibrary.set_level_viewport_camera_info(pos,rot)

def inventory():
 result=[]
 for a in actors.get_all_level_actors():
  p=a.get_actor_location();entry={'class':a.get_class().get_name(),'name':a.get_name(),'label':a.get_actor_label(),'location_cm':[p.x,p.y,p.z]}
  if isinstance(a,unreal.LandscapeProxy):
   s=a.get_actor_scale3d();origin,extent=a.get_actor_bounds(False)
   entry.update(scale=[s.x,s.y,s.z],bounds_origin_cm=[origin.x,origin.y,origin.z],bounds_extent_cm=[extent.x,extent.y,extent.z],components=len(a.get_components_by_class(unreal.LandscapeComponent)))
  result.append(entry)
 return result

def finish():
 global pending
 actor_data=inventory();landscapes=[a for a in actor_data if a['class'] in ('Landscape','LandscapeStreamingProxy')]
 if len(landscapes)!=5:raise RuntimeError('Expected five baked native Landscapes, found '+str(len(landscapes)))
 # Task-specific saves only. The pre-existing maps and accepted terrain are untouched.
 assert unreal.EditorAssetLibrary.save_directory(ASSET_ROOT,only_if_is_dirty=False,recursive=True)
 assert levels.save_current_level()
 camera((650000,1000000,800000),(0,35000,40000))
 unreal.AutomationLibrary.set_editor_viewport_view_mode(unreal.ViewModeIndex.VMI_LIT)
 log('SAVED_READY_FOR_VISUAL_REVIEW',saved=True,actors=actor_data,finished=time.time(),performance_pass=False)
 pending=None

def post_bake(w,success):
 global wrapper,pending
 try:
  w.on_post_bake_delegate.remove_callable(post_bake)
  if not success:raise RuntimeError('SideFX native bake failed: '+str(w.get_last_error_message()))
  name=manifest['tiles'][state['tile']]['name']
  state['baked'].append(name)
  if not w.delete_instantiated_asset():raise RuntimeError('Could not remove completed HDA instance after bake')
  wrapper=None;state['tile']+=1
  log('BAKED',completed=name)
  pending=finish if state['tile']==len(manifest['tiles']) else start_tile
 except Exception:fail()

def post_cook(w,success):
 if not success:
  state['errors'].append(str(w.get_last_error_message()));log('COOK_FAILED')

def post_process(w):
 try:
  w.on_post_processing_delegate.remove_callable(post_process)
  if w.get_num_outputs()<1:raise RuntimeError('Houdini produced no output')
  log('BAKING',outputs=w.get_num_outputs())
  w.on_post_bake_delegate.add_callable(post_bake)
  if not w.bake_all_outputs_with_settings(unreal.HoudiniEngineBakeOption.TO_ACTOR,replace_previous_bake=False,remove_temp_outputs_on_success=True):
   raise RuntimeError('Native bake could not start: '+str(w.get_last_error_message()))
 except Exception:fail()

def start_tile():
 global wrapper
 tile=manifest['tiles'][state['tile']]
 log('INSTANTIATING',current=tile['name'])
 api=unreal.HoudiniPublicAPIBlueprintLib.get_api()
 settings=unreal.HoudiniPublicAPISettings()
 settings.enable_auto_cook=False
 settings.enable_auto_bake=False
 settings.bake_directory_path=ASSET_ROOT+'/Baked'
 wrapper=api.instantiate(asset,unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT,settings)
 if not wrapper:raise RuntimeError('Native HDA instantiation failed: '+str(api.get_last_error_message()))
 if not wrapper.set_string_parameter_value('terrain_cache',str(TRANSFER/tile['file']).replace('\\','/')):
  raise RuntimeError('Could not select native terrain cache')
 wrapper.on_post_processing_delegate.add_callable(post_process)
 wrapper.on_post_cook_delegate.add_callable(post_cook)
 if not wrapper.recook():raise RuntimeError('Could not queue cook: '+str(wrapper.get_last_error_message()))
 log('COOKING',current=tile['name'])

def create_review_material():
 material=unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_TerrainReview',ASSET_ROOT+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
 if not material:raise RuntimeError('New review material could not be created')
 material.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
 edit=unreal.MaterialEditingLibrary
 color=edit.create_material_expression(material,unreal.MaterialExpressionConstant3Vector,-350,0)
 color.set_editor_property('constant',unreal.LinearColor(.42,.46,.49,1))
 rough=edit.create_material_expression(material,unreal.MaterialExpressionConstant,-350,140);rough.set_editor_property('r',.9)
 vis=edit.create_material_expression(material,unreal.MaterialExpressionLandscapeVisibilityMask,-350,280)
 edit.connect_material_property(color,'',unreal.MaterialProperty.MP_BASE_COLOR)
 edit.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
 edit.connect_material_property(vis,'',unreal.MaterialProperty.MP_OPACITY_MASK)
 edit.recompile_material(material)
 unreal.EditorAssetLibrary.save_loaded_asset(material)

def prepare():
 global asset,pending
 if unreal.EditorAssetLibrary.does_asset_exist(MAP):raise RuntimeError('Refusing to overwrite existing terrain-only map')
 if not levels.new_level(MAP):raise RuntimeError('Cannot create terrain-only level')
 create_review_material()
 sun=actors.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,200000),unreal.Rotator(-38,-35,0));sun.set_actor_label('Review Sun')
 light=sun.get_component_by_class(unreal.DirectionalLightComponent);light.set_mobility(unreal.ComponentMobility.MOVABLE);light.set_intensity(6)
 light.set_editor_property('atmosphere_sun_light',True)
 atmosphere=actors.spawn_actor_from_class(unreal.SkyAtmosphere,unreal.Vector());atmosphere.set_actor_label('Review Sky Atmosphere')
 sky=actors.spawn_actor_from_class(unreal.SkyLight,unreal.Vector(0,0,500000));sky.set_actor_label('Review Sky Light')
 sc=sky.get_component_by_class(unreal.SkyLightComponent);sc.set_mobility(unreal.ComponentMobility.MOVABLE);sc.set_editor_property('real_time_capture',True)
 pp=actors.spawn_actor_from_class(unreal.PostProcessVolume,unreal.Vector());pp.set_actor_label('Review Exposure');pp.set_editor_property('unbound',True)
 settings=pp.get_editor_property('settings')
 for k,v in {'override_auto_exposure_min_brightness':True,'override_auto_exposure_max_brightness':True,'auto_exposure_min_brightness':1.0,'auto_exposure_max_brightness':1.0,'override_vignette_intensity':True,'vignette_intensity':0.0}.items():settings.set_editor_property(k,v)
 pp.set_editor_property('settings',settings)
 camera((650000,1000000,800000),(0,35000,40000))
 task=unreal.AssetImportTask();task.filename=str(TRANSFER/'SaCalobra_Terrain_Transfer_v2.hdalc');task.destination_path=ASSET_ROOT+'/Houdini';task.automated=True;task.save=True;task.replace_existing=False
 unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
 paths=task.imported_object_paths
 if not paths:raise RuntimeError('Houdini asset import produced no asset')
 asset=unreal.load_asset(paths[0])
 api=unreal.HoudiniPublicAPIBlueprintLib.get_api()
 api.create_session()
 if not api.is_session_valid():raise RuntimeError('Houdini Engine session not available')
 log('SESSION_READY',hda_asset=paths[0])
 pending=start_tile

def tick(delta):
 global pending
 try:
  # Temporary local review queue; no network listener or background service.
  # Only files intentionally written for this task are evaluated. Removed on handoff.
  for p in sorted(COMMANDS.glob('*.py')):
   if p not in executed:
    executed.add(p)
    try:exec(compile(p.read_text(encoding='utf-8'),str(p),'exec'),globals())
    except Exception:fail()
  if pending:
   fn=pending;pending=None;fn()
 except Exception:fail()

tick_handle=unreal.register_slate_post_tick_callback(tick)
pending=prepare
log('WAITING_FOR_EDITOR')
