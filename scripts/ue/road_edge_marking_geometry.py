"""Pure, source-derived edge paint payloads; no Unreal, source edits or physics.

``build_markings`` consumes the authenticated plan from ``road_shoulder_sources``.
Its pavement samples already contain the accepted hairpin's 0.04 m lift. Each
paint band is clipped in barycentric coordinates to the actual two triangles
of each source quad, never fitted through four non-coplanar corners. The caller
MUST supply their ordered corner triples from the pinned pavement producer;
this module cannot infer the saved road's diagonal or certify native agreement.

SI units throughout. UV0 U is (cross-section distance - setback) / width,
from the outside to the inside of BOTH edge bands. Distance follows the 25
source samples in 3D, not a new perpendicular-distance survey. UV0 V is metres
along the respective source boundary, reset for each owner and interpolated
on the source triangle. No owner endpoints are joined, even when coincident.

The sole render lift is ``surface_offset_m`` in world +Z. A common translation
keeps neighbouring clipped faces coincident; offsets along separate face
normals would open cracks on twisted quads. Normals retain the ordered source
triangle's mathematical cross product. A separate native consumer must verify
the source correspondence/winding and enforce the render-only requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import struct


MAX_OWNERS = 186
MAX_SECTIONS_PER_OWNER = 5000
MAX_TOTAL_SECTIONS = 20000
MAX_OUTPUT_VERTICES = 1000000
MAX_OUTPUT_TRIANGLES = 750000
MAX_MANIFEST_BYTES = 512 * 1024
MAX_SOURCE_IDENTITY_BYTES = 16 * 1024
MAX_COORDINATE_M = 1000000.0
MAX_SOURCE_SPAN_M = 100.0
MIN_SOURCE_SPAN_M = 1e-8
MIN_SOURCE_PROJECTED_AREA_M2 = 1e-12
SECTION_POINT_COUNT = 25
EDGES = ("edge0", "edge24")
_QUAD_OFFSETS = ((0, 0), (0, 1), (1, 0), (1, 1))


@dataclass(frozen=True)
class MarkingAppearance:
    """Owner-selected appearance values in metres, not a road marking standard."""

    width_m: float = 0.10
    setback_m: float = 0.12
    surface_offset_m: float = 0.001


@dataclass(frozen=True)
class MarkingFragment:
    """Payload span owned by (section, lateral cell, supplied triangle slot).

    These three source indices are NOT native road triangle IDs. Vertices and
    triangles use zero-based indices within their containing MarkingMesh.
    """

    source_triangle: tuple[int, int, int]
    first_vertex: int
    vertex_count: int
    first_triangle: int
    triangle_count: int


@dataclass(frozen=True)
class MarkingMesh:
    """Separate immutable payload, deliberately excluded from the manifest."""

    owner_label: str
    window_id: str
    edge: str
    positions_m: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]
    normals: tuple[tuple[float, float, float], ...]
    uv0: tuple[tuple[float, float], ...]
    barycentric_weights: tuple[tuple[float, float, float], ...]
    fragments: tuple[MarkingFragment, ...]


@dataclass(frozen=True)
class MarkingBuild:
    manifest: dict
    meshes: tuple[MarkingMesh, ...]


@dataclass(frozen=True)
class _ClipVertex:
    weights: tuple[float, float, float]
    distance_m: float


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _finite(value, name):
    _require(type(value) in (int, float) and math.isfinite(value), name + " must be finite")
    return float(value)


def _json_bytes(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        raise ValueError("Marking metadata must be bounded finite JSON") from error


def _identifier(value, name):
    _require(isinstance(value, str) and 0 < len(value) <= 192
             and all(32 <= ord(char) < 127 for char in value), name + " is missing or unbounded")
    return value


def _appearance_values(appearance):
    _require(isinstance(appearance, MarkingAppearance), "Expected MarkingAppearance")
    width = _finite(appearance.width_m, "width_m")
    setback = _finite(appearance.setback_m, "setback_m")
    offset = _finite(appearance.surface_offset_m, "surface_offset_m")
    _require(0.0001 <= width <= 0.5 and 0 <= setback <= 2.0 and 0 <= offset <= 0.005,
             "Appearance exceeds the bounded render-only candidate range")
    return width, setback, offset


def _cross(a, b, c):
    ab = tuple(y - x for x, y in zip(a, b))
    ac = tuple(y - x for x, y in zip(a, c))
    return (ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0])


def _quad_topology(quad_triangles):
    _require(isinstance(quad_triangles, (list, tuple)) and len(quad_triangles) == 2,
             "Supply the two ordered source quad triangles explicitly")
    result = []
    reference = ((0., 0., 0.), (1., 0., 0.), (0., 1., 0.), (1., 1., 0.))
    signs = []
    for triangle in quad_triangles:
        _require(isinstance(triangle, (list, tuple)) and len(triangle) == 3
                 and all(type(x) is int and 0 <= x <= 3 for x in triangle)
                 and len(set(triangle)) == 3, "Invalid ordered source quad triangle")
        result.append(tuple(triangle))
        signs.append(_cross(*(reference[index] for index in triangle))[2])
    shared = set(result[0]) & set(result[1])
    _require(shared in ({0, 3}, {1, 2}) and set(result[0]) | set(result[1]) == set(range(4))
             and signs[0] == signs[1], "Source triangles must cover one quad with consistent winding")
    return tuple(result)


def _source_inventory(source_plan):
    _require(isinstance(source_plan, dict), "Expected authenticated source plan")
    identity, owners = source_plan.get("source_identity"), source_plan.get("owners")
    _require(isinstance(identity, dict) and type(identity.get("support_source_schema_version")) is int
             and identity["support_source_schema_version"] == 1
             and identity.get("geometry_consumers_executed") is False
             and identity.get("geometry_authored") is False,
             "Expected the read-only authenticated pavement source contract")
    raw_identity = _json_bytes(identity)
    _require(len(raw_identity) <= MAX_SOURCE_IDENTITY_BYTES, "Source identity exceeds its explicit bound")
    _require(isinstance(owners, (list, tuple)) and 0 < len(owners) <= MAX_OWNERS,
             "Source owner inventory is missing or unbounded")
    labels, windows, targets, excluded, total_rows = set(), set(), [], [], 0
    for owner in owners:
        _require(isinstance(owner, dict), "Source owner must be an object")
        label = _identifier(owner.get("support_label"), "support_label")
        window = _identifier(owner.get("window_id"), "window_id")
        _require(label not in labels, "Duplicate source owner label")
        labels.add(label)
        target, kind = owner.get("material_target"), owner.get("kind")
        _require(type(target) is bool, "Source material_target must be an explicit boolean")
        if not target:
            _require(kind == "parapet", "Only source-owned parapets may be excluded")
            excluded.append({"support_label": label, "window_id": window, "kind": kind})
            continue
        _require(kind in ("ordinary", "nudo", "hairpin"), "Unsupported source pavement owner kind")
        _require(window not in windows, "Duplicate pavement window ownership")
        windows.add(window)
        count, rows = owner.get("section_count"), owner.get("pavement_sections_m")
        _require(type(count) is int and 2 <= count <= MAX_SECTIONS_PER_OWNER
                 and isinstance(rows, (list, tuple)) and len(rows) == count,
                 "Pavement section count differs or exceeds its bound")
        total_rows += count
        _require(total_rows <= MAX_TOTAL_SECTIONS, "Total pavement section bound exceeded")
        targets.append(owner)
    _require(targets, "No source pavement owners")
    for key, expected in (("support_count", len(owners)), ("material_target_count", len(targets)),
                          ("excluded_parapet_count", len(excluded))):
        _require(type(identity.get(key)) is int and identity[key] == expected,
                 "Source identity owner count differs: " + key)
    return json.loads(raw_identity), raw_identity, targets, excluded, total_rows


def _source_sections(owner, outer_limit):
    rows, distances = [], []
    digest = hashlib.sha256(b"YACS_PAVEMENT_SECTIONS_M_V1\0")
    digest.update(struct.pack("<II", owner["section_count"], SECTION_POINT_COUNT))
    for source_row in owner["pavement_sections_m"]:
        _require(isinstance(source_row, (list, tuple)) and len(source_row) == SECTION_POINT_COUNT,
                 "Pavement requires exactly 25 source points per section")
        row = []
        for source_point in source_row:
            _require(isinstance(source_point, (list, tuple)) and len(source_point) == 3,
                     "Pavement source point must contain XYZ in metres")
            point = tuple(_finite(value, "Pavement coordinate") for value in source_point)
            _require(all(abs(value) <= MAX_COORDINATE_M for value in point),
                     "Pavement source coordinate exceeds its bound")
            digest.update(struct.pack("<3d", *point))
            row.append(point)
        cumulative = [0.0]
        for a, b in zip(row, row[1:]):
            length = math.dist(a, b)
            _require(MIN_SOURCE_SPAN_M < length <= MAX_SOURCE_SPAN_M,
                     "Degenerate or unbounded pavement lateral span")
            cumulative.append(cumulative[-1] + length)
        _require(cumulative[-1] > 2 * outer_limit, "The two paint bands would overlap or touch")
        rows.append(tuple(row))
        distances.append(tuple(cumulative))
    stations = {edge: [0.0] for edge in EDGES}
    for edge, column in (("edge0", 0), ("edge24", 24)):
        for a, b in zip(rows, rows[1:]):
            length = math.dist(a[column], b[column])
            _require(MIN_SOURCE_SPAN_M < length <= MAX_SOURCE_SPAN_M,
                     "Degenerate or unbounded pavement boundary span")
            stations[edge].append(stations[edge][-1] + length)
    return tuple(rows), tuple(distances), stations, digest.hexdigest()


def _clip_polygon(polygon, threshold, keep_above):
    if not polygon:
        return []
    result = []
    previous = polygon[-1]
    was_inside = previous.distance_m >= threshold if keep_above else previous.distance_m <= threshold
    for current in polygon:
        inside = current.distance_m >= threshold if keep_above else current.distance_m <= threshold
        if inside != was_inside:
            t = (threshold - previous.distance_m) / (current.distance_m - previous.distance_m)
            weights = tuple((1 - t) * a + t * b for a, b in zip(previous.weights, current.weights))
            result.append(_ClipVertex(weights, threshold))
        if inside:
            result.append(current)
        previous, was_inside = current, inside
    return result


def _resolve_vertex(vertex, keys, points, distances, stations, width, setback):
    """Use shared source edge order, so adjacent faces get identical positions."""
    support = [index for index, weight in enumerate(vertex.weights) if weight > 0]
    _require(len(support) in (1, 2), "Parallel band clipping left its source triangle edges")
    if len(support) == 1:
        index = support[0]
        weights = tuple(1.0 if other == index else 0.0 for other in range(3))
        point, station = points[index], stations[index]
    else:
        first, second = sorted(support, key=lambda index: keys[index])
        denominator = distances[second] - distances[first]
        _require(denominator != 0, "Band intersection has no source edge distance interval")
        t = (vertex.distance_m - distances[first]) / denominator
        _require(-1e-12 <= t <= 1 + 1e-12, "Band intersection left its source edge")
        t = min(1.0, max(0.0, t))
        point = tuple(a + (b - a) * t for a, b in zip(points[first], points[second]))
        station = stations[first] + (stations[second] - stations[first]) * t
        weights = tuple(1.0 - t if index == first else t if index == second else 0.0
                        for index in range(3))
    distance = vertex.distance_m
    u = (0.0 if distance == setback else 1.0 if distance == setback + width
         else (distance - setback) / width)
    _require(-1e-12 <= u <= 1 + 1e-12, "Paint UV lies outside the clipped band")
    return point, (min(1.0, max(0.0, u)), station), weights


def _clipped_triangle(keys, points, distances, stations, width, setback):
    polygon = [_ClipVertex(tuple(1.0 if i == j else 0.0 for i in range(3)), distances[j])
               for j in range(3)]
    polygon = _clip_polygon(polygon, setback, True)
    polygon = _clip_polygon(polygon, setback + width, False)
    resolved = []
    for vertex in polygon:
        value = _resolve_vertex(vertex, keys, points, distances, stations, width, setback)
        if not resolved or value[2] != resolved[-1][2]:
            resolved.append(value)
    if len(resolved) > 1 and resolved[0][2] == resolved[-1][2]:
        resolved.pop()
    return resolved


def _append_fragment(buffers, vertices, normal, source_ref, offset, budget):
    # A band can merely touch a source vertex/edge: it owns no area there.
    if len(vertices) < 3:
        return
    faces = []
    for index in range(1, len(vertices) - 1):
        cross = _cross(vertices[0][0], vertices[index][0], vertices[index + 1][0])
        orientation = sum(a * b for a, b in zip(cross, normal))
        _require(orientation >= 0, f"Clipped triangle reversed source normal at {source_ref}")
        if orientation > 0:
            faces.append((0, index, index + 1))
    if not faces:
        return
    used = sorted({index for face in faces for index in face})
    budget[0] += len(used)
    budget[1] += len(faces)
    _require(budget[0] <= MAX_OUTPUT_VERTICES and budget[1] <= MAX_OUTPUT_TRIANGLES,
             "Edge marking payload exceeds its explicit geometry bound")
    first_vertex, first_triangle = len(buffers["positions_m"]), len(buffers["triangles"])
    mapping = {old: first_vertex + new for new, old in enumerate(used)}
    for index in used:
        point, uv, weights = vertices[index]
        buffers["positions_m"].append((point[0], point[1], point[2] + offset))
        buffers["normals"].append(normal)
        buffers["uv0"].append(uv)
        buffers["barycentric_weights"].append(weights)
    buffers["triangles"].extend(tuple(mapping[index] for index in face) for face in faces)
    buffers["fragments"].append(MarkingFragment(source_ref, first_vertex, len(used), first_triangle, len(faces)))


def mesh_sha256(mesh):
    """Hash v1: tagged little-endian counts/buffers, plus UTF-8 owner identity.

    Buffer order: float64 XYZ, uint32 triangle triples, float64 normals, float64
    UV, float64 barycentrics, then seven uint32 fragment fields in dataclass
    order (the source triple first). Each buffer starts with its uint32 count.
    """
    _require(isinstance(mesh, MarkingMesh), "Expected MarkingMesh")
    digest = hashlib.sha256(b"YACS_EDGE_MARKING_MESH_V1\0")
    for value in (mesh.owner_label, mesh.window_id, mesh.edge):
        raw = value.encode("utf-8")
        digest.update(struct.pack("<I", len(raw)))
        digest.update(raw)
    for values, fmt in ((mesh.positions_m, "<3d"), (mesh.triangles, "<3I"),
                        (mesh.normals, "<3d"), (mesh.uv0, "<2d"), (mesh.barycentric_weights, "<3d")):
        digest.update(struct.pack("<I", len(values)))
        for value in values:
            digest.update(struct.pack(fmt, *value))
    digest.update(struct.pack("<I", len(mesh.fragments)))
    for fragment in mesh.fragments:
        digest.update(struct.pack("<7I", *fragment.source_triangle, fragment.first_vertex,
                                  fragment.vertex_count, fragment.first_triangle, fragment.triangle_count))
    return digest.hexdigest()


def _owner_meshes(owner, topology, width, setback, offset, budget):
    rows, from_edge0, stations, source_hash = _source_sections(owner, setback + width)
    names = ("positions_m", "triangles", "normals", "uv0", "barycentric_weights", "fragments")
    outputs = {edge: {name: [] for name in names} for edge in EDGES}
    source_sign = None
    for section in range(len(rows) - 1):
        for cell in range(SECTION_POINT_COUNT - 1):
            for slot, corners in enumerate(topology):
                keys = tuple((section + _QUAD_OFFSETS[corner][0], cell + _QUAD_OFFSETS[corner][1])
                             for corner in corners)
                points = tuple(rows[i][j] for i, j in keys)
                cross = _cross(*points)
                if abs(cross[2]) <= MIN_SOURCE_PROJECTED_AREA_M2:
                    raise ValueError(f"Degenerate source pavement triangle in XY at {(section, cell, slot)}")
                sign = 1 if cross[2] > 0 else -1
                if source_sign is None:
                    source_sign = sign
                if sign != source_sign:
                    raise ValueError(f"Source pavement folds or reverses triangle winding at {(section, cell, slot)}")
                magnitude = math.hypot(*cross)
                normal = tuple(value / magnitude for value in cross)
                for edge in EDGES:
                    distances = tuple(from_edge0[i][j] if edge == "edge0"
                                      else from_edge0[i][-1] - from_edge0[i][j] for i, j in keys)
                    if max(distances) < setback or min(distances) > setback + width:
                        continue
                    along = tuple(stations[edge][i] for i, _ in keys)
                    clipped = _clipped_triangle(keys, points, distances, along, width, setback)
                    _append_fragment(outputs[edge], clipped, normal, (section, cell, slot), offset, budget)
    meshes = tuple(MarkingMesh(owner["support_label"], owner["window_id"], edge,
                               **{name: tuple(values) for name, values in outputs[edge].items()}) for edge in EDGES)
    _require(all(mesh.triangles for mesh in meshes), "A source boundary produced no paint surface")
    summary = {"support_label": owner["support_label"], "window_id": owner["window_id"], "kind": owner["kind"],
               "section_count": len(rows), "pavement_sections_sha256": source_hash,
               "source_top_triangle_count": (len(rows) - 1) * 48,
               "ordered_source_normal_z_sign": source_sign, "edges": []}
    for mesh in meshes:
        summary["edges"].append({"edge": mesh.edge, "vertex_count": len(mesh.positions_m),
                                 "triangle_count": len(mesh.triangles), "fragment_count": len(mesh.fragments),
                                 "mesh_sha256": mesh_sha256(mesh), "boundary_length_m": stations[mesh.edge][-1]})
    return meshes, summary


def build_markings(source_plan, *, quad_triangles, appearance=MarkingAppearance()):
    """Build two continuous per-owner bands without changing any source data.

    Required ``quad_triangles`` refers to a=row[i][j], b=row[i][j+1],
    c=row[i+1][j], d=row[i+1][j+1], encoded as 0,1,2,3. Supply the pinned
    pavement producer's exact two ordered triples, not the support mesh's
    convention. Either diagonal is supported; none is an implicit default.
    ``source_plan`` is the read-only ``road_shoulder_sources.load_sources()``
    return value. Its file authentication remains the caller's responsibility.
    """
    width, setback, offset = _appearance_values(appearance)
    topology = _quad_topology(quad_triangles)
    identity, raw_identity, owners, excluded, total_rows = _source_inventory(source_plan)
    meshes, summaries, budget = [], [], [0, 0]
    for owner in owners:
        try:
            owner_meshes, summary = _owner_meshes(owner, topology, width, setback, offset, budget)
        except ValueError as error:
            raise ValueError(f"Edge marking owner {owner['support_label']} ({owner['window_id']}): {error}") from error
        meshes.extend(owner_meshes)
        summaries.append(summary)
    manifest = {
        "schema_version": 1, "status": "SOURCE_DERIVED_EDGE_MARKING_CANDIDATE",
        "source_identity": identity, "source_identity_sha256": hashlib.sha256(raw_identity).hexdigest(),
        "source_triangle_layout": {"corner_order": ["row[i][j]", "row[i][j+1]", "row[i+1][j]", "row[i+1][j+1]"],
                                   "quad_triangles": [list(triangle) for triangle in topology],
                                   "authority": "caller_supplied_pinned_pavement_producer",
                                   "native_triangle_ids_inferred": False},
        "appearance": {"width_m": width, "setback_m": setback, "surface_offset_m": offset,
                       "surface_offset_axis": "world_positive_z", "legal_standard_claimed": False},
        "uv0": {"u": "(source_cross_section_3d_distance_from_this_edge_m-setback_m)/width_m",
                "u_domain": [0, 1], "v": "source_edge_cumulative_3d_length_m_per_owner",
                "interpolation": "source_triangle_barycentric", "edge_names": list(EDGES)},
        "material_uv_contract": {"channel": 0, "u": "normalized_paint_width", "u_range": [0.0, 1.0],
                                 "v": "edge_station_metres", "line_width_cm": width * 100.0},
        "seam_policy": "retain_source_owner_boundaries_no_endpoint_join_or_nearest_distance_search",
        "required_native_consumer": {"collision_enabled": "NO_COLLISION", "cast_shadow": False,
                                     "affects_navigation": False, "source_triangle_readback": True},
        "hash_format": {"sections": "YACS_PAVEMENT_SECTIONS_M_V1_le_uint32_rows_columns_float64_xyz",
                        "mesh": "YACS_EDGE_MARKING_MESH_V1_see_mesh_sha256"},
        "counts": {"source_owner_count": len(owners) + len(excluded), "pavement_owner_count": len(owners),
                   "excluded_parapet_count": len(excluded), "source_section_count": total_rows,
                   "mesh_count": len(meshes), "vertex_count": budget[0], "triangle_count": budget[1],
                   "fragment_count": sum(len(mesh.fragments) for mesh in meshes)},
        "owners": summaries, "excluded_owners": excluded,
        "source_only": True, "derivative_render_geometry_authored": True,
        "source_geometry_mutated": False, "road_uv_mutated": False, "physics_authored": False,
        "native_surface_correspondence_verified": False, "native_consumer_verified": False,
        "owner_visual_pass": False, "performance_status": "DEFERRED_AFTER_M3", "performance_pass": False,
    }
    _require(len(_json_bytes(manifest)) <= MAX_MANIFEST_BYTES, "Marking manifest exceeds its explicit bound")
    return MarkingBuild(manifest, tuple(meshes))
