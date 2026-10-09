"""Import checked network candidates with the established transient UE paths."""

import hashlib
import json
import math
import time
from pathlib import Path

import unreal

from scripts.geometry.bob_vertical_support import build_vertical_support
from scripts.geometry.nudo_structure import bridge_parapets, build_nudo_support, inspect_underpass
from scripts.geometry.reviewed_network import construction_windows, validate_slab
from scripts.geometry.road_review_policy import review_surface, width_review
from scripts.geometry.network_pavement import (
    PREVIEW_SUPPORT_CAP_M,
    pavement_slab,
    shoulder_sections,
)
from scripts.ue.ma2141_road_preview import spawn_pavement_mesh
from scripts.geometry.network_visual_preview import (
    MARKER_GROUND_OFFSET_M,
    source_marker_mesh,
    validate_full_preview,
)


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
    started = time.perf_counter()
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
    proof = validate_full_preview(network["full_preview"], network["source_clipped_length_m"])
    if proof != network.get("full_preview_proof"):
        raise RuntimeError("Full network preview receipt mismatch")
    landscapes = list(
        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    )
    if len(landscapes) != 1:
        raise RuntimeError("Network needs the existing single Landscape")
    labels = [str(layer.get_name_bp()) for layer in landscapes[0].get_edit_layers_bp()]
    if labels.count("Base_DTM") != 1 or labels.count("Road_Earthworks") != 1:
        raise RuntimeError("Network Landscape layer ownership is ambiguous")
    network["runtime_review_reasons"] = {}
    for window in construction_windows(network):
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
            patch.get("owner_reviewed_geometry", False) != window.get("owner_reviewed_geometry", False)
            or digest(directory / patch["patch_file"]) != patch["patch_sha256"]
        ):
            raise RuntimeError("Network CUT cap/hash mismatch")
        if patch["max_cut_m"] > 1.0 and not window.get("owner_reviewed_geometry"):
            network["runtime_review_reasons"][window["id"]] = ["Ordinary CUT exceeds 1 m; render for review without applying this patch"]
            continue
        if not unreal.CyclingLandscapeEarthworksLibrary.apply_road_earthworks_patch(
            landscapes[0], str(path), True
        ):
            raise RuntimeError("Network native CUT patch application failed")
    if not unreal.CyclingLandscapeEarthworksLibrary.finish_road_earthworks_batch(landscapes[0]):
        raise RuntimeError("Network native CUT batch flush failed")
    network["native_timings"] = {"patch_batch_seconds": time.perf_counter()-started,
                                 "explicit_network_landscape_flush_count": 1}
    return network


def spawn_extreme_cut_diagnostic(world, network):
    """Render the deepest rejected road/CUT conflict without repairing it."""
    if "owner_reviewed" in network:
        construction_windows(network)  # Do not overlay rejected/shifted slabs on adopted asphalt.
        return []
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
    road, road_material = None, None
    if not network.get("full_context_rendered"):
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


def spawn_full_visual_context(world, network):
    """Render every rejected candidate and full source location without CUT/collision."""
    preview = network["full_preview"]
    proof = validate_full_preview(preview, network["source_clipped_length_m"])
    if proof != network["full_preview_proof"]:
        raise RuntimeError("Full preview geometry changed")
    kept = []
    reviewed = "owner_reviewed" in network
    if reviewed:
        construction_windows(network)
    for item in ([] if reviewed else preview["rejected_surfaces"]):
        vertices, triangles = pavement_slab(item["sections"])
        actor, material = spawn_pavement_mesh(world, vertices, triangles, "REVIEW rejected road " + item["id"])
        material.set_vector_parameter_value("Color", unreal.LinearColor(0.9, 0.04, 0.01, 1))
        kept.append((actor, material))
    for marker in ([] if reviewed else preview["source_markers"]):
        points = [[x, y, trace(world, (x, y, marker["ground_m"][index])) + MARKER_GROUND_OFFSET_M] for index, (x, y) in enumerate(marker["xy_local_m"])]
        vertices, triangles = source_marker_mesh(points)
        actor, material = spawn_pavement_mesh(world, vertices, triangles, "SOURCE LOCATION " + marker["id"])
        material.set_vector_parameter_value("Color", unreal.LinearColor(1.0, 0.55, 0.03, 1))
        kept.append((actor, material))
    proof = {**proof, "rendered_source_marker_count": len(preview["source_markers"]), "rendered_rejected_surface_count": len(preview["rejected_surfaces"]), "marker_ground_offset_m": MARKER_GROUND_OFFSET_M, "collision_admitted": False, "terrain_change_applied": False}
    if reviewed:
        replaced_surfaces = {w["decision_interval_id"] for w in network.get("owner_reviewed", [])
                             if w["id"] in network.get("nudo", {}).get("replaced_window_ids", [])}
        proof.update(rendered_rejected_surface_count=0,
                     rendered_source_marker_count=0,
                     source_markers_hidden=True,
                     rendered_reviewed_surface_count=len(preview["rejected_surfaces"])-len(replaced_surfaces),
                     reviewed_surfaces_replaced_by_nudo=len(replaced_surfaces),
                     terrain_change_applied=True, material="ASPHALT")
    return kept, proof


def render_window(world, window, network):
    """Render valid buffers; mark measured road problems red instead of aborting."""
    kept = []
    sections = window["sections"]
    if len(sections) < 3 or any(len(r) != 25 or any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in r) for r in sections):
        raise RuntimeError("Network buffers are not renderable")
    reasons = list(window.get("visual_review_reasons", []))
    reasons.extend(network.get("runtime_review_reasons", {}).get(window["id"], []))
    try:
        validate_slab(sections)
    except ValueError as exc:
        reasons.append(str(exc))
    surface = review_surface(sections)
    if surface != window["surface_inspection"]:
        raise RuntimeError("Native network 3D surface receipt mismatch")
    if surface["status"] != "PASS" and (not window.get("owner_reviewed_geometry") or window.get("nudo_structure")):
        reasons.append("3D surface parameters require owner review")
    widths = width_review(sections, window.get("connection", False))
    if widths["status"] != "PASS":
        reasons.append("Pavement width outside the owner 5% envelope")
    support = None
    ground = []
    missed_clearance = 0
    maximum_penetration = 0.0
    shoulder_penetrations = 0
    trace_misses = 0
    def sample(point):
        nonlocal trace_misses
        try:
            return trace(world, point)
        except RuntimeError as exc:
            if str(exc) != "Network Landscape trace missed":
                raise
            trace_misses += 1
            return None
    for row in sections:
        for point in row:
            height = sample(point)
            if height is None:
                continue
            penetration = height-point[2]
            maximum_penetration = max(maximum_penetration, penetration)
            missed_clearance += penetration > 0.005
    if missed_clearance:
        reasons.append(f"Asphalt intersects terrain at {missed_clearance} samples; max {maximum_penetration:.4f} m")
    proof = {"status": "REVIEW_REQUIRED", "underpass_clearance": {"status": "NOT_BUILT"}}
    try:
        if trace_misses:
            raise ValueError(f"Native ground missing at {trace_misses} asphalt samples; support not built")
        support = selected_shoulder_sections(window, network)
        for row in support:
            endpoints = [sample(row[0]), sample(row[-1])]
            if None in endpoints:
                raise ValueError("Native shoulder ground missing; support not built")
            shoulder_penetrations += sum(g-p[2] > .005 for g,p in zip(endpoints,(row[0],row[-1])))
            ground.append(endpoints)
        if shoulder_penetrations:
            reasons.append(f"Shoulders intersect terrain at {shoulder_penetrations} samples")
        if window.get("nudo_structure"):
            sv, st, proof = build_nudo_support(support, ground, window["station_start_m"], network["nudo"]["structure"])
            if proof["arch_soffit_triangle_count"]:
                try:
                    proof["underpass_clearance"] = inspect_underpass(sv, st, network["nudo"]["structure"])
                except ValueError as exc:
                    proof["underpass_clearance"] = {"status": "REVIEW_REQUIRED", "reason": str(exc)}
                    reasons.append(str(exc))
        else:
            sv, st, proof = build_vertical_support(support, ground)
        cap = network["nudo"]["structure"]["support_cap_m"] if window.get("nudo_structure") else PREVIEW_SUPPORT_CAP_M
        if proof["min_shoulder_extent_m"] < .4999 or proof["max_shoulder_extent_m"] > .51 or proof["max_wall_height_m"] > cap:
            reasons.append("Support or shoulder dimensions outside the design envelope")
        actor, material = spawn_pavement_mesh(world, sv, st, "BOB network support " + window["id"])
        material.set_vector_parameter_value("Color", unreal.LinearColor(.34,.31,.25,1))
        kept.append((actor,material))
        if window.get("nudo_structure"):
            pv,pt = bridge_parapets(support,window["station_start_m"],network["nudo"]["structure"])
            if pv:
                parapet,pm = spawn_pavement_mesh(world,pv,pt,"Nudo bridge parapets " + window["id"])
                pm.set_vector_parameter_value("Color",unreal.LinearColor(.34,.31,.25,1))
                kept.append((parapet,pm))
    except ValueError as exc:
        # A support recipe may reject a folded buffer; keep the actual pavement
        # visible rather than inventing a different support to conceal it.
        reasons.append(str(exc))
        proof = {"status":"REVIEW_REQUIRED", "reason":str(exc)}
    vertices,triangles = pavement_slab(sections)
    actor,material = spawn_pavement_mesh(world,vertices,triangles,"BOB network pavement " + window["id"])
    if reasons:
        material.set_vector_parameter_value("Color",unreal.LinearColor(.9,.04,.01,1))
    kept.append((actor,material))
    return kept, {
        "id":window["id"], "length_m":window["length_m"],
        "trace_count":len(sections)*25+len(ground)*2,
        "asphalt_penetration_count":missed_clearance, "maximum_penetration_m":maximum_penetration,
        "trace_miss_count":trace_misses,
        "shoulder_penetration_count":shoulder_penetrations, "support":proof,
        "surface_inspection":surface, "width_inspection":widths,
        "visual_review_required":bool(reasons), "visual_review_reasons":reasons,
        "pavement_material":"REVIEW_RED" if reasons else "ASPHALT",
        "owner_reviewed_geometry":window.get("owner_reviewed_geometry",False),
        "connection":window.get("connection",False),
    }


def prepare_shared_shoulders(network):
    """Compute shared endpoints before rendering; retain rejected buffers for review."""
    from scripts.geometry.network_shoulder_joints import fingerprint, repair_shoulder_joints

    windows = list(construction_windows(network))
    eligible, original, failed = [], {}, {}
    for window in windows:
        try:
            original[window["id"]] = shoulder_sections(window["sections"])
            eligible.append({"id": window["id"], "sections": window["sections"]})
        except ValueError as exc:
            failed[window["id"]] = str(exc)
    if eligible:
        protected = [w["id"] for w in windows
                     if w.get("nudo_structure") and w["id"] in original]
        supports, report = repair_shoulder_joints(
            eligible, original, protected_ids=protected
        )
    else:
        supports = {}
        report = {"status": "NO_REPAIRABLE_SUPPORT", "joints": [],
                  "native_contact_verified": False, "visual_acceptance": "PENDING"}
    network["shared_shoulder_sections"] = supports
    network["shared_shoulder_source_hashes"] = {
        w["id"]: fingerprint(w["sections"]) for w in eligible
    }
    network["shared_shoulder_output_hashes"] = {
        name: fingerprint(rows) for name, rows in supports.items()
    }
    report["excluded_window_reasons"] = failed
    report["construction_window_count"] = len(windows)
    network["shoulder_joint_repair"] = report


def selected_shoulder_sections(window, network):
    """Reject stale candidates; the normal native trace loop samples these NEW points."""
    from scripts.geometry.network_shoulder_joints import fingerprint

    candidates = network.get("shared_shoulder_sections", {})
    if window["id"] not in candidates:
        return shoulder_sections(window["sections"])
    if network["shared_shoulder_source_hashes"].get(window["id"]) != fingerprint(
        window["sections"]
    ):
        raise RuntimeError("Shared shoulder source changed before native trace")
    candidate = candidates[window["id"]]
    if network["shared_shoulder_output_hashes"].get(window["id"]) != fingerprint(candidate):
        raise RuntimeError("Shared shoulder geometry changed before native trace")
    return candidate


def finish(world, root, exact_sha, network):
    started = time.perf_counter()
    prepare_shared_shoulders(network)
    kept, reports = [], []
    for window in construction_windows(network):
        objects, report = render_window(world, window, network)
        kept.extend(objects)
        reports.append(report)
    context_objects, context_proof = spawn_full_visual_context(world, network)
    review_count = sum(w["visual_review_required"] for w in reports)
    context_proof["rendered_review_red_window_count"] = review_count
    kept.extend(context_objects)
    network["full_context_rendered"] = True
    report = {
        "native_timings": {**network.get("native_timings", {}), "trace_and_mesh_seconds": time.perf_counter()-started},
        "full_visual_context": context_proof,
        "owner_construction_decision": network.get("owner_construction_decision"),
        "nudo": ({k: v for k, v in network["nudo"].items() if k != "windows"} if "nudo" in network else None),
        "shoulder_joint_repair": network["shoulder_joint_repair"],
        "construction_window_count": len(reports),
        "visual_review_window_count": review_count,
        "preview_policy": "RENDER_DEVIATIONS_RED_WIDTH_TOLERANCE_5_PERCENT",
        "owner_reviewed_patch_tile_count": sum(w.get("owner_reviewed_geometry", False) and not w.get("nudo_structure", False) for w in construction_windows(network)),
        "constructed_length_m": sum(w["length_m"] for w in reports),
        "surface_review_exception_count": sum(w["surface_inspection"]["status"] != "PASS" for w in reports),
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
