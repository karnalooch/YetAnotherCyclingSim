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


def _xy_length(vector: Vec3) -> float:
    return math.hypot(vector.x, vector.y)


def _horizontal_tangent(centerline: Sequence[Vec3], index: int) -> Vec3:
    if index == 0:
        delta = centerline[1] - centerline[0]
    elif index == len(centerline) - 1:
        delta = centerline[-1] - centerline[-2]
    else:
        delta = centerline[index + 1] - centerline[index - 1]

    length = _xy_length(delta)
    if length <= _EPSILON:
        raise ValueError(
            f"centerline station {index} has no stable horizontal tangent"
        )
    return Vec3(delta.x / length, delta.y / length, 0.0)


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

    reference_offsets = tuple(point.lateral_m for point in profiles[0])
    for index, profile in enumerate(profiles[1:], start=1):
        offsets = tuple(point.lateral_m for point in profile)
        if offsets != reference_offsets:
            raise ValueError(
                "cross-section lateral offsets must stay stable across stations; "
                f"station {index} differs"
            )


def build_corridor_mesh(
    centerline: Sequence[Vec3],
    profiles: Sequence[Sequence[CrossSectionPoint]],
) -> CorridorMesh:
    """Sweep asymmetric cross-sections along a presentation-only centerline."""

    _validate_inputs(centerline, profiles)

    vertices: list[Vec3] = []
    for station_index, center in enumerate(centerline):
        tangent = _horizontal_tangent(centerline, station_index)
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
