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


def _segment_distance(p, a, b):
    d = _sub(b, a)
    length_squared = _dot(d, d)
    if length_squared == 0:
        return math.dist(p, a)
    u = max(0, min(1, _dot(_sub(p, a), d)/length_squared))
    return math.dist(p, tuple(a[k]+u*d[k] for k in range(3)))


def _certify_triangle_band(points, segments, unchanged=None, radius_cm=10,
                           max_depth=20, max_pieces=4096):
    """Bound every point, including triangle interiors, inside the capsule union.

    Distance to one finite segment is convex, so a common capsule containing
    all three vertices contains their whole triangle. For a union of capsules
    that argument no longer holds. Distance to the union is 1-Lipschitz: its
    value at the centroid plus the farthest corner distance is an upper bound
    everywhere on the triangle. Subdivide the longest edge when neither bound
    certifies a piece. An exhausted budget rejects; sampled points never grant
    acceptance by themselves.

    The caller can exempt a piece only when all corners belong to one unchanged
    source facet. A source triangle is convex, so this proves the whole piece.
    """
    limit = radius_cm + 1e-6
    pending = [(tuple(points), 0)]
    visited = 0
    certified_bound = 0.0
    while pending:
        piece, depth = pending.pop()
        visited += 1
        if visited > max_pieces:
            raise ValueError('Could not certify the complete narrow edge band within the subdivision budget')
        if unchanged is not None and unchanged(piece):
            continue
        if not segments:
            raise ValueError('Changed triangle surface extends outside the narrow edge band')
        distances = [[_segment_distance(p, a, b) for p in piece] for a, b in segments]
        if any(min(row[k] for row in distances) > limit for k in range(3)):
            raise ValueError('Changed triangle surface extends outside the narrow edge band')
        capsule_bound = min(max(row) for row in distances)
        if capsule_bound <= limit:
            certified_bound = max(certified_bound, capsule_bound)
            continue
        center = tuple(sum(p[k] for p in piece)/3 for k in range(3))
        center_distance = min(_segment_distance(center, a, b) for a, b in segments)
        if center_distance > limit:
            raise ValueError('Changed triangle surface extends outside the narrow edge band')
        lipschitz_bound = center_distance + max(math.dist(center, p) for p in piece)
        if lipschitz_bound <= limit:
            certified_bound = max(certified_bound, lipschitz_bound)
            continue
        if depth >= max_depth:
            raise ValueError('Could not certify the complete narrow edge band within the subdivision budget')
        i, j = max(((0, 1), (1, 2), (2, 0)), key=lambda pair: math.dist(piece[pair[0]], piece[pair[1]]))
        other = 3-i-j
        midpoint = tuple((piece[i][k]+piece[j][k])/2 for k in range(3))
        pending.extend((((piece[i], midpoint, piece[other]), depth+1),
                        ((midpoint, piece[j], piece[other]), depth+1)))
    return certified_bound


def audit_edges(plan, reference, evidence):
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
                    best = min(best, _segment_distance(p, a, b))
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

    def closest_triangle(p, a, b, c):
        ab, ac, ap = _sub(b,a), _sub(c,a), _sub(p,a)
        d1,d2 = _dot(ab,ap),_dot(ac,ap)
        if d1 <= 0 and d2 <= 0: return a
        bp = _sub(p,b); d3,d4 = _dot(ab,bp),_dot(ac,bp)
        if d3 >= 0 and d4 <= d3: return b
        vc = d1*d4-d3*d2
        if vc <= 0 and d1 >= 0 and d3 <= 0:
            v = d1/(d1-d3); return tuple(a[k]+v*ab[k] for k in range(3))
        cp = _sub(p,c); d5,d6 = _dot(ab,cp),_dot(ac,cp)
        if d6 >= 0 and d5 <= d6: return c
        vb = d5*d2-d1*d6
        if vb <= 0 and d2 >= 0 and d6 <= 0:
            w = d2/(d2-d6); return tuple(a[k]+w*ac[k] for k in range(3))
        va = d3*d6-d5*d4
        if va <= 0 and d4-d3 >= 0 and d5-d6 >= 0:
            w = (d4-d3)/((d4-d3)+(d5-d6)); return tuple(b[k]+w*(c[k]-b[k]) for k in range(3))
        denominator = 1/(va+vb+vc); v,w = vb*denominator,vc*denominator
        return tuple(a[k]+v*ab[k]+w*ac[k] for k in range(3))

    def closest_source_distance(p):
        x,y = (math.floor(p[k]/50) for k in (0,1))
        distances = [math.dist(p,closest_triangle(p,*(source[i] for i in f)))
            for dx in (-1,0,1) for dy in (-1,0,1) for f in face_tiles[(x+dx,y+dy)]]
        return min(distances,default=float('inf'))

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
    for v,p in candidate.items():
        q = before[v]
        if v in source and v not in edge_vertices and q != source[v]:
            raise ValueError('Bevel reset original reference')
        if v not in source or v in edge_vertices:
            on_surface,_ = containing_faces(q,True)
            if not on_surface or abs(math.dist(p,q)-closest_source_distance(p)) > 1e-5:
                raise ValueError('New vertex reference is not the nearest untouched source surface')
        shift = math.dist(q,p)
        if v in source and v not in edge_vertices and shift > 1e-8:
            raise ValueError('Bevel moved a vertex away from a selected edge')
        if shift > 20.000001:
            raise ValueError('Edge-only displacement exceeds 20 cm')
        if v not in source or math.dist(p,source[v]) > 1e-8:
            distance = max(band_distance(p),band_distance(q))
            if distance > 10.000001:
                raise ValueError('Edge treatment exceeds the 20 cm total band')
            max_band = max(max_band,distance)
            changed += 1
        max_shift = max(max_shift,shift)
        membership[v] = containing_faces(p,True)[0]
    candidate_faces = evidence['triangles']
    edges = Counter()
    area = 0
    certified_triangles = 0
    max_surface_band = 0

    def unchanged_source_piece(points):
        return bool(set.intersection(*(containing_faces(p, True)[0] for p in points)))

    if len(candidate_faces) > 60000 or len({tuple(sorted(f)) for f in candidate_faces}) != len(candidate_faces):
        raise ValueError('Triangle budget or duplicate face violation')
    for f in candidate_faces:
        if len(f)!=3 or len(set(f))!=3 or any(v not in candidate for v in f):
            raise ValueError('Invalid candidate face')
        signed = _area(*(candidate[v] for v in f))
        if signed >= -1e-8:
            raise ValueError('Folded or degenerate candidate triangle')
        area -= signed
        if not set.intersection(*(membership[v] for v in f)):
            points = tuple(candidate[v] for v in f)
            # Include every capsule that could cover any point of this triangle.
            # Omitting a farther capsule can only tighten the conservative bound.
            nearby = set()
            for x in range(math.floor(min(p[0] for p in points)/50)-1,
                           math.floor(max(p[0] for p in points)/50)+2):
                for y in range(math.floor(min(p[1] for p in points)/50)-1,
                               math.floor(max(p[1] for p in points)/50)+2):
                    nearby.update(edge_tiles[(x, y)])
            bound = _certify_triangle_band(points, tuple(nearby), unchanged_source_piece)
            max_surface_band = max(max_surface_band, bound)
            certified_triangles += 1
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
        complete_changed_triangle_band_certified=True,
        band_certification='adaptive-lipschitz-and-convex-capsules-v1',
        certified_changed_triangles=certified_triangles,
        max_certified_triangle_band_cm=max_surface_band,
        max_displacement_cm=max_shift, nonmanifold_edges=0, folded_xy_triangles=0,
        outside_edge_vertices_unchanged=True, outside_edge_surface_unchanged=True,
        native_source_vertices_unchanged=all(
            math.dist(candidate[v], p) <= 1e-8 for v, p in source.items()),
        terrain_heightfield_modified=False)
