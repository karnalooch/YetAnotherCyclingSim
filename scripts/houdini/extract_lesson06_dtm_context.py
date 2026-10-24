"""Window retained geographic raster into registered UE-sized input tiles.

Rasterio copies samples only. Native Houdini HeightField File is the terrain
importer. No resampling, synthesis, erosion, or modification of source files.
"""
import hashlib,json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window
P=Path(__file__).resolve().parents[2]
O=P/'Saved/RuntimeProof/Lesson06DTMContext';O.mkdir(exist_ok=True)
source=Path('D:/yacs/work/sa-calobra-houdini-unreal-20261016/inputs/dtm_height_float32.tif')
valid=source.with_name('dtm_validity.tif')
rects=[]
def add(x,z,cx,cz):
 rects.append({'name':f'SaCalobra_DTM_Context_{len(rects):02d}','x0':x,'z0':z,'nx':cx*254+1,'ny':cz*254+1,'components':[cx,cz]})
# No new Context geometry under the four retained Working tiles. All boundaries
# share Working's half-metre vertex lattice, with 127 m UE component spans.
for x in [-4059.25,1909.75]:
 for cx,offset in [(8,0),(9,1016)]:
  for z in [-4086.25,-2054.25,-22.25,2009.75]:add(x+offset,z,cx,16)
for x in [-1900.25,4.75]:
 for z in [-4086.25,-2943.25]:add(x,z,15,9)
 add(x,3279.75,15,6)
r={'status':'EXTRACTING','source':str(source),'validity_source':str(valid),'source_sha256':{},'limit_m':2.,'spacing_m':.5,'tiles':rects,'source_modified':False}
for p in [source,valid]:
 with p.open('rb') as f:r['source_sha256'][str(p)]=hashlib.file_digest(f,'sha256').hexdigest()
with rasterio.open(source) as d,rasterio.open(valid) as v:
 for t in rects:
  nx,ny=t['nx'],t['ny'];zmax=t['z0']+(ny-1)*.5
  # Existing project: Houdini X=easting-origin; Z=origin-northing (south).
  col=(t['x0']+3999.75)/.5;row=(3999.75+t['z0'])/.5
  assert col==round(col) and row==round(row)
  window=Window(int(col),int(row),nx,ny)
  a=d.read(1,window=window,boundless=True,fill_value=0)[::-1].copy()
  alpha=v.read(1,window=window,boundless=True,fill_value=0)[::-1].copy()
  assert a.shape==(ny,nx) and np.isfinite(a).all()
  np.save(O/(t['name']+'_source.npy'),a)
  np.save(O/(t['name']+'_valid.npy'),alpha)
  # HF File reverses image rows; compensate in this transport-only input.
  path=O/(t['name']+'.tif')
  profile={'driver':'GTiff','width':nx,'height':ny,'count':1,'dtype':'float32','compress':'deflate','transform':rasterio.Affine.identity()}
  with rasterio.open(path,'w',**profile) as out:out.write(a[::-1],1)
  t.update(zmax=zmax,source_array_sha256=hashlib.sha256(a.tobytes()).hexdigest(),valid_samples=int(np.count_nonzero(alpha)),source_window=[int(col),int(row),nx,ny])
  print(t['name'],nx,ny,flush=True)
r['status']='WINDOWS_EXTRACTED_NO_RESAMPLING'
(O/'windows.json').write_text(json.dumps(r,indent=2)+'\n')
