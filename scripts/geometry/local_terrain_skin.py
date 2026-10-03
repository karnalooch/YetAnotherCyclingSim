"""Bounded world-aligned terrain skin helpers for rider-close visual recovery.

This module has no Unreal dependency. It operates on sampled Landscape heights
only for presentation geometry. It never changes canonical road XY or physics.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import struct
from typing import Mapping, Sequence

from scripts.geometry.sp638_local_corridor import CorridorMesh, CrossSectionPoint, Vec3


_EPSILON = 1e-9


@dataclass(frozen=True)
class TerrainSkinMesh:
    vertices: tuple[Vec3, ...]
    triangles: tuple[tuple[int, int, int], ...]
    row_count: int
    column_count: int


@dataclass(frozen=True)
class TerrainSkinSmoothingMetrics:
    max_abs_adjustment_m: float
    rms_adjustment_m: float
    max_abs_laplacian_before_m: float
    max_abs_laplacian_after_m: float


@dataclass(frozen=True)
class TerrainConstraintMetrics:
    constrained_sample_count: int
    max_abs_adjustment_m: float
    rms_adjustment_m: float
    overlapping_sample_count: int
    max_overlap_delta_m: float


_DEFAULT_CORRIDOR_ROLE_WEIGHTS: Mapping[str, float] = {
    "left_tie": 0.0,
    "left_earthwork": 0.35,
    "left_shoulder": 1.0,
    "left_road_edge": 1.0,
    "right_road_edge": 1.0,
    "right_shoulder": 1.0,
    "right_earthwork": 0.35,
    "right_tie": 0.0,
}


def _validate_grid(heights: Sequence[Sequence[float]]) -> tuple[int, int]:
    if len(heights) < 3:
        raise ValueError("terrain skin needs at least 3 rows")
    columns = len(heights[0])
    if columns < 3:
        raise ValueError("terrain skin needs at least 3 columns")
    for row_index, row in enumerate(heights):
        if len(row) != columns:
            raise ValueError("terrain skin height rows must have equal width")
        for column_index, value in enumerate(row):
            if not math.isfinite(value):
                raise ValueError(
                    f"terrain skin height {row_index},{column_index} is not finite"
                )
    return len(heights), columns


def _max_abs_laplacian(
    heights: Sequence[Sequence[float]],
    *,
    excluded_border_cells: int = 1,
) -> float:
    rows, columns = _validate_grid(heights)
    border = max(1, excluded_border_cells)
    if rows <= 2 * border or columns <= 2 * border:
        raise ValueError("terrain skin grid is too small for curvature metrics")
    maximum = 0.0
    for row in range(border, rows - border):
        for column in range(border, columns - border):
            center = heights[row][column]
            average = (
                heights[row - 1][column]
                + heights[row + 1][column]
                + heights[row][column - 1]
                + heights[row][column + 1]
            ) * 0.25
            maximum = max(maximum, abs(average - center))
    return maximum


def smooth_height_grid(
    heights: Sequence[Sequence[float]],
    *,
    iterations: int = 3,
    blend: float = 0.45,
    curvature_threshold_m: float = 0.04,
    max_step_adjustment_m: float = 0.30,
    max_total_adjustment_m: float = 0.90,
    pinned_border_cells: int = 2,
) -> tuple[tuple[tuple[float, ...], ...], TerrainSkinSmoothingMetrics]:
    """Low-pass only local second-order height noise, with hard bounded edits.

    A constant or planar slope has a near-zero 4-neighbour Laplacian and remains
    unchanged. Stair/rib artefacts have high local curvature and are relaxed
    toward the neighbour mean. Outer cells stay pinned so the skin ties back to
    the macro Landscape instead of drifting at its boundary.
    """

    rows, columns = _validate_grid(heights)
    if isinstance(iterations, bool) or iterations < 1:
        raise ValueError("iterations must be a positive integer")
    if not 0.0 < blend <= 1.0:
        raise ValueError("blend must be in (0, 1]")
    if curvature_threshold_m < 0.0:
        raise ValueError("curvature_threshold_m cannot be negative")
    if max_step_adjustment_m <= 0.0 or max_total_adjustment_m <= 0.0:
        raise ValueError("adjustment bounds must be positive")
    if pinned_border_cells < 1:
        raise ValueError("pinned_border_cells must be positive")
    if rows <= 2 * pinned_border_cells or columns <= 2 * pinned_border_cells:
        raise ValueError("terrain skin grid is too small for the pinned border")

    original = tuple(tuple(float(value) for value in row) for row in heights)
    current = [list(row) for row in original]
    before = _max_abs_laplacian(
        original,
        excluded_border_cells=pinned_border_cells,
    )

    for _ in range(iterations):
        previous = [row[:] for row in current]
        for row in range(pinned_border_cells, rows - pinned_border_cells):
            for column in range(
                pinned_border_cells,
                columns - pinned_border_cells,
            ):
                center = previous[row][column]
                average = (
                    previous[row - 1][column]
                    + previous[row + 1][column]
                    + previous[row][column - 1]
                    + previous[row][column + 1]
                ) * 0.25
                laplacian = average - center
                if abs(laplacian) < curvature_threshold_m:
                    continue

                step = max(
                    -max_step_adjustment_m,
                    min(max_step_adjustment_m, laplacian * blend),
                )
                candidate = center + step
                lower = original[row][column] - max_total_adjustment_m
                upper = original[row][column] + max_total_adjustment_m
                current[row][column] = max(lower, min(upper, candidate))

    result = tuple(tuple(row) for row in current)
    adjustments = [
        result[row][column] - original[row][column]
        for row in range(rows)
        for column in range(columns)
    ]
    max_abs = max(abs(value) for value in adjustments)
    rms = math.sqrt(
        sum(value * value for value in adjustments) / len(adjustments)
    )
    after = _max_abs_laplacian(
        result,
        excluded_border_cells=pinned_border_cells,
    )
    return result, TerrainSkinSmoothingMetrics(
        max_abs_adjustment_m=max_abs,
        rms_adjustment_m=rms,
        max_abs_laplacian_before_m=before,
        max_abs_laplacian_after_m=after,
    )



def make_road_clearance_profiles(
    profiles: Sequence[Sequence[CrossSectionPoint]],
) -> tuple[tuple[CrossSectionPoint, ...], ...]:
    """Keep the first ground metre outside asphalt from rising into the road.

    The asphalt already owns the visible rideable surface above the road-edge
    ground height. On a regular 1 m terrain grid, an uphill shoulder vertex can
    otherwise form a triangle that crosses back over the asphalt edge and
    produces a moving saw-tooth seam. Preserve every lateral coordinate, role
    and road-edge height; only cap each shoulder height to its adjacent road
    edge so the terrain transition starts outside that clearance apron.
    """

    result: list[tuple[CrossSectionPoint, ...]] = []
    for station_index, profile in enumerate(profiles):
        role_points: dict[str, list[CrossSectionPoint]] = {}
        for point in profile:
            role_points.setdefault(point.role, []).append(point)

        required = (
            "left_shoulder",
            "left_road_edge",
            "right_road_edge",
            "right_shoulder",
        )
        for role in required:
            matches = role_points.get(role, [])
            if len(matches) != 1:
                raise ValueError(
                    f"corridor profile {station_index} needs exactly one {role}"
                )

        left_edge_height_m = role_points["left_road_edge"][0].vertical_m
        right_edge_height_m = role_points["right_road_edge"][0].vertical_m
        built: list[CrossSectionPoint] = []
        for point in profile:
            vertical_m = point.vertical_m
            if point.role == "left_shoulder":
                vertical_m = min(vertical_m, left_edge_height_m)
            elif point.role == "right_shoulder":
                vertical_m = min(vertical_m, right_edge_height_m)
            built.append(
                CrossSectionPoint(
                    lateral_m=point.lateral_m,
                    vertical_m=vertical_m,
                    role=point.role,
                )
            )
        result.append(tuple(built))
    return tuple(result)


def _uniform_axis_step(
    values: Sequence[float],
    *,
    descending: bool,
    name: str,
) -> float:
    if len(values) < 2:
        raise ValueError(f"{name} needs at least two coordinates")
    raw_step = float(values[1]) - float(values[0])
    if descending:
        if raw_step >= 0.0:
            raise ValueError(f"{name} must be strictly descending")
        step = -raw_step
    else:
        if raw_step <= 0.0:
            raise ValueError(f"{name} must be strictly increasing")
        step = raw_step
    for index in range(len(values) - 1):
        observed = float(values[index + 1]) - float(values[index])
        if abs(observed - raw_step) > 1e-6:
            raise ValueError(f"{name} must use a uniform grid")
    return step


def _barycentric_xy(
    a: Vec3,
    b: Vec3,
    c: Vec3,
    x: float,
    y: float,
) -> tuple[float, float, float] | None:
    denominator = (
        (b.y - c.y) * (a.x - c.x)
        + (c.x - b.x) * (a.y - c.y)
    )
    if abs(denominator) <= _EPSILON:
        return None
    wa = (
        (b.y - c.y) * (x - c.x)
        + (c.x - b.x) * (y - c.y)
    ) / denominator
    wb = (
        (c.y - a.y) * (x - c.x)
        + (a.x - c.x) * (y - c.y)
    ) / denominator
    return wa, wb, 1.0 - wa - wb


def apply_corridor_constraints_to_height_grid(
    x_coordinates_m: Sequence[float],
    y_coordinates_descending_m: Sequence[float],
    heights_m: Sequence[Sequence[float]],
    corridor_mesh: CorridorMesh,
    corridor_profiles: Sequence[Sequence[CrossSectionPoint]],
    *,
    corridor_origin_m: Vec3,
    role_weights: Mapping[str, float] | None = None,
    strong_overlap_weight: float = 0.25,
    overlap_height_tolerance_m: float = 0.10,
    adjustment_mode: str = "both",
) -> tuple[tuple[tuple[float, ...], ...], TerrainConstraintMetrics]:
    """Bake the route-local road/earthwork ribbon into one native-DTM ground grid.

    The outer tie role has zero influence, so the constrained ribbon returns to
    untouched native terrain instead of layering a second ground surface. A
    materially different strong overlap fails closed because one heightfield
    cannot safely represent stacked road levels.
    """

    rows, columns = _validate_grid(heights_m)
    if len(x_coordinates_m) != columns:
        raise ValueError("constraint x coordinate count must match grid columns")
    if len(y_coordinates_descending_m) != rows:
        raise ValueError("constraint y coordinate count must match grid rows")
    step_x = _uniform_axis_step(
        x_coordinates_m,
        descending=False,
        name="constraint x coordinates",
    )
    step_y = _uniform_axis_step(
        y_coordinates_descending_m,
        descending=True,
        name="constraint y coordinates",
    )
    if not 0.0 < strong_overlap_weight <= 1.0:
        raise ValueError("strong_overlap_weight must be in (0, 1]")
    if overlap_height_tolerance_m <= 0.0:
        raise ValueError("overlap_height_tolerance_m must be positive")
    if adjustment_mode not in {"both", "cut_only"}:
        raise ValueError("adjustment_mode must be 'both' or 'cut_only'")
    if len(corridor_profiles) != corridor_mesh.station_count:
        raise ValueError("corridor profile count must match station count")

    width = corridor_mesh.cross_section_point_count
    if width < 2:
        raise ValueError("corridor mesh cross-section is unexpectedly narrow")
    if len(corridor_mesh.vertices) != corridor_mesh.station_count * width:
        raise ValueError("corridor mesh vertex count violates station/profile layout")

    weights = dict(_DEFAULT_CORRIDOR_ROLE_WEIGHTS)
    if role_weights is not None:
        weights.update(role_weights)

    vertex_weights: list[float] = []
    for station_index, profile in enumerate(corridor_profiles):
        if len(profile) != width:
            raise ValueError(
                f"corridor profile {station_index} width does not match mesh"
            )
        if weights.get(profile[0].role) != 0.0 or weights.get(profile[-1].role) != 0.0:
            raise ValueError(
                "corridor transition must pin both outer profile roles to native terrain"
            )
        for point in profile:
            if point.role not in weights:
                raise ValueError(f"missing constraint weight for role {point.role!r}")
            weight = float(weights[point.role])
            if not 0.0 <= weight <= 1.0:
                raise ValueError(f"constraint weight for {point.role!r} is outside [0,1]")
            vertex_weights.append(weight)

    world_vertices = tuple(
        Vec3(
            vertex.x + corridor_origin_m.x,
            vertex.y + corridor_origin_m.y,
            vertex.z + corridor_origin_m.z,
        )
        for vertex in corridor_mesh.vertices
    )
    original = tuple(tuple(float(value) for value in row) for row in heights_m)
    result = [list(row) for row in original]

    claims: dict[tuple[int, int], tuple[float, float]] = {}
    overlap_samples: set[tuple[int, int]] = set()
    max_overlap_delta_m = 0.0
    x0 = float(x_coordinates_m[0])
    y0 = float(y_coordinates_descending_m[0])

    for triangle_index, triangle in enumerate(corridor_mesh.triangles):
        if min(triangle) < 0 or max(triangle) >= len(world_vertices):
            raise ValueError(f"corridor triangle {triangle_index} has an invalid index")
        ia, ib, ic = triangle
        a, b, c = world_vertices[ia], world_vertices[ib], world_vertices[ic]
        min_x = min(a.x, b.x, c.x)
        max_x = max(a.x, b.x, c.x)
        min_y = min(a.y, b.y, c.y)
        max_y = max(a.y, b.y, c.y)

        first_column = max(0, int(math.floor((min_x - x0) / step_x)) - 1)
        last_column = min(
            columns - 1,
            int(math.ceil((max_x - x0) / step_x)) + 1,
        )
        first_row = max(0, int(math.floor((y0 - max_y) / step_y)) - 1)
        last_row = min(
            rows - 1,
            int(math.ceil((y0 - min_y) / step_y)) + 1,
        )
        if first_column > last_column or first_row > last_row:
            continue

        for row in range(first_row, last_row + 1):
            y = float(y_coordinates_descending_m[row])
            for column in range(first_column, last_column + 1):
                x = float(x_coordinates_m[column])
                barycentric = _barycentric_xy(a, b, c, x, y)
                if barycentric is None:
                    continue
                wa, wb, wc = barycentric
                if min(wa, wb, wc) < -1e-8:
                    continue

                constraint_weight = max(
                    0.0,
                    min(
                        1.0,
                        wa * vertex_weights[ia]
                        + wb * vertex_weights[ib]
                        + wc * vertex_weights[ic],
                    ),
                )
                if constraint_weight <= _EPSILON:
                    continue

                target_height_m = wa * a.z + wb * b.z + wc * c.z
                native_height_m = original[row][column]
                candidate_height_m = native_height_m + constraint_weight * (
                    target_height_m - native_height_m
                )
                if adjustment_mode == "cut_only":
                    candidate_height_m = min(
                        native_height_m,
                        candidate_height_m,
                    )
                key = (row, column)
                previous = claims.get(key)
                if previous is not None:
                    overlap_samples.add(key)
                    previous_height_m, previous_weight = previous
                    overlap_delta_m = abs(candidate_height_m - previous_height_m)
                    max_overlap_delta_m = max(max_overlap_delta_m, overlap_delta_m)
                    if (
                        min(previous_weight, constraint_weight) >= strong_overlap_weight
                        and overlap_delta_m > overlap_height_tolerance_m
                    ):
                        raise ValueError(
                            "route-local corridor branches strongly overlap one "
                            f"heightfield sample at row={row} column={column}: "
                            f"delta={overlap_delta_m:.3f} m"
                        )
                    if constraint_weight > previous_weight + _EPSILON:
                        claims[key] = (candidate_height_m, constraint_weight)
                else:
                    claims[key] = (candidate_height_m, constraint_weight)

    if not claims:
        raise ValueError("corridor constraints did not touch the native terrain grid")

    adjustments: list[float] = []
    for (row, column), (height_m, _weight) in claims.items():
        adjustment_m = height_m - original[row][column]
        result[row][column] = height_m
        adjustments.append(adjustment_m)

    max_abs_adjustment_m = max(abs(value) for value in adjustments)
    rms_adjustment_m = math.sqrt(
        sum(value * value for value in adjustments) / len(adjustments)
    )
    return tuple(tuple(row) for row in result), TerrainConstraintMetrics(
        constrained_sample_count=len(adjustments),
        max_abs_adjustment_m=max_abs_adjustment_m,
        rms_adjustment_m=rms_adjustment_m,
        overlapping_sample_count=len(overlap_samples),
        max_overlap_delta_m=max_overlap_delta_m,
    )


def build_terrain_skin_mesh(
    x_coordinates_m: Sequence[float],
    y_coordinates_descending_m: Sequence[float],
    heights_m: Sequence[Sequence[float]],
    *,
    origin_x_m: float,
    origin_y_m: float,
    origin_z_m: float,
    lift_m: float = 0.02,
) -> TerrainSkinMesh:
    """Build a UE-front-facing world-aligned regular grid mesh."""

    rows, columns = _validate_grid(heights_m)
    if len(x_coordinates_m) != columns:
        raise ValueError("x coordinate count must match terrain skin columns")
    if len(y_coordinates_descending_m) != rows:
        raise ValueError("y coordinate count must match terrain skin rows")
    if any(
        x_coordinates_m[index + 1] <= x_coordinates_m[index]
        for index in range(columns - 1)
    ):
        raise ValueError("terrain skin x coordinates must be strictly increasing")
    if any(
        y_coordinates_descending_m[index + 1]
        >= y_coordinates_descending_m[index]
        for index in range(rows - 1)
    ):
        raise ValueError("terrain skin y coordinates must be strictly decreasing")

    vertices = tuple(
        Vec3(
            x_coordinates_m[column] - origin_x_m,
            y_coordinates_descending_m[row] - origin_y_m,
            heights_m[row][column] - origin_z_m + lift_m,
        )
        for row in range(rows)
        for column in range(columns)
    )

    triangles: list[tuple[int, int, int]] = []
    for row in range(rows - 1):
        base = row * columns
        next_base = (row + 1) * columns
        for column in range(columns - 1):
            a = base + column
            b = a + 1
            c = next_base + column
            d = c + 1
            # Unreal renders clockwise front faces in its left-handed world.
            # Rows descend in UE Y, so (a,b,c)/(b,d,c) faces the terrain
            # upward to the rider camera. The previous conventional +Z winding
            # exposed the underside and produced the black-ribbon/sky visual.
            triangles.append((a, b, c))
            triangles.append((b, d, c))

    mesh = TerrainSkinMesh(
        vertices=vertices,
        triangles=tuple(triangles),
        row_count=rows,
        column_count=columns,
    )
    validate_terrain_skin_mesh(mesh)
    return mesh


def validate_terrain_skin_mesh(mesh: TerrainSkinMesh) -> None:
    expected_vertices = mesh.row_count * mesh.column_count
    expected_triangles = (mesh.row_count - 1) * (mesh.column_count - 1) * 2
    if len(mesh.vertices) != expected_vertices:
        raise ValueError("terrain skin vertex count violates grid contract")
    if len(mesh.triangles) != expected_triangles:
        raise ValueError("terrain skin triangle count violates grid contract")

    for triangle_index, triangle in enumerate(mesh.triangles):
        a, b, c = (mesh.vertices[index] for index in triangle)
        ab = b - a
        ac = c - a
        conventional_normal_z = ab.x * ac.y - ab.y * ac.x
        # With descending UE Y rows, the Unreal front-facing winding has a
        # negative conventional XY cross-product. Reject degenerate or flipped
        # cells rather than silently rendering their underside.
        if conventional_normal_z >= -_EPSILON:
            raise ValueError(
                f"terrain skin triangle {triangle_index} has invalid UE front-face winding"
            )


def terrain_skin_hash(mesh: TerrainSkinMesh) -> str:
    digest = hashlib.sha256()
    digest.update(struct.pack("<II", mesh.row_count, mesh.column_count))
    for vertex in mesh.vertices:
        digest.update(struct.pack("<ddd", vertex.x, vertex.y, vertex.z))
    for triangle in mesh.triangles:
        digest.update(struct.pack("<III", *triangle))
    return digest.hexdigest()
