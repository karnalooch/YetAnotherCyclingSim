"""Bounded world-aligned terrain skin helpers for rider-close visual recovery.

This module has no Unreal dependency. It operates on sampled Landscape heights
only for presentation geometry. It never changes canonical road XY or physics.
"""

from __future__ import annotations

from collections import deque
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
class MesoGroundMesh:
    """Compact irregular mesh cut from a sampled terrain grid."""

    vertices: tuple[Vec3, ...]
    triangles: tuple[tuple[int, int, int], ...]
    source_row_count: int
    source_column_count: int
    boundary_vertex_count: int


@dataclass(frozen=True)
class MesoGroundMetrics:
    active_vertex_count: int
    triangle_count: int
    boundary_vertex_count: int
    max_abs_adjustment_m: float
    minimum_adjustment_m: float
    rms_adjustment_m: float
    boundary_max_abs_adjustment_m: float
    minimum_protected_distance_m: float | None
    minimum_protected_clearance_m: float | None
    minimum_protected_half_width_m: float | None
    maximum_protected_half_width_m: float | None


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



def _point_to_segment_distance_and_t_xy(
    point_x: float,
    point_y: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[float, float, float]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= _EPSILON:
        return math.hypot(point_x - start[0], point_y - start[1]), 0.0, 0.0
    t = (
        (point_x - start[0]) * dx + (point_y - start[1]) * dy
    ) / length_squared
    t = max(0.0, min(1.0, t))
    closest_x = start[0] + t * dx
    closest_y = start[1] + t * dy
    distance = math.hypot(point_x - closest_x, point_y - closest_y)
    segment_length = math.sqrt(length_squared)
    signed_lateral = (
        dx * (point_y - closest_y) - dy * (point_x - closest_x)
    ) / segment_length
    return distance, t, signed_lateral


def _minimum_polyline_protection_xy(
    point_x: float,
    point_y: float,
    polyline_xy_m: Sequence[tuple[float, float]],
    negative_half_widths_m: Sequence[float],
    positive_half_widths_m: Sequence[float],
) -> tuple[float, float, float] | None:
    """Return minimum signed clearance, distance and interpolated half-width."""

    if not polyline_xy_m:
        return None
    if len(polyline_xy_m) < 2:
        raise ValueError("protected centerline needs at least two points")
    if (
        len(negative_half_widths_m) != len(polyline_xy_m)
        or len(positive_half_widths_m) != len(polyline_xy_m)
    ):
        raise ValueError(
            "protected half-width profile must match protected centerline points"
        )

    best: tuple[float, float, float] | None = None
    for index in range(len(polyline_xy_m) - 1):
        distance, t, signed_lateral = _point_to_segment_distance_and_t_xy(
            point_x,
            point_y,
            polyline_xy_m[index],
            polyline_xy_m[index + 1],
        )
        if signed_lateral > _EPSILON:
            widths = positive_half_widths_m
        elif signed_lateral < -_EPSILON:
            widths = negative_half_widths_m
        else:
            widths = tuple(
                max(negative, positive)
                for negative, positive in zip(
                    negative_half_widths_m,
                    positive_half_widths_m,
                )
            )
        start_width = float(widths[index])
        end_width = float(widths[index + 1])
        half_width = start_width + t * (end_width - start_width)
        clearance = distance - half_width
        candidate = (clearance, distance, half_width)
        if best is None or candidate[0] < best[0]:
            best = candidate
    return best


def _smoothstep01(value: float) -> float:
    t = max(0.0, min(1.0, value))
    return t * t * (3.0 - 2.0 * t)


def build_bounded_meso_ground_mesh(
    x_coordinates_m: Sequence[float],
    y_coordinates_descending_m: Sequence[float],
    source_heights_m: Sequence[Sequence[float]],
    target_heights_m: Sequence[Sequence[float]],
    *,
    origin_x_m: float,
    origin_y_m: float,
    origin_z_m: float,
    center_x_m: float,
    center_y_m: float,
    radius_x_m: float,
    radius_y_m: float,
    protected_centerline_xy_m: Sequence[tuple[float, float]] = (),
    protected_half_width_m: float = 0.0,
    protected_half_widths_m: Sequence[float] = (),
    protected_negative_half_widths_m: Sequence[float] = (),
    protected_positive_half_widths_m: Sequence[float] = (),
    seam_rings: int = 4,
    lift_m: float = 0.03,
) -> tuple[MesoGroundMesh, MesoGroundMetrics]:
    """Build an irregular rider-close meso patch with pinned topology seams.

    The patch uses the sampled macro terrain only as input. A smooth target may
    correct rider-visible heightfield ribbing, but the actual mesh boundary is
    pinned exactly back to the source terrain. Triangles touching the protected
    road/shoulder corridor are omitted rather than pushing authoritative road XY.
    """

    rows, columns = _validate_grid(source_heights_m)
    target_rows, target_columns = _validate_grid(target_heights_m)
    if (target_rows, target_columns) != (rows, columns):
        raise ValueError("source and target meso-ground grids must match")
    if len(x_coordinates_m) != columns:
        raise ValueError("x coordinate count must match meso-ground columns")
    if len(y_coordinates_descending_m) != rows:
        raise ValueError("y coordinate count must match meso-ground rows")
    if radius_x_m <= 0.0 or radius_y_m <= 0.0:
        raise ValueError("meso-ground radii must be positive")
    if protected_half_width_m < 0.0:
        raise ValueError("protected_half_width_m cannot be negative")
    asymmetric_widths = bool(
        protected_negative_half_widths_m or protected_positive_half_widths_m
    )
    if asymmetric_widths and (
        protected_half_width_m > 0.0 or protected_half_widths_m
    ):
        raise ValueError(
            "use scalar, symmetric profile, or asymmetric profiles, not a mix"
        )
    if asymmetric_widths and not (
        protected_negative_half_widths_m and protected_positive_half_widths_m
    ):
        raise ValueError(
            "both negative and positive protected half-width profiles are required"
        )
    for widths in (
        protected_half_widths_m,
        protected_negative_half_widths_m,
        protected_positive_half_widths_m,
    ):
        if any(
            not math.isfinite(float(value)) or float(value) < 0.0
            for value in widths
        ):
            raise ValueError(
                "protected half-width profile must be finite and non-negative"
            )
    if seam_rings < 1:
        raise ValueError("seam_rings must be positive")
    if lift_m < 0.0:
        raise ValueError("lift_m cannot be negative")
    if any(
        x_coordinates_m[index + 1] <= x_coordinates_m[index]
        for index in range(columns - 1)
    ):
        raise ValueError("meso-ground x coordinates must be strictly increasing")
    if any(
        y_coordinates_descending_m[index + 1]
        >= y_coordinates_descending_m[index]
        for index in range(rows - 1)
    ):
        raise ValueError("meso-ground y coordinates must be strictly decreasing")
    if asymmetric_widths:
        if len(protected_centerline_xy_m) < 2:
            raise ValueError(
                "protected centerline needs at least two points for width profile"
            )
        if (
            len(protected_negative_half_widths_m) != len(protected_centerline_xy_m)
            or len(protected_positive_half_widths_m)
            != len(protected_centerline_xy_m)
        ):
            raise ValueError(
                "protected half-width profile must match protected centerline points"
            )
        negative_protection_widths = tuple(
            float(value) for value in protected_negative_half_widths_m
        )
        positive_protection_widths = tuple(
            float(value) for value in protected_positive_half_widths_m
        )
    elif protected_half_widths_m:
        if len(protected_centerline_xy_m) < 2:
            raise ValueError(
                "protected centerline needs at least two points for width profile"
            )
        if len(protected_half_widths_m) != len(protected_centerline_xy_m):
            raise ValueError(
                "protected half-width profile must match protected centerline points"
            )
        symmetric = tuple(float(value) for value in protected_half_widths_m)
        negative_protection_widths = symmetric
        positive_protection_widths = symmetric
    elif protected_centerline_xy_m:
        if protected_half_width_m > 0.0 and len(protected_centerline_xy_m) < 2:
            raise ValueError(
                "protected centerline needs at least two points when width is positive"
            )
        symmetric = tuple(
            float(protected_half_width_m) for _ in protected_centerline_xy_m
        )
        negative_protection_widths = symmetric
        positive_protection_widths = symmetric
    else:
        negative_protection_widths = ()
        positive_protection_widths = ()

    active: list[bool] = []
    protected_distances: list[float | None] = []
    protected_clearances: list[float | None] = []
    for row in range(rows):
        y = float(y_coordinates_descending_m[row])
        for column in range(columns):
            x = float(x_coordinates_m[column])
            ellipse = (
                ((x - center_x_m) / radius_x_m) ** 2
                + ((y - center_y_m) / radius_y_m) ** 2
            )
            protection = (
                _minimum_polyline_protection_xy(
                    x,
                    y,
                    protected_centerline_xy_m,
                    negative_protection_widths,
                    positive_protection_widths,
                )
                if negative_protection_widths
                else None
            )
            protected_distance = protection[1] if protection is not None else None
            protected_clearance = protection[0] if protection is not None else None
            protected_distances.append(protected_distance)
            protected_clearances.append(protected_clearance)
            outside_protected = (
                protected_clearance is None
                or protected_clearance >= -_EPSILON
            )
            active.append(ellipse <= 1.0 + _EPSILON and outside_protected)

    source_triangles: list[tuple[int, int, int]] = []
    for row in range(rows - 1):
        base = row * columns
        next_base = (row + 1) * columns
        for column in range(columns - 1):
            a = base + column
            b = a + 1
            c_index = next_base + column
            d = c_index + 1
            for triangle in ((a, c_index, b), (b, c_index, d)):
                if all(active[index] for index in triangle):
                    source_triangles.append(triangle)
    if not source_triangles:
        raise ValueError("meso-ground footprint produced no triangles")

    edge_counts: dict[tuple[int, int], int] = {}
    adjacency: dict[int, set[int]] = {}
    used_source_indices: set[int] = set()
    for triangle in source_triangles:
        used_source_indices.update(triangle)
        for start, end in (
            (triangle[0], triangle[1]),
            (triangle[1], triangle[2]),
            (triangle[2], triangle[0]),
        ):
            edge = (min(start, end), max(start, end))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1
            adjacency.setdefault(start, set()).add(end)
            adjacency.setdefault(end, set()).add(start)

    boundary_vertices = {
        vertex
        for edge, count in edge_counts.items()
        if count == 1
        for vertex in edge
    }
    if not boundary_vertices:
        raise ValueError("meso-ground mesh has no boundary")

    ring_distance: dict[int, int] = {index: 0 for index in boundary_vertices}
    queue = deque(boundary_vertices)
    while queue:
        current = queue.popleft()
        next_distance = ring_distance[current] + 1
        for neighbor in adjacency.get(current, ()):
            if neighbor in ring_distance:
                continue
            ring_distance[neighbor] = next_distance
            queue.append(neighbor)

    compact_order = sorted(used_source_indices)
    compact_index = {
        source_index: index for index, source_index in enumerate(compact_order)
    }
    vertices: list[Vec3] = []
    adjustments: list[float] = []
    boundary_adjustments: list[float] = []
    used_protected_distances: list[float] = []
    used_protected_clearances: list[float] = []

    for source_index in compact_order:
        row, column = divmod(source_index, columns)
        x = float(x_coordinates_m[column])
        y = float(y_coordinates_descending_m[row])
        source_height = float(source_heights_m[row][column])
        target_height = float(target_heights_m[row][column])
        rings_from_boundary = ring_distance.get(source_index, seam_rings)
        correction_weight = _smoothstep01(rings_from_boundary / seam_rings)
        # The macro Landscape stays visible below the local patch. Never move
        # meso ground below that sampled source surface or the heightfield can
        # win depth testing and reintroduce occlusion/ribbon artefacts. The
        # bounded repair is therefore a fill/cover envelope: low ribs may rise
        # toward the smoothed target, while source highs remain covered by the
        # small interior lift. The topology seam itself remains exactly pinned.
        target_delta = max(0.0, target_height - source_height)
        adjustment = (target_delta + lift_m) * correction_weight
        vertices.append(
            Vec3(
                x - origin_x_m,
                y - origin_y_m,
                source_height - origin_z_m + adjustment,
            )
        )
        adjustments.append(adjustment)
        if source_index in boundary_vertices:
            boundary_adjustments.append(adjustment)
        protected_distance = protected_distances[source_index]
        if protected_distance is not None:
            used_protected_distances.append(protected_distance)
        protected_clearance = protected_clearances[source_index]
        if protected_clearance is not None:
            used_protected_clearances.append(protected_clearance)

    triangles = tuple(
        tuple(compact_index[index] for index in triangle)
        for triangle in source_triangles
    )
    mesh = MesoGroundMesh(
        vertices=tuple(vertices),
        triangles=triangles,
        source_row_count=rows,
        source_column_count=columns,
        boundary_vertex_count=len(boundary_vertices),
    )
    validate_meso_ground_mesh(mesh)

    rms = math.sqrt(
        sum(value * value for value in adjustments) / len(adjustments)
    )
    metrics = MesoGroundMetrics(
        active_vertex_count=len(mesh.vertices),
        triangle_count=len(mesh.triangles),
        boundary_vertex_count=len(boundary_vertices),
        max_abs_adjustment_m=max(abs(value) for value in adjustments),
        minimum_adjustment_m=min(adjustments),
        rms_adjustment_m=rms,
        boundary_max_abs_adjustment_m=max(
            (abs(value) for value in boundary_adjustments),
            default=0.0,
        ),
        minimum_protected_distance_m=min(used_protected_distances, default=None),
        minimum_protected_clearance_m=min(
            used_protected_clearances,
            default=None,
        ),
        minimum_protected_half_width_m=min(
            (*negative_protection_widths, *positive_protection_widths),
            default=None,
        ),
        maximum_protected_half_width_m=max(
            (*negative_protection_widths, *positive_protection_widths),
            default=None,
        ),
    )
    if (
        metrics.minimum_protected_clearance_m is not None
        and metrics.minimum_protected_clearance_m < -1e-7
    ):
        raise ValueError("meso-ground entered the protected road corridor")
    if metrics.boundary_max_abs_adjustment_m > 1e-9:
        raise ValueError("meso-ground boundary must tie exactly to source terrain")
    if metrics.minimum_adjustment_m < -1e-9:
        raise ValueError("meso-ground must not fall below sampled macro terrain")
    return mesh, metrics


def validate_meso_ground_mesh(mesh: MesoGroundMesh) -> None:
    if not mesh.vertices or not mesh.triangles:
        raise ValueError("meso-ground mesh cannot be empty")
    if mesh.boundary_vertex_count < 3:
        raise ValueError("meso-ground mesh boundary is unexpectedly small")
    triangle_set: set[tuple[int, int, int]] = set()
    for triangle_index, triangle in enumerate(mesh.triangles):
        if triangle in triangle_set:
            raise ValueError(f"duplicate meso-ground triangle {triangle_index}")
        triangle_set.add(triangle)
        if any(index < 0 or index >= len(mesh.vertices) for index in triangle):
            raise ValueError(f"meso-ground triangle {triangle_index} has invalid index")
        a, b, c = (mesh.vertices[index] for index in triangle)
        ab = b - a
        ac = c - a
        normal_z = ab.x * ac.y - ab.y * ac.x
        if normal_z <= _EPSILON:
            raise ValueError(
                f"meso-ground triangle {triangle_index} is degenerate or folded in XY"
            )
    for vertex_index, vertex in enumerate(mesh.vertices):
        if not all(math.isfinite(value) for value in (vertex.x, vertex.y, vertex.z)):
            raise ValueError(f"meso-ground vertex {vertex_index} is not finite")


def meso_ground_hash(mesh: MesoGroundMesh) -> str:
    digest = hashlib.sha256()
    digest.update(
        struct.pack(
            "<III",
            mesh.source_row_count,
            mesh.source_column_count,
            mesh.boundary_vertex_count,
        )
    )
    for vertex in mesh.vertices:
        digest.update(struct.pack("<ddd", vertex.x, vertex.y, vertex.z))
    for triangle in mesh.triangles:
        digest.update(struct.pack("<III", *triangle))
    return digest.hexdigest()


def terrain_skin_hash(mesh: TerrainSkinMesh) -> str:
    digest = hashlib.sha256()
    digest.update(struct.pack("<II", mesh.row_count, mesh.column_count))
    for vertex in mesh.vertices:
        digest.update(struct.pack("<ddd", vertex.x, vertex.y, vertex.z))
    for triangle in mesh.triangles:
        digest.update(struct.pack("<III", *triangle))
    return digest.hexdigest()
