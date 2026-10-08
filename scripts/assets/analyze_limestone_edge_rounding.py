"""Audit a narrow edge bevel against the complete untouched native source."""
from collections import Counter, defaultdict
import math


def _sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _area(a, b, c):
    return _cross(_sub(b, a), _sub(c, a))[2]/2


def audit_edges(plan, reference, evidence):
    from scripts.assets.analyze_local_cliff_smoothing import audit as audit_domain
    # The existing domain audit remains separately available to historical runs.
    contract = plan.get('rounding_domain_contract', {})
    cells = plan.get('rounding_cells', [])
    if (contract.get('method') != 'source-cliff-six-metre-crown-apron-v1'
            or contract.get('radius_m') != 6 or contract.get('classifier_unchanged') is not True
            or contract.get('hard_protected_samples') != 0
            or contract.get('cell_count') != len(cells) or contract.get('area_m2') != len(cells)
            or not 1017 <= len(cells) <= 3969):
        raise ValueError('Invalid protected edge eligibility domain')
    quads = set()
    for cell in cells:
        if (cell['protected_samples'] != 0 or cell['row1']-cell['row0'] != 2
                or cell['col1']-cell['col0'] != 2
                or not 882 <= cell['row0'] < cell['row1'] <= 1008
                or not 756 <= cell['col0'] < cell['col1'] <= 882):
            raise ValueError('Protected or invalid edge domain cell')
        for r in range(cell['row0'], cell['row1']):
            for c in range(cell['col0'], cell['col1']):
                if (c, r) in quads:
                    raise ValueError('Overlapping edge domain cells')
                quads.add((c, r))
    if len(plan['skin_cells']) != 1017 or not {(c, r) for a in plan['skin_cells']
            for r in range(a['row0'], a['row1']) for c in range(a['col0'], a['col1'])} <= quads:
        raise ValueError('Original classifier footprint changed')
    source = {int(r[0]): tuple(r[1:4]) for r in evidence['edge_source_vertices_cm']}
    originals = {tuple(r[1:3]): tuple(r[1:4]) for r in reference['vertices_cm']}
    if len(source) != 16129 or len(source) != len(evidence['edge_source_vertices_cm']):
        raise ValueError('Incomplete or duplicate native source')
    grid = {}
    for v, p in source.items():
        if (not all(math.isfinite(x) for x in p)
                or any(abs(x/50-round(x/50)) > 1e-6 for x in p[:2])
                or originals.get(p[:2]) != p):
            raise ValueError('Native source differs from original before erosion')
        grid[(round(p[0]/50), round(p[1]/50))] = v
    expected_faces = set()
    for y in range(882, 1008):
        for x in range(756, 882):
            a, b, c, d = [grid.get(k) for k in ((x,y),(x+1,y),(x,y+1),(x+1,y+1))]
            if None in (a,b,c,d):
                raise ValueError('Native source grid hole')
            expected_faces.update((tuple(sorted((a,c,d))), tuple(sorted((a,d,b)))))
    faces = evidence['edge_source_triangles']
    if len(faces) != 31752 or {tuple(sorted(f)) for f in faces} != expected_faces:
        raise ValueError('Native source topology changed')
    face_tiles, source_edges = defaultdict(list), defaultdict(list)
    safe = set(source)
    for f in faces:
        points = [source[i] for i in f]
        n = _cross(_sub(points[1], points[0]), _sub(points[2], points[0]))
        if n[2] >= 0:
            raise ValueError('Native source winding changed')
        n = tuple(-x/math.sqrt(_dot(n,n)) for x in n)
        tile = tuple(math.floor(sum(p[k] for p in points)/150) for k in (0,1))
        face_tiles[tile].append(f)
        if tile not in quads:
            safe.difference_update(f)
        for a,b in zip(f, f[1:]+f[:1]):
            source_edges[tuple(sorted((a,b)))].append((n,f))
    for e, adjacent in source_edges.items():
        if len(adjacent) == 1:
            safe.difference_update(e)
    selected = set()
    for (a,b), adjacent in source_edges.items():
        if len(adjacent) != 2 or a not in safe or b not in safe:
            continue
        (n0,f0),(n1,f1) = adjacent
        other = next(i for i in f1 if i not in (a,b))
        if _dot(n0,n1) < math.cos(math.radians(45)) and _dot(n0,_sub(source[other],source[a])) < -1:
            selected.add((a,b))
    recorded = evidence['rounded_source_edges']
    if not selected or len(recorded) != len(selected) or {tuple(sorted(e)) for e in recorded} != selected:
        raise ValueError('Rounded edge selection does not match original sharp convex edges')
    edge_vertices = {v for e in selected for v in e}
    edge_tiles = defaultdict(list)
    for a,b in selected:
        p,q = source[a],source[b]
        # A native edge spans at most one half-metre XY tile; index all touched tiles.
        for x in range(math.floor(min(p[0],q[0])/50),math.floor(max(p[0],q[0])/50)+1):
            for y in range(math.floor(min(p[1],q[1])/50),math.floor(max(p[1],q[1])/50)+1):
                edge_tiles[(x,y)].append((p,q))

    def band_distance(p):
        x,y = (math.floor(p[k]/50) for k in (0,1))
        best = float('inf')
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for a,b in edge_tiles[(x+dx,y+dy)]:
                    d = _sub(b,a)
                    u = max(0,min(1,_dot(_sub(p,a),d)/_dot(d,d)))
                    best = min(best,math.dist(p,tuple(a[k]+u*d[k] for k in range(3))))
        return best

    def containing_faces(p, on_surface=False):
        tile = tuple(math.floor(p[k]/50) for k in (0,1))
        found = set()
        heights = []
        for dx in (-1,0):
            for dy in (-1,0):
                for f in face_tiles[(tile[0]+dx,tile[1]+dy)]:
                    a,b,c = [source[i] for i in f]
                    d = _area(a,b,c)*2
                    u = _cross(_sub(p,a),_sub(c,a))[2]/d
                    w = _cross(_sub(b,a),_sub(p,a))[2]/d
                    z = a[2]+u*(b[2]-a[2])+w*(c[2]-a[2])
                    if u >= -1e-8 and w >= -1e-8 and u+w <= 1+1e-8:
                        heights.append(z)
                        if not on_surface or abs(z-p[2]) < 1e-5:
                            found.add(tuple(sorted(f)))
        return found, heights

    rows = evidence['vertices_cm']
    if len({r[0] for r in rows}) != len(rows) or any(len(r)!=8 or not all(math.isfinite(v) for v in r) for r in rows):
        raise ValueError('Invalid candidate vertex evidence')
    candidate = {int(r[0]): tuple(r[4:7]) for r in rows}
    before = {int(r[0]): tuple(r[1:4]) for r in rows}
    if not set(source) <= candidate.keys():
        raise ValueError('Bevel removed an original vertex')
    max_shift = max_band = 0
    changed = 0
    membership = {}
    band = {}
    for v,p in candidate.items():
        q = before[v]
        if v in source and q != source[v]:
            raise ValueError('Bevel reset original reference')
        if v not in source:
            _, heights = containing_faces(p)
            if not heights or q[:2] != p[:2] or min(abs(q[2]-h) for h in heights) > 1e-6:
                raise ValueError('New vertex reference is not original surface interpolation')
        shift = math.dist(q,p)
        if v in source and v not in edge_vertices and shift > 1e-8:
            raise ValueError('Bevel moved a vertex away from a selected edge')
        if shift > 20.000001:
            raise ValueError('Edge-only displacement exceeds 20 cm')
        if v not in source or shift > 1e-8:
            distance = max(band_distance(p),band_distance(q))
            if distance > 10.000001:
                raise ValueError('Edge treatment exceeds the 20 cm total band')
            max_band = max(max_band,distance)
            changed += 1
        max_shift = max(max_shift,shift)
        membership[v] = containing_faces(p,True)[0]
        band[v] = band_distance(p)
    candidate_faces = evidence['triangles']
    edges = Counter()
    area = 0
    if len(candidate_faces) > 60000 or len({tuple(sorted(f)) for f in candidate_faces}) != len(candidate_faces):
        raise ValueError('Triangle budget or duplicate face violation')
    for f in candidate_faces:
        if len(f)!=3 or len(set(f))!=3 or any(v not in candidate for v in f):
            raise ValueError('Invalid candidate face')
        signed = _area(*(candidate[v] for v in f))
        if signed >= -1e-8:
            raise ValueError('Folded or degenerate candidate triangle')
        area -= signed
        if not set.intersection(*(membership[v] for v in f)) and any(band[v] > 10.000001 for v in f):
            raise ValueError('Changed triangle surface extends outside the narrow edge band')
        for a,b in zip(f, f[1:]+f[:1]):
            edges[tuple(sorted((a,b)))] += 1
    if any(n>2 for n in edges.values()) or abs(area/10000-3969) > 1e-6:
        raise ValueError('Mesh manifold or original footprint violation')
    expected_boundary = {e for e,adj in source_edges.items() if len(adj)==1}
    if {e for e,n in edges.items() if n==1} != expected_boundary:
        raise ValueError('Source footprint boundary changed')
    if not changed:
        raise ValueError('Empty edge treatment')
    return dict(status='PASS',scope='LOCAL_EDGE_BAND_AUDIT_NOT_VISUAL_ACCEPTANCE',
        vertices=len(candidate), triangles=len(candidate_faces), rounded_edge_count=len(selected),
        changed_vertices=changed, source_area_m2=3969, candidate_area_m2=area/10000,
        eligibility_area_m2=len(cells), edge_band_radius_cm=10,
        max_edge_band_distance_cm=max_band, displacement_limit_cm=20,
        max_displacement_cm=max_shift, nonmanifold_edges=0, folded_xy_triangles=0,
        outside_edge_vertices_unchanged=True, outside_edge_surface_unchanged=True,
        terrain_heightfield_modified=False)
