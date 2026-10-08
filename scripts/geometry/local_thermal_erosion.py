"""Deterministic bounded thermal erosion of an owned native heightfield copy."""

from __future__ import annotations

import math


def movable_samples(field, plan):
    size = field["size"]
    cells = set()
    for cell in plan["skin_cells"]:
        if cell["protected_samples"] != 0:
            raise ValueError("Protected erosion cell")
        cells.update(
            (c, r)
            for r in range(cell["row0"], cell["row1"])
            for c in range(cell["col0"], cell["col1"])
        )
    col, row = field["origin_col"], field["origin_row"]
    return [
        0 < x < size - 1
        and 0 < y < size - 1
        and all(
            (col + x + dx, row + y + dy) in cells
            for dx, dy in ((0, 0), (-1, 0), (0, -1), (-1, -1))
        )
        for y in range(size)
        for x in range(size)
    ]


def erode(field, plan, *, iterations=48, talus_slope=1.2):
    """Move equal integer height units downhill; no sediment crosses fixed edges.

    This is a thermal/talus relaxation experiment, not hydraulic weathering or
    a geological simulation. Integer pair transfers conserve the height sum and
    enforce the total one-metre envelope during every transfer, not just at end.
    """
    size, unit = field["size"], field["height_unit_cm"]
    source = field["heights"]
    if (
        size < 3
        or len(source) != size * size
        or not math.isfinite(unit)
        or unit <= 0
        or iterations < 1
        or talus_slope < 0
        or not math.isfinite(talus_slope)
        or any(type(v) is not int or not 0 <= v <= 65535 for v in source)
    ):
        raise ValueError("Invalid native heightfield or erosion parameters")
    movable = movable_samples(field, plan)
    limit = math.floor(100.0 / unit)
    lower = [max(0, h - limit) for h in source]
    upper = [min(65535, h + limit) for h in source]
    heights = list(source)
    edges = [
        (i, j)
        for i in range(len(source))
        if movable[i]
        for j in (i + 1, i + size)
        if j < len(source) and movable[j] and (j != i + 1 or i // size == j // size)
    ]
    threshold = 50.0 * talus_slope / unit
    transfers = 0
    for step in range(iterations):
        for a, b in edges if step % 2 == 0 else reversed(edges):
            high, low = (a, b) if heights[a] > heights[b] else (b, a)
            excess = heights[high] - heights[low] - threshold
            amount = min(
                max(0, math.floor(excess * 0.125)),
                heights[high] - lower[high],
                upper[low] - heights[low],
            )
            if amount:
                heights[high] -= amount
                heights[low] += amount
                transfers += 1
    delta = [(b - a) * unit for a, b in zip(source, heights)]
    return dict(field, heights=heights), {
        "method": "bounded-integer-thermal-talus-transfer",
        "iterations": iterations,
        "talus_slope": talus_slope,
        "transfers": transfers,
        "changed_samples": sum(d != 0 for d in delta),
        "max_abs_change_cm": max(map(abs, delta)),
        "limit_cm": 100.0,
        "height_sum_delta_units": sum(heights) - sum(source),
        "fixed_samples_changed": sum(
            a != b and not m for a, b, m in zip(source, heights, movable)
        ),
        "canonical_landscape_mutation": False,
        "derived_heightfield_modified": heights != source,
    }
