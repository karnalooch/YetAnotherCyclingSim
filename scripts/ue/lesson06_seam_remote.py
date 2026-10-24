"""Bounded startup observer/controller for the owner-authorized L06 handoff.

Only fixed local commands are accepted. No map load/save, terrain import,
Houdini cook, editor restart, or arbitrary remote code endpoint is provided.
"""
import json
import os
from pathlib import Path
import runpy
import time
import traceback
import unreal

PROJECT=Path(unreal.Paths.project_dir()).resolve()
ROOT=PROJECT/'Saved/RuntimeProof/Lesson06SeamRemote'
ROOT.mkdir(parents=True,exist_ok=True)
MAP='/Game/Generated/YACS/Lesson05_20261018/L_SaCalobra_Lesson05'
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert editor.get_editor_world().get_path_name().split('.')[0]==MAP
unreal.EditorPythonScripting.set_keep_python_script_alive(True)

def snapshot():
    rows=[]
    for a in actors.get_all_level_actors():
        if not isinstance(a,unreal.LandscapeProxy):continue
        mi=a.get_editor_property('landscape_material')
        tex=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(mi,'AlbedoTexture')
        components=[]
        for c in a.get_components_by_class(unreal.LandscapeComponent):
            row={'path':c.get_path_name()}
            for prop in ['heightmap_texture','weightmap_textures','section_base_x','section_base_y']:
                try:
                    v=c.get_editor_property(prop)
                    row[prop]=v.get_path_name() if hasattr(v,'get_path_name') else [x.get_path_name() for x in v] if prop=='weightmap_textures' else v
                except Exception as e:row[prop]=str(e)
            components.append(row)
        uv={}
        for p in ['OriginCm','InvSizeCm']:
            v=unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(mi,p)
            uv[p]=[v.r,v.g,v.b,v.a]
        rows.append({'name':a.get_actor_label(),'path':a.get_path_name(),'transform':str(a.get_actor_transform()),'layers':[str(l.get_name_bp()) for l in a.get_edit_layers_bp()], 'material':mi.get_path_name(),'parent':mi.get_editor_property('parent').get_path_name(),'albedo':tex.get_path_name() if tex else None,'uv':uv,'components':components})
    return {'pid':os.getpid(),'engine':unreal.SystemLibrary.get_engine_version(),'map':editor.get_editor_world().get_path_name(),'actors':rows,'dirty_maps':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],'dirty_content':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}

before=snapshot()
(ROOT/('session_'+str(os.getpid())+'_before.json')).write_text(json.dumps(before,indent=2))
if not (ROOT/'before.json').exists():
    (ROOT/'before.json').write_text(json.dumps(before,indent=2))
# A launch must not replay an import/readback left by a previous session.
last=json.loads((ROOT/'command.json').read_text(encoding='utf-8-sig')).get('id') if (ROOT/'command.json').exists() else None
last_poll=0
scopes=[]
def tick(dt):
    global last,last_poll
    if time.monotonic()-last_poll<1:return
    last_poll=time.monotonic()
    f=ROOT/'command.json'
    if not f.exists():return
    try:
        cmd=json.loads(f.read_text(encoding='utf-8-sig'))
        if cmd['id']==last:return
        last=cmd['id']
        assert editor.get_editor_world().get_path_name().split('.')[0]==MAP
        if cmd['action']=='apply':
            scopes.append(runpy.run_path(str(PROJECT/'scripts/ue/apply_lesson06_seam_materials.py'),init_globals={'before':before,'snapshot':snapshot}))
        elif cmd['action']=='camera':
            cameras=json.loads((ROOT/'cameras.json').read_text())
            view=cameras[cmd['view']]
            loc=unreal.Vector(*view['location_cm']);target=unreal.Vector(*view['target_cm'])
            editor.set_level_viewport_camera_info(loc,unreal.MathLibrary.find_look_at_rotation(loc,target))
        elif cmd['action']=='snapshot':
            (ROOT/'after.json').write_text(json.dumps(snapshot(),indent=2))
        else:raise ValueError('Unknown bounded command')
        (ROOT/'command_result.json').write_text(json.dumps({'id':last,'status':'DONE','pid':os.getpid()}))
    except Exception:
        (ROOT/'command_result.json').write_text(json.dumps({'id':last,'status':'ERROR','error':traceback.format_exc()}))
handle=unreal.register_slate_post_tick_callback(tick)
(ROOT/'ready.json').write_text(json.dumps({'pid':os.getpid(),'status':'READY','map':MAP}))
