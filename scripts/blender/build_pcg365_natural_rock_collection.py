"""Twenty source-diverse decorative rocks from reviewed components of eight scans.

Requires actual inspector-bound selection; no inferred LOD/component, contact
threshold tuning or geographic admission. Run only under the coordinator lease.
"""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

IDS = {
    "namaqualand_boulder_02",
    "namaqualand_boulder_03",
    "namaqualand_boulder_04",
    "namaqualand_boulder_05",
    "namaqualand_boulder_06",
    "rock_07",
    "rock_09",
    "boulder_01",
}
REQUEST_SHA = "cca6cb185f48f586903f1285a2bba19b378873c14494cec89d8f09b548f44ea0"
RECIPES = (
    (1.0, 1.0, 1.0, 0.0, 0.0),
    (1.08, 0.94, 0.90, 0.025, -0.015),
    (0.93, 1.05, 1.10, -0.02, 0.025),
)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sibling(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_selection(request, inspection, selection):
    require(
        request["schema_version"]
        == inspection["schema_version"]
        == selection["schema_version"]
        == 1,
        "Schema1 required",
    )
    require(
        inspection["status"] == "ROCK_COMPONENT_SOURCE_INSPECTION_ONLY"
        and inspection["request_sha256"] == REQUEST_SHA,
        "Actual pinned inspector result required",
    )
    require(
        {a["id"] for a in request["assets"]} == IDS and len(request["assets"]) == 8,
        "Exact eight sources required",
    )
    require(
        selection["inspection_sha256"]
        and re.fullmatch("[0-9a-f]{64}", selection["inspection_sha256"]),
        "Inspection SHA required",
    )
    rows = selection["selections"]
    require(
        len(rows) == 8 and {r["id"] for r in rows} == IDS,
        "Exactly one selection per source required",
    )
    require(
        sum(r["variant_count"] for r in rows) == 20,
        "Exactly20 declared variants required",
    )
    for row in rows:
        require(
            set(row)
            == {
                "id",
                "object_name",
                "component_index",
                "component_triangles_sha256",
                "cut_fraction",
                "post_cut_selection",
                "variant_count",
            },
            "Unexpected selection fields",
        )
        require(
            type(row["variant_count"]) is int and row["variant_count"] in (2, 3),
            "Two or three variants per scan only",
        )
        require(
            type(row["cut_fraction"]) in (int, float)
            and math.isfinite(row["cut_fraction"])
            and 0.05 <= row["cut_fraction"] <= 0.20,
            "Source-only cut must be declared within5..20percent before execution",
        )
        require(
            row["post_cut_selection"] in ("KEEP_ALL", "LARGEST_SURFACE_AREA"),
            "Explicit post-cut selection required",
        )
        require(
            type(row["component_index"]) is int and row["component_index"] >= 0,
            "Explicit component index required",
        )
        asset = next(a for a in request["assets"] if a["id"] == row["id"])
        observed = [a for a in inspection["assets"] if a["id"] == row["id"]]
        require(
            len(observed) == 1
            and observed[0]["source_sha256_before"]
            == observed[0]["source_sha256_after"]
            == asset["sha256"],
            "Inspected source identity differs",
        )
        objects = [
            o
            for o in observed[0]["objects"]
            if o["name"] == row["object_name"] and o["type"] == "MESH"
        ]
        require(len(objects) == 1, "Reviewed mesh object missing/ambiguous")
        obj = objects[0]
        require(
            row["component_index"] < len(obj["components"]),
            "Reviewed component missing",
        )
        require(
            obj["components"][row["component_index"]]["triangle_indices_sha256"]
            == row["component_triangles_sha256"],
            "Reviewed component triangle identity differs",
        )
    return rows


def upper_witness(bm, cut):
    uv_layers = list(bm.loops.layers.uv.values())
    values = []
    for face in bm.faces:
        if not all(v.co.z > cut for v in face.verts):
            continue
        corners = [
            (
                tuple(loop.vert.co),
                tuple(tuple(loop[layer].uv) for layer in uv_layers),
                loop.edge.smooth,
                loop.edge.seam,
            )
            for loop in face.loops
        ]
        canonical = min(tuple(corners[i:] + corners[:i]) for i in range(len(corners)))
        values.append((canonical, face.material_index, face.smooth))
    return Counter(values)


def materialize_render_triangles(mesh, bpy):
    """Copy the exact inspected Blender render triangles and indexed UV corners."""
    mesh.calc_loop_triangles()
    data = bpy.data.meshes.new(mesh.name + "_ExplicitRenderTriangles")
    triangles = list(mesh.loop_triangles)
    data.from_pydata(
        [tuple(v.co) for v in mesh.vertices], [], [list(t.vertices) for t in triangles]
    )
    for material in mesh.materials:
        data.materials.append(material)
    for polygon, triangle in zip(data.polygons, triangles):
        source_polygon = mesh.polygons[triangle.polygon_index]
        polygon.material_index = source_polygon.material_index
        polygon.use_smooth = source_polygon.use_smooth
    for source_layer in mesh.uv_layers:
        layer = data.uv_layers.new(name=source_layer.name)
        for polygon, triangle in zip(data.polygons, triangles):
            for output_loop, source_loop in zip(polygon.loop_indices, triangle.loops):
                layer.data[output_loop].uv = source_layer.data[source_loop].uv
    edge_flags = {
        tuple(sorted(e.vertices)): (e.use_edge_sharp, e.use_seam) for e in mesh.edges
    }
    for edge in data.edges:
        sharp, seam = edge_flags.get(tuple(sorted(edge.vertices)), (False, False))
        edge.use_edge_sharp = sharp
        edge.use_seam = seam
    data.update()
    require(
        [list(p.vertices) for p in data.polygons]
        == [list(t.vertices) for t in triangles],
        "Explicit render triangle copy changed inspected vertex indices",
    )
    return data


def prepare(asset, row, output, base, inspector):
    import bmesh
    import bpy
    from mathutils import Matrix, Vector

    source = Path(asset["path"]).resolve(strict=True)
    require(
        sha(source) == asset["sha256"] and source.stat().st_size == asset["bytes"],
        "Source identity drift",
    )
    before = sha(source)
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
        "FBX import failed",
    )
    imported = set(bpy.data.objects) - existing
    bm = bmesh.new()
    created = []
    try:
        objects = [
            o for o in imported if o.name == row["object_name"] and o.type == "MESH"
        ]
        require(len(objects) == 1, "Exact reviewed object missing")
        original = objects[0]
        require(
            not original.modifiers
            and original.animation_data is None
            and original.data.shape_keys is None,
            "Deformed source unsupported",
        )
        matrix = original.matrix_world.copy()
        require(
            all(math.isfinite(x) for r in matrix for x in r)
            and list(matrix[3]) == [0.0, 0.0, 0.0, 1.0]
            and matrix.to_3x3().determinant() > 0,
            "Unsupported imported source matrix",
        )
        mesh = original.data
        mesh.calc_loop_triangles()
        source_nontri_polygon_count = sum(len(p.vertices) != 3 for p in mesh.polygons)
        triangular_mesh = materialize_render_triangles(mesh, bpy)
        groups = inspector.face_components(
            [list(t.vertices) for t in mesh.loop_triangles]
        )
        indices = groups[row["component_index"]]
        require(
            hashlib.sha256(
                json.dumps(indices, separators=(",", ":")).encode()
            ).hexdigest()
            == row["component_triangles_sha256"],
            "Actual component index witness drift",
        )
        bm.from_mesh(triangular_mesh)
        bm.faces.ensure_lookup_table()
        chosen = {bm.faces[i] for i in indices}
        keep = {v for f in chosen for v in f.verts}
        bmesh.ops.delete(
            bm, geom=[v for v in bm.verts if v not in keep], context="VERTS"
        )
        require(
            set(bm.faces) == chosen, "Component deletion changed selected triangles"
        )
        for vertex in bm.verts:
            vertex.co = matrix @ vertex.co
        bm.normal_update()
        source_topology = base.topology(
            bm, allow_open=any(e.is_boundary for e in bm.edges)
        )
        bounds = base.dimensions(bm)
        cut = Vector(
            (0, 0, bounds["min"][2] + bounds["dimensions"][2] * row["cut_fraction"])
        ).z
        original_boundary = [v.co.z for e in bm.edges if e.is_boundary for v in e.verts]
        require(
            not original_boundary or max(original_boundary) < cut,
            "Declared cut fails to remove every original open boundary",
        )
        upper_before = upper_witness(bm, cut)
        require(upper_before, "No preserved wholly upper triangles")
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
        components = base.face_components(bm)
        component_reports = [report for _, report in components]
        excluded_upper = 0
        if row["post_cut_selection"] == "LARGEST_SURFACE_AREA":
            keep_faces = components[0][0]
            keep_verts = {v for f in keep_faces for v in f.verts}
            bmesh.ops.delete(
                bm, geom=[v for v in bm.verts if v not in keep_verts], context="VERTS"
            )
            selected = upper_witness(bm, cut)
            require(
                not (selected - upper_before),
                "Post-cut selection changed upper source triangles",
            )
            excluded_upper = sum((upper_before - selected).values())
            upper_before = selected
        else:
            require(
                len(components) == 1,
                f"Declared KEEP_ALL produced multiple disconnected components: {component_reports}",
            )
        boundary = [e for e in bm.edges if e.is_boundary]
        require(boundary, "Missing cut boundary")
        require(
            max(abs(v.co.z - cut) for e in boundary for v in e.verts) < 1e-6,
            "Boundary exceeds1um numeric plane guard",
        )
        for v in {v for e in boundary for v in e.verts}:
            v.co.z = cut
        loops, loop_records = base.ordered_boundary_loops(boundary)
        prior = set(bm.faces)
        bmesh.ops.triangle_fill(
            bm,
            edges=boundary,
            normal=Vector((0, 0, -1)),
            use_beauty=False,
            use_dissolve=False,
        )
        cap = [f for f in bm.faces if f not in prior]
        require(cap, "Stock cap failed")
        cap_material = len(mesh.materials)
        for f in cap:
            f.material_index = cap_material
            f.smooth = False
        cap_validation = base.validate_holed_cap(cap, loop_records)
        cap_validation["method"] = "Blender4.5.9 bmesh.ops.triangle_fill HOLES|POLYS"
        require(
            upper_witness(bm, cut) == upper_before,
            "Wholly upper coordinates/UV/material/smooth identity changed",
        )
        bm.normal_update()
        require(all(f.normal.z < 0 for f in cap), "Cap winding must point downward")
        clipped_polygons = [f for f in bm.faces if len(f.verts) > 3]
        if clipped_polygons:
            bmesh.ops.triangulate(
                bm, faces=clipped_polygons, quad_method="FIXED", ngon_method="EAR_CLIP"
            )
        require(
            upper_witness(bm, cut) == upper_before,
            "Clipped-face triangulation changed wholly upper source triangles",
        )
        prepared_topology = base.topology(bm)
        upper_sha = hashlib.sha256(
            repr(sorted(upper_before.items())).encode()
        ).hexdigest()
        for v in bm.verts:
            v.co.z -= cut
        prepared_bounds = base.dimensions(bm)
        center = base.center_of_mass(bm)
        records = []
        for number, recipe in enumerate(RECIPES[: row["variant_count"]], 1):
            sx, sy, sz, lx, ly = recipe
            transform = Matrix(
                ((sx, 0, lx, 0), (0, sy, ly, 0), (0, 0, sz, 0), (0, 0, 0, 1))
            )
            variant = bm.copy()
            try:
                for v in variant.verts:
                    v.co = transform @ v.co
                variant.normal_update()
                topo = base.topology(variant)
                vbounds = base.dimensions(variant)
                det = transform.to_3x3().determinant()
                require(
                    abs(topo["volume_m3"] - prepared_topology["volume_m3"] * det)
                    <= max(1e-9, abs(topo["volume_m3"]) * 3e-6),
                    "ART volume/determinant witness differs",
                )
                require(abs(vbounds["min"][2]) <= 1e-6, "BaseZ0 changed")
                ident = asset["id"] + "_" + str(number).zfill(2)
                data = bpy.data.meshes.new(ident + "_Geometry")
                for material in mesh.materials:
                    data.materials.append(material)
                capmat = bpy.data.materials.get(
                    "PCG365_SourceOnly_Underside"
                ) or bpy.data.materials.new("PCG365_SourceOnly_Underside")
                data.materials.append(capmat)
                variant.to_mesh(data)
                # Fresh mesh has no stale imported custom normal attributes.
                # Geometric normals honor retained BMesh smooth/sharp flags.
                require(
                    not data.has_custom_normals,
                    "Unexpected custom normals in fresh prepared mesh",
                )
                readback = bmesh.new()
                try:
                    readback.from_mesh(data)
                    require(
                        upper_witness(readback, 0.0) == upper_witness(variant, 0.0),
                        "Prepared mesh readback changed upper geometry/UV/material/smooth/sharp/seam identity",
                    )
                finally:
                    readback.free()
                data.update()
                require(
                    all(
                        math.isfinite(v) for n in data.corner_normals for v in n.vector
                    ),
                    "Nonfinite recalculated corner normal",
                )
                obj = bpy.data.objects.new(ident, data)
                bpy.context.collection.objects.link(obj)
                created.append(obj)
                bpy.ops.object.select_all(action="DESELECT")
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                target = output / (ident + ".fbx")
                require(not target.exists(), "Output overwrite forbidden")
                require(
                    bpy.ops.export_scene.fbx(
                        filepath=str(target),
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
                    "FBX export failed",
                )
                geometry_sha = hashlib.sha256(
                    json.dumps(
                        [list(v.co) for v in data.vertices],
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode()
                ).hexdigest()
                lengths = [
                    sum(
                        (
                            data.vertices[e.vertices[0]].co[i]
                            - data.vertices[e.vertices[1]].co[i]
                        )
                        ** 2
                        for i in range(3)
                    )
                    for e in data.edges
                ]
                mean = sum(lengths) / len(lengths)
                shape_sha = hashlib.sha256(
                    json.dumps(
                        [round(x / mean, 7) for x in lengths], separators=(",", ":")
                    ).encode()
                ).hexdigest()
                records.append(
                    {
                        "id": ident,
                        "source_id": asset["id"],
                        "source": str(target),
                        "source_relative": "rock-collection/" + target.name,
                        "sha256": sha(target),
                        "bytes": target.stat().st_size,
                        "base_source_sha256": before,
                        "original_source_sha256": asset.get(
                            "original_source_sha256", before
                        ),
                        "license": asset["license"],
                        "geometry_sha256": geometry_sha,
                        "normalized_shape_sha256": shape_sha,
                        "expected_lod0_triangles": topo["triangles"],
                        "expected_native_bounds_cm": {
                            "min": [
                                vbounds["min"][0] * 100,
                                -vbounds["max"][1] * 100,
                                vbounds["min"][2] * 100,
                            ],
                            "max": [
                                vbounds["max"][0] * 100,
                                -vbounds["min"][1] * 100,
                                vbounds["max"][2] * 100,
                            ],
                        },
                        "recipe": {
                            "source_component": row,
                            "affine_art_matrix": [list(r) for r in transform],
                            "native_actor_scale": [1, 1, 1],
                        },
                        "source_provenance": "LICENSED_SCAN_REVIEWED_COMPONENT_PLANAR_UNDERSIDE_DECLARED_ART_AFFINE",
                        "source_object_matrix_world": [list(r) for r in matrix],
                        "source_nontri_polygon_count": source_nontri_polygon_count,
                        "source_triangulation": "Exact inspected Mesh.loop_triangles vertex/UV-loop mapping; source file unchanged",
                        "clipped_nontri_face_count": len(clipped_polygons),
                        "source_topology": source_topology,
                        "prepared_topology": prepared_topology,
                        "derived_topology": topo,
                        "bounds_m": vbounds,
                        "prepared_bounds_m": prepared_bounds,
                        "cut_z_source_m": cut,
                        "preserved_upper_triangle_count": sum(upper_before.values()),
                        "excluded_upper_triangle_count": excluded_upper,
                        "preserved_upper_coordinates_uv_material_smooth_sha256": upper_sha,
                        "upper_preserved_exact_before_base_translation_and_art": True,
                        "post_cut_component_reports": component_reports,
                        "cap_validation": cap_validation,
                        "cap_material_id": cap_material,
                        "cap_xy_loops_m": [
                            {
                                **record,
                                "xy_m": [[sx * x, sy * y] for x, y in record["xy_m"]],
                                "area_m2": record["area_m2"] * sx * sy,
                            }
                            for record in loop_records
                        ],
                        "com_m": list(transform @ Vector(center)),
                        "normal_handling": "Geometric normals recalculated after source-only planar cut and positive ART affine; original face smooth flags and UV custom data retained; source imported custom normals are not claimed preserved",
                        "source_self_intersection": "UNKNOWN_NOT_TESTED",
                        "placement": False,
                        "qualified_assets": [],
                        "native_readback": "NOT_RUN",
                    }
                )
            finally:
                variant.free()
        require(
            sha(source) == before and source.stat().st_size == asset["bytes"],
            "Source changed",
        )
        return records
    finally:
        bm.free()
        for obj in created + list(imported):
            bpy.data.objects.remove(obj, do_unlink=True)


def main():
    import bpy

    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("request", "inspection", "selection"):
        parser.add_argument("--" + key, type=Path, required=True)
        parser.add_argument("--expected-" + key + "-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    require(
        bpy.app.background and bpy.app.version == (4, 5, 9),
        "Pinned background Blender4.5.9 required",
    )
    inputs = {
        key: getattr(args, key).read_bytes()
        for key in ("request", "inspection", "selection")
    }
    for key, raw in inputs.items():
        require(
            hashlib.sha256(raw).hexdigest()
            == getattr(args, "expected_" + key + "_sha256"),
            "Input SHA differs: " + key,
        )
    require(
        args.expected_request_sha256 == REQUEST_SHA,
        "Only exact eight-source request supported",
    )
    request, inspection, selection = (
        json.loads(inputs[k]) for k in ("request", "inspection", "selection")
    )
    require(
        selection["inspection_sha256"] == args.expected_inspection_sha256,
        "Selection not bound to actual inspection",
    )
    rows = validate_selection(request, inspection, selection)
    output = args.output_directory.resolve()
    root = Path("D:/yacs/work/pcg365").resolve(strict=True)
    require(
        output.is_relative_to(root) and output != root and not output.exists(),
        "Fresh bounded output required",
    )
    base = sibling("prepare_pcg365_large_scan_bases")
    inspector = sibling("inspect_pcg365_rock_components")
    output.mkdir(parents=True, exist_ok=False)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    records, rejected = [], []
    for row in sorted(rows, key=lambda r: r["id"]):
        asset = next(a for a in request["assets"] if a["id"] == row["id"])
        try:
            records.extend(prepare(asset, row, output, base, inspector))
        except ValueError as exc:
            require(
                sha(Path(asset["path"])) == asset["sha256"],
                "Source identity changed on rejection",
            )
            rejected.append(
                {
                    "id": asset["id"],
                    "status": "REJECTED_PREPARATION",
                    "reason": str(exc),
                    "selection": row,
                    "source_sha256_after": sha(Path(asset["path"])),
                    "unadmitted_partial_files": [
                        {"file": p.name, "sha256": sha(p), "bytes": p.stat().st_size}
                        for p in sorted(output.glob(asset["id"] + "_*.fbx"))
                    ],
                }
            )
    for key, raw in inputs.items():
        require(
            getattr(args, key).read_bytes() == raw, "Input changed during production"
        )
    require(
        len({r["geometry_sha256"] for r in records}) == len(records),
        "Duplicate geometry output",
    )
    report = {
        "schema_version": 1,
        "issue": 365,
        "scope": "LOCAL_NATURAL_ROCK_COLLECTION20_ASSET_LIBRARY_ONLY",
        "status": "NATURAL_ROCK_COLLECTION20_PREPARED_ONLY"
        if not rejected and len(records) == 20
        else "NATURAL_ROCK_COLLECTION_PARTIAL_REJECTION",
        "variants": records,
        "rejected_sources": rejected,
        "variant_count": len(records),
        "source_family_count": len({r["source_id"] for r in records}),
        "inputs_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in inputs.items()},
        "script_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "utility_sha256": {
            m.__name__: sha(Path(m.__file__)) for m in (base, inspector)
        },
        "source_modified": False,
        "terrain_modified": False,
        "placement": False,
        "qualified_assets": [],
        "production_admission": False,
        "native_unreal_execution": "NOT_RUN",
    }
    with (output / "natural-rock-collection.json").open(
        "x", encoding="utf-8"
    ) as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
