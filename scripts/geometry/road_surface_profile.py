"""Bounded preview road alignment and measured surface gates, independent of DTM slope."""

import numpy as np

from scripts.geometry.road_transition import evaluate, quintic

WINDOW = (110.0, 165.0)
ARC = (135.0, 155.0)
PREVIEW_CROSSFALL = -0.02
LIMITS = {"crossfall_abs": 0.06, "crossfall_rate_per_m": 0.005,
          "adjacent_normal_angle_deg": 5.0, "edge_grade_abs": 0.5}


def design_profile(stations, xy, center, crossfall, *, reference_edge=0, inner_edge=1):
    """Preserve approach elevation/grade/vertical curvature; blend banking separately.

    2% is an explicit preview choice, not a survey or engineering admission.
    All interpolation uses sampled midpoint distance rather than uneven GIS keys.
    """
    if reference_edge not in (0, 1) or inner_edge not in (0, 1):
        raise ValueError("Explicit physical edge indices required")
    preview_crossfall = abs(PREVIEW_CROSSFALL) * (1 if inner_edge == 0 else -1)
    stations, xy = np.asarray(stations), np.asarray(xy)
    center, crossfall = np.asarray(center).copy(), np.asarray(crossfall).copy()
    midpoint = (xy[:, 0] + xy[:, -1]) / 2
    distance = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(midpoint, axis=0), axis=1))]
    if not np.isfinite(distance).all() or (np.diff(distance) <= 0).any():
        raise ValueError("Road midpoint distance stops")
    indices = [int(np.flatnonzero(stations == s)[0]) for s in (*WINDOW, *ARC)]
    first, last, arc_start, arc_end = indices
    width = np.linalg.norm(xy[:, -1] - xy[:, 0], axis=1)
    reference_offset = width / 2 * (-1 if reference_edge == 0 else 1)
    reference_height = center + crossfall * reference_offset
    grade = np.gradient(center, distance, edge_order=2)
    acceleration = np.gradient(grade, distance, edge_order=2)
    q_rate = np.gradient(crossfall, distance, edge_order=2)
    q_acceleration = np.gradient(q_rate, distance, edge_order=2)
    length = distance[last] - distance[first]
    vertical = quintic(center[first], grade[first], acceleration[first],
                       center[last], grade[last], acceleration[last], length)
    apex = int(np.flatnonzero(stations == 145.0)[0])
    apex_u = (distance[apex] - distance[first]) / length
    apex_target = reference_height[apex] - preview_crossfall * reference_offset[apex]
    correction = (apex_target - evaluate(vertical, distance[apex] - distance[first], length)) / (apex_u**3 * (1 - apex_u)**3)
    entry = quintic(crossfall[first], q_rate[first], q_acceleration[first],
                    preview_crossfall, 0, 0, distance[arc_start] - distance[first])
    exit_curve = quintic(preview_crossfall, 0, 0, crossfall[last], q_rate[last],
                         q_acceleration[last], distance[last] - distance[arc_end])
    for i in range(first, last + 1):
        if i < arc_start:
            crossfall[i] = evaluate(entry, distance[i] - distance[first], distance[arc_start] - distance[first])
        elif i <= arc_end:
            crossfall[i] = preview_crossfall
        else:
            crossfall[i] = evaluate(exit_curve, distance[i] - distance[arc_end], distance[last] - distance[arc_end])
        u = (distance[i] - distance[first]) / length
        center[i] = evaluate(vertical, distance[i] - distance[first], length) + correction * u**3 * (1 - u)**3
    return center, crossfall, {
        "method": "C2-approach-profile-with-reference-apex-datum", "window_m": list(WINDOW),
        "arc_m": list(ARC), "preview_crossfall": preview_crossfall, "reference_edge": reference_edge, "inner_edge": inner_edge,
        "source": "approach reference-edge elevation/grade; explicit preview banking, not hillside fit",
        "reference_apex_station_m": 145.0, "reference_apex_height_m": float(reference_height[apex]),
        "engineering_admitted": False,
    }


def inspect_surface(rows):
    xy = np.asarray([r["xy_local_m"] for r in rows], dtype=float)
    z = np.asarray([r["candidate_ground_m"] for r in rows], dtype=float)
    stations = np.asarray([r["station_m"] for r in rows])
    if xy.shape != (len(rows), 25, 2) or z.shape != (len(rows), 25) or not np.isfinite(xy).all() or not np.isfinite(z).all():
        raise ValueError("Invalid road surface samples")
    points = np.dstack((xy, z))
    a, b, c, d = points[:-1, :-1], points[:-1, 1:], points[1:, :-1], points[1:, 1:]
    n0, n1 = np.cross(b - a, c - a), np.cross(d - b, c - b)
    for normals in (n0, n1):
        lengths = np.linalg.norm(normals, axis=2)
        if (lengths <= 1e-10).any():
            raise ValueError("Degenerate road surface facet")
        normals /= lengths[:, :, None]
    use = (stations[:-1] >= WINDOW[0]) & (stations[1:] <= WINDOW[1])

    def angles(first, second):
        return np.degrees(np.arccos(np.clip(np.sum(first * second, axis=2), -1, 1)))

    angle = max(float(angles(n0, n1)[use].max()),
                float(angles(n1[:, :-1], n0[:, 1:])[use].max()),
                float(angles(n1[:-1], n0[1:])[use[:-1] & use[1:]].max()))
    midpoint = (xy[:, 0] + xy[:, -1]) / 2
    distance = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(midpoint, axis=0), axis=1))]
    if (np.diff(distance) <= 0).any():
        raise ValueError("Road surface midpoint stops")
    width = np.linalg.norm(xy[:, -1] - xy[:, 0], axis=1)
    q = (z[:, -1] - z[:, 0]) / width
    edge_step = np.linalg.norm(np.diff(xy[:, [0, -1]], axis=0), axis=2)
    if (edge_step <= 1e-9).any():
        raise ValueError("Road surface edge stops")
    metrics = {
        "crossfall_abs": float(np.abs(q[(stations >= WINDOW[0]) & (stations <= WINDOW[1])]).max()),
        "crossfall_rate_per_m": float(np.abs(np.diff(q) / np.diff(distance))[use].max()),
        "adjacent_normal_angle_deg": angle,
        "edge_grade_abs": float(np.abs(np.diff(z[:, [0, -1]], axis=0) / edge_step)[use].max()),
    }
    return {"status": "PASS" if all(metrics[k] <= v for k, v in LIMITS.items()) else "FAIL",
            "window_m": list(WINDOW), "limits": LIMITS.copy(), "metrics": metrics,
            "engineering_admitted": False}


def surface_proof_valid(profile):
    try:
        actual = inspect_surface(profile["stations"])
        return actual["status"] == "PASS" and profile.get("surface_inspection") == actual
    except (ValueError, KeyError, TypeError, IndexError):
        return False
