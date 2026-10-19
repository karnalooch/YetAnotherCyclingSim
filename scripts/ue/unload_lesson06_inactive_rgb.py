"""Unload only saved, inactive RGB trial packages; never delete files or terrain."""
import unreal,json,os
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Saved/RuntimeProof/Lesson06NorthMaterial'
actors=[a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(a,unreal.LandscapeProxy)]
active=set()
for a in actors:
 for prop in ['landscape_material','landscape_hole_material']:
  m=a.get_editor_property(prop)
  if m:
   active.add(m.get_outermost().get_path_name());t=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(m,'AlbedoTexture')
   if t:active.add(t.get_outermost().get_path_name())
roots=['/Game/Generated/YACS/Lesson06ContextColor_20261018','/Game/Generated/YACS/Lesson06ContextColor_20261018_RGB']
if globals().get('north_after',False):
 roots.extend(['/Game/Generated/YACS/Lesson06ContextColor_20261018_SourceBoundaryRGB','/Game/Generated/YACS/Lesson06ContextColor_20261018_NorthBoundaryRGB'])
 roots.append('/Game/Generated/YACS/Lesson06ContextColor_20261018_NorthMirrorRGB')
 roots.append('/Game/Generated/YACS/Lesson06ContextColor_20261018_NorthEdgeRGB')
 roots.append('/Game/Generated/YACS/Lesson06ContextColor_20261018_NorthFillRGB')
packages=[]
for root in roots:
 for path in unreal.EditorAssetLibrary.list_assets(root,recursive=False,include_folder=False):
  asset=unreal.find_object(None,path)
  if asset is None:continue
  package=asset.get_outermost()
  if package.get_path_name() in active:continue
  assert isinstance(asset,(unreal.Texture2D,unreal.MaterialInstanceConstant)),path
  packages.append(package)
paths=[p.get_path_name() for p in packages]
asset=package=None
result=unreal.EditorLoadingAndSavingUtils.unload_packages(packages)
(O/('unload_old_rgb_after_north.json' if globals().get('north_after',False) else 'unload_old_rgb.json')).write_text(json.dumps({'pid':os.getpid(),'packages':paths,'result':str(result),'files_deleted':False},indent=2))
unreal.SystemLibrary.collect_garbage()
