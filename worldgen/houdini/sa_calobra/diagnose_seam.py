import hou
import numpy as np

def load_geo(path):
    g = hou.Geometry()
    g.loadFromFile(path)
    return g

def vol_layer(g, name):
    for p in g.prims():
        if isinstance(p, hou.Volume) and p.attribValue('name') == name:
            return np.frombuffer(p.allVoxelsAsString(), np.float32).reshape(p.resolution()[1], p.resolution()[0]), p
    return None, None

w_l04 = load_geo('worldgen/houdini/sa_calobra/cache/lesson04_working_material_05m.bgeo.sc')
print('=== Lesson 04 Working Material Layers ===')
for prim in w_l04.prims():
    if isinstance(prim, hou.Volume):
        print(f"  Layer: {prim.attribValue('name')} res={prim.resolution()}")

r, pr = vol_layer(w_l04, 'r')
g, pg = vol_layer(w_l04, 'g')
b, pb = vol_layer(w_l04, 'b')
h, ph = vol_layer(w_l04, 'height')
alpha, pa = vol_layer(w_l04, 'Alpha')
mask, pm = vol_layer(w_l04, 'mask')

print('Shape of r:', r.shape)
o = pr.indexToPos((0,0,0))
vx = pr.indexToPos((1,0,0)) - o
vy = pr.indexToPos((0,1,0)) - o
print(f"Origin={o}, vx={vx}, vy={vy}")
# Remember: index (col, row, 0)
# In numpy shape is (ny, nx) -> [row, col]
# row 0 is y=0 -> Pos=(o.x(), 0, o.z()) -> Z = +3144.25 (South!)
# row ny-1 is y=ny-1 -> Pos Z = 3144.25 - 9828*0.5 = -1769.75 (North!)
print(f"Row 0 Z={pr.indexToPos((0,0,0)).z()} (SOUTH)")
print(f"Row -1 Z={pr.indexToPos((0,r.shape[0]-1,0)).z()} (NORTH)")

print('South edge (row 0) r min/max:', r[0].min(), r[0].max())
print('North edge (row -1) r min/max:', r[-1].min(), r[-1].max())
print('North edge row -1 r < 0.05 count:', np.count_nonzero(r[-1] < 0.05), 'total:', r.shape[1])
print('North edge row -2 r < 0.05 count:', np.count_nonzero(r[-2] < 0.05))
print('North edge row -3 r < 0.05 count:', np.count_nonzero(r[-3] < 0.05))
print('North edge row -10 r < 0.05 count:', np.count_nonzero(r[-10] < 0.05))

print('Alpha row -1 (North) min/max:', alpha[-1].min(), alpha[-1].max() if alpha is not None else None)
print('Alpha row 0 (South) min/max:', alpha[0].min(), alpha[0].max() if alpha is not None else None)
print('Alpha total zero count:', np.count_nonzero(alpha == 0) if alpha is not None else None)
print('Height row -1 (North) min/max:', h[-1].min(), h[-1].max())
