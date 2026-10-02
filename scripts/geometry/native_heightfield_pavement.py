"""Clip a presentation footprint to native heightfield facets without terrain edits.

The caller must establish the quad diagonal against native engine measurements.
This preserves the heightfield's surface, including its roughness; it does not
regularize asphalt, infer geographic edges or provide gameplay collision.
"""
from __future__ import annotations

from collections import Counter
import math

from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon, box
from shapely.prepared import prep


def build_surface(outline, height_at_grid, *, cell_size=0.5, diagonal):
    if diagonal not in ('a_d', 'b_c') or cell_size <= 0:
        raise ValueError('Explicit native diagonal and positive cell size required')
    footprint = Polygon(outline)
    if not footprint.is_valid or footprint.is_empty or footprint.area <= 0:
        raise ValueError('Invalid pavement footprint; do not repair source silently')
    ready = prep(footprint)
    vertices, faces, ids = [], [], {}
    xmin,ymin,xmax,ymax = footprint.bounds
    c0,c1 = math.floor(xmin/cell_size), math.ceil(xmax/cell_size)
    r0,r1 = math.floor(ymin/cell_size), math.ceil(ymax/cell_size)
    if (c1-c0)*(r1-r0) > 500000:
        raise ValueError('Pavement trial exceeds bounded cell budget')
    for r in range(r0,r1):
        for c in range(c0,c1):
            x,y = c*cell_size,r*cell_size
            if not ready.intersects(box(x,y,x+cell_size,y+cell_size)):
                continue
            xy = [(x,y),(x+cell_size,y),(x,y+cell_size),(x+cell_size,y+cell_size)]
            z = [float(height_at_grid(*p)) for p in xy]
            if not all(math.isfinite(v) for v in z):
                raise ValueError('Nonfinite native grid height')
            cells = ((0,1,3),(0,3,2)) if diagonal == 'a_d' else ((0,1,2),(1,3,2))
            for indices in cells:
                native = Polygon([xy[i] for i in indices])
                clipped = native.intersection(footprint)
                if clipped.is_empty or clipped.area < 1e-12:
                    continue
                for tri in constrained_delaunay_triangles(clipped).geoms:
                    points = list(tri.exterior.coords)[:3]
                    # Clockwise top faces match the established UE corridor kernel.
                    if (points[1][0]-points[0][0])*(points[2][1]-points[0][1])-(points[1][1]-points[0][1])*(points[2][0]-points[0][0]) > 0:
                        points.reverse()
                    face=[]
                    for px,py in points:
                        u,v=(px-x)/cell_size,(py-y)/cell_size
                        if diagonal == 'a_d':
                            h=z[0]+(z[1]-z[0])*u+(z[3]-z[1])*v if indices[1] == 1 else z[0]+(z[3]-z[2])*u+(z[2]-z[0])*v
                        else:
                            h=z[0]+(z[1]-z[0])*u+(z[2]-z[0])*v if indices[0] == 0 else z[3]+(z[2]-z[3])*(1-u)+(z[1]-z[3])*(1-v)
                        key=round(px,8),round(py,8)
                        if key not in ids:
                            ids[key]=len(vertices);vertices.append([px,py,h])
                        elif abs(vertices[ids[key]][2]-h) > 1e-5:
                            raise ValueError('Conflicting shared native-facet height')
                        face.append(ids[key])
                    if len(set(face)) != 3:
                        raise ValueError('Degenerate native-facet pavement triangle')
                    faces.append(tuple(face))
    area=sum(abs((vertices[b][0]-vertices[a][0])*(vertices[c][1]-vertices[a][1])-(vertices[b][1]-vertices[a][1])*(vertices[c][0]-vertices[a][0]))*.5 for a,b,c in faces)
    if abs(area-footprint.area) > max(1e-6,footprint.area*1e-8):
        raise ValueError('Native-facet clipping lost or duplicated pavement coverage')
    return vertices,faces,{'footprint_area_m2':footprint.area,'mesh_area_xy_m2':area,
                          'native_diagonal':diagonal,'native_cell_size_m':cell_size}


def solidify(ground, faces, *, thickness=.08, burial=.04):
    if not 0 < burial < thickness:
        raise ValueError('Fixed burial must be inside nominal slab')
    top=[[x,y,z+thickness-burial] for x,y,z in ground]
    bottom=[[x,y,z-burial] for x,y,z in ground]
    n=len(top)
    triangles=list(faces)+[(a+n,c+n,b+n) for a,b,c in faces]
    counts=Counter(tuple(sorted(e)) for a,b,c in faces for e in ((a,b),(b,c),(c,a)))
    if any(v>2 for v in counts.values()):
        raise ValueError('Nonmanifold pavement top')
    for a,b,c in faces:
        for u,v in ((a,b),(b,c),(c,a)):
            if counts[tuple(sorted((u,v)))] == 1:
                triangles.extend([(v,u,u+n),(v,u+n,v+n)])
    return top+bottom,triangles
