"""Bounded preview road alignment and measured surface gates, independent of DTM slope."""

import hashlib
import json
import math

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
    import numpy as np

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
    """Pure stdlib consumer also runs in Unreal's embedded Python."""
    points, q, stations = [], [], []
    canonical = []
    for row in rows:
        xy, z = row["xy_local_m"], row["candidate_ground_m"]
        if len(xy) != 25 or len(z) != 25 or any(len(p) != 2 for p in xy):
            raise ValueError("Invalid road surface samples")
        station = row["station_m"]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                   for v in [station, *z, *(v for p in xy for v in p)]):
            raise ValueError("Nonfinite road surface samples")
        width = math.dist(xy[0], xy[-1])
        if width <= 1e-9 or (stations and station <= stations[-1]):
            raise ValueError("Invalid ordered road surface")
        points.append([(*p, height) for p, height in zip(xy, z)])
        q.append((z[-1] - z[0]) / width)
        stations.append(station)
        canonical.append([station, xy, z])

    def normal(a, b, c):
        u, v = [b[k] - a[k] for k in range(3)], [c[k] - a[k] for k in range(3)]
        n = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
        length = math.sqrt(sum(x*x for x in n))
        if length <= 1e-10:
            raise ValueError("Degenerate road surface facet")
        return [x / length for x in n]

    def angle(a, b):
        return math.degrees(math.acos(max(-1.0, min(1.0, sum(x*y for x, y in zip(a, b))))))

    metrics = dict.fromkeys(LIMITS, 0.0)
    previous = None
    evaluated = 0
    for i in range(len(rows) - 1):
        use = WINDOW[0] <= stations[i] and stations[i + 1] <= WINDOW[1]
        first, second = points[i], points[i + 1]
        n0, n1 = [], []
        for j in range(24):
            n0.append(normal(first[j], first[j+1], second[j]))
            n1.append(normal(first[j+1], second[j+1], second[j]))
        if use:
            evaluated += 1
            angles = [angle(a, b) for a, b in zip(n0, n1)]
            angles.extend(angle(n1[j], n0[j+1]) for j in range(23))
            if previous is not None:
                angles.extend(angle(a, b) for a, b in zip(previous, n0))
            metrics["adjacent_normal_angle_deg"] = max(metrics["adjacent_normal_angle_deg"], *angles)
            midpoint_step = math.dist([(first[0][k]+first[-1][k])/2 for k in (0,1)],
                                      [(second[0][k]+second[-1][k])/2 for k in (0,1)])
            if midpoint_step <= 1e-9:
                raise ValueError("Road surface midpoint stops")
            metrics["crossfall_abs"] = max(metrics["crossfall_abs"], abs(q[i]), abs(q[i+1]))
            metrics["crossfall_rate_per_m"] = max(metrics["crossfall_rate_per_m"], abs(q[i+1]-q[i])/midpoint_step)
            for j in (0, 24):
                edge_step = math.dist(first[j][:2], second[j][:2])
                if edge_step <= 1e-9:
                    raise ValueError("Road surface edge stops")
                metrics["edge_grade_abs"] = max(metrics["edge_grade_abs"], abs(second[j][2]-first[j][2])/edge_step)
        previous = n1 if use else None
    if evaluated == 0:
        raise ValueError("Missing bounded road surface domain")
    return {"status": "PASS" if all(metrics[k] <= v for k, v in LIMITS.items()) else "FAIL",
            "window_m": list(WINDOW), "limits": LIMITS.copy(), "metrics": metrics,
            "surface_sha256": hashlib.sha256(json.dumps(canonical, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
            "engineering_admitted": False}


def surface_proof_valid(profile):
    try:
        actual = inspect_surface(profile["stations"])
        recorded = profile.get("surface_inspection", {})
        return (actual["status"] == "PASS"
                and all(recorded.get(k) == actual[k] for k in ("status", "window_m", "limits", "surface_sha256", "engineering_admitted"))
                and all(abs(recorded.get("metrics", {}).get(k, math.inf)-v) <= 1e-9 for k,v in actual["metrics"].items()))
    except (ValueError, KeyError, TypeError, IndexError):
        return False
