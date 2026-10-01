"""Replace bounded shoulder-side ground with a stitched vertical cut/fill face.

Uses the existing transient DynamicMesh consumer. It clips the original ground
triangles before inserting faces, rather than covering ground with wall meshes.
This is a neutral geometry candidate, not engineering or human visual approval.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from scripts.geometry.local_terrain_skin import TerrainSkinMesh
from scripts.geometry.sp638_local_corridor import Vec3


def _cross(a, b, p):
    return (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x)


def _clip(poly, a, b, keep_left):
    result = []
    for p, q in zip(poly, poly[1:] + poly[:1]):
        dp, dq = _cross(a, b, p), _cross(a, b, q)
        ip = dp >= -1e-9 if keep_left else dp <= 1e-9
        iq = dq >= -1e-9 if keep_left else dq <= 1e-9
        if ip:
            result.append(p)
        if ip != iq:
            t = dp / (dp - dq)
            result.append(Vec3(p.x + t * (q.x - p.x), p.y + t * (q.y - p.y), p.z + t * (q.z - p.z)))
    return result


def _partition(poly, footprint):
    """Disjoint outside pieces plus the convex intersection, preserving winding."""
    inside, outside = poly, []
    for a, b in zip(footprint, footprint[1:] + footprint[:1]):
        piece = _clip(inside, a, b, False)
        if len(piece) >= 3:
            outside.append(piece)
        inside = _clip(inside, a, b, True)
        if len(inside) < 3:
            break
    return outside, inside


@dataclass(frozen=True)
class RetainingRepairResult:
    mesh: TerrainSkinMesh
    segment_count: int
    replaced_triangle_count: int
    vertical_face_triangle_count: int
    max_face_height_m: float


def sample_triangle_grid(xs, ys, heights, x, y):
    """Sample the exact (a,b,c)/(b,d,c) mesh surface, without clamping coverage."""
    if not xs[0] <= x <= xs[-1] or not ys[-1] <= y <= ys[0]:
        raise ValueError("repair tie-in lies outside native grid")
    fx, fy = (x-xs[0])/(xs[1]-xs[0]), (ys[0]-y)/(ys[0]-ys[1])
    col, row = min(int(fx),len(xs)-2), min(int(fy),len(ys)-2)
    u, v = fx-col, fy-row
    a,b,c,d = heights[row][col],heights[row][col+1],heights[row+1][col],heights[row+1][col+1]
    if u+v <= 1:
        return a*(1-u-v)+b*u+c*v
    return b*(1-v)+c*(1-u)+d*(u+v-1)


def replace_shoulder_ground(mesh, segments, *, sample_constrained, sample_native,
                            wall_fraction=0.15):
    """Execute non-overlapping convex shoulder-to-tie segments in mesh coordinates.

    Each segment has inner/outer start/end XY vertices and start/end strengths.
    Zero strength at the ends returns exactly to the existing ground. Side and
    interval selection belong to the BOB adapter, not this geometry kernel.
    Samples must use the original triangle surface, so carved boundary heights
    match retained triangles exactly. Unsupported overlapping regions fail closed.
    """
    if not 0.0 < wall_fraction < 1.0:
        raise ValueError("wall fraction must be inside the shoulder-to-tie span")
    vertices = list(mesh.vertices)
    triangles = list(mesh.triangles)
    replacements = {}
    walls, maximum = 0, 0.0

    def emit(poly, output):
        ids = []
        for p in poly:
            if not all(math.isfinite(v) for v in (p.x, p.y, p.z)):
                raise ValueError("repair generated a non-finite vertex")
            ids.append(len(vertices))
            vertices.append(p)
        for i in range(1, len(ids) - 1):
            a, b, c = (vertices[j] for j in (ids[0], ids[i], ids[i + 1]))
            ab, ac = b - a, c - a
            norm = ((ab.y * ac.z - ab.z * ac.y) ** 2
                    + (ab.z * ac.x - ab.x * ac.z) ** 2
                    + (ab.x * ac.y - ab.y * ac.x) ** 2)
            if norm > 1e-16:
                output.append((ids[0], ids[i], ids[i + 1]))

    for segment in segments:
        a, b, c, d = segment["inner_start"], segment["inner_end"], segment["outer_end"], segment["outer_start"]
        footprint = [a, b, c, d]
        area = sum(p.x * q.y - q.x * p.y for p, q in zip(footprint, footprint[1:] + footprint[:1]))
        if abs(area) < 1e-8:
            raise ValueError("repair footprint is degenerate")
        if area < 0:
            footprint.reverse()
        if any(_cross(footprint[i], footprint[(i + 1) % 4], footprint[(i + 2) % 4]) <= 1e-8 for i in range(4)):
            raise ValueError("repair footprint folds; competing branches require another representation")
        sa, sb = float(segment["start_strength"]), float(segment["end_strength"])
        if not (0 <= sa <= 1 and 0 <= sb <= 1):
            raise ValueError("repair taper strength must be bounded")
        wa = Vec3(a.x + wall_fraction * (d.x - a.x), a.y + wall_fraction * (d.y - a.y), 0)
        wb = Vec3(b.x + wall_fraction * (c.x - b.x), b.y + wall_fraction * (c.y - b.y), 0)
        inner_left = _cross(wa, wb, a) > 0
        lx, ly = b.x - a.x, b.y - a.y
        length2 = lx * lx + ly * ly
        if length2 < 1e-8:
            raise ValueError("repair segment has no longitudinal span")

        def levels(p, bench):
            # Projection selects the longitudinal station; lateral correction
            # uses that station's actual varying shoulder-to-tie vector.
            t, f = 0.5, 0.5
            vx0, vy0 = d.x-a.x, d.y-a.y
            dvx, dvy = c.x-b.x-vx0, c.y-b.y-vy0
            for _ in range(12):
                rx = a.x+t*lx+f*(vx0+t*dvx)-p.x
                ry = a.y+t*ly+f*(vy0+t*dvy)-p.y
                jtx, jty = lx+f*dvx, ly+f*dvy
                jfx, jfy = vx0+t*dvx, vy0+t*dvy
                det = jtx*jfy-jty*jfx
                if abs(det) < 1e-10:
                    raise ValueError("repair footprint has a singular lateral frame")
                t -= (rx*jfy-ry*jfx)/det
                f -= (jtx*ry-jty*rx)/det
            if not (-1e-6 <= t <= 1+1e-6 and -1e-6 <= f <= 1+1e-6):
                raise ValueError("repair sample escaped its footprint")
            t, f = max(0.0,min(1.0,t)), max(0.0,min(1.0,f))
            ix, iy = a.x+t*lx, a.y+t*ly
            ox, oy = d.x+t*(c.x-d.x), d.y+t*(c.y-d.y)
            vx, vy = ox-ix, oy-iy
            strength = sa + t * (sb - sa)
            wx, wy = ix + wall_fraction * vx, iy + wall_fraction * vy
            inner_z = sample_constrained(ix, iy)
            if bench:
                desired = inner_z
            else:
                outer_z = sample_constrained(ox, oy)
                native_z = sample_native(wx, wy)
                blend = max(0.0, min(1.0, (f - wall_fraction) / (1 - wall_fraction)))
                desired = native_z + blend * (outer_z - native_z)
            # Preserve all four footprint boundaries exactly. At the inner
            # edge use the original surface; at the outer edge do likewise.
            if f <= 1e-8 or f >= 1 - 1e-8 or strength <= 1e-9:
                return p
            return Vec3(p.x, p.y, p.z + strength * (desired - p.z))

        minx, maxx = min(p.x for p in footprint), max(p.x for p in footprint)
        miny, maxy = min(p.y for p in footprint), max(p.y for p in footprint)
        x0,y0 = mesh.vertices[0].x,mesh.vertices[0].y
        sx = mesh.vertices[1].x-x0
        sy = y0-mesh.vertices[mesh.column_count].y
        if sx <= 0 or sy <= 0:
            raise ValueError("repair requires the admitted ascending-X/descending-Y grid")
        first_col=max(0,int(math.floor((minx-x0)/sx))-1)
        last_col=min(mesh.column_count-2,int(math.ceil((maxx-x0)/sx))+1)
        first_row=max(0,int(math.floor((y0-maxy)/sy))-1)
        last_row=min(mesh.row_count-2,int(math.ceil((y0-miny)/sy))+1)
        candidates=(2*(row*(mesh.column_count-1)+col)+half
            for row in range(first_row,last_row+1)
            for col in range(first_col,last_col+1) for half in (0,1))
        for index in candidates:
            triangle=mesh.triangles[index]
            poly = [mesh.vertices[i] for i in triangle]
            if max(p.x for p in poly) < minx or min(p.x for p in poly) > maxx or max(p.y for p in poly) < miny or min(p.y for p in poly) > maxy:
                continue
            outside, inside = _partition(poly, footprint)
            if len(inside) < 3 or abs(sum(p.x*q.y-q.x*p.y for p,q in zip(inside,inside[1:]+inside[:1]))) < 1e-8:
                continue
            if index in replacements:
                # Adjacent segment boundaries may traverse the same grid
                # triangle. Repartition its retained pieces, not duplicate it.
                work = replacements[index]
            else:
                work = [poly]
            remaining, built = [], []
            consumed_area = 0.0
            for piece in work:
                outs, ins = _partition(piece, footprint)
                remaining.extend(outs)
                if len(ins) < 3:
                    continue
                consumed_area += abs(sum(p.x*q.y-q.x*p.y for p,q in zip(ins,ins[1:]+ins[:1])))
                for bench in (True, False):
                    part = _clip(ins, wa, wb, inner_left if bench else not inner_left)
                    if len(part) >= 3:
                        emit([levels(p, bench) for p in part], built)
                intersections = [p for p in _clip(ins, wa, wb, True) if abs(_cross(wa, wb, p)) < 1e-7]
                if len(intersections) >= 2:
                    intersections.sort(key=lambda p: p.x * lx + p.y * ly)
                    p, q = intersections[0], intersections[-1]
                    pb, qb, pn, qn = levels(p, True), levels(q, True), levels(p, False), levels(q, False)
                    if (pb.z-pn.z)*(qb.z-qn.z) < -1e-8:
                        raise ValueError("repair face switches cut/fill within one triangle")
                    maximum = max(maximum, abs(pb.z - pn.z), abs(qb.z - qn.z))
                    wall = [pb, qb, qn, pn]
                    # Face the higher side's exposed cut/fill toward the lower
                    # side; UE front faces reverse the conventional normal.
                    desired_x, desired_y = (-(wb.y-wa.y), wb.x-wa.x)
                    if not inner_left:
                        desired_x, desired_y = -desired_x, -desired_y
                    if (pn.z + qn.z) < (pb.z + qb.z):
                        desired_x, desired_y = -desired_x, -desired_y
                    ab, ac = wall[1]-wall[0], wall[2]-wall[0]
                    if (ab.y*ac.z-ab.z*ac.y)*desired_x + (ab.z*ac.x-ab.x*ac.z)*desired_y > 0:
                        wall.reverse()
                    before = len(built)
                    emit(wall, built)
                    walls += len(built)-before
            expected_area = abs(sum(p.x*q.y-q.x*p.y for p,q in zip(inside,inside[1:]+inside[:1])))
            if abs(expected_area-consumed_area) > 1e-6:
                raise ValueError("repair regions overlap; shared branch ground needs explicit ownership")
            replacements[index] = remaining
            # Generated surfaces are separate from retained original pieces,
            # so following segments can only consume untouched ground.
            triangles.extend(built)

    result = [t for i, t in enumerate(mesh.triangles) if i not in replacements]
    result.extend(triangles[len(mesh.triangles):])
    for pieces in replacements.values():
        for poly in pieces:
            emit(poly, result)
    return RetainingRepairResult(TerrainSkinMesh(tuple(vertices), tuple(result), mesh.row_count, mesh.column_count),
                                 len(segments), len(replacements), walls, maximum)
