"""Exhaustive live DTM/retention checks plus common-grid perimeter comparison.

Readback only: no terrain generation, resampling, or source writes.
"""
import json
from pathlib import Path
import numpy as np
from repair_lesson06_idmap import read, volume, values, lattice
from lesson04_height_encoding import decode_h22_readback

P = Path(__file__).resolve().parents[2]
O = P / 'Saved/RuntimeProof/Lesson06DTMContext'
originals = O / 'dtm_readback_originals'
context = O / 'dtm_readback_final'
assert (originals/'complete.json').exists() and (context/'complete.json').exists()
admission = json.loads((O/'dtm_readback_final_verification.json').read_text())
assert admission['status']=='PASS' and len(admission['tiles'])==22
rows=[]; edges={}; seams={}

def collect_edges(name, g, actual):
    v=volume(g,'height'); nx,ny,_=v.resolution(); lat=lattice(v)
    np.testing.assert_allclose(lat['x'], [.5,0,0], atol=.002, rtol=0)
    np.testing.assert_allclose(lat['y'], [0,0,-.5], atol=.002, rtol=0)
    a=actual.reshape(ny,nx)
    # Integer quarter-metre coordinates avoid float transform roundoff.
    x0=int(round(lat['origin'][0]*4)); z0=int(round(lat['origin'][2]*4))
    perimeter=[(x,0) for x in range(nx)]+[(x,ny-1) for x in range(nx)]
    perimeter += [(0,y) for y in range(1,ny-1)]+[(nx-1,y) for y in range(1,ny-1)]
    for x,y in perimeter:
        key=(x0+2*x,z0-2*y); h=float(a[y,x])
        for other, old in edges.get(key,[]):
            pair=' / '.join(sorted([name,other]))
            r=seams.setdefault(pair,{'samples':0,'maximum_vertical_m':0.0})
            r['samples']+=1; r['maximum_vertical_m']=max(r['maximum_vertical_m'],abs(h-old))
        edges.setdefault(key,[]).append((name,h))

for actor in json.loads((originals/'inventory.json').read_text()):
    name=actor['name']; g=read(originals/(name+'.bgeo.sc'))
    old=read(P/'Saved/RuntimeProof/Lesson06GeometryRemote/before'/(name+'.bgeo.sc'))
    assert {p.attribValue('name') for p in old.prims()}=={p.attribValue('name') for p in g.prims()}
    for prim in old.prims():
        other=volume(g,prim.attribValue('name'))
        assert lattice(prim)==lattice(other)
        assert prim.allVoxelsAsString()==other.allVoxelsAsString(),(name,prim.attribValue('name'))
    if name.startswith('SaCalobra_Detail_'):
        _,actual=decode_h22_readback(values(g,'height'),actor['scale'][2])
        src=np.load(Path('D:/yacs/work/lesson04-ue-repair-20261018/transfer2')/(name+'_base.npy')).reshape(-1)
        error=np.abs(actual-src); maximum=float(error.max()); assert maximum<=2
        rows.append({'name':name,'samples':int(src.size),'maximum_source_delta_m':maximum,'above_2m':int((error>2).sum())})
        collect_edges(name,g,actual)
        del actual,src,error
    del g,old

for actor in json.loads((context/'inventory.json').read_text()):
    name=actor['name'];g=read(context/(name+'.bgeo.sc'))
    _,actual=decode_h22_readback(values(g,'height'),actor['scale'][2])
    collect_edges(name,g,actual);del g,actual

rows+=admission['tiles']
working_context={k:v for k,v in seams.items() if 'SaCalobra_Detail_' in k and 'SaCalobra_DTM_Context_' in k}
assert working_context,'No common Working/Context edges found'
report={'status':'PASS_DTM_AND_RETAINED_ORIGINALS','reference':'Original 0.5 m DTM; Working base equality pinned in working_dtm_reference.json',
        'limit_m':2,'tiles':rows,'total_samples':sum(r['samples'] for r in rows),
        'maximum_source_delta_m':max(r['maximum_source_delta_m'] for r in rows),
        'original_five_height_and_masks':'BIT_EXACT','shared_grid_spacing_m':.5,
        'working_context_edges':working_context,'all_shared_edges':seams,
        'maximum_shared_edge_vertical_m':max(r['maximum_vertical_m'] for r in seams.values()),
        'scope':'Every exported height sample; visible UE LOD and visual boundary require separate viewport evidence.'}
(O/'whole_dtm_verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('tiles','all_shared_edges','working_context_edges')}),flush=True)
