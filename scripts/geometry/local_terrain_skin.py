"""Bounded world-aligned terrain skin helpers for rider-close visual recovery.

This module has no Unreal dependency. It operates on sampled Landscape heights
only for presentation geometry. It never changes canonical road XY or physics.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import struct
from typing import Sequence

from scripts.geometry.sp638_local_corridor import Vec3


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
class TerrainRoadClearanceMetrics:
    adjusted_sample_count: int
    protected_sample_count: int
    max_lowering_m: float
    minimum_vertical_clearance_m: float


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
    boundary_blend_cells: int = 6,
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
    if boundary_blend_cells < 1:
        raise ValueError("boundary_blend_cells must be positive")

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

    tapered: list[tuple[float, ...]] = []
    for row in range(rows):
        values: list[float] = []
        for column in range(columns):
            edge_distance = min(
                row,
                column,
                rows - 1 - row,
                columns - 1 - column,
            )
            if edge_distance < pinned_border_cells:
                weight = 0.0
            else:
                blend_distance = edge_distance - pinned_border_cells + 1
                weight = min(
                    1.0,
                    blend_distance / float(boundary_blend_cells + 1),
                )
            values.append(
                original[row][column]
                + (current[row][column] - original[row][column]) * weight
            )
        tapered.append(tuple(values))

    result = tuple(tapered)
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


def _nearest_centerline_projection_xy(
    x_m: float,
    y_m: float,
    centerline: Sequence[Vec3],
) -> tuple[float, float]:
    if len(centerline) < 2:
        raise ValueError("road-clearance centerline needs at least 2 stations")

    best_distance_sq = math.inf
    best_z_m = 0.0
    found = False
    for start, end in zip(centerline, centerline[1:]):
        dx = end.x - start.x
        dy = end.y - start.y
        length_sq = dx * dx + dy * dy
        if length_sq <= _EPSILON:
            continue
        t = ((x_m - start.x) * dx + (y_m - start.y) * dy) / length_sq
        t = max(0.0, min(1.0, t))
        projected_x = start.x + dx * t
        projected_y = start.y + dy * t
        distance_sq = (x_m - projected_x) ** 2 + (y_m - projected_y) ** 2
        if distance_sq < best_distance_sq:
            best_distance_sq = distance_sq
            best_z_m = start.z + (end.z - start.z) * t
            found = True

    if not found:
        raise ValueError("road-clearance centerline has no stable XY segment")
    return math.sqrt(best_distance_sq), best_z_m


def apply_road_clearance_to_height_grid(
    x_coordinates_m: Sequence[float],
    y_coordinates_descending_m: Sequence[float],
    heights_m: Sequence[Sequence[float]],
    centerline_world_m: Sequence[Vec3],
    *,
    protected_half_width_m: float = 4.0,
    transition_width_m: float = 4.0,
    minimum_surface_offset_m: float = -0.07,
    vertical_clearance_m: float = 0.08,
    max_lowering_m: float = 3.0,
) -> tuple[tuple[tuple[float, ...], ...], TerrainRoadClearanceMetrics]:
    """Lower only presentation terrain that could cover road/shoulder surfaces."""

    rows, columns = _validate_grid(heights_m)
    if len(x_coordinates_m) != columns:
        raise ValueError("road-clearance x coordinate count does not match grid")
    if len(y_coordinates_descending_m) != rows:
        raise ValueError("road-clearance y coordinate count does not match grid")
    if protected_half_width_m <= 0.0:
        raise ValueError("protected_half_width_m must be positive")
    if transition_width_m <= 0.0:
        raise ValueError("transition_width_m must be positive")
    if vertical_clearance_m <= 0.0:
        raise ValueError("vertical_clearance_m must be positive")
    if max_lowering_m <= 0.0:
        raise ValueError("max_lowering_m must be positive")

    result = [list(float(value) for value in row) for row in heights_m]
    adjusted = 0
    protected = 0
    max_lowering = 0.0
    minimum_clearance = math.inf
    outer_width = protected_half_width_m + transition_width_m

    for row, y_m in enumerate(y_coordinates_descending_m):
        for column, x_m in enumerate(x_coordinates_m):
            distance_m, road_z_m = _nearest_centerline_projection_xy(
                float(x_m),
                float(y_m),
                centerline_world_m,
            )
            if distance_m > outer_width + _EPSILON:
                continue

            minimum_surface_z_m = road_z_m + minimum_surface_offset_m
            allowed_terrain_z_m = minimum_surface_z_m - vertical_clearance_m
            current_z_m = result[row][column]
            if distance_m <= protected_half_width_m + _EPSILON:
                weight = 1.0
                protected += 1
            else:
                weight = max(
                    0.0,
                    min(
                        1.0,
                        (outer_width - distance_m) / transition_width_m,
                    ),
                )

            if current_z_m > allowed_terrain_z_m + _EPSILON and weight > 0.0:
                requested_lowering = (
                    current_z_m - allowed_terrain_z_m
                ) * weight
                if requested_lowering > max_lowering_m + _EPSILON:
                    raise ValueError(
                        "road-clearance terrain lowering exceeds bounded limit: "
                        f"{requested_lowering:.3f} m > {max_lowering_m:.3f} m"
                    )
                result[row][column] = current_z_m - requested_lowering
                adjusted += 1
                max_lowering = max(max_lowering, requested_lowering)

            if distance_m <= protected_half_width_m + _EPSILON:
                minimum_clearance = min(
                    minimum_clearance,
                    minimum_surface_z_m - result[row][column],
                )

    if protected == 0:
        raise ValueError("road-clearance grid sampled no protected road cells")
    if minimum_clearance < vertical_clearance_m - 1e-8:
        raise ValueError(
            "road-clearance contract was not preserved: "
            f"{minimum_clearance:.6f} m < {vertical_clearance_m:.6f} m"
        )

    return tuple(tuple(row) for row in result), TerrainRoadClearanceMetrics(
        adjusted_sample_count=adjusted,
        protected_sample_count=protected,
        max_lowering_m=max_lowering,
        minimum_vertical_clearance_m=minimum_clearance,
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
    """Build an upward-wound world-aligned regular grid mesh."""

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
            triangles.append((a, c, b))
            triangles.append((b, c, d))

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
        normal_z = ab.x * ac.y - ab.y * ac.x
        if normal_z <= _EPSILON:
            raise ValueError(
                f"terrain skin triangle {triangle_index} is folded in XY"
            )


def terrain_skin_hash(mesh: TerrainSkinMesh) -> str:
    digest = hashlib.sha256()
    digest.update(struct.pack("<II", mesh.row_count, mesh.column_count))
    for vertex in mesh.vertices:
        digest.update(struct.pack("<ddd", vertex.x, vertex.y, vertex.z))
    for triangle in mesh.triangles:
        digest.update(struct.pack("<III", *triangle))
    return digest.hexdigest()
