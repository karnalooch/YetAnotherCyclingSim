"""Publish only the exact native-verified cached recovery and RGB correction."""
import json,os
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Saved/RuntimeProof/Lesson06ContextColor';R=O/'recovery'
pid=os.getpid();assert pid==json.loads((P/'Saved/RuntimeProof/Lesson06SeamRemote/ready.json').read_text())['pid']
proof=json.loads((R/'native_verification.json').read_text());assert proof['status']=='PASS_EXACT_NATIVE_RECOVERY'
assert len(proof['actors'])==27 and proof['dtm_maximum_m']<=2
RGB=O/'StreakRGB' if globals().get('rgb_streak_fix',False) else O
assert json.loads((RGB/'texture_verification.json').read_text())['status']=='BIT_EXACT'
applied=json.loads((RGB/'applied.json').read_text());assert applied['pid']==pid and applied['status']=='APPLIED_RGB_ONLY'
assert not (R/'published.json').exists()
actors={a.get_actor_label():a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(a,unreal.LandscapeProxy)}
assert len(actors)==27
for i in range(22):
    stage=json.loads((R/('stage_'+str(i).zfill(2)+'.json')).read_text());assert stage['pid']==pid and stage['status']=='STAGED_HIDDEN'
    a=actors['SaCalobra_DTM_Context_'+str(i).zfill(2)]
    assert '__LANDSCAPE_VISIBILITY__' in [str(n) for n in a.get_target_layer_names(True)]
    assert [str(l.get_name_bp()) for l in a.get_edit_layers_bp()]==['DTM_Original_05m']
    a.set_is_temporarily_hidden_in_editor(False);a.set_actor_hidden_in_game(False)
old=actors['SaCalobra_Context_Valid'];old.set_is_temporarily_hidden_in_editor(True);old.set_actor_hidden_in_game(True);old.set_actor_enable_collision(False)
assert sum(not a.is_temporarily_hidden_in_editor() for a in actors.values())==26
(R/'published.json').write_text(json.dumps({'status':'LIVE_VERIFIED_RECOVERY','pid':pid,'visible':26,'retained_hidden':1,'map_saved':False,'working_sharp':True,'feather_side':'Context'},indent=2))
(R/'final_snapshot.json').write_text(json.dumps(snapshot(),indent=2))
