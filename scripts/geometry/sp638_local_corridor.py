"""Deterministic local earthwork corridor mesh kernel for the SP638 visual spike.

This module deliberately has no Unreal dependency. It converts an authoritative
presentation centerline plus one asymmetric cross-section per station into a
regular triangle strip that can later be copied into UE Dynamic Mesh / Geometry
Script. It never owns route or physics truth.

Units are metres.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import struct
from typing import Sequence


_EPSILON = 1e-9
_DEFAULT_PROTECTED_ROLES = frozenset(
    {
        "left_road_edge",
        "right_road_edge",
    }
)
_DEFAULT_SHOULDER_ROLES = frozenset(
    {
        "left_shoulder",
        "right_shoulder",
    }
)


@dataclass(frozen=True)
class Vec3:
    x: float
    y: float
    z: float

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vec3":
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)


@dataclass(frozen=True)
class CrossSectionPoint:
    """One ordered point in the local road-earthwork cross-section.

    lateral_m is signed right-offset from the presentation centerline.
    Negative values are left of the spline, positive values are right.
    vertical_m is presentation-only elevation relative to the centerline.
    """

    lateral_m: float
    vertical_m: float
    role: str


@dataclass(frozen=True)
class CorridorMesh:
    vertices: tuple[Vec3, ...]
    triangles: tuple[tuple[int, int, int], ...]
    station_count: int
    cross_section_point_count: int


@dataclass(frozen=True)
class CorridorOverlapDiagnostics:
    checked_pair_count: int
    overlap_pair_count: int
    first_overlap: tuple[int, int, int, int] | None


def _xy_length(vector: Vec3) -> float:
    return math.hypot(vector.x, vector.y)


def _validate_half_window_stations(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _horizontal_tangent(
    centerline: Sequence[Vec3],
    index: int,
    half_window_stations: int = 1,
) -> Vec3:
    """Return a horizontal frame tangent without moving canonical centerline XY.

    A wider station window is useful when the sampled centerline is denser than
    the positional accuracy of its source. Only the orientation estimate is
    filtered; mesh stations remain at their original coordinates.
    """

    _validate_half_window_stations(
        half_window_stations,
        "tangent_half_window_stations",
    )
    left = max(0, index - half_window_stations)
    right = min(len(centerline) - 1, index + half_window_stations)
    if left == right:
        raise ValueError(
            f"centerline station {index} has no tangent estimation window"
        )

    delta = centerline[right] - centerline[left]
    length = _xy_length(delta)
    if length <= _EPSILON:
        raise ValueError(
            f"centerline station {index} has no stable horizontal tangent"
        )
    return Vec3(delta.x / length, delta.y / length, 0.0)


def _signed_curvature_xy(
    centerline: Sequence[Vec3],
    index: int,
    half_window_stations: int = 1,
) -> float:
    """Return source-scale signed horizontal curvature in 1/metre.

    Positive curvature means the positive-lateral side of the corridor frame is
    the inside of the bend; negative curvature means the negative side.

    The points used for the curvature estimate may be farther apart than the
    mesh stations. This deliberately avoids treating a dense resample as if it
    contained higher-frequency positional truth than the source geometry.
    Canonical centerline coordinates are never modified.
    """

    _validate_half_window_stations(
        half_window_stations,
        "curvature_half_window_stations",
    )
    window = min(
        half_window_stations,
        index,
        len(centerline) - 1 - index,
    )
    if window < 1:
        return 0.0

    a = centerline[index - window]
    b = centerline[index]
    c = centerline[index + window]
    ab_x = b.x - a.x
    ab_y = b.y - a.y
    bc_x = c.x - b.x
    bc_y = c.y - b.y
    ca_x = a.x - c.x
    ca_y = a.y - c.y

    ab = math.hypot(ab_x, ab_y)
    bc = math.hypot(bc_x, bc_y)
    ca = math.hypot(ca_x, ca_y)
    if min(ab, bc, ca) <= _EPSILON:
        return 0.0

    cross2 = ab_x * bc_y - ab_y * bc_x
    return 2.0 * cross2 / (ab * bc * ca)


def minimum_sampled_radius_xy(
    centerline: Sequence[Vec3],
    half_window_stations: int = 1,
) -> float | None:
    """Return the minimum finite XY radius seen at the requested analysis scale."""

    _validate_half_window_stations(
        half_window_stations,
        "curvature_half_window_stations",
    )
    radii: list[float] = []
    for index in range(1, len(centerline) - 1):
        curvature = _signed_curvature_xy(
            centerline,
            index,
            half_window_stations,
        )
        if abs(curvature) > _EPSILON:
            radii.append(1.0 / abs(curvature))
    return min(radii) if radii else None


def _validate_profile(profile: Sequence[CrossSectionPoint], station_index: int) -> None:
    if len(profile) < 2:
        raise ValueError(
            f"cross-section at station {station_index} needs at least 2 points"
        )

    previous = profile[0].lateral_m
    for point_index, point in enumerate(profile):
        if not all(math.isfinite(value) for value in (point.lateral_m, point.vertical_m)):
            raise ValueError(
                f"cross-section station {station_index} point {point_index} "
                "contains a non-finite coordinate"
            )
        if not point.role:
            raise ValueError(
                f"cross-section station {station_index} point {point_index} "
                "has an empty role"
            )
        if point_index > 0 and point.lateral_m <= previous:
            raise ValueError(
                f"cross-section station {station_index} is not strictly "
                "ordered left-to-right"
            )
        previous = point.lateral_m


def _validate_inputs(
    centerline: Sequence[Vec3],
    profiles: Sequence[Sequence[CrossSectionPoint]],
) -> None:
    if len(centerline) < 2:
        raise ValueError("centerline needs at least 2 stations")
    if len(profiles) != len(centerline):
        raise ValueError(
            "one cross-section profile is required for every centerline station"
        )

    point_count = len(profiles[0])
    for index, center in enumerate(centerline):
        if not all(math.isfinite(value) for value in (center.x, center.y, center.z)):
            raise ValueError(f"centerline station {index} contains non-finite values")
        _validate_profile(profiles[index], index)
        if len(profiles[index]) != point_count:
            raise ValueError("all cross-sections must have the same point count")

    reference_roles = tuple(point.role for point in profiles[0])
    for index, profile in enumerate(profiles[1:], start=1):
        roles = tuple(point.role for point in profile)
        if roles != reference_roles:
            raise ValueError(
                "cross-section roles/order must stay stable across stations; "
                f"station {index} differs"
            )


def _side_extents(
    profile: Sequence[CrossSectionPoint],
    protected_roles: frozenset[str],
    *,
    positive_side: bool,
) -> tuple[float, float]:
    if positive_side:
        signed = [point for point in profile if point.lateral_m > 0.0]
    else:
        signed = [point for point in profile if point.lateral_m < 0.0]
    if not signed:
        return 0.0, 0.0

    outer_extent = max(abs(point.lateral_m) for point in signed)
    protected = [
        abs(point.lateral_m)
        for point in signed
        if point.role in protected_roles
    ]
    core_extent = max(protected) if protected else 0.0
    return core_extent, outer_extent


def _side_shoulder_extent(
    profile: Sequence[CrossSectionPoint],
    shoulder_roles: frozenset[str],
    *,
    positive_side: bool,
) -> float | None:
    candidates = [
        abs(point.lateral_m)
        for point in profile
        if point.role in shoulder_roles
        and (point.lateral_m > 0.0 if positive_side else point.lateral_m < 0.0)
    ]
    return max(candidates) if candidates else None


def _taper_scales(
    raw_scales: Sequence[float],
    max_delta_per_station: float,
) -> tuple[float, ...]:
    """Conservatively spread contractions so neighboring rows change gradually."""

    if max_delta_per_station <= 0.0:
        raise ValueError("max_delta_per_station must be positive")

    result: list[float] = []
    for index in range(len(raw_scales)):
        envelope = min(
            raw_scales[source]
            + max_delta_per_station * abs(index - source)
            for source in range(len(raw_scales))
        )
        result.append(min(1.0, max(0.0, envelope)))
    return tuple(result)


def _contract_profile_side(
    profile: Sequence[CrossSectionPoint],
    *,
    positive_side: bool,
    scale: float,
    protected_roles: frozenset[str],
    shoulder_roles: frozenset[str],
    minimum_shoulder_span_m: float,
    minimum_earthwork_span_m: float,
) -> tuple[CrossSectionPoint, ...]:
    core_extent, outer_extent = _side_extents(
        profile,
        protected_roles,
        positive_side=positive_side,
    )
    if outer_extent <= core_extent + _EPSILON or scale >= 1.0 - _EPSILON:
        return tuple(profile)

    contracted_outer_extent = core_extent + (outer_extent - core_extent) * scale
    shoulder_extent = _side_shoulder_extent(
        profile,
        shoulder_roles,
        positive_side=positive_side,
    )
    if shoulder_extent is None or shoulder_extent <= core_extent + _EPSILON:
        shoulder_extent = core_extent

    minimum_shoulder_extent = core_extent + minimum_shoulder_span_m
    maximum_shoulder_extent = contracted_outer_extent - minimum_earthwork_span_m
    if maximum_shoulder_extent < minimum_shoulder_extent - _EPSILON:
        side = "positive" if positive_side else "negative"
        raise ValueError(
            f"contracted {side} corridor leaves no room for minimum shoulder "
            f"{minimum_shoulder_span_m:.3f} m plus earthwork "
            f"{minimum_earthwork_span_m:.3f} m"
        )

    contracted_shoulder_extent = min(shoulder_extent, maximum_shoulder_extent)
    contracted_shoulder_extent = max(
        contracted_shoulder_extent,
        minimum_shoulder_extent,
    )
    inner_span = max(_EPSILON, shoulder_extent - core_extent)
    outer_span = max(_EPSILON, outer_extent - shoulder_extent)

    result: list[CrossSectionPoint] = []
    for point in profile:
        on_side = (
            point.lateral_m > 0.0 if positive_side else point.lateral_m < 0.0
        )
        extent = abs(point.lateral_m)
        if (
            not on_side
            or point.role in protected_roles
            or extent <= core_extent + _EPSILON
        ):
            result.append(point)
            continue

        if point.role in shoulder_roles:
            new_extent = contracted_shoulder_extent
        elif extent < shoulder_extent:
            normalized = (extent - core_extent) / inner_span
            new_extent = core_extent + normalized * (
                contracted_shoulder_extent - core_extent
            )
        else:
            normalized = (extent - shoulder_extent) / outer_span
            new_extent = contracted_shoulder_extent + normalized * (
                contracted_outer_extent - contracted_shoulder_extent
            )

        result.append(
            CrossSectionPoint(
                new_extent if positive_side else -new_extent,
                point.vertical_m,
                point.role,
            )
        )
    return tuple(result)


def _first_folded_lateral_band(
    centerline: Sequence[Vec3],
    profiles: Sequence[Sequence[CrossSectionPoint]],
    *,
    tangent_half_window_stations: int,
) -> tuple[int, int] | None:
    """Return the first station/lateral band whose swept triangles fold in XY.

    This mirrors the exact tangent-frame geometry used by build_corridor_mesh,
    but reports the offending band before a mesh is accepted. It exists only to
    tighten non-protected presentation earthwork; it never moves centerline XY
    or protected road edges.
    """

    _validate_inputs(centerline, profiles)
    _validate_half_window_stations(
        tangent_half_window_stations,
        "tangent_half_window_stations",
    )

    vertices: list[Vec3] = []
    for station_index, center in enumerate(centerline):
        tangent = _horizontal_tangent(
            centerline,
            station_index,
            tangent_half_window_stations,
        )
        right = Vec3(-tangent.y, tangent.x, 0.0)
        for section_point in profiles[station_index]:
            vertices.append(
                center
                + right * section_point.lateral_m
                + Vec3(0.0, 0.0, section_point.vertical_m)
            )

    width = len(profiles[0])
    for station_index in range(len(centerline) - 1):
        row = station_index * width
        next_row = (station_index + 1) * width
        for lateral_index in range(width - 1):
            a = vertices[row + lateral_index]
            b = vertices[row + lateral_index + 1]
            c = vertices[next_row + lateral_index]
            d = vertices[next_row + lateral_index + 1]

            first_normal_z = (
                (c.x - a.x) * (b.y - a.y)
                - (c.y - a.y) * (b.x - a.x)
            )
            second_normal_z = (
                (c.x - b.x) * (d.y - b.y)
                - (c.y - b.y) * (d.x - b.x)
            )
            if first_normal_z <= _EPSILON or second_normal_z <= _EPSILON:
                return station_index, lateral_index
    return None


def make_curvature_adaptive_profiles(
    centerline: Sequence[Vec3],
    profile: Sequence[CrossSectionPoint],
    *,
    protected_roles: frozenset[str] = _DEFAULT_PROTECTED_ROLES,
    shoulder_roles: frozenset[str] = _DEFAULT_SHOULDER_ROLES,
    clearance_fraction: float = 0.75,
    minimum_shoulder_span_m: float = 0.25,
    minimum_earthwork_span_m: float = 0.10,
    taper_per_station: float = 0.12,
    curvature_half_window_stations: int = 1,
) -> tuple[tuple[CrossSectionPoint, ...], ...]:
    """Contract inside-bend shoulder/earthwork before a swept offset can fold.

    Road edges stay fixed. The inside shoulder may narrow only where its authored
    offset would cross the local curvature radius, and it retains a bounded
    minimum width. Earthwork remains outside that shoulder. The target outer
    extent consumes only clearance_fraction of the radial clearance beyond the
    protected road edge, leaving the rest as a singularity margin.

    Contraction is tapered across neighboring samples. If the road edge plus the
    minimum shoulder and earthwork spans cannot fit, the function fails closed
    instead of pinching the rideable road.
    """

    if len(centerline) < 2:
        raise ValueError("centerline needs at least 2 stations")
    _validate_profile(profile, 0)
    if not 0.0 < clearance_fraction < 1.0:
        raise ValueError("clearance_fraction must be between 0 and 1")
    if minimum_shoulder_span_m <= 0.0:
        raise ValueError("minimum_shoulder_span_m must be positive")
    if minimum_earthwork_span_m <= 0.0:
        raise ValueError("minimum_earthwork_span_m must be positive")
    if taper_per_station <= 0.0 or taper_per_station > 1.0:
        raise ValueError("taper_per_station must be in (0, 1]")
    _validate_half_window_stations(
        curvature_half_window_stations,
        "curvature_half_window_stations",
    )

    left_core, left_outer = _side_extents(
        profile, protected_roles, positive_side=False
    )
    right_core, right_outer = _side_extents(
        profile, protected_roles, positive_side=True
    )

    raw_left = [1.0] * len(centerline)
    raw_right = [1.0] * len(centerline)

    for index in range(1, len(centerline) - 1):
        curvature = _signed_curvature_xy(
            centerline,
            index,
            curvature_half_window_stations,
        )
        if abs(curvature) <= _EPSILON:
            continue

        positive_inside = curvature > 0.0
        core_extent = right_core if positive_inside else left_core
        outer_extent = right_outer if positive_inside else left_outer
        if outer_extent <= core_extent + _EPSILON:
            continue

        local_radius = 1.0 / abs(curvature)
        if local_radius <= core_extent + _EPSILON:
            side = "positive" if positive_inside else "negative"
            raise ValueError(
                f"centerline station {index} radius {local_radius:.3f} m "
                f"reaches the {core_extent:.3f} m protected {side} road edge"
            )

        safe_outer_extent = core_extent + clearance_fraction * (
            local_radius - core_extent
        )
        minimum_outer_extent = (
            core_extent
            + minimum_shoulder_span_m
            + minimum_earthwork_span_m
        )
        if safe_outer_extent < minimum_outer_extent - _EPSILON:
            side = "positive" if positive_inside else "negative"
            raise ValueError(
                f"centerline station {index} safe outer extent "
                f"{safe_outer_extent:.3f} m on the {side} inside side cannot "
                f"preserve {minimum_shoulder_span_m:.3f} m shoulder plus "
                f"{minimum_earthwork_span_m:.3f} m earthwork beyond the "
                f"{core_extent:.3f} m protected road edge"
            )

        if safe_outer_extent >= outer_extent:
            continue

        scale = (safe_outer_extent - core_extent) / (
            outer_extent - core_extent
        )
        if positive_inside:
            raw_right[index] = scale
        else:
            raw_left[index] = scale

    left_scales = _taper_scales(raw_left, taper_per_station)
    right_scales = _taper_scales(raw_right, taper_per_station)

    left_minimum_outer = (
        left_core + minimum_shoulder_span_m + minimum_earthwork_span_m
    )
    right_minimum_outer = (
        right_core + minimum_shoulder_span_m + minimum_earthwork_span_m
    )
    left_floor_scale = (
        (left_minimum_outer - left_core) / (left_outer - left_core)
        if left_outer > left_core + _EPSILON
        else 1.0
    )
    right_floor_scale = (
        (right_minimum_outer - right_core) / (right_outer - right_core)
        if right_outer > right_core + _EPSILON
        else 1.0
    )

    def build_profiles_from_scales() -> tuple[tuple[CrossSectionPoint, ...], ...]:
        built: list[tuple[CrossSectionPoint, ...]] = []
        for left_scale, right_scale in zip(left_scales, right_scales):
            station_profile = tuple(profile)
            if left_scale < 1.0 - _EPSILON:
                station_profile = _contract_profile_side(
                    station_profile,
                    positive_side=False,
                    scale=left_scale,
                    protected_roles=protected_roles,
                    shoulder_roles=shoulder_roles,
                    minimum_shoulder_span_m=minimum_shoulder_span_m,
                    minimum_earthwork_span_m=minimum_earthwork_span_m,
                )
            if right_scale < 1.0 - _EPSILON:
                station_profile = _contract_profile_side(
                    station_profile,
                    positive_side=True,
                    scale=right_scale,
                    protected_roles=protected_roles,
                    shoulder_roles=shoulder_roles,
                    minimum_shoulder_span_m=minimum_shoulder_span_m,
                    minimum_earthwork_span_m=minimum_earthwork_span_m,
                )
            built.append(station_profile)
        return tuple(built)

    # Curvature radius is only a first-order bound. On a real non-uniform
    # hairpin, neighboring source-scale tangent frames can still make an outer
    # earthwork quad fold even when each individual radius estimate is safe.
    # Tighten only the offending non-protected side, taper the contraction
    # across neighboring stations, and fail closed if the protected road plus
    # minimum shoulder/earthwork cannot fit.
    max_sweep_iterations = max(16, len(centerline) * 2)
    for _ in range(max_sweep_iterations):
        result = build_profiles_from_scales()
        _validate_inputs(centerline, result)
        folded = _first_folded_lateral_band(
            centerline,
            result,
            tangent_half_window_stations=curvature_half_window_stations,
        )
        if folded is None:
            break

        station_index, lateral_index = folded

        # Only the terminal tie-to-macro-terrain band may be healed
        # automatically. A fold that reaches the shoulder/embankment interior
        # or protected road corridor is evidence that the canonical geometry
        # or cross-section needs an explicit redesign, not more smoothing.
        negative_terminal = lateral_index == 0
        positive_terminal = lateral_index == len(profile) - 2
        if not negative_terminal and not positive_terminal:
            # Do not heal folds that reach the inner earthwork/shoulder/road.
            # Return the bounded curvature-adaptive profile unchanged and let
            # build_corridor_mesh() retain ownership of strict topology
            # rejection for invalid canonical geometry.
            return result

        left_point = profile[lateral_index]
        right_point = profile[lateral_index + 1]
        positive_side = (
            positive_terminal
            and left_point.lateral_m >= right_core - _EPSILON
            and right_point.lateral_m > right_core + _EPSILON
        )
        negative_side = (
            negative_terminal
            and right_point.lateral_m <= -left_core + _EPSILON
            and left_point.lateral_m < -left_core - _EPSILON
        )

        if not positive_side and not negative_side:
            raise ValueError(
                "terminal corridor fold cannot be assigned to a safe "
                "non-protected side"
            )

        if positive_side:
            current_scale = min(
                right_scales[station_index],
                right_scales[station_index + 1],
            )
            if current_scale <= right_floor_scale + _EPSILON:
                return result
            target_scale = max(
                right_floor_scale,
                0.5 * (current_scale + right_floor_scale),
            )
            raw_right[station_index] = min(
                raw_right[station_index],
                target_scale,
            )
            raw_right[station_index + 1] = min(
                raw_right[station_index + 1],
                target_scale,
            )
            right_scales = _taper_scales(raw_right, taper_per_station)
        else:
            current_scale = min(
                left_scales[station_index],
                left_scales[station_index + 1],
            )
            if current_scale <= left_floor_scale + _EPSILON:
                return result
            target_scale = max(
                left_floor_scale,
                0.5 * (current_scale + left_floor_scale),
            )
            raw_left[station_index] = min(
                raw_left[station_index],
                target_scale,
            )
            raw_left[station_index + 1] = min(
                raw_left[station_index + 1],
                target_scale,
            )
            left_scales = _taper_scales(raw_left, taper_per_station)

    max_overlap_iterations = max(16, len(centerline) * 2)
    for _ in range(max_overlap_iterations):
        result = build_profiles_from_scales()
        if (
            _first_folded_lateral_band(
                centerline,
                result,
                tangent_half_window_stations=curvature_half_window_stations,
            )
            is not None
        ):
            return result

        mesh = _assemble_corridor_mesh(
            centerline,
            result,
            tangent_half_window_stations=curvature_half_window_stations,
        )
        diagnostics = corridor_global_overlap_diagnostics(mesh)
        if diagnostics.overlap_pair_count == 0:
            return result

        if diagnostics.first_overlap is None:
            raise ValueError("global overlap diagnostics lost first overlap identity")

        requested: list[tuple[bool, int]] = []
        for station_index, lateral_index in (
            (diagnostics.first_overlap[0], diagnostics.first_overlap[1]),
            (diagnostics.first_overlap[2], diagnostics.first_overlap[3]),
        ):
            if lateral_index == 0:
                requested.append((False, station_index))
            elif lateral_index == len(profile) - 2:
                requested.append((True, station_index))
            else:
                # Never contract road/shoulder/interior earthwork to hide a
                # non-local collision. Let strict mesh validation fail closed.
                return result

        changed = False
        for positive_side, station_index in requested:
            station_pair = (station_index, station_index + 1)
            scales = right_scales if positive_side else left_scales
            raw = raw_right if positive_side else raw_left
            floor_scale = right_floor_scale if positive_side else left_floor_scale
            current_scale = min(scales[index] for index in station_pair)
            if current_scale <= floor_scale + _EPSILON:
                continue

            target_scale = max(
                floor_scale,
                0.5 * (current_scale + floor_scale),
            )
            for index in station_pair:
                raw[index] = min(raw[index], target_scale)
            changed = True

        if not changed:
            return result

        left_scales = _taper_scales(raw_left, taper_per_station)
        right_scales = _taper_scales(raw_right, taper_per_station)

    return build_profiles_from_scales()


def _assemble_corridor_mesh(
    centerline: Sequence[Vec3],
    profiles: Sequence[Sequence[CrossSectionPoint]],
    *,
    tangent_half_window_stations: int = 1,
) -> CorridorMesh:
    _validate_inputs(centerline, profiles)
    _validate_half_window_stations(
        tangent_half_window_stations,
        "tangent_half_window_stations",
    )

    vertices: list[Vec3] = []
    for station_index, center in enumerate(centerline):
        tangent = _horizontal_tangent(
            centerline,
            station_index,
            tangent_half_window_stations,
        )
        right = Vec3(-tangent.y, tangent.x, 0.0)
        for section_point in profiles[station_index]:
            vertices.append(
                center
                + right * section_point.lateral_m
                + Vec3(0.0, 0.0, section_point.vertical_m)
            )

    width = len(profiles[0])
    triangles: list[tuple[int, int, int]] = []
    for station_index in range(len(centerline) - 1):
        row = station_index * width
        next_row = (station_index + 1) * width
        for lateral_index in range(width - 1):
            a = row + lateral_index
            b = row + lateral_index + 1
            c = next_row + lateral_index
            d = next_row + lateral_index + 1
            triangles.append((a, c, b))
            triangles.append((b, c, d))

    mesh = CorridorMesh(
        vertices=tuple(vertices),
        triangles=tuple(triangles),
        station_count=len(centerline),
        cross_section_point_count=width,
    )
    validate_corridor_mesh(mesh)
    return mesh


def build_corridor_mesh(
    centerline: Sequence[Vec3],
    profiles: Sequence[Sequence[CrossSectionPoint]],
    *,
    tangent_half_window_stations: int = 1,
) -> CorridorMesh:
    """Sweep asymmetric cross-sections and reject non-local overlap.

    A wider tangent window changes only the local cross-section frame. It never
    moves or resamples the canonical centerline stations.
    """

    mesh = _assemble_corridor_mesh(
        centerline,
        profiles,
        tangent_half_window_stations=tangent_half_window_stations,
    )
    validate_corridor_global_topology(mesh)
    return mesh

def _cross(a: Vec3, b: Vec3) -> Vec3:
    return Vec3(
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x,
    )


def _length(vector: Vec3) -> float:
    return math.sqrt(vector.x**2 + vector.y**2 + vector.z**2)


def triangle_normal(mesh: CorridorMesh, triangle: tuple[int, int, int]) -> Vec3:
    a, b, c = (mesh.vertices[index] for index in triangle)
    return _cross(b - a, c - a)


def validate_corridor_mesh(mesh: CorridorMesh) -> None:
    expected_vertices = mesh.station_count * mesh.cross_section_point_count
    expected_triangles = (
        (mesh.station_count - 1) * (mesh.cross_section_point_count - 1) * 2
    )
    if len(mesh.vertices) != expected_vertices:
        raise ValueError("corridor vertex count does not match the grid contract")
    if len(mesh.triangles) != expected_triangles:
        raise ValueError("corridor triangle count does not match the grid contract")

    for triangle_index, triangle in enumerate(mesh.triangles):
        if len(set(triangle)) != 3:
            raise ValueError(f"triangle {triangle_index} repeats a vertex")
        if min(triangle) < 0 or max(triangle) >= len(mesh.vertices):
            raise ValueError(f"triangle {triangle_index} has an invalid index")

        normal = triangle_normal(mesh, triangle)
        if _length(normal) <= _EPSILON:
            raise ValueError(f"triangle {triangle_index} is degenerate")
        if normal.z <= _EPSILON:
            raise ValueError(
                f"triangle {triangle_index} is inverted or folded in XY"
            )



def _orientation_xy(a: Vec3, b: Vec3, c: Vec3) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _strict_segment_intersection_xy(
    a: Vec3,
    b: Vec3,
    c: Vec3,
    d: Vec3,
) -> bool:
    ab_c = _orientation_xy(a, b, c)
    ab_d = _orientation_xy(a, b, d)
    cd_a = _orientation_xy(c, d, a)
    cd_b = _orientation_xy(c, d, b)
    return (
        ab_c * ab_d < -_EPSILON
        and cd_a * cd_b < -_EPSILON
    )


def _strict_point_in_triangle_xy(
    point: Vec3,
    a: Vec3,
    b: Vec3,
    c: Vec3,
) -> bool:
    o1 = _orientation_xy(a, b, point)
    o2 = _orientation_xy(b, c, point)
    o3 = _orientation_xy(c, a, point)
    has_positive = max(o1, o2, o3) > _EPSILON
    has_negative = min(o1, o2, o3) < -_EPSILON
    if has_positive and has_negative:
        return False
    return min(abs(o1), abs(o2), abs(o3)) > _EPSILON


def _triangles_overlap_xy(
    first: tuple[Vec3, Vec3, Vec3],
    second: tuple[Vec3, Vec3, Vec3],
) -> bool:
    first_edges = (
        (first[0], first[1]),
        (first[1], first[2]),
        (first[2], first[0]),
    )
    second_edges = (
        (second[0], second[1]),
        (second[1], second[2]),
        (second[2], second[0]),
    )
    if any(
        _strict_segment_intersection_xy(a, b, c, d)
        for a, b in first_edges
        for c, d in second_edges
    ):
        return True
    return (
        _strict_point_in_triangle_xy(first[0], *second)
        or _strict_point_in_triangle_xy(second[0], *first)
    )


def corridor_global_overlap_diagnostics(
    mesh: CorridorMesh,
    *,
    minimum_station_gap: int = 2,
    z_clearance_m: float = 0.05,
) -> CorridorOverlapDiagnostics:
    """Detect non-local swept-quad overlap without penalizing shared topology."""

    if minimum_station_gap < 2:
        raise ValueError("minimum_station_gap must be at least 2")
    if z_clearance_m < 0.0:
        raise ValueError("z_clearance_m cannot be negative")

    width = mesh.cross_section_point_count
    quads: list[
        tuple[
            int,
            int,
            tuple[Vec3, Vec3, Vec3, Vec3],
            tuple[float, float, float, float, float, float],
        ]
    ] = []
    for station_index in range(mesh.station_count - 1):
        row = station_index * width
        next_row = (station_index + 1) * width
        for lateral_index in range(width - 1):
            a = mesh.vertices[row + lateral_index]
            b = mesh.vertices[row + lateral_index + 1]
            c = mesh.vertices[next_row + lateral_index]
            d = mesh.vertices[next_row + lateral_index + 1]
            points = (a, b, c, d)
            quads.append(
                (
                    station_index,
                    lateral_index,
                    points,
                    (
                        min(point.x for point in points),
                        max(point.x for point in points),
                        min(point.y for point in points),
                        max(point.y for point in points),
                        min(point.z for point in points),
                        max(point.z for point in points),
                    ),
                )
            )

    checked = 0
    overlaps = 0
    first_overlap: tuple[int, int, int, int] | None = None
    for index, first in enumerate(quads):
        first_station, first_band, first_points, first_bounds = first
        for second in quads[index + 1 :]:
            second_station, second_band, second_points, second_bounds = second
            if abs(first_station - second_station) < minimum_station_gap:
                continue

            if (
                first_bounds[1] <= second_bounds[0] + _EPSILON
                or second_bounds[1] <= first_bounds[0] + _EPSILON
                or first_bounds[3] <= second_bounds[2] + _EPSILON
                or second_bounds[3] <= first_bounds[2] + _EPSILON
            ):
                continue
            if (
                first_bounds[5] + z_clearance_m < second_bounds[4]
                or second_bounds[5] + z_clearance_m < first_bounds[4]
            ):
                continue

            checked += 1
            first_triangles = (
                (first_points[0], first_points[2], first_points[1]),
                (first_points[1], first_points[2], first_points[3]),
            )
            second_triangles = (
                (second_points[0], second_points[2], second_points[1]),
                (second_points[1], second_points[2], second_points[3]),
            )
            if not any(
                _triangles_overlap_xy(first_triangle, second_triangle)
                for first_triangle in first_triangles
                for second_triangle in second_triangles
            ):
                continue

            overlaps += 1
            if first_overlap is None:
                first_overlap = (
                    first_station,
                    first_band,
                    second_station,
                    second_band,
                )

    return CorridorOverlapDiagnostics(
        checked_pair_count=checked,
        overlap_pair_count=overlaps,
        first_overlap=first_overlap,
    )


def validate_corridor_global_topology(mesh: CorridorMesh) -> None:
    diagnostics = corridor_global_overlap_diagnostics(mesh)
    if diagnostics.overlap_pair_count > 0:
        raise ValueError(
            "corridor has non-local XY overlap: "
            f"count={diagnostics.overlap_pair_count} "
            f"first={diagnostics.first_overlap}"
        )

def corridor_mesh_hash(mesh: CorridorMesh) -> str:
    """Return a stable binary hash for deterministic-output regression tests."""

    digest = hashlib.sha256()
    digest.update(struct.pack("<II", mesh.station_count, mesh.cross_section_point_count))
    for vertex in mesh.vertices:
        digest.update(struct.pack("<ddd", vertex.x, vertex.y, vertex.z))
    for triangle in mesh.triangles:
        digest.update(struct.pack("<III", *triangle))
    return digest.hexdigest()


def make_constant_profiles(
    station_count: int,
    profile: Sequence[CrossSectionPoint],
) -> tuple[tuple[CrossSectionPoint, ...], ...]:
    """Repeat an immutable cross-section for simple deterministic proofs."""

    frozen = tuple(profile)
    return tuple(frozen for _ in range(station_count))
