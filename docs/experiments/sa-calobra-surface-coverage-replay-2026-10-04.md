# Sa Calobra surface coverage — replay recipe

Companion to [the audit report](sa-calobra-surface-coverage-2026-10-04.md). This records one read-only measurement recipe; it is not a production world-building subsystem or a new dependency specification.

## Preconditions

Use the canonical `D:/yacs/project` checkout and its configured workspace. Restore the exact candidate files listed in the measurement appendix; a current filename without the recorded hash is insufficient. This recipe requires the existing Python environment with NumPy 2.3.5, SciPy 1.17.1, Rasterio 1.5.2 and Pillow 12.3.0. It does not install packages. The helper `scripts/manage_local_workspace.py` belongs to the inspected candidate checkout; its definition is not imported into main by this report. Running the recipe from main alone is therefore not claimed.

The measurement sources below were executed from `D:/yacs/work/surface-coverage-audit-2026-10-04`. They create or replace only their named audit JSON/PNG outputs in their own directory. Keep original receipts separately when replaying. They read the frozen masks and never mutate source files or the Unreal project. Image outputs remain local under the existing provider-data restrictions.

```powershell
.venv/Scripts/python.exe D:/yacs/work/surface-coverage-audit-2026-10-04/analyze.py
.venv/Scripts/python.exe D:/yacs/work/surface-coverage-audit-2026-10-04/inspect_candidates.py
```

Manifest fingerprints and all raw ancestors are not comprehensively revalidated here: the script checks four manifest file identities through the recorded receipt, their declared outputs, and the surface parent-manifest references. Exact source-manifest SHA-256 values must be compared with the measurement appendix before claiming the same snapshot.

## Analysis source

### `analyze.py`

Executed file SHA-256: `3298010ded84f2244b92b2610958ccf204e777b75c976ffc1d2777f1b916e58c`.

```python
"""Read-only audit of pinned candidate masks; never edits source or UE assets."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'project'))
from scripts.manage_local_workspace import load_workspace

ROOT = Path(load_workspace()['data']) / 'world-data/sa-calobra-working-v1'
OUT = Path(__file__).resolve().parent
NAMES = {
    'surface': ('surface-cover-v1a-2026-10-04', 'surface-cover-manifest.json'),
    'lidar': ('lidar-masks-v1b-2026-10-04', 'lidar-manifest.json'),
    'road': ('road-masks-v1a-2026-10-04', 'road-mask-manifest.json'),
    'review': ('mask-transition-review-v1a-2026-10-04', 'review-manifest.json'),
}


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def read(kind, name):
    with rasterio.open(ROOT / NAMES[kind][0] / name) as ds:
        assert ds.shape == (4033, 4033)
        assert str(ds.crs) == 'EPSG:25831'
        assert list(ds.transform)[:6] == [0.5, 0, 483000, 0, -0.5, 4409516.5]
        a = ds.read()
    return a[0] if len(a) == 1 else a


def sums(a, step):
    return np.add.reduceat(np.add.reduceat(a.astype(np.uint64), np.arange(0, a.shape[0], step), axis=0), np.arange(0, a.shape[1], step), axis=1)


def components(mask, connectivity):
    labels, count = ndimage.label(mask, structure=ndimage.generate_binary_structure(2, connectivity))
    sizes = np.bincount(labels.ravel())[1:]
    ids = np.argsort(sizes)[-10:][::-1] + 1
    boxes = ndimage.find_objects(labels)
    largest = []
    for idx in ids:
        sy, sx = boxes[idx - 1]
        largest.append({'cells': int(sizes[idx - 1]), 'area_m2': float(sizes[idx - 1] * .25), 'bounds_pixels_r0_r1_c0_c1': [sy.start, sy.stop, sx.start, sx.stop], 'bounds_epsg25831': [483000 + sx.start*.5, 4409516.5-sy.stop*.5, 483000+sx.stop*.5, 4409516.5-sy.start*.5]})
    return {'connectivity': 4 if connectivity == 1 else 8, 'components': int(count), 'total_cells': int(sizes.sum()), 'single_cell_components': int((sizes == 1).sum()), 'cells_in_components_le_4': int(sizes[sizes <= 4].sum()), 'cells_in_components_ge_400': int(sizes[sizes >= 400].sum()), 'largest': largest}


def metrics(surface, mask, raw_missing):
    total = int(mask.sum())
    vals, nums = np.unique(surface[mask], return_counts=True)
    return {'cells': total, 'area_m2': total*.25, 'class_cells': {str(v):int(n) for v,n in zip(vals,nums)}, 'unresolved_pct': float(100*np.count_nonzero(mask & (surface == 0))/total) if total else None, 'display_no_lidar_pct': float(100*np.count_nonzero(mask & (surface == 255))/total) if total else None, 'raw_no_lidar_pct': float(100*np.count_nonzero(mask & raw_missing)/total) if total else None}


def main():
    # Independent arithmetic checks include clipped edge blocks and connectivity.
    assert sums(np.ones((3, 5), dtype=bool), 2).tolist() == [[4,4,2],[2,2,1]]
    assert ndimage.label(np.eye(2), ndimage.generate_binary_structure(2, 1))[1] == 2
    assert ndimage.label(np.eye(2), ndimage.generate_binary_structure(2, 2))[1] == 1
    report = {'status':'READ_ONLY_CANDIDATE_AUDIT', 'geometry_mutation':False, 'production_admission':False, 'script_sha256':digest(Path(__file__)), 'inputs':{}, 'limitations':['No independent field truth; no calibrated classification accuracy.', 'Block occupancy is sampling support, never permission to fill native cells.', 'Road proximity uses an existing conservative raster-distance lower bound, not surveyed edge distance.']}
    manifests = {}
    for kind, (folder, filename) in NAMES.items():
        p = ROOT/folder/filename
        m = json.loads(p.read_text())
        manifests[kind] = m
        verified = []
        for item in m['outputs']:
            q=p.parent/item['path']
            assert q.parent == p.parent
            assert digest(q) == item['sha256'], str(q)
            if 'size_bytes' in item:
                assert q.stat().st_size == item['size_bytes'], str(q)
            verified.append(item['path'])
        report['inputs'][kind]={'manifest':str(p),'sha256':digest(p),'verified_outputs':verified}
    for item in manifests['surface']['source_manifests']:
        assert digest(ROOT/item['path']) == item['sha256']
    surface = read('surface','surface-class-candidate.tif')
    counts = read('lidar','class-counts.tif')
    total = counts.sum(axis=0,dtype=np.uint64)
    missing = total == 0
    assert int(total.sum()) == manifests['lidar']['counts']['accepted_aoi']
    for key, name in manifests['surface']['legend'].items():
        assert int((surface == int(key)).sum()) == manifests['surface']['counts'][name]
    report['grid'] = manifests['surface']['grid']
    report['whole_area'] = metrics(surface,np.ones(surface.shape,bool),missing)
    report['point_count'] = int(total.sum())
    report['mean_accepted_returns_per_m2'] = float(total.sum()/(surface.size*.25))
    report['raw_no_lidar_cells_hidden_by_mapped_classes'] = int((missing & (surface != 255)).sum())
    report['sampling_support'] = []
    for step in (1,2,4,10,20):
        samples, cells = sums(total,step), sums(np.ones(total.shape,np.uint8),step)
        occupied = samples > 0
        report['sampling_support'].append({'nominal_block_m':step*.5,'blocks':int(samples.size),'empty_blocks':int((~occupied).sum()),'empty_support_area_m2':float(cells[~occupied].sum()*.25),'supported_area_pct':float(100*cells[occupied].sum()/surface.size),'minimum_returns_per_block':int(samples.min())})
    report['missing_components'] = [components(missing,k) for k in (1,2)]
    report['unresolved_components_8'] = components(surface == 0,2)
    d = ndimage.distance_transform_edt(missing,sampling=.5)
    report['missing_cell_distance_to_observed_center_m'] = {'percentiles':dict(zip(['50','90','95','99','100'],map(float,np.percentile(d[missing],[50,90,95,99,100])))),'cells_gt_1m':int((d>1).sum()),'cells_gt_2m':int((d>2).sum()),'cells_gt_5m':int((d>5).sum())}
    del d
    distance = read('road','road-distance-lower-bound.tif')
    pavement = read('road','road-footprint.tif') == 1
    report['road_bands'] = {'pavement':metrics(surface,pavement,missing)}
    for lo,hi in ((0,10),(10,25),(25,50),(50,100),(100,float('inf'))):
        report['road_bands'][f'{lo}_{hi}m_off_pavement'] = metrics(surface,(~pavement)&(distance>=lo)&(distance<hi),missing)
    rgb = np.asarray(Image.open(ROOT/NAMES['review'][0]/'orthophoto.png').convert('RGB'))
    ground_only = (counts[0]>0)&(counts[1:].sum(axis=0,dtype=np.uint64)==0)
    unresolved = surface == 0
    mean = rgb.mean(axis=2)
    report['unresolved_composition']={'ground_only_cells':int((unresolved&ground_only).sum()),'not_ground_only_cells':int((unresolved&~ground_only).sum()),'dark_rgb_mean_lt_60_cells':int((unresolved&(mean<60)).sum()),'mean_rgb_percentiles':list(map(float,np.percentile(mean[unresolved],[10,50,90]))),'note':'Dark RGB is a diagnostic proxy, not confirmed shadow.'}
    report['sectors'] = []
    edges = np.rint(np.linspace(0,4033,9)).astype(int)
    for row in range(8):
        for col in range(8):
            sy,sx=slice(edges[row],edges[row+1]),slice(edges[col],edges[col+1])
            s=surface[sy,sx]; m=missing[sy,sx]
            report['sectors'].append({'id':f'R{row+1}C{col+1}','bounds_pixels_r0_r1_c0_c1':[int(edges[row]),int(edges[row+1]),int(edges[col]),int(edges[col+1])],**metrics(s,np.ones(s.shape,bool),m)})
    # Visuals are local evidence, not a new geographic layer.
    ortho=Image.fromarray(rgb)
    colors=Image.open(ROOT/NAMES['surface'][0]/'surface-classes.png').convert('RGB')
    board=Image.new('RGB',(2048,1100),'white'); draw=ImageDraw.Draw(board)
    board.paste(ortho.resize((1024,1024)),(0,45));board.paste(colors.resize((1024,1024),Image.Resampling.NEAREST),(1024,45))
    draw.text((15,10),'2024 orthophoto | entire 2016.5 m square | north up',fill='black')
    draw.text((1040,10),'Candidate classes | gray unresolved | mauve no LiDAR | beige rock candidate',fill='black')
    draw.text((15,1078),'PNOA / LiDAR-PNOA CC-BY 4.0 scne.es. Diagnostic only; no production admission.',fill='black')
    board.save(OUT/'whole-area.png')
    # 16 systematic 128m crops, one per 4x4 macro-sector. Not accuracy ground truth.
    report['systematic_crops']=[]
    for gr in range(2):
        for gc in range(2):
            panel=Image.new('RGB',(1100,1160),'white'); dr=ImageDraw.Draw(panel)
            for ir in range(2):
                for ic in range(2):
                    r,c=gr*2+ir,gc*2+ic
                    y,x=int((r+.5)*4033/4),int((c+.5)*4033/4)
                    box=(x-128,y-128,x+128,y+128)
                    ox,oy=ic*550,ir*560
                    panel.paste(ortho.crop(box).resize((256,256)),(ox,oy+30))
                    panel.paste(colors.crop(box),(ox+270,oy+30))
                    # Same crop at 2x for RGB detail, cropped central 128x128.
                    panel.paste(ortho.crop((x-64,y-64,x+64,y+64)).resize((256,256)),(ox,oy+294))
                    panel.paste(colors.crop((x-64,y-64,x+64,y+64)).resize((256,256),Image.Resampling.NEAREST),(ox+270,oy+294))
                    label=f'S{r+1}{c+1} | E {483000.25+x*.5:.2f}, N {4409516.25-y*.5:.2f} | 128m / 64m'
                    dr.text((ox+5,oy+8),label,fill='black')
                    report['systematic_crops'].append({'id':f'S{r+1}{c+1}','center_row_col':[y,x],'size_m':128,'epsg25831_center':[483000.25+x*.5,4409516.25-y*.5]})
            dr.text((10,1130),'Left: orthophoto. Right: candidate classes. Source: PNOA CC-BY 4.0 scne.es. No field truth.',fill='black')
            panel.save(OUT/f'crops-{gr+1}-{gc+1}.png')
    (OUT/'audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['sectors','inputs','systematic_crops']},indent=2))


if __name__=='__main__':
    main()
```

### `inspect_candidates.py`

Executed file SHA-256: `68c5cc5b2c1576075bba59462f6b33ab8d7d34083c4462501219769d402d42d2`.

```python
"""Targeted local crop review and explanatory counts, never relabels cells."""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from analyze import ROOT, OUT, NAMES, read, sums, digest

s=read('surface','surface-class-candidate.tif')
c=read('lidar','class-counts.tif')
rgb=Image.open(ROOT/NAMES['review'][0]/'orthophoto.png').convert('RGB')
color=Image.open(ROOT/NAMES['surface'][0]/'surface-classes.png').convert('RGB')
ground=(c[0]>0)&(c[1:].sum(0,dtype=np.uint64)==0)
a=np.asarray(rgb).astype(np.float32)
r,g,b=np.moveaxis(a,-1,0)
mean=a.mean(2);maximum=a.max(2);sat=(maximum-a.min(2))/np.maximum(maximum,1)
report={'script_sha256':digest(Path(__file__)),'unresolved_ground_only_cells':int(((s==0)&ground).sum())}
gu=(s==0)&ground
report['overlapping_diagnostic_rejections']={
 'mean_rgb_below_150':int((gu&(mean<150)).sum()),
 'red_minus_green_outside_minus5_to10':int((gu&((r-g < -5)|(r-g > 10))).sum()),
 'green_minus_blue_outside_0_to32':int((gu&((g-b < 0)|(g-b > 32))).sum()),
 'saturation_above_0_25':int((gu&(sat>.25)).sum()),
}
report['candidate_rgb_quantiles']={str(k):{'cells':int((s==k).sum()),'mean_rgb_p10_p50_p90':np.percentile(mean[s==k],[10,50,90]).tolist(),'saturation_p10_p50_p90':np.percentile(sat[s==k],[10,50,90]).tolist()} for k in [4,5]}
samples=[]
for cls in [4,5]:
 counts=sums(s==cls,64)
 selected=[]
 for flat in np.argsort(counts.ravel())[::-1]:
  rr,cc=np.unravel_index(flat,counts.shape)
  y,x=min(int(rr*64+32),3905),min(int(cc*64+32),3905)
  y,x=max(y,128),max(x,128)
  if all((y-py)**2+(x-px)**2>=500**2 for py,px in selected):
   selected.append((y,x));samples.append({'id':f'class{cls}-{len(selected)}','selection':'highest 32m block count; centers at least 250m apart within class','class':cls,'center_row_col':[y,x],'block_candidate_cells':int(counts[rr,cc])})
  if len(selected)==4:break
main=json.loads((OUT/'audit.json').read_text())
for i,entry in enumerate(main['unresolved_components_8']['largest'][:2]):
 r0,r1,c0,c1=entry['bounds_pixels_r0_r1_c0_c1']
 samples.append({'id':f'unresolved-component-{i+1}','selection':'center of bounding box of largest connected unresolved components','center_row_col':[(r0+r1)//2,(c0+c1)//2]})
missing=c.sum(0,dtype=np.uint64)==0
dist=ndimage.distance_transform_edt(missing,sampling=.5)
flat=int(dist.argmax());y,x=map(int,np.unravel_index(flat,dist.shape))
samples.append({'id':'deepest-empty-cell','selection':'maximum distance to an observed cell center','center_row_col':[y,x],'distance_m':float(dist[y,x])})
report['samples']=samples
for start in range(0,len(samples),4):
 selected=samples[start:start+4]
 panel=Image.new('RGB',(1080,560*len(selected)//2+50 if len(selected)%2==0 else 1170),'white')
 draw=ImageDraw.Draw(panel)
 for n,row in enumerate(selected):
  y,x=row['center_row_col'];x=max(128,min(3905,x));y=max(128,min(3905,y))
  row['display_center_row_col']=[y,x]
  row['epsg25831_display_center']=[483000.25+x*.5,4409516.25-y*.5]
  ox,oy=n%2*540,n//2*560
  draw.text((ox+5,oy+8),f"{row['id']} | center E{row['epsg25831_display_center'][0]} N{row['epsg25831_display_center'][1]}",fill='black')
  for image,xx,method in [(rgb,ox,Image.Resampling.BILINEAR),(color,ox+270,Image.Resampling.NEAREST)]:
   panel.paste(image.crop((x-128,y-128,x+128,y+128)),(xx,oy+30))
   panel.paste(image.crop((x-64,y-64,x+64,y+64)).resize((256,256),method),(xx,oy+295))
 panel.save(OUT/f'targeted-{start//4+1}.png')
(OUT/'targeted-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(report,indent=2))
```

## Saved review-marker recipe

Run after the analysis above: `.venv/Scripts/python.exe D:/yacs/work/surface-coverage-audit-2026-10-04/mark_review.py`. This saves local review imagery and a georeferenced flag raster; it never applies a material in Unreal. The Polish figure captions are owner-facing labels, preserved verbatim in the source. Arial is read from the existing Windows fonts directory.

### `mark_review.py`

Executed file SHA-256: `3419727919b4adcac5de2e28f034c4f07212b119b79284150c8be048226cbfa9`.

```python
"""Persist diagnostic review colors from measured flags, without class changes."""
import json
from pathlib import Path
import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from analyze import ROOT, OUT, NAMES, read, digest

surface=read('surface','surface-class-candidate.tif')
counts=read('lidar','class-counts.tif')
observed=counts.sum(0,dtype=np.uint64)>0
distance=ndimage.distance_transform_edt(~observed,sampling=.5)
report=json.loads((OUT/'audit.json').read_text())
for row in report['inputs'].values():
    assert digest(Path(row['manifest']))==row['sha256']
red=surface==0
orange=(~observed)&(distance>1.0)
flags=np.zeros(surface.shape,dtype=np.uint8)
flags[red]=1
flags[orange]=2
ortho_path=ROOT/NAMES['review'][0]/'orthophoto.png'
surface_path=ROOT/NAMES['surface'][0]/'surface-class-candidate.tif'
before={str(p):digest(p) for p in [ortho_path,surface_path]}
rgb=np.asarray(Image.open(ortho_path).convert('RGB')).astype(np.float32)
rgb[red]=.35*rgb[red]+.65*np.array([240,35,45],np.float32)
rgb[orange]=.2*rgb[orange]+.8*np.array([255,155,20],np.float32)
overlay=Image.fromarray(np.rint(rgb).astype(np.uint8))
overlay.save(OUT/'problem-overlay-native.png')
with rasterio.open(surface_path) as ds:profile=ds.profile
with rasterio.open(OUT/'problem-review-flags.tif','w',**{**profile,'dtype':'uint8','count':1,'nodata':None,'compress':'DEFLATE'}) as ds:ds.write(flags,1)
with rasterio.open(OUT/'problem-review-flags.tif') as ds:
    assert np.array_equal(ds.read(1),flags)
    assert ds.transform==profile['transform']
# A labelled overview is separate from the correctly registered native texture.
size=1600;left=75;top=140
board=Image.new('RGB',(1750,1960),'#f5f4f0');draw=ImageDraw.Draw(board)
font_path='C:/Windows/Fonts/arial.ttf'
font=ImageFont.truetype(font_path,24);small=ImageFont.truetype(font_path,18);title=ImageFont.truetype(font_path,31)
draw.text((left,25),'Sa Calobra — miejsca do późniejszego przeglądu',font=title,fill='#17202a')
draw.text((left,70),'Cały obszar 2016,5 × 2016,5 m • północ u góry • stan 04.10.2026',font=font,fill='#17202a')
board.paste(overlay.resize((size,size),Image.Resampling.BILINEAR),(left,top))
for n in range(9):
    z=round(n*size/8)
    draw.line((left+z,top,left+z,top+size),fill='#dedbd4',width=1)
    draw.line((left,top+z,left+size,top+z),fill='#dedbd4',width=1)
    if n<8:
        draw.text((left+z+size/16-15,top-29),f'C{n+1}',font=small,fill='#17202a')
        draw.text((15,top+z+size/16-10),f'R{n+1}',font=small,fill='#17202a')
markers=[]
for i,entry in enumerate(report['unresolved_components_8']['largest'][:5],1):
    r0,r1,c0,c1=entry['bounds_pixels_r0_r1_c0_c1']
    box=(left+c0/4033*size,top+r0/4033*size,left+c1/4033*size,top+r1/4033*size)
    draw.rectangle(box,outline='white',width=7)
    draw.rectangle(box,outline='#e31b2e',width=3)
    bx,by=box[0],box[1]
    draw.rectangle((bx,by,bx+49,by+31),fill='#e31b2e')
    draw.text((bx+6,by+2),f'P{i}',font=font,fill='white')
    markers.append({'id':f'P{i}',**entry})
y=1770
draw.rectangle((left,y,left+24,y+24),fill='#f0232d');draw.text((left+38,y-2),'Czerwony: powierzchnia nierozstrzygnięta mimo próbek LiDAR (20,98%).',font=font,fill='#17202a')
draw.rectangle((left,y+42,left+24,y+66),fill='#ff9b14');draw.text((left+38,y+40),'Pomarańczowy: brak próbki dalej niż 1 m od najbliższej obserwacji.',font=font,fill='#17202a')
draw.text((left,y+83),'P1–P5: obwiednie największych skupisk nierozstrzygniętych komórek; nie całe prostokąty.',font=small,fill='#17202a')
draw.text((left,y+113),'Brak koloru nie oznacza potwierdzonej poprawności. Próg 1 m służy tylko przeglądowi.',font=small,fill='#17202a')
draw.text((left,y+143),'Źródło: PNOA / LiDAR-PNOA CC-BY 4.0 scne.es. Geometria i klasy źródłowe bez zmian.',font=small,fill='#17202a')
board.save(OUT/'problem-review-map.png')
assert before=={p:digest(Path(p)) for p in before}
receipt={'status':'SAVED_REVIEW_MARKERS_ONLY','script_sha256':digest(Path(__file__)),'grid':report['grid'],'legend':{'0':'not highlighted; not validated','1':'observed unresolved surface; red','2':'no accepted LiDAR return and nearest observed cell center >1m; orange; diagnostic threshold only'},'counts':{str(k):int((flags==k).sum()) for k in [0,1,2]},'source_hashes':before,'source_manifests':report['inputs'],'markers':markers,'geometry_mutation':False,'source_classes_modified':False,'unreal_applied':False,'saved_map_modified':False,'outputs':[{ 'path':p,'sha256':digest(OUT/p),'size_bytes':(OUT/p).stat().st_size} for p in ['problem-overlay-native.png','problem-review-flags.tif','problem-review-map.png']]}
(OUT/'problem-review-manifest.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:v for k,v in receipt.items() if k in ['status','counts','unreal_applied','outputs']},indent=2))
```
