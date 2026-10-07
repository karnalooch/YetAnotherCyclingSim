"""Prepare deterministic Component_230 cliff/scree visual placement plan.

Phase 2B visual proof only. The hard exclusion policy is intentionally narrow:
pavement + conservative shoulder + mapped water buffered by 0.5 m. BOB,
buildings, infrastructure and other/unknown LiDAR exclusions remain deferred.

Attempt 3 builds a small number of connected coarse cliff-skin clusters instead
of one independent plate per local block. The UE consumer drapes each cluster
over real Landscape heights, smooths only the presentation skin, and tucks its
boundary back under the canonical terrain. No canonical selector or Landscape
geometry is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sa_calobra_cliff_erosion import GRID, classify  # noqa: E402
from prepare_sa_calobra_cliff_erosion_handoff import label_components_8  # noqa: E402
from prepare_sa_calobra_pcg_masks import verified_manifest  # noqa: E402
from prepare_sa_calobra_road_masks import distance_lower_bound  # noqa: E402
from verify_normalized_context import verify as verify_normalized  # noqa: E402
from verify_sa_calobra_lidar_masks import digest  # noqa: E402

PIXEL_SIZE_M = 0.5
ROAD_BIT = 1
SHOULDER_BIT = 2
WATER_BUFFER_M = 0.5
COMPONENT = {
    "name": "LandscapeComponent_230",
    "row_min": 882,
    "row_max": 1008,
    "col_min": 756,
    "col_max": 882,
    "width_cells": 127,
    "height_cells": 127,
    "x_min_m": 378.0,
    "x_max_m": 441.0,
    "y_min_m": 441.0,
    "y_max_m": 504.0,
}

# A skin cell spans 4 source-grid intervals = 2 m. This is coarse enough to
# bridge native heightfield stair-step noise but still follows the real cliff.
SKIN_STEP_CELLS = 4
SKIN_MIN_SOURCE_CLIFF_SAMPLES = 4
SKIN_MIN_CLUSTER_CELLS = 2
SKIN_MAX_CLUSTERS = 24
SCREE_BLOCK_CELLS = 8
MAX_SCREE_ROCKS = 40


def _grid_tuple(manifest: dict[str, object]) -> tuple[object, ...]:
    grid = manifest["grid"]
    return (
        grid["crs"],
        grid["width"],
        grid["height"],
        [float(value) for value in grid["transform"]],
    )


def _read(root: Path, name: str, band: int = 1):
    with rasterio.open(root / name) as dataset:
        return dataset.read(band), dataset.profile


def _unit_interval(key: str) -> float:
    value = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big")
    return value / float((1 << 64) - 1)


def mapped_water_mask(
    features: list[dict[str, object]],
    *,
    buffer_m: float,
    out_shape: tuple[int, int],
    transform,
) -> np.ndarray:
    geometries = []
    for record in features:
        if record.get("group") != "water":
            continue
        geometry = shape(record["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError("Invalid mapped water geometry")
        if buffer_m > 0 and geometry.geom_type not in ("Polygon", "MultiPolygon"):
            geometry = geometry.buffer(buffer_m)
        geometries.append((geometry.__geo_interface__, 1))
    if not geometries:
        raise ValueError("No mapped water geometry")
    return (
        rasterize(
            geometries,
            out_shape=out_shape,
            transform=transform,
            fill=0,
            dtype="uint8",
            all_touched=True,
        )
        > 0
    )


def _representative(
    mask: np.ndarray,
    score: np.ndarray,
    row0: int,
    row1: int,
    col0: int,
    col1: int,
) -> tuple[int, int, int] | None:
    local = mask[row0:row1, col0:col1]
    rows, cols = np.nonzero(local)
    if len(rows) == 0:
        return None
    world_rows = rows + row0
    world_cols = cols + col0
    values = score[world_rows, world_cols]
    order = np.lexsort((world_cols, world_rows, -values))
    index = int(order[0])
    return int(world_rows[index]), int(world_cols[index]), int(len(rows))


def _neighbour_count(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask.astype(np.uint8), 1)
    result = np.zeros(mask.shape, dtype=np.uint8)
    for dr in range(3):
        for dc in range(3):
            if dr == 1 and dc == 1:
                continue
            result += padded[dr : dr + mask.shape[0], dc : dc + mask.shape[1]]
    return result


def _supported_bridge(seed: np.ndarray, support: np.ndarray) -> np.ndarray:
    """Join one-cell gaps only where source cliff evidence still exists."""
    result = seed.copy()
    for _ in range(2):
        neighbours = _neighbour_count(result)
        horizontal = np.zeros_like(result)
        vertical = np.zeros_like(result)
        horizontal[:, 1:-1] = result[:, :-2] & result[:, 2:]
        vertical[1:-1, :] = result[:-2, :] & result[2:, :]
        fill = support & (~result) & (
            (neighbours >= 4) | horizontal | vertical
        )
        result |= fill

    # Remove unsupported singletons, but keep every multi-cell chain.
    neighbours = _neighbour_count(result)
    result &= neighbours > 0
    return result


def _coarse_skin_cells(
    cliff: np.ndarray,
    protected: np.ndarray,
) -> tuple[list[dict[str, object]], np.ndarray]:
    row_nodes = list(
        range(COMPONENT["row_min"], COMPONENT["row_max"], SKIN_STEP_CELLS)
    )
    col_nodes = list(
        range(COMPONENT["col_min"], COMPONENT["col_max"], SKIN_STEP_CELLS)
    )
    shape_ = (len(row_nodes), len(col_nodes))
    occupancy = np.zeros(shape_, dtype=np.int16)
    support = np.zeros(shape_, dtype=bool)
    seed = np.zeros(shape_, dtype=bool)
    metadata: dict[tuple[int, int], dict[str, int]] = {}

    for grid_r, row0 in enumerate(row_nodes):
        row1 = min(row0 + SKIN_STEP_CELLS, COMPONENT["row_max"])
        for grid_c, col0 in enumerate(col_nodes):
            col1 = min(col0 + SKIN_STEP_CELLS, COMPONENT["col_max"])
            # Include both end samples so neighbouring skin cells share evidence
            # along their common edge.
            block = cliff[row0 : row1 + 1, col0 : col1 + 1]
            protected_block = protected[row0 : row1 + 1, col0 : col1 + 1]
            count = int(block.sum())
            occupancy[grid_r, grid_c] = count
            support[grid_r, grid_c] = count > 0
            # Hard authority stays fail-closed for each 2 m skin cell.
            allowed = not bool(protected_block.any())
            seed[grid_r, grid_c] = (
                allowed and count >= SKIN_MIN_SOURCE_CLIFF_SAMPLES
            )
            metadata[(grid_r, grid_c)] = {
                "row0": row0,
                "row1": row1,
                "col0": col0,
                "col1": col1,
                "source_cliff_samples": count,
                "source_sample_count": int(block.size),
                "protected_samples": int(protected_block.sum()),
            }

    joined = _supported_bridge(seed, support)
    labels = label_components_8(joined)
    cells: list[dict[str, object]] = []

    counts = np.bincount(labels.ravel())
    accepted_labels = {
        label
        for label in range(1, len(counts))
        if int(counts[label]) >= SKIN_MIN_CLUSTER_CELLS
    }

    for grid_r in range(joined.shape[0]):
        for grid_c in range(joined.shape[1]):
            label = int(labels[grid_r, grid_c])
            if label not in accepted_labels:
                continue
            row = metadata[(grid_r, grid_c)]
            cluster_id = "skin-" + hashlib.sha256(
                (
                    "component230-skin-v1|"
                    f"label={label}|r={grid_r}|c={grid_c}"
                ).encode()
            ).hexdigest()[:10]
            cells.append(
                {
                    "grid_rc": [grid_r, grid_c],
                    "cluster_label": label,
                    "cluster_cell_id": cluster_id,
                    **row,
                }
            )

    # Relabel clusters by deterministic top-left cell, not scipy/union order.
    by_label: dict[int, list[dict[str, object]]] = {}
    for row in cells:
        by_label.setdefault(int(row["cluster_label"]), []).append(row)
    stable_ids: dict[int, str] = {}
    for label, rows in by_label.items():
        anchor = min(
            (int(row["row0"]), int(row["col0"])) for row in rows
        )
        stable_ids[label] = "cluster-" + hashlib.sha256(
            f"component230-cliff-skin|r={anchor[0]}|c={anchor[1]}".encode()
        ).hexdigest()[:12]
    for row in cells:
        row["cluster_id"] = stable_ids[int(row["cluster_label"])]
        row.pop("cluster_label")
        row.pop("cluster_cell_id")

    cluster_labels = sorted(stable_ids)
    if len(cluster_labels) > SKIN_MAX_CLUSTERS:
        raise ValueError(
            "Connected skin clustering is still too fragmented: "
            f"{len(cluster_labels)} > {SKIN_MAX_CLUSTERS}"
        )
    return cells, occupancy


def build_plan(
    elevation: np.ndarray,
    slope: np.ndarray,
    roughness: np.ndarray,
    reasons: np.ndarray,
    water: np.ndarray,
) -> dict[str, object]:
    protected = ((reasons & ROAD_BIT) != 0) | ((reasons & SHOULDER_BIT) != 0) | water
    classified = classify(
        slope,
        roughness,
        elevation,
        protected,
        pixel_size_m=PIXEL_SIZE_M,
    )
    cliff = np.asarray(classified["cliff_selector"]) == 1
    scree = np.asarray(classified["scree_selector"]) == 1
    step = np.asarray(classified["step_proxy_m"])
    clearance = distance_lower_bound(protected, PIXEL_SIZE_M)

    view = (
        slice(COMPONENT["row_min"], COMPONENT["row_max"] + 1),
        slice(COMPONENT["col_min"], COMPONENT["col_max"] + 1),
    )
    skin_cells, coarse_occupancy = _coarse_skin_cells(cliff, protected)
    cluster_ids = sorted({str(row["cluster_id"]) for row in skin_cells})

    # Cluster receipts provide aggregate source severity and conservative
    # clearance, but UE derives actual vertex heights from Landscape traces.
    clusters: list[dict[str, object]] = []
    for cluster_id in cluster_ids:
        rows = [row for row in skin_cells if row["cluster_id"] == cluster_id]
        r0 = min(int(row["row0"]) for row in rows)
        r1 = max(int(row["row1"]) for row in rows)
        c0 = min(int(row["col0"]) for row in rows)
        c1 = max(int(row["col1"]) for row in rows)
        local = cliff[r0 : r1 + 1, c0 : c1 + 1]
        local_slope = slope[r0 : r1 + 1, c0 : c1 + 1][local]
        local_rough = roughness[r0 : r1 + 1, c0 : c1 + 1][local]
        local_step = step[r0 : r1 + 1, c0 : c1 + 1][local]
        local_clearance = clearance[r0 : r1 + 1, c0 : c1 + 1]
        jitter = _unit_interval(cluster_id)
        clusters.append(
            {
                "cluster_id": cluster_id,
                "cell_count": len(rows),
                "bounds_rc": [r0, r1, c0, c1],
                "mean_slope_deg": round(float(np.mean(local_slope)), 4),
                "max_slope_deg": round(float(np.max(local_slope)), 4),
                "mean_roughness_m": round(float(np.mean(local_rough)), 4),
                "max_step_proxy_m": round(float(np.max(local_step)), 4),
                "clearance_lower_bound_m": round(
                    float(np.min(local_clearance)), 4
                ),
                "interior_lift_m": round(0.025 + jitter * 0.015, 4),
                "boundary_underlap_m": round(0.045 + jitter * 0.025, 4),
                "smoothing_passes": 2,
                "smoothing_blend": 0.55,
                "smoothing_clamp_m": 0.85,
            }
        )

    scree_score = roughness.astype(np.float64) * 4.0 + np.where(
        np.isfinite(step), step, 0.0
    ).astype(np.float64) * 8.0
    rock_candidates: list[dict[str, object]] = []
    for row0 in range(
        COMPONENT["row_min"], COMPONENT["row_max"] + 1, SCREE_BLOCK_CELLS
    ):
        row1 = min(row0 + SCREE_BLOCK_CELLS, COMPONENT["row_max"] + 1)
        for col0 in range(
            COMPONENT["col_min"], COMPONENT["col_max"] + 1, SCREE_BLOCK_CELLS
        ):
            col1 = min(col0 + SCREE_BLOCK_CELLS, COMPONENT["col_max"] + 1)
            representative = _representative(
                scree, scree_score, row0, row1, col0, col1
            )
            if representative is None:
                continue
            row, col, occupancy = representative
            jitter = _unit_interval(f"scree:{row}:{col}")
            radius_m = 0.20 + jitter * 0.22
            required_clearance_m = radius_m + 0.25
            x_m, y_m = col * PIXEL_SIZE_M, row * PIXEL_SIZE_M
            if not (
                COMPONENT["x_min_m"] + required_clearance_m
                <= x_m
                <= COMPONENT["x_max_m"] - required_clearance_m
                and COMPONENT["y_min_m"] + required_clearance_m
                <= y_m
                <= COMPONENT["y_max_m"] - required_clearance_m
            ):
                continue
            if float(clearance[row, col]) < required_clearance_m:
                continue
            rock_candidates.append(
                {
                    "rock_id": "scree-" + hashlib.sha256(
                        f"component230:{row}:{col}".encode()
                    ).hexdigest()[:12],
                    "source_rc": [row, col],
                    "center_xy_m": [round(x_m, 4), round(y_m, 4)],
                    "radius_m": round(radius_m, 4),
                    "height_m": round(0.16 + jitter * 0.30, 4),
                    "yaw_deg": round(jitter * 360.0, 4),
                    "clearance_lower_bound_m": round(
                        float(clearance[row, col]), 4
                    ),
                    "block_occupancy_cells": occupancy,
                    "_priority": _unit_interval(f"scree-priority:{row}:{col}"),
                }
            )

    if len(rock_candidates) > MAX_SCREE_ROCKS:
        rock_candidates.sort(key=lambda row: (row["_priority"], row["source_rc"]))
        rock_candidates = rock_candidates[:MAX_SCREE_ROCKS]
    rock_candidates.sort(key=lambda row: row["source_rc"])
    for row in rock_candidates:
        row.pop("_priority", None)

    return {
        "hard_policy": {
            "pavement": True,
            "shoulder_envelope": True,
            "mapped_water_buffer_m": WATER_BUFFER_M,
            "bob": False,
            "buildings": False,
            "infrastructure": False,
            "other_unknown_lidar": False,
        },
        "component": COMPONENT,
        "skin_contract": {
            "source_grid_step_cells": SKIN_STEP_CELLS,
            "source_grid_step_m": SKIN_STEP_CELLS * PIXEL_SIZE_M,
            "minimum_source_cliff_samples": SKIN_MIN_SOURCE_CLIFF_SAMPLES,
            "minimum_cluster_cells": SKIN_MIN_CLUSTER_CELLS,
            "supported_bridge_passes": 2,
            "boundary_policy": "underlap-real-landscape",
            "interior_policy": "smoothed-real-landscape-traces",
            "uv_world_size_m": 3.0,
        },
        "counts": {
            "component_cliff_cells": int(cliff[view].sum()),
            "component_cliff_area_m2": float(cliff[view].sum()) * 0.25,
            "component_scree_cells": int(scree[view].sum()),
            "component_scree_area_m2": float(scree[view].sum()) * 0.25,
            "skin_cluster_count": len(clusters),
            "skin_cell_count": len(skin_cells),
            # Compatibility alias used by the current proof workflow.
            "plate_count": len(clusters),
            "scree_rock_count": len(rock_candidates),
            "hard_protected_cells_component": int(protected[view].sum()),
            "coarse_source_occupied_cells": int((coarse_occupancy > 0).sum()),
        },
        "plates": clusters,
        "skin_cells": skin_cells,
        "scree_rocks": rock_candidates,
    }


def prepare(
    normalized_path: Path,
    pcg_path: Path,
    context_path: Path,
    output: Path,
):
    if output.exists():
        raise FileExistsError("Preserve previous Component_230 visual plans")
    verify_normalized(normalized_path)
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    pcg = verified_manifest(pcg_path)
    context = verified_manifest(context_path)
    if not (
        _grid_tuple(normalized)
        == _grid_tuple(pcg)
        == _grid_tuple(context)
        == GRID
    ):
        raise ValueError("Phase 2B inputs do not share frozen native grid")

    elevation, profile = _read(normalized_path.parent, "elevation.tif")
    slope, _ = _read(normalized_path.parent, "slope.tif")
    roughness, _ = _read(normalized_path.parent, "roughness.tif")
    reasons, _ = _read(pcg_path.parent, "exclusion-reasons.tif")
    records = json.loads(
        (context_path.parent / "context-exclusions.json").read_text(encoding="utf-8")
    )["features"]
    water = mapped_water_mask(
        records,
        buffer_m=WATER_BUFFER_M,
        out_shape=elevation.shape,
        transform=profile["transform"],
    )
    plan = build_plan(elevation, slope, roughness, reasons, water)
    if plan["counts"]["component_cliff_cells"] != 2611:
        raise ValueError(
            "Narrow road+shoulder+water0.5 cliff checkpoint drifted: "
            + str(plan["counts"]["component_cliff_cells"])
        )
    if plan["counts"]["component_scree_cells"] != 1237:
        raise ValueError(
            "Narrow road+shoulder+water0.5 scree checkpoint drifted: "
            + str(plan["counts"]["component_scree_cells"])
        )
    if plan["counts"]["skin_cluster_count"] <= 0:
        raise ValueError("Component_230 visual plan produced no cliff skins")
    if plan["counts"]["skin_cluster_count"] > SKIN_MAX_CLUSTERS:
        raise ValueError("Component_230 visual plan is still too fragmented")

    report = {
        "schema_version": 2,
        "status": "COMPONENT230_CLIFF_VISUAL_PLAN",
        "geometry_mutation": False,
        "canonical_landscape_mutation": False,
        "selector_policy_mutation": False,
        "grid": normalized["grid"],
        "sources": {
            "normalized_manifest_sha256": digest(normalized_path),
            "pcg_manifest_sha256": digest(pcg_path),
            "context_manifest_sha256": digest(context_path),
        },
        **plan,
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
    output.mkdir(parents=True)
    path = output / "component230-cliff-visual-plan.json"
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized-manifest", required=True, type=Path)
    parser.add_argument("--pcg-manifest", required=True, type=Path)
    parser.add_argument("--context-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = prepare(
        args.normalized_manifest,
        args.pcg_manifest,
        args.context_manifest,
        args.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "fingerprint": result["fingerprint"],
                "counts": result["counts"],
            }
        )
    )
