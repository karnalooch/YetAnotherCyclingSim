"""Read-only native seam feasibility probe; never loads or saves authoring HIPs."""
import hou
import numpy as np
from repair_lesson06_idmap import geometry, volume, values, lattice
g = hou.node('/obj').createNode('geo')
def source(area):
    f=g.createNode('file',area)
    f.parm('file').set('D:/yacs/work/lesson06-reviewed-20261018/'+area+'/final.bgeo.sc')
    b=g.createNode('blast');b.setInput(0,f);b.setParms({'group':'@name=id','negate':1})
    c=g.createNode('heightfield_crop');c.setInput(0,b)
    c.setParms({'sizex':32,'sizey':32,'tx':-1750,'tz':3120})
    v=g.createNode('convertvdb');v.setInput(0,c);v.parm('conversion').set('vdb')
    print(area,lattice(volume(geometry(c),'id')),flush=True)
    print('vdb',[(p.type().name(),p.boundingBox()) for p in geometry(v).prims()],flush=True)
    return c,v
c,cv=source('context');w,wv=source('working')
r=g.createNode('vdbresample');r.setInput(0,cv);r.setInput(1,wv);r.setParms({'order':'point','mode':'refvdb'})
back=g.createNode('convertvdb');back.setInput(0,r);back.parm('conversion').set('volume')
print('back',[(p.resolution(),p.boundingBox()) for p in geometry(back).prims()],flush=True)
layer=g.createNode('heightfield_layer');layer.setInput(0,w);layer.setInput(1,back);layer.setParms({'layer':'id','mode':'replace'})
out=geometry(layer);print('layer',lattice(volume(out,'id')),np.unique(values(out,'id')),flush=True)
