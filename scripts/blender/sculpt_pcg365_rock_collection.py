"""Twenty affine sculpt recipes of pinned prepared scans; no contact admission."""

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
from mathutils import Matrix

RECIPES = (
    (1.18, 0.84, 0.88, 0.06, -0.03),
    (0.82, 1.16, 0.96, -0.05, 0.04),
    (1.10, 0.94, 1.18, 0.08, 0.02),
    (0.94, 1.08, 0.80, -0.07, -0.04),
    (1.22, 1.02, 0.84, 0.03, 0.08),
    (0.88, 0.80, 1.20, -0.04, 0.07),
    (1.04, 1.20, 1.06, 0.09, -0.05),
    (0.80, 0.98, 0.90, -0.09, 0.03),
    (1.14, 0.88, 1.08, 0.02, -0.09),
    (0.96, 1.14, 1.22, -0.06, -0.08),
)
IDS = {"namaqualand_boulder_02", "namaqualand_boulder_06"}


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
        "surface_area_m2": sum(sorted(face.calc_area() for face in bm.faces)),
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


def mesh_identity(mesh):
    mesh.calc_loop_triangles()
    return {
        "triangles": [list(t.vertices) for t in mesh.loop_triangles],
        "smooth_faces": [p.use_smooth for p in mesh.polygons],
        "sharp_edges": [item.value for item in mesh.attributes["sharp_edge"].data]
        if "sharp_edge" in mesh.attributes
        else None,
        "polygon_material_indices": [p.material_index for p in mesh.polygons],
        "material_slots": [m.name if m else None for m in mesh.materials],
        "uv_layers": [
            {"name": layer.name, "uv": [list(item.uv) for item in layer.data]}
            for layer in mesh.uv_layers
        ],
    }


def measure(mesh):
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        return topology(bm), dimensions(bm)
    finally:
        bm.free()


def produce(asset, output):
    source = Path(asset["source"]).resolve(strict=True)
    allowed = Path("D:/yacs/work/pcg365/large-base-half-yaw01/derived").resolve(
        strict=True
    )
    require(
        source.is_relative_to(allowed) and source.suffix.lower() == ".fbx",
        "Only final prepared FBX stage is allowed",
    )
    before = sha(source)
    require(
        before == asset["sha256"] and source.stat().st_size == asset["bytes"],
        "Prepared source identity differs",
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
        "Prepared FBX import failed",
    )
    imported = set(bpy.data.objects) - existing
    meshes = [obj for obj in imported if obj.type == "MESH"]
    require(len(meshes) == 1, "Exactly one prepared mesh required; no combined sources")
    original = meshes[0]
    require(
        not original.modifiers
        and original.animation_data is None
        and original.data.shape_keys is None,
        "Deformed source is unsupported",
    )
    imported_matrix = original.matrix_world.copy()
    require(
        all(math.isfinite(value) for row in imported_matrix for value in row),
        "Nonfinite imported object matrix",
    )
    require(
        list(imported_matrix[3]) == [0.0, 0.0, 0.0, 1.0],
        "Non-affine imported object matrix",
    )
    determinant = imported_matrix.to_3x3().determinant()
    require(
        math.isfinite(determinant) and determinant > 0,
        "Singular/mirrored imported source matrix",
    )
    before_bake_identity = mesh_identity(original.data)
    expected_world = [
        tuple(imported_matrix @ vertex.co) for vertex in original.data.vertices
    ]
    original.data.transform(imported_matrix)
    original.matrix_world = Matrix.Identity(4)
    original.data.update()
    require(
        mesh_identity(original.data) == before_bake_identity,
        "World-space bake changed triangle/UV/material identity",
    )
    bake_error = max(
        abs(vertex.co[i] - point[i])
        for vertex, point in zip(original.data.vertices, expected_world)
        for i in range(3)
    )
    bake_guard = max(
        1e-7, max(abs(value) for point in expected_world for value in point) * 2**-22
    )
    require(
        bake_error <= bake_guard,
        "Imported world matrix bake exceeds float32 serialization guard",
    )
    original_topology, original_bounds = measure(original.data)
    require(
        original_topology["triangles"] == asset["expected_lod0_triangles"],
        "Pinned triangle count differs",
    )
    expected = asset["expected_native_bounds_cm"]
    native = {
        "min": [
            original_bounds["min"][0] * 100,
            -original_bounds["max"][1] * 100,
            original_bounds["min"][2] * 100,
        ],
        "max": [
            original_bounds["max"][0] * 100,
            -original_bounds["min"][1] * 100,
            original_bounds["max"][2] * 100,
        ],
    }
    require(
        max(abs(native[k][i] - expected[k][i]) for k in native for i in range(3))
        <= 0.01,
        "Prepared importer bounds differ from pinned source witness",
    )
    identity = mesh_identity(original.data)
    records = []
    try:
        for recipe_index, recipe in enumerate(RECIPES, 1):
            sx, sy, sz, lean_x, lean_y = recipe
            affine = Matrix(
                ((sx, 0, lean_x, 0), (0, sy, lean_y, 0), (0, 0, sz, 0), (0, 0, 0, 1))
            )
            affine_det = affine.to_3x3().determinant()
            require(affine_det > 0, "Affine sculpt must preserve orientation")
            variant_id = (
                "rock02_" if asset["id"].endswith("02") else "rock06_"
            ) + f"{recipe_index:02d}"
            obj = original.copy()
            obj.data = original.data.copy()
            obj.name = variant_id
            obj.data.name = variant_id + "_Geometry"
            bpy.context.collection.objects.link(obj)
            try:
                expected_positions = [
                    tuple(affine @ vertex.co) for vertex in original.data.vertices
                ]
                custom_normals = (
                    [normal.vector.copy() for normal in original.data.corner_normals]
                    if original.data.has_custom_normals
                    else None
                )
                obj.data.transform(affine)
                if custom_normals is not None:
                    normal_matrix = affine.to_3x3().inverted().transposed()
                    expected_normals = [
                        (normal_matrix @ normal).normalized()
                        for normal in custom_normals
                    ]
                    # rna_mesh_api.cc v4.5.9 validates corner-count and sets custom normals.
                    # Explicit inverse-transpose assignment; independently observe decoded values.
                    obj.data.normals_split_custom_set(expected_normals)
                obj.data.update()
                normal_dot_error = None
                if custom_normals is not None:
                    observed_normals = [item.vector for item in obj.data.corner_normals]
                    require(
                        len(observed_normals) == len(expected_normals),
                        "Custom corner normal count changed",
                    )
                    normal_dot_error = max(
                        abs(1.0 - actual.normalized().dot(expected))
                        for actual, expected in zip(observed_normals, expected_normals)
                    )
                    require(
                        normal_dot_error <= 1e-4,
                        f"Inverse-transpose custom normals readback differs: max_one_minus_dot={normal_dot_error:.17g}, guard=0.0001; numeric decode guard only",
                    )
                require(
                    mesh_identity(obj.data) == identity,
                    "Sculpt changed topology/UV/material/sharp flags",
                )
                error = max(
                    abs(vertex.co[i] - point[i])
                    for vertex, point in zip(obj.data.vertices, expected_positions)
                    for i in range(3)
                )
                guard = max(
                    1e-7, max(abs(v) for p in expected_positions for v in p) * 2**-22
                )
                require(
                    error <= guard,
                    "Affine positions exceed float32 serialization guard",
                )
                topo, bounds = measure(obj.data)
                expected_volume = original_topology["volume_m3"] * affine_det
                require(
                    abs(topo["volume_m3"] - expected_volume)
                    <= max(1e-9, abs(expected_volume) * 3e-6),
                    "Affine determinant/volume witness differs",
                )
                require(abs(bounds["min"][2]) <= guard, "Affine sculpt moved baseZ0")
                positions = [tuple(v.co) for v in obj.data.vertices]
                geometry_sha = hashlib.sha256(
                    json.dumps(
                        positions, separators=(",", ":"), allow_nan=False
                    ).encode()
                ).hexdigest()
                edge_lengths_sq = [
                    sum(
                        (positions[e.vertices[0]][i] - positions[e.vertices[1]][i]) ** 2
                        for i in range(3)
                    )
                    for e in obj.data.edges
                ]
                mean_length_sq = sum(edge_lengths_sq) / len(edge_lengths_sq)
                shape_sha = hashlib.sha256(
                    json.dumps(
                        [round(value / mean_length_sq, 7) for value in edge_lengths_sq],
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest()
                bpy.ops.object.select_all(action="DESELECT")
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                destination = output / (variant_id + ".fbx")
                require(not destination.exists(), "Variant overwrite forbidden")
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
                    "Variant export failed",
                )
                records.append(
                    {
                        "id": variant_id,
                        "source_id": asset["id"],
                        "source": str(source),
                        "source_sha256_before": before,
                        "source_sha256_after": sha(source),
                        "source_bytes": asset["bytes"],
                        "original_source_sha256": asset["original_source_sha256"],
                        "license": asset["license"],
                        "source_metadata": {
                            k: v for k, v in asset.items() if k != "support_patch"
                        },
                        "file": destination.name,
                        "sha256": sha(destination),
                        "bytes": destination.stat().st_size,
                        "recipe": {
                            "id": variant_id,
                            "seed": 365000
                            + (200 if asset["id"].endswith("02") else 600)
                            + recipe_index,
                            "scale_xyz": [sx, sy, sz],
                            "lean_x_per_z": lean_x,
                            "lean_y_per_z": lean_y,
                            "twist": False,
                        },
                        "geometry_sha256": geometry_sha,
                        "normalized_shape_sha256": shape_sha,
                        "normalized_shape_hash_basis": "Indexed edge squared lengths divided by mean, rounded7decimals; invariant under translation, rotation, uniformscale; topology correspondence unchanged",
                        "normal_handling": "Explicit inverse-transpose custom corner normals assigned with normals_split_custom_set after Mesh.transform; independently read back with unchanged decode guard; positive determinant; original sharp/smooth flags preserved"
                        if custom_normals is not None
                        else "Stock Mesh.transform/update geometric normals; positive determinant; original sharp/smooth flags preserved",
                        "custom_normal_max_one_minus_dot": normal_dot_error,
                        "custom_normal_decode_dot_guard": 1e-4
                        if custom_normals is not None
                        else None,
                        "normal_transform_primary_source": "https://raw.githubusercontent.com/blender/blender/v4.5.9/source/blender/makesrna/intern/rna_mesh_api.cc#rna_Mesh_normals_split_custom_set",
                        "source_self_intersection": "UNKNOWN_NOT_TESTED",
                        "new_self_intersection": "Invertible global affine map preserves source intersection relationships in exact arithmetic; float32 geometric intersections NOT independently tested",
                        "yaw_deg": 0,
                        "native_actor_scale": [1, 1, 1],
                        "imported_object_matrix_world": [
                            list(row) for row in imported_matrix
                        ],
                        "imported_matrix_determinant": determinant,
                        "imported_world_bake_serialization_error_m": bake_error,
                        "imported_world_bake_float32_guard_m": bake_guard,
                        "source_geometry_basis": "Imported source WORLD metres; stock FBX object matrix baked without adjustment, then explicit decorative ART scale; post-bake pinned native bounds/triangles enforced",
                        "source_to_variant_matrix": [list(row) for row in affine],
                        "original_topology": original_topology,
                        "derived_topology": topo,
                        "bounds_m": bounds,
                        "volume_expected_factor": affine_det,
                        "surface_area_factor_measured": topo["surface_area_m2"]
                        / original_topology["surface_area_m2"],
                        "vertex_serialization_max_error_m": error,
                        "float32_serialization_guard_m": guard,
                        "geometry_connectivity_winding_uv_materials_unchanged": True,
                        "uv_material_triangle_inventory_sha256": hashlib.sha256(
                            json.dumps(
                                identity, sort_keys=True, separators=(",", ":")
                            ).encode()
                        ).hexdigest(),
                        "expected_native_bounds_cm": {
                            "min": [
                                bounds["min"][0] * 100,
                                -bounds["max"][1] * 100,
                                bounds["min"][2] * 100,
                            ],
                            "max": [
                                bounds["max"][0] * 100,
                                -bounds["min"][1] * 100,
                                bounds["max"][2] * 100,
                            ],
                        },
                        "native_axis_mapping": "EXPECTED_EXISTING_X_MINUS_Y_Z_WITNESS_REQUIRES_FRESH_NATIVE_READBACK",
                        "placement": False,
                        "qualified_assets": [],
                        "native_readback": "NOT_RUN",
                    }
                )
            finally:
                bpy.data.objects.remove(obj, do_unlink=True)
        require(
            sha(source) == before and source.stat().st_size == asset["bytes"],
            "Original prepared source changed",
        )
    finally:
        for obj in imported:
            bpy.data.objects.remove(obj, do_unlink=True)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--expected-request-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    require(
        bpy.app.background and bpy.app.version == (4, 5, 9),
        "Pinned background Blender4.5.9 required",
    )
    raw = args.request.read_bytes()
    require(
        args.expected_request_sha256
        == "427bc0bbc939d244d7cd728e613725c18fa8da43da9d022bba67e90f2e9cf5a3",
        "Only explicitly pinned source request allowed",
    )
    require(
        hashlib.sha256(raw).hexdigest() == args.expected_request_sha256,
        "Request SHA mismatch",
    )
    request = json.loads(raw)
    require(
        request["schema_version"] == 1
        and request["scope"] == "ISOLATED_ROCK_QUALIFICATION_ONLY"
        and request["placement"] is False
        and request["qualified_assets"] == []
        and len(request["assets"]) == 2
        and {a["id"] for a in request["assets"]} == IDS,
        "Unexpected source contract",
    )
    output = args.output_directory.resolve()
    allowed = Path("D:/yacs/work/pcg365").resolve(strict=True)
    require(
        output.is_relative_to(allowed) and output != allowed and not output.exists(),
        "Fresh bounded output required",
    )
    output.mkdir(parents=True, exist_ok=False)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    records = [
        record for asset in request["assets"] for record in produce(asset, output)
    ]
    require(args.request.read_bytes() == raw, "Request changed during production")
    require(
        len(records) == 20
        and len({r["geometry_sha256"] for r in records}) == 20
        and len({r["normalized_shape_sha256"] for r in records}) == 20,
        "Collection must contain20distinct geometries and nonuniform shapes",
    )
    report = {
        "schema_version": 1,
        "issue": 365,
        "status": "SCULPTED_ROCK_COLLECTION_PREPARED_ONLY",
        "request_sha256": args.expected_request_sha256,
        "script_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "blender_version": bpy.app.version_string,
        "exporter_sha256": sha(Path(export_fbx_bin.__file__)),
        "variant_count": len(records),
        "variants": records,
        "source_modified": False,
        "terrain_modified": False,
        "placement": False,
        "qualified_assets": [],
        "native_unreal_execution": "NOT_RUN",
        "production_admission": False,
    }
    with (output / "rock-collection.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
