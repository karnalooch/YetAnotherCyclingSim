"""Bounded source recuts; ideal-plane sampled diagnostics never admit UE placement.

Runs only in pinned background Blender 4.5.9. Original FBX bytes and wholly
upper triangle/UV/material/smoothing identity are preserved. Fixed repair cuts
are relative to the already derived source height, not the original scan cut
contract. No terrain, native session, GPU, material or contact-policy mutation.
"""

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

CUT_FRACTIONS = (0.20, 0.35, 0.50, 0.65)
SCHEMA = "PCG365_SOURCE_RECUT_SUPPORT_V1"
ROOT = Path("D:/yacs/work/pcg365")
FAMILIES = {
    *("namaqualand_boulder_0" + str(i) for i in range(2, 7)),
    "rock_07",
    "rock_09",
    "boulder_01",
}


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


def asset_module(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).parents[1] / "assets" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_catalog(data):
    require(
        data.get("schema_version") == 1 and type(data.get("schema_version")) is int,
        "Schema1 source catalog required",
    )
    require(
        data.get("placement") is False and data.get("qualified_assets") == [],
        "Source catalog cannot admit placement",
    )
    rows = data.get("variants")
    require(
        isinstance(rows, list) and len(rows) == 20,
        "Exactly twenty source derivatives required",
    )
    ids = set()
    for row in rows:
        ident = row.get("id")
        require(
            isinstance(ident, str)
            and re.fullmatch(
                r"(?:namaqualand_boulder_0[2-6]|rock_0[79]|boulder_01)_0[1-3]", ident
            )
            and ident not in ids,
            "Invalid or duplicate source ID",
        )
        ids.add(ident)
        require(
            row.get("source_id", ident.rsplit("_", 1)[0]) == ident.rsplit("_", 1)[0],
            "Source family mismatch",
        )
        require(
            row.get("license") == "CC0-1.0", "Pinned licensed scan lineage required"
        )
        require(
            isinstance(row.get("sha256"), str)
            and re.fullmatch("[0-9a-f]{64}", row["sha256"]),
            "Invalid source hash",
        )
        require(
            type(row.get("bytes")) is int and row["bytes"] > 0, "Invalid source size"
        )
        require(
            row.get("placement") is False and row.get("qualified_assets") == [],
            "Source derivative cannot admit placement",
        )
    require(
        {i.rsplit("_", 1)[0] for i in ids} == FAMILIES,
        "Exactly eight source families required",
    )
    return sorted(rows, key=lambda r: r["id"])


def evaluate_ideal_plane(coarse, fine, height_cm, policy_module, support_module):
    """Use unchanged V1 against local BVH intervals; no native authenticity claim."""
    measurements = []
    for count, intervals in ((33, coarse), (65, fine)):
        require(intervals, "No projected footprint samples")
        fit = support_module.solve_support(intervals)
        fit["max_positive_bottom_gap_cm"] = max(
            0.0, max(s["bottom_gap_cm"] for s in fit["samples"])
        )
        measurements.append((count, fit))
    measurement = {
        "height_cm": height_cm,
        "uniform_scale": 1.0,
        "yaw_deg": 0.0,
        "tilt_deg": 0.0,
        "max_local_slope_deg": 0.0,
        "sample_count": len(fine),
        "valid_ground_count": len(fine),
        "coverage_status": "COMPLETE_SAMPLED_MESH_FOOTPRINT",
        # Policy input shape only: this is an ideal analytical plane, NOT a hit.
        "ground_class": "LandscapeHeightfieldCollisionComponent",
        "fit": measurements[1][1],
        "refinement": {
            "coarse_grid": 33,
            "fine_grid": 65,
            "coarse_root_cm": measurements[0][1]["root_zero_sampled_air_cm"],
            "fine_root_cm": measurements[1][1]["root_zero_sampled_air_cm"],
            "coarse_embedding_cm": measurements[0][1]["required_embedding_cm"],
            "fine_embedding_cm": measurements[1][1]["required_embedding_cm"],
        },
    }
    decision = policy_module.evaluate(measurement, policy_module.trial_policy())
    return {
        "status": "PASS_IDEAL_PLANE_SAMPLED_SOURCE_DIAGNOSTIC_ONLY"
        if decision["status"] == "PASS_SAMPLED_CONTACT_ONLY"
        else "REJECTED_SOURCE_DIAGNOSTIC",
        "actual_ground_kind": "ANALYTICAL_LOCAL_Z0_PLANE_NOT_LANDSCAPE",
        "policy_adapter_ground_class_is_not_a_measured_native_hit": True,
        "policy_decision_for_synthetic_plane": decision,
        "coarse_sample_count": len(coarse),
        "fine_sample_count": len(fine),
        "height_cm": height_cm,
        "refinement": measurement["refinement"],
        "fine_fit": {k: v for k, v in measurement["fit"].items() if k != "samples"},
        "native_qualification": False,
        "continuous_support_verified": False,
        "placement": False,
    }


def sample_bvh(bm, bounds, grid):
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    tree = BVHTree.FromBMesh(bm, epsilon=0.0)
    low, high = bounds["min"], bounds["max"]
    span = max(bounds["dimensions"])
    start, end = low[2] - span, high[2] + span
    result = []
    for i in range(grid):
        for j in range(grid):
            x = low[0] + (i + 0.5) * bounds["dimensions"][0] / grid
            y = low[1] + (j + 0.5) * bounds["dimensions"][1] / grid
            bottom = tree.ray_cast(
                Vector((x, y, start)), Vector((0, 0, 1)), end - start
            )[0]
            top = tree.ray_cast(Vector((x, y, end)), Vector((0, 0, -1)), end - start)[0]
            require(
                (bottom is None) == (top is None),
                "Unpaired full-footprint source BVH interval",
            )
            if bottom is not None:
                require(bottom.z <= top.z, "Inverted source BVH interval")
                result.append(
                    {
                        "bottom_z_cm": bottom.z * 100,
                        "top_z_cm": top.z * 100,
                        "ground_z_cm": 0.0,
                    }
                )
    return result


def repair_candidate(original, cut_fraction, base, natural):
    import bmesh
    from mathutils import Vector

    bm = original.copy()
    try:
        bounds = base.dimensions(original)
        # BMesh stores float32 coordinates. Freeze the actual native plane
        # before taking the upper witness, as in the original source producer.
        cut = Vector(
            (0, 0, bounds["min"][2] + cut_fraction * bounds["dimensions"][2])
        ).z
        witness = natural.upper_witness(original, cut)
        require(witness, "No wholly upper source triangles")
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
        require(
            natural.upper_witness(bm, cut) == witness,
            "Recut changed wholly upper coordinates/UV/material/smoothing",
        )
        boundary = [e for e in bm.edges if e.is_boundary]
        require(boundary, "Recut has no boundary")
        require(
            max(abs(v.co.z - cut) for e in boundary for v in e.verts) < 1e-6,
            "Boundary exceeds existing1um plane guard",
        )
        for vertex in {v for e in boundary for v in e.verts}:
            vertex.co.z = cut
        loops, records = base.ordered_boundary_loops(boundary)
        prior = set(bm.faces)
        bmesh.ops.triangle_fill(
            bm,
            edges=boundary,
            normal=Vector((0, 0, -1)),
            use_beauty=False,
            use_dissolve=False,
        )
        cap = [f for f in bm.faces if f not in prior]
        require(cap, "Stock recut cap failed")
        for face in cap:
            face.smooth = False
            face.material_index = max(f.material_index for f in original.faces)
        cap_validation = base.validate_holed_cap(cap, records)
        bm.normal_update()
        require(all(f.normal.z < 0 for f in cap), "Recut cap winding invalid")
        polygons = [f for f in bm.faces if len(f.verts) > 3]
        if polygons:
            bmesh.ops.triangulate(
                bm, faces=polygons, quad_method="FIXED", ngon_method="EAR_CLIP"
            )
        require(
            natural.upper_witness(bm, cut) == witness,
            "Cap changed upper source witness",
        )
        topology = base.topology(bm)
        for vertex in bm.verts:
            vertex.co.z -= cut
        result_bounds = base.dimensions(bm)
        require(abs(result_bounds["min"][2]) <= 1e-6, "Recut base translation invalid")
        original_volume = base.topology(original)["volume_m3"]
        removed = original_volume - topology["volume_m3"]
        require(
            0 <= removed <= original_volume,
            "Source-only cut added volume or exceeded source",
        )
        report = {
            "cut_fraction_of_derived_source_height": cut_fraction,
            "cut_source_z_m": cut,
            "base_translation_m": [0, 0, -cut],
            "upper_preserved_before_translation": True,
            "preserved_upper_triangle_count": sum(witness.values()),
            "preserved_upper_coordinates_uv_material_smooth_sha256": hashlib.sha256(
                repr(sorted(witness.items())).encode()
            ).hexdigest(),
            "source_volume_m3": original_volume,
            "removed_volume_m3": removed,
            "added_volume_m3": 0.0,
            "removed_volume_fraction": removed / original_volume,
            "volume_bounds": "0<=removed<=source;added==0;closed_positive_derived_volume",
            "topology": topology,
            "bounds_m": result_bounds,
            "cap_validation": cap_validation,
            "cap_xy_loops_m": [{**r, "xy_m": r["xy_m"]} for r in records],
            "com_m": base.center_of_mass(bm),
        }
        return bm, report
    except Exception:
        bm.free()
        raise


def produce(row, output, base, natural, policy, support):
    import bmesh
    import bpy

    source = Path(row["source"]).resolve(strict=True)
    require(
        source.is_relative_to(ROOT.resolve(strict=True))
        and source.suffix.lower() == ".fbx",
        "Source escaped local retained pcg365 assets",
    )
    require(
        sha(source) == row["sha256"] and source.stat().st_size == row["bytes"],
        "Source FBX identity drift",
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
        "Source FBX import failed",
    )
    imported = set(bpy.data.objects) - existing
    bm = bmesh.new()
    attempts = []
    try:
        meshes = [o for o in imported if o.type == "MESH"]
        require(len(meshes) == 1, "Exactly one prepared source object required")
        obj = meshes[0]
        require(
            not obj.modifiers
            and obj.animation_data is None
            and obj.data.shape_keys is None,
            "Source deformation unsupported",
        )
        matrix = obj.matrix_world.copy()
        require(
            all(math.isfinite(v) for r in matrix for v in r)
            and list(matrix[3]) == [0.0, 0.0, 0.0, 1.0]
            and matrix.to_3x3().determinant() > 0,
            "Invalid source matrix",
        )
        triangular = natural.materialize_render_triangles(obj.data, bpy)
        bm.from_mesh(triangular)
        for vertex in bm.verts:
            vertex.co = matrix @ vertex.co
        bm.normal_update()
        base.topology(bm)
        bounds = base.dimensions(bm)
        expected = row["expected_native_bounds_cm"]
        native = {
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
        }
        require(
            all(
                abs(a - b) <= 0.01
                for k in ("min", "max")
                for a, b in zip(native[k], expected[k])
            ),
            "Prepared source FBX bounds differ from pinned producer",
        )
        for fraction in CUT_FRACTIONS:
            candidate = None
            try:
                candidate, report = repair_candidate(bm, fraction, base, natural)
                b = report["bounds_m"]
                diagnostic = evaluate_ideal_plane(
                    sample_bvh(candidate, b, 33),
                    sample_bvh(candidate, b, 65),
                    b["dimensions"][2] * 100,
                    policy,
                    support,
                )
                attempts.append(
                    {
                        "cut_fraction": fraction,
                        "repair": report,
                        "diagnostic": diagnostic,
                    }
                )
                if (
                    diagnostic["status"]
                    != "PASS_IDEAL_PLANE_SAMPLED_SOURCE_DIAGNOSTIC_ONLY"
                ):
                    continue
                name = row["id"]
                mesh = bpy.data.meshes.new(name + "_RepairedSupport")
                for material in obj.data.materials:
                    mesh.materials.append(material)
                candidate.to_mesh(mesh)
                mesh.update()
                readback = bmesh.new()
                try:
                    readback.from_mesh(mesh)
                    require(
                        natural.upper_witness(readback, 0.0)
                        == natural.upper_witness(candidate, 0.0),
                        "Prepared output readback changed upper witness",
                    )
                    base.topology(readback)
                finally:
                    readback.free()
                result = bpy.data.objects.new(name, mesh)
                bpy.context.collection.objects.link(result)
                imported.add(result)
                bpy.ops.object.select_all(action="DESELECT")
                result.select_set(True)
                bpy.context.view_layer.objects.active = result
                target = output / (name + ".fbx")
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
                    "Repair FBX export failed",
                )
                return {
                    "id": row["id"],
                    "source_id": row["source_id"],
                    "license": row["license"],
                    "original_source_sha256": row.get(
                        "original_source_sha256", row["base_source_sha256"]
                    ),
                    "source": str(target),
                    "source_relative": "rock-collection/" + target.name,
                    "sha256": sha(target),
                    "bytes": target.stat().st_size,
                    "base_source_sha256": row["sha256"],
                    "expected_lod0_triangles": report["topology"]["triangles"],
                    "expected_native_bounds_cm": {
                        "min": [
                            b["min"][0] * 100,
                            -b["max"][1] * 100,
                            b["min"][2] * 100,
                        ],
                        "max": [
                            b["max"][0] * 100,
                            -b["min"][1] * 100,
                            b["max"][2] * 100,
                        ],
                    },
                    "bounds_m": b,
                    "com_m": report["com_m"],
                    "cap_xy_loops_m": report["cap_xy_loops_m"],
                    "recipe": {
                        "repair_schema": SCHEMA,
                        "parent_recipe": row.get("recipe"),
                        "parent_source_sha256": row["sha256"],
                        "repair": report,
                        "predeclared_cut_fractions": list(CUT_FRACTIONS),
                    },
                    "repair_attempts": attempts,
                    "source_provenance": "LICENSED_SCAN_DERIVATIVE_SOURCE_ONLY_RECUT",
                    "placement": False,
                    "qualified_assets": [],
                    "native_readback": "NOT_RUN",
                    "source_self_intersection": "UNKNOWN_NOT_TESTED",
                }, attempts
            except ValueError as exc:
                attempts.append(
                    {
                        "cut_fraction": fraction,
                        "status": "REJECTED_SOURCE_REPAIR",
                        "reason": str(exc),
                    }
                )
            finally:
                if candidate is not None:
                    candidate.free()
        return None, attempts
    finally:
        bm.free()
        for obj in imported:
            bpy.data.objects.remove(obj, do_unlink=True)
        require(
            sha(source) == row["sha256"] and source.stat().st_size == row["bytes"],
            "Source bytes changed during repair",
        )


def main():
    import bpy

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--expected-catalog-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--asset")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    require(
        bpy.app.background and bpy.app.version == (4, 5, 9),
        "Pinned background Blender4.5.9 required",
    )
    raw = args.catalog.read_bytes()
    require(
        hashlib.sha256(raw).hexdigest() == args.expected_catalog_sha256,
        "Catalog identity drift",
    )
    rows = validate_catalog(json.loads(raw))
    if args.asset:
        rows = [r for r in rows if r["id"] == args.asset]
        require(len(rows) == 1, "Unknown single-asset identity")
    output = args.output_directory.resolve()
    require(
        output.is_relative_to(ROOT.resolve(strict=True))
        and output != ROOT.resolve()
        and not output.exists(),
        "Fresh bounded repair output required",
    )
    base = sibling("prepare_pcg365_large_scan_bases")
    natural = sibling("build_pcg365_natural_rock_collection")
    policy = asset_module("pcg_rock_contact_policy")
    support = asset_module("pcg_boulder_support")
    output.mkdir(parents=True, exist_ok=False)
    derived = output / "rock-collection"
    derived.mkdir()
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    variants, rejected = [], []
    for row in rows:
        try:
            result, attempts = produce(row, derived, base, natural, policy, support)
            if result is None:
                rejected.append(
                    {
                        "id": row["id"],
                        "status": "REJECTED_ALL_PREDECLARED_RECUTS",
                        "attempts": attempts,
                    }
                )
            else:
                variants.append(result)
        except ValueError as exc:
            rejected.append(
                {
                    "id": row["id"],
                    "status": "REJECTED_SOURCE_AUTHENTICATION",
                    "reason": str(exc),
                }
            )
    require(args.catalog.read_bytes() == raw, "Catalog changed during repair")
    report = {
        "schema_version": 1,
        "repair_schema": SCHEMA,
        "issue": 365,
        "status": "SOURCE_RECUT_IDEAL_PLANE_DIAGNOSTIC_ONLY",
        "variants": variants,
        "rejected": rejected,
        "requested_assets": len(rows),
        "variant_count": len(variants),
        "source_family_count": len({r["source_id"] for r in variants}),
        "parent_catalog_sha256": args.expected_catalog_sha256,
        "predeclared_cut_fractions": list(CUT_FRACTIONS),
        "script_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "helper_sha256": {
            m.__name__: sha(m.__file__) for m in (base, natural, policy, support)
        },
        "source_modified": False,
        "terrain_modified": False,
        "placement": False,
        "qualified_assets": [],
        "native_unreal_execution": "NOT_RUN",
        "full_qualification": False,
        "continuous_support_verified": False,
        "performance_pass": False,
        "performance_status": "DEFERRED_AFTER_M3",
        "limits": "Ideal plane BVH preflight only; native contact, source intersections, regional domains and visual review unverified",
    }
    with (output / "rock-collection-catalog.json").open(
        "x", encoding="utf-8"
    ) as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "prepared": len(variants),
                "rejected": len(rejected),
            }
        )
    )


if __name__ == "__main__":
    main()
