"""Source-derived heightfield rocks with complete planar underside support.

Explicit alternative to exact-triangle recuts: resample the visible upper source
envelope, retain its concave sampled footprint and add closed underside/walls.
Overhangs are removed by declaration, never presented as unchanged scan geometry.
Only source-only diagnostics follow; native qualification remains mandatory.
"""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def module(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(name + ".py")
    )
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def shell(points, cells):
    """Close the largest edge-connected sampled domain, preserving holes."""
    if not cells:
        raise ValueError("No complete source envelope cells")
    original_cells = len(cells)
    cells = set(cells)
    # Diagonal-only corner contact creates a nonmanifold vertical wall edge.
    # Erode one declared cell at each pinch; never fill absent source geometry.
    removed_pinches = 0
    while True:
        removals = set()
        corners = {
            key
            for i, j in cells
            for key in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
        }
        for i, j in sorted(corners):
            incident = {(i - 1, j - 1), (i - 1, j), (i, j - 1), (i, j)} & cells
            if len(incident) == 2:
                first, second = sorted(incident)
                if first[0] != second[0] and first[1] != second[1]:
                    removals.add(second)
        if not removals:
            break
        cells -= removals
        removed_pinches += len(removals)
    if not cells:
        raise ValueError("Source envelope eroded to an empty domain")
    pending, groups = set(cells), []
    while pending:
        first = min(pending)
        queue, group = deque([first]), set()
        pending.remove(first)
        while queue:
            cell = queue.popleft()
            group.add(cell)
            i, j = cell
            for neighbour in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                if neighbour in pending:
                    pending.remove(neighbour)
                    queue.append(neighbour)
        groups.append(group)
    kept = max(groups, key=lambda g: (len(g), tuple(sorted(g))))
    corners = sorted(
        {
            key
            for i, j in kept
            for key in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
        }
    )
    indices = {key: index for index, key in enumerate(corners)}
    vertices = [points[key] for key in corners]
    count = len(vertices)
    vertices += [(p[0], p[1], 0.0) for p in vertices]
    faces, edges = [], {}
    for i, j in sorted(kept):
        a, b, c, d = [
            indices[key] for key in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
        ]
        faces.extend(
            (
                (a, b, c),
                (a, c, d),
                (count + a, count + c, count + b),
                (count + a, count + d, count + c),
            )
        )
        for u, v in ((a, b), (b, c), (c, d), (d, a)):
            if (v, u) in edges:
                del edges[(v, u)]
            else:
                edges[(u, v)] = True
    for u, v in sorted(edges):
        faces.extend(((u, count + u, count + v), (u, count + v, v)))
    return (
        vertices,
        faces,
        {
            "retained_cells": len(kept),
            "source_eligible_cells": original_cells,
            "discarded_corner_pinch_cells": removed_pinches,
            "discarded_disconnected_cells": len(cells) - len(kept),
            "boundary_edges": len(edges),
            "top_vertices": count,
        },
    )


def produce(row, output, grid, repair, base, natural):
    import bmesh
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    source = Path(row["source"]).resolve(strict=True)
    repair.require(
        repair.sha(source) == row["sha256"] and source.stat().st_size == row["bytes"],
        "Source identity differs",
    )
    existing = set(bpy.data.objects)
    repair.require(
        bpy.ops.import_scene.fbx(
            filepath=str(source), use_anim=False, use_image_search=False
        )
        == {"FINISHED"},
        "Source import failed",
    )
    imported = set(bpy.data.objects) - existing
    bm = bmesh.new()
    result_bm = bmesh.new()
    try:
        objects = [o for o in imported if o.type == "MESH"]
        repair.require(len(objects) == 1, "One source mesh required")
        original = objects[0]
        repair.require(
            not original.modifiers
            and original.data.shape_keys is None
            and original.animation_data is None,
            "Source deformation unsupported",
        )
        data = natural.materialize_render_triangles(original.data, bpy)
        bm.from_mesh(data)
        for v in bm.verts:
            v.co = original.matrix_world @ v.co
        bm.normal_update()
        source_topology = base.topology(bm)
        bounds = base.dimensions(bm)
        low, high = bounds["min"], bounds["max"]
        expected = row["expected_native_bounds_cm"]
        observed = {
            "min": [low[0] * 100, -high[1] * 100, low[2] * 100],
            "max": [high[0] * 100, -low[1] * 100, high[2] * 100],
        }
        repair.require(
            all(
                abs(a - b) <= 0.01
                for key in observed
                for a, b in zip(observed[key], expected[key])
            ),
            "Source native bounds differ",
        )
        tree = BVHTree.FromBMesh(bm, epsilon=0)
        span = max(bounds["dimensions"])

        def hit(x, y):
            return tree.ray_cast(
                Vector((x, y, high[2] + span)),
                Vector((0, 0, -1)),
                high[2] - low[2] + 2 * span,
            )[0]

        points = {}
        for i in range(grid):
            for j in range(grid):
                x = low[0] + (i + 0.5) * bounds["dimensions"][0] / grid
                y = low[1] + (j + 0.5) * bounds["dimensions"][1] / grid
                value = hit(x, y)
                if value is not None and value.z - low[2] > 1e-6:
                    points[(i, j)] = (x, y, float(value.z - low[2]))
        cells = set()
        error_bound = max(bounds["dimensions"][:2]) / grid
        rejected_top_cells = 0
        for i in range(grid - 1):
            for j in range(grid - 1):
                keys = ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
                if all(key in points for key in keys):
                    p = [points[k] for k in keys]
                    # Reject holes visible in either proposed top triangle.
                    checks = []
                    for tri in ((0, 1, 2), (0, 2, 3)):
                        x, y, z = [
                            sum(p[k][axis] for k in tri) / 3 for axis in range(3)
                        ]
                        actual = hit(x, y)
                        checks.append(
                            actual is not None
                            and abs(z - (actual.z - low[2])) <= error_bound
                        )
                    if all(checks):
                        cells.add((i, j))
                    else:
                        rejected_top_cells += 1
        vertices, faces, shell_report = shell(points, cells)
        shell_report["discarded_top_error_or_hole_cells"] = rejected_top_cells
        mesh = bpy.data.meshes.new(row["id"] + "_SourceEnvelope")
        mesh.from_pydata(vertices, [], faces)
        mesh.materials.append(
            bpy.data.materials.new("PCG365_SourceEnvelope_ForgeConsumer")
        )
        for polygon in mesh.polygons:
            polygon.use_smooth = all(
                i < shell_report["top_vertices"] for i in polygon.vertices
            )
        mesh.update()
        repair.require(not mesh.validate(), "Source envelope required mesh repair")
        result_bm.from_mesh(mesh)
        result_bm.normal_update()
        topology = base.topology(result_bm)
        derived_bounds = base.dimensions(result_bm)
        diagnostic = repair.evaluate_ideal_plane(
            repair.sample_bvh(result_bm, derived_bounds, 33),
            repair.sample_bvh(result_bm, derived_bounds, 65),
            derived_bounds["dimensions"][2] * 100,
            repair.asset_module("pcg_rock_contact_policy"),
            repair.asset_module("pcg_boulder_support"),
        )
        repair.require(
            diagnostic["status"] == "PASS_IDEAL_PLANE_SAMPLED_SOURCE_DIAGNOSTIC_ONLY",
            "Envelope ideal-plane contact rejected",
        )
        errors = []
        for face in faces:
            if any(index >= shell_report["top_vertices"] for index in face):
                continue
            x, y, z = [
                sum(vertices[index][axis] for index in face) / 3 for axis in range(3)
            ]
            actual = hit(x, y)
            repair.require(actual is not None, "Envelope crossed unsampled source hole")
            errors.append(abs(z - (actual.z - low[2])))
        # Error budget is source sampling scale, not terrain/contact tolerance.
        repair.require(
            max(errors) <= error_bound,
            "Source top resampling exceeds one-cell diagnostic error budget",
        )
        bpy.ops.object.select_all(action="DESELECT")
        obj = bpy.data.objects.new(row["id"], mesh)
        bpy.context.collection.objects.link(obj)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        path = output / (row["id"] + ".fbx")
        repair.require(not path.exists(), "Preserve previous derived asset")
        repair.require(
            bpy.ops.export_scene.fbx(
                filepath=str(path),
                use_selection=True,
                object_types={"MESH"},
                global_scale=1,
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
            "Envelope export failed",
        )
        b = derived_bounds
        return {
            "id": row["id"],
            "source_id": row["source_id"],
            "license": row["license"],
            "source": str(path),
            "source_relative": "rock-collection/" + path.name,
            "sha256": repair.sha(path),
            "bytes": path.stat().st_size,
            "base_source_sha256": row["sha256"],
            "original_source_sha256": row.get(
                "original_source_sha256", row["base_source_sha256"]
            ),
            "expected_lod0_triangles": topology["triangles"],
            "expected_native_bounds_cm": {
                "min": [b["min"][0] * 100, -b["max"][1] * 100, b["min"][2] * 100],
                "max": [b["max"][0] * 100, -b["min"][1] * 100, b["max"][2] * 100],
            },
            "recipe": {
                "repair_schema": "PCG365_SOURCE_TOP_ENVELOPE_V1",
                "grid": grid,
                "parent_source_sha256": row["sha256"],
                "parent_recipe": row["recipe"],
                "original_upper_triangles_preserved": False,
                "overhangs": "REMOVED_BY_DECLARED_UPPER_ENVELOPE_RESAMPLING",
                "source_top_sampled_error_max_m": max(errors),
                "source_top_sampled_error_p95_m": sorted(errors)[
                    int(0.95 * (len(errors) - 1))
                ],
                "source_top_error_limit_m": error_bound,
                "continuous_error_bound": "NOT_PROVED",
                "source_volume_m3": source_topology["volume_m3"],
                "derived_volume_m3": topology["volume_m3"],
                "volume_delta_m3": topology["volume_m3"] - source_topology["volume_m3"],
                "topology": topology,
                "footprint": shell_report,
                "uv": "NO_SOURCE_UV_REUSE_WORLD_ALIGNED_FORGE_CONSUMER_REQUIRED",
                "ideal_plane": diagnostic,
            },
            "placement": False,
            "qualified_assets": [],
            "native_readback": "NOT_RUN",
        }
    finally:
        bm.free()
        result_bm.free()
        for obj in set(bpy.data.objects) - existing:
            bpy.data.objects.remove(obj, do_unlink=True)
        repair.require(repair.sha(source) == row["sha256"], "Source changed")


def main():
    import bpy

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--expected-catalog-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--asset", action="append")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    repair = module("repair_pcg365_natural_rock_support")
    repair.require(
        bpy.app.background and bpy.app.version == (4, 5, 9),
        "Pinned Blender4.5.9 required",
    )
    repair.require(
        repair.sha(args.catalog) == args.expected_catalog_sha256,
        "Source catalog differs",
    )
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    all_rows = repair.validate_catalog(catalog)
    requested = args.asset or [r["id"] for r in all_rows]
    repair.require(
        len(requested) == len(set(requested))
        and set(requested) <= {r["id"] for r in all_rows},
        "Exact unique source IDs required",
    )
    rows = [r for r in all_rows if r["id"] in requested]
    output = args.output_directory.resolve()
    repair.require(
        output.is_relative_to(repair.ROOT.resolve()) and not output.exists(),
        "Fresh bounded output required",
    )
    output.mkdir(parents=True)
    derived = output / "rock-collection"
    derived.mkdir()
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1
    base = module("prepare_pcg365_large_scan_bases")
    natural = module("build_pcg365_natural_rock_collection")
    results, rejected = [], []
    for row in rows:
        try:
            result = produce(row, derived, 129, repair, base, natural)
            results.append(result)
            print(
                json.dumps(
                    {"asset": row["id"], "status": "SOURCE_ENVELOPE_PREPARED_ONLY"}
                ),
                flush=True,
            )
        except ValueError as error:
            rejected.append(
                {
                    "asset": row["id"],
                    "status": "REJECTED_SOURCE_ENVELOPE",
                    "reason": str(error),
                }
            )
            print(json.dumps(rejected[-1]), flush=True)
    report = {
        "schema_version": 1,
        "repair_schema": "PCG365_SOURCE_TOP_ENVELOPE_V1",
        "variants": results,
        "rejected": rejected,
        "requested_assets": len(rows),
        "placement": False,
        "qualified_assets": [],
        "parent_catalog_sha256": args.expected_catalog_sha256,
        "source_modified": False,
        "native_qualification": "NOT_RUN",
        "performance_pass": False,
        "script_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
    }
    (output / "rock-collection-catalog.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "SOURCE_ENVELOPE_PREPARED_ONLY",
                "prepared": len(results),
                "rejected": len(rejected),
            }
        )
    )


if __name__ == "__main__":
    main()
