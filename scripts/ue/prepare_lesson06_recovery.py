"""Restore retained Context color bindings before cached tile recovery."""
import json,os
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Saved/RuntimeProof/Lesson06ContextColor/recovery';O.mkdir(exist_ok=True)
assert os.getpid()==json.loads((P/'Saved/RuntimeProof/Lesson06SeamRemote/ready.json').read_text())['pid']
assert not (O/'initial.json').exists()
before=snapshot();assert len(before['actors'])==5
(O/'initial.json').write_text(json.dumps(before,indent=2))
a=next(a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if a.get_actor_label()=='SaCalobra_Context_Valid')
m=unreal.load_asset('/Game/Generated/YACS/Lesson06Seam_20261018/Materials/MI_SaCalobra_Context_Valid');assert m
a.set_editor_property('landscape_material',m);a.set_editor_property('landscape_hole_material',m)
(O/'prepared.json').write_text(json.dumps({'pid':os.getpid(),'status':'CONTEXT_COLOR_RESTORED_ONLY','map_saved':False}))
