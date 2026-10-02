"""Pure geometry for BOB's transient cut-only Sa Calobra ground preview."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from scripts.geometry.sp638_local_corridor import (
    CorridorMesh,
    CrossSectionPoint,
    Vec3,
    validate_corridor_mesh,
)

CUT_CROSS_SECTION_POINTS = 4


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def build_cut_only_corridor(profile: Mapping[str, Any], *, falloff_m: float):
    if not math.isfinite(falloff_m) or falloff_m <= 0.0:
        raise ValueError("falloff_m must be positive")
    rows = profile.get("stations")
    if not isinstance(rows, list) or len(rows) < 3:
        raise ValueError("cut-only corridor needs ordered profile stations")

    vertices = []
    profiles = []
    all_x, all_y = [], []
    for row in rows:
        xy = row["xy_local_m"]
        lateral = row["lateral_m"]
        target = row["candidate_ground_m"]
        if len(xy) != 25 or len(lateral) != 25 or len(target) != 25:
            raise ValueError("cut-only corridor needs 25-point sections")

        lx, ly = (_finite(v, "left_xy") for v in xy[0])
        rx, ry = (_finite(v, "right_xy") for v in xy[-1])
        lo = _finite(lateral[0], "left_lateral")
        hi = _finite(lateral[-1], "right_lateral")
        lz = _finite(target[0], "left_target")
        rz = _finite(target[-1], "right_target")
        width = hi - lo
        dx, dy = rx - lx, ry - ly
        measured = math.hypot(dx, dy)
        if width <= 0.0 or measured <= 0.0 or abs(measured - width) > 1e-5:
            raise ValueError("cut-only XY width differs from lateral width")
        ux, uy = dx / measured, dy / measured
        crossfall = (rz - lz) / width
        points = (
            Vec3(lx - ux * falloff_m, ly - uy * falloff_m, lz - crossfall * falloff_m),
            Vec3(lx, ly, lz),
            Vec3(rx, ry, rz),
            Vec3(rx + ux * falloff_m, ry + uy * falloff_m, rz + crossfall * falloff_m),
        )
        vertices.extend(points)
        all_x.extend(point.x for point in points)
        all_y.extend(point.y for point in points)
        profiles.append((
            CrossSectionPoint(lo - falloff_m, 0.0, "left_tie"),
            CrossSectionPoint(lo, 0.0, "left_road_edge"),
            CrossSectionPoint(hi, 0.0, "right_road_edge"),
            CrossSectionPoint(hi + falloff_m, 0.0, "right_tie"),
        ))

    triangles = []
    width = CUT_CROSS_SECTION_POINTS
    for station in range(len(rows) - 1):
        row = station * width
        nxt = (station + 1) * width
        for lateral_index in range(width - 1):
            a, b0 = row + lateral_index, row + lateral_index + 1
            c, d = nxt + lateral_index, nxt + lateral_index + 1
            triangles.extend(((a, b0, c), (b0, d, c)))

    mesh = CorridorMesh(
        vertices=tuple(vertices),
        triangles=tuple(triangles),
        station_count=len(rows),
        cross_section_point_count=width,
    )
    validate_corridor_mesh(mesh)
    return mesh, tuple(profiles), {
        "min_x_m": min(all_x), "max_x_m": max(all_x),
        "min_y_m": min(all_y), "max_y_m": max(all_y),
    }


def sample_regular_grid_height(
    x_coordinates_m: Sequence[float],
    y_coordinates_descending_m: Sequence[float],
    heights_m: Sequence[Sequence[float]],
    *,
    x_m: float,
    y_m: float,
) -> float:
    if len(x_coordinates_m) < 2 or len(y_coordinates_descending_m) < 2:
        raise ValueError("regular grid needs at least 2x2 samples")
    step_x = float(x_coordinates_m[1]) - float(x_coordinates_m[0])
    step_y = float(y_coordinates_descending_m[0]) - float(y_coordinates_descending_m[1])
    if step_x <= 0.0 or step_y <= 0.0:
        raise ValueError("regular grid axes have invalid direction")
    u = (float(x_m) - float(x_coordinates_m[0])) / step_x
    v = (float(y_coordinates_descending_m[0]) - float(y_m)) / step_y
    if u < -1e-8 or v < -1e-8:
        raise ValueError("sample lies outside cut-only grid")
    column = min(len(x_coordinates_m) - 2, max(0, int(math.floor(u))))
    row = min(len(y_coordinates_descending_m) - 2, max(0, int(math.floor(v))))
    fu, fv = u - column, v - row
    if fu > 1.0 + 1e-8 or fv > 1.0 + 1e-8:
        raise ValueError("sample lies outside cut-only grid")
    a = float(heights_m[row][column])
    b0 = float(heights_m[row][column + 1])
    c = float(heights_m[row + 1][column])
    d = float(heights_m[row + 1][column + 1])
    if fu + fv <= 1.0:
        return a + (b0 - a) * fu + (c - a) * fv
    return d + (c - d) * (1.0 - fu) + (b0 - d) * (1.0 - fv)
