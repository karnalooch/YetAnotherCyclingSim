"""Deterministic semantic scene-layout helpers for YACS world authoring."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
from typing import Iterable


@dataclass(frozen=True)
class TreePlacement:
    x_m: float
    y_m: float
    yaw_deg: float
    uniform_scale: float
    cluster_index: int


@dataclass(frozen=True)
class RectExclusion:
    center_x_m: float
    center_y_m: float
    width_m: float
    height_m: float

    def contains(self, x_m: float, y_m: float) -> bool:
        return (
            abs(x_m - self.center_x_m) <= self.width_m * 0.5
            and abs(y_m - self.center_y_m) <= self.height_m * 0.5
        )


def _distance_sq(a: TreePlacement, x_m: float, y_m: float) -> float:
    dx = a.x_m - x_m
    dy = a.y_m - y_m
    return dx * dx + dy * dy


def _inside_patch(
    x_m: float,
    y_m: float,
    size_x_m: float,
    size_y_m: float,
    margin_m: float,
) -> bool:
    return (
        -size_x_m * 0.5 + margin_m <= x_m <= size_x_m * 0.5 - margin_m
        and -size_y_m * 0.5 + margin_m <= y_m <= size_y_m * 0.5 - margin_m
    )


def _allowed(
    x_m: float,
    y_m: float,
    placements: list[TreePlacement],
    *,
    size_x_m: float,
    size_y_m: float,
    margin_m: float,
    min_spacing_m: float,
    exclusions: Iterable[RectExclusion],
) -> bool:
    if not _inside_patch(x_m, y_m, size_x_m, size_y_m, margin_m):
        return False
    if any(exclusion.contains(x_m, y_m) for exclusion in exclusions):
        return False
    min_spacing_sq = min_spacing_m * min_spacing_m
    return all(
        _distance_sq(existing, x_m, y_m) >= min_spacing_sq
        for existing in placements
    )


def plan_clustered_forest_patch(
    *,
    size_x_m: float,
    size_y_m: float,
    tree_count: int,
    seed: int,
    cluster_count: int = 3,
    min_spacing_m: float = 0.85,
    edge_margin_m: float = 0.35,
    min_scale: float = 0.82,
    max_scale: float = 1.22,
    irregularity: float = 0.82,
    exclusions: Iterable[RectExclusion] = (),
) -> list[TreePlacement]:
    """Create a deterministic natural-looking clustered tree layout.

    Coordinates are local patch metres around (0, 0). The caller owns world
    placement and terrain-height projection.
    """

    if size_x_m <= 0.0 or size_y_m <= 0.0:
        raise ValueError("forest patch dimensions must be positive")
    if tree_count <= 0:
        raise ValueError("tree_count must be positive")
    if cluster_count <= 0:
        raise ValueError("cluster_count must be positive")
    if min_spacing_m <= 0.0:
        raise ValueError("min_spacing_m must be positive")
    if edge_margin_m < 0.0:
        raise ValueError("edge_margin_m cannot be negative")
    if min_scale <= 0.0 or max_scale < min_scale:
        raise ValueError("invalid scale range")
    if not 0.0 <= irregularity <= 1.0:
        raise ValueError("irregularity must be inside [0, 1]")
    if (
        size_x_m <= 2.0 * edge_margin_m
        or size_y_m <= 2.0 * edge_margin_m
    ):
        raise ValueError("edge margin consumes the entire forest patch")

    exclusion_list = tuple(exclusions)
    rng = random.Random(seed)

    # Cluster centres are intentionally kept away from hard edges. A small
    # deterministic free-space fallback below prevents a bad centre draw from
    # making the whole layout fail.
    centre_margin_x = max(edge_margin_m + 0.5, size_x_m * 0.16)
    centre_margin_y = max(edge_margin_m + 0.5, size_y_m * 0.16)
    cluster_centres: list[tuple[float, float]] = []
    for _ in range(cluster_count):
        cluster_centres.append(
            (
                rng.uniform(
                    -size_x_m * 0.5 + centre_margin_x,
                    size_x_m * 0.5 - centre_margin_x,
                ),
                rng.uniform(
                    -size_y_m * 0.5 + centre_margin_y,
                    size_y_m * 0.5 - centre_margin_y,
                ),
            )
        )

    placements: list[TreePlacement] = []
    sigma_x = max(0.35, size_x_m * (0.12 + 0.16 * irregularity))
    sigma_y = max(0.35, size_y_m * (0.12 + 0.16 * irregularity))
    max_attempts = max(500, tree_count * 180)

    for attempt in range(max_attempts):
        if len(placements) >= tree_count:
            break

        cluster_index = attempt % cluster_count
        cx, cy = cluster_centres[cluster_index]

        # Most trees belong to a loose cluster; some are deliberately sampled
        # from the full patch to avoid three obvious circles.
        free_sample_probability = 0.10 + 0.22 * irregularity
        if rng.random() < free_sample_probability:
            x_m = rng.uniform(
                -size_x_m * 0.5 + edge_margin_m,
                size_x_m * 0.5 - edge_margin_m,
            )
            y_m = rng.uniform(
                -size_y_m * 0.5 + edge_margin_m,
                size_y_m * 0.5 - edge_margin_m,
            )
        else:
            x_m = rng.gauss(cx, sigma_x)
            y_m = rng.gauss(cy, sigma_y)

        if not _allowed(
            x_m,
            y_m,
            placements,
            size_x_m=size_x_m,
            size_y_m=size_y_m,
            margin_m=edge_margin_m,
            min_spacing_m=min_spacing_m,
            exclusions=exclusion_list,
        ):
            continue

        yaw_deg = rng.uniform(0.0, 360.0)
        # Slightly bias toward 1.0 while retaining a useful size range.
        raw_scale = (rng.random() + rng.random()) * 0.5
        uniform_scale = min_scale + (max_scale - min_scale) * raw_scale
        placements.append(
            TreePlacement(
                x_m=round(x_m, 6),
                y_m=round(y_m, 6),
                yaw_deg=round(yaw_deg, 6),
                uniform_scale=round(uniform_scale, 6),
                cluster_index=cluster_index,
            )
        )

    if len(placements) != tree_count:
        raise RuntimeError(
            "could not fit requested forest patch: "
            f"requested={tree_count} placed={len(placements)} "
            f"size={size_x_m}x{size_y_m}m spacing={min_spacing_m}m"
        )

    return placements


def minimum_pair_distance_m(placements: list[TreePlacement]) -> float:
    if len(placements) < 2:
        return math.inf
    minimum = math.inf
    for index, left in enumerate(placements):
        for right in placements[index + 1 :]:
            distance = math.hypot(left.x_m - right.x_m, left.y_m - right.y_m)
            minimum = min(minimum, distance)
    return minimum


def serialize_placements(
    placements: list[TreePlacement],
) -> list[dict[str, float | int]]:
    return [asdict(item) for item in placements]
