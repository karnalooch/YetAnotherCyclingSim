"""Bounded BOB bend design and independent final-boundary admission.

NumPy/Shapely are producer-only existing dependencies. The consumer is stdlib
and measures the actual native/rendered edges, not just spline handles.
"""

import hashlib
import json
import math
from itertools import pairwise

CONTRACT = "cliff-convex-bend-v4"
RECIPE = "native-cliff-convex-bend-v4"
METHOD = "native-convex-cubic-bend-v1"
DOMAIN = (122.5, 175.0)
MAIN_BEND = (137.5, 155.0)
FIT_DOMAIN = (115.0, 180.0)
POSITION_PRECISION_M = 0.0001
INSPECTION_STEP_M = 0.25
MINIMUM_INNER_RADIUS_M = 1.5


def design(guides, source_sections, observations, circle_prior, *, reference_edge):
    """Convex control envelope -> regularized fit -> native cubic controls.

The fitted circle is a fairness prior only. It does not fix approach endpoints.
Cardinal cubic B-spline knot values/derivatives become ordinary native Hermite
controls; there is no custom runtime spline evaluator or new dependency.
"""
    import numpy as np
    from shapely.geometry import MultiPoint

    from scripts.geometry.road_width_profile import width_at

    keys = np.array([g["station_m"] for g in guides])
    if reference_edge not in (0, 1):
        raise ValueError("Explicit physical reference edge required")
    raw = np.array([g["edges_xy_m"][reference_edge] for g in guides])
    first, last = (int(s / 2.5) for s in FIT_DOMAIN)

    def convex_envelope(controls):
        points = controls[first:last + 1]
        hull = list(MultiPoint(points).convex_hull.exterior.coords)[:-1]
        lookup = {tuple(p): i for i, p in enumerate(points)}
        indices = sorted(lookup[tuple(p)] + first for p in hull)
        if indices[0] != first or indices[-1] != last:
            raise ValueError("Convex bend fit would discard an approach endpoint")
        result = controls.copy()
        for axis in (0, 1):
            result[first:last + 1, axis] = np.interp(
                keys[first:last + 1], keys[indices], controls[indices, axis]
            )
        return result

    controls = convex_envelope(raw)
    samples = np.arange(FIT_DOMAIN[0], FIT_DOMAIN[1] + 0.0625, 0.125)
    integer = np.floor(samples / 2.5).astype(int)
    u = samples / 2.5 - integer
    basis = np.zeros((len(samples), len(guides)))
    weights = np.array([(1-u)**3, 3*u**3-6*u*u+4,
                        -3*u**3+3*u*u+3*u+1, u**3]).T / 6
    for j in range(4):
        basis[np.arange(len(samples)), integer + j - 1] = weights[:, j]
    source = np.asarray(source_sections)[:, 0 if reference_edge == 0 else -1, :2]
    targets = np.column_stack([
        np.interp(samples, np.arange(len(source)) * 0.5, source[:, k])
        for k in (0, 1)
    ])
    # The accepted circular prior reduces sharp source-polygon corners. Its
    # influence is explicit; source displacement is still independently capped.
    circle_weight = 0.75
    regularization = 10.0
    for n, station in enumerate(samples):
        if circle_prior["start_station_m"] <= station <= circle_prior["end_station_m"]:
            i, t = int(station / 2.5), station / 2.5 % 1
            a, b = guides[i], guides[i + 1]
            prior = ((2*t**3-3*t*t+1)*np.array(a["reference_xy_m"])
                     +(t**3-2*t*t+t)*np.array(a["leave_tangent_xy_m"])
                     +(-2*t**3+3*t*t)*np.array(b["reference_xy_m"])
                     +(t**3-t*t)*np.array(b["arrive_tangent_xy_m"]))
            targets[n] = (1-circle_weight)*targets[n] + circle_weight*prior
    columns = np.arange(first, last + 1)
    free = basis[:, columns]
    controls[columns] += np.linalg.solve(
        free.T @ free + regularization*np.eye(len(columns)),
        free.T @ (targets - basis @ controls),
    )
    controls = convex_envelope(controls)
    positions = (controls[:-2] + 4*controls[1:-1] + controls[2:]) / 6
    tangents = (controls[2:] - controls[:-2]) / 2
    for i, guide in enumerate(guides):
        station = guide["station_m"]
        if 110.0 <= station <= 195.0:
            # Rejoin the unchanged road over 175..195 m, rather than abruptly
            # switching control families at 187.5 m and pinching its shoulder.
            u = max(0.0, (station - 175.0) / 20.0)
            weight = 1 - u**3*(10 - 15*u + 6*u*u)
            derivative = -30*u*u*(1-u)**2 / 20.0
            old_position = np.array(guide["reference_xy_m"])
            old_tangent = np.array(guide["leave_tangent_xy_m"])
            position = old_position + weight*(positions[i - 1] - old_position)
            tangent = (old_tangent + weight*(tangents[i - 1] - old_tangent)
                       + 2.5*derivative*(positions[i - 1] - old_position))
            guide.update(reference_xy_m=position.tolist(),
                         arrive_tangent_xy_m=tangent.tolist(),
                         leave_tangent_xy_m=tangent.tolist())
    base_width = sum(width_at(observations, 125.0))
    width_samples = [dict(r) for r in observations["samples"]
                     if r["station_m"] < FIT_DOMAIN[0] or r["station_m"] > FIT_DOMAIN[1]]
    width_samples.extend({"station_m": s, "left_m": base_width/2, "right_m": base_width/2}
                         for s in FIT_DOMAIN)
    widths = {
        "evidence": {**observations["evidence"], "raw_width_samples": observations["samples"],
                     "method": "Constant approach width from station 125; bus widening unproven",
                     "vehicle_swept_path_admitted": False},
        "samples": sorted(width_samples, key=lambda r: r["station_m"]),
    }
    vectors = np.diff(raw[first:last + 1], axis=0)
    signed_turn = np.sum(vectors[:-1, 0]*vectors[1:, 1] - vectors[:-1, 1]*vectors[1:, 0])
    if abs(signed_turn) <= 1e-9:
        raise ValueError("Single bend has no evidenced turn direction")
    spec = {"method": METHOD, "domain_m": list(DOMAIN), "main_bend_m": list(MAIN_BEND),
            "turn_sign": 1 if signed_turn > 0 else -1, "base_width_m": base_width, "widening_m": 0.0,
            "base_width_source_station_m": 125.0,
            "fit_domain_m": list(FIT_DOMAIN), "circle_prior_weight": circle_weight,
            "exit_rejoin_domain_m": [175.0, 195.0],
            "regularization": regularization, "circle_prior": circle_prior,
            "vehicle_swept_path_admitted": False}
    return widths, spec


def _metric_samples(points):
    """Inspect at a physical spacing; input-key speed must not hide a reversal."""
    result = [points[0]]
    travelled, next_distance = 0.0, INSPECTION_STEP_M
    for a, b in pairwise(points):
        length = math.dist(a, b)
        if length <= 1e-9:
            raise ValueError("Single bend boundary stops")
        while next_distance <= travelled + length:
            t = (next_distance - travelled) / length
            result.append([a[k] + t*(b[k]-a[k]) for k in (0, 1)])
            next_distance += INSPECTION_STEP_M
        travelled += length
    if math.dist(result[-1], points[-1]) >= INSPECTION_STEP_M/2:
        result.append(points[-1])
    return result


def inspect(rows, spec):
    if (spec.get("method") != METHOD or spec.get("domain_m") != list(DOMAIN)
            or spec.get("main_bend_m") != list(MAIN_BEND)
            or spec.get("turn_sign") not in (-1, 1) or isinstance(spec.get("turn_sign"), bool)
            or spec.get("widening_m") != 0.0):
        raise ValueError("Missing or unsupported single bend contract")
    width = spec.get("base_width_m")
    if isinstance(width, bool) or not isinstance(width, (float, int)) or not 2 <= width <= 12:
        raise ValueError("Missing finite base width")
    selected = [r for r in rows if DOMAIN[0] <= r["station_m"] <= DOMAIN[1]]
    if (len(selected) < 3 or selected[0]["station_m"] != DOMAIN[0]
            or selected[-1]["station_m"] != DOMAIN[1]):
        raise ValueError("Incomplete single bend domain")
    canonical, curves = [], [[], [], []]
    widths = []
    for row in selected:
        s, edges = row["station_m"], row["edges_xy_m"]
        if (len(edges) != 2 or any(len(p) != 2 for p in edges)
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                           and math.isfinite(v) for p in edges for v in p)
                or (canonical and s <= canonical[-1][0])):
            raise ValueError("Nonfinite or unordered single bend samples")
        widths.append(math.dist(*edges))
        canonical.append([s, edges])
        curves[0].append(edges[0]); curves[1].append(edges[1])
        curves[2].append([(edges[0][k]+edges[1][k])/2 for k in (0, 1)])
    if max(abs(w-width) for w in widths) > POSITION_PRECISION_M:
        raise ValueError("Single bend entry/exit or unproved main width varies")
    metrics = []
    for points in curves:
        # Check every original segment as well: metric resampling must not
        # average away a short hook. Tolerance is positional roundoff only.
        for a, b, c in zip(points, points[1:], points[2:]):
            u, v = [b[k]-a[k] for k in (0, 1)], [c[k]-b[k] for k in (0, 1)]
            ab, bc = math.hypot(*u), math.hypot(*v)
            if min(ab, bc) <= 1e-9:
                raise ValueError("Single bend boundary stops")
            turn = math.atan2((u[0]*v[1]-u[1]*v[0])*spec["turn_sign"],
                              sum(x*y for x, y in zip(u, v)))
            if turn < -4*POSITION_PRECISION_M*(1/ab + 1/bc):
                raise ValueError("Single bend counter-turn in original samples")
        points = _metric_samples(points)
        minimum, maximum, heading, worst_reverse, failures = math.inf, 0.0, 0.0, 0.0, 0
        for a, b, c in zip(points, points[1:], points[2:]):
            ab, bc, ac = math.dist(a, b), math.dist(b, c), math.dist(a, c)
            if min(ab, bc, ac) <= 1e-9:
                raise ValueError("Single bend boundary reverses or degenerates")
            u, v = [b[k]-a[k] for k in (0, 1)], [c[k]-b[k] for k in (0, 1)]
            cross = (u[0]*v[1]-u[1]*v[0])*spec["turn_sign"]
            turn = math.atan2(cross, sum(x*y for x, y in zip(u, v)))
            tolerance = 4*POSITION_PRECISION_M*(1/ab + 1/bc)
            failures += turn < -tolerance
            curvature = 2*cross/(ab*bc*ac)
            minimum, maximum = min(minimum, curvature), max(maximum, curvature)
            heading += turn
            worst_reverse = max(worst_reverse, -turn)
        if failures:
            raise ValueError(f"Single bend counter-turn: {failures} intervals")
        if maximum > 1/MINIMUM_INNER_RADIUS_M:
            raise ValueError("Single bend inner radius remains pinched")
        metrics.append({"minimum_signed_curvature_per_m": minimum,
                        "maximum_signed_curvature_per_m": maximum,
                        "minimum_radius_m": 1/maximum if maximum else None,
                        "heading_change_deg": math.degrees(heading),
                        "worst_reverse_turn_deg": math.degrees(worst_reverse),
                        "counter_turn_intervals": failures})
    return {"status": "PASS", "method": METHOD, "domain_m": list(DOMAIN),
            "width_min_m": min(widths), "width_max_m": max(widths),
            "inspection_step_m": INSPECTION_STEP_M,
            "position_precision_m": POSITION_PRECISION_M,
            "curves": metrics,
            "edges_sha256": hashlib.sha256(json.dumps(canonical, separators=(",", ":"), allow_nan=False).encode()).hexdigest()}


def profile_proof_valid(profile):
    try:
        plan = profile["presentation_plan"]
        spec = plan["controlled_width"]["single_bend"]
        rows = [{"station_m": r["station_m"], "edges_xy_m": [r["xy_local_m"][0], r["xy_local_m"][-1]]}
                for r in profile["stations"]]
        return inspect(rows, spec) == plan["single_bend_inspection"]
    except (ValueError, KeyError, TypeError, IndexError, OverflowError):
        return False
