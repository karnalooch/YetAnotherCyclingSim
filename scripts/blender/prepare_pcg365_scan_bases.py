"""Reversible diagnostic 10%-height planar cuts of the two pinned scan LOD0s."""

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
    "rock_07": "8f93bfba3e5abe10fcf51e76bd3ee3d60bb166d5fcfddb4eac6b6bf7b910b148",
    "rock_09": "e4d60fca53f426e986700ca90676452bd8ce3c3a7be26dec8d782251a6a82297",
}
CUT_FRACTION = 0.10
API_SOURCE = "https://raw.githubusercontent.com/blender/blender/v4.5.9/source/blender/bmesh/intern/bmesh_opdefines.cc"


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(face):
    points = [tuple(v.co) for v in face.verts]
    return min(tuple(points[i:] + points[:i]) for i in range(len(points)))


def topology(bm):
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
            count == 1 and directed[(b, a)] == 1 for (a, b), count in directed.items()
        ),
        "volume_m3": bm.calc_volume(signed=True),
    }
    require(
        report["connected"]
        and report["consistent_winding"]
        and report["boundary_edges"]
        == report["nonmanifold_edges"]
        == report["wire_edges"]
        == 0
        and report["volume_m3"] > 0,
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


def prepare(asset, output):
    source = Path(asset["source"]).resolve(strict=True)
    allowed = Path("D:/yacs/work/pcg365/rock-source-inspection01/lod0").resolve(
        strict=True
    )
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
    bm = bmesh.new()
    try:
        bm.from_mesh(original.data)
        for vertex in bm.verts:
            vertex.co = original.matrix_world @ vertex.co
        bm.normal_update()
        original_topology, original_bounds = topology(bm), dimensions(bm)
        require(
            original_topology["triangles"] == asset["expected_lod0_triangles"],
            "LOD0 triangle identity differs",
        )
        requested_cut = (
            original_bounds["min"][2] + CUT_FRACTION * original_bounds["dimensions"][2]
        )
        cut = Vector(
            (0, 0, requested_cut)
        ).z  # Match BMesh's native float32 plane coordinates.
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
        boundary = [edge for edge in bm.edges if edge.is_boundary]
        loop = boundary_loop(boundary)
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
        by_coordinate = {tuple(v.co): v for v in loop}
        for triangle in tessellate_polygon([loop_vectors]):
            verts = [by_coordinate[tuple(v)] for v in triangle]
            if (verts[1].co - verts[0].co).cross(verts[2].co - verts[0].co).z > 0:
                verts.reverse()
            face = bm.faces.new(verts)
            face.material_index = cap_material_id
            face.smooth = False
            cap_faces.append(face)
        require(len(cap_faces) == len(loop) - 2, "Unexpected cap triangulation")
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
        bm.normal_update()
        derived_topology, derived_bounds = topology(bm), dimensions(bm)
        com = center_of_mass(bm)
        mesh = bpy.data.meshes.new(asset["id"] + "_PlanarBase10_Geometry")
        bm.to_mesh(mesh)
        mesh.update()
        obj = bpy.data.objects.new(asset["id"] + "_PlanarBase10", mesh)
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
        destination = output / (asset["id"] + "_planar_base10.fbx")
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
        require(sha(source) == before, "Protected LOD0 source changed")
        record = {
            "id": asset["id"],
            "source": str(source),
            "source_sha256_before": before,
            "source_sha256_after": sha(source),
            "original_acquired_source_sha256": asset["original_source_sha256"],
            "license": asset["license"],
            "file": destination.name,
            "sha256": sha(destination),
            "bytes": destination.stat().st_size,
            "source_provenance": "POLY_HAVEN_LOD0_DERIVED_PLANAR_UNDERSIDE_CUT",
            "cut_height_fraction": CUT_FRACTION,
            "cut_world_z_m": cut,
            "requested_cut_world_z_m": requested_cut,
            "translation_m": [0, 0, -cut],
            "removed_height_m": cut - original_bounds["min"][2],
            "original_bounds_m": original_bounds,
            "derived_bounds_m": derived_bounds,
            "original_topology": original_topology,
            "derived_topology": derived_topology,
            "retained_volume_fraction": derived_topology["volume_m3"]
            / original_topology["volume_m3"],
            "retained_original_surface_area_fraction": retained_surface_area
            / original_area,
            "preserved_upper_triangle_count": sum(preserved.values()),
            "preserved_upper_triangles_exact_before_translation": True,
            "translation_float32_roundtrip_max_error_m": serialization_delta,
            "cap_triangle_count": len(cap_faces),
            "cap_preassignment_plane_error_m": boundary_plane_error,
            "cap_material_id": cap_material_id,
            "cap_xy_polygon_m": [list(v.co)[:2] for v in loop],
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
            "scale_modified": False,
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    require(
        bpy.app.background and bpy.app.version == (4, 5, 9),
        "Pinned background Blender4.5.9 required",
    )
    raw = args.request.read_bytes()
    request = json.loads(raw)
    require(
        request["schema_version"] == 1
        and request["scope"] == "ISOLATED_ROCK_QUALIFICATION_ONLY"
        and request["placement"] is False
        and request["qualified_assets"] == []
        and len(request["assets"]) == 2
        and {a["id"] for a in request["assets"]} == set(PINS),
        "Unexpected source request",
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
    records = [prepare(asset, output) for asset in request["assets"]]
    require(args.request.read_bytes() == raw, "Request changed during preparation")
    receipt = {
        "schema_version": 1,
        "issue": 365,
        "status": "SCAN_PLANAR_BASE_DERIVATIVES_PREPARED_ONLY",
        "blender_version": bpy.app.version_string,
        "cut_fraction_frozen_before_execution": CUT_FRACTION,
        "request_sha256": hashlib.sha256(raw).hexdigest(),
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
