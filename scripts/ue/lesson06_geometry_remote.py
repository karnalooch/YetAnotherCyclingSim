"""Fixed L06 geometry handoff using retained native Houdini Engine adapters."""
import os
import json
import runpy
from pathlib import Path
import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
PROOF = PROJECT/'Saved/RuntimeProof/Lesson06GeometryRemote'
PROOF.mkdir(exist_ok=True)
current = snapshot()
if operation in ('geometry_apply', 'geometry_show_after'):
    raise RuntimeError('Rejected transition: 112.84 m deformation exceeds owner global 2 m limit. Keep layer disabled.')
assert current['pid'] == 31408
assert current['map'].split('.')[0] == '/Game/Generated/YACS/Lesson05_20261018/L_SaCalobra_Lesson05'
if operation in ('geometry_context_hide', 'geometry_context_show'):
    context = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(a,unreal.LandscapeProxy) and a.get_actor_label()=='SaCalobra_Context_Valid']
    assert len(context)==1
    context[0].set_is_temporarily_hidden_in_editor(operation=='geometry_context_hide')
    (PROOF/(operation+'.json')).write_text(json.dumps({'temporary_editor_hidden':context[0].is_temporarily_hidden_in_editor()},indent=2))
if operation in ('geometry_show_before', 'geometry_show_after'):
    shown = operation == 'geometry_show_after'
    rows = []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if not isinstance(actor, unreal.LandscapeProxy):
            continue
        for layer in actor.get_edit_layers_bp():
            if str(layer.get_name_bp()) != 'Lesson06_Boundary_Transition':
                continue
            old_visible = bool(layer.get_editor_property('visible'))
            layer.set_editor_property('visible', shown)
            if not shown:
                layer.set_editor_property('heightmap_alpha', 0.0)
            assert bool(layer.get_editor_property('visible')) == shown
            assert unreal.CyclingLandscapeEarthworksLibrary.finish_road_earthworks_batch(actor)
            rows.append({'actor':actor.get_actor_label(),'before_visible':old_visible,'visible':shown,'heightmap_alpha':layer.get_editor_property('heightmap_alpha')})
    assert len(rows) == 4
    (PROOF/(operation+'.json')).write_text(json.dumps({'pid':os.getpid(),'layers':rows},indent=2))
api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
if not api.is_session_valid():
    api.create_session()
assert api.is_session_valid(), api.get_last_error_message()
if operation in ('geometry_readback_before', 'geometry_readback_after', 'geometry_readback_disabled', 'geometry_readback_final', 'geometry_readback_postprobe'):
    label = operation.removeprefix('geometry_readback_')
    os.environ['YACS_LANDSCAPE_LESSON'] = '05'
    os.environ['YACS_LESSON04_READBACK_OUT'] = str(PROOF/label)
    os.environ['YACS_LESSON04_READBACK_HDA'] = 'D:/yacs/work/lesson04-ue-repair-20261018/probe/Landscape_Readback_v3.hda'
    (PROOF/(label+'_scene.json')).write_text(json.dumps(current, indent=2))
    scope = runpy.run_path(str(PROJECT/'scripts/ue/export_lesson04_ue_readback.py'))
elif operation == 'geometry_apply':
    assert operation == 'geometry_apply'
    scope = runpy.run_path(str(PROJECT/'scripts/ue/apply_lesson06_geometry.py'), init_globals={'snapshot': snapshot})
