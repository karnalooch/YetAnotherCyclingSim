"""Validate native curved presentation boundaries independently of shading."""

from __future__ import annotations

import hashlib
import itertools
import json
import math

RECIPE = "native-paired-edge-curves-v1"
RENDER_STEP_M = 0.25
STATION_COUNT = 1201
MAX_DISPLACEMENT_M = (
    1.0  # Existing inferred edge review allowance, not survey accuracy.
)
MAX_CHORD_ERROR_M = 0.02


def xy_digest(sections):
    return hashlib.sha256(
        json.dumps(sections, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


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
        and plan.get("recipe") == RECIPE
        and plan.get("status") == "PASS"
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
        or packet.get("point_type") != "Curve"
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
    boundaries = [[r["edges_xy_m"][side] for r in rows] for side in (0, 1)]
    polygon = Polygon(boundaries[0] + boundaries[1][::-1])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Curved pavement self-intersects or edges cross")
    if any(not LineString(edge).is_simple for edge in boundaries):
        raise ValueError("Curved pavement boundary self-intersects")
    sections, displacement, chord_error, min_area = [], 0.0, 0.0, math.inf
    for index, row in enumerate(rows):
        segment = min(index // 4, STATION_COUNT - 2)
        alpha = (index - segment * 4) / 4
        for side, endpoint in ((0, 0), (1, 24)):
            a, b = (
                source_sections[segment][endpoint],
                source_sections[segment + 1][endpoint],
            )
            reference = [a[k] + (b[k] - a[k]) * alpha for k in range(2)]
            displacement = max(
                displacement, math.dist(reference, row["edges_xy_m"][side])
            )
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
    if displacement > MAX_DISPLACEMENT_M:
        raise ValueError(
            f"Curved edge exceeds 1 m source review allowance: {displacement:.6f} m"
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
    return sections, {
        "recipe": RECIPE,
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
        "human_visual_status": "PENDING",
        "canonical_chainage_preserved": True,
        "presentation_length_is_not_physics_length": True,
    }
