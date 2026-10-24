"""Read-only full-perimeter test of native categorical resampling and feather."""
from pathlib import Path
import numpy as np
from repair_lesson06_idmap import read,values,lattice,volume
r=Path('D:/yacs/work/lesson06-seam-20261018')
g=read(r/'context_id_aligned.bgeo.sc');lat=lattice(volume(g,'id'))
nx,ny,_=lat['resolution'];a=values(g,'id').reshape(ny,nx)
ix=np.concatenate([np.arange(nx),np.arange(nx),np.zeros(ny),np.full(ny,nx-1)])
iy=np.concatenate([np.zeros(nx),np.full(nx,ny-1),np.arange(ny),np.arange(ny)])
c=read('D:/yacs/work/lesson06-reviewed-20261018/context/final.bgeo.sc');cl=lattice(volume(c,'id'))
cx=np.rint((lat['origin'][0]+ix*lat['x'][0]-cl['origin'][0])/cl['x'][0]).astype(int)
cy=np.rint((lat['origin'][2]+iy*lat['y'][2]-cl['origin'][2])/cl['y'][2]).astype(int)
actual=np.concatenate([a[0],a[-1],a[:,0],a[:,-1]])
expected=values(c,'id').reshape(2048,2048)[cy,cx]
weight=values(read(r/'border_weight.bgeo.sc'),'mask').reshape(ny,nx)
print('nearest mismatches',np.count_nonzero(actual!=expected),'unique',np.unique(a))
print('nearest material mismatches',np.count_nonzero(np.rint(actual*255)!=np.rint(expected*255)),'max numeric error',np.max(np.abs(actual-expected)))
print('rounded all codes',np.unique(np.rint(a*255)))
cx2=np.floor((lat['origin'][0]+ix*lat['x'][0]-cl['origin'][0])/cl['x'][0]+.5).astype(int)
cy2=np.floor((lat['origin'][2]+iy*lat['y'][2]-cl['origin'][2])/cl['y'][2]+.5).astype(int)
expected2=values(c,'id').reshape(2048,2048)[cy2,cx2]
print('half up material mismatches',np.count_nonzero(np.rint(actual*255)!=np.rint(expected2*255)))
bad=np.flatnonzero(np.rint(actual*255)!=np.rint(expected*255))
print('tie diagnostics',[(int(i),float((lat['origin'][0]+ix[i]*lat['x'][0]-cl['origin'][0])/cl['x'][0]),float((lat['origin'][2]+iy[i]*lat['y'][2]-cl['origin'][2])/cl['y'][2]),float(actual[i]),float(expected[i])) for i in bad[:20]])
print('weight perimeter',np.unique(np.concatenate([weight[0],weight[-1],weight[:,0],weight[:,-1]])),'affected',np.count_nonzero(weight),'max',weight.max())
