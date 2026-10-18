"""Assemble retained native Lesson05 stage graphs into a separate Lesson04 copy."""
import argparse
import hashlib
import json
from pathlib import Path
import hou

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--source-root', type=Path, required=True)
ap.add_argument('--output-root', type=Path, required=True)
ap.add_argument('--corpus', type=Path, required=True)
ap.add_argument('--checkpoint', type=Path, required=True)
a = ap.parse_args()
assert a.checkpoint.parent.resolve() == a.source_root.resolve()
assert not a.checkpoint.exists(), 'Refuse checkpoint overwrite'
baseline = a.source_root/'SaCalobra_Pegasus_Lesson04.hiplc'
before = hashlib.file_digest(baseline.open('rb'),'sha256').hexdigest()
hou.setUpdateMode(hou.updateMode.Manual)
hou.hipFile.load(str(baseline), suppress_save_prompt=True, ignore_load_warnings=True)
hou.hda.installFile(str(next(a.corpus.rglob('sop_PE_heightfield_layerslump.hda'))))
stages = ['source','slump','pockets','transport','material','cliff_tint','scree_tint','occlusion','curvature','verify']
for area in ['working','context']:
    directory = a.output_root/area
    assert (directory/'final.bgeo.sc').is_file()
    obj = hou.node('/obj').createNode('geo','LESSON05_'+area.upper(),run_init_scripts=False)
    for stage in stages:
        network = obj.createNode('subnet',stage.upper())
        network.loadItemsFromFile(str(directory/(stage+'.cpio')))
        network.setDisplayFlag(False); network.setRenderFlag(False)
    f = obj.createNode('file','FINAL_CACHE');f.parm('file').set(str(directory/'final.bgeo.sc'))
    color = obj.createNode('heightfield_visualize','GLOBAL_COLOR')
    color.setInput(0,f);color.setParms({'updatetinting':'custom','cdvolume':'r g b'})
    neutral = obj.createNode('heightfield_visualize','NEUTRAL_GEOMETRY')
    neutral.setInput(0,f);neutral.parm('updatetinting').set('none')
    color.setDisplayFlag(True); color.setRenderFlag(True)
    obj.layoutChildren()
    obj.setDisplayFlag(True)
old = hou.node('/obj/SA_CALOBRA')
if old: old.setDisplayFlag(False)
hou.hipFile.save(str(a.checkpoint))
assert hashlib.file_digest(baseline.open('rb'),'sha256').hexdigest() == before
receipt = {'hip':str(a.checkpoint),'hip_sha256':hashlib.file_digest(a.checkpoint.open('rb'),'sha256').hexdigest(),'lesson04_unchanged_sha256':before,'stage_graphs_per_area':len(stages),'fresh_reopen':'pending'}
(a.output_root/'checkpoint.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
