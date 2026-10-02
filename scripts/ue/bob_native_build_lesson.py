"""Execute one transient native-spline lesson and measure before/after support."""

import hashlib
import json
import math
from pathlib import Path
import unreal


def ground(world, x, y, z):
    hit = unreal.SystemLibrary.line_trace_single(
        world,
        unreal.Vector(x * 100, y * 100, (z + 100) * 100),
        unreal.Vector(x * 100, y * 100, (z - 100) * 100),
        unreal.TraceTypeQuery.ECC_VISIBILITY,
        True,
        [],
        unreal.DrawDebugTrace.NONE,
        True,
    )
    values = () if hit is None else hit.to_tuple()
    candidates = [
        float(v.z) / 100
        for v in values
        if all(hasattr(v, k) for k in ("x", "y", "z"))
        and abs(float(v.x) / 100 - x) < 0.001
        and abs(float(v.y) / 100 - y) < 0.001
        and abs(float(v.z) / 100 - z) < 99.99
    ]
    if not candidates:
        raise RuntimeError("Lesson Landscape trace missed")
    return candidates[0]


def execute(world, root, exact_sha):
    from ma2141_road_preview import spawn_pavement_mesh

    plan = json.loads((root / "bob-build-lesson.json").read_text())
    if (
        plan["exact_sha"] != exact_sha
        or plan["recipe_id"] != "bob-native-spline-minor-adjustment-v1"
        or plan["station_range_m"] != [70.0, 90.0]
        or plan["layer"] != "Road_Earthworks"
        or plan["status"] != "EXPERIMENTAL_LESSON_ONLY"
        or plan["save_map"]
        or plan["eligible_for_learning"]
        or plan["production_authoring_permitted"]
    ):
        raise RuntimeError("Unadmitted lesson contract")
    landscapes = list(
        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    )
    if len(landscapes) != 1:
        raise RuntimeError("Expected one Landscape")
    landscape = landscapes[0]
    layers = [str(layer.get_name_bp()) for layer in landscape.get_edit_layers_bp()]
    if layers.count("Base_DTM") != 1 or layers.count("Road_Earthworks") != 1:
        raise RuntimeError("Ambiguous semantic layer ownership")
    project = Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    )
    asset = project / "Content/Worlds/SaCalobra/L_SaCalobraTerrainBaseline.umap"
    baseline_hash = hashlib.sha256(asset.read_bytes()).hexdigest()
    rows = plan["points"]
    samples = [
        [*xy, z] for row in rows for xy, z in zip(row["xy_m"], row["target_ground_m"])
    ]
    before = [ground(world, *p) for p in samples]
    xs = [p[0] for p in samples]
    ys = [p[1] for p in samples]
    z = rows[20]["center_m"][2]
    guard = []
    for i in range(21):
        t = i / 20
        x = min(xs) - 4 + (max(xs) - min(xs) + 8) * t
        y = min(ys) - 4 + (max(ys) - min(ys) + 8) * t
        guard.extend(
            [
                [x, min(ys) - 4, z],
                [x, max(ys) + 4, z],
                [min(xs) - 4, y, z],
                [max(xs) + 4, y, z],
            ]
        )
    guard_before = [ground(world, *p) for p in guard]
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    holder = actors.spawn_actor_from_class(
        unreal.Actor, unreal.Vector(), unreal.Rotator(), transient=True
    )
    holder.set_actor_label("BOB experimental spline lesson — unsaved")
    spline = unreal.SplineComponent(outer=holder)
    spline.clear_spline_points(False)
    for i, row in enumerate(rows):
        spline.add_spline_point(
            unreal.Vector(*[v * 100 for v in row["center_m"]]),
            unreal.SplineCoordinateSpace.WORLD,
            False,
        )
        spline.set_spline_point_type(i, unreal.SplinePointType.CURVE_CLAMPED, False)
    spline.set_closed_loop(False, False)
    spline.update_spline()
    width = max(r["half_width_m"] for r in rows) * 100 + 25
    landscape.editor_apply_spline(
        spline,
        start_width=width,
        end_width=width,
        start_side_falloff=100,
        end_side_falloff=100,
        start_roll=rows[0]["roll_deg"],
        end_roll=rows[-1]["roll_deg"],
        num_subdivisions=256,
        raise_heights=True,
        lower_heights=True,
        paint_layer=None,
        edit_layer_name="Road_Earthworks",
    )
    after = [ground(world, *p) for p in samples]
    guard_after = [ground(world, *p) for p in guard]
    vertices = plan["vertices_local_m"]
    triangles = plan["triangles"]
    n = plan["top_vertex_count"]
    for i in range(n):
        x, y = vertices[i][:2]
        h = ground(world, x, y, z)
        vertices[i][2] = h + 0.04
        vertices[i + n][2] = h - 0.04
    checks = vertices[:n] + [
        [sum(vertices[i][axis] for i in face) / 3 for axis in range(3)]
        for face in triangles[: plan["top_triangle_count"]]
    ]
    gaps = [p[2] - ground(world, *p) for p in checks]
    rms = lambda values: math.sqrt(sum(v * v for v in values) / len(values))
    before_error = rms([p[2] - h for p, h in zip(samples, before)])
    after_error = rms([p[2] - h for p, h in zip(samples, after)])
    guard_change = max(abs(a - b) for a, b in zip(guard_before, guard_after))
    saved_unchanged = baseline_hash == hashlib.sha256(asset.read_bytes()).hexdigest()
    improved = after_error < before_error and after_error <= 0.08
    contact = all(0 <= v <= 0.08 for v in gaps)
    report = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "architect": "BOB",
        "recipe_id": plan["recipe_id"],
        "status": "TECHNICAL_TRIAL_PASS"
        if improved and contact and guard_change <= 0.002 and saved_unchanged
        else "REJECT_LESSON",
        "station_range_m": plan["station_range_m"],
        "api": "LandscapeProxy.editor_apply_spline",
        "selected_layer": "Road_Earthworks",
        "available_layers": layers,
        "execution_scope": "transient editor session; map not saved",
        "saved_baseline_sha256": baseline_hash,
        "saved_baseline_unchanged": saved_unchanged,
        "profile_sample_count": len(samples),
        "profile_error_before_rms_m": before_error,
        "profile_error_after_rms_m": after_error,
        "profile_improved": improved,
        "max_sampled_ground_change_m": max(abs(a - b) for a, b in zip(before, after)),
        "outside_guard_sample_count": len(guard),
        "outside_guard_max_change_m": guard_change,
        "contact_sample_count": len(gaps),
        "floating_count": sum(g > 0.08 for g in gaps),
        "penetrating_count": sum(g < 0 for g in gaps),
        "contact_status": "PASS" if contact else "FAIL",
        "geographic_width_admitted": False,
        "continuous_contact": "NOT_PROVEN",
        "road_collision": "NOT_PROVEN",
        "ride": "NOT_PROVEN",
        "human_visual": "PENDING",
        "eligible_for_learning": False,
        "production_authoring_permitted": False,
        "limitations": [
            "Native spline uses interpolated endpoint roll and constant width.",
            "Outside guard is sampled, not a complete deformation-bound proof.",
            "Base_DTM preservation uses named-layer API and unchanged saved map, not per-layer pixel export.",
            "No retained production geometry or verified recipe admission.",
        ],
    }
    (root / "bob-build-lesson-proof.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    actor, material = spawn_pavement_mesh(
        world, vertices, triangles, "BOB built pavement lesson — not admitted"
    )
    return holder, spline, actor, material, report
