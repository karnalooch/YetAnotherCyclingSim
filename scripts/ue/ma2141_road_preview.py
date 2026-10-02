"""Bounded inferred pavement trial using the established Geometry Script path."""

import json
from pathlib import Path
import sys
import unreal


def spawn_trial(world, root, exact_sha):
    trial = json.loads((root / "ma2141-road-preview.json").read_text(encoding="utf-8"))
    if (trial["exact_sha"] != exact_sha or trial["region_id"] != "sa_calobra"
            or trial["status"] != "INFERRED_CONTACT_TRIAL"
            or trial["authoritative_physics"] or trial["authoritative_route_geometry"]
            or trial["geographic_width_admitted"] or trial["earthworks_authored"]):
        raise RuntimeError("Road preview identity/authority mismatch")
    vertices = trial["vertices_local_m"]
    triangles = trial["triangles"]
    topology = trial["native_mesh"]
    top_count = topology["top_vertex_count"]
    face_count = topology["top_triangle_count"]
    if (not 1000 <= top_count <= 30000 or not 1000 <= face_count <= 60000
            or len(vertices) != top_count*2 or not face_count*2 <= len(triangles) <= 150000
            or topology["native_diagonal"] != "a_d" or topology["native_cell_size_m"] != 0.5):
        raise RuntimeError("Unexpected bounded pavement mesh topology")
    # Sample each transverse vertex before spawning the road, so the trace cannot
    # accidentally hit the road itself and declare a floating surface supported.
    deltas = []
    misses = []
    diagonal_errors = [[], []]
    worst = []
    samples = list(vertices[:top_count])
    samples.extend([[sum(vertices[i][axis] for i in face)/3 for axis in range(3)]
                    for face in triangles[:face_count]])
    for i,point in enumerate(samples):
        x,y,z = [v*100 for v in point]
        hit = unreal.SystemLibrary.line_trace_single(
            world, unreal.Vector(x,y,z+10000), unreal.Vector(x,y,z-10000),
            unreal.TraceTypeQuery.ECC_VISIBILITY, True, [], unreal.DrawDebugTrace.NONE, True)
        values = () if hit is None else hit.to_tuple()
        candidates = [float(v.z) for v in values
                      if all(hasattr(v,k) for k in ("x","y","z"))
                      and abs(float(v.x)-x) < 0.1 and abs(float(v.y)-y) < 0.1
                      and abs(float(v.z)-z) < 9999]
        if not candidates:
            misses.append(i)
        else:
            deltas.append((z-candidates[0])/100)
            ground_m = candidates[0]/100
            if i < top_count:
                for j in range(2):
                    diagonal_errors[j].append(abs(trial["native_triangle_candidates_m"][i][j]-ground_m))
            worst.append({"sample_index": i, "sample_kind": "vertex" if i<top_count else "centroid",
                          "local_xy_m": point[:2], "surface_minus_landscape_m": deltas[-1]})
    report = {
        "schema_version": 1, "exact_sha": exact_sha,
        "region_id": "sa_calobra", "status": "INFERRED_CONTACT_TRIAL",
        "trace_sample_count": len(deltas), "trace_miss_count": len(misses),
        "requested_vertex_trace_count": top_count,
        "requested_centroid_trace_count": face_count,
        "native_mesh": topology,
        "missing_sample_indices": misses[:50],
        "triangle_diagonal_comparison": {
            name: {"max_abs_error_m": max(errors) if errors else None,
                   "mean_abs_error_m": sum(errors)/len(errors) if errors else None}
            for name,errors in zip(("a_d", "b_c"),diagonal_errors)},
        "worst_native_samples": sorted(worst, key=lambda p: abs(p["surface_minus_landscape_m"]-0.04), reverse=True)[:30],
        "surface_minus_landscape_min_m": min(deltas) if deltas else None,
        "surface_minus_landscape_max_m": max(deltas) if deltas else None,
        "floating_sample_count": sum(d > trial["pavement_thickness_m"] for d in deltas),
        "penetrating_sample_count": sum(d < 0 for d in deltas),
        "native_sample_contact_status": "PASS" if not misses and all(
            0 <= d <= trial["pavement_thickness_m"] for d in deltas) else "FAIL",
        "r16_centroid_contact": trial["contact_diagnostic"],
        "continuous_contact_status": "NOT_PROVEN",
        "road_collision_status": "NOT_PROVEN", "human_visual_status": "PENDING",
        "performance_status": "PENDING", "final_road_status": "NOT_ADMITTED",
        "terrain_modified": False, "road_earthworks_modified": False,
        "attribution": trial["attribution"],
    }
    sys.path.insert(0, str(Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))))
    from scripts.worldgen.adaptive_terrain_solver import review_pavement_contact_trial
    report["bob_review"] = review_pavement_contact_trial(
        trial["contact_diagnostic"], geographic_width_admitted=False, native_contact=report)
    (root / "ma2141-road-contact-proof.json").write_text(
        json.dumps(report, indent=2)+"\n", encoding="utf-8")
    actor, material = spawn_pavement_mesh(world, vertices, triangles,
        "Ma-2141 inferred pavement contact trial — not admitted")
    return actor, material, report


def spawn_pavement_mesh(world, vertices, triangles, label):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = actors.spawn_actor_from_class(unreal.DynamicMeshActor, unreal.Vector(),
                                          unreal.Rotator(), transient=True)
    actor.set_actor_label(label)
    component = actor.get_dynamic_mesh_component()
    mesh = component.get_dynamic_mesh()
    buffers = unreal.GeometryScriptSimpleMeshBuffers()
    buffers.set_editor_property("vertices", [unreal.Vector(*[v*100 for v in p]) for p in vertices])
    buffers.set_editor_property("triangles", [unreal.IntVector(*t) for t in triangles])
    mesh.reset()
    mesh.append_buffers_to_mesh(buffers, material_id=0, defer_change_notifications=True)
    mesh.recompute_normals(unreal.GeometryScriptCalculateNormalsOptions(),
                           defer_change_notifications=True)
    component.notify_mesh_modified()
    if mesh.get_vertex_count() != len(vertices) or mesh.get_triangle_count() != len(triangles):
        raise RuntimeError("Unreal pavement mesh differs from the prepared trial")
    parent = unreal.load_asset("/Engine/BasicShapes/BasicShapeMaterial")
    material = unreal.MaterialLibrary.create_dynamic_material_instance(world, parent)
    material.set_vector_parameter_value("Color", unreal.LinearColor(0.035,0.035,0.035,1))
    component.set_material(0, material)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    # Keep UObject references alive until screenshots complete.
    return actor, material
