"""BOB transient cut-only local-ground builder for Sa Calobra."""

from __future__ import annotations

import array
import hashlib
import json
from pathlib import Path
import sys

import unreal

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.geometry.bob_cut_only_ground import (
    build_cut_only_corridor,
    sample_regular_grid_height,
)
from scripts.geometry.local_terrain_skin import (
    apply_corridor_constraints_to_height_grid,
    build_terrain_skin_mesh,
    terrain_skin_hash,
)
from scripts.geometry.sp638_local_corridor import Vec3

MAP_ASSET = ROOT / "Content/Worlds/SaCalobra/L_SaCalobraTerrainBaseline.umap"
VERTICES = 4033
_EPSILON_M = 1e-6


def _section_base(component, axis):
    name = f"section_base_{axis}"
    try:
        return int(component.get_editor_property(name))
    except Exception:
        return int(getattr(component, name))


def _component_quads(components):
    xs = sorted({_section_base(component, "x") for component in components})
    ys = sorted({_section_base(component, "y") for component in components})
    dx = [b - a for a, b in zip(xs, xs[1:]) if b > a]
    dy = [b - a for a, b in zip(ys, ys[1:]) if b > a]
    if not dx or not dy:
        raise RuntimeError("Could not infer Landscape component grid")
    qx, qy = min(dx), min(dy)
    if qx != qy or qx <= 0:
        raise RuntimeError("Landscape component grid is not square")
    return qx


def _select_components(components, component_quads, spacing_m, bounds):
    selected = []
    for component in components:
        sx = _section_base(component, "x")
        sy = _section_base(component, "y")
        min_x, max_x = sx * spacing_m, (sx + component_quads) * spacing_m
        min_y, max_y = sy * spacing_m, (sy + component_quads) * spacing_m
        if (
            max_x < bounds["min_x_m"]
            or min_x > bounds["max_x_m"]
            or max_y < bounds["min_y_m"]
            or min_y > bounds["max_y_m"]
        ):
            continue
        selected.append(component)
    if not selected:
        raise RuntimeError("Cut-only corridor selected no Landscape components")
    return selected


def _native_grid(root, manifest, selected, component_quads):
    spacing_m = float(manifest["scale_xy_cm_per_vertex"]) / 100.0
    if abs(spacing_m - 0.5) > 1e-9:
        raise RuntimeError("Cut-only preview requires the admitted 0.5 m grid")
    min_qx = min(_section_base(component, "x") for component in selected)
    max_qx = max(
        _section_base(component, "x") + component_quads for component in selected
    )
    min_qy = min(_section_base(component, "y") for component in selected)
    max_qy = max(
        _section_base(component, "y") + component_quads for component in selected
    )
    if min(min_qx, min_qy) < 0 or max(max_qx, max_qy) >= VERTICES:
        raise RuntimeError("Cut-only component patch exceeds terrain bounds")

    raw = array.array("H")
    raw.frombytes((root / "Prepared/terrain.r16").read_bytes())
    if sys.byteorder != "little":
        raw.byteswap()
    if len(raw) != VERTICES * VERTICES:
        raise RuntimeError("Cut-only preview heightmap size mismatch")

    scale_z = float(manifest["scale_z"])
    location_z_cm = float(manifest["location_z_cm"])

    def height_m(qx, qy):
        encoded = raw[qy * VERTICES + qx]
        return ((encoded - 32768) * scale_z / 128.0 + location_z_cm) / 100.0

    x_quads = tuple(range(min_qx, max_qx + 1))
    y_quads = tuple(range(max_qy, min_qy - 1, -1))
    xs = tuple(value * spacing_m for value in x_quads)
    ys = tuple(value * spacing_m for value in y_quads)
    heights = tuple(
        tuple(height_m(qx, qy) for qx in x_quads) for qy in y_quads
    )
    return xs, ys, heights


def _spawn_cut_mesh(world, terrain_mesh, origin_world):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = actors.spawn_actor_from_class(
        unreal.DynamicMeshActor, origin_world, unreal.Rotator(), transient=True
    )
    if actor is None:
        raise RuntimeError("Failed to spawn BOB cut-only local ground")
    actor.set_actor_label("BOB cut-only local ground - transient unsaved")

    component = actor.get_dynamic_mesh_component()
    mesh = component.get_dynamic_mesh()
    buffers = unreal.GeometryScriptSimpleMeshBuffers()
    buffers.set_editor_property(
        "vertices",
        [
            unreal.Vector(vertex.x * 100.0, vertex.y * 100.0, vertex.z * 100.0)
            for vertex in terrain_mesh.vertices
        ],
    )
    buffers.set_editor_property(
        "triangles",
        [unreal.IntVector(*triangle) for triangle in terrain_mesh.triangles],
    )
    mesh.reset()
    mesh.append_buffers_to_mesh(
        buffers, material_id=0, defer_change_notifications=True
    )
    mesh.recompute_normals(
        unreal.GeometryScriptCalculateNormalsOptions(),
        defer_change_notifications=True,
    )
    component.notify_mesh_modified()
    if (
        mesh.get_vertex_count() != len(terrain_mesh.vertices)
        or mesh.get_triangle_count() != len(terrain_mesh.triangles)
    ):
        raise RuntimeError("BOB cut-only local ground mesh count mismatch")

    parent = unreal.load_asset("/Engine/BasicShapes/BasicShapeMaterial")
    material = unreal.MaterialLibrary.create_dynamic_material_instance(world, parent)
    material.set_vector_parameter_value(
        "Color", unreal.LinearColor(0.34, 0.31, 0.25, 1.0)
    )
    component.set_material(0, material)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    return actor, material


def spawn_cut_only_preview(
    world, root, exact_sha, profile, smooth_vertices, smooth_meta, terrain_fit
):
    if terrain_fit.get("inspection_complete") is not True:
        raise RuntimeError("Cut-only preview requires complete terrain-fit inspection")
    counts = terrain_fit["class_counts"]
    if int(counts.get("CUT_REQUIRED", 0)) <= 0:
        raise RuntimeError("Cut-only preview requires CUT_REQUIRED samples")
    if int(counts.get("STRUCTURE_REVIEW", 0)) != 0:
        raise RuntimeError("Cut-only preview refuses STRUCTURE_REVIEW locations")

    policy = json.loads(
        (ROOT / "worldgen/terrain/adaptive_terrain_policy.json").read_text(
            encoding="utf-8"
        )
    )
    native_blend = policy["strategies"]["native_blend"]
    cut_limit = float(native_blend["max_ground_adjustment_m"])
    falloff_m = float(native_blend["shoulder_apron_m"])
    if float(terrain_fit["max_cut_required_m"]) > cut_limit + _EPSILON_M:
        raise RuntimeError("Cut-only preview exceeds first-lesson depth")

    manifest = json.loads(
        (root / "Prepared/terrain-import.json").read_text(encoding="utf-8")
    )
    landscapes = list(
        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    )
    if len(landscapes) != 1:
        raise RuntimeError("Cut-only preview expects one Landscape")
    components = list(
        landscapes[0].get_components_by_class(unreal.LandscapeComponent)
    )
    if len(components) != 1024:
        raise RuntimeError("Cut-only preview expects 1024 Landscape components")

    corridor, profiles, bounds = build_cut_only_corridor(
        profile, falloff_m=falloff_m
    )
    component_quads = _component_quads(components)
    spacing_m = float(manifest["scale_xy_cm_per_vertex"]) / 100.0
    selected = _select_components(
        components, component_quads, spacing_m, bounds
    )
    xs, ys, native = _native_grid(root, manifest, selected, component_quads)
    constrained, metrics = apply_corridor_constraints_to_height_grid(
        xs,
        ys,
        native,
        corridor,
        profiles,
        corridor_origin_m=Vec3(0.0, 0.0, 0.0),
        adjustment_mode="cut_only",
    )

    adjustments = [
        constrained[row][column] - native[row][column]
        for row in range(len(ys))
        for column in range(len(xs))
    ]
    raised_count = sum(value > _EPSILON_M for value in adjustments)
    cut_count = sum(value < -_EPSILON_M for value in adjustments)
    max_cut = max(
        (-value for value in adjustments if value < -_EPSILON_M),
        default=0.0,
    )
    if raised_count != 0 or cut_count <= 0 or max_cut > cut_limit + _EPSILON_M:
        raise RuntimeError("Cut-only grid violated bounded lowering contract")

    origin_z = min(min(row) for row in constrained)
    terrain_mesh = build_terrain_skin_mesh(
        xs,
        ys,
        constrained,
        origin_x_m=float(xs[0]),
        origin_y_m=float(ys[0]),
        origin_z_m=origin_z,
        lift_m=0.0,
    )

    top_count = int(smooth_meta["top_vertex_count"])
    penetration = []
    minimum_clearance = float("inf")
    for index, point in enumerate(smooth_vertices[:top_count]):
        x_m, y_m, road_z_m = [float(value) for value in point]
        ground_z = sample_regular_grid_height(
            xs, ys, constrained, x_m=x_m, y_m=y_m
        )
        clearance = road_z_m - ground_z
        minimum_clearance = min(minimum_clearance, clearance)
        if clearance < -_EPSILON_M:
            penetration.append(index)
    if penetration:
        raise RuntimeError(
            "Cut-only preview left terrain penetrating the ribbon"
        )

    baseline_hash = hashlib.sha256(MAP_ASSET.read_bytes()).hexdigest()
    for component in selected:
        component.set_visibility(False, True)

    origin_world = unreal.Vector(
        float(xs[0]) * 100.0,
        float(ys[0]) * 100.0,
        origin_z * 100.0,
    )
    actor, material = _spawn_cut_mesh(world, terrain_mesh, origin_world)
    saved_unchanged = (
        baseline_hash == hashlib.sha256(MAP_ASSET.read_bytes()).hexdigest()
    )
    report = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "architect": "BOB",
        "recipe_id": "bob-cut-only-local-ground-v1",
        "status": (
            "TECHNICAL_PREVIEW_PASS"
            if saved_unchanged
            else "REJECT_CUT_PREVIEW"
        ),
        "mode": "CUT_ONLY_TRANSIENT",
        "role": "INSPECTOR_PLUS_TRANSIENT_CUT_ONLY",
        "input_cut_required_sample_count": int(counts["CUT_REQUIRED"]),
        "ignored_fill_required_sample_count": int(counts["FILL_REQUIRED"]),
        "input_structure_review_sample_count": int(counts["STRUCTURE_REVIEW"]),
        "cut_depth_limit_m": cut_limit,
        "falloff_m": falloff_m,
        "hidden_landscape_component_count": len(selected),
        "component_quads": component_quads,
        "local_grid_rows": len(ys),
        "local_grid_columns": len(xs),
        "local_grid_sample_count": len(xs) * len(ys),
        "cut_grid_sample_count": cut_count,
        "raised_grid_sample_count": raised_count,
        "max_cut_depth_m": max_cut,
        "constraint_sample_count": metrics.constrained_sample_count,
        "constraint_rms_adjustment_m": metrics.rms_adjustment_m,
        "constraint_overlap_sample_count": metrics.overlapping_sample_count,
        "constraint_max_overlap_delta_m": metrics.max_overlap_delta_m,
        "remaining_road_penetration_count": len(penetration),
        "minimum_road_clearance_m": minimum_clearance,
        "terrain_mesh_vertex_count": len(terrain_mesh.vertices),
        "terrain_mesh_triangle_count": len(terrain_mesh.triangles),
        "terrain_mesh_sha256": terrain_skin_hash(terrain_mesh),
        "saved_baseline_sha256": baseline_hash,
        "saved_baseline_unchanged": saved_unchanged,
        "base_dtm_modified": False,
        "persistent_road_earthworks_modified": False,
        "map_saved": False,
        "production_authoring_permitted": False,
        "eligible_for_learning": False,
        "human_visual_status": "PENDING",
        "fill_authored": False,
        "structures_authored": False,
    }
    (root / "bob-cut-only-preview-proof.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    if report["status"] != "TECHNICAL_PREVIEW_PASS":
        raise RuntimeError("BOB cut-only preview changed the saved baseline")
    return actor, material, report
