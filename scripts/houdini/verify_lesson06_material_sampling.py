"""Fresh-open the isolated RGB branches and compare every exported pixel."""
import json
from pathlib import Path
import hou,numpy as np,OpenImageIO as oi
from repair_lesson06_idmap import values,digest
O=Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06MaterialSampling'
rows=[]
for file in sorted(O.glob('*_Color.json')):
    r=json.loads(file.read_text());assert digest(r['file'])==r['sha256']
    hou.hipFile.load(str(O/(r['name']+'_Color.hiplc')),suppress_save_prompt=True)
    n=hou.node('/obj/L06_COLOR_SAMPLING/RGB_ONLY_COMPOSITE');g=n.geometry()
    assert not n.errors()
    nx,ny=r['resolution']
    actual=np.rint(np.clip(np.stack([values(g,c).reshape(ny,nx) for c in 'rgb'],axis=-1),0,1)*255).astype(np.uint8)
    inp=oi.ImageInput.open(r['file']);expected=inp.read_image(format=oi.UINT8);inp.close()
    assert np.array_equal(actual,expected),r['name']
    rows.append({'name':r['name'],'pixels':nx*ny,'fresh_reopen':'BIT_EXACT','unchanged_core_pixels':r['unchanged_core_pixels']})
    print('REPLAY_PASS',r['name'],flush=True)
assert len(rows)==4
(O/'fresh_reopen.json').write_text(json.dumps({'status':'PASS','tiles':rows},indent=2))
