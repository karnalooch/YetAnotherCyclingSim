"""Two sparse, source-triangle-clipped asphalt crack candidates in SI units.

The event station uses the same 3D mean-cross-section centreline as the retained
TPP camera plan. A fixed orthonormal event frame owns UV0; clipping intersects
its [0, 1] square with each explicitly ordered source face. This is separate
render geometry, never a decal volume, a fitted four-corner surface or a search
for another nearby road level. Every output vertex retains all three source
barycentric weights. The native consumer must read the exact source triangle
and interpolate its recorded split normals under a separate payload hash.

The common +Z 1 mm translation is applied once. The source loader has already
applied the accepted hairpin lift. Entire footprint polygons, including their
transparent border, stay at least 10 cm inside the existing paint bands.
Neither source positions/indices/normals/UV nor the existing paint are edited.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import hashlib
import math
import re
import struct

from scripts.proof import sa_calobra_tpp_survey as survey
from scripts.ue import road_edge_marking_geometry as paint

MAX_EVENTS = 2
MAX_VERTICES = 24000
MAX_TRIANGLES = 16000
MAX_FRAGMENTS = 6000
SURFACE_OFFSET_M = 0.001
PAINT_SETBACK_M = 0.12
PAINT_WIDTH_M = 0.10
PAINT_CLEARANCE_M = 0.10
MIN_EDGE_DISTANCE_M = PAINT_SETBACK_M + PAINT_WIDTH_M + PAINT_CLEARANCE_M
CORNER_OFFSETS = ((0, 0), (0, 1), (1, 0), (1, 1))
EPSILON = 1e-12


@dataclass(frozen=True)
class CrackEvent:
    event_id: str
    motif_id: str
    window_id: str
    station_m: float
    extent_m: float
    lateral_offset_m: float = 0.0
    rotation_deg: float = 0.0
    anchor_frame_id: str = ""
    expected_centre_cm: tuple[float, float, float] | None = None


# These are authored canary positions, not a distribution across the world.
# Identity and station/centre are retained native-9519 camera-plan values.
CANARY_EVENTS = (
    CrackEvent("ordinary_0112", "drifting_interrupted",
               "reviewed-VIAL_TR70190001272-1-interval-24-0", 35.533179724061036, 1.8,
               anchor_frame_id="window-0112-forward-00002",
               expected_centre_cm=(58972.43407088867, 52130.994966778686, 46408.89952744225)),
    CrackEvent("nudo_0082", "short_oblique", "nudo-0", 39.94374219674143, 1.4,
               rotation_deg=90.0,
               anchor_frame_id="window-0082-forward-00002",
               expected_centre_cm=(125897.40827086054, 39245.2767894417, 67462.5197009283)),
)


@dataclass(frozen=True)
class CrackMesh:
    event_id: str
    motif_id: str
    owner_label: str
    window_id: str
    extent_m: float
    uv_rotation_degrees: float
    positions_m: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]
    normals: tuple[tuple[float, float, float], ...]
    uv0: tuple[tuple[float, float], ...]
    barycentric_weights: tuple[tuple[float, float, float], ...]
    fragments: tuple[paint.MarkingFragment, ...]


@dataclass(frozen=True)
class CrackBuild:
    manifest: dict
    meshes: tuple[CrackMesh, ...]


@dataclass(frozen=True)
class _Vertex:
    weights: tuple[float, float, float]
    uv: tuple[float, float]


def require(value, message):
    if not value:
        raise ValueError(message)


def _unit(values):
    length = math.hypot(*values)
    require(math.isfinite(length) and length > EPSILON, "Crack event has a degenerate frame/face")
    return tuple(value / length for value in values)


def _dot(a, b):
    return math.fsum(x * y for x, y in zip(a, b, strict=True))


def _event(event):
    require(isinstance(event, CrackEvent), "Expected explicit CrackEvent")
    require(all(isinstance(value, str) and re.fullmatch(r"[a-z0-9_]{1,64}", value)
                for value in (event.event_id, event.motif_id)), "Invalid crack event/motif identity")
    paint._identifier(event.window_id, "crack window_id")
    for name in ("station_m", "extent_m", "lateral_offset_m", "rotation_deg"):
        paint._finite(getattr(event, name), name)
    require(0 <= event.station_m <= 100000 and 0.5 <= event.extent_m <= 2.0
            and abs(event.lateral_offset_m) <= 1.0 and -180 <= event.rotation_deg <= 180,
            "Crack event exceeds its bounded local appearance range")
    require(isinstance(event.anchor_frame_id, str) and len(event.anchor_frame_id) <= 96,
            "Crack camera anchor identity is unbounded")
    if event.expected_centre_cm is not None:
        require(isinstance(event.expected_centre_cm, tuple) and len(event.expected_centre_cm) == 3
                and all(type(v) in (int, float) and math.isfinite(v) for v in event.expected_centre_cm),
                "Invalid retained crack camera anchor")


def _frame(rows, event):
    centres, stations, duplicates = survey._centreline({"sections": rows})
    # Dropped duplicate centres would destroy the one-to-one source-row address
    # used below. Do not silently pick a different section or road level.
    require(duplicates == 0 and len(centres) == len(rows) and 0 < event.station_m < stations[-1],
            "Crack station is outside its unchanged source-row centreline")
    centre, forward = survey._pose(centres, stations, event.station_m)
    if event.expected_centre_cm is not None:
        require(max(abs(p * 100.0 - q) for p, q in zip(centre, event.expected_centre_cm, strict=True)) <= 0.0001,
                "Crack station no longer matches its retained camera-plan source centre")
    section = next(i for i in range(len(stations) - 1) if stations[i] <= event.station_m < stations[i + 1])
    fraction = (event.station_m - stations[section]) / (stations[section + 1] - stations[section])
    across = tuple((1 - fraction) * (rows[section][24][axis] - rows[section][0][axis])
                   + fraction * (rows[section + 1][24][axis] - rows[section + 1][0][axis])
                   for axis in range(3))
    projection = _dot(across, forward)
    across = _unit(tuple(across[axis] - projection * forward[axis] for axis in range(3)))
    origin = tuple(centre[axis] + event.lateral_offset_m * across[axis] for axis in range(3))
    angle = math.radians(event.rotation_deg)
    cosine, sine = math.cos(angle), math.sin(angle)
    if event.rotation_deg in (-180.0, -90.0, 0.0, 90.0, 180.0):
        cosine, sine = float(round(cosine)), float(round(sine))
    u = tuple(cosine * across[axis] + sine * forward[axis] for axis in range(3))
    v = tuple(-sine * across[axis] + cosine * forward[axis] for axis in range(3))
    require(abs(_dot(u, v)) < 1e-10, "Crack event UV frame is not orthonormal")
    # A named local source interval prevents projection onto a second branch
    # of the same owner. Full-square coverage must still be proved after clip.
    interval = (max(0.0, event.station_m - 2 * event.extent_m),
                min(stations[-1], event.station_m + 2 * event.extent_m))
    return origin, u, v, stations, {"centre_m": list(centre), "origin_m": list(origin),
        "u_unit": list(u), "v_unit": list(v), "source_station_interval_m": list(interval),
        "station_contract": "retained_tpp_mean_cross_section_cumulative_3d_length",
        "frame_contract": "fixed_orthonormal_source_across_and_positive_station_with_authored_rotation"}


def _clip(polygon, axis, limit, above):
    if not polygon:
        return []
    result, previous = [], polygon[-1]
    previous_inside = previous.uv[axis] >= limit if above else previous.uv[axis] <= limit
    for current in polygon:
        inside = current.uv[axis] >= limit if above else current.uv[axis] <= limit
        if inside != previous_inside:
            t = (limit - previous.uv[axis]) / (current.uv[axis] - previous.uv[axis])
            weights = tuple((1 - t) * a + t * b for a, b in zip(previous.weights, current.weights, strict=True))
            uv = [(1 - t) * a + t * b for a, b in zip(previous.uv, current.uv, strict=True)]
            uv[axis] = limit
            result.append(_Vertex(weights, tuple(uv)))
        if inside:
            result.append(current)
        previous, previous_inside = current, inside
    return result


def _barycentric(uv, triangle_uv):
    a, b, c = triangle_uv
    ab, ac, ap = tuple(b[i] - a[i] for i in range(2)), tuple(c[i] - a[i] for i in range(2)), tuple(uv[i] - a[i] for i in range(2))
    determinant = ab[0] * ac[1] - ab[1] * ac[0]
    require(abs(determinant) > EPSILON, "Source crack face has a degenerate UV projection")
    second = (ap[0] * ac[1] - ap[1] * ac[0]) / determinant
    third = (ab[0] * ap[1] - ab[1] * ap[0]) / determinant
    return 1 - second - third, second, third


def _resolve(vertex, keys, points, uvs, edge_cache):
    """Resolve shared source edges once; full-three-weight corners stay on-face."""
    weights = vertex.weights
    support = [index for index, weight in enumerate(weights) if weight > EPSILON]
    require(support and min(weights) >= -EPSILON, "Clipped crack vertex escaped its source triangle")
    uv = tuple(float(round(value)) if abs(value - round(value)) < EPSILON else value for value in vertex.uv)
    if len(support) == 1:
        index = support[0]
        return points[index], uvs[index], tuple(1.0 if other == index else 0.0 for other in range(3))
    if len(support) == 2:
        first, second = sorted(support, key=lambda index: keys[index])
        boundaries = [(axis, float(bound)) for axis in range(2) for bound in (0, 1)
                      if uv[axis] == bound and abs(uvs[second][axis] - uvs[first][axis]) > EPSILON]
        require(boundaries, "Crack source-edge intersection has no explicit footprint boundary")
        axis, bound = boundaries[0]
        cache_key = (keys[first], keys[second], axis, bound)
        if cache_key not in edge_cache:
            t = (bound - uvs[first][axis]) / (uvs[second][axis] - uvs[first][axis])
            require(-EPSILON <= t <= 1 + EPSILON, "Crack source-edge intersection is outside its source edge")
            t = min(1.0, max(0.0, t))
            point = tuple(a + t * (b - a) for a, b in zip(points[first], points[second], strict=True))
            resolved_uv = [a + t * (b - a) for a, b in zip(uvs[first], uvs[second], strict=True)]
            resolved_uv[axis] = bound
            resolved_uv = tuple(float(round(value)) if abs(value - round(value)) < EPSILON else value
                                for value in resolved_uv)
            edge_cache[cache_key] = point, resolved_uv, t
        point, uv, t = edge_cache[cache_key]
        weights = tuple(1 - t if index == first else t if index == second else 0.0 for index in range(3))
        return point, uv, weights
    # A footprint corner can lie strictly inside a source triangle. Resolve
    # its complete barycentric coordinates; a two-weight shortcut is invalid.
    require(all(value in (0.0, 1.0) for value in uv), "Interior clipped crack vertex is not a footprint corner")
    weights = _barycentric(uv, uvs)
    require(min(weights) >= -EPSILON, "Footprint corner lies outside its source triangle")
    weights = tuple(max(0.0, value) for value in weights)
    total = math.fsum(weights)
    weights = tuple(value / total for value in weights)
    point = tuple(math.fsum(weights[corner] * points[corner][axis] for corner in range(3)) for axis in range(3))
    return point, uv, weights


def _patch_boundary(mesh):
    edges, uv_by_point = Counter(), {}
    for point, uv in zip(mesh.positions_m, mesh.uv0, strict=True):
        require(point not in uv_by_point or uv_by_point[point] == uv, "Crack UV discontinuity on a shared source edge")
        uv_by_point[point] = uv
    for face in mesh.triangles:
        points = [mesh.positions_m[index] for index in face]
        for a, b in zip(points, points[1:] + points[:1], strict=True):
            edges[tuple(sorted((a, b)))] += 1
    require(edges and all(count in (1, 2) for count in edges.values()), "Crack footprint is empty or non-manifold")
    adjacency = defaultdict(set)
    for (a, b), count in edges.items():
        if count == 1:
            uv_a, uv_b = uv_by_point[a], uv_by_point[b]
            require(any(uv_a[axis] == uv_b[axis] == bound for axis in range(2) for bound in (0.0, 1.0)),
                    "Crack footprint has an interior gap or a missing source face")
            adjacency[a].add(b)
            adjacency[b].add(a)
    require(adjacency and all(len(neighbours) == 2 for neighbours in adjacency.values()),
            "Crack footprint boundary is not a closed loop")
    seen, pending = set(), [next(iter(adjacency))]
    while pending:
        point = pending.pop()
        if point not in seen:
            seen.add(point)
            pending.extend(adjacency[point] - seen)
    require(seen == set(adjacency), "Crack footprint contains disconnected boundaries")


def mesh_sha256(mesh):
    require(isinstance(mesh, CrackMesh), "Expected immutable CrackMesh")
    digest = hashlib.sha256(b"YACS_LOCAL_ROAD_CRACK_MESH_V1\0")
    digest.update((mesh.event_id + "\0" + mesh.motif_id + "\0" + mesh.owner_label + "\0" + mesh.window_id).encode())
    digest.update(struct.pack("<2d", mesh.extent_m, mesh.uv_rotation_degrees))
    for rows, fmt in ((mesh.positions_m, "<3d"), (mesh.triangles, "<3I"), (mesh.normals, "<3d"),
                      (mesh.uv0, "<2d"), (mesh.barycentric_weights, "<3d")):
        digest.update(struct.pack("<I", len(rows)))
        for row in rows:
            digest.update(struct.pack(fmt, *row))
    digest.update(struct.pack("<I", len(mesh.fragments)))
    for fragment in mesh.fragments:
        digest.update(struct.pack("<7I", *fragment.source_triangle, fragment.first_vertex, fragment.vertex_count,
                                  fragment.first_triangle, fragment.triangle_count))
    return digest.hexdigest()


def needed_faces(build):
    require(isinstance(build, CrackBuild), "Expected clipped CrackBuild")
    return tuple(sorted({(mesh.owner_label, *fragment.source_triangle)
                         for mesh in build.meshes for fragment in mesh.fragments}))


def _mesh(owner, event, topology):
    rows, distances, _, source_hash = paint._source_sections(owner, MIN_EDGE_DISTANCE_M)
    origin, u, v, stations, frame = _frame(rows, event)
    uv_rows = tuple(tuple(tuple(0.5 + _dot(tuple(point[axis] - origin[axis] for axis in range(3)), vector)
                                   / event.extent_m for vector in (u, v)) for point in row) for row in rows)
    positions, triangles, normals, uv0, barycentric, fragments = [], [], [], [], [], []
    edge_cache, signs, projected_area, minimum_edge_distance = {}, set(), 0.0, math.inf
    start, end = frame["source_station_interval_m"]
    for section in range(len(rows) - 1):
        if stations[section + 1] < start or stations[section] > end:
            continue
        for cell in range(24):
            for slot, triangle in enumerate(topology):
                keys = tuple((section + CORNER_OFFSETS[i][0], cell + CORNER_OFFSETS[i][1]) for i in triangle)
                points = tuple(rows[i][j] for i, j in keys)
                uvs = tuple(uv_rows[i][j] for i, j in keys)
                if any(max(uv[axis] for uv in uvs) < 0 or min(uv[axis] for uv in uvs) > 1 for axis in range(2)):
                    continue
                polygon = [_Vertex(tuple(1.0 if index == corner else 0.0 for index in range(3)), uv)
                           for corner, uv in enumerate(uvs)]
                for axis, limit, above in ((0, 0., True), (0, 1., False), (1, 0., True), (1, 1., False)):
                    polygon = _clip(polygon, axis, limit, above)
                if len(polygon) < 3:
                    continue
                resolved = []
                for vertex in polygon:
                    value = _resolve(vertex, keys, points, uvs, edge_cache)
                    if not resolved or value[0] != resolved[-1][0]:
                        resolved.append(value)
                if len(resolved) > 1 and resolved[0][0] == resolved[-1][0]:
                    resolved.pop()
                if len(resolved) < 3:
                    continue
                face_cross = paint._cross(*points)
                normal = _unit(face_cross)
                require(abs(normal[2]) > 1e-6, "Crack footprint reached a vertical source face")
                sign = math.copysign(1.0, (uvs[1][0] - uvs[0][0]) * (uvs[2][1] - uvs[0][1])
                                      - (uvs[1][1] - uvs[0][1]) * (uvs[2][0] - uvs[0][0]))
                local_faces, local_area = [], 0.0
                for index in range(1, len(resolved) - 1):
                    indices = (0, index, index + 1)
                    cross = paint._cross(*(resolved[i][0] for i in indices))
                    if math.hypot(*cross) <= EPSILON:
                        continue
                    require(_dot(cross, normal) > 0, "Crack clipping changed source face winding")
                    a, b, c = (resolved[i][1] for i in indices)
                    area = ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2
                    require(sign * area > 0, "Crack source folds across the local UV footprint")
                    local_faces.append(indices)
                    local_area += abs(area)
                if not local_faces:
                    continue
                signs.add(sign)
                require(len(signs) == 1, "Crack footprint spans folded or reversed source faces")
                require(len(positions) + len(resolved) <= MAX_VERTICES
                        and len(triangles) + len(local_faces) <= MAX_TRIANGLES
                        and len(fragments) < MAX_FRAGMENTS, "Local crack geometry exceeds its bounded budget")
                first_vertex, first_triangle = len(positions), len(triangles)
                for point, uv, weights in resolved:
                    left = math.fsum(weights[k] * distances[i][j] for k, (i, j) in enumerate(keys))
                    right = math.fsum(weights[k] * (distances[i][-1] - distances[i][j])
                                      for k, (i, j) in enumerate(keys))
                    minimum_edge_distance = min(minimum_edge_distance, left, right)
                    require(min(left, right) >= MIN_EDGE_DISTANCE_M,
                            "Crack footprint would touch the existing edge paint or leave the pavement interior")
                    require(all(-EPSILON <= value <= 1 + EPSILON for value in uv), "Crack UV escaped its local source extent")
                    positions.append((point[0], point[1], point[2] + SURFACE_OFFSET_M))
                    uv0.append(uv)
                    normals.append(normal)
                    barycentric.append(weights)
                triangles.extend(tuple(first_vertex + i for i in face) for face in local_faces)
                fragments.append(paint.MarkingFragment((section, cell, slot), first_vertex, len(resolved),
                                                       first_triangle, len(local_faces)))
                projected_area += local_area
    require(triangles and abs(projected_area - 1.0) <= 1e-8,
            "Crack source faces do not cover exactly one complete local UV square")
    mesh = CrackMesh(event.event_id, event.motif_id, owner["support_label"], event.window_id, event.extent_m,
                     float(event.rotation_deg),
                     tuple(positions), tuple(triangles), tuple(normals), tuple(uv0), tuple(barycentric), tuple(fragments))
    _patch_boundary(mesh)
    return mesh, {"event": asdict(event), "support_label": owner["support_label"], "kind": owner["kind"],
                  "frame": frame, "pavement_sections_sha256": source_hash, "mesh_sha256": mesh_sha256(mesh),
                  "vertex_count": len(positions), "triangle_count": len(triangles), "fragment_count": len(fragments),
                  "complete_uv_square_area": projected_area, "minimum_source_edge_distance_m": minimum_edge_distance,
                  "minimum_clearance_to_paint_m": minimum_edge_distance - PAINT_SETBACK_M - PAINT_WIDTH_M,
                  "source_winding_preserved": True, "single_closed_footprint_verified": True}


def build_cracks(source_plan, *, quad_triangles, events=CANARY_EVENTS):
    """Pure bounded clipping; source authentication and native agreement are separate."""
    topology = paint._quad_topology(quad_triangles)
    identity, raw_identity, owners, excluded, total_rows = paint._source_inventory(source_plan)
    require(isinstance(events, (tuple, list)) and 0 < len(events) <= MAX_EVENTS, "Crack event inventory is empty or unbounded")
    for event in events:
        _event(event)
    require(len({event.event_id for event in events}) == len(events)
            and len({event.window_id for event in events}) == len(events),
            "The sparse crack canaries require separate event and source-window identities")
    by_window = {owner["window_id"]: owner for owner in owners}
    meshes, summaries = [], []
    for event in events:
        require(event.window_id in by_window, "Crack event has no exact source pavement owner")
        mesh, summary = _mesh(by_window[event.window_id], event, topology)
        meshes.append(mesh)
        summaries.append(summary)
    manifest = {
        "schema_version": 1, "status": "SOURCE_DERIVED_LOCAL_CRACK_CANDIDATE",
        "source_identity": identity, "source_identity_sha256": hashlib.sha256(raw_identity).hexdigest(),
        "quad_triangles": [list(face) for face in topology], "events": summaries,
        "surface_offset_m": SURFACE_OFFSET_M, "surface_offset_axis": "world_positive_z",
        "uv0": {"channel": 0, "range": [0.0, 1.0], "u": "across_road_station",
                "v": "along_positive_road_station", "projection": "fixed_source_event_frame",
                "named_axes": "source_frame_before_explicit_event_uv_rotation",
                "interpolation": "source_triangle_barycentric", "shader_uv_rotation": False},
        "paint_exclusion": {"setback_m": PAINT_SETBACK_M, "width_m": PAINT_WIDTH_M,
                            "additional_clearance_m": PAINT_CLEARANCE_M, "entire_footprint_checked": True},
        "counts": {"source_owner_count": len(owners) + len(excluded), "pavement_owner_count": len(owners),
                   "excluded_parapet_count": len(excluded), "source_section_count": total_rows,
                   "mesh_count": len(meshes), "vertex_count": sum(len(mesh.positions_m) for mesh in meshes),
                   "triangle_count": sum(len(mesh.triangles) for mesh in meshes)},
        "source_geometry_mutated": False, "road_uv_mutated": False, "existing_paint_mutated": False,
        "source_normals_are_flat_witness_only": True, "native_split_normal_interpolation_required": True,
        "normal_world_space_canary_required": True, "native_surface_correspondence_verified": False,
        "native_consumer_verified": False, "owner_visual_pass": False, "physics_authored": False,
        "performance_status": "DEFERRED_AFTER_M3", "performance_pass": False,
    }
    require(len(paint._json_bytes(manifest)) <= paint.MAX_MANIFEST_BYTES, "Crack manifest exceeds its explicit bound")
    return CrackBuild(manifest, tuple(meshes))
