"""CPU diagnostic views of native seam caches; never changes geometry."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from repair_lesson06_idmap import read,values,volume,lattice
from render_lesson06_review import sheet,rgb

root=Path('D:/yacs/work/lesson06-seam-20261018')
source=Path('D:/yacs/work/lesson06-reviewed-20261018')
out=Path(__file__).resolve().parents[2]/'worldgen/houdini/sa_calobra/evidence/lesson06_seam'
out.mkdir(exist_ok=True)
data=np.load(root/'previews.npz')
sheet([('Working before / ID',rgb(data['before'])),('Working transition / ID',rgb(data['after'])),('Native border weight',data['weight'])],out/'overview.png',width=450)
for name,start,length in [('north',0,7154),('south',7154,7154),('west',14308,9829),('east',24137,9829)]:
    arrays=[data[k][start:start+length][None,:] for k in ['perimeter_before','perimeter_after','perimeter_context']]
    from render_lesson06_review import image
    im=image(rgb(np.concatenate(arrays,axis=0))).resize((1800,180),Image.Resampling.NEAREST)
    im.save(out/('perimeter_'+name+'.png'))
# Inspect a 512 m segment around a source ID disagreement on each edge.
# Composite native Working RGB against bilinear Context RGB outside its footprint.
cg=read(source/'context/final.bgeo.sc');cl=lattice(volume(cg,'height'))
context={n:values(cg,n).reshape(2048,2048) for n in ['r','g','b']}
del cg
before=read(source/'working/final.bgeo.sc');after=read(root/'final.bgeo.sc')
lat=lattice(volume(before,'height'));nx,ny,_=lat['resolution']
colors_before=np.stack([values(before,n).reshape(ny,nx) for n in ['r','g','b']],axis=-1)
colors_after=np.stack([values(after,n).reshape(ny,nx) for n in ['r','g','b']],axis=-1)
del before,after
windows={}
for edge,start,length in [('north',0,nx),('south',nx,nx),('west',2*nx,ny),('east',2*nx+ny,ny)]:
    bad=np.flatnonzero(data['perimeter_before'][start:start+length]!=data['perimeter_context'][start:start+length])
    center=int(bad[len(bad)//2]);center=max(512,min(center,length-512))
    along=np.arange(center-512,center+512)
    across=np.arange(-128,128)
    if edge in ['north','south']:
        xx,yy=np.meshgrid(along,across if edge=='north' else ny-1-across)
    else:
        yy,xx=np.meshgrid(along,across if edge=='west' else nx-1-across)
    wx=lat['origin'][0]+xx*lat['x'][0];wz=lat['origin'][2]+yy*lat['y'][2]
    fx=(wx-cl['origin'][0])/cl['x'][0];fy=(wz-cl['origin'][2])/cl['y'][2]
    x0=np.floor(fx).astype(int);y0=np.floor(fy).astype(int);u=fx-x0;v=fy-y0
    background=np.stack([(1-v)*((1-u)*context[n][y0,x0]+u*context[n][y0,x0+1])+v*((1-u)*context[n][y0+1,x0]+u*context[n][y0+1,x0+1]) for n in ['r','g','b']],axis=-1)
    inside=(xx>=0)&(xx<nx)&(yy>=0)&(yy<ny)
    images=[]
    for title,colors in [('Before / '+edge,colors_before),('After / '+edge,colors_after)]:
        arr=background.copy();arr[inside]=colors[yy[inside],xx[inside]]
        images.append((title,arr))
    sheet(images,out/('color_'+edge+'.png'),width=1024)
    windows[edge]={'center_index':center,'length_m':512,'across_m':128,'boundary_row':128,'outside':'bilinear diagnostic Context RGB','inside':'native Working cache RGB'}
(out/'windows.json').write_text(json.dumps(windows,indent=2)+'\n')
print(str(out),flush=True)
