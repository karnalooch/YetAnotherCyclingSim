"""Revision 5 diagnostic source-repair cuts of two pinned scan LOD0s."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from io_scene_fbx import export_fbx_bin
from mathutils import Matrix, Vector
from mathutils.geometry import tessellate_polygon


PINS = {
    "namaqualand_boulder_02": "ee43e9e5b274337c62b83b921ed472f5456f3441c393ec144c658fdd47cc430a",
    "namaqualand_boulder_06": "697f69814e3c2f33873dd4aa424505ee82ec6e4c940a6c1540afb0a4ef3897c7",
}
RECIPE_REVISION = 5
CUT_FRACTIONS = {"namaqualand_boulder_02": 0.12, "namaqualand_boulder_06": 0.10}
CUT_REASONS = {
    "namaqualand_boulder_02": "Source-only open-underside repair: retained revision1 10% cut lay below original boundary maxZ 0.04504789785m; fixed 12% cut expected at 0.0464433m clears that boundary. Chosen before native measurement, not contact-policy tuning.",
    "namaqualand_boulder_06": "Retain original fixed 10% source-relative planar underside recipe for closed source.",
}
API_SOURCE = "https://raw.githubusercontent.com/blender/blender/v4.5.9/source/blender/bmesh/intern/bmesh_opdefines.cc"


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(face):
    points = [tuple(v.co) for v in face.verts]
    return min(tuple(points[i:] + points[:i]) for i in range(len(points)))


def topology(bm, allow_open=False):
    require(bm.verts and bm.faces, "Empty mesh")
    pending, visited = [next(iter(bm.verts))], set()
    while pending:
        vertex = pending.pop()
        if vertex in visited:
            continue
        visited.add(vertex)
        pending.extend(edge.other_vert(vertex) for edge in vertex.link_edges)
    bm.verts.index_update()
    directed = Counter()
    for face in bm.faces:
        require(
            len(face.verts) == 3 and face.calc_area() > 0,
            "Source/derived must have nondegenerate triangles",
        )
        indices = [v.index for v in face.verts]
        directed.update((indices[i], indices[(i + 1) % 3]) for i in range(3))
    report = {
        "vertices": len(bm.verts),
        "edges": len(bm.edges),
        "triangles": len(bm.faces),
        "boundary_edges": sum(e.is_boundary for e in bm.edges),
        "nonmanifold_edges": sum(not e.is_manifold for e in bm.edges),
        "wire_edges": sum(e.is_wire for e in bm.edges),
        "connected": len(visited) == len(bm.verts),
        "consistent_winding": all(
            count == 1 and directed[(b, a)] in ({0, 1} if allow_open else {1})
            for (a, b), count in directed.items()
        ),
        "volume_m3": None if allow_open else bm.calc_volume(signed=True),
        "volume_status": "UNVERIFIED_OPEN_SOURCE"
        if allow_open
        else "CLOSED_SIGNED_VOLUME",
    }
    require(
        report["connected"]
        and report["consistent_winding"]
        and report["wire_edges"] == 0
        and (
            report["nonmanifold_edges"] == report["boundary_edges"]
            if allow_open
            else report["nonmanifold_edges"] == report["boundary_edges"] == 0
        )
        and (allow_open or report["volume_m3"] > 0),
        "Mesh must be connected outward closed manifold",
    )
    return report


def dimensions(bm):
    points = [tuple(v.co) for v in bm.verts]
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    require(all(math.isfinite(v) for p in points for v in p), "Nonfinite geometry")
    return {"min": low, "max": high, "dimensions": [high[i] - low[i] for i in range(3)]}


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def intersect(a, b, c, d):
    if (
        max(a[0], b[0]) < min(c[0], d[0])
        or max(c[0], d[0]) < min(a[0], b[0])
        or max(a[1], b[1]) < min(c[1], d[1])
        or max(c[1], d[1]) < min(a[1], b[1])
    ):
        return False
    return cross(a, b, c) * cross(a, b, d) <= 0 and cross(c, d, a) * cross(c, d, b) <= 0


def boundary_loop(edges):
    require(edges, "No cut boundary")
    neighbors = {}
    for edge in edges:
        a, b = edge.verts
        neighbors.setdefault(a, []).append(b)
        neighbors.setdefault(b, []).append(a)
    require(
        all(len(v) == 2 for v in neighbors.values()), "Ambiguous cut boundary degree"
    )
    start = min(neighbors, key=lambda v: tuple(v.co))
    loop, previous, current = [], None, start
    while current not in loop:
        loop.append(current)
        choices = [v for v in neighbors[current] if v != previous]
        following = min(choices, key=lambda v: tuple(v.co))
        previous, current = current, following
    require(
        current == start and len(loop) == len(neighbors),
        "Multiple or ambiguous cut loops",
    )
    xy = [tuple(v.co)[:2] for v in loop]
    require(len(set(xy)) == len(xy), "Repeated cut polygon position")
    for i in range(len(xy)):
        for j in range(i + 1, len(xy)):
            if j == i + 1 or (i == 0 and j == len(xy) - 1):
                continue
            require(
                not intersect(
                    xy[i], xy[(i + 1) % len(xy)], xy[j], xy[(j + 1) % len(xy)]
                ),
                "Self-intersecting cut polygon",
            )
    return loop


def center_of_mass(bm):
    volume, moment = 0.0, Vector()
    for face in bm.faces:
        a, b, c = [v.co for v in face.verts]
        signed = a.dot(b.cross(c)) / 6
        volume += signed
        moment += (a + b + c) * (signed / 4)
    require(volume > 0, "Invalid volume for COM")
    return list(moment / volume)


def inside_xy(point, polygon):
    inside = False
    x, y = point
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            if x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
                inside = not inside
    return inside


def polygon_area(polygon):
    return (
        sum(
            a[0] * b[1] - a[1] * b[0]
            for a, b in zip(polygon, polygon[1:] + polygon[:1])
        )
        / 2
    )


def ordered_boundary_loops(edges):
    remaining = set(edges)
    loops = []
    while remaining:
        seed = min(remaining, key=lambda e: sorted(tuple(v.co) for v in e.verts))
        selected = {seed}
        vertices = set(seed.verts)
        pending = list(seed.verts)
        while pending:
            v = pending.pop()
            for edge in v.link_edges:
                if edge in remaining and edge not in selected:
                    selected.add(edge)
                    for other in edge.verts:
                        if other not in vertices:
                            vertices.add(other)
                            pending.append(other)
        remaining -= selected
        loops.append(boundary_loop(list(selected)))
    loops.sort(
        key=lambda loop: (
            -abs(polygon_area([tuple(v.co)[:2] for v in loop])),
            tuple(tuple(v.co) for v in loop),
        )
    )
    polygons = [[tuple(v.co)[:2] for v in loop] for loop in loops]
    for i, a in enumerate(polygons):
        for b in polygons[i + 1 :]:
            for p, q in zip(a, a[1:] + a[:1]):
                for r, t in zip(b, b[1:] + b[:1]):
                    require(not intersect(p, q, r, t), "Cut loops intersect or touch")
    records = []
    for i, polygon in enumerate(polygons):
        area = abs(polygon_area(polygon))
        require(area > 0, "Zero-area cut loop")
        depth = sum(
            inside_xy(polygon[0], other) for j, other in enumerate(polygons) if i != j
        )
        records.append(
            {
                "xy_m": [list(p) for p in polygon],
                "area_m2": area,
                "nesting_depth": depth,
                "role": "OUTER_OR_ISLAND" if depth % 2 == 0 else "HOLE",
            }
        )
    return loops, records


def validate_holed_cap(faces, records):
    expected = sum(
        r["area_m2"] * (-1 if r["nesting_depth"] % 2 else 1) for r in records
    )
    require(expected > 0, "Invalid parity cap area")
    actual = sum(f.calc_area() for f in faces)
    # Floating-point integration guard only; never a terrain/contact tolerance.
    tolerance = max(1e-8, expected * 1e-6)
    require(
        abs(actual - expected) <= tolerance, "Cap area differs from loop parity area"
    )
    for face in faces:
        center = face.calc_center_median()
        require(
            sum(inside_xy((center.x, center.y), r["xy_m"]) for r in records) % 2 == 1,
            "Cap triangle centroid outside odd-even support region",
        )
        require(len(face.verts) == 3 and face.calc_area() > 0, "Invalid cap triangle")
    triangles = [[tuple(v.co)[:2] for v in face.verts] for face in faces]
    boxes = [
        (
            min(p[0] for p in t),
            max(p[0] for p in t),
            min(p[1] for p in t),
            max(p[1] for p in t),
        )
        for t in triangles
    ]

    def strictly_inside(point, triangle):
        signs = [
            cross(a, b, point) for a, b in zip(triangle, triangle[1:] + triangle[:1])
        ]
        return all(v > 0 for v in signs) or all(v < 0 for v in signs)

    for i, a in enumerate(triangles):
        for j in range(i + 1, len(triangles)):
            aa, bb = boxes[i], boxes[j]
            if aa[1] <= bb[0] or bb[1] <= aa[0] or aa[3] <= bb[2] or bb[3] <= aa[2]:
                continue
            b = triangles[j]
            require(
                not any(strictly_inside(p, b) for p in a)
                and not any(strictly_inside(p, a) for p in b),
                "Overlapping cap triangles",
            )
            for p, q in zip(a, a[1:] + a[:1]):
                for r, t in zip(b, b[1:] + b[:1]):
                    require(
                        not (
                            cross(p, q, r) * cross(p, q, t) < 0
                            and cross(r, t, p) * cross(r, t, q) < 0
                        ),
                        "Crossing cap triangle edges",
                    )
    return {
        "nonoverlapping_triangle_interiors": True,
        "expected_parity_area_m2": expected,
        "actual_triangle_area_m2": actual,
        "numeric_area_tolerance_m2": tolerance,
        "centroids_inside_odd_even": True,
        "method": "Blender4.5.9 stock triangle_fill HOLES|POLYS; full closed manifold/winding verification remains mandatory",
    }


def face_components(bm):
    remaining = set(bm.faces)
    components = []
    while remaining:
        pending = [remaining.pop()]
        faces = set(pending)
        while pending:
            face = pending.pop()
            for edge in face.edges:
                for neighbor in edge.link_faces:
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        faces.add(neighbor)
                        pending.append(neighbor)
        vertices = {v for f in faces for v in f.verts}
        points = [tuple(v.co) for v in vertices]
        low = [min(p[i] for p in points) for i in range(3)]
        high = [max(p[i] for p in points) for i in range(3)]
        report = {
            "surface_area_m2": sum(sorted(f.calc_area() for f in faces)),
            "facecount": len(faces),
            "bounds_m": {"min": low, "max": high},
        }
        components.append((faces, report))
    components.sort(
        key=lambda pair: (
            -pair[1]["surface_area_m2"],
            pair[1]["bounds_m"]["min"],
            pair[1]["bounds_m"]["max"],
            sorted(key(f) for f in pair[0]),
        )
    )
    return components


def prepare(asset, output):
    source = Path(asset["source"]).resolve(strict=True)
    allowed = Path("D:/yacs/data/assets/pcg365-large-rocks01").resolve(strict=True)
    require(
        source.is_relative_to(allowed) and source.suffix.lower() == ".fbx",
        "Source outside corrected LOD0 stage",
    )
    before = sha(source)
    require(
        before == PINS[asset["id"]] == asset["sha256"]
        and source.stat().st_size == asset["bytes"],
        "Pinned source mismatch",
    )
    existing = set(bpy.data.objects)
    require(
        bpy.ops.import_scene.fbx(
            filepath=str(source),
            global_scale=1.0,
            use_manual_orientation=False,
            bake_space_transform=False,
            use_anim=False,
            use_image_search=False,
            use_custom_normals=True,
        )
        == {"FINISHED"},
        "LOD0 import failed",
    )
    imported = set(bpy.data.objects) - existing
    meshes = [o for o in imported if o.type == "MESH"]
    require(
        len(meshes) == 1 and meshes[0].name == asset["selected_source_object"],
        "Exactly selected source LOD0 required",
    )
    original = meshes[0]
    require(
        not original.modifiers
        and original.animation_data is None
        and original.data.shape_keys is None,
        "Deformed source unsupported",
    )
    original.data.calc_loop_triangles()
    geometry = {
        "world_vertices": [
            list(original.matrix_world @ v.co) for v in original.data.vertices
        ],
        "triangles": [list(t.vertices) for t in original.data.loop_triangles],
    }
    require(
        hashlib.sha256(
            json.dumps(geometry, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        == asset["expected_geometry_sha256"],
        "Geometry differs from inspected object",
    )
    bm = bmesh.new()
    try:
        bm.from_mesh(original.data)
        for vertex in bm.verts:
            vertex.co = original.matrix_world @ vertex.co
        bm.normal_update()
        allow_open = asset["id"] == "namaqualand_boulder_02"
        original_topology, original_bounds = topology(bm, allow_open), dimensions(bm)
        require(
            original_topology["triangles"] == asset["expected_lod0_triangles"],
            "LOD0 triangle identity differs",
        )
        requested_cut = (
            original_bounds["min"][2]
            + CUT_FRACTIONS[asset["id"]] * original_bounds["dimensions"][2]
        )
        cut = Vector(
            (0, 0, requested_cut)
        ).z  # Match BMesh's native float32 plane coordinates.
        original_boundary = [e for e in bm.edges if e.is_boundary]
        original_boundary_max_z = None
        if allow_open:
            require(original_boundary, "02 expected original open underside")
            # Single degree-2 cycle; boundary_loop also rejects XY self intersection.
            source_boundary = boundary_loop(original_boundary)
            original_boundary_max_z = max(v.co.z for v in source_boundary)
            require(
                all(v.co.z < cut for v in source_boundary),
                "Frozen per-asset cut does not lie above every original boundary vertex",
            )
        preserved = Counter(
            key(f) for f in bm.faces if all(v.co.z > cut for v in f.verts)
        )
        original_area = sum(f.calc_area() for f in bm.faces)
        # 4.5.9 bmesh_opdefines.cc:1627-1658; negative half is discarded.
        bmesh.ops.bisect_plane(
            bm,
            geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
            dist=0.0,
            plane_co=Vector((0, 0, cut)),
            plane_no=Vector((0, 0, 1)),
            use_snap_center=False,
            clear_outer=False,
            clear_inner=True,
        )
        components = face_components(bm)
        component_report = {
            "schema_version": 1,
            "id": asset["id"],
            "recipe_revision": RECIPE_REVISION,
            "cut_world_z_m": cut,
            "components": [r for _, r in components],
            "selection_enabled": bool(asset["split_source02"]),
            "selection_reason": "Largest post-cut surface area; bounds then canonical face-coordinate tie break; fixed before terrain measurements. Discard only derived-copy islands.",
        }
        with (output / (asset["id"] + "_cut-components.json")).open(
            "x", encoding="utf-8"
        ) as stream:
            stream.write(json.dumps(component_report, indent=2, allow_nan=False) + "\n")
        excluded_upper_count = 0
        if asset["id"] == "namaqualand_boulder_02" and asset["split_source02"]:
            require(components, "No surviving cut face components")
            selected_faces = components[0][0]
            selected_upper = Counter(
                key(f) for f in selected_faces if all(v.co.z > cut for v in f.verts)
            )
            require(
                not (selected_upper - preserved),
                "Selected upper triangles differ from original",
            )
            excluded_upper_count = sum((preserved - selected_upper).values())
            preserved = selected_upper
            excluded_faces = [f for f in bm.faces if f not in selected_faces]
            if excluded_faces:
                bmesh.ops.delete(bm, geom=excluded_faces, context="FACES")
            require(
                len(bm.faces) == len(selected_faces),
                "Component selection removed unexpected faces",
            )
        boundary = [edge for edge in bm.edges if edge.is_boundary]
        holed_cap = asset["allow_holed_cap"] and allow_open
        if holed_cap:
            loops, cap_loop_records = ordered_boundary_loops(boundary)
            loop = [v for one_loop in loops for v in one_loop]
        else:
            try:
                loop = boundary_loop(boundary)
            except ValueError as exc:
                raise ValueError(
                    f"{exc}; post-cut component facecounts={[r['facecount'] for _, r in components]}, selected boundary edges={len(boundary)}; see cut-components.json"
                ) from exc
            _, cap_loop_records = ordered_boundary_loops(boundary)
        boundary_plane_error = max(abs(v.co.z - cut) for v in loop)
        require(
            boundary_plane_error < 1e-6, "Cut boundary exceeds 1um numeric plane guard"
        )
        for vertex in loop:
            vertex.co.z = cut
        require(
            all(abs(v.co.z - cut) < 1e-6 for edge in boundary for v in edge.verts),
            "Cut boundary is not planar",
        )
        cap_material_id = len(original.data.materials)
        cap_faces = []
        loop_vectors = [v.co.copy() for v in loop]
        # Installed 4.5 bpy_extras/mesh_utils.py:394-398 maps integer
        # tessellation indices into the concatenated input polygon vertices.
        if holed_cap:
            before_faces = set(bm.faces)
            bmesh.ops.triangle_fill(
                bm,
                edges=boundary,
                normal=Vector((0, 0, -1)),
                use_beauty=False,
                use_dissolve=False,
            )
            cap_faces = [f for f in bm.faces if f not in before_faces]
            require(cap_faces, "Stock holed triangle fill produced no cap")
            for face in cap_faces:
                face.material_index = cap_material_id
                face.smooth = False
        else:
            for triangle in tessellate_polygon([loop_vectors]):
                require(
                    len(triangle) == 3
                    and all(
                        type(index) is int and 0 <= index < len(loop)
                        for index in triangle
                    )
                    and len(set(triangle)) == 3,
                    "Unexpected Blender4.5.9 tessellation index result",
                )
                verts = [loop[index] for index in triangle]
                if (verts[1].co - verts[0].co).cross(verts[2].co - verts[0].co).z > 0:
                    verts.reverse()
                face = bm.faces.new(verts)
                face.material_index = cap_material_id
                face.smooth = False
                cap_faces.append(face)
            require(len(cap_faces) == len(loop) - 2, "Unexpected cap triangulation")
        cap_validation = validate_holed_cap(cap_faces, cap_loop_records)
        cap_validation["method"] = (
            "Blender4.5.9 bmesh.ops.triangle_fill HOLES|POLYS"
            if holed_cap
            else "Blender4.5.9 mathutils.geometry.tessellate_polygon single simple loop"
        )
        polygons = [face for face in bm.faces if len(face.verts) > 3]
        if polygons:
            bmesh.ops.triangulate(
                bm, faces=polygons, quad_method="FIXED", ngon_method="EAR_CLIP"
            )
        after_upper = Counter(
            key(f) for f in bm.faces if all(v.co.z > cut for v in f.verts)
        )
        require(after_upper == preserved, "Wholly upper source triangles changed")
        bm.normal_update()
        require(all(f.normal.z < 0 for f in cap_faces), "Cap winding is not downward")
        retained_surface_area = sum(
            f.calc_area() for f in bm.faces if f not in cap_faces
        )
        cap_area = sum(f.calc_area() for f in cap_faces)
        cap_centroid = (
            sum((f.calc_center_median() * f.calc_area() for f in cap_faces), Vector())
            / cap_area
        )
        before_translation = {v: tuple(v.co) for v in bm.verts}
        for vertex in bm.verts:
            vertex.co.z -= cut
        serialization_delta = max(
            abs(v.co.z + cut - before_translation[v][2]) for v in bm.verts
        )
        # Cut loop is declared support Z=0; exact assignment only affects new boundary.
        for vertex in loop:
            vertex.co.z = 0.0
        pre_art_topology = topology(bm)
        art_scale = asset["uniform_art_scale"]
        before_art_scale = {v: tuple(v.co) for v in bm.verts}
        if art_scale != 1.0:
            for vertex in bm.verts:
                vertex.co *= art_scale
            cap_centroid *= art_scale
            cap_area *= art_scale**2
            for one_loop in cap_loop_records:
                one_loop["xy_m"] = [
                    [x * art_scale, y * art_scale] for x, y in one_loop["xy_m"]
                ]
                one_loop["area_m2"] *= art_scale**2
            cap_validation = validate_holed_cap(cap_faces, cap_loop_records)
            cap_validation["method"] = (
                "Blender4.5.9 bmesh.ops.triangle_fill HOLES|POLYS; baked source ART scale after upper preservation verification"
            )
        art_quantization_delta = max(
            abs(v.co[i] - before_art_scale[v][i] * art_scale)
            for v in bm.verts
            for i in range(3)
        )
        bm.normal_update()
        derived_topology, derived_bounds = topology(bm), dimensions(bm)
        com = center_of_mass(bm)
        mesh = bpy.data.meshes.new(
            asset["id"]
            + f"_PlanarBase{round(CUT_FRACTIONS[asset['id']] * 100)}{asset['art_suffix']}_Geometry"
        )
        bm.to_mesh(mesh)
        mesh.update()
        obj = bpy.data.objects.new(
            asset["id"]
            + f"_PlanarBase{round(CUT_FRACTIONS[asset['id']] * 100)}{asset['art_suffix']}",
            mesh,
        )
        bpy.context.collection.objects.link(obj)
        for slot in original.data.materials:
            mesh.materials.append(slot)
        mesh.materials.append(bpy.data.materials.new(asset["id"] + "_GeneratedCap"))
        require(
            obj.matrix_world == Matrix.Identity(4), "Derived transform must be identity"
        )
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        destination = output / (
            asset["id"]
            + f"_planar_base{round(CUT_FRACTIONS[asset['id']] * 100)}{asset['art_suffix']}.fbx"
        )
        require(
            bpy.ops.export_scene.fbx(
                filepath=str(destination),
                use_selection=True,
                object_types={"MESH"},
                global_scale=1.0,
                apply_unit_scale=True,
                apply_scale_options="FBX_SCALE_NONE",
                use_mesh_modifiers=False,
                bake_anim=False,
                axis_forward="-Y",
                axis_up="Z",
                use_space_transform=True,
                bake_space_transform=False,
                embed_textures=False,
                mesh_smooth_type="FACE",
            )
            == {"FINISHED"},
            "Derived FBX export failed",
        )
        require(
            sha(source) == before and source.stat().st_size == asset["bytes"],
            "Protected LOD0 source changed",
        )
        record = {
            "id": asset["id"],
            "status": "PREPARED_DERIVATIVE_DIAGNOSTIC_ONLY",
            "source": str(source),
            "source_sha256_before": before,
            "source_sha256_after": sha(source),
            "original_acquired_source_sha256": asset["original_source_sha256"],
            "license": asset["license"],
            "file": destination.name,
            "sha256": sha(destination),
            "bytes": destination.stat().st_size,
            "source_provenance": "POLY_HAVEN_LOD0_DERIVED_PLANAR_UNDERSIDE_CUT",
            "recipe_revision": RECIPE_REVISION,
            "source_repair_reason": CUT_REASONS[asset["id"]],
            "cut_height_fraction": CUT_FRACTIONS[asset["id"]],
            "cut_world_z_m": cut,
            "requested_cut_world_z_m": requested_cut,
            "translation_m": [0, 0, -cut],
            "removed_height_m": cut - original_bounds["min"][2],
            "original_bounds_m": original_bounds,
            "derived_bounds_m": derived_bounds,
            "original_topology": original_topology,
            "derived_topology": derived_topology,
            "retained_volume_fraction": derived_topology["volume_m3"]
            / original_topology["volume_m3"]
            if original_topology["volume_m3"] is not None
            else None,
            "source_volume_status": original_topology["volume_status"],
            "original_boundary_vertices_all_below_cut": True if allow_open else None,
            "original_boundary_max_z_m": original_boundary_max_z,
            "cut_above_original_boundary_margin_m": cut - original_boundary_max_z
            if original_boundary_max_z is not None
            else None,
            "retained_surface_ratio_basis": "PRE_ART_SCALE",
            "retained_original_surface_area_fraction": retained_surface_area
            / original_area,
            "preserved_upper_triangle_count": sum(preserved.values()),
            "preserved_upper_triangle_fraction": sum(preserved.values())
            / original_topology["triangles"],
            "preserved_upper_triangles_exact_before_translation": True,
            "upper_preservation_scope": "SELECTED_COMPONENT_ONLY"
            if asset["split_source02"] and allow_open
            else "ALL_SOURCE_UPPER_TRIANGLES",
            "excluded_upper_triangle_count": excluded_upper_count,
            "post_cut_component_selection": component_report,
            "translation_float32_roundtrip_max_error_m": serialization_delta,
            "cap_triangle_count": len(cap_faces),
            "cap_preassignment_plane_error_m": boundary_plane_error,
            "cap_material_id": cap_material_id,
            "cap_xy_polygon_m": [list(v.co)[:2] for v in loop]
            if len(cap_loop_records) == 1
            else None,
            "cap_xy_loops_m": cap_loop_records,
            "cap_loop_count": len(cap_loop_records),
            "cap_support_classification": "ODD_EVEN_PLANAR_REGION_WITH_DECLARED_HOLES",
            "cap_validation": cap_validation,
            "cap_area_m2": cap_area,
            "cap_centroid_m": [cap_centroid.x, cap_centroid.y, 0],
            "closed_solid_center_of_mass_m": com,
            "com_xy_m": com[:2],
            "com_basis": "uniform-density closed derived solid; not measured rock density",
            "export_axes": {"axis_forward": "-Y", "axis_up": "Z"},
            "expected_native_ue_bounds_cm": {
                "min": [
                    derived_bounds["min"][0] * 100,
                    -derived_bounds["max"][1] * 100,
                    derived_bounds["min"][2] * 100,
                ],
                "max": [
                    derived_bounds["max"][0] * 100,
                    -derived_bounds["min"][1] * 100,
                    derived_bounds["max"][2] * 100,
                ],
            },
            "native_axis_mapping": "EXPECTED_FROM_EXISTING_IMPORT_WITNESS_UE_CM_EQUALS_100_TIMES_X_MINUS_Y_Z_NOT_PROVED_FOR_THIS_EXPORT",
            "native_readback_required": "Every bounds min/max within 0.01cm plus planar cap bottom rays; dimensions alone insufficient",
            "no_overhang": False,
            "overhang_assessment": "NOT_PROVEN; preserved upper silhouette may extend beyond cap",
            "smoothing_modified": False,
            "scale_modified": art_scale != 1.0,
            "source_unmodified": True,
            "source_uniform_art_scale": art_scale,
            "source_art_scale_reason": "Explicit decorative half-size variant selected before native measurement; source units unchanged, native actor/import scale1"
            if art_scale != 1.0
            else "Unchanged source size",
            "source_to_derived_matrix": [
                [art_scale, 0, 0, 0],
                [0, art_scale, 0, 0],
                [0, 0, art_scale, -cut * art_scale],
                [0, 0, 0, 1],
            ],
            "source_to_derived_matrix_basis": "Imported source WORLD metres -> base translation -> baked uniform ART scale; source object matrix_world is already applied",
            "art_scale_quantization_max_delta_m": art_quantization_delta,
            "pre_art_scale_derived_topology": pre_art_topology,
            "art_scale_volume_expected_factor": art_scale**3,
            "yaw_modified": False,
            "placement": False,
            "qualified_assets": [],
            "classification": "DERIVED_ASSET_DIAGNOSTIC_ONLY",
        }
        bpy.data.objects.remove(obj, do_unlink=True)
        return record
    finally:
        bm.free()
        for obj in imported:
            bpy.data.objects.remove(obj, do_unlink=True)


def prepare_assets(assets, output):
    records = []
    allowed = Path("D:/yacs/data/assets/pcg365-large-rocks01").resolve(strict=True)
    for asset in assets:
        source = Path(asset["source"]).resolve(strict=True)
        require(
            source.is_relative_to(allowed) and source.suffix.lower() == ".fbx",
            "Source outside corrected LOD0 stage",
        )
        before = sha(source)
        size = source.stat().st_size
        require(
            before == PINS[asset["id"]] == asset["sha256"] and size == asset["bytes"],
            "Pinned source mismatch",
        )
        try:
            record = prepare(asset, output)
        except ValueError as exc:
            # A preparation guard rejection is evidence, never permission to
            # merge loops, change the frozen cut or silently substitute geometry.
            after = sha(source)
            require(
                after == before and source.stat().st_size == size,
                "Protected source changed during rejected preparation",
            )
            partial = output / (
                asset["id"]
                + f"_planar_base{round(CUT_FRACTIONS[asset['id']] * 100)}{asset['art_suffix']}.fbx"
            )
            record = {
                "id": asset["id"],
                "status": "REJECTED_PREPARATION",
                "reason": str(exc),
                "source": str(source),
                "source_sha256_before": before,
                "source_sha256_after": after,
                "source_bytes": size,
                "original_acquired_source_sha256": asset["original_source_sha256"],
                "license": asset["license"],
                "recipe_revision": RECIPE_REVISION,
                "source_repair_reason": CUT_REASONS[asset["id"]],
                "cut_height_fraction": CUT_FRACTIONS[asset["id"]],
                "source_provenance": "POLY_HAVEN_LOD0_DERIVATION_REJECTED_ORIGINAL_UNCHANGED",
                "partial_export": {
                    "file": partial.name,
                    "sha256": sha(partial),
                    "bytes": partial.stat().st_size,
                    "admitted": False,
                }
                if partial.is_file()
                else None,
                "placement": False,
                "qualified_assets": [],
                "classification": "DERIVED_ASSET_DIAGNOSTIC_ONLY",
            }
        records.append(record)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-source02-largest-component", action="store_true")
    parser.add_argument("--allow-source02-holed-cap", action="store_true")
    parser.add_argument("--source02-uniform-art-scale-half", action="store_true")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--expected-request-sha256", required=True)
    parser.add_argument("--inspection", type=Path, required=True)
    parser.add_argument("--inspection-sha256", required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--selection-sha256", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    require(
        bpy.app.background and bpy.app.version == (4, 5, 9),
        "Pinned background Blender4.5.9 required",
    )
    raw = args.request.read_bytes()
    request = json.loads(raw)
    require(
        hashlib.sha256(raw).hexdigest() == args.expected_request_sha256,
        "Request hash mismatch",
    )
    require(
        set(request) == {"schema_version", "assets"}
        and request["schema_version"] == 1
        and len(request["assets"]) == 2
        and {a["id"] for a in request["assets"]} == set(PINS),
        "Unexpected source request",
    )
    require(
        sha(args.inspection) == args.inspection_sha256
        and sha(args.selection) == args.selection_sha256,
        "Inspection/selection hash mismatch",
    )
    inspection = json.loads(args.inspection.read_bytes())
    selection = json.loads(args.selection.read_bytes())
    require(
        inspection["request_sha256"] == args.expected_request_sha256,
        "Inspection request mismatch",
    )
    require(
        set(selection) == {"schema_version", "selections"}
        and selection["schema_version"] == 1
        and len(selection["selections"]) == 2
        and {r["id"] for r in selection["selections"]} == set(PINS),
        "Explicit two-object selection required",
    )
    for asset in request["assets"]:
        require(
            set(asset) == {"id", "path", "sha256", "bytes"},
            "Unexpected source asset fields",
        )
        row = next(r for r in selection["selections"] if r["id"] == asset["id"])
        require(set(row) == {"id", "object_name"}, "Unexpected selection fields")
        inspected = next(a for a in inspection["assets"] if a["id"] == asset["id"])
        require(
            inspected["sha256_before"] == inspected["sha256_after"] == asset["sha256"],
            "Inspected source mismatch",
        )
        matches = [m for m in inspected["meshes"] if m["object"] == row["object_name"]]
        require(
            len(matches) == 1 and inspected["mesh_count"] == 1,
            "Explicit sole inspected LOD0 required",
        )
        require(
            not args.allow_source02_holed_cap or args.split_source02_largest_component,
            "Holed02 cap requires explicit largest component selection",
        )
        asset["uniform_art_scale"] = (
            0.5
            if args.source02_uniform_art_scale_half
            and asset["id"] == "namaqualand_boulder_02"
            else 1.0
        )
        asset["art_suffix"] = "Half" if asset["uniform_art_scale"] == 0.5 else ""
        asset["allow_holed_cap"] = args.allow_source02_holed_cap
        asset["split_source02"] = (
            args.split_source02_largest_component
            and asset["id"] == "namaqualand_boulder_02"
        )
        asset.update(
            source=asset["path"],
            selected_source_object=row["object_name"],
            expected_lod0_triangles=matches[0]["triangles"],
            original_source_sha256=asset["sha256"],
            license="CC0-1.0",
            expected_geometry_sha256=matches[0]["geometry_sha256"],
        )
    output = args.output_directory.resolve()
    allowed = Path("D:/yacs/work/pcg365").resolve(strict=True)
    require(
        output.is_relative_to(allowed) and output != allowed and not output.exists(),
        "Fresh isolated output required",
    )
    output.mkdir(parents=True, exist_ok=False)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    records = prepare_assets(request["assets"], output)
    require(args.request.read_bytes() == raw, "Request changed during preparation")
    require(
        sha(args.inspection) == args.inspection_sha256
        and sha(args.selection) == args.selection_sha256,
        "Inspection/selection changed",
    )
    receipt = {
        "schema_version": 1,
        "issue": 365,
        "status": "SCAN_PLANAR_BASE_DERIVATIVES_PARTIAL_REJECTION"
        if any(record["status"] == "REJECTED_PREPARATION" for record in records)
        else "SCAN_PLANAR_BASE_DERIVATIVES_PREPARED_ONLY",
        "blender_version": bpy.app.version_string,
        "recipe_revision": RECIPE_REVISION,
        "split_source02_largest_component": args.split_source02_largest_component,
        "allow_source02_holed_cap": args.allow_source02_holed_cap,
        "source02_uniform_art_scale_half": args.source02_uniform_art_scale_half,
        "art_scale_chosen_before_native_measurement": True,
        "prior_revision4_attempt": "Retained unchanged: full-size derivatives. Revision5 permits explicit baked decorative half-size02 variant, source units/native scale and contact policy unchanged.",
        "prior_revision3_attempt": "Retained unchanged: selected02 component rejected multiple boundary loops. Revision4 explicitly preserves holes using stock scanfill; no outer-only support claim.",
        "prior_revision2_attempt": "Retained unchanged: 02 rejected multiple cut loops; 06 prepared. Revision3 optionally selects one post-cut source component, never merges loops or changes terrain/contact gates.",
        "cut_fractions_frozen_before_execution": CUT_FRACTIONS,
        "source_repair_reasons": CUT_REASONS,
        "prior_revision1_attempt": "Retained unchanged: 02 rejected original boundary above 10% plane; 06 prepared. No native contact thresholds changed.",
        "request_sha256": hashlib.sha256(raw).hexdigest(),
        "inspection_sha256": args.inspection_sha256,
        "selection_sha256": args.selection_sha256,
        "assets": records,
        "script_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "exporter_sha256": sha(Path(export_fbx_bin.__file__)),
        "bmesh_api_version_source": API_SOURCE,
        "placement": False,
        "qualified_assets": [],
        "terrain_modified": False,
        "native_unreal_execution": "NOT_RUN",
        "art_acceptance": "PENDING_OWNER",
        "contact_sheet": "NOT_RUN_NO_RENDER_RESOURCE_CLAIM",
        "limitations": "Upper shape preserved with declared base translation; no continuous footprint/overhang, material, contact or final art admission.",
    }
    with (output / "scan-planar-bases.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
