"""Validate native curved presentation boundaries independently of shading."""

from __future__ import annotations

import hashlib
import itertools
import json
import math

RECIPE = "native-paired-edge-curves-v1"
ANCHOR_RECIPE = "native-cliff-edge-width-v3"
COMMON_AXIS_RECIPE = "native-common-axis-width-v2"
RENDER_STEP_M = 0.25
STATION_COUNT = 1201
MAX_DISPLACEMENT_M = (
    1.0  # Existing inferred edge review allowance, not survey accuracy.
)
MAX_CHORD_ERROR_M = 0.02


def boundary_span_metrics(rows, spec):
    """Reject a pinched native fillet and retain its measured endpoint joins."""
    edge, start, end = spec["edge"], spec["start_station_m"], spec["end_station_m"]
    required = spec["minimum_radius_m"]
    joins = [
        spec.get("join_position_error_m"),
        spec.get("join_tangent_error_m_per_key"),
    ]
    if (
        edge not in (0, 1)
        or not 0 <= start < end <= 300
        or not math.isfinite(required)
        or required < 1.5
        or spec.get("point_type") != "CurveCustomTangent"
        or any(
            not isinstance(v, (int, float))
            or not math.isfinite(v)
            or not 0 <= v <= 1e-4
            for v in joins
        )
    ):
        raise ValueError("Invalid native boundary span or discontinuous join")
    points = [r["edges_xy_m"][edge] for r in rows if start <= r["station_m"] <= end]
    if len(points) < 3:
        raise ValueError("Boundary span needs complete curvature samples")
    max_curvature = 0.0
    for a, b, c in zip(points, points[1:], points[2:]):
        ab, bc, ac = math.dist(a, b), math.dist(b, c), math.dist(a, c)
        if min(ab, bc, ac) <= 1e-9:
            raise ValueError("Boundary span stops or reverses")
        double_area = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
        max_curvature = max(max_curvature, 2 * double_area / (ab * bc * ac))
    if max_curvature > 1 / required:
        raise ValueError("Boundary span remains pinched below its minimum radius")
    return dict(
        spec,
        maximum_sampled_curvature_per_m=max_curvature,
        minimum_sampled_radius_m=1 / max_curvature if max_curvature else None,
    )


def xy_digest(sections):
    return hashlib.sha256(
        json.dumps(sections, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def edge_role_proof_valid(plan):
    if plan.get("recipe") != ANCHOR_RECIPE:
        return True
    from scripts.geometry.road_edge_roles import edge_roles, terrain_roles_at

    try:
        rows = plan["edge_role_samples"]
        spans = plan["controlled_width"]["edge_constraint"]["terrain_spans"]
        return (
            len(rows) == STATION_COUNT
            and plan["edge_roles_sha256"] == xy_digest(rows)
            and all(
                row["station_m"] == i * RENDER_STEP_M
                and row["travel_direction"] == 1
                and row["edges"]
                == edge_roles(
                    row["curvature_per_m"], terrain_roles_at(spans, row["station_m"])
                )
                for i, row in enumerate(rows)
            )
        )
    except (KeyError, TypeError, ValueError):
        return False


def profile_plan_valid(profile):
    """Keep the legacy source-preserving recipe; explicitly admit derived XY."""
    if profile.get("source_xy_preserved") is True:
        return "presentation_plan" not in profile
    plan = profile.get("presentation_plan", {})
    rows = profile.get("stations", [])
    if not isinstance(plan, dict) or not isinstance(rows, list):
        return False
    return (
        profile.get("source_xy_preserved") is False
        and profile.get("canonical_source_xy_preserved") is True
        and plan.get("recipe") in (RECIPE, COMMON_AXIS_RECIPE, ANCHOR_RECIPE)
        and plan.get("status") == "PASS"
        and edge_role_proof_valid(plan)
        and plan.get("exact_sha") == profile.get("exact_sha")
        and plan.get("source_sha256") == profile.get("source_sha256")
        and plan.get("profile_sha256") == profile.get("profile_sha256")
        and len(rows) == STATION_COUNT
        and all(len(row.get("source_xy_local_m", [])) == 25 for row in rows)
        and plan.get("sections_sha256")
        == xy_digest([r.get("xy_local_m") for r in rows])
        and plan.get("source_sections_sha256")
        == xy_digest([r.get("source_xy_local_m") for r in rows])
    )


def prepare_sections(
    packet, source_sections, *, exact_sha, source_sha, profile_sha, origin
):
    """Check dense native curves, then emit 1201 paired 25-point sections."""
    from shapely.geometry import LineString, Polygon

    if (
        packet.get("exact_sha") != exact_sha
        or packet.get("source_sha256") != source_sha
        or packet.get("profile_sha256") != profile_sha
        or packet.get("origin_epsg_m") != origin
        or packet.get("producer") != "USplineComponent"
        or packet.get("point_type")
        != (
            "CurveCustomTangent"
            if packet.get("geometry_contract")
            in ("common-axis-width-v2", "cliff-edge-width-v3")
            else "Curve"
        )
        or packet.get("status") != "NATIVE_CURVES_EXPORTED_REVIEW_REQUIRED"
        or packet.get("canonical_source_modified") is not False
        or packet.get("map_modified") is not False
    ):
        raise ValueError("Native curve provenance mismatch")
    rows = packet["stations"]
    if len(rows) != 4801 or len(source_sections) != STATION_COUNT:
        raise ValueError("Incomplete paired curve domain")
    for i, row in enumerate(rows):
        edges = row["edges_xy_m"]
        if (
            row["station_m"] != i * 0.0625
            or len(edges) != 2
            or any(
                len(p) != 2
                or any(
                    isinstance(v, bool)
                    or not isinstance(v, (float, int))
                    or not math.isfinite(v)
                    for v in p
                )
                for p in edges
            )
        ):
            raise ValueError("Nonfinite or unordered native curve samples")
    anchor_contract = packet.get("geometry_contract") == "cliff-edge-width-v3"
    anchor_edge = None
    width_metrics = None
    if packet.get("geometry_contract") == "common-axis-width-v2":
        from scripts.geometry.road_width_profile import offset_edges, width_at

        profile = packet["width_profile"]
        max_error, minimum, maximum = 0.0, math.inf, 0.0
        for row in rows:
            center, tangent = row["center_xy_m"], row["tangent_xy_m_per_key"]
            if any(
                len(p) != 2 or any(not math.isfinite(v) for v in p)
                for p in (center, tangent)
            ):
                raise ValueError("Nonfinite common-axis sample")
            expected = offset_edges(
                center, tangent, width_at(profile, row["station_m"])
            )
            error = max(math.dist(a, b) for a, b in zip(expected, row["edges_xy_m"]))
            max_error = max(max_error, error)
            width = math.dist(*row["edges_xy_m"])
            minimum, maximum = min(minimum, width), max(maximum, width)
        if max_error > 1e-4:
            raise ValueError(
                "Pavement departs from common axis / intended width profile"
            )
        arc = packet["axis_arc"]
        if (
            not 0 <= arc["fit_start_m"] < arc["fit_end_m"] <= 300
            or arc["radius_m"] <= 0
        ):
            raise ValueError("Invalid designed arc domain")
        radial_error = max(
            abs(math.dist(row["center_xy_m"], arc["center_xy_m"]) - arc["radius_m"])
            for row in rows
            if arc["fit_start_m"] <= row["station_m"] <= arc["fit_end_m"]
        )
        if radial_error > MAX_CHORD_ERROR_M:
            raise ValueError("Native axis departs from designed circular arc")
        width_metrics = {
            "profile": profile,
            "maximum_edge_profile_error_m": max_error,
            "minimum_width_m": minimum,
            "maximum_width_m": maximum,
            "axis_arc": arc,
            "maximum_axis_radial_error_m": radial_error,
        }
    if anchor_contract:
        from scripts.geometry.road_edge_roles import anchored_edges, terrain_roles_at
        from scripts.geometry.road_width_profile import boundary_width_profile, width_at

        constraint = packet["edge_constraint"]
        anchor_edge = constraint["reference_edge"]
        if anchor_edge not in (0, 1) or not constraint.get("evidence"):
            raise ValueError("Missing evidenced authoritative edge")
        spans = constraint["terrain_spans"]
        for span in spans:
            if not 0 <= span["start_station_m"] < span["end_station_m"] <= 300:
                raise ValueError("Terrain side span outside road domain")
            if span["roles"][1 - anchor_edge] == "CLIFF":
                raise ValueError("Reference edge disagrees with cliff-side evidence")
        distance_profile, distances = boundary_width_profile(
            packet["width_profile"], rows
        )
        if packet.get("width_distance_profile") != distance_profile:
            raise ValueError("Boundary distance width profile mismatch")
        max_error, minimum, maximum = 0.0, math.inf, 0.0
        for row, distance in zip(rows, distances):
            terrain_roles_at(spans, row["station_m"])
            anchor, tangent = row["anchor_xy_m"], row["anchor_tangent_xy_m_per_key"]
            expected = anchored_edges(
                anchor,
                tangent,
                sum(width_at(distance_profile, distance)),
                anchor_edge,
            )
            error = max(math.dist(a, b) for a, b in zip(expected, row["edges_xy_m"]))
            if (
                math.dist(
                    row["center_xy_m"],
                    [(expected[0][k] + expected[1][k]) / 2 for k in range(2)],
                )
                > 1e-4
            ):
                raise ValueError("Derived pavement axis does not match boundaries")
            max_error = max(max_error, error)
            width = math.dist(*row["edges_xy_m"])
            minimum, maximum = min(minimum, width), max(maximum, width)
        if max_error > 1e-4:
            raise ValueError(
                "Pavement departs from authoritative edge / intended width profile"
            )
        reference_arc = packet.get("reference_arc")
        radial_error = None
        if reference_arc is not None:
            start, end = (
                reference_arc["start_station_m"],
                reference_arc["end_station_m"],
            )
            radius = reference_arc["radius_m"]
            if not 0 <= start < end <= 300 or not math.isfinite(radius) or radius <= 0:
                raise ValueError("Invalid reference arc")
            radial_error = max(
                abs(
                    math.dist(row["anchor_xy_m"], reference_arc["center_xy_m"]) - radius
                )
                for row in rows
                if start <= row["station_m"] <= end
            )
            if radial_error > MAX_CHORD_ERROR_M:
                raise ValueError("Reference curve departs from designed arc")
        width_metrics = {
            "profile": packet["width_profile"],
            "distance_profile": distance_profile,
            "reference_arc": reference_arc,
            "maximum_reference_radial_error_m": radial_error,
            "maximum_edge_profile_error_m": max_error,
            "minimum_width_m": minimum,
            "maximum_width_m": maximum,
            "edge_constraint": constraint,
            "width_frame": "authoritative-boundary horizontal normal",
        }
    boundaries = [[r["edges_xy_m"][side] for r in rows] for side in (0, 1)]
    polygon = Polygon(boundaries[0] + boundaries[1][::-1])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Curved pavement self-intersects or edges cross")
    if any(not LineString(edge).is_simple for edge in boundaries):
        raise ValueError("Curved pavement boundary self-intersects")
    spans = [
        boundary_span_metrics(rows, spec) for spec in packet.get("boundary_spans", [])
    ]
    sections, displacement, chord_error, min_area = [], 0.0, 0.0, math.inf
    side_displacements = [0.0, 0.0]
    for index, row in enumerate(rows):
        segment = min(index // 4, STATION_COUNT - 2)
        alpha = (index - segment * 4) / 4
        for side, endpoint in ((0, 0), (1, 24)):
            a, b = (
                source_sections[segment][endpoint],
                source_sections[segment + 1][endpoint],
            )
            reference = [a[k] + (b[k] - a[k]) * alpha for k in range(2)]
            side_displacements[side] = max(
                side_displacements[side], math.dist(reference, row["edges_xy_m"][side])
            )
            displacement = max(displacement, side_displacements[side])
    for i in range(STATION_COUNT):
        left, right = rows[i * 4]["edges_xy_m"]
        width = math.dist(left, right)
        if not 2.0 <= width <= 12.0:
            raise ValueError("Curved pavement width outside preview bounds")
        section = [
            [left[k] + (right[k] - left[k]) * j / 24 for k in range(2)]
            for j in range(25)
        ]
        sections.append(section)
        for side, index in ((0, 0), (1, 24)):
            # Compare corresponding chainage, not a nearby arm of the hairpin.
            if i < STATION_COUNT - 1:
                a, b = (
                    rows[i * 4]["edges_xy_m"][side],
                    rows[i * 4 + 4]["edges_xy_m"][side],
                )
                for sub in (1, 2, 3):
                    p = rows[i * 4 + sub]["edges_xy_m"][side]
                    chord = [a[k] + (b[k] - a[k]) * sub / 4 for k in range(2)]
                    chord_error = max(chord_error, math.dist(p, chord))
    constrained_displacement = (
        side_displacements[anchor_edge] if anchor_contract else displacement
    )
    if constrained_displacement > MAX_DISPLACEMENT_M:
        raise ValueError(
            f"Curved edge exceeds 1 m source review allowance: {constrained_displacement:.6f} m"
        )
    if chord_error > MAX_CHORD_ERROR_M:
        raise ValueError(
            f"0.25 m tessellation misses native curve: {chord_error:.6f} m"
        )
    for first, second in itertools.pairwise(sections):
        for j in range(24):
            for a, b, c in (
                (first[j], first[j + 1], second[j]),
                (first[j + 1], second[j + 1], second[j]),
            ):
                area = -((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
                min_area = min(min_area, area)
                if area <= 1e-9:
                    raise ValueError("Curved road cross-sections fold or invert")
    role_samples = []
    if anchor_contract:
        from scripts.geometry.road_edge_roles import edge_roles, terrain_roles_at

        centers = [row[12] for row in sections]
        for i, center in enumerate(centers):
            j = max(1, min(i, len(centers) - 2))
            a, b, c = centers[j - 1 : j + 2]
            ab, bc, ac = math.dist(a, b), math.dist(b, c), math.dist(a, c)
            if min(ab, bc, ac) <= 1e-9:
                raise ValueError("Pavement axis stops or reverses")
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            curvature = 2 * cross / (ab * bc * ac)
            roles = edge_roles(
                curvature,
                terrain_roles_at(
                    packet["edge_constraint"]["terrain_spans"], i * RENDER_STEP_M
                ),
            )
            role_samples.append(
                {
                    "station_m": i * RENDER_STEP_M,
                    "curvature_per_m": curvature,
                    "travel_direction": 1,
                    "edges": roles,
                }
            )
    return sections, {
        "recipe": ANCHOR_RECIPE
        if anchor_contract
        else (COMMON_AXIS_RECIPE if width_metrics else RECIPE),
        "edge_role_samples": role_samples,
        "edge_roles_sha256": xy_digest(role_samples),
        "edge_displacements_m": side_displacements,
        "maximum_constrained_edge_displacement_m": constrained_displacement,
        "controlled_width": width_metrics,
        "status": "PASS",
        "exact_sha": exact_sha,
        "source_sha256": source_sha,
        "profile_sha256": profile_sha,
        "sections_sha256": xy_digest(sections),
        "source_sections_sha256": xy_digest(source_sections),
        "max_corresponding_edge_displacement_m": displacement,
        "max_sampled_chord_error_m": chord_error,
        "minimum_triangle_double_area_m2": min_area,
        "self_intersection": False,
        "boundary_spans": spans,
        "human_visual_status": "PENDING",
        "canonical_chainage_preserved": True,
        "presentation_length_is_not_physics_length": True,
    }
