"""Source-declared cap fitting diagnostics; never production qualification.

diagnose(rows, declaration, refinement): rows use native local_xy_cm,
bottom_z_cm/top_z_cm/ground_z_cm. Declaration binds source_sha256 and
basecut_source_sha256 (original corrected source), topology_verified, cap_z_cm=0,
cap_tolerance_cm=.01, cap_xy_polygon, com_xy_cm (source volume COM projection),
expected_full_ray_count, expected_cap_ray_count, height_cm (native AABB height).
Optional cap_xy_loops contains the legacy outer polygon first, then disjoint,
strictly interior nonnested holes. Outer boundary belongs; hole boundaries do not.
Explicit cap_loop_mode=DISJOINT_OUTER_UNION_V1 instead declares separate,
nonnested outer regions, all with inclusive boundaries; default is OUTER_WITH_HOLES_V1.
Optional planting_depth_fraction is frozen at 0 (default) or .05 before measurement;
planting lowers the cap-fit root and consumes the same full-geometry burial budget.
Each row supplies ground_slope_deg. Refinement supplies measured
root_delta_cm and embedding_delta_cm. Source/topology claims are NOT authenticated
by this pure calculator. Expected ray counts come from source geometry, not
successful terrain hits. Missing ground anywhere in the full footprint rejects.
The COM hull is the sampled cap extent, not a load-contact force polygon or
proof of static stability; penetration samples are not physical contact forces.
"""

import math
import re
from functools import lru_cache


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("NONFINITE_OR_MISSING_MEASUREMENT")
    return float(value)


def xy(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("INVALID_XY")
    return tuple(number(v) for v in value)


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def hull(points):
    points = sorted(set(points))
    halves = []
    for ordered in (points, list(reversed(points))):
        half = []
        for point in ordered:
            while len(half) >= 2 and cross(half[-2], half[-1], point) <= 0:
                half.pop()
            half.append(point)
        halves.append(half[:-1])
    return halves[0] + halves[1]


def inside(point, polygon):
    """Boundary-inclusive ray crossing for a verified simple cap polygon."""
    result = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (
            cross(a, b, point) == 0
            and min(a[0], b[0]) <= point[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= point[1] <= max(a[1], b[1])
        ):
            return True
        if (a[1] > point[1]) != (b[1] > point[1]):
            intercept = a[0] + (point[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if point[0] < intercept:
                result = not result
    return result


def edges_touch(a, b, c, e):
    return (
        cross(a, b, c) * cross(a, b, e) <= 0
        and cross(c, e, a) * cross(c, e, b) <= 0
        and all(
            max(min(a[k], b[k]), min(c[k], e[k]))
            <= min(max(a[k], b[k]), max(c[k], e[k]))
            for k in (0, 1)
        )
    )


def patch_loops(declaration):
    outer = [xy(p) for p in declaration["cap_xy_polygon"]]
    supplied = declaration.get("cap_xy_loops", [outer])
    if not isinstance(supplied, (list, tuple)) or not supplied:
        raise ValueError("INVALID_CAP_LOOPS")
    loops = [[xy(p) for p in loop] for loop in supplied]
    if loops[0] != outer:
        raise ValueError("CAP_OUTER_LOOP_MISMATCH")
    return validated_loops(
        tuple(tuple(loop) for loop in loops),
        declaration.get("cap_loop_mode", "OUTER_WITH_HOLES_V1"),
    )


@lru_cache(maxsize=16)
def validated_loops(immutable_loops, mode="OUTER_WITH_HOLES_V1"):
    if mode not in ("OUTER_WITH_HOLES_V1", "DISJOINT_OUTER_UNION_V1"):
        raise ValueError("UNKNOWN_CAP_LOOP_MODE")
    loops = [list(loop) for loop in immutable_loops]
    outer = loops[0]
    for loop in loops:
        if len(loop) < 3 or len(set(loop)) != len(loop) or len(hull(loop)) < 3:
            raise ValueError("DEGENERATE_CAP_POLYGON")
        for i, a in enumerate(loop):
            b = loop[(i + 1) % len(loop)]
            # Collinear reversal makes adjacent edges overlap ambiguously.
            c = loop[(i + 2) % len(loop)]
            if (
                cross(a, b, c) == 0
                and sum((a[k] - b[k]) * (c[k] - b[k]) for k in (0, 1)) > 0
            ):
                raise ValueError("SELF_INTERSECTING_CAP_POLYGON")
            for j in range(i + 1, len(loop)):
                if j == i + 1 or (i == 0 and j == len(loop) - 1):
                    continue
                if edges_touch(a, b, loop[j], loop[(j + 1) % len(loop)]):
                    raise ValueError("SELF_INTERSECTING_CAP_POLYGON")
    for i, loop in enumerate(loops):
        for other in loops[i + 1 :]:
            if any(
                edges_touch(a, b, c, e)
                for a, b in zip(loop, loop[1:] + loop[:1])
                for c, e in zip(other, other[1:] + other[:1])
            ):
                raise ValueError("CAP_LOOPS_INTERSECT_OR_TOUCH")
    if mode == "DISJOINT_OUTER_UNION_V1":
        for i, loop in enumerate(loops):
            if any(
                inside(loop[0], other) or inside(other[0], loop)
                for other in loops[i + 1 :]
            ):
                raise ValueError("NESTED_UNION_LOOPS_UNSUPPORTED")
        return immutable_loops
    for i, hole in enumerate(loops[1:], 1):
        if not inside(hole[0], outer):
            raise ValueError("CAP_HOLE_OUTSIDE_OUTER")
        if any(
            inside(hole[0], other) or inside(other[0], hole) for other in loops[1:i]
        ):
            raise ValueError("NESTED_CAP_HOLES_UNSUPPORTED")
    return immutable_loops


def inside_patch(point, declaration):
    """Validated declared patch mode; hole boundaries conservatively excluded.

    Raises on ambiguous declarations, including touching, intersecting or nested
    loops. This geometric selector authenticates neither source nor ground.
    """
    loops = patch_loops(declaration)
    return inside_validated_patch(
        point, loops, declaration.get("cap_loop_mode", "OUTER_WITH_HOLES_V1")
    )


def inside_validated_patch(point, immutable_loops, mode="OUTER_WITH_HOLES_V1"):
    """Select against immutable loops returned by patch_loops, without revalidation.

    Caller must obtain these loops from patch_loops for the same declaration.
    """
    point = xy(point)
    if mode == "DISJOINT_OUTER_UNION_V1":
        return any(inside(point, loop) for loop in immutable_loops)
    if mode != "OUTER_WITH_HOLES_V1":
        raise ValueError("UNKNOWN_CAP_LOOP_MODE")
    return inside(point, immutable_loops[0]) and not any(
        inside(point, hole) for hole in immutable_loops[1:]
    )


def diagnose(rows, declaration, refinement=None):
    result = {
        "status": "REJECTED_DIAGNOSTIC",
        "placement": False,
        "full_qualification": False,
        "regional_production_qualified": False,
        "continuous_support_verified": False,
        "proof_authenticity": "NOT_VERIFIED",
        "reasons": [],
        "coverage": {},
        "limits_basis": "TRIAL_DIAGNOSTIC_ONLY_NOT_CONTACT_ADMISSION",
    }
    try:
        d = declaration
        source = d["source_sha256"]
        if any(
            not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value)
            for value in (source, d["basecut_source_sha256"])
        ):
            raise ValueError("SOURCE_BINDING_MISMATCH")
        if d["topology_verified"] is not True:
            raise ValueError("TOPOLOGY_NOT_VERIFIED")
        if number(d["cap_z_cm"]) != 0 or number(d["cap_tolerance_cm"]) != 0.01:
            raise ValueError("UNSUPPORTED_CAP_DECLARATION")
        loops = patch_loops(d)
        loop_mode = d.get("cap_loop_mode", "OUTER_WITH_HOLES_V1")

        def selected(point):
            return inside_validated_patch(point, loops, loop_mode)

        center = xy(d["com_xy_cm"])
        full_expected, cap_expected = (
            d["expected_full_ray_count"],
            d["expected_cap_ray_count"],
        )
        if (
            type(full_expected) is not int
            or type(cap_expected) is not int
            or not 3 <= cap_expected <= full_expected
        ):
            raise ValueError("INVALID_EXPECTED_COVERAGE")
        full, cap, seen = [], [], set()
        invalid_ground, missing_cap_bottom, max_slope = 0, 0, 0.0
        for row in rows:
            point = xy(row["local_xy_cm"])
            if point in seen:
                raise ValueError("DUPLICATE_SOURCE_RAY")
            seen.add(point)
            try:
                bottom, top = number(row["bottom_z_cm"]), number(row["top_z_cm"])
            except (KeyError, ValueError):
                if selected(point):
                    missing_cap_bottom += 1
                continue
            if top < bottom:
                raise ValueError("INVERTED_MESH_INTERVAL")
            try:
                ground = number(row["ground_z_cm"])
            except (ValueError, KeyError):
                invalid_ground += 1
                continue
            slope = number(row["ground_slope_deg"])
            if not 0 <= slope <= 90:
                raise ValueError("INVALID_LOCAL_SLOPE")
            max_slope = max(max_slope, slope)
            entry = (point, bottom, top, ground)
            full.append(entry)
            if selected(point) and abs(bottom) <= 0.01:
                cap.append(entry)
        result["coverage"] = {
            "full_expected": full_expected,
            "full_valid": len(full),
            "invalid_ground": invalid_ground,
            "cap_expected": cap_expected,
            "cap_valid": len(cap),
            "missing_cap_bottom": missing_cap_bottom,
        }
        if missing_cap_bottom:
            raise ValueError("MISSING_DECLARED_CAP_BOTTOM")
        if invalid_ground or len(full) != full_expected:
            raise ValueError("INCOMPLETE_FULL_FOOTPRINT_GROUND")
        if len(cap) != cap_expected:
            raise ValueError("INCOMPLETE_DECLARED_CAP_SUPPORT")
        support_hull = hull([r[0] for r in cap])
        if len(support_hull) < 3:
            raise ValueError("INSUFFICIENT_NONCOLLINEAR_SUPPORT")
        if not inside(center, support_hull):
            raise ValueError("COM_OUTSIDE_SUPPORT_HULL")
        height = number(d["height_cm"])
        if height <= 0:
            raise ValueError("ZERO_SAMPLED_HEIGHT")
        planting_fraction = number(d.get("planting_depth_fraction", 0))
        if planting_fraction not in (0.0, 0.05):
            raise ValueError("UNSUPPORTED_PLANTING_DEPTH_FRACTION")
        unplanted_root = min(g - b for _, b, _, g in cap)
        planting_depth = number(planting_fraction * height)
        root = number(unplanted_root - planting_depth)
        nonpenetrating = max(g - b for _, b, _, g in full)
        embedding = max(0.0, nonpenetrating - root)
        fitted = [
            {
                "local_xy_cm": list(p),
                "bottom_gap_cm": number(root - (g - b)),
                "exposed_top_cm": max(0.0, number((t - b) + (root - (g - b)))),
                "cap_support": selected(p) and abs(b) <= 0.01,
            }
            for p, b, t, g in full
        ]
        exposed = sum(r["exposed_top_cm"] > 0 for r in fitted)
        max_exposure = max(r["exposed_top_cm"] for r in fitted)
        root_delta, embedding_delta = (
            (0.0, 0.0)
            if refinement is None
            else (
                number(refinement["root_delta_cm"]),
                number(refinement["embedding_delta_cm"]),
            )
        )
        if min(root_delta, embedding_delta) < 0:
            raise ValueError("INVALID_REFINEMENT_DELTA")
        for failed, reason in [
            (max_slope > 10, "EXCESSIVE_LOCAL_SLOPE"),
            (embedding > 0.2 * height, "EXCESSIVE_FULL_GEOMETRY_EMBEDDING"),
            (max_exposure < 0.8 * height, "INSUFFICIENT_FULL_GEOMETRY_EXPOSURE"),
            (exposed < 0.8 * len(full), "INSUFFICIENT_EXPOSED_RAYS"),
            (
                root_delta > 0.1 or embedding_delta > 0.1,
                "SAMPLE_REFINEMENT_NOT_CONVERGED",
            ),
        ]:
            if failed:
                result["reasons"].append(reason)
        result.update(
            fit={
                "root_zero_sampled_air_cm": number(root),
                "required_embedding_cm": number(embedding),
                "exposure_max_cm": max_exposure,
                "exposed_count": exposed,
            },
            max_local_slope_deg=max_slope,
            root_z_cm=number(root),
            unplanted_root_z_cm=number(unplanted_root),
            planting_depth_cm=planting_depth,
            planting_depth_fraction=planting_fraction,
            cap_loop_mode=loop_mode,
            full_nonpenetrating_root_cm=number(nonpenetrating),
            full_embedding_cm=number(embedding),
            sampled_height_cm=number(height),
            exposed_ray_fraction=exposed / len(full),
            exposed_height_fraction=max_exposure / height,
            support_hull_xy_cm=[list(p) for p in support_hull],
            com_inside_support_hull=True,
            remaining_positive_overhang_gap_cm=max(
                0.0,
                max(r["bottom_gap_cm"] for r in fitted if not r["cap_support"])
                if any(not r["cap_support"] for r in fitted)
                else 0.0,
            ),
            samples=fitted,
        )
        if not result["reasons"]:
            result["status"] = (
                "DIAGNOSTIC_AWAITING_REFINEMENT"
                if refinement is None
                else "DIAGNOSTIC_SUPPORT_PATCH_ONLY"
            )
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        result["reasons"].append(
            str(error)
            if isinstance(error, ValueError)
            else "MISSING_OR_MALFORMED_INPUT"
        )
    return result
