"""Import checked network candidates with the established transient UE paths."""

import hashlib
import json
import math
from pathlib import Path

import unreal

from scripts.geometry.bob_vertical_support import build_vertical_support
from scripts.geometry.network_pavement import (
    PREVIEW_SUPPORT_CAP_M,
    pavement_slab,
    shoulder_sections,
    surface_inspection,
)
from scripts.ue.ma2141_road_preview import spawn_pavement_mesh


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def trace(world, point):
    x, y, z = point
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
    candidates = [
        p.z / 100
        for p in (() if hit is None else hit.to_tuple())
        if all(hasattr(p, k) for k in ("x", "y", "z"))
        and abs(p.x - x * 100) < 0.1
        and abs(p.y - y * 100) < 0.1
        and abs(p.z - z * 100) < 9999
    ]
    if not candidates:
        raise RuntimeError("Network Landscape trace missed")
    return candidates[0]


def shifted_sections_laterally(sections, shift_m):
    """Mirror the offline diagnostic shift using the Python standard library."""
    shifted = []
    for row in sections:
        dx = row[-1][0] - row[0][0]
        dy = row[-1][1] - row[0][1]
        length = math.hypot(dx, dy)
        if length <= 0 or not math.isfinite(length):
            raise RuntimeError("Extreme CUT transverse direction is invalid")
        offset_x, offset_y = dx / length * shift_m, dy / length * shift_m
        shifted.append(
            [[p[0] + offset_x, p[1] + offset_y, p[2]] for p in row]
        )
    return shifted


def start(world, root, exact_sha):
    directory = root / "Network"
    network = json.loads((directory / "network.json").read_text())
    if (
        network["exact_sha"] != exact_sha
        or network["width_m"] != 5.0
        or network["shoulder_m"] != 0.5
        or network["map_saved"]
        or network["base_dtm_modified"]
        or network.get("segmentation", {}).get("method")
        != "CONTINUOUS_CORRIDOR_ADAPTIVE_CONFLICT_INTERVALS_V1"
        or network.get("segmentation", {}).get("fixed_tiles_are_admission_boundaries")
        is not False
    ):
        raise RuntimeError("Network preview provenance mismatch")
    landscapes = list(
        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    )
    if len(landscapes) != 1:
        raise RuntimeError("Network needs the existing single Landscape")
    labels = [str(layer.get_name_bp()) for layer in landscapes[0].get_edit_layers_bp()]
    if labels.count("Base_DTM") != 1 or labels.count("Road_Earthworks") != 1:
        raise RuntimeError("Network Landscape layer ownership is ambiguous")
    for window in network["approved"]:
        if (
            window.get("technical_patch_tile") is not True
            or not isinstance(window.get("decision_interval_id"), str)
        ):
            raise RuntimeError("Network patch tile was used as an admission boundary")
        path = directory / window["cut_manifest"]
        if path.name != window["cut_manifest"] or digest(path) != window["cut_sha256"]:
            raise RuntimeError("Network CUT manifest changed")
        patch = json.loads(path.read_text())
        if (
            patch["max_cut_m"] > 1.0
            or digest(directory / patch["patch_file"]) != patch["patch_sha256"]
        ):
            raise RuntimeError("Network CUT cap/hash mismatch")
        if not unreal.CyclingLandscapeEarthworksLibrary.apply_road_earthworks_patch(
            landscapes[0], str(path)
        ):
            raise RuntimeError("Network native CUT patch application failed")
    return network


def spawn_extreme_cut_diagnostic(world, network):
    """Render the deepest rejected road/CUT conflict without repairing it."""
    case = network.get("extreme_cut_case")
    if (
        not isinstance(case, dict)
        or case.get("visual_status") != "CAPTURE_REQUIRED"
        or case.get("geometry_repair_executed") is not False
        or case.get("height_change_applied") is not False
        or case.get("road_admitted") is not False
        or case.get("cut_depth", {}).get("max_cut_m", 0) <= 1.0
    ):
        raise RuntimeError("Extreme network CUT evidence is missing or invalid")
    sections = case.get("sections")
    if not isinstance(sections, list) or len(sections) < 3:
        raise RuntimeError("Extreme network CUT geometry is incomplete")
    vertices, triangles = pavement_slab(sections)
    road, road_material = spawn_pavement_mesh(
        world, vertices, triangles, "BOB rejected extreme CUT " + case["id"]
    )
    road_material.set_vector_parameter_value(
        "Color", unreal.LinearColor(0.9, 0.04, 0.01, 1)
    )
    component = road.get_component_by_class(unreal.DynamicMeshComponent)
    component.set_enable_wireframe_render_pass(True)
    component.set_editor_property("explicit_show_wireframe", True)
    component.set_editor_property(
        "wireframe_color", unreal.LinearColor(1.0, 0.8, 0.0, 1.0)
    )

    lateral = case.get("lateral_sweep")
    if (
        not isinstance(lateral, dict)
        or lateral.get("lateral_change_applied") is not False
        or lateral.get("road_admitted") is not False
        or not isinstance(lateral.get("best_candidate"), dict)
    ):
        raise RuntimeError("Extreme CUT lateral diagnostic is missing or invalid")
    shift_m = lateral["best_candidate"].get("shift_m")
    if not isinstance(shift_m, (int, float)) or not math.isfinite(shift_m):
        raise RuntimeError("Extreme CUT lateral diagnostic shift is invalid")
    shifted_sections = shifted_sections_laterally(sections, shift_m)
    shifted_vertices, shifted_triangles = pavement_slab(shifted_sections)
    shifted_road, shifted_material = spawn_pavement_mesh(
        world,
        shifted_vertices,
        shifted_triangles,
        "BOB least-bad lateral diagnostic " + case["id"],
    )
    shifted_material.set_vector_parameter_value(
        "Color", unreal.LinearColor(0.0, 0.75, 0.9, 1)
    )
    shifted_component = shifted_road.get_component_by_class(
        unreal.DynamicMeshComponent
    )
    shifted_component.set_enable_wireframe_render_pass(True)
    shifted_component.set_editor_property("explicit_show_wireframe", True)
    shifted_component.set_editor_property(
        "wireframe_color", unreal.LinearColor(0.0, 1.0, 1.0, 1.0)
    )

    cut = case["cut_depth"]
    x_m, y_m = cut["peak_local_xy_m"]
    top_cm = cut["peak_base_height_m"] * 100
    bottom_cm = cut["peak_target_height_m"] * 100
    depth_cm = top_cm - bottom_cm
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    marker = actors.spawn_actor_from_class(
        unreal.StaticMeshActor,
        unreal.Vector(x_m * 100, y_m * 100, (top_cm + bottom_cm) / 2),
        unreal.Rotator(),
        transient=True,
    )
    marker.set_actor_label("BOB deepest rejected CUT marker")
    marker_component = marker.get_component_by_class(unreal.StaticMeshComponent)
    cube = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
    parent = unreal.load_asset("/Engine/BasicShapes/BasicShapeMaterial")
    if marker_component is None or cube is None or parent is None:
        raise RuntimeError("Extreme CUT marker assets are unavailable")
    marker_component.set_static_mesh(cube)
    marker_material = unreal.MaterialLibrary.create_dynamic_material_instance(
        world, parent
    )
    marker_material.set_vector_parameter_value(
        "Color", unreal.LinearColor(1.0, 0.8, 0.0, 1.0)
    )
    marker_component.set_material(0, marker_material)
    marker_component.set_cast_shadow(False)
    marker.set_actor_scale3d(unreal.Vector(0.2, 0.2, depth_cm / 100))
    return [
        road,
        road_material,
        shifted_road,
        shifted_material,
        marker,
        marker_material,
    ]


def finish(world, root, exact_sha, network):
    kept = []
    reports = []
    for window in network["approved"]:
        sections = window["sections"]
        surface = surface_inspection(sections)
        if surface["status"] != "PASS" or surface != window["surface_inspection"]:
            raise RuntimeError("Native network 3D surface receipt mismatch")
        if len(sections) < 3 or any(len(row) != 25 for row in sections):
            raise RuntimeError("Network sections are incomplete")
        ground = []
        support = shoulder_sections(sections)
        missed_clearance = 0
        maximum_penetration = 0.0
        for row, extended in zip(sections, support, strict=True):
            if any(not math.isfinite(v) for p in row for v in p):
                raise RuntimeError("Network nonfinite vertex")
            width = math.dist(row[0][:2], row[-1][:2])
            if abs(width - 5.0) > 0.0001:
                raise RuntimeError("Native network width drift")
            for point in row:
                penetration = trace(world, point) - point[2]
                maximum_penetration = max(maximum_penetration, penetration)
                missed_clearance += penetration > 0.005
            endpoints = [trace(world, extended[0]), trace(world, extended[-1])]
            if any(
                g - p[2] > 0.005 for g, p in zip(endpoints, (extended[0], extended[-1]))
            ):
                raise RuntimeError("Native network shoulder buried")
            ground.append(endpoints)
        if missed_clearance:
            raise RuntimeError(
                f"Network asphalt penetration: {window['id']}: {missed_clearance} samples, {maximum_penetration:.4f} m"
            )
        vertices, triangles = pavement_slab(sections)
        sv, st, proof = build_vertical_support(support, ground)
        if (
            proof["min_shoulder_extent_m"] < 0.4999
            or proof["max_shoulder_extent_m"] > 0.51
            or proof["max_wall_height_m"] > PREVIEW_SUPPORT_CAP_M
        ):
            raise RuntimeError("Network support/shoulder admission failed")
        kept.append(
            spawn_pavement_mesh(
                world, vertices, triangles, "BOB network asphalt " + window["id"]
            )
        )
        actor, material = spawn_pavement_mesh(
            world, sv, st, "BOB network support " + window["id"]
        )
        material.set_vector_parameter_value(
            "Color", unreal.LinearColor(0.34, 0.31, 0.25, 1)
        )
        kept.append((actor, material))
        reports.append(
            {
                "id": window["id"],
                "length_m": window["length_m"],
                "trace_count": len(sections) * 27,
                "asphalt_penetration_count": missed_clearance,
                "maximum_penetration_m": maximum_penetration,
                "support": proof,
                "surface_inspection": surface,
            }
        )
    report = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "status": "PARTIAL_IMPORTED"
        if network["blocked"]
        else "IMPORTED_REVIEW_REQUIRED",
        "approved_length_m": network["approved_length_m"],
        "blocked_length_m": network["blocked_length_m"],
        "continuous_corridor_count": network["continuous_corridor_count"],
        "decision_interval_count": network["decision_interval_count"],
        "adaptive_conflict_interval_count": network[
            "adaptive_conflict_interval_count"
        ],
        "technical_patch_tile_count": network["technical_patch_tile_count"],
        "segmentation": network["segmentation"],
        "windows": reports,
        "blocked": network["blocked"],
        "height_profile_candidate_window_count": network[
            "height_profile_candidate_window_count"
        ],
        "height_profile_candidate_length_m": network[
            "height_profile_candidate_length_m"
        ],
        "height_profile_incompatible_window_count": network[
            "height_profile_incompatible_window_count"
        ],
        "extreme_cut_case": {
            "id": network["extreme_cut_case"]["id"],
            "max_cut_m": network["extreme_cut_case"]["cut_depth"]["max_cut_m"],
            "cut_depth_by_envelope": network["extreme_cut_case"][
                "cut_depth_by_envelope"
            ],
            "profile_fit_status": network["extreme_cut_case"][
                "height_profile_fit"
            ]["status"],
            "review": network["extreme_cut_case"]["review"],
            "width_sensitivity": network["extreme_cut_case"][
                "width_sensitivity"
            ],
            "lateral_sweep": network["extreme_cut_case"]["lateral_sweep"],
            "visual_status": "CAPTURE_REQUIRED",
            "capture": "network-extreme-cut.png",
            "diagnostic_image": network["extreme_cut_case"]["diagnostic_image"],
            "diagnostic_image_sha256": network["extreme_cut_case"][
                "diagnostic_image_sha256"
            ],
            "review_document": network["extreme_cut_case"]["review_document"],
            "review_document_sha256": network["extreme_cut_case"][
                "review_document_sha256"
            ],
        },
        "map_saved": False,
        "base_dtm_modified": False,
        "collision_admitted": False,
        "human_visual_status": "PENDING",
        "performance_status": "PENDING",
    }
    (root / "network-native-proof.json").write_text(json.dumps(report, indent=2) + "\n")
    return kept, report
