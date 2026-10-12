"""Independent Blender first-hit witness for retained Rock07/09 point-3 rays.

--manifest is the corrected lod0-source-report.json; --native-receipt is the
retained rock-qualify-receipt.json. No geometry edits, asset saves or admission.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(path):
    return {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--native-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    require(
        bpy.app.background and bpy.app.version == (4, 5, 9), "Pinned Blender required"
    )
    output = args.output.resolve()
    require(
        output.is_relative_to(Path("D:/yacs/work/pcg365").resolve())
        and output.parent.is_dir()
        and not output.exists(),
        "Fresh work output required",
    )
    manifest_identity, native_identity = (
        identity(args.manifest),
        identity(args.native_receipt),
    )
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    native = json.loads(args.native_receipt.read_text(encoding="utf-8"))
    require(
        {a["id"] for a in manifest["assets"]} == {"rock_07", "rock_09"},
        "Unexpected assets",
    )
    settings = dict(
        global_scale=1.0,
        use_manual_orientation=False,
        bake_space_transform=False,
        use_anim=False,
        use_image_search=False,
        use_custom_normals=True,
    )
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    results = []
    for asset in manifest["assets"]:
        source = asset["derived_lod0_fbx"]
        path = Path(source["path"]).resolve(strict=True)
        require(
            path.is_relative_to(Path("D:/yacs/work/pcg365").resolve()),
            "Unexpected source root",
        )
        before = identity(path)
        require(before["sha256"] == source["sha256"], "Source hash mismatch")
        mesh_receipts = [m for m in native["meshes"] if m["id"] == asset["id"]]
        require(len(mesh_receipts) == 1, "Ambiguous native mesh")
        mesh_receipt = mesh_receipts[0]
        require(
            mesh_receipt["source"]["sha256"] == before["sha256"],
            "Native source mismatch",
        )
        objects_before = set(bpy.data.objects)
        require(
            bpy.ops.import_scene.fbx(filepath=str(path), **settings) == {"FINISHED"},
            "Import failed",
        )
        imported = set(bpy.data.objects) - objects_before
        objects = [o for o in imported if o.type == "MESH"]
        require(len(objects) == 1, "Exactly one source mesh required")
        obj = objects[0]
        mesh = obj.data
        mesh.calc_loop_triangles()
        triangles = [tuple(t.vertices) for t in mesh.loop_triangles]
        require(
            len(triangles) == mesh_receipt["lod0_render_triangles"],
            "Triangle count mismatch",
        )
        points_m = [obj.matrix_world @ v.co for v in mesh.vertices]
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.transform(obj.matrix_world)
        topology = {
            "boundary_edges": sum(e.is_boundary for e in bm.edges),
            "nonmanifold_edges": sum(not e.is_manifold for e in bm.edges),
            "inconsistent_winding_edges": sum(
                e.is_manifold and not e.is_contiguous for e in bm.edges
            ),
            "signed_volume_m3": bm.calc_volume(signed=True),
        }
        bm.free()
        # Reflection matches UE FbxConvert.h; winding checks above use original space.
        points = [Vector((p.x * 100, -p.y * 100, p.z * 100)) for p in points_m]
        tree = BVHTree.FromPolygons(points, triangles, all_triangles=True, epsilon=0.0)
        bounds = mesh_receipt["bounds_cm"]
        low = bounds["origin"][2] - bounds["extent"][2] - 100.0
        high = bounds["origin"][2] + bounds["extent"][2] + 100.0
        cases = [
            c
            for c in native["cases"]
            if c["mesh_id"] == asset["id"] and c["point_index"] == 3
        ]
        require(len(cases) == 1, "Ambiguous point 3")
        grids = [g for g in cases[0]["grids"] if g["grid_size"] == 65]
        require(len(grids) == 1, "Ambiguous grid 65")
        raw_ref = grids[0]["raw_samples"]
        raw_path = args.native_receipt.parent / raw_ref["path"]
        require(
            raw_path.resolve().parent == args.native_receipt.resolve().parent,
            "Raw path escaped",
        )
        raw_identity = identity(raw_path)
        require(
            raw_identity["sha256"] == raw_ref["sha256"], "Raw samples hash mismatch"
        )
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        witnesses, errors, disagreements = [], [], []
        for row in raw["support_rows"] + raw["rejected_rows"]:
            x, y = row["local_xy_cm"]
            hits = []
            for start, direction in ((low, 1), (high, -1)):
                location, normal, face, distance = tree.ray_cast(
                    Vector((x, y, start)), Vector((0, 0, direction)), high - low
                )
                hits.append(
                    None
                    if location is None
                    else {
                        "z_cm": location.z,
                        "normal": list(normal),
                        "triangle_index": face,
                        "distance_cm": distance,
                    }
                )
            expected_pair = "bottom_z_cm" in row
            if expected_pair and all(h is not None for h in hits):
                pair_errors = [
                    abs(hits[i]["z_cm"] - row[key])
                    for i, key in enumerate(("bottom_z_cm", "top_z_cm"))
                ]
                errors.extend(pair_errors)
                witnesses.append(
                    {
                        "local_xy_cm": [x, y],
                        "native_z_cm": [row["bottom_z_cm"], row["top_z_cm"]],
                        "source_hits": hits,
                        "absolute_errors_cm": pair_errors,
                    }
                )
            elif not (row.get("status") == "PAIRED_MESH_MISS" and hits == [None, None]):
                disagreements.append({"native": row, "source_hits": hits})
        sorted_errors = sorted(errors)
        require(sorted_errors, "No comparable source rays")
        topology_ok = (
            not any(
                topology[k]
                for k in (
                    "boundary_edges",
                    "nonmanifold_edges",
                    "inconsistent_winding_edges",
                )
            )
            and topology["signed_volume_m3"] > 0
        )
        after = identity(path)
        require(before == after, "Source changed")
        results.append(
            {
                "id": asset["id"],
                "source_before": before,
                "source_after": after,
                "raw_samples": raw_identity,
                "triangles": len(triangles),
                "topology": topology,
                "topology_consistent_closed_positive_volume": topology_ok,
                "pair_disagreement_count": len(disagreements),
                "pair_disagreements": disagreements,
                "status": "REJECTED_PAIR_OR_TOPOLOGY"
                if disagreements or not topology_ok
                else "MEASURED_NO_ERROR_THRESHOLD_APPLIED",
                "error_distribution_cm": {
                    "min": sorted_errors[0],
                    "median": sorted_errors[len(sorted_errors) // 2],
                    "p95": sorted_errors[int(0.95 * (len(sorted_errors) - 1))],
                    "max": sorted_errors[-1],
                },
                "maximum_error_witness": max(
                    witnesses, key=lambda w: max(w["absolute_errors_cm"])
                ),
                "bottom_extreme_witness": max(
                    witnesses, key=lambda w: w["source_hits"][0]["z_cm"]
                ),
                "ray_witnesses": witnesses,
            }
        )
        for item in imported:
            bpy.data.objects.remove(item, do_unlink=True)
    require(
        identity(args.manifest) == manifest_identity
        and identity(args.native_receipt) == native_identity,
        "Input changed",
    )
    report = {
        "schema_version": 1,
        "blender_version": bpy.app.version_string,
        "manifest": manifest_identity,
        "native_receipt": native_identity,
        "producer": identity(Path(__file__)),
        "import_settings": settings,
        "coordinate_mapping": "UE cm = Blender world metres [x,-y,z]*100",
        "results": results,
        "placement": False,
        "qualified_assets": [],
        "limitations": "Finite first-hit parity only; no self-intersection, continuous support, visual or production admission proof",
    }
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"output": identity(output), "status": "MEASURED_ONLY"}))


if __name__ == "__main__":
    main()
