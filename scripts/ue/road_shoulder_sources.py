"""Read authenticated frozen sources for every saved road support.

This module produces comparison witnesses and material-domain IDs only. It
never imports Unreal, executes an archived consumer, traces terrain, invokes a
road/support builder, or authors geometry. Source order nominates an owner;
the native consumer must compare every oriented witness before assigning IDs.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct

from scripts.ci import official_mcp_bob_session as session
from scripts.manage_local_workspace import load_workspace
from scripts.proof.sa_calobra_tpp_survey import load_frozen_windows

RECIPE = "worldgen/terrain/benchmarks/sa_calobra/world_data/frozen_road_recipe_2026-10-04.json"
SUPPORT_MATERIAL = "/Game/Worlds/SaCalobra/CheckpointMaterials/MI_Accepted_1.MI_Accepted_1"
PARAPET_MATERIAL = "/Game/Worlds/SaCalobra/CheckpointMaterials/MI_Accepted_2.MI_Accepted_2"
NETWORK_COUNT = 184
OWNER_COUNT = 186
MAX_SECTIONS = 5000
MAX_DOCUMENT_BYTES = 64 * 1024 * 1024
PROFILE_REPORT_MAX_BYTES = 8 * 1024 * 1024
# Frozen pavement_slab: 50*N vertices and 100*N-4 triangles per window.
# For 185 windows, the accepted road's 856250/1711760 buffers require 17125 rows.
PROFILE_PAVEMENT_ROW_COUNT = 17125
PROFILE_STRAIGHT_CURVATURE_INV_M = 0.0001
PROFILE_COLUMNS = (
    "section_index", "local_station_xy_m", "edge0_xyz_m", "center12_xyz_m", "edge24_xyz_m",
    "width_xy_m", "signed_crossfall_ratio", "edge0_grade_ratio", "center_grade_ratio",
    "edge24_grade_ratio", "signed_curvature_inv_m", "bend_support_ratio",
)
PRODUCERS = {
    "network_pavement.py": {
        "sha256": "9f43ab7a3f2ca3e23e6eb6321bf42a6a84616b8faa9d84dbff9b04d2c7bbb451",
        "size_bytes": 3393,
    },
    "nudo_structure.py": {
        "sha256": "a8031e7725d57bdab3de717064dc18fca0e509142d88bf8d5cf624d336768ed9",
        "size_bytes": 6580,
    },
}


def require(value, message):
    if not value:
        raise ValueError(message)


def _finite(value):
    require(type(value) in (int, float) and math.isfinite(value),
            "Frozen support coordinate/design value is not finite")
    return float(value)


def _read_checked_json(root, relative, identity):
    """Read the exact verified bytes, including a second hash after loader use."""
    path = session._safe_path(root, relative)
    size = identity.get("size_bytes")
    require(type(size) is int and 0 < size <= MAX_DOCUMENT_BYTES,
            "Frozen source document exceeds its explicit bound")
    with path.open("rb") as handle:
        raw = handle.read(size + 1)
    require(len(raw) == size and hashlib.sha256(raw).hexdigest() == identity.get("sha256"),
            "Frozen source document bytes changed: " + relative)
    return json.loads(raw.decode("utf-8-sig"))


def _sections(rows):
    require(isinstance(rows, list) and 3 <= len(rows) <= MAX_SECTIONS,
            "Frozen support section count is missing or unbounded")
    result = []
    for row in rows:
        require(isinstance(row, (list, tuple)) and len(row) == 25,
                "Frozen support requires exactly 25 pavement samples")
        require(all(isinstance(p, (list, tuple)) and len(p) == 3 for p in row),
                "Frozen pavement sample shape differs")
        result.append([tuple(_finite(v) for v in p) for p in row])
    return result


def _area(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _support_top_witnesses(pavement, *, hairpin=False):
    """Evaluate the frozen top-domain equations solely for native comparison.

    Ordinary/Nudo outer edges use the pinned network_pavement boundary miter.
    Hairpin sources already include the checkpoint's +4 cm pavement lift;
    subtracting the 8 cm slab recovers the original -4 cm support top. Only
    that profile uses the accepted sixteen-pass concave-shoulder taper.
    """
    pavement = _sections(pavement)
    result = [[None, *[(x, y, z - 0.08) for x, y, z in row], None]
              for row in pavement]
    for side, outer, sign in ((0, 0, -1), (-1, 26, 1)):
        boundary = [row[side] for row in pavement]
        for i, point in enumerate(boundary):
            normals = []
            for a, b in ((boundary[max(0, i - 1)], point),
                         (point, boundary[min(len(boundary) - 1, i + 1)])):
                dx, dy = b[0] - a[0], b[1] - a[1]
                length = math.hypot(dx, dy)
                if length > 1e-9:
                    normals.append((-dy / length * sign, dx / length * sign))
            require(normals, "Frozen shoulder boundary has no direction")
            nx, ny = map(sum, zip(*normals))
            length = math.hypot(nx, ny)
            require(length > 1e-9, "Frozen shoulder boundary reverses")
            nx, ny = nx / length, ny / length
            denominator = nx * normals[0][0] + ny * normals[0][1]
            require(denominator > 0.1, "Frozen shoulder miter is unbounded")
            x, y = point[0] + nx * 0.5 / denominator, point[1] + ny * 0.5 / denominator
            left, right = pavement[i][0], pavement[i][-1]
            dx, dy = right[0] - left[0], right[1] - left[1]
            require(dx * dx + dy * dy > 0, "Frozen pavement width is zero")
            ratio = ((x - left[0]) * dx + (y - left[1]) * dy) / (dx * dx + dy * dy)
            result[i][outer] = (x, y, left[2] + ratio * (right[2] - left[2]) - 0.08)
    if hairpin:
        for _ in range(16):
            narrow = set()
            for i in range(len(result) - 1):
                for j, outer, inner in ((0, 0, 1), (25, 26, 25)):
                    a, b, c, d = result[i][j], result[i][j + 1], result[i + 1][j], result[i + 1][j + 1]
                    if any(_area(*triangle) >= -1e-9 for triangle in ((a, b, c), (b, d, c))):
                        narrow.update(((i, outer, inner), (i + 1, outer, inner)))
            if not narrow:
                break
            for i, outer, inner in sorted(narrow):
                result[i][outer] = tuple((a + b) * 0.5
                                        for a, b in zip(result[i][outer], result[i][inner]))
        else:
            raise ValueError("Frozen hairpin shoulder cannot be tapered without folding")
    for i in range(len(result) - 1):
        for j in range(26):
            a, b, c, d = result[i][j], result[i][j + 1], result[i + 1][j], result[i + 1][j + 1]
            require(_area(a, b, c) < -1e-9 and _area(b, d, c) < -1e-9,
                    "Frozen support top witness folds or reverses winding")
    return tuple(tuple(tuple(_finite(v) for v in p) for p in row) for row in result)


def _parapet_rows(sections, station_start, design):
    """Read the frozen bridge domain; this is not a general guardrail rule."""
    require(isinstance(design, dict) and "upper_domain_station_m" in design,
            "Nudo structure domain is missing")
    station, upper = _finite(station_start), _finite(design["upper_domain_station_m"])
    selected = []
    for i, row in enumerate(sections):
        if i:
            station += math.dist(row[13][:2], sections[i - 1][13][:2])
        if station <= upper:
            selected.append(row)
    return selected if len(selected) >= 3 else []


def _parapet_witnesses(selected):
    """Expected oriented faces of the two already existing 0.30 x 0.65 m walls.

    No vertices are delivered to Unreal. These tuples authenticate the sole
    excluded owner, so a label or a brown material cannot stand in for source
    ownership. The frozen slab face order includes top, bottom and side faces.
    """
    vertices, faces = [], []
    for outer, inner in ((0, 1), (-1, -2)):
        rows = []
        for section in selected:
            a, b = section[outer], section[inner]
            length = math.dist(a[:2], b[:2])
            require(length > 0, "Frozen parapet has no source boundary width")
            row = [(a[0] + (b[0] - a[0]) * j / 24 * 0.3 / length,
                    a[1] + (b[1] - a[1]) * j / 24 * 0.3 / length,
                    a[2] + 0.65) for j in range(25)]
            rows.append(row if outer == 0 else list(reversed(row)))
        top = [p for row in rows for p in row]
        count, offset = len(top), len(vertices)
        vertices.extend(top)
        vertices.extend((x, y, z - 0.08 - 0.57) for x, y, z in top)
        triangles = []
        for i in range(len(rows) - 1):
            for j in range(24):
                a = i * 25 + j
                b, c, d = a + 1, a + 25, a + 26
                triangles.extend(((a, b, c), (b, d, c),
                                  (c + count, b + count, a + count),
                                  (c + count, d + count, b + count)))
        last = (len(rows) - 1) * 25
        edges = [(j, j + 1) for j in range(24)]
        edges += [(last + j + 1, last + j) for j in range(24)]
        edges += [((i + 1) * 25, i * 25) for i in range(len(rows) - 1)]
        edges += [(i * 25 + 24, (i + 1) * 25 + 24) for i in range(len(rows) - 1)]
        for a, b in edges:
            triangles.extend(((b, a, a + count), (b, a + count, b + count)))
        faces.extend(tuple(v + offset for v in face) for face in triangles)
    return tuple(tuple(v * 100 for v in p) for p in vertices), tuple(faces)


def profile_diagnostic(window):
    """Summarize the existing frozen pavement; do not assert real-road banking.

    The sign uses source point 24 minus point 0, and forward means increasing
    section order. Distances below are local XY distances, not route chainage.
    The hairpin's uniform checkpoint lift changes neither crossfall nor grade.
    """
    sections = _sections(window["sections"])
    widths = [math.dist(row[0][:2], row[24][:2]) for row in sections]
    require(all(value > 1e-9 for value in widths), "Frozen profile has zero pavement width")
    edge_deltas = [row[24][2] - row[0][2] for row in sections]
    crossfalls = [dz / width for dz, width in zip(edge_deltas, widths, strict=True)]
    centres = [row[12] for row in sections]
    spans = [math.dist(a[:2], b[:2]) for a, b in zip(centres, centres[1:])]
    require(all(value > 1e-9 for value in spans), "Frozen profile has a zero XY station span")
    grades = [(b[2] - a[2]) / span
              for a, b, span in zip(centres, centres[1:], spans)]

    def stats(values):
        return {"min": min(values), "max": max(values),
                "first": values[0], "last": values[-1]}

    result = {
        "provenance": "authenticated_frozen_checkpoint_pavement_only",
        "real_road_match_validated": False,
        "geometry_authored": False,
        "crossfall_sign": "source_point_24_height_minus_source_point_0_height",
        "grade_sign": "increasing_source_section_order",
        "station_basis": "cumulative_xy_distance_of_source_point_12_within_window",
        "section_count": len(sections), "local_xy_length_m": math.fsum(spans),
        "edge_width_xy_m": stats(widths), "edge_height_difference_m": stats(edge_deltas),
        "signed_crossfall_ratio": stats(crossfalls), "signed_grade_ratio": stats(grades),
        "centre_height_m": stats([p[2] for p in centres]),
    }
    for name in ("station_start_m", "station_end_m"):
        if name in window:
            result["source_" + name] = _finite(window[name])
    return result


def _owner(window, index, sections, kind, *, parapet_rows=None):
    target = kind != "parapet"
    count = len(sections)
    selected = tuple(i * 52 + j * 2 + side
                     for i in range(count - 1) for j in (0, 25) for side in (0, 1)) if target else ()
    owner = {
        "support_label": f"YACS_PERSIST_SUPPORT_{index:03d}",
        "window_id": window["id"], "kind": kind, "material_target": target,
        "section_count": count,
        "sections_cm": tuple(tuple(tuple(v * 100 for v in p) for p in row) for row in sections),
        "top_triangle_count": (count - 1) * 52 if target else 0,
        "selected_triangle_ids": selected,
        "original_material_path": SUPPORT_MATERIAL if target else PARAPET_MATERIAL,
        "profile_diagnostic": profile_diagnostic(window),
    }
    if target:
        # Retain original source pavement coordinates. Reporting never reverses
        # the 8 cm support lowering or treats either outer shoulder as asphalt.
        owner["pavement_sections_m"] = tuple(tuple(row) for row in _sections(window["sections"]))
    else:
        vertices, faces = _parapet_witnesses(parapet_rows)
        owner["parapet_vertices_cm"], owner["parapet_faces"] = vertices, faces
        owner["expected_triangle_count"] = len(faces)
        owner["parapet_section_count"] = len(parapet_rows)
    return owner


def _plan_owners(source, design):
    windows = source.get("windows")
    require(isinstance(windows, list) and len(windows) == NETWORK_COUNT + 1,
            "Frozen source must account for 184 network windows and one hairpin")
    require(all(isinstance(row, dict) for row in windows), "Frozen window object is missing")
    ids = [row.get("id") for row in windows]
    require(all(isinstance(x, str) and x for x in ids) and len(set(ids)) == len(ids)
            and ids[-1] == "accepted-hairpin" and "accepted-hairpin" not in ids[:-1],
            "Frozen support source IDs are missing, duplicated or reordered")
    owners = []
    for window in windows:
        flag = window.get("nudo_structure", False)
        require(type(flag) is bool, "Nudo ownership flag must be an explicit boolean")
        kind = "hairpin" if window["id"] == "accepted-hairpin" else "nudo" if flag else "ordinary"
        require(not (kind == "hairpin" and flag), "Hairpin cannot impersonate a Nudo structure")
        sections = _support_top_witnesses(window["sections"], hairpin=kind == "hairpin")
        if flag:
            parapet_rows = _parapet_rows(sections, window.get("station_start_m"), design)
            if parapet_rows:
                owners.append(_owner(window, len(owners), sections, "parapet", parapet_rows=parapet_rows))
        owners.append(_owner(window, len(owners), sections, kind))
    require(len(owners) == OWNER_COUNT and sum(not row["material_target"] for row in owners) == 1,
            "Frozen producer order does not account for exactly 186 supports and one parapet")
    require(len({row["support_label"] for row in owners}) == OWNER_COUNT,
            "Frozen support owner is duplicated")
    return owners


def iter_expected_triangles(owner):
    """Yield every source-oriented comparison triangle, never count-only probes."""
    if owner["kind"] == "parapet":
        points = owner["parapet_vertices_cm"]
        for tid, face in enumerate(owner["parapet_faces"]):
            yield tid, tuple(points[v] for v in face)
        return
    sections = owner["sections_cm"]
    for i in range(len(sections) - 1):
        for j in range(26):
            a, b, c, d = sections[i][j], sections[i][j + 1], sections[i + 1][j], sections[i + 1][j + 1]
            yield i * 52 + j * 2, (a, b, c)
            yield i * 52 + j * 2 + 1, (b, d, c)


def owner_identity(owner):
    """Compact immutable source witness for the saved/reload/GPU manifest."""
    digest, count = hashlib.sha256(), 0
    for tid, triangle in iter_expected_triangles(owner):
        digest.update(struct.pack("<i9d", tid, *(v for point in triangle for v in point)))
        count += 1
    fields = ("support_label", "window_id", "kind", "material_target", "section_count",
              "top_triangle_count", "original_material_path", "profile_diagnostic")
    result = {key: owner[key] for key in fields}
    result.update(expected_witness_triangle_count=count,
                  expected_oriented_triangles_sha256=digest.hexdigest(),
                  selected_triangle_count=len(owner["selected_triangle_ids"]),
                  selected_triangle_ids=list(owner["selected_triangle_ids"]))
    if owner["kind"] == "parapet":
        result.update(expected_triangle_count=owner["expected_triangle_count"],
                      parapet_section_count=owner["parapet_section_count"],
                      exclusion="existing_nudo_parapet_preserved_without_material_assignment")
    return result


def _profile_rows(owner):
    """Read local pavement profiles; no smoothing, fitting or height correction."""
    raw = owner.get("pavement_sections_m")
    require(isinstance(raw, (list, tuple)), "Frozen source pavement coordinates are missing")
    pavement = _sections(list(raw))
    require(len(pavement) == owner["section_count"] == len(owner["sections_cm"]),
            "Frozen profile/source section counts differ")
    # Match every original pavement point to the already authenticated support
    # interior. This checks the retained data without reconstructing output Z.
    for original, support in zip(pavement, owner["sections_cm"], strict=True):
        require(len(support) == 27 and all(
            tuple(actual) == (p[0] * 100, p[1] * 100, (p[2] - 0.08) * 100)
            for p, actual in zip(original, support[1:26], strict=True)),
            "Frozen pavement disagrees with the source-owned support interior")
    tracks = [[row[column] for row in pavement] for column in (0, 12, 24)]
    spans = [[math.dist(a[:2], b[:2]) for a, b in zip(track, track[1:])]
             for track in tracks]
    require(all(distance > 1e-9 for distance in spans[1]), "Frozen profile centre has a zero XY span")
    stations = [0.0]
    for distance in spans[1]:
        stations.append(stations[-1] + distance)

    def grade(track, distances, index):
        first, last = max(0, index - 1), min(len(track) - 1, index + 1)
        steps = distances[first:last]
        if any(distance <= 1e-9 for distance in steps):
            return None
        return (track[last][2] - track[first][2]) / math.fsum(steps)

    result = []
    for index, section in enumerate(pavement):
        left, centre, right = section[0], section[12], section[24]
        width = math.dist(left[:2], right[:2])
        require(width > 1e-9, "Frozen profile has zero pavement width")
        q = (right[2] - left[2]) / width
        curvature = bend_support = None
        if 0 < index < len(pavement) - 1:
            previous, following = tracks[1][index - 1], tracks[1][index + 1]
            before = (centre[0] - previous[0], centre[1] - previous[1])
            after = (following[0] - centre[0], following[1] - centre[1])
            tangent = (following[0] - previous[0], following[1] - previous[1])
            chord = math.hypot(*tangent)
            if chord > 1e-9:
                curvature = 2 * (before[0] * after[1] - before[1] * after[0]) / (
                    spans[1][index - 1] * spans[1][index] * chord)
                across = (right[0] - left[0], right[1] - left[1])
                orientation = (tangent[0] * across[1] - tangent[1] * across[0]) / (chord * width)
                if abs(curvature) > PROFILE_STRAIGHT_CURVATURE_INV_M and abs(orientation) > 1e-6:
                    bend_support = -math.copysign(1.0, curvature * orientation) * q
        values = [index, stations[index], left, centre, right, width, q,
                  *(grade(track, distances, index) for track, distances in zip(tracks, spans, strict=True)),
                  curvature, bend_support]
        require(all(value is None or math.isfinite(value) for value in values[5:]),
                "Frozen profile derivative is nonfinite")
        result.append(values)
    return result


def network_profile_report(source_plan):
    """Complete source-only local profiles for the 185 frozen pavement windows.

    The caller supplies load_sources() output and writes compact JSON to its
    separate hashed diagnostic file. This does not query native geometry,
    establish real-road measurement or grant geometry/physics admission.
    """
    owners = source_plan.get("owners")
    require(isinstance(source_plan.get("source_identity"), dict)
            and isinstance(owners, list) and len(owners) == OWNER_COUNT
            and [row["support_label"] for row in owners]
            == [f"YACS_PERSIST_SUPPORT_{i:03d}" for i in range(OWNER_COUNT)]
            and all(type(row["material_target"]) is bool for row in owners)
            and sum(row["material_target"] for row in owners) == NETWORK_COUNT + 1
            and sum(row["kind"] == "parapet" and not row["material_target"] for row in owners) == 1,
            "Frozen profile owner coverage is incomplete or reordered")
    targets = [row for row in owners if row["material_target"]]
    require(sum(row["section_count"] for row in targets) == PROFILE_PAVEMENT_ROW_COUNT,
            "Frozen profile row inventory differs from the exact accepted road buffers")
    records = []
    for owner in targets:
        identity = json.dumps(owner_identity(owner), sort_keys=True, separators=(",", ":"), allow_nan=False)
        records.append({
            "support_label": owner["support_label"], "window_id": owner["window_id"], "kind": owner["kind"],
            "section_count": owner["section_count"],
            "source_owner_identity_sha256": hashlib.sha256(identity.encode()).hexdigest(),
            "rows": _profile_rows(owner),
        })
    result = {
        "schema_version": 1, "status": "FROZEN_NETWORK_PROFILE_DIAGNOSTIC",
        "source_identity": source_plan["source_identity"], "source_only": True,
        "real_road_match_validated": False, "native_geometry_observed": False,
        "geometry_authored": False, "authoritative_physics": False,
        "material_target_count": len(records), "excluded_parapet_count": 1,
        "section_count": sum(row["section_count"] for row in records),
        "columns": list(PROFILE_COLUMNS), "owners": records,
        "basis": {
            "coordinates": "original frozen pavement top XYZ in checkpoint-local UE metres; source indices 0,12,24",
            "support_crosscheck": "all 25 source pavement points match support interior 1..25 after source lowering by 0.08 m; output uses original pavement XYZ",
            "station": "cumulative XY distance of source point12 within each owner; not route chainage or original source station keys",
            "crossfall": "(edge24.z-edge0.z)/XY_width; positive rises toward physical source edge24",
            "grade": "signed two-sided secant over each track's adjacent XY segment lengths; one-sided at endpoints; null for zero XY support",
            "curvature": "signed circumcircle curvature from three adjacent point12 XY samples; positive XY cross product; endpoints/collapsed chord null",
            "bend_support": "-q*sign(curvature*cross(chord,edge24-edge0)); positive means bend-inner edge is lower; source transverse slope only",
            "bend_support_null": "curvature unavailable or abs(curvature)<=straight threshold or abs(normalized transverse orientation)<=1e-6",
            "straight_curvature_threshold_inv_m": PROFILE_STRAIGHT_CURVATURE_INV_M,
            "row_inventory": "185 frozen slabs: 50*N vertices and 100*N-4 triangles; accepted road 856250/1711760 requires total N=17125",
            "classification": "frozen visual/design candidate; no LiDAR road-deck measurement or real-road/engineering admission",
        },
    }
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    require(len(encoded) <= PROFILE_REPORT_MAX_BYTES,
            "Frozen network profile diagnostic exceeds the compact serialization budget")
    return result


def load_sources():
    """Authenticate the existing host's frozen data once per consumer phase.

    The 375 input identities come only from the tracked recipe. Archived
    consumer files are hashed as inert source evidence; no code is executed.
    The native consumer must authenticate all 186 owners, including the one
    excluded parapet, before any material mutation or saved output.
    """
    config = load_workspace()
    relative = str(Path(session.PROFILE_RELATIVE).parent).replace("\\", "/")
    frozen_root = session._safe_path(Path(config["data"]), relative)
    recipe_path = session._safe_path(session.ROOT, RECIPE)
    recipe_identity = session._identity(recipe_path, 256 * 1024)
    recipe = _read_checked_json(session.ROOT, RECIPE, recipe_identity)
    for row in recipe["inputs"]:
        session._safe_path(frozen_root, row["path"])
    source = load_frozen_windows(frozen_root, recipe_path=recipe_path)
    identities = {row["path"]: row for row in recipe["inputs"]}
    network = _read_checked_json(frozen_root, "Network/network.json", identities["Network/network.json"])
    native = _read_checked_json(frozen_root, "network-native-proof.json", identities["network-native-proof.json"])
    profile = _read_checked_json(frozen_root, "ma2141-profile-candidate.json", identities["ma2141-profile-candidate.json"])
    # Use values decoded from the exact pinned byte snapshots. Also require
    # agreement with the existing loader's complete recipe/inventory checks;
    # an altered loader snapshot cannot acquire authority from later hashes.
    native_ids = {row["id"] for row in native["windows"]}
    checked_windows = [row for row in network["approved"] + network["owner_reviewed"] + network["nudo"]["windows"]
                       if row["id"] in native_ids]
    checked_windows.append({"id": "accepted-hairpin", "sections": [
        [[xy[0], xy[1], _finite(z) + 0.04]
         for xy, z in zip(row["xy_local_m"], row["candidate_ground_m"], strict=True)]
        for row in profile["stations"]]})
    require(source["windows"] == checked_windows,
            "Frozen source loader values differ from authenticated byte snapshots")
    producer_files = {}
    for name, expected in PRODUCERS.items():
        relative = "support-consumers/" + name
        actual = session._identity(session._safe_path(frozen_root, relative), 32 * 1024)
        require(actual == expected, "Frozen support producer bytes changed: " + name)
        producer_files[relative] = actual
    require(session._identity(recipe_path, 256 * 1024) == recipe_identity
            and source["source_identity"]["recipe_sha256"] == recipe_identity["sha256"],
            "Tracked frozen source recipe changed during authentication")
    owners = _plan_owners({"windows": checked_windows}, network["nudo"]["structure"])
    identity = {**source["source_identity"], "support_source_schema_version": 1,
                "support_count": len(owners),
                "material_target_count": sum(row["material_target"] for row in owners),
                "excluded_parapet_count": sum(not row["material_target"] for row in owners),
                "producer_files": producer_files,
                "source_documents": {name: {key: identities[name][key] for key in ("sha256", "size_bytes")}
                                     for name in ("Network/network.json", "network-native-proof.json", "ma2141-profile-candidate.json")},
                "geometry_consumers_executed": False, "geometry_authored": False}
    return {"source_identity": identity, "owners": owners}
