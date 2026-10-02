"""Bounded experimental builder lesson; never grants production/learning admission."""

import math

from scripts.worldgen.bob_profile_inspector import inspect_road_profile

START_M, END_M = 70.0, 90.0
MAX_ADJUSTMENT_M = 0.5
MAX_CROSSFALL = 0.08


def plan_lesson(candidate):
    inspection = inspect_road_profile(candidate)
    if not inspection["inspection_complete"]:
        raise ValueError("Incomplete profile evidence")
    rows = [r for r in candidate["stations"] if START_M <= r["station_m"] <= END_M]
    if len(rows) != 41:
        raise ValueError("Lesson requires the complete 20 m section")
    if any(
        max(abs(a - b) for a, b in zip(r["candidate_ground_m"], r["native_ground_m"]))
        > MAX_ADJUSTMENT_M
        or abs(
            (r["candidate_ground_m"][-1] - r["candidate_ground_m"][0])
            / (r["lateral_m"][-1] - r["lateral_m"][0])
        )
        > MAX_CROSSFALL
        for r in rows
    ):
        raise ValueError("Lesson exceeds bounded minor-adjustment recipe")
    points = []
    for r in rows:
        xy = r["xy_local_m"]
        if len(xy) != 25 or any(
            len(p) != 2 or any(not math.isfinite(v) for v in p) for p in xy
        ):
            raise ValueError("Invalid lesson XY samples")
        lo, hi = r["lateral_m"][0], r["lateral_m"][-1]
        width = hi - lo
        if not 4 <= width <= 6:
            raise ValueError("Lesson width outside reviewed range")
        crossfall = (r["candidate_ground_m"][-1] - r["candidate_ground_m"][0]) / width
        if abs(math.dist(xy[0], xy[-1]) - width) > 1e-6:
            raise ValueError("XY width differs from metric transverse samples")
        for offset, point in zip(r["lateral_m"], xy):
            fraction = (offset - lo) / width
            expected = [xy[0][k] + fraction * (xy[-1][k] - xy[0][k]) for k in range(2)]
            if math.dist(point, expected) > 1e-6:
                raise ValueError("Nonlinear XY transect")
        center = [(xy[0][k] + xy[-1][k]) / 2 for k in range(2)]
        z = r["candidate_center_m"] + crossfall * (lo + hi) / 2
        points.append(
            {
                "station_m": r["station_m"],
                "center_m": [*center, z],
                "half_width_m": width / 2,
                "roll_deg": math.degrees(math.atan(crossfall)),
                "xy_m": xy,
                "target_ground_m": r["candidate_ground_m"],
            }
        )
    return {
        "schema_version": 1,
        "recipe_id": "bob-native-spline-minor-adjustment-v1",
        "exact_sha": candidate["exact_sha"],
        "profile_sha256": candidate["profile_sha256"],
        "heightmap_sha256": candidate["heightmap_sha256"],
        "status": "EXPERIMENTAL_LESSON_ONLY",
        "station_range_m": [START_M, END_M],
        "points": points,
        "side_falloff_m": 1.0,
        "layer": "Road_Earthworks",
        "production_authoring_permitted": False,
        "eligible_for_learning": False,
        "source_xy_modified": False,
        "save_map": False,
    }
