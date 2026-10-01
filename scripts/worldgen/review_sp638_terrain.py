"""BOB's bounded review of existing SP638 geometry against native DTM.

Measurements are YACS Python analysis of the rendered centerline, not features
emitted by PCGEx. This adapter reviews an existing candidate; it does not apply
BOB's proposed parameters or admit learning cases. Units are metres.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from typing import Sequence

from scripts.geometry.sp638_local_corridor import (
    CorridorMesh,
    CrossSectionPoint,
    Vec3,
    minimum_sampled_radius_xy,
)
from scripts.worldgen.adaptive_terrain_solver import (
    BOB_SYSTEM_ID,
    HEIGHTFIELD_STRATEGIES,
    BobTerrainArchitect,
    TerrainFeaturePacket,
    TerrainFeatureProvenance,
    TerrainFeatures,
)


class MissingDtmCoverage(ValueError):
    """A required measurement falls outside the prepared patch."""


def sample_native_height(
    xs: Sequence[float],
    ys: Sequence[float],
    heights: Sequence[Sequence[float]],
    x: float,
    y: float,
) -> float:
    """Bilinear native-grid sample; never clamp an uncovered location."""
    if not xs[0] <= x <= xs[-1] or not ys[-1] <= y <= ys[0]:
        raise MissingDtmCoverage(f"native DTM does not cover ({x:.3f},{y:.3f})")
    fx = (x - xs[0]) / (xs[1] - xs[0])
    fy = (ys[0] - y) / (ys[0] - ys[1])
    column = min(int(math.floor(fx)), len(xs) - 2)
    row = min(int(math.floor(fy)), len(ys) - 2)
    wx, wy = fx - column, fy - row
    value = (
        (1.0 - wy)
        * ((1.0 - wx) * heights[row][column] + wx * heights[row][column + 1])
        + wy
        * ((1.0 - wx) * heights[row + 1][column] + wx * heights[row + 1][column + 1])
    )
    if not math.isfinite(value):
        raise ValueError("native DTM measurement is non-finite")
    return value


def _validate_grid(xs, ys, heights) -> None:
    if len(xs) < 3 or len(ys) < 3 or len(heights) != len(ys):
        raise ValueError("native DTM grid dimensions are invalid")
    if any(len(row) != len(xs) for row in heights):
        raise ValueError("native DTM rows do not match the x axis")
    for axis, direction in ((xs, 1.0), (ys, -1.0)):
        step = direction * (axis[1] - axis[0])
        if not math.isfinite(step) or step <= 0.0:
            raise ValueError("native DTM axis direction is invalid")
        if any(
            not math.isfinite(value)
            or abs(direction * (value - previous) - step) > 1e-6
            for previous, value in zip(axis, axis[1:])
        ):
            raise ValueError("native DTM axes must be finite and uniform")
        if not math.isfinite(axis[0]):
            raise ValueError("native DTM axis is non-finite")


def _nearest_branch(points, distances, index, exclusion_m):
    """Closest non-local segment within this rendered slice, with paired Z."""
    point = points[index]
    nearest = None
    for other, (a, b) in enumerate(zip(points, points[1:])):
        # Exclude the full adjacent arc interval, not only its first endpoint.
        if min(
            abs(distances[other] - distances[index]),
            abs(distances[other + 1] - distances[index]),
        ) < exclusion_m:
            continue
        dx, dy = b.x - a.x, b.y - a.y
        length_squared = dx * dx + dy * dy
        if length_squared <= 1e-12:
            continue
        fraction = max(
            0.0,
            min(1.0, ((point.x - a.x) * dx + (point.y - a.y) * dy) / length_squared),
        )
        xy = math.hypot(point.x - a.x - fraction * dx, point.y - a.y - fraction * dy)
        z = abs(point.z - (a.z + fraction * (b.z - a.z)))
        candidate = (xy, other, z)
        if nearest is None or candidate < nearest:
            nearest = candidate
    return (None, None) if nearest is None else (nearest[0], nearest[2])


def review_existing_corridor(
    *,
    bob: BobTerrainArchitect,
    xs: Sequence[float],
    ys: Sequence[float],
    native_heights: Sequence[Sequence[float]],
    centerline: Sequence[Vec3],
    corridor_mesh: CorridorMesh,
    profiles: Sequence[Sequence[CrossSectionPoint]],
    origin: Vec3,
    exact_sha: str,
    native_binary_sha256: str,
    pcgex_output_sha256: str,
    start_station_m: float,
    sample_step_m: float = 2.0,
    tangent_half_window_stations: int = 3,
    nonlocal_arc_exclusion_m: float = 20.0,
) -> dict:
    """Review each covered station and retain rejects and missing coverage.

The 20 m non-local arc exclusion is an explicit measurement definition, not a
terrain safety threshold. Branch search covers only the supplied render slice.
Roughness is the 3x3 neighbourhood RMS residual from the local tangent plane.
Cut/fill is the road-edge/shoulder envelope; outer zero-weight ties are excluded.
"""
    _validate_grid(xs, ys, native_heights)
    if (
        len(centerline) < 3
        or len(centerline) != corridor_mesh.station_count
        or len(profiles) != len(centerline)
        or len(corridor_mesh.vertices)
        != len(centerline) * corridor_mesh.cross_section_point_count
    ):
        raise ValueError("BOB corridor station/mesh layout mismatch")
    if (
        isinstance(tangent_half_window_stations, bool)
        or not isinstance(tangent_half_window_stations, int)
        or tangent_half_window_stations < 1
        or not math.isfinite(nonlocal_arc_exclusion_m)
        or nonlocal_arc_exclusion_m <= 0.0
        or not math.isfinite(start_station_m)
        or not math.isfinite(sample_step_m) or sample_step_m <= 0.0
    ):
        raise ValueError("BOB measurement scope is invalid")
    world = [Vec3(p.x + origin.x, p.y + origin.y, p.z + origin.z) for p in centerline]
    if any(not all(math.isfinite(v) for v in (p.x, p.y, p.z)) for p in world):
        raise ValueError("BOB centerline contains non-finite values")
    distances = [0.0]
    for a, b in zip(world, world[1:]):
        distances.append(distances[-1] + math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)))
    source_hash = hashlib.sha256(json.dumps(
        {
            "native_binary_sha256": native_binary_sha256,
            "pcgex_output_sha256": pcgex_output_sha256,
            "rendered_centerline": [asdict(p) for p in world],
        }, sort_keys=True, allow_nan=False,
    ).encode()).hexdigest()
    provenance = TerrainFeatureProvenance(
        source_kind="yacs_python_analysis",
        source_artifact_sha256=source_hash,
        source_dataset_id="SP638-rendered-H/native-DTM",
        canonical_road_xy_preserved=True,
        authoritative_route_geometry=False,
        authoritative_physics=False,
    )
    # Verify packet identity even when every station is uncovered.
    if len(exact_sha) != 40 or any(c not in "0123456789abcdef" for c in exact_sha):
        raise ValueError("BOB review requires exact lowercase SHA40")
    for digest in (native_binary_sha256, pcgex_output_sha256):
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("BOB source digest must be lowercase SHA256")

    reports, uncovered, escalations = [], [], []
    width = corridor_mesh.cross_section_point_count
    for index, point in enumerate(world):
        station_m = start_station_m + index * sample_step_m
        try:
            left = max(0, index - tangent_half_window_stations)
            right = min(len(world) - 1, index + tangent_half_window_stations)
            a, b = world[left], world[right]
            span = math.hypot(b.x - a.x, b.y - a.y)
            if span <= 1e-9:
                raise ValueError(f"BOB station {index} has no stable horizontal tangent")
            # Match the existing corridor mesh's signed right frame.
            right_x, right_y = -(b.y - a.y) / span, (b.x - a.x) / span
            def sample(x, y):
                return sample_native_height(xs, ys, native_heights, x, y)
            native = sample(point.x, point.y)
            left_height = sample(point.x - 3.0 * right_x, point.y - 3.0 * right_y)
            right_height = sample(point.x + 3.0 * right_x, point.y + 3.0 * right_y)
            step_x, step_y = xs[1] - xs[0], ys[0] - ys[1]
            gx = (sample(point.x + step_x, point.y) - sample(point.x - step_x, point.y)) / (2 * step_x)
            gy = (sample(point.x, point.y + step_y) - sample(point.x, point.y - step_y)) / (2 * step_y)
            residuals = [
                sample(point.x + dx, point.y + dy) - native - gx * dx - gy * dy
                for dx in (-step_x, 0.0, step_x)
                for dy in (-step_y, 0.0, step_y)
            ]
            envelope = []
            for offset, profile_point in enumerate(profiles[index]):
                if profile_point.role not in {
                    "left_road_edge", "right_road_edge", "left_shoulder", "right_shoulder"
                }:
                    continue
                vertex = corridor_mesh.vertices[index * width + offset]
                envelope.append(abs(vertex.z + origin.z - sample(vertex.x + origin.x, vertex.y + origin.y)))
            if len(envelope) != 4:
                raise ValueError("BOB cut/fill measurement requires four edge/shoulder roles")
            branch_xy, branch_z = _nearest_branch(world, distances, index, nonlocal_arc_exclusion_m)
            window = min(tangent_half_window_stations, index, len(centerline) - 1 - index)
            radius = (
                minimum_sampled_radius_xy(
                    (centerline[index - window], centerline[index], centerline[index + window]),
                    half_window_stations=1,
                ) if window > 0 else None
            )
            features = TerrainFeatures(
                longitudinal_grade=(b.z - a.z) / span,
                left_cross_slope=(left_height - native) / 3.0,
                right_cross_slope=(right_height - native) / 3.0,
                road_to_dtm_delta_m=point.z - native,
                dtm_roughness_m=math.sqrt(sum(r * r for r in residuals) / len(residuals)),
                curvature_radius_m=radius,
                nearest_branch_xy_m=branch_xy,
                nearest_branch_z_separation_m=branch_z,
                max_cut_fill_m=max(envelope),
            )
            report = bob.review(TerrainFeaturePacket(
                corridor_id=f"SP638-H-station-{index:04d}",
                exact_sha=exact_sha, provenance=provenance, features=features,
            ))
            report.update({"station_index": index, "station_m": station_m})
            reports.append(report)
            if report["decision"]["strategy"] not in HEIGHTFIELD_STRATEGIES:
                escalations.append(index)
        except MissingDtmCoverage as exc:
            uncovered.append({"station_index": index, "station_m": station_m, "reason": str(exc)})

    status = "REQUIRES_ESCALATION" if escalations else "INCOMPLETE" if uncovered else "MEASURED"
    return {
        "schema_version": 1,
        "architect": {"name": "BOB", "system_id": BOB_SYSTEM_ID},
        "exact_sha": exact_sha,
        "mode": "review_existing_candidate",
        "parameters_applied": False,
        "status": status,
        "technical_acceptance": "FAIL" if escalations else "PENDING",
        "visual_acceptance": "PENDING_HUMAN_REVIEW",
        "learning_case_promoted": False,
        "measurement_contract": {
            "producer": "yacs_python_analysis",
            "pcgex_feature_emission": False,
            "branch_search_scope": "supplied_render_slice",
            "nonlocal_arc_exclusion_m": nonlocal_arc_exclusion_m,
            "tangent_half_window_stations": tangent_half_window_stations,
            "station_basis": "sampled_render_spline_distance",
            "sample_step_m": sample_step_m,
            "cross_slope_offset_m": 3.0,
            "roughness": "3x3 tangent-plane RMS residual",
            "cut_fill": "native-DTM versus road-edge/shoulder envelope",
            "native_binary_sha256": native_binary_sha256,
            "pcgex_output_sha256": pcgex_output_sha256,
        },
        "station_count": len(centerline),
        "measured_station_count": len(reports),
        "uncovered_stations": uncovered,
        "escalation_station_indices": escalations,
        "strategy_counts": dict(sorted(Counter(r["decision"]["strategy"] for r in reports).items())),
        "max_measured_cut_fill_m": max((r["features"]["max_cut_fill_m"] for r in reports), default=None),
        "decisions": reports,
    }
