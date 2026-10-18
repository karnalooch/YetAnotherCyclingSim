import json, hashlib
from pathlib import Path
import numpy as np
from PIL import Image
import argparse
ap=argparse.ArgumentParser(description='Verify retained visibility, colour registration and source map identity.')
ap.add_argument('--root',type=Path,required=True)
ap.add_argument('--proof',default='proof')
a=ap.parse_args()
r=a.root
p=r/a.proof
m=json.loads((r/'transfer/manifest.json').read_text())
result={'visibility':[], 'materials':[], 'color_edges':[], 'source_map_unchanged':False}
inv={x['name']:x for x in json.loads((p/'reopened/inventory.json').read_text())}
edges={}
for tile in m['tiles']:
    n=tile['name']
    initial=np.load(r/'proof/baseline'/f'{n}_visibility.npy',mmap_mode='r')
    after=np.load(p/'after'/f'{n}_visibility.npy',mmap_mode='r')
    fresh=np.load(p/'reopened'/f'{n}_visibility.npy',mmap_mode='r')
    result['visibility'].append({'name':n,'changed_after':int(np.count_nonzero(initial!=after)),'changed_reopened':int(np.count_nonzero(initial!=fresh)),'hidden_vertices':int(np.count_nonzero(fresh>=.5))})
    assert np.array_equal(initial,after) and np.array_equal(initial,fresh)
    row=inv[n]
    assert '/Lesson05_20261018/' in row['material'] and '/Lesson05_20261018/' in row['albedo']
    assert row['albedo_srgb'] is True
    assert row['hole_material']==row['material'] and 'BLEND_MASKED' in row['blend_mode']
    assert 'LandscapeVisibilityMask' in row['opacity_mask_input']
    for param,key in [('OriginCm','uv_origin_cm'),('InvSizeCm','uv_inverse_cm')]:
        assert np.allclose(row['uv'][param],tile[key],rtol=1e-6,atol=1e-11)
    result['materials'].append(row)
    image=np.asarray(Image.open(r/'transfer'/tile['albedo']))
    edges[n]=[image[0].copy(),image[-1].copy(),image[:,0].copy(),image[:,-1].copy()]
for a,ae,b,be in [('0_0',3,'1_0',2),('0_1',3,'1_1',2),('0_1',1,'0_0',0),('1_1',1,'1_0',0)]:
    err=int(np.max(np.abs(edges['SaCalobra_Detail_'+a][ae].astype(int)-edges['SaCalobra_Detail_'+b][be].astype(int))))
    result['color_edges'].append({'tiles':[a,b],'max_uint8_channel_error':err})
    # Report exact discrepancies; do not turn a colour difference into a hidden PASS.
source=json.loads((r/'source-map-hash.json').read_text(encoding='utf-8-sig'))
with open(source['Path'],'rb') as f: current=hashlib.file_digest(f,'sha256').hexdigest()
assert current.lower()==source['Hash'].lower()
result['source_map_unchanged']=True
result['exact_color_seams']=all(x['max_uint8_channel_error']==0 for x in result['color_edges'])
result['status']='MATCH' if result['exact_color_seams'] else 'GEOMETRY_OWNERSHIP_MATERIAL_MATCH_COLOR_DIFFERENCE_RECORDED'
(p/'consumer-audit.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='materials'},indent=2))
