"""Build deterministic Phase 2A cliff-patch and scree placement handoff data.

Consumes the frozen Phase 1 selectors and source terrain/PCG evidence. It never
modifies the accepted Landscape or source DTM. Outputs are presentation handoff
candidates for later PCG/PCGEx consumers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sa_calobra_cliff_erosion import (  # noqa: E402
    GRID,
    NODATA,
    PROTECTED_REASON_BITS,
)
from prepare_sa_calobra_pcg_masks import verified_manifest  # noqa: E402
from prepare_sa_calobra_road_masks import distance_lower_bound  # noqa: E402
from verify_normalized_context import verify as verify_normalized  # noqa: E402
from verify_sa_calobra_lidar_masks import digest  # noqa: E402

PIXEL_SIZE_M = 0.5
SCREE_BLOCK_CELLS = 4
PATCH_ID_VERSION = "sa-calobra-cliff-patch-v1"
SCREE_ID_VERSION = "sa-calobra-scree-sample-v1"
COMPONENT_230 = {
    "name": "LandscapeComponent_230",
    "row_min": 882,
    "row_max": 1008,
    "col_min": 756,
    "col_max": 882,
    "width_cells": 127,
    "height_cells": 127,
    "sample_bounds_local_m": {"x": [378.0, 441.0], "y": [441.0, 504.0]},
}


def _grid_tuple(manifest: dict[str, object]) -> tuple[object, ...]:
    grid = manifest["grid"]
    return (
        grid["crs"],
        grid["width"],
        grid["height"],
        [float(value) for value in grid["transform"]],
    )


def verified_selector_manifest(path: Path) -> dict[str, object]:
    report = json.loads(path.read_text(encoding="utf-8"))
    content = {key: value for key, value in report.items() if key != "fingerprint"}
    actual = hashlib.sha256(
        json.dumps(
            content, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    if (
        actual != report.get("fingerprint")
        or report.get("status") != "CLIFF_EROSION_PRESENTATION_SELECTOR_CANDIDATE"
        or report.get("geometry_mutation") is not False
        or report.get("canonical_landscape_mutation") is not False
        or _grid_tuple(report) != GRID
    ):
        raise ValueError("Stale, mutating or off-grid cliff selector manifest")

    required = {
        "cliff-candidate.tif",
        "scree-candidate.tif",
        "curvature-step-proxy.tif",
        "cliff-distance-lower-bound.tif",
    }
    seen = set()
    for row in report["outputs"]:
        relative = Path(row["path"])
        if relative.is_absolute() or len(relative.parts) != 1:
            raise ValueError("Unsafe cliff selector product path")
        product = path.parent / relative
        if (
            product.stat().st_size != row["size_bytes"]
            or digest(product) != row["sha256"]
        ):
            raise ValueError("Stale cliff selector product: " + row["path"])
        if "logical_sha256" in row:
            with rasterio.open(product) as dataset:
                values = dataset.read()
                grid = report["grid"]
                if (
                    dataset.crs.to_string() != grid["crs"]
                    or dataset.width != grid["width"]
                    or dataset.height != grid["height"]
                    or list(dataset.transform)[:6] != grid["transform"]
                ):
                    raise ValueError("Cliff selector product grid mismatch")
            if (
                hashlib.sha256(values.tobytes(order="C")).hexdigest()
                != row["logical_sha256"]
            ):
                raise ValueError("Cliff selector logical hash mismatch: " + row["path"])
        seen.add(row["path"])
    if not required.issubset(seen):
        raise ValueError("Incomplete Phase 1 selector package")
    return report


def _selector_bool(values: np.ndarray, name: str) -> tuple[np.ndarray, np.ndarray]:
    if values.ndim != 2:
        raise ValueError(name + " must be a 2D selector")
    if not bool(np.isin(values, [0, 1, 255]).all()):
        raise ValueError(name + " contains values outside 0/1/255")
    return values == 1, values == 255


def label_components_8(mask: np.ndarray) -> np.ndarray:
    """Label True cells with deterministic 8-connected component IDs."""
    mask = np.asarray(mask, dtype=bool)
    if mask.ndim != 2:
        raise ValueError("Connected-component mask must be 2D")

    height, width = mask.shape
    labels = np.zeros((height, width), dtype=np.int32)
    parent = [0]
    previous_runs: list[tuple[int, int, int]] = []
    next_label = 1

    def find(label: int) -> int:
        while parent[label] != label:
            parent[label] = parent[parent[label]]
            label = parent[label]
        return label

    def union(a: int, b: int) -> int:
        root_a, root_b = find(a), find(b)
        if root_a == root_b:
            return root_a
        if root_a < root_b:
            parent[root_b] = root_a
            return root_a
        parent[root_a] = root_b
        return root_b

    for row_index in range(height):
        padded = np.zeros(width + 2, dtype=bool)
        padded[1:-1] = mask[row_index]
        starts = np.flatnonzero((~padded[:-1]) & padded[1:])
        ends = np.flatnonzero(padded[:-1] & (~padded[1:])) - 1
        current_runs: list[tuple[int, int, int]] = []
        previous_index = 0

        for start, end in zip(starts.tolist(), ends.tolist(), strict=True):
            while (
                previous_index < len(previous_runs)
                and previous_runs[previous_index][1] < start - 1
            ):
                previous_index += 1
            probe = previous_index
            overlaps = []
            while (
                probe < len(previous_runs)
                and previous_runs[probe][0] <= end + 1
            ):
                overlaps.append(previous_runs[probe][2])
                probe += 1

            if overlaps:
                roots = sorted({find(label) for label in overlaps})
                label = roots[0]
                for other in roots[1:]:
                    label = union(label, other)
                label = find(label)
            else:
                parent.append(next_label)
                label = next_label
                next_label += 1

            labels[row_index, start : end + 1] = label
            current_runs.append((start, end, label))
        previous_runs = current_runs

    mapping = np.arange(next_label, dtype=np.int32)
    for label in range(1, next_label):
        mapping[label] = find(label)
    labels = mapping[labels]

    flat = labels.ravel()
    active = flat > 0
    if not bool(active.any()):
        return labels

    positions = np.flatnonzero(active).astype(np.int64)
    roots = flat[active]
    maximum = np.iinfo(np.int64).max
    anchors = np.full(next_label, maximum, dtype=np.int64)
    np.minimum.at(anchors, roots, positions)
    live = np.flatnonzero(anchors < maximum)
    live = live[np.argsort(anchors[live], kind="stable")]

    remap = np.zeros(next_label, dtype=np.int32)
    remap[live] = np.arange(1, len(live) + 1, dtype=np.int32)
    return remap[labels]


def surface_gradients(
    elevation: np.ndarray, pixel_size_m: float = PIXEL_SIZE_M
) -> tuple[np.ndarray, np.ndarray]:
    """Return dz/dX-east and dz/dY-south on valid cardinal neighborhoods."""
    elevation = np.asarray(elevation)
    if elevation.ndim != 2 or min(elevation.shape) < 3:
        raise ValueError("Elevation must contain a 3x3 neighborhood")
    if not np.isfinite(pixel_size_m) or pixel_size_m <= 0:
        raise ValueError("Pixel size must be positive and finite")

    east = elevation[1:-1, 2:]
    west = elevation[1:-1, :-2]
    south = elevation[2:, 1:-1]
    north = elevation[:-2, 1:-1]
    center = elevation[1:-1, 1:-1]
    valid = np.logical_and.reduce(
        [
            np.isfinite(value) & (value != NODATA)
            for value in (center, east, west, south, north)
        ]
    )
    gradient_x = np.full(elevation.shape, np.nan, dtype=np.float32)
    gradient_y = np.full(elevation.shape, np.nan, dtype=np.float32)
    scale = 2.0 * pixel_size_m
    gradient_x[1:-1, 1:-1] = np.where(valid, (east - west) / scale, np.nan)
    gradient_y[1:-1, 1:-1] = np.where(valid, (south - north) / scale, np.nan)
    return gradient_x, gradient_y


def _stable_mix64(rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
    rows = np.asarray(rows, dtype=np.uint64)
    cols = np.asarray(cols, dtype=np.uint64)
    value = (rows << np.uint64(32)) | cols
    value = value + np.uint64(0x9E3779B97F4A7C15)
    value = (
        value ^ (value >> np.uint64(30))
    ) * np.uint64(0xBF58476D1CE4E5B9)
    value = (
        value ^ (value >> np.uint64(27))
    ) * np.uint64(0x94D049BB133111EB)
    return value ^ (value >> np.uint64(31))


def sample_scree_blocks(
    mask: np.ndarray, block_cells: int = SCREE_BLOCK_CELLS
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Choose one stable candidate per fixed raster block."""
    mask = np.asarray(mask, dtype=bool)
    if mask.ndim != 2 or block_cells <= 0:
        raise ValueError("Scree sampling requires a 2D mask and positive block size")

    rows, cols = np.nonzero(mask)
    if len(rows) == 0:
        return (
            rows.astype(np.int32),
            cols.astype(np.int32),
            np.empty(0, dtype=np.uint64),
        )

    priority = _stable_mix64(rows, cols)
    blocks_per_row = (mask.shape[1] + block_cells - 1) // block_cells
    block_ids = (
        (rows // block_cells).astype(np.uint64) * np.uint64(blocks_per_row)
        + (cols // block_cells).astype(np.uint64)
    )
    order = np.lexsort((cols, rows, priority, block_ids))
    ordered_blocks = block_ids[order]
    first = np.ones(len(order), dtype=bool)
    first[1:] = ordered_blocks[1:] != ordered_blocks[:-1]
    selected = order[first]

    out_rows = rows[selected]
    out_cols = cols[selected]
    out_priority = priority[selected]
    spatial = np.lexsort((out_cols, out_rows))
    return (
        out_rows[spatial].astype(np.int32),
        out_cols[spatial].astype(np.int32),
        out_priority[spatial],
    )


def aggregate_min_by_label(labels: np.ndarray, values: np.ndarray) -> np.ndarray:
    if labels.shape != values.shape:
        raise ValueError("Label/value grids must match")
    count = int(labels.max())
    result = np.full(count + 1, np.inf, dtype=np.float32)
    active = labels > 0
    np.minimum.at(
        result,
        labels[active],
        values[active].astype(np.float32, copy=False),
    )
    return result


def _stable_id(version: str, row: int, col: int) -> str:
    payload = f"{version}|EPSG:25831|4033x4033|0.5m|r={row}|c={col}"
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def _patch_id(row: int, col: int) -> str:
    return "cliff-" + _stable_id(PATCH_ID_VERSION, row, col)


def _scree_id(row: int, col: int) -> str:
    return "scree-" + _stable_id(SCREE_ID_VERSION, row, col)


def _patch_size_class(area_m2: float) -> str:
    if area_m2 < 8.0:
        return "micro"
    if area_m2 < 40.0:
        return "small"
    if area_m2 < 200.0:
        return "medium"
    if area_m2 < 1000.0:
        return "large"
    return "massif"


def _rounded(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(
                json.dumps(
                    row,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                + "\n"
            )


def _read_raster(root: Path, name: str, band: int = 1):
    with rasterio.open(root / name) as dataset:
        return dataset.read(band), dataset.profile


def _output_row(
    path: Path,
    *,
    logical_sha256: str | None = None,
    **extra,
):
    row = {
        "path": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": digest(path),
        **extra,
    }
    if logical_sha256 is not None:
        row["logical_sha256"] = logical_sha256
    return row


def prepare(
    normalized_path: Path,
    pcg_path: Path,
    selector_path: Path,
    output: Path,
):
    if output.exists():
        raise FileExistsError("Preserve previous Phase 2A handoff packages")

    normalized_verification = verify_normalized(normalized_path)
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    pcg = verified_manifest(pcg_path)
    selector = verified_selector_manifest(selector_path)
    if not (
        _grid_tuple(normalized)
        == _grid_tuple(pcg)
        == _grid_tuple(selector)
        == GRID
    ):
        raise ValueError("Phase 2A inputs do not share the frozen native grid")
    if pcg["status"] != "READY_FOR_BOUNDED_MASK_CONSUMER_WITH_FALLBACKS":
        raise ValueError("Unsupported PCG exclusion authority")

    elevation, _ = _read_raster(normalized_path.parent, "elevation.tif")
    slope, _ = _read_raster(normalized_path.parent, "slope.tif")
    roughness, _ = _read_raster(normalized_path.parent, "roughness.tif")
    cliff_values, selector_profile = _read_raster(
        selector_path.parent, "cliff-candidate.tif"
    )
    scree_values, _ = _read_raster(
        selector_path.parent, "scree-candidate.tif"
    )
    step_proxy, _ = _read_raster(
        selector_path.parent, "curvature-step-proxy.tif", band=2
    )
    cliff_distance, _ = _read_raster(
        selector_path.parent, "cliff-distance-lower-bound.tif"
    )
    reasons, _ = _read_raster(pcg_path.parent, "exclusion-reasons.tif")
    all_exclusion_distance, _ = _read_raster(
        pcg_path.parent, "exclusion-distance-lower-bound.tif"
    )

    arrays = [
        elevation,
        slope,
        roughness,
        cliff_values,
        scree_values,
        step_proxy,
        cliff_distance,
        reasons,
        all_exclusion_distance,
    ]
    if any(array.shape != elevation.shape for array in arrays):
        raise ValueError("Phase 2A raster shapes disagree")

    cliff, cliff_unknown = _selector_bool(cliff_values, "cliff selector")
    scree, scree_unknown = _selector_bool(scree_values, "scree selector")
    if not np.array_equal(cliff_unknown, scree_unknown):
        raise ValueError("Phase 1 selector unknown domains disagree")

    protected = (reasons & PROTECTED_REASON_BITS) != 0
    if bool((cliff & protected).any()) or bool((scree & protected).any()):
        raise ValueError("Phase 1 selector crosses protected authority")

    labels = label_components_8(cliff)
    if not np.array_equal(labels > 0, cliff):
        raise ValueError(
            "Connected-component reconstruction changed cliff membership"
        )
    patch_count = int(labels.max())
    if patch_count <= 0:
        raise ValueError("No cliff patches available for Phase 2A handoff")

    gradient_x, gradient_y = surface_gradients(elevation)
    if not (
        np.isfinite(gradient_x[cliff]).all()
        and np.isfinite(gradient_y[cliff]).all()
    ):
        raise ValueError(
            "Cliff patch lacks valid frozen-grid orientation evidence"
        )

    cliff_rows, cliff_cols = np.nonzero(cliff)
    cliff_labels = labels[cliff].astype(np.int32, copy=False)
    counts = np.bincount(
        cliff_labels, minlength=patch_count + 1
    ).astype(np.int64)

    def mean_by_label(values: np.ndarray) -> np.ndarray:
        sums = np.bincount(
            cliff_labels,
            weights=values[cliff].astype(np.float64, copy=False),
            minlength=patch_count + 1,
        )
        result = np.zeros(patch_count + 1, dtype=np.float64)
        result[1:] = sums[1:] / counts[1:]
        return result

    mean_row = np.bincount(
        cliff_labels,
        weights=cliff_rows.astype(np.float64),
        minlength=patch_count + 1,
    )
    mean_col = np.bincount(
        cliff_labels,
        weights=cliff_cols.astype(np.float64),
        minlength=patch_count + 1,
    )
    mean_row[1:] /= counts[1:]
    mean_col[1:] /= counts[1:]

    minimum = np.iinfo(np.int32).max
    min_row = np.full(patch_count + 1, minimum, dtype=np.int32)
    min_col = np.full(patch_count + 1, minimum, dtype=np.int32)
    max_row = np.full(patch_count + 1, -1, dtype=np.int32)
    max_col = np.full(patch_count + 1, -1, dtype=np.int32)
    np.minimum.at(min_row, cliff_labels, cliff_rows.astype(np.int32))
    np.minimum.at(min_col, cliff_labels, cliff_cols.astype(np.int32))
    np.maximum.at(max_row, cliff_labels, cliff_rows.astype(np.int32))
    np.maximum.at(max_col, cliff_labels, cliff_cols.astype(np.int32))

    flat_index = (
        cliff_rows.astype(np.int64) * cliff.shape[1] + cliff_cols
    )
    anchors = np.full(
        patch_count + 1, np.iinfo(np.int64).max, dtype=np.int64
    )
    np.minimum.at(anchors, cliff_labels, flat_index)
    anchor_row = anchors // cliff.shape[1]
    anchor_col = anchors % cliff.shape[1]

    max_step = np.full(
        patch_count + 1, -np.inf, dtype=np.float32
    )
    np.maximum.at(
        max_step,
        cliff_labels,
        step_proxy[cliff].astype(np.float32, copy=False),
    )

    mean_elevation = mean_by_label(elevation)
    mean_slope = mean_by_label(slope)
    mean_roughness = mean_by_label(roughness)
    mean_gradient_x = mean_by_label(gradient_x)
    mean_gradient_y = mean_by_label(gradient_y)

    c = COMPONENT_230
    component_slice = (
        slice(c["row_min"], c["row_max"] + 1),
        slice(c["col_min"], c["col_max"] + 1),
    )
    if (
        c["row_max"] - c["row_min"] + 1 != c["height_cells"]
        or c["col_max"] - c["col_min"] + 1 != c["width_cells"]
        or [
            c["col_min"] * PIXEL_SIZE_M,
            c["col_max"] * PIXEL_SIZE_M,
        ]
        != c["sample_bounds_local_m"]["x"]
        or [
            c["row_min"] * PIXEL_SIZE_M,
            c["row_max"] * PIXEL_SIZE_M,
        ]
        != c["sample_bounds_local_m"]["y"]
    ):
        raise ValueError("Component_230 window contract is inconsistent")

    component_labels = labels[component_slice]
    component_patch_cells = np.bincount(
        component_labels[component_labels > 0],
        minlength=patch_count + 1,
    ).astype(np.int64)

    scree_rows, scree_cols, scree_priority = sample_scree_blocks(scree)

    patch_clearance: dict[str, np.ndarray] = {
        "all_pcg_exclusions": aggregate_min_by_label(
            labels, all_exclusion_distance
        )
    }
    sample_clearance: dict[str, np.ndarray] = {
        "all_pcg_exclusions": all_exclusion_distance[
            scree_rows, scree_cols
        ].astype(np.float32, copy=True)
    }
    for name, bit in [("road", 1), ("shoulder", 2), ("bob", 4)]:
        domain = (reasons & bit) != 0
        if not bool(domain.any()):
            raise ValueError(
                "Required protected domain is absent: " + name
            )
        distance = distance_lower_bound(domain, PIXEL_SIZE_M)
        patch_clearance[name] = aggregate_min_by_label(
            labels, distance
        )
        sample_clearance[name] = distance[
            scree_rows, scree_cols
        ].astype(np.float32, copy=True)
        del distance

    patch_rows: list[dict[str, object]] = []
    seen_patch_ids = set()
    for index in range(1, patch_count + 1):
        anchor_r = int(anchor_row[index])
        anchor_c = int(anchor_col[index])
        patch_id = _patch_id(anchor_r, anchor_c)
        if patch_id in seen_patch_ids:
            raise ValueError("Stable cliff patch ID collision")
        seen_patch_ids.add(patch_id)

        gx = float(mean_gradient_x[index])
        gy = float(mean_gradient_y[index])
        normal_length = math.sqrt(gx * gx + gy * gy + 1.0)
        normal = [
            -gx / normal_length,
            -gy / normal_length,
            1.0 / normal_length,
        ]
        horizontal = math.hypot(gx, gy)
        downslope_azimuth = (
            math.degrees(math.atan2(-gy, -gx)) % 360.0
            if horizontal > 1e-12
            else None
        )

        centroid_x = float(mean_col[index]) * PIXEL_SIZE_M
        centroid_y = float(mean_row[index]) * PIXEL_SIZE_M
        area_m2 = (
            float(counts[index]) * PIXEL_SIZE_M * PIXEL_SIZE_M
        )
        patch_rows.append(
            {
                "patch_id": patch_id,
                "patch_index": index,
                "anchor_rc": [anchor_r, anchor_c],
                "bbox_rc_inclusive": [
                    int(min_row[index]),
                    int(min_col[index]),
                    int(max_row[index]),
                    int(max_col[index]),
                ],
                "bbox_sample_centres_local_m": [
                    _rounded(
                        float(min_col[index]) * PIXEL_SIZE_M, 3
                    ),
                    _rounded(
                        float(min_row[index]) * PIXEL_SIZE_M, 3
                    ),
                    _rounded(
                        float(max_col[index]) * PIXEL_SIZE_M, 3
                    ),
                    _rounded(
                        float(max_row[index]) * PIXEL_SIZE_M, 3
                    ),
                ],
                "bbox_footprint_edges_local_m": [
                    _rounded(
                        float(min_col[index]) * PIXEL_SIZE_M
                        - PIXEL_SIZE_M / 2,
                        3,
                    ),
                    _rounded(
                        float(min_row[index]) * PIXEL_SIZE_M
                        - PIXEL_SIZE_M / 2,
                        3,
                    ),
                    _rounded(
                        float(max_col[index]) * PIXEL_SIZE_M
                        + PIXEL_SIZE_M / 2,
                        3,
                    ),
                    _rounded(
                        float(max_row[index]) * PIXEL_SIZE_M
                        + PIXEL_SIZE_M / 2,
                        3,
                    ),
                ],
                "cell_count": int(counts[index]),
                "area_m2": _rounded(area_m2, 2),
                "size_class": _patch_size_class(area_m2),
                "centroid_local_xyz_m": [
                    _rounded(centroid_x, 4),
                    _rounded(centroid_y, 4),
                    _rounded(mean_elevation[index], 4),
                ],
                "centroid_epsg_xy_m": [
                    _rounded(483000.25 + centroid_x, 4),
                    _rounded(4409516.25 - centroid_y, 4),
                ],
                "mean_slope_deg": _rounded(
                    mean_slope[index], 4
                ),
                "mean_roughness_m": _rounded(
                    mean_roughness[index], 4
                ),
                "max_step_proxy_m": _rounded(
                    max_step[index], 4
                ),
                "orientation": {
                    "gradient_dz_dx_east": _rounded(gx, 6),
                    "gradient_dz_dy_south": _rounded(gy, 6),
                    "surface_normal_xyz": [
                        _rounded(value, 7) for value in normal
                    ],
                    "downslope_azimuth_deg_from_east_toward_south": (
                        None
                        if downslope_azimuth is None
                        else _rounded(downslope_azimuth, 4)
                    ),
                },
                "clearance_lower_bound_m": {
                    name: _rounded(values[index], 4)
                    for name, values in patch_clearance.items()
                },
                "component_230_cells": int(
                    component_patch_cells[index]
                ),
            }
        )

    sample_rows_out: list[dict[str, object]] = []
    seen_scree_ids = set()
    for sample_index, (row, col, priority) in enumerate(
        zip(
            scree_rows.tolist(),
            scree_cols.tolist(),
            scree_priority.tolist(),
            strict=True,
        ),
        start=1,
    ):
        sample_id = _scree_id(row, col)
        if sample_id in seen_scree_ids:
            raise ValueError("Stable scree sample ID collision")
        seen_scree_ids.add(sample_id)

        local_x = col * PIXEL_SIZE_M
        local_y = row * PIXEL_SIZE_M
        sample_rows_out.append(
            {
                "sample_id": sample_id,
                "sample_index": sample_index,
                "row": row,
                "col": col,
                "block_rc": [
                    row // SCREE_BLOCK_CELLS,
                    col // SCREE_BLOCK_CELLS,
                ],
                "priority_u64_hex": f"{int(priority):016x}",
                "local_xyz_m": [
                    _rounded(local_x, 3),
                    _rounded(local_y, 3),
                    _rounded(elevation[row, col], 4),
                ],
                "epsg_xy_m": [
                    _rounded(483000.25 + local_x, 3),
                    _rounded(4409516.25 - local_y, 3),
                ],
                "slope_deg": _rounded(slope[row, col], 4),
                "roughness_m": _rounded(
                    roughness[row, col], 4
                ),
                "step_proxy_m": _rounded(
                    step_proxy[row, col], 4
                ),
                "cliff_distance_lower_bound_m": _rounded(
                    cliff_distance[row, col], 4
                ),
                "clearance_lower_bound_m": {
                    name: _rounded(
                        values[sample_index - 1], 4
                    )
                    for name, values in sample_clearance.items()
                },
                "component_230": bool(
                    c["row_min"] <= row <= c["row_max"]
                    and c["col_min"] <= col <= c["col_max"]
                ),
            }
        )

    output.mkdir(parents=True)
    outputs = []

    label_path = output / "cliff-patch-labels.tif"
    with rasterio.open(
        label_path,
        "w",
        **{
            **selector_profile,
            "dtype": "uint32",
            "count": 1,
            "nodata": 0,
            "compress": "DEFLATE",
        },
    ) as dataset:
        dataset.write(labels.astype(np.uint32), 1)

    with rasterio.open(label_path) as dataset:
        readback = dataset.read(1)
        if (
            dataset.crs.to_string() != selector["grid"]["crs"]
            or dataset.width != selector["grid"]["width"]
            or dataset.height != selector["grid"]["height"]
            or list(dataset.transform)[:6]
            != selector["grid"]["transform"]
            or not np.array_equal(
                readback, labels.astype(np.uint32)
            )
        ):
            raise ValueError(
                "Cliff patch label raster readback mismatch"
            )

    outputs.append(
        _output_row(
            label_path,
            logical_sha256=hashlib.sha256(
                labels.astype(np.uint32).tobytes(order="C")
            ).hexdigest(),
            records=patch_count,
            semantics=(
                "0=not cliff; positive integer maps exact Phase 1 "
                "cliff cells to cliff-patches.jsonl patch_index"
            ),
        )
    )

    patch_path = output / "cliff-patches.jsonl"
    _write_jsonl(patch_path, patch_rows)
    outputs.append(
        _output_row(
            patch_path,
            logical_sha256=digest(patch_path),
            records=len(patch_rows),
            semantics=(
                "stable cliff patch metadata ordered by deterministic "
                "spatial patch_index"
            ),
        )
    )

    scree_path = output / "scree-samples.jsonl"
    _write_jsonl(scree_path, sample_rows_out)
    outputs.append(
        _output_row(
            scree_path,
            logical_sha256=digest(scree_path),
            records=len(sample_rows_out),
            semantics=(
                "one deterministic Phase 2A candidate point per "
                "occupied 4x4 source-cell block; not final rock density"
            ),
        )
    )

    component_cliff = int(cliff[component_slice].sum())
    component_scree = int(scree[component_slice].sum())
    component_protected = int(protected[component_slice].sum())
    component_invalid = int(
        cliff_unknown[component_slice].sum()
    )
    component_patch_count = int(
        np.unique(
            component_labels[component_labels > 0]
        ).size
    )
    component_sample_count = int(
        sum(row["component_230"] for row in sample_rows_out)
    )

    size_classes = {}
    for row in patch_rows:
        key = row["size_class"]
        size_classes[key] = size_classes.get(key, 0) + 1

    report = {
        "schema_version": 1,
        "status": "CLIFF_EROSION_PHASE2A_PLACEMENT_HANDOFF",
        "geometry_mutation": False,
        "canonical_landscape_mutation": False,
        "grid": normalized["grid"],
        "world_mapping": pcg["world_mapping"],
        "source_identity": {
            "normalized_fingerprint": normalized_verification[
                "fingerprint"
            ],
            "pcg_fingerprint": pcg["fingerprint"],
            "selector_fingerprint": selector["fingerprint"],
        },
        "parameters": {
            "cliff_connectivity": 8,
            "pixel_size_m": PIXEL_SIZE_M,
            "stable_patch_id": (
                "hash of fixed Sa Calobra grid identity plus "
                "deterministic top-left anchor cell; shape changes "
                "away from the anchor do not churn the ID"
            ),
            "scree_sampler": (
                "one minimum SplitMix64 coordinate-priority candidate "
                "per fixed 4x4 source-cell block"
            ),
            "scree_block_cells": SCREE_BLOCK_CELLS,
            "scree_block_size_m": (
                SCREE_BLOCK_CELLS * PIXEL_SIZE_M
            ),
            "patch_size_classes_m2": {
                "micro": "<8",
                "small": "8..<40",
                "medium": "40..<200",
                "large": "200..<1000",
                "massif": ">=1000",
            },
        },
        "counts": {
            "cliff_candidate_cells": int(cliff.sum()),
            "cliff_patch_count": patch_count,
            "cliff_patch_size_classes": size_classes,
            "scree_candidate_cells": int(scree.sum()),
            "scree_sample_count": len(sample_rows_out),
            "protected_cells": int(protected.sum()),
            "invalid_selector_cells": int(
                cliff_unknown.sum()
            ),
        },
        "coverage": {
            "cell_area_m2": PIXEL_SIZE_M * PIXEL_SIZE_M,
            "cliff_candidate_area_m2": (
                float(cliff.sum())
                * PIXEL_SIZE_M
                * PIXEL_SIZE_M
            ),
            "scree_candidate_area_m2": (
                float(scree.sum())
                * PIXEL_SIZE_M
                * PIXEL_SIZE_M
            ),
        },
        "component_230": {
            **COMPONENT_230,
            "window_cells": (
                COMPONENT_230["width_cells"]
                * COMPONENT_230["height_cells"]
            ),
            "cliff_candidate_cells": component_cliff,
            "cliff_candidate_area_m2": (
                component_cliff
                * PIXEL_SIZE_M
                * PIXEL_SIZE_M
            ),
            "cliff_patch_count_intersecting": (
                component_patch_count
            ),
            "scree_candidate_cells": component_scree,
            "scree_candidate_area_m2": (
                component_scree
                * PIXEL_SIZE_M
                * PIXEL_SIZE_M
            ),
            "scree_sample_count": component_sample_count,
            "protected_cells": component_protected,
            "invalid_selector_cells": component_invalid,
        },
        "consumer_contract": {
            "authority": (
                "Presentation handoff only. Base_DTM/Landscape and "
                "Road/BOB remain authoritative."
            ),
            "cliff_footprint": (
                "cliff-patch-labels.tif is the exact source-cell "
                "footprint. JSONL bbox metadata is an index, not "
                "replacement geometry."
            ),
            "stable_ids": (
                "Persist patch_id/sample_id in later PCG/PCGEx "
                "outputs. Never use patch_index/sample_index as "
                "durable identity."
            ),
            "orientation": (
                "Patch normal is a mean frozen-grid gradient proxy in "
                "local X east, Y south, Z up. It guides initial facing "
                "and is not a surveyed rock-face plane."
            ),
            "clearance": (
                "No asset is authorized by selector membership alone. "
                "Require known horizontal footprint radius plus "
                "explicit clearance to fit within the reported "
                "conservative lower-bound distances; "
                "road/shoulder/BOB must never be crossed."
            ),
            "unknown": (
                "Unknown selector cells cannot authorize placement. "
                "all_pcg_exclusions additionally remains fail-closed "
                "for the broader PCG exclusion authority."
            ),
            "scree": (
                "Phase 2A samples are deterministic handoff seeds only. "
                "Final talus density/blue-noise may thin or expand them "
                "only inside scree selector==1 and under the same "
                "clearance contract."
            ),
            "terrain": (
                "Do not save, smooth, erode or displace the canonical "
                "Landscape from this handoff."
            ),
        },
        "outputs": outputs,
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
    }
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            report,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    (
        output / "cliff-erosion-handoff-manifest.json"
    ).write_text(
        json.dumps(
            report, indent=2, sort_keys=True, allow_nan=False
        )
        + "\n",
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--normalized-manifest", required=True, type=Path
    )
    parser.add_argument(
        "--pcg-manifest", required=True, type=Path
    )
    parser.add_argument(
        "--selector-manifest", required=True, type=Path
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = prepare(
        args.normalized_manifest,
        args.pcg_manifest,
        args.selector_manifest,
        args.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "fingerprint": result["fingerprint"],
                "counts": result["counts"],
                "component_230": result["component_230"],
            }
        )
    )
