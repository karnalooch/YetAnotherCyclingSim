"""Coordinate-aware seam and validity checks for native L07 Houdini->UE tiles.

This module intentionally has no hou or unreal imports, so hosted Python can
exercise exactly the same orientation/overlap rules as the native transfer.
"""
from __future__ import annotations

import numpy as np


def edge(data, start, end, side):
    """Return edge coordinate, ascending along-edge positions, and voxel values."""
    a = np.asarray(data, dtype=np.float32)
    if a.ndim != 2 or min(a.shape) < 2 or not np.isfinite(a).all():
        raise ValueError("Invalid finite 2D tile voxel data")
    x0, z0 = float(start[0]), float(start[2])
    x1, z1 = float(end[0]), float(end[2])
    if abs(x1 - x0) < 1e-6 or abs(z1 - z0) < 1e-6:
        raise ValueError("Degenerate tile world-coordinate bounds")
    if side in ("west", "east"):
        left_is_first = x0 < x1
        col = 0 if (side == "west") == left_is_first else -1
        fixed = min(x0, x1) if side == "west" else max(x0, x1)
        along = np.linspace(z0, z1, a.shape[0], dtype=np.float64)
        values = a[:, col]
    elif side in ("south", "north"):
        south_is_first = z0 < z1
        row = 0 if (side == "south") == south_is_first else -1
        fixed = min(z0, z1) if side == "south" else max(z0, z1)
        along = np.linspace(x0, x1, a.shape[1], dtype=np.float64)
        values = a[row, :]
    else:
        raise ValueError(f"Unknown tile edge: {side}")
    if along[0] > along[-1]:
        along = along[::-1]
        values = values[::-1]
    return fixed, along, values


def compare_edge(first, second, side_a, side_b, tolerance_m=0.0001):
    """Fail closed if two adjacent tile edges are not the same physical samples."""
    (array_a, start_a, end_a) = first
    (array_b, start_b, end_b) = second
    loc_a, coords_a, values_a = edge(array_a, start_a, end_a, side_a)
    loc_b, coords_b, values_b = edge(array_b, start_b, end_b, side_b)
    if coords_a.shape != coords_b.shape:
        raise ValueError(f"Seam grids differ: {coords_a.shape} != {coords_b.shape}")
    position_error = max(
        abs(loc_a - loc_b),
        float(np.max(np.abs(coords_a - coords_b))),
    )
    if position_error > 1e-4:
        raise ValueError(
            f"Seam world-coordinate mismatch {position_error:.6f} m"
        )
    height_error = float(np.max(np.abs(values_a - values_b)))
    if not np.isfinite(height_error) or height_error > tolerance_m:
        raise ValueError(
            f"Seam voxel mismatch {height_error:.6f} m > {tolerance_m:.6f} m"
        )
    return {
        "position_error_m": position_error,
        "sample_error": height_error,
        "samples": int(values_a.size),
    }


def compare_all_four(tiles, *, tolerance_m=0.0001):
    """Check both internal X and Z seams, no assumption about storage flips."""
    pairs = (
        ("x_south", (0, 0), (1, 0), "east", "west"),
        ("x_north", (0, 1), (1, 1), "east", "west"),
        ("z_west", (0, 0), (0, 1), "north", "south"),
        ("z_east", (1, 0), (1, 1), "north", "south"),
    )
    if set(tiles) != {(0, 0), (1, 0), (0, 1), (1, 1)}:
        raise ValueError("Expected exactly four L07 tiles")
    results = {}
    for label, a, b, side_a, side_b in pairs:
        results[label] = compare_edge(
            tiles[a], tiles[b], side_a, side_b, tolerance_m
        )
    return results


def mask_padding(alpha, start, end, src_x, src_z, epsilon=0.0001):
    """Zero true out-of-source padding, with explicit (world x,z) semantics."""
    a = np.asarray(alpha, dtype=np.float32)
    if a.ndim != 2 or not np.isfinite(a).all():
        raise ValueError("Invalid Alpha array")
    if np.min(a) < -1e-5 or np.max(a) > 1.00001:
        raise ValueError("Alpha outside [0,1]")
    x = np.linspace(start[0], end[0], a.shape[1], dtype=np.float64)
    z = np.linspace(start[2], end[2], a.shape[0], dtype=np.float64)
    outside_columns = (x < min(src_x) - epsilon) | (x > max(src_x) + epsilon)
    outside_rows = (z < min(src_z) - epsilon) | (z > max(src_z) + epsilon)
    out = a.copy()
    out[outside_rows, :] = 0
    out[:, outside_columns] = 0
    padded = int(
        outside_rows.sum() * out.shape[1]
        + outside_columns.sum() * out.shape[0]
        - outside_rows.sum() * outside_columns.sum()
    )
    if padded == 0:
        raise ValueError("No outer padding detected; check world-coordinate lattice")
    return out, padded


def interpolate_bilinear(tile, start, end, x, z):
    """CPU-only reference; collision triangle interpolation is a separate test."""
    data = np.asarray(tile, dtype=np.float32)
    x0, z0, x1, z1 = start[0], start[2], end[0], end[2]
    fx = (x - x0) / (x1 - x0) * (data.shape[1] - 1)
    fz = (z - z0) / (z1 - z0) * (data.shape[0] - 1)
    if not (0 <= fx <= data.shape[1] - 1 and 0 <= fz <= data.shape[0] - 1):
        raise ValueError("Query is outside tile bounds")
    i, j = min(int(fx), data.shape[1] - 2), min(int(fz), data.shape[0] - 2)
    u, v = fx - i, fz - j
    return float(
        data[j, i] * (1 - u) * (1 - v)
        + data[j, i + 1] * u * (1 - v)
        + data[j + 1, i] * (1 - u) * v
        + data[j + 1, i + 1] * u * v
    )
