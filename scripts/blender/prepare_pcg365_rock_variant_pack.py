"""Six explicit decorative size variants of hash-pinned prepared rocks; no admission."""

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

SCALES = (0.75, 1.0, 1.25)
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
    require(
        original.matrix_world == Matrix.Identity(4),
        "Prepared source transform must be identity; no implicit pose correction",
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
    coordinates = [tuple(v.co) for v in original.data.vertices]
    records = []
    try:
        for scale in SCALES:
            variant_id = asset["id"] + "_s" + str(round(scale * 100))
            obj = original.copy()
            obj.data = original.data.copy()
            obj.name = variant_id
            obj.data.name = variant_id + "_Geometry"
            bpy.context.collection.objects.link(obj)
            try:
                for vertex, point in zip(obj.data.vertices, coordinates):
                    vertex.co = tuple(value * scale for value in point)
                obj.data.update()
                require(
                    mesh_identity(obj.data) == identity,
                    "Triangles, winding, material slots or UVs changed",
                )
                error = max(
                    abs(vertex.co[i] - point[i] * scale)
                    for vertex, point in zip(obj.data.vertices, coordinates)
                    for i in range(3)
                )
                # Float32 storage guard only, never a contact/terrain tolerance.
                guard = max(
                    1e-7, max(abs(v * scale) for p in coordinates for v in p) * 2**-22
                )
                require(
                    error <= guard,
                    "Vertex transform serialization exceeds float32 guard",
                )
                topo, bounds = measure(obj.data)
                expected_volume = original_topology["volume_m3"] * scale**3
                expected_area = original_topology["surface_area_m2"] * scale**2
                require(
                    abs(topo["surface_area_m2"] - expected_area)
                    <= max(1e-9, expected_area * 2e-6),
                    "Scaled surface area factor differs",
                )
                require(
                    abs(topo["volume_m3"] - expected_volume)
                    <= max(1e-9, abs(expected_volume) * 2e-6),
                    "Scaled volume factor differs",
                )
                require(
                    max(
                        abs(bounds[k][i] - original_bounds[k][i] * scale)
                        for k in ("min", "max")
                        for i in range(3)
                    )
                    <= guard,
                    "Scaled bounds differ",
                )
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
                        "source_metadata": asset,
                        "file": destination.name,
                        "sha256": sha(destination),
                        "bytes": destination.stat().st_size,
                        "uniform_art_scale_relative_prepared": scale,
                        "yaw_deg": 0,
                        "native_actor_scale": [1, 1, 1],
                        "source_to_variant_matrix": [
                            [scale, 0, 0, 0],
                            [0, scale, 0, 0],
                            [0, 0, scale, 0],
                            [0, 0, 0, 1],
                        ],
                        "original_topology": original_topology,
                        "derived_topology": topo,
                        "bounds_m": bounds,
                        "volume_expected_factor": scale**3,
                        "surface_area_expected_factor": scale**2,
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
    report = {
        "schema_version": 1,
        "issue": 365,
        "status": "DECORATIVE_VARIANT_PACK_PREPARED_ONLY",
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
    with (output / "rock-variant-pack.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
