"""Continuous source-grounded asphalt with local adaptive conflict intervals.

The accepted 300 m recipe keeps ownership of its footprint. Other pavement is
provisional 5 m. A part is designed once as a continuous axis/profile; recursive
measurement localises only the failing spans. Fixed-size pieces remain technical
patch/streaming units and never decide whether the road is admitted.
No canonical source coordinates, physics data or saved Landscape are modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, Polygon, box, shape
from shapely.ops import substring, transform

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import itertools

from scripts.assets.prepare_ma2141_cut_patch import _decode_height_m, _inside_triangle
from scripts.assets.prepare_ma2141_diagnostic import select_alignment
from scripts.assets.prepare_ma2141_profile import local_linear_fit
from scripts.assets.prepare_ma2141_road_preview import triangle_candidates
from scripts.geometry.bob_vertical_support import build_vertical_support
from scripts.geometry.network_earthworks_diagnostics import (
    height_fit_bounds,
    uniform_height_candidate,
)
from scripts.geometry.network_pavement import (
    PREVIEW_SUPPORT_CAP_M,
    shoulder_sections,
    surface_inspection,
)

from scripts.geometry.network_visual_preview import validate_full_preview

SOURCE = (
    ROOT
    / "worldgen/terrain/benchmarks/sa_calobra/current_landscape_igr_roads_2026-10-03.json"
)
SOURCE_SHA = "0b959ed9ae741d64721669531edd33fac7fe1f1969cd1be58b77785d6eb05ea5"
ANOMALY_REVIEWS = SOURCE.with_name(
    "current_landscape_road_anomaly_reviews_2026-10-03.json"
)
WIDTH = 5.0
SHOULDER = 0.5
STEP = 0.5
CUT_CAP = 1.0
SUPPORT_CAP = PREVIEW_SUPPORT_CAP_M
LATERAL_SWEEP_LIMIT_M = 4.0
LATERAL_SWEEP_STEP_M = 0.25
WIDTH_SENSITIVITY_M = (3.0, 4.0, 5.0)
MIN_CONFLICT_INTERVAL_M = 8.0
CONFLICT_MARGIN_M = 2.0
PATCH_TILE_MAX_M = 100.0
MEASUREMENT_PROBE_MAX_M = 100.0


def adaptive_conflict_intervals(
    stations,
    assessor,
    *,
    minimum_conflict_m=MIN_CONFLICT_INTERVAL_M,
    conflict_margin_m=CONFLICT_MARGIN_M,
    measurement_probe_max_m=MEASUREMENT_PROBE_MAX_M,
):
    """Localise failing spans while preserving full continuous-part coverage.

    Intervals use inclusive station indices and therefore share exactly one
    endpoint. The assessor returns ``status`` (PASS/BLOCKED), diagnostics and an
    optional failure station relative to the inspected interval. Conflict margin
    is applied to segment coverage after localisation, never to source geometry.
    """
    values = np.asarray(stations, dtype=float)
    if (
        values.ndim != 1
        or len(values) < 3
        or not np.isfinite(values).all()
        or (np.diff(values) <= 0).any()
    ):
        raise ValueError("Adaptive stations must be finite and strictly increasing")
    if (
        minimum_conflict_m <= 0
        or conflict_margin_m < 0
        or measurement_probe_max_m < minimum_conflict_m
    ):
        raise ValueError("Adaptive interval limits are invalid")

    raw = []

    def visit(start, end):
        outcome = assessor(start, end)
        if outcome.get("status") not in ("PASS", "BLOCKED"):
            raise ValueError("Adaptive assessor returned an invalid status")
        length = float(values[end] - values[start])
        if outcome["status"] == "PASS" or length <= minimum_conflict_m:
            raw.append({**outcome, "start_index": start, "end_index": end})
            return
        relative = outcome.get("failure_station_index")
        if not isinstance(relative, int) or isinstance(relative, bool):
            pivot = (start + end) // 2
        else:
            pivot = min(max(start + relative, start + 1), end - 1)
        half = max(
            1,
            int(math.ceil(minimum_conflict_m / np.median(np.diff(values)) / 2)),
        )
        core_start = max(start, pivot - half)
        core_end = min(end, pivot + half)
        # Never recurse into a one-segment boundary remainder: every road
        # decision needs at least three stations. Conservatively absorb that
        # sliver into the failing core instead of creating an unmeasurable
        # admitted island at an adaptive partition boundary.
        if 0 < core_start - start < 2:
            core_start = start
        if 0 < end - core_end < 2:
            core_end = end
        if core_start == start and core_end == end:
            split = (start + end) // 2
            if split - start < 2 or end - split < 2:
                raw.append({**outcome, "start_index": start, "end_index": end})
                return
            visit(start, split)
            visit(split, end)
            return
        if core_start > start:
            visit(start, core_start)
        visit(core_start, core_end)
        if core_end < end:
            visit(core_end, end)

    # Bound raster memory with measurement probes. Their seams disappear when
    # segment coverage is rebuilt below, so they are not admission boundaries.
    cursor = 0
    while cursor < len(values) - 1:
        limit = values[cursor] + measurement_probe_max_m
        stop = int(np.searchsorted(values, limit, side="right") - 1)
        stop = min(max(stop, cursor + 2), len(values) - 1)
        remaining = len(values) - 1 - stop
        if 0 < remaining < 2:
            stop -= 2 - remaining
        visit(cursor, stop)
        cursor = stop
    raw.sort(key=lambda item: (item["start_index"], item["end_index"]))

    # Classify segment coverage, then expand only blocked segments by the
    # explicit review margin. This avoids gaps and double-counted length.
    blocked = np.zeros(len(values) - 1, dtype=bool)
    for item in raw:
        if item["status"] == "BLOCKED":
            blocked[item["start_index"] : item["end_index"]] = True
    margin_samples = int(math.ceil(conflict_margin_m / np.median(np.diff(values))))
    if margin_samples and blocked.any():
        indices = np.flatnonzero(blocked)
        expanded = blocked.copy()
        for index in indices:
            expanded[
                max(0, index - margin_samples) : min(
                    len(expanded), index + margin_samples + 1
                )
            ] = True
        blocked = expanded

    def segment_runs(mask):
        groups = []
        run_start = 0
        for index in range(1, len(mask)):
            if mask[index] != mask[run_start]:
                groups.append((run_start, index, bool(mask[run_start])))
                run_start = index
        groups.append((run_start, len(mask), bool(mask[run_start])))
        return groups

    # A road check requires at least three stations (two segments). Absorb any
    # one-segment remainder into conflict evidence instead of inventing a tiny
    # admitted island at a partition boundary.
    while True:
        runs = segment_runs(blocked)
        short = [(a, b) for a, b, _ in runs if b - a < 2]
        if not short:
            break
        for start_segment, end_segment in short:
            blocked[
                max(0, start_segment - 1) : min(len(blocked), end_segment + 1)
            ] = True

    result = []
    for start_segment, end_segment, is_blocked in runs:
        start_index, end_index = start_segment, end_segment
        run_length = float(values[end_index] - values[start_index])
        if run_length <= measurement_probe_max_m + 1e-9:
            outcome = assessor(start_index, end_index)
            evidence_range = [start_index, end_index]
        else:
            components = [
                item
                for item in raw
                if item["end_index"] > start_index
                and item["start_index"] < end_index
                and item["status"] == ("BLOCKED" if is_blocked else "PASS")
            ]
            if is_blocked and components:

                def severity(item):
                    diagnostics = item.get("diagnostics", {})
                    return diagnostics.get("cut_depth", {}).get("max_cut_m", 0.0)

                evidence = max(components, key=severity)
                outcome = {
                    **evidence,
                    "component_interval_count": len(components),
                }
                evidence_range = [
                    evidence["start_index"],
                    evidence["end_index"],
                ]
            else:
                outcome = {
                    "status": "PASS",
                    "reason": None,
                    "failure_station_index": None,
                    "diagnostics": {
                        "stage": "AGGREGATED_CONTINUOUS_PASS",
                        "component_interval_count": len(components),
                    },
                }
                evidence_range = [start_index, end_index]
        # Expansion is conservative; PASS may become BLOCKED, never vice versa.
        status = "BLOCKED" if is_blocked or outcome["status"] == "BLOCKED" else "PASS"
        if is_blocked and outcome["status"] == "PASS":
            # Reassessment cannot erase a conservative conflict margin or an
            # absorbed short interval. Preserve its distinct blocking reason.
            outcome = {
                **outcome,
                "reason": "Conservative conflict margin or absorbed short interval",
                "diagnostics": {
                    **outcome.get("diagnostics", {}),
                    "blocking_basis": "CONSERVATIVE_INTERVAL_EXPANSION",
                    "reassessment_status": "PASS",
                },
            }
        result.append(
            {
                **outcome,
                "status": status,
                "start_index": start_index,
                "end_index": end_index,
                "start_m": float(values[start_index]),
                "end_m": float(values[end_index]),
                "length_m": float(values[end_index] - values[start_index]),
                "evidence_station_range": evidence_range,
                "conflict_margin_m": conflict_margin_m if status == "BLOCKED" else 0.0,
            }
        )
    if not math.isclose(
        sum(item["length_m"] for item in result),
        float(values[-1] - values[0]),
        abs_tol=1e-6,
    ):
        raise ValueError("Adaptive intervals do not cover the continuous part")
    return result


def technical_patch_tiles(start_index, end_index, stations):
    """Split an admitted interval for storage without changing its decision."""
    tiles = []
    cursor = start_index
    while cursor < end_index:
        limit = float(stations[cursor]) + PATCH_TILE_MAX_M
        stop = int(np.searchsorted(stations, limit, side="right") - 1)
        stop = min(max(stop, cursor + 2), end_index)
        remaining = end_index - stop
        if 0 < remaining < 2:
            stop -= 2 - remaining
        tiles.append((cursor, stop))
        cursor = stop
    return tiles


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "LineString":
        return [geometry]
    return [g for g in geometry.geoms if g.geom_type == "LineString"]


def smooth_axis(line, spacing=4.0):
    """Uniform cubic B-spline control envelope, evaluated offline into buffers.

    Same convex cubic family as the accepted bend; no runtime curve authority.
    Independent checks of both offsets reject a pinched inner edge/short hook.
    """
    keys = np.linspace(0, line.length, max(4, math.ceil(line.length / spacing) + 1))
    raw = np.array([line.interpolate(s).coords[0][:2] for s in keys])
    controls = np.vstack([2 * raw[0] - raw[1], raw, 2 * raw[-1] - raw[-2]])
    count = math.ceil(line.length / STEP)
    stations = np.linspace(0, line.length, count + 1)
    key = stations / keys[1]
    integer = np.minimum(np.floor(key).astype(int), len(raw) - 2)
    u = key - integer
    weights = (
        np.array(
            [
                (1 - u) ** 3,
                3 * u**3 - 6 * u * u + 4,
                -3 * u**3 + 3 * u * u + 3 * u + 1,
                u**3,
            ]
        ).T
        / 6
    )
    xy = sum(weights[:, j, None] * controls[integer + j] for j in range(4))
    return stations, xy


def turns(points):
    a, b = np.diff(points, axis=0)[:-1], np.diff(points, axis=0)[1:]
    lengths = np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)
    if (lengths <= 1e-12).any():
        raise ValueError("Boundary stops or reverses")
    return np.arctan2(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0], np.sum(a * b, axis=1))


def inspect_sections(sections, source_line, *, source_displacement_cap_m=1.0):
    xy = np.asarray(sections)[:, :, :2]
    left, right = xy[:, 0], xy[:, -1]
    axis = (left + right) / 2
    widths = np.linalg.norm(right - left, axis=1)
    if np.max(abs(widths - WIDTH)) > 0.0001:
        raise ValueError("Nonconstant asphalt width")
    ring = Polygon(np.vstack([left, right[::-1]]))
    if (
        not ring.is_valid
        or not LineString(left).is_simple
        or not LineString(right).is_simple
    ):
        raise ValueError("Pavement intersects/folds")
    center_turn = turns(axis)
    source_points = np.asarray(source_line.coords)[:, :2]
    source_turn = turns(source_points) if len(source_points) > 2 else np.array([])
    significant = source_turn[abs(source_turn) > 1e-4]
    single_sign = (
        int(np.sign(significant[0]))
        if len(significant) and np.all(np.sign(significant) == np.sign(significant[0]))
        else 0
    )
    if single_sign and np.sum(abs(significant)) > math.radians(30):
        for curve in (left, right, axis):
            lengths = np.linalg.norm(np.diff(curve, axis=0), axis=1)
            tolerance = 0.0004 * (1 / lengths[:-1] + 1 / lengths[1:])
            if (turns(curve) * single_sign < -tolerance).any():
                raise ValueError(
                    "Single source bend has a counter-turn in final boundary/axis"
                )
    # Every original segment is checked; a hook cannot disappear by averaging.
    for edge in (left, right):
        t = turns(edge)
        tolerance = 0.0008 / np.minimum(
            np.linalg.norm(np.diff(edge, axis=0), axis=1)[:-1],
            np.linalg.norm(np.diff(edge, axis=0), axis=1)[1:],
        )
        if ((t * np.sign(center_turn) < -tolerance) & (abs(center_turn) > 1e-5)).any():
            raise ValueError("Pavement counter-turns relative to bend")
        segments = np.linalg.norm(np.diff(edge, axis=0), axis=1)
        radius = (segments[:-1] + segments[1:]) / 2 / np.maximum(abs(t), 1e-12)
        if radius.min() < 1.5:
            raise ValueError("Inner radius below accepted minimum")
    displacement = source_line.hausdorff_distance(LineString(axis))
    if (
        source_displacement_cap_m is not None
        and displacement > source_displacement_cap_m
    ):
        raise ValueError(
            "Source displacement exceeds "
            f"{source_displacement_cap_m:g} m ({displacement:.3f})"
        )
    for a, b in itertools.pairwise(xy):
        for j in range(len(a) - 1):
            for p, q, r in ((a[j], a[j + 1], b[j]), (a[j + 1], b[j + 1], b[j])):
                if (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (
                    r[0] - p[0]
                ) >= -1e-9:
                    raise ValueError("Folded asphalt facet")
    return {
        "width_min_m": float(widths.min()),
        "width_max_m": float(widths.max()),
        "source_displacement_m": displacement,
        "both_edges_checked": True,
    }


def native_ground(heights, manifest, points):
    result = []
    for x, y in np.asarray(points).reshape(-1, 2):
        # Reuse the independently proved native triangle diagonal (not bilinear).
        candidates = triangle_candidates(
            heights,
            manifest,
            manifest["origin_epsg_m"][0] + x,
            manifest["origin_epsg_m"][1] - y,
        )
        result.append(candidates[0])
    return np.asarray(result).reshape(np.asarray(points).shape[:-1])


def _cut_depth_summary(base, patch, rect, sections):
    depth = base - patch
    minx, miny, _, _ = rect
    peak_y, peak_x = np.unravel_index(np.argmax(depth), depth.shape)
    grid_x, grid_y = minx + int(peak_x), miny + int(peak_y)
    section_xy = np.asarray(sections, dtype=float)[:, :, :2]
    distances = np.linalg.norm(
        section_xy - np.array([grid_x * STEP, grid_y * STEP]), axis=2
    )
    station_index, transverse_index = np.unravel_index(
        np.argmin(distances), distances.shape
    )
    positive = depth[depth > 0]
    return {
        "max_cut_m": float(depth[peak_y, peak_x]),
        "p95_positive_cut_m": float(np.percentile(positive, 95))
        if positive.size
        else 0.0,
        "positive_cut_cell_count": int(positive.size),
        "over_cap_cell_count": int(np.count_nonzero(depth > CUT_CAP)),
        "peak_grid_xy": [grid_x, grid_y],
        "peak_local_xy_m": [grid_x * STEP, grid_y * STEP],
        "peak_base_height_m": float(base[peak_y, peak_x]),
        "peak_target_height_m": float(patch[peak_y, peak_x]),
        "nearest_station_index": int(station_index),
        "nearest_transverse_index": int(transverse_index),
        "nearest_section_distance_m": float(
            distances[station_index, transverse_index]
        ),
    }


def measure_patch(
    sections,
    terrain,
    manifest,
    *,
    include_interpolation_corners=True,
    guard_cells=1,
):
    """Measure raster CUT; defaults reproduce the authored patch envelope."""
    if (
        not isinstance(guard_cells, int)
        or isinstance(guard_cells, bool)
        or guard_cells < 0
    ):
        raise ValueError("CUT guard cell count must be a nonnegative integer")
    samples = {}
    for a, b in itertools.pairwise(sections):
        for j in range(len(a) - 1):
            for tri in ((a[j], a[j + 1], b[j]), (a[j + 1], b[j + 1], b[j])):
                for gy in range(
                    math.floor(min(p[1] for p in tri) / STEP),
                    math.ceil(max(p[1] for p in tri) / STEP) + 1,
                ):
                    for gx in range(
                        math.floor(min(p[0] for p in tri) / STEP),
                        math.ceil(max(p[0] for p in tri) / STEP) + 1,
                    ):
                        z = _inside_triangle(gx * STEP, gy * STEP, tri)
                        if z is not None:
                            samples[gx, gy] = min(
                                samples.get((gx, gy), math.inf), z - 0.05
                            )
    if include_interpolation_corners:
        for row in sections:
            for x, y, z in row:
                gx, gy = math.floor(x / STEP), math.floor(y / STEP)
                for dx in (0, 1):
                    for dy in (0, 1):
                        samples[gx + dx, gy + dy] = min(
                            samples.get((gx + dx, gy + dy), math.inf), z - 0.05
                        )
    # The authored patch keeps one same-height raster guard around its sampled
    # pavement/shoulder footprint. The rectangle's outer cell remains neutral.
    for _ in range(guard_cells):
        for (gx, gy), z in list(samples.items()):
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    samples[gx + dx, gy + dy] = min(
                        samples.get((gx + dx, gy + dy), math.inf), z
                    )
    minx, miny = min(x for x, y in samples) - 1, min(y for x, y in samples) - 1
    maxx, maxy = max(x for x, y in samples) + 1, max(y for x, y in samples) + 1
    if minx < 0 or miny < 0 or maxx > 4032 or maxy > 4032:
        raise ValueError("CUT footprint outside existing Landscape")
    base = (
        _decode_height_m(0, manifest)
        + terrain[miny : maxy + 1, minx : maxx + 1].astype(float)
        * manifest["scale_z"]
        / 12800
    )
    patch = base.copy()
    for (x, y), target in samples.items():
        patch[y - miny, x - minx] = min(patch[y - miny, x - minx], target)
    rect = (minx, miny, maxx, maxy)
    depth = base - patch
    return {
        "base": base,
        "patch": patch,
        "depth": depth,
        "rect": rect,
        "cut_depth": _cut_depth_summary(base, patch, rect, sections),
    }


def measure_cut_envelopes(asphalt, shoulders, terrain, manifest):
    """Separate physical footprints from the authored interpolation guard."""
    strict_asphalt = measure_patch(
        asphalt,
        terrain,
        manifest,
        include_interpolation_corners=False,
        guard_cells=0,
    )["cut_depth"]
    strict_shoulders = measure_patch(
        shoulders,
        terrain,
        manifest,
        include_interpolation_corners=False,
        guard_cells=0,
    )["cut_depth"]
    authored = measure_patch(shoulders, terrain, manifest)["cut_depth"]
    return {
        "asphalt": strict_asphalt,
        "asphalt_and_shoulders": strict_shoulders,
        "authored_patch_envelope": authored,
        "admission_envelope": "authored_patch_envelope",
    }


def prepare_patch(
    sections, terrain, manifest, path, *, diagnostics=None, asphalt_sections=None,
    reviewed_geometry=False
):
    measured = measure_patch(sections, terrain, manifest)
    base, patch, depth = measured["base"], measured["patch"], measured["depth"]
    minx, miny, maxx, maxy = measured["rect"]
    if diagnostics is not None:
        diagnostics["cut_depth"] = measured["cut_depth"]
        if asphalt_sections is not None:
            diagnostics["cut_depth_by_envelope"] = measure_cut_envelopes(
                asphalt_sections, sections, terrain, manifest
            )
        diagnostics["earthworks_fit"] = height_fit_bounds(
            float(depth.max()),
            diagnostics["max_core_support_m"],
            diagnostics["max_shoulder_support_m"],
            cut_cap_m=CUT_CAP,
            support_cap_m=SUPPORT_CAP,
        )
    if depth.max() > CUT_CAP and not reviewed_geometry:
        raise ValueError(f"Ordinary 1 m CUT cap exceeded ({depth.max():.3f})")
    patch = (patch * 100).astype("<f4")
    patch.tofile(path.with_suffix(".f32"))
    payload = {
        "schema_version": 1,
        "region_id": "sa_calobra",
        "operation": "CUT_ONLY",
        "layer": "Road_Earthworks",
        "layer_encoding": "LANDSCAPE_TEXTURE_PATCH_WORLD_UNITS_F32_MIN",
        "blend_mode": "Min",
        "height_encoding": "WorldUnits",
        "zero_height_meaning": "WorldZero",
        "world_space_unit": "centimeter",
        "base_layer": "Base_DTM",
        "base_dtm_modified": False,
        "fill_authoring_permitted": False,
        "structure_authoring_permitted": False,
        "save_map": False,
        "patch_file": path.with_suffix(".f32").name,
        "patch_sha256": digest(path.with_suffix(".f32")),
        "max_cut_m": float(depth.max()),
        "owner_reviewed_geometry": reviewed_geometry,
        "rect": {
            "min_x": minx,
            "min_y": miny,
            "max_x": maxx,
            "max_y": maxy,
            "width": maxx - minx + 1,
            "height": maxy - miny + 1,
        },
    }
    path.write_text(json.dumps(payload) + "\n")
    return payload


def assess_height_profile_candidate(part, terrain, manifest, diagnostics):
    """Remeasure a bounded Z candidate without authoring or admitting it."""
    candidate = uniform_height_candidate(diagnostics["earthworks_fit"])
    if not candidate["bounds_overlap"]:
        return candidate
    lift = candidate["candidate_lift_m"]
    try:
        shifted = np.asarray(part, dtype=float).copy()
        shifted[:, :, 2] += lift
        surface = surface_inspection(shifted.tolist())
        support = shoulder_sections(shifted.tolist())
        outer_ground = native_ground(
            terrain, manifest, np.asarray(support)[:, [0, -1], :2]
        )
        _, _, support_proof = build_vertical_support(support, outer_ground.tolist())
        measured = measure_patch(np.asarray(support), terrain, manifest)
        max_core_support = diagnostics["max_core_support_m"] + lift
        max_shoulder_support = float(
            np.max(np.asarray(support)[:, [0, -1], 2] - outer_ground)
        )
    except ValueError as exc:
        candidate.update(
            {
                "status": "REJECT_LOCAL_REMEASUREMENT",
                "local_numeric_checks_pass": False,
                "rejection_reason": str(exc),
            }
        )
        return candidate
    local_pass = (
        measured["cut_depth"]["max_cut_m"] <= CUT_CAP
        and max_core_support <= SUPPORT_CAP
        and max_shoulder_support <= SUPPORT_CAP
        and support_proof["max_wall_height_m"] <= SUPPORT_CAP
        and surface["status"] == "PASS"
    )
    candidate.update(
        {
            "status": "LOCAL_NUMERIC_PASS_SOURCE_AND_JOINS_UNVERIFIED"
            if local_pass
            else "REJECT_LOCAL_REMEASUREMENT",
            "local_numeric_checks_pass": local_pass,
            "candidate_cut_depth": measured["cut_depth"],
            "candidate_max_core_support_m": float(max_core_support),
            "candidate_max_shoulder_support_m": max_shoulder_support,
            "candidate_support_proof": support_proof,
            "candidate_surface_inspection": surface,
        }
    )
    return candidate


def resize_sections_width(sections, width_m):
    """Create a centred width counterfactual without changing the source axis."""
    values = np.asarray(sections, dtype=float)
    if values.ndim != 3 or values.shape[1] < 2 or values.shape[2] != 3:
        raise ValueError("Road sections must be an NxMx3 array")
    widths = np.linalg.norm(values[:, -1, :2] - values[:, 0, :2], axis=1)
    if width_m <= 0 or width_m > float(widths.min()) + 1e-9:
        raise ValueError("Width counterfactual must fit inside existing pavement")
    result = np.empty_like(values)
    sample_t = np.linspace(0.0, 1.0, values.shape[1])
    target_offset = np.linspace(-width_m / 2, width_m / 2, values.shape[1])
    for index, row in enumerate(values):
        axis = (row[0, :2] + row[-1, :2]) / 2
        across = (row[-1, :2] - row[0, :2]) / widths[index]
        target_t = 0.5 + target_offset / widths[index]
        result[index, :, :2] = axis + target_offset[:, None] * across
        result[index, :, 2] = np.interp(target_t, sample_t, row[:, 2])
    return result


def shift_sections_laterally(sections, shift_m):
    """Shift a road cross-section toward its stored final transverse edge."""
    values = np.asarray(sections, dtype=float)
    result = values.copy()
    across = values[:, -1, :2] - values[:, 0, :2]
    lengths = np.linalg.norm(across, axis=1)
    if (lengths <= 0).any() or not np.isfinite(lengths).all():
        raise ValueError("Road transverse direction is invalid")
    result[:, :, :2] += across[:, None, :] / lengths[:, None, None] * shift_m
    return result


def width_sensitivity(sections, terrain, manifest):
    """Measure whether width alone can clear terrain; never admit a width change."""
    candidates = []
    for width_m in WIDTH_SENSITIVITY_M:
        candidate = resize_sections_width(sections, width_m)
        cut = measure_patch(
            candidate,
            terrain,
            manifest,
            include_interpolation_corners=False,
            guard_cells=0,
        )["cut_depth"]
        candidates.append(
            {
                "width_m": width_m,
                "strict_asphalt_cut_depth": cut,
                "ordinary_cut_pass": cut["max_cut_m"] <= CUT_CAP,
                "width_change_applied": False,
                "road_admitted": False,
            }
        )
    return {
        "method": "CENTRED_WIDTH_COUNTERFACTUAL_DIAGNOSTIC_ONLY",
        "candidates": candidates,
        "any_width_passes_ordinary_cut": any(
            candidate["ordinary_cut_pass"] for candidate in candidates
        ),
        "source_width_verified": False,
        "width_change_applied": False,
        "road_admitted": False,
    }


def assess_lateral_sweep(sections, source_line, terrain, manifest):
    """Remeasure bounded XY shifts without applying or admitting a repair."""
    candidates = []
    shifts = np.arange(
        -LATERAL_SWEEP_LIMIT_M,
        LATERAL_SWEEP_LIMIT_M + LATERAL_SWEEP_STEP_M / 2,
        LATERAL_SWEEP_STEP_M,
    )
    for shift_m in shifts:
        candidate = {"shift_m": float(round(shift_m, 10))}
        try:
            shifted = shift_sections_laterally(sections, shift_m)
            metrics = inspect_sections(
                shifted, source_line, source_displacement_cap_m=None
            )
            surface = surface_inspection(shifted.tolist())
            support = np.asarray(shoulder_sections(shifted.tolist()), dtype=float)
            asphalt_ground = native_ground(
                terrain, manifest, shifted[:, :, :2]
            )
            outer_ground = native_ground(
                terrain, manifest, support[:, [0, -1], :2]
            )
            _, _, support_proof = build_vertical_support(
                support.tolist(), outer_ground.tolist()
            )
            cuts = measure_cut_envelopes(shifted, support, terrain, manifest)
            max_core_support = float(
                np.max(shifted[:, :, 2] - asphalt_ground)
            )
            max_shoulder_support = float(
                np.max(support[:, [0, -1], 2] - outer_ground)
            )
            violations = {
                "cut_excess_m": max(
                    0.0,
                    cuts["authored_patch_envelope"]["max_cut_m"] - CUT_CAP,
                ),
                "core_support_excess_m": max(
                    0.0, max_core_support - SUPPORT_CAP
                ),
                "shoulder_support_excess_m": max(
                    0.0,
                    max(
                        max_shoulder_support,
                        support_proof["max_wall_height_m"],
                    )
                    - SUPPORT_CAP,
                ),
                "source_displacement_excess_m": max(
                    0.0, metrics["source_displacement_m"] - 1.0
                ),
            }
            numeric_pass = (
                not any(value > 1e-9 for value in violations.values())
                and surface["status"] == "PASS"
            )
            candidate.update(
                {
                    "status": "LOCAL_NUMERIC_PASS_EVIDENCE_AND_JOINS_UNVERIFIED"
                    if numeric_pass
                    else "REJECT_LOCAL_NUMERIC_LIMITS",
                    "local_numeric_checks_pass": numeric_pass,
                    "source_displacement_m": metrics["source_displacement_m"],
                    "cut_depth_by_envelope": cuts,
                    "max_core_support_m": max_core_support,
                    "max_shoulder_support_m": max_shoulder_support,
                    "support_proof": support_proof,
                    "surface_inspection": surface,
                    "violations": violations,
                }
            )
        except ValueError as exc:
            candidate.update(
                {
                    "status": "REJECT_LOCAL_REMEASUREMENT",
                    "local_numeric_checks_pass": False,
                    "rejection_reason": str(exc),
                }
            )
        candidate.update(
            {
                "lateral_change_applied": False,
                "source_alignment_verified": False,
                "adjacent_joins_verified": False,
                "road_admitted": False,
            }
        )
        candidates.append(candidate)

    def rank(candidate):
        if "violations" not in candidate:
            return (1, math.inf, math.inf, math.inf)
        return (
            candidate["surface_inspection"]["status"] != "PASS",
            max(candidate["violations"].values()),
            candidate["cut_depth_by_envelope"]["asphalt"]["max_cut_m"],
            abs(candidate["shift_m"]),
        )

    best = min(candidates, key=rank)
    return {
        "method": "BOUNDED_LATERAL_TRANSLATION_DIAGNOSTIC_ONLY",
        "shift_range_m": [-LATERAL_SWEEP_LIMIT_M, LATERAL_SWEEP_LIMIT_M],
        "shift_step_m": LATERAL_SWEEP_STEP_M,
        "positive_direction": "TOWARD_STORED_FINAL_TRANSVERSE_EDGE",
        "candidate_count": len(candidates),
        "locally_numeric_pass_count": sum(
            candidate.get("local_numeric_checks_pass", False)
            for candidate in candidates
        ),
        "best_candidate_selection": "SURFACE_PASS_THEN_MINIMAX_LIMIT_EXCESS_METRES",
        "best_candidate": best,
        "candidates": candidates,
        "lateral_change_applied": False,
        "source_alignment_verified": False,
        "adjacent_joins_verified": False,
        "road_admitted": False,
    }


def _reviewed_anomaly(window_id, hotspot_wgs84):
    payload = json.loads(ANOMALY_REVIEWS.read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != 1
        or payload.get("road_source_sha256") != SOURCE_SHA
        or not isinstance(payload.get("reviews"), list)
    ):
        raise ValueError("Road anomaly review evidence is invalid")
    matches = [
        review for review in payload["reviews"] if review.get("window_id") == window_id
    ]
    if len(matches) > 1:
        raise ValueError("Road anomaly review evidence is duplicated")
    if not matches:
        return None
    review = matches[0]
    expected = review.get("hotspot_wgs84")
    if not isinstance(expected, list) or len(expected) != 2:
        raise ValueError("Road anomaly hotspot evidence is invalid")
    to_metric = Transformer.from_crs(4326, 25831, always_xy=True)
    measured_xy = to_metric.transform(*hotspot_wgs84)
    expected_xy = to_metric.transform(*expected)
    if math.dist(measured_xy, expected_xy) > 5.0:
        raise ValueError("Road anomaly evidence does not match measured hotspot")
    panorama = review.get("panorama")
    if (
        review.get("classification")
        not in ("NATURAL_FEATURE_CONFIRMED", "ALGORITHM_SUSPECT", "UNRESOLVED")
        or not isinstance(panorama, dict)
        or not isinstance(panorama.get("url"), str)
        or not panorama["url"].startswith("https://www.google.com/maps/")
        or review.get("metric_width_admitted") is not False
        or review.get("metric_cut_admitted") is not False
        or review.get("road_geometry_admitted") is not False
    ):
        raise ValueError("Road anomaly qualitative review contract is invalid")
    return review


def build_extreme_review(case, manifest):
    cut = case["cut_depth"]
    sections = np.asarray(case["sections"], dtype=float)
    station = min(cut["nearest_station_index"], len(sections) - 1)
    axis = (sections[station, 0, :2] + sections[station, -1, :2]) / 2
    across = sections[station, -1, :2] - sections[station, 0, :2]
    across /= np.linalg.norm(across)
    peak = np.asarray(cut["peak_local_xy_m"], dtype=float)
    signed_offset = float(np.dot(peak - axis, across))
    east_m = manifest["origin_epsg_m"][0] + peak[0]
    north_m = manifest["origin_epsg_m"][1] - peak[1]
    lon, lat = Transformer.from_crs(25831, 4326, always_xy=True).transform(
        east_m, north_m
    )
    hotspot_wgs84 = [float(lon), float(lat)]
    reviewed = _reviewed_anomaly(
        case.get("review_evidence_id", case["id"]), hotspot_wgs84
    )
    default_url = (
        "https://www.google.com/maps/@?api=1&map_action=pano&viewpoint="
        f"{lat:.8f}%2C{lon:.8f}"
    )
    return {
        "classification": reviewed["classification"] if reviewed else "UNRESOLVED",
        "hotspot_wgs84": hotspot_wgs84,
        "peak_signed_transverse_offset_m": signed_offset,
        "peak_distance_from_axis_m": abs(signed_offset),
        "peak_beyond_asphalt_edge_m": abs(signed_offset) - WIDTH / 2,
        "peak_beyond_shoulder_edge_m": abs(signed_offset) - WIDTH / 2 - SHOULDER,
        "rock_side": "POSITIVE_TRANSVERSE"
        if signed_offset >= 0
        else "NEGATIVE_TRANSVERSE",
        "away_from_rock_shift_sign": -1 if signed_offset >= 0 else 1,
        "street_view_url": reviewed["panorama"]["url"]
        if reviewed
        else default_url,
        "manual_evidence": reviewed,
        "anomaly_reviews_sha256": digest(ANOMALY_REVIEWS),
        "metric_cut_verified_by_street_view": False,
        "metric_width_verified_by_street_view": False,
        "road_admitted": False,
    }


def write_extreme_cut_review(case, path):
    review = case["review"]
    cuts = case["cut_depth_by_envelope"]
    width = case["width_sensitivity"]
    lateral = case["lateral_sweep"]
    best = lateral["best_candidate"]
    lines = [
        f"# Extreme road/terrain review: `{case['id']}`",
        "",
        f"- Classification: `{review['classification']}`",
        f"- Hotspot WGS84: `{review['hotspot_wgs84'][1]:.8f}, {review['hotspot_wgs84'][0]:.8f}`",
        f"- [Interactive Street View]({review['street_view_url']})",
        f"- Authored patch-envelope CUT: `{cuts['authored_patch_envelope']['max_cut_m']:.4f} m`",
        f"- Strict asphalt CUT: `{cuts['asphalt']['max_cut_m']:.4f} m`",
        f"- Strict asphalt + shoulders CUT: `{cuts['asphalt_and_shoulders']['max_cut_m']:.4f} m`",
        f"- Peak distance from axis: `{review['peak_distance_from_axis_m']:.4f} m`",
        f"- Peak beyond asphalt edge: `{review['peak_beyond_asphalt_edge_m']:.4f} m`",
        f"- Peak beyond shoulder edge: `{review['peak_beyond_shoulder_edge_m']:.4f} m`",
        "",
        "## Counterfactual checks",
        "",
        "- Width-only candidates passing the ordinary CUT cap: "
        f"`{sum(c['ordinary_cut_pass'] for c in width['candidates'])}/"
        f"{len(width['candidates'])}`",
        "- Lateral candidates passing all local numeric limits: "
        f"`{lateral['locally_numeric_pass_count']}/"
        f"{lateral['candidate_count']}`",
        f"- Least-bad lateral shift: `{best['shift_m']:.2f} m` (`{best['status']}`)",
        "",
        "No width, height or lateral change was applied. Source alignment, "
        "adjacent joins, collision and road admission remain unverified.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_extreme_cut_diagnostic(case, path):
    """Write a deterministic plan/depth image for chat and artifact review."""
    from PIL import Image, ImageDraw

    width, height = 1600, 900
    image = Image.new("RGB", (width, height), (22, 27, 34))
    draw = ImageDraw.Draw(image)
    red, yellow, cyan = (232, 62, 44), (255, 204, 38), (45, 210, 230)
    white, muted = (245, 247, 250), (167, 178, 194)
    cut = case["cut_depth"]
    sections = np.asarray(case["sections"], dtype=float)
    left, right = sections[:, 0, :2], sections[:, -1, :2]
    best = case["lateral_sweep"]["best_candidate"]
    shifted = shift_sections_laterally(sections, best["shift_m"])
    shifted_left, shifted_right = shifted[:, 0, :2], shifted[:, -1, :2]
    all_xy = np.vstack(
        [
            left,
            right,
            shifted_left,
            shifted_right,
            np.asarray([cut["peak_local_xy_m"]]),
        ]
    )
    low, high = all_xy.min(axis=0), all_xy.max(axis=0)
    span = np.maximum(high - low, 1.0)
    plan_box = (70, 150, 960, 820)
    scale = min(
        (plan_box[2] - plan_box[0] - 60) / span[0],
        (plan_box[3] - plan_box[1] - 60) / span[1],
    )

    def plan_point(point):
        x = plan_box[0] + 30 + (point[0] - low[0]) * scale
        y = plan_box[3] - 30 - (point[1] - low[1]) * scale
        return (float(x), float(y))

    draw.text((70, 45), "EXTREME CUT - REJECTED", fill=red)
    draw.text(
        (70, 80),
        f"{case['id']}  patch-envelope CUT {cut['max_cut_m']:.2f} m",
        fill=white,
    )
    draw.text(
        (70, 108),
        "Red: rejected asphalt | Cyan: least-bad lateral diagnostic | Yellow: CUT peak",
        fill=muted,
    )
    draw.rectangle(plan_box, outline=(70, 82, 98), width=2)
    draw.text((plan_box[0] + 15, plan_box[1] + 12), "PLAN", fill=muted)
    draw.line([plan_point(p) for p in left], fill=red, width=5)
    draw.line([plan_point(p) for p in right], fill=red, width=5)
    draw.line(
        [plan_point(p) for p in (left + right) / 2], fill=(150, 44, 38), width=2
    )
    draw.line([plan_point(p) for p in shifted_left], fill=cyan, width=3)
    draw.line([plan_point(p) for p in shifted_right], fill=cyan, width=3)
    hx, hy = plan_point(cut["peak_local_xy_m"])
    draw.ellipse((hx - 11, hy - 11, hx + 11, hy + 11), fill=yellow)

    gauge_x, gauge_top, gauge_bottom = 1240, 210, 720
    draw.text((1050, 155), "MEASURED DEPTH", fill=muted)
    draw.line((1030, gauge_top, 1450, gauge_top), fill=white, width=4)
    draw.text(
        (1050, gauge_top - 30),
        f"Base terrain {cut['peak_base_height_m']:.2f} m",
        fill=white,
    )
    draw.line((gauge_x, gauge_top, gauge_x, gauge_bottom), fill=yellow, width=18)
    draw.line((1030, gauge_bottom, 1450, gauge_bottom), fill=red, width=4)
    draw.text(
        (1050, gauge_bottom + 18),
        f"Patch target {cut['peak_target_height_m']:.2f} m",
        fill=red,
    )
    draw.text(
        (1280, (gauge_top + gauge_bottom) / 2 - 10),
        f"{cut['max_cut_m']:.2f} m",
        fill=yellow,
    )
    envelopes = case["cut_depth_by_envelope"]
    draw.text(
        (1050, 760),
        f"Strict asphalt: {envelopes['asphalt']['max_cut_m']:.2f} m",
        fill=white,
    )
    draw.text(
        (1050, 790),
        "Lateral: "
        f"{case['lateral_sweep']['locally_numeric_pass_count']}/"
        f"{case['lateral_sweep']['candidate_count']} pass; "
        f"best {best['shift_m']:+.2f} m",
        fill=white,
    )
    draw.text(
        (1050, 820),
        f"Class: {case['review']['classification']} | No repair applied",
        fill=muted,
    )
    image.save(path, format="PNG", optimize=False)


def assess_network_interval(
    start, end, s, sections, center, bank, line, terrain, manifest, origin
):
    """Measure one interval of an already-authored continuous road part."""
    if end - start < 2:
        raise ValueError("Road decision interval needs at least three stations")
    source_window = substring(line, float(s[start]), float(s[end]))
    source_window_local = transform(
        lambda x, y, z=None: (x - origin[0], origin[1] - y),
        source_window,
    )
    part = sections[start : end + 1]
    diagnostics = {
        "stage": "PLANAR_GEOMETRY",
        "continuous_part_station_range": [int(start), int(end)],
    }
    failure_station_index = None
    try:
        metrics = inspect_sections(part, source_window_local)
        diagnostics.update(metrics)
        diagnostics["stage"] = "GRADE_AND_BANK"
        grades = abs(
            np.diff(center[start : end + 1]) / np.diff(s[start : end + 1])
        )
        bank_rates = abs(
            np.diff(bank[start : end + 1]) / np.diff(s[start : end + 1])
        )
        diagnostics["max_grade_abs"] = float(grades.max())
        diagnostics["max_bank_rate_per_m"] = float(bank_rates.max())
        if grades.max() > 0.31:
            failure_station_index = int(np.argmax(grades))
            raise ValueError("Road grade exceeds reviewed preview limit")
        if bank_rates.max() > 0.004:
            failure_station_index = int(np.argmax(bank_rates))
            raise ValueError("Banking transition exceeds reviewed rate")

        asphalt_ground = native_ground(terrain, manifest, part[:, :, :2])
        delta = part[:, :, 2] - asphalt_ground
        diagnostics["stage"] = "CORE_SUPPORT"
        diagnostics["max_core_support_m"] = float(delta.max())
        if delta.max() > SUPPORT_CAP:
            failure_station_index = int(
                np.unravel_index(np.argmax(delta), delta.shape)[0]
            )
            raise ValueError("Support height needs structure review")

        surface = surface_inspection(part.tolist())
        diagnostics["stage"] = "SURFACE_3D"
        diagnostics["surface_inspection"] = surface
        if surface["status"] != "PASS":
            raise ValueError("Accepted 3D road surface limits exceeded")

        support = np.asarray(shoulder_sections(part.tolist()), dtype=float)
        outer_ground = native_ground(terrain, manifest, support[:, [0, -1], :2])
        _, _, support_proof = build_vertical_support(
            support.tolist(), outer_ground.tolist()
        )
        shoulder_delta = support[:, [0, -1], 2] - outer_ground
        diagnostics["stage"] = "SHOULDER_SUPPORT"
        diagnostics["max_shoulder_wall_m"] = support_proof["max_wall_height_m"]
        diagnostics["max_shoulder_support_m"] = float(shoulder_delta.max())
        if support_proof["max_wall_height_m"] > SUPPORT_CAP:
            failure_station_index = int(
                np.unravel_index(np.argmax(shoulder_delta), shoulder_delta.shape)[0]
            )
            raise ValueError("Shoulder support needs structure review")

        diagnostics["stage"] = "RASTER_CUT"
        measured = measure_patch(support, terrain, manifest)
        diagnostics["cut_depth"] = measured["cut_depth"]
        diagnostics["earthworks_fit"] = height_fit_bounds(
            measured["cut_depth"]["max_cut_m"],
            diagnostics["max_core_support_m"],
            diagnostics["max_shoulder_support_m"],
            cut_cap_m=CUT_CAP,
            support_cap_m=SUPPORT_CAP,
        )
        if measured["cut_depth"]["max_cut_m"] > CUT_CAP:
            failure_station_index = measured["cut_depth"]["nearest_station_index"]
            raise ValueError(
                "Ordinary 1 m CUT cap exceeded "
                f"({measured['cut_depth']['max_cut_m']:.3f})"
            )
        return {
            "status": "PASS",
            "reason": None,
            "failure_station_index": None,
            "diagnostics": diagnostics,
        }
    except ValueError as exc:
        if failure_station_index is None and "cut_depth" in diagnostics:
            failure_station_index = diagnostics["cut_depth"]["nearest_station_index"]
        return {
            "status": "BLOCKED",
            "reason": str(exc),
            "failure_station_index": failure_station_index,
            "diagnostics": diagnostics,
        }


def write_full_preview_plan(network, path):
    """Show complete source coverage and admission decisions in one review image."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1800, 1800), (23, 29, 35))
    draw = ImageDraw.Draw(image)
    preview = network["full_preview"]
    points = [p for marker in preview["source_markers"] for p in marker["xy_local_m"]]
    minx, miny = np.min(points, axis=0)
    maxx, maxy = np.max(points, axis=0)
    scale = min(1600 / max(maxx-minx, 1), 1500 / max(maxy-miny, 1))

    def pixel(p):
        return (100 + (p[0]-minx)*scale, 200 + (p[1]-miny)*scale)

    draw.text((60, 35), "FULL SOURCE CONTEXT - CURRENT LANDSCAPE", fill="white")
    draw.text((60, 65), "Green: prepared pavement | Red: rejected pavement | Amber: source location / unresolved structures", fill="white")
    draw.text((60, 95), "Visual review only. Source markers do not resolve road elevation or Nudo separation.", fill="white")
    for marker in preview["source_markers"]:
        draw.line([pixel(p) for p in marker["xy_local_m"]], fill=(255, 184, 53), width=3)
    for windows, color in ((network["approved"], (76, 210, 123)), (preview["rejected_surfaces"], (250, 62, 49))):
        for item in windows:
            for side in (0, -1):
                draw.line([pixel(row[side]) for row in item["sections"]], fill=color, width=3)
    image.save(path, format="PNG")


def build_full_source_markers(source, area, transformer, origin):
    """Preserve all clipped source XY, including protected/short/unresolved parts."""
    markers = []
    for feature in source["features"]:
        clipped = transform(transformer, shape(feature["geometry"])).intersection(area)
        for part_index, line in enumerate(lines(clipped)):
            points = []
            coords = list(line.coords)
            for a, b in itertools.pairwise(coords):
                length = math.dist(a[:2], b[:2])
                if length == 0:
                    continue
                count = max(1, math.ceil(length / 2.0))
                for index in range(count):
                    t = index / count
                    points.append([
                        a[0] + (b[0] - a[0]) * t - origin[0],
                        origin[1] - a[1] - (b[1] - a[1]) * t,
                    ])
            if not points:
                continue
            points.append([coords[-1][0] - origin[0], origin[1] - coords[-1][1]])
            markers.append({
                "id": f"{feature['id']}-source-{part_index}",
                "feature_id": feature["id"],
                "length_m": line.length,
                "xy_local_m": points,
                "height_evidence": "NATIVE_GROUND_LOCATION_MARKER_ONLY",
                "structure_review_required": feature["id"] in ("VIAL_TR70190001288", "VIAL_TR70190001289"),
            })
    return markers


def prepare(prepared, output, exact_sha):
    if output.exists():
        raise FileExistsError("Preserve previous network evidence")
    if len(exact_sha) != 40 or any(c not in "0123456789abcdef" for c in exact_sha):
        raise ValueError("Exact SHA required")
    manifest = json.loads((prepared / "terrain-import.json").read_text())
    if (
        manifest["region_id"] != "sa_calobra"
        or manifest["vertices"] != [4033, 4033]
        or digest(prepared / "terrain.r16") != manifest["heightmap_sha256"]
    ):
        raise ValueError("Unadmitted terrain")
    terrain = np.fromfile(prepared / "terrain.r16", dtype="<u2").reshape(4033, 4033)
    if digest(SOURCE) != SOURCE_SHA:
        raise ValueError("Pinned IGN road source changed")
    source = json.loads(SOURCE.read_text())
    if source["numberReturned"] != len(source["features"]) or source[
        "numberMatched"
    ] != len(source["features"]):
        raise ValueError("Incomplete road source collection")
    output.mkdir(parents=True)
    origin = manifest["origin_epsg_m"]
    tf = Transformer.from_crs(4326, 25831, always_xy=True).transform
    area = box(origin[0] + 10, origin[1] - 2006, origin[0] + 2006, origin[1] - 10)
    _, accepted, _ = select_alignment()
    protected = accepted.buffer(8)
    for feature in source["features"]:
        if feature["id"] in ("VIAL_TR70190001288", "VIAL_TR70190001289"):
            protected = protected.union(
                transform(tf, shape(feature["geometry"])).buffer(12)
            )
    result = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "region_id": "sa_calobra",
        "source_sha256": digest(SOURCE),
        "anomaly_reviews_sha256": digest(ANOMALY_REVIEWS),
        "heightmap_sha256": manifest["heightmap_sha256"],
        "width_m": WIDTH,
        "shoulder_m": SHOULDER,
        "width_evidence": "INFERRED_PREVIEW_ONLY",
        "base_dtm_modified": False,
        "map_saved": False,
        "canonical_source_modified": False,
        "road_physics_admitted": False,
        "full_preview": {
            "schema_version": 1,
            "role": "VISUAL_REVIEW_ONLY",
            "road_admitted": False,
            "height_change_applied": False,
            "terrain_change_applied": False,
            "source_markers": build_full_source_markers(source, area, tf, origin),
            "rejected_surfaces": [],
        },
        "approved": [],
        "blocked": [],
        "continuous_corridors": [],
        "conflict_intervals": [],
        "segmentation": {
            "method": "CONTINUOUS_CORRIDOR_ADAPTIVE_CONFLICT_INTERVALS_V1",
            "station_spacing_m": STEP,
            "minimum_conflict_interval_m": MIN_CONFLICT_INTERVAL_M,
            "conflict_margin_m": CONFLICT_MARGIN_M,
            "technical_patch_tile_max_m": PATCH_TILE_MAX_M,
            "measurement_probe_max_m": MEASUREMENT_PROBE_MAX_M,
            "fixed_tiles_are_admission_boundaries": False,
        },
        "height_profile_candidates": [],
        "extreme_cut_case": None,
        "source_clipped_length_m": 0,
    }
    for feature in source["features"]:
        geometry = transform(tf, shape(feature["geometry"]))
        clipped = geometry.intersection(area)
        result["source_clipped_length_m"] += clipped.length
        if feature["properties"].get("surfacecategory") != "paved":
            result["blocked"].append(
                {
                    "id": feature["id"],
                    "reason": "Unverified paved surface",
                    "length_m": clipped.length,
                }
            )
            continue
        # Known Nudo loop requires a bridge/underpass recipe, not two terrain cuts.
        if feature["id"] in ("VIAL_TR70190001288", "VIAL_TR70190001289"):
            result["blocked"].append(
                {
                    "id": feature["id"],
                    "reason": "Grade-separated Nudo structure review",
                    "length_m": clipped.length,
                }
            )
            continue
        for part_index, line in enumerate(lines(clipped.difference(protected))):
            if line.length < 3:
                continue
            s, xy = smooth_axis(line)
            tangent = np.gradient(xy, s, axis=0)
            norm = np.linalg.norm(tangent, axis=1)
            normals = np.column_stack([-tangent[:, 1], tangent[:, 0]]) / norm[:, None]
            local = np.column_stack([xy[:, 0] - origin[0], origin[1] - xy[:, 1]])
            normals[:, 1] *= -1
            offsets = np.linspace(-WIDTH / 2, WIDTH / 2, 25)
            section_xy = (
                local[:, None, :] + normals[:, None, :] * offsets[None, :, None]
            )
            # UE reflected Y requires left-to-right sections with clockwise top faces.
            section_xy = section_xy[:, ::-1, :]
            heights = native_ground(terrain, manifest, section_xy)
            center = local_linear_fit(s, heights[:, 12], 7.5)
            bank = local_linear_fit(s, (heights[:, -1] - heights[:, 0]) / WIDTH, 20.0)
            # Preview design only: no survey banking or bus-width inference.
            bank *= min(
                1.0,
                0.04 / max(float(np.max(abs(bank))), 1e-12),
                0.0037 / max(float(np.max(abs(np.diff(bank) / np.diff(s)))), 1e-12),
            )
            ground = center[:, None] + bank[:, None] * offsets[None, :]
            sections = np.dstack([section_xy, ground + 0.04])

            def assess(start, end):
                return assess_network_interval(
                    start,
                    end,
                    s,
                    sections,
                    center,
                    bank,
                    line,
                    terrain,
                    manifest,
                    origin,
                )

            intervals = adaptive_conflict_intervals(s, assess)
            corridor_id = f"{feature['id']}-{part_index}"
            corridor = {
                "id": corridor_id,
                "feature_id": feature["id"],
                "part_index": part_index,
                "length_m": float(s[-1] - s[0]),
                "station_count": len(s),
                "continuous_axis_profile": True,
                "decision_intervals": [],
                "technical_patch_tiles": [],
            }
            for interval_index, interval in enumerate(intervals):
                start, end = interval["start_index"], interval["end_index"]
                length = interval["length_m"]
                decision_id = f"{corridor_id}-interval-{interval_index}"
                decision = {
                    "id": decision_id,
                    "status": interval["status"],
                    "start_m": interval["start_m"],
                    "end_m": interval["end_m"],
                    "length_m": length,
                    "station_range": [start, end],
                    "conflict_margin_m": interval["conflict_margin_m"],
                }
                corridor["decision_intervals"].append(decision)
                if interval["status"] == "PASS":
                    for tile_index, (tile_start, tile_end) in enumerate(
                        technical_patch_tiles(start, end, s)
                    ):
                        tile = assess(tile_start, tile_end)
                        if tile["status"] != "PASS":
                            raise ValueError(
                                "Technical tile contradicted admitted adaptive interval"
                            )
                        diagnostics = tile["diagnostics"]
                        part = sections[tile_start : tile_end + 1]
                        support = np.asarray(
                            shoulder_sections(part.tolist()), dtype=float
                        )
                        ident = f"{decision_id}-tile-{tile_index}"
                        patch_path = output / (ident + "-cut.json")
                        patch = prepare_patch(
                            support,
                            terrain,
                            manifest,
                            patch_path,
                            diagnostics=diagnostics,
                            asphalt_sections=part,
                        )
                        result["approved"].append(
                            {
                                "id": ident,
                                "decision_interval_id": decision_id,
                                "technical_patch_tile": True,
                                "length_m": float(s[tile_end] - s[tile_start]),
                                "sections": part.tolist(),
                                "metrics": {
                                    key: diagnostics[key]
                                    for key in (
                                        "width_min_m",
                                        "width_max_m",
                                        "source_displacement_m",
                                        "both_edges_checked",
                                    )
                                },
                                "surface_inspection": diagnostics[
                                    "surface_inspection"
                                ],
                                "cut_manifest": patch_path.name,
                                "cut_sha256": digest(patch_path),
                                "max_cut_m": patch["max_cut_m"],
                                "earthworks_fit": diagnostics["earthworks_fit"],
                            }
                        )
                        corridor["technical_patch_tiles"].append(ident)
                    continue

                result["full_preview"]["rejected_surfaces"].append({
                    "id": decision_id,
                    "reason": interval["reason"],
                    "length_m": length,
                    "sections": sections[start : end + 1].tolist(),
                    "road_admitted": False,
                })
                diagnostics = interval["diagnostics"]
                ident = decision_id
                evidence_start, evidence_end = interval["evidence_station_range"]
                part = sections[evidence_start : evidence_end + 1]
                source_window = substring(
                    line, float(s[evidence_start]), float(s[evidence_end])
                )
                source_window_local = transform(
                    lambda x, y, z=None: (x - origin[0], origin[1] - y),
                    source_window,
                )
                if "earthworks_fit" in diagnostics:
                    support = np.asarray(
                        shoulder_sections(part.tolist()), dtype=float
                    )
                    diagnostics["cut_depth_by_envelope"] = measure_cut_envelopes(
                        part, support, terrain, manifest
                    )
                    fit = assess_height_profile_candidate(
                        part, terrain, manifest, diagnostics
                    )
                    diagnostics["height_profile_fit"] = fit
                    if fit.get("local_numeric_checks_pass"):
                        result["height_profile_candidates"].append(
                            {"id": ident, "length_m": length, "fit": fit}
                        )
                    extreme = result["extreme_cut_case"]
                    if extreme is None or diagnostics["cut_depth"][
                        "max_cut_m"
                    ] > extreme["cut_depth"]["max_cut_m"]:
                        peak_global = (
                            evidence_start
                            + diagnostics["cut_depth"]["nearest_station_index"]
                        )
                        legacy_start = peak_global // 200 * 200
                        result["extreme_cut_case"] = {
                            "id": ident,
                            "review_evidence_id": (
                                f"{feature['id']}-{part_index}-{legacy_start}"
                            ),
                            "length_m": length,
                            "reason": interval["reason"],
                            "sections": part.tolist(),
                            "cut_depth": diagnostics["cut_depth"],
                            "cut_depth_by_envelope": diagnostics[
                                "cut_depth_by_envelope"
                            ],
                            "height_profile_fit": fit,
                            "source_window_local_xy": [
                                list(point[:2]) for point in source_window_local.coords
                            ],
                            "geometry_repair_executed": False,
                            "height_change_applied": False,
                            "road_admitted": False,
                            "visual_status": "CAPTURE_REQUIRED",
                        }
                blocked = {
                    "id": ident,
                    "corridor_id": corridor_id,
                    "adaptive_conflict_interval": True,
                    "start_m": interval["start_m"],
                    "end_m": interval["end_m"],
                    "length_m": length,
                    "evidence_station_range": [evidence_start, evidence_end],
                    "reason": interval["reason"],
                    "diagnostics": diagnostics,
                }
                result["blocked"].append(blocked)
                result["conflict_intervals"].append(blocked)
            result["continuous_corridors"].append(corridor)
    result["approved_length_m"] = sum(x["length_m"] for x in result["approved"])
    result["blocked_length_m"] = sum(x["length_m"] for x in result["blocked"])
    result["continuous_corridor_count"] = len(result["continuous_corridors"])
    result["decision_interval_count"] = sum(
        len(corridor["decision_intervals"])
        for corridor in result["continuous_corridors"]
    )
    result["adaptive_conflict_interval_count"] = len(
        result["conflict_intervals"]
    )
    result["technical_patch_tile_count"] = len(result["approved"])
    result["height_profile_candidate_length_m"] = sum(
        x["length_m"] for x in result["height_profile_candidates"]
    )
    result["height_profile_candidate_window_count"] = len(
        result["height_profile_candidates"]
    )
    result["height_profile_incompatible_window_count"] = sum(
        x.get("diagnostics", {})
        .get("height_profile_fit", {})
        .get("status")
        == "REJECT_INCOMPATIBLE_CUT_SUPPORT_BOUNDS"
        for x in result["blocked"]
    )
    if result["extreme_cut_case"] is None:
        raise ValueError("Network CUT diagnostics did not retain an extreme case")
    extreme = result["extreme_cut_case"]
    extreme["width_sensitivity"] = width_sensitivity(
        np.asarray(extreme["sections"], dtype=float), terrain, manifest
    )
    extreme["lateral_sweep"] = assess_lateral_sweep(
        np.asarray(extreme["sections"], dtype=float),
        LineString(extreme["source_window_local_xy"]),
        terrain,
        manifest,
    )
    extreme["review"] = build_extreme_review(extreme, manifest)
    diagnostic_image = output / "network-extreme-cut-diagnostic.png"
    write_extreme_cut_diagnostic(extreme, diagnostic_image)
    extreme["diagnostic_image"] = diagnostic_image.name
    extreme["diagnostic_image_sha256"] = digest(diagnostic_image)
    review_path = output / "network-extreme-cut-review.md"
    write_extreme_cut_review(extreme, review_path)
    extreme["review_document"] = review_path.name
    extreme["review_document_sha256"] = digest(review_path)
    result["protected_or_boundary_length_m"] = (
        result["source_clipped_length_m"]
        - result["approved_length_m"]
        - result["blocked_length_m"]
    )
    result["status"] = (
        "PARTIAL_PREVIEW_REQUIRES_REVIEW"
        if result["blocked"]
        else "PREVIEW_REQUIRES_NATIVE_PROOF"
    )
    for marker in result["full_preview"]["source_markers"]:
        marker["ground_m"] = native_ground(terrain, manifest, marker["xy_local_m"]).tolist()
    result["full_preview_proof"] = validate_full_preview(
        result["full_preview"], result["source_clipped_length_m"]
    )
    from scripts.assets.prepare_reviewed_network import prepare_reviewed
    prepare_reviewed(result, terrain, manifest, output)
    write_full_preview_plan(result, output / "network-full-preview-plan.png")
    result["full_preview_plan"] = "network-full-preview-plan.png"
    (output / "network.json").write_text(
        json.dumps(result, separators=(",", ":"), allow_nan=False) + "\n"
    )
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepared-terrain", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--exact-sha", required=True)
    a = p.parse_args()
    r = prepare(a.prepared_terrain, a.output_dir, a.exact_sha)
    print(
        json.dumps(
            {
                k: v
                for k, v in r.items()
                if k
                not in (
                    "approved",
                    "owner_reviewed",
                    "blocked",
                    "full_preview",
                    "height_profile_candidates",
                    "extreme_cut_case",
                )
            },
            indent=2,
        )
    )
    print("Approved windows:", len(r["approved"]), "Blocked:", len(r["blocked"]))
    print(
        "NETWORK_ADAPTIVE_SUMMARY",
        json.dumps(
            {
                key: r[key]
                for key in (
                    "continuous_corridor_count",
                    "decision_interval_count",
                    "adaptive_conflict_interval_count",
                    "technical_patch_tile_count",
                    "approved_length_m",
                    "blocked_length_m",
                    "height_profile_candidate_length_m",
                    "height_profile_candidate_window_count",
                    "height_profile_incompatible_window_count",
                )
            },
            separators=(",", ":"),
            allow_nan=False,
        ),
    )
    # Keep compact blocked-window evidence available through Actions job logs,
    # independently of the large native image/terrain artifact archive.
    for window in r["blocked"]:
        print(
            "NETWORK_BLOCKED",
            json.dumps(window, separators=(",", ":"), allow_nan=False),
        )
    extreme = r["extreme_cut_case"]
    print(
        "NETWORK_EXTREME_REVIEW",
        json.dumps(
            {
                "id": extreme["id"],
                "review": extreme["review"],
                "cut_depth_by_envelope": extreme["cut_depth_by_envelope"],
                "width_sensitivity": {
                    "candidates": extreme["width_sensitivity"]["candidates"],
                    "any_width_passes_ordinary_cut": extreme[
                        "width_sensitivity"
                    ]["any_width_passes_ordinary_cut"],
                },
                "lateral_sweep": {
                    "candidate_count": extreme["lateral_sweep"][
                        "candidate_count"
                    ],
                    "locally_numeric_pass_count": extreme["lateral_sweep"][
                        "locally_numeric_pass_count"
                    ],
                    "best_candidate": extreme["lateral_sweep"][
                        "best_candidate"
                    ],
                },
                "diagnostic_image": extreme["diagnostic_image"],
                "review_document": extreme["review_document"],
                "road_admitted": False,
            },
            separators=(",", ":"),
            allow_nan=False,
        ),
    )
