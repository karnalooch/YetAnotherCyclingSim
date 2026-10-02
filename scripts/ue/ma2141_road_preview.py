"""Bounded inferred pavement trial using the established Geometry Script path."""

import json
from pathlib import Path
import sys
import unreal

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.geometry.smooth_road_ribbon import build_smooth_road_ribbon
from scripts.worldgen.bob_terrain_fit_inspector import inspect_terrain_fit
from scripts.ue.bob_cut_only_preview import spawn_cut_only_preview


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
    profile = json.loads(
        (root / "ma2141-profile-candidate.json").read_text(encoding="utf-8")
    )
    if profile.get("exact_sha") != exact_sha:
        raise RuntimeError("Smooth road profile candidate SHA mismatch")
    smooth_vertices, smooth_triangles, smooth_meta = build_smooth_road_ribbon(
        profile
    )

    policy = json.loads(
        (ROOT / "worldgen/terrain/adaptive_terrain_policy.json").read_text(
            encoding="utf-8"
        )
    )
    structure_threshold_m = float(
        policy["thresholds"]["retaining_cut_fill_m"]
    )
    fit_samples = []
    smooth_top_count = int(smooth_meta["top_vertex_count"])
    section_points = int(smooth_meta["cross_section_point_count"])
    profile_rows = profile["stations"]
    if smooth_top_count != len(profile_rows) * section_points:
        raise RuntimeError("Smooth ribbon/profile sample count mismatch")

    for sample_index, point in enumerate(smooth_vertices[:smooth_top_count]):
        x_m, y_m, road_z_m = [float(value) for value in point]
        x_cm, y_cm, road_z_cm = (
            x_m * 100.0,
            y_m * 100.0,
            road_z_m * 100.0,
        )
        hit = unreal.SystemLibrary.line_trace_single(
            world,
            unreal.Vector(x_cm, y_cm, road_z_cm + 10000.0),
            unreal.Vector(x_cm, y_cm, road_z_cm - 10000.0),
            unreal.TraceTypeQuery.ECC_VISIBILITY,
            True,
            [],
            unreal.DrawDebugTrace.NONE,
            True,
        )
        values = () if hit is None else hit.to_tuple()
        candidates = [
            float(value.z) / 100.0
            for value in values
            if all(hasattr(value, key) for key in ("x", "y", "z"))
            and abs(float(value.x) - x_cm) < 0.1
            and abs(float(value.y) - y_cm) < 0.1
            and abs(float(value.z) - road_z_cm) < 9999.0
        ]
        station_index = sample_index // section_points
        lateral_index = sample_index % section_points
        row = profile_rows[station_index]
        fit_samples.append(
            {
                "station_m": float(row["station_m"]),
                "lateral_m": float(row["lateral_m"][lateral_index]),
                "local_xy_m": [x_m, y_m],
                "road_surface_z_m": road_z_m,
                "landscape_z_m": candidates[0] if candidates else None,
            }
        )

    terrain_fit = inspect_terrain_fit(
        fit_samples,
        exact_sha=exact_sha,
        contact_band_max_m=float(trial["pavement_thickness_m"]),
        structure_review_threshold_m=structure_threshold_m,
    )
    (root / "ma2141-road-terrain-fit-proof.json").write_text(
        json.dumps(terrain_fit, indent=2) + "\n",
        encoding="utf-8",
    )

    cut_actor, cut_material, cut_report = spawn_cut_only_preview(
        world,
        root,
        exact_sha,
        profile,
        smooth_vertices,
        smooth_meta,
        terrain_fit,
    )

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
        "visible_road_mesh_role": smooth_meta["role"],
        "contact_mesh_visible": False,
        "smooth_presentation": smooth_meta,
        "terrain_fit": {
            "status": terrain_fit["status"],
            "inspection_complete": terrain_fit["inspection_complete"],
            "sample_count": terrain_fit["sample_count"],
            "trace_miss_count": terrain_fit["trace_miss_count"],
            "class_counts": terrain_fit["class_counts"],
            "max_cut_required_m": terrain_fit["max_cut_required_m"],
            "max_fill_required_m": terrain_fit["max_fill_required_m"],
            "max_required_adjustment_m": terrain_fit[
                "max_required_adjustment_m"
            ],
            "geometry_inspection_view": terrain_fit[
                "geometry_inspection_view"
            ],
            "earthworks_authoring_permitted": terrain_fit[
                "earthworks_authoring_permitted"
            ],
        },
        "terrain_fit_proof": "ma2141-road-terrain-fit-proof.json",
        "bob_cut_only_preview": {
            "status": cut_report["status"],
            "mode": cut_report["mode"],
            "cut_grid_sample_count": cut_report["cut_grid_sample_count"],
            "raised_grid_sample_count": cut_report["raised_grid_sample_count"],
            "max_cut_depth_m": cut_report["max_cut_depth_m"],
            "remaining_road_penetration_count": cut_report[
                "remaining_road_penetration_count"
            ],
            "hidden_landscape_component_count": cut_report[
                "hidden_landscape_component_count"
            ],
            "saved_baseline_unchanged": cut_report[
                "saved_baseline_unchanged"
            ],
            "production_authoring_permitted": cut_report[
                "production_authoring_permitted"
            ],
        },
        "bob_cut_only_preview_proof": "bob-cut-only-preview-proof.json",
        "attribution": trial["attribution"],
    }
    sys.path.insert(0, str(Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))))
    from scripts.worldgen.adaptive_terrain_solver import review_pavement_contact_trial
    report["bob_review"] = review_pavement_contact_trial(
        trial["contact_diagnostic"], geographic_width_admitted=False, native_contact=report)
    (root / "ma2141-road-contact-proof.json").write_text(
        json.dumps(report, indent=2)+"\n", encoding="utf-8")
    actor, material = spawn_pavement_mesh(
        world,
        smooth_vertices,
        smooth_triangles,
        "Ma-2141 smooth asphalt ribbon — inspector preview only",
    )
    return actor, material, report, cut_actor, cut_material, cut_report


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
