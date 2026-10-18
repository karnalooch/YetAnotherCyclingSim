"""Bounded in-editor Lesson05 import; never restart or reconfigure the stream.

Execute once in the current editor. External native measurements gate each
step. Only the fixed Lesson05 derivative may be mutated or saved.
"""
import json
import hashlib
import os
from pathlib import Path
import runpy
import time
import traceback
import unreal
unreal.EditorPythonScripting.set_keep_python_script_alive(True)

PROJECT=Path(unreal.Paths.project_dir()).resolve()
WORK=PROJECT.parent/'work/lesson05-ue-20261018'
CONTEXT_REPAIR=os.environ.get('YACS_LESSON05_CONTEXT_REPAIR')=='1'
RECOVER=os.environ.get('YACS_LESSON05_RECOVER_BASELINE')=='1'
PROOF=WORK/('proof-context' if CONTEXT_REPAIR else 'proof-retry' if RECOVER else 'proof')
SOURCE='/Game/Generated/YACS/Lesson04Repair_20261018/L_SaCalobra_Lesson04_Test'
TARGET='/Game/Generated/YACS/Lesson05_20261018/L_SaCalobra_Lesson05'
HDA=PROJECT.parent/'work/lesson04-ue-repair-20261018/probe/Landscape_Readback_v3.hda'
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert editor.get_editor_world().get_path_name().split('.')[0]==(TARGET if RECOVER or CONTEXT_REPAIR else SOURCE)
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), 'Preserve unsaved owner maps'
if CONTEXT_REPAIR:
    measured_before=json.loads((WORK/'proof-retry/after/measurements.json').read_text())
    assert measured_before['status']=='MISMATCH'
    assert [x['name'] for x in measured_before['tiles'] if not x['all_codes_match_expected']]==['SaCalobra_Context_Valid']
elif RECOVER:
    previous=json.loads((WORK/'proof/session.json').read_text())
    assert previous['status']=='ERROR'
    assert json.loads((WORK/'proof/baseline/measurements.json').read_text())['status']=='MATCH'
else:
    assert not unreal.EditorAssetLibrary.does_asset_exist(TARGET), 'Refuse existing destination'
assert HDA.is_file() and (WORK/'transfer-height-only/manifest.json').is_file()
assert not PROOF.exists(), 'Use fresh proof state; do not repeat an incremental import'
source_file=PROJECT/('Content/'+SOURCE.removeprefix('/Game/')+'.umap')
with source_file.open('rb') as stream:
    source_hash=hashlib.file_digest(stream,'sha256').hexdigest()
identity=WORK/'source-map-hash.json'
if identity.exists():
    assert json.loads(identity.read_text(encoding='utf-8-sig'))['Hash'].lower()==source_hash
else:
    identity.write_text(json.dumps({'Algorithm':'SHA256','Path':str(source_file),'Hash':source_hash},indent=2))
PROOF.mkdir()
camera=editor.get_level_viewport_camera_info()
if not RECOVER and not CONTEXT_REPAIR:
    assert levels.new_level_from_template(TARGET,SOURCE)
assert editor.get_editor_world().get_path_name().split('.')[0]==TARGET
editor.set_level_viewport_camera_info(*camera)
assert levels.save_current_level()
os.environ['YACS_LANDSCAPE_LESSON']='05'
os.environ['YACS_LESSON04_TRANSFER']=str(WORK/'transfer-height-only')
os.environ['YACS_LESSON04_PROOF']=str(PROOF/'apply')
os.environ['YACS_LESSON04_READBACK_HDA']=str(HDA)
scopes=[]
phase='baseline'
started=time.monotonic()
busy=False

def record(status,**fields):
    (PROOF/'session.json').write_text(json.dumps({'status':status,'pid':os.getpid(),'map':TARGET,**fields},indent=2))

def readback(label):
    os.environ['YACS_LESSON04_READBACK_OUT']=str(PROOF/label)
    scopes.append(runpy.run_path(str(PROJECT/'scripts/ue/export_lesson04_ue_readback.py')))
    record('WAITING_NATIVE_MEASUREMENTS',label=label)

def measured(label):
    folder=PROOF/label
    assert not (folder/'error.json').exists(), (folder/'error.json').read_text() if (folder/'error.json').exists() else ''
    path=folder/'measurements.json'
    if not path.exists():return False
    result=json.loads(path.read_text())
    assert result['status']=='MATCH', 'Native height/seam measurements failed'
    return True

def tick(dt):
    global phase,busy
    if busy:return
    busy=True
    try:
        assert time.monotonic()-started<7200, 'Bounded import timeout'
        assert editor.get_editor_world().get_path_name().split('.')[0]==TARGET
        if phase=='baseline' and measured('baseline'):
            phase='apply'
            scopes.append(runpy.run_path(str(PROJECT/'scripts/ue/apply_lesson04_ue_repair.py')))
        elif phase=='apply':
            path=PROOF/'apply/apply.json'
            if path.exists():
                result=json.loads(path.read_text())
                assert result['status']!='ERROR',result
                if result['status']=='SAVED_CANDIDATE':
                    phase='after';readback('after')
        elif phase=='after' and measured('after'):
            assert levels.load_level(TARGET)
            editor.set_level_viewport_camera_info(*camera)
            phase='reopened';readback('reopened')
        elif phase=='reopened' and measured('reopened'):
            record('IMPORTED_MEASURED_REOPENED',stream_restarted_during_import=False,visual_acceptance=False)
            unreal.unregister_slate_post_tick_callback(handle)
    except Exception:
        record('ERROR',error=traceback.format_exc())
        unreal.unregister_slate_post_tick_callback(handle)
    finally:busy=False

unreal.EditorPythonScripting.set_keep_python_script_alive(True)
readback('baseline')
handle=unreal.register_slate_post_tick_callback(tick)
