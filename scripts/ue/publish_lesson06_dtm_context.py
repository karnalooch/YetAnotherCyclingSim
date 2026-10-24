"""Reversible live switch after exhaustive native DTM and mask admission."""
import json, os
from pathlib import Path
import unreal

P=Path(unreal.Paths.project_dir()).resolve();O=P/'Saved/RuntimeProof/Lesson06DTMContext'
assert os.getpid()==json.loads((P/'Saved/RuntimeProof/Lesson06SeamRemote/ready.json').read_text())['pid']
report=json.loads((O/'whole_dtm_verification.json').read_text())
assert report['status']=='PASS_DTM_AND_RETAINED_ORIGINALS' and report['maximum_source_delta_m']<=2
assert len(report['tiles'])==26
stage=json.loads((O/'dtm_stage_remaining.json').read_text())
assert stage['pid']==os.getpid() and stage['status']=='STAGED_HIDDEN'
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
by_name={a.get_actor_label():a for a in actors if isinstance(a,unreal.LandscapeProxy)}
names=[t['name'] for t in json.loads((O/'windows.json').read_text())['tiles']]
assert len(names)==22 and all(n in by_name for n in names)
for n in names:
    a=by_name[n]
    assert [str(x.get_name_bp()) for x in a.get_edit_layers_bp()]==['DTM_Original_05m']
    assert '__LANDSCAPE_VISIBILITY__' in [str(x) for x in a.get_target_layer_names(True)]
old=by_name['SaCalobra_Context_Valid']
record={'pid':os.getpid(),'status':'SWITCHING','old_context_hidden_before':old.is_temporarily_hidden_in_editor(),
        'old_context_collision_before':old.get_actor_enable_collision(),'new_tiles':names,'map_saved':False}
(O/'publication.json').write_text(json.dumps(record,indent=2))
for n in names:
    by_name[n].set_is_temporarily_hidden_in_editor(False)
    by_name[n].set_actor_hidden_in_game(False)
old.set_is_temporarily_hidden_in_editor(True)
old.set_actor_hidden_in_game(True)
old.set_actor_enable_collision(False)
record.update(status='LIVE_DTM_CONTEXT',old_context_retained=True,original_working_changed=False,
              maximum_source_delta_m=report['maximum_source_delta_m'])
(O/'publication.json').write_text(json.dumps(record,indent=2))
