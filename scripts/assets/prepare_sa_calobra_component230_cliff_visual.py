"""Prepare deterministic Component_230 cliff/scree visual placement plan.

Diagnostic Phase 2B only. The hard exclusion policy is intentionally narrow:
pavement + conservative shoulder + mapped water buffered by 0.5 m. BOB,
buildings, infrastructure and other/unknown LiDAR exclusions remain deferred.
No canonical terrain or selector package is mutated.
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
from rasterio.features import rasterize
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sa_calobra_cliff_erosion import GRID, classify  # noqa: E402
from prepare_sa_calobra_cliff_erosion_handoff import (  # noqa: E402
    label_components_8,
    surface_gradients,
)
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
CLIFF_BLOCK_CELLS = 4
SCREE_BLOCK_CELLS = 4
MAX_SCREE_ROCKS = 160


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


def _rotate(x: float, y: float, degrees: float) -> tuple[float, float]:
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    return x * c - y * s, x * s + y * c


def _patch_ids(labels: np.ndarray) -> dict[int, str]:
    flat = labels.ravel()
    active = flat > 0
    if not bool(active.any()):
        return {}
    live_labels = flat[active].astype(np.int32, copy=False)
    positions = np.flatnonzero(active).astype(np.int64)
    maximum = np.iinfo(np.int64).max
    anchors = np.full(int(labels.max()) + 1, maximum, dtype=np.int64)
    np.minimum.at(anchors, live_labels, positions)
    result = {}
    width = labels.shape[1]
    for label in range(1, len(anchors)):
        if anchors[label] == maximum:
            continue
        row = int(anchors[label] // width)
        col = int(anchors[label] % width)
        payload = (
            "sa-calobra-cliff-patch-v1|EPSG:25831|4033x4033|0.5m|"
            f"r={row}|c={col}"
        )
        result[label] = "cliff-" + hashlib.sha256(payload.encode()).hexdigest()[:12]
    return result


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


def _inside_component(x_m: float, y_m: float, radius_m: float) -> bool:
    return (
        COMPONENT["x_min_m"] + radius_m <= x_m <= COMPONENT["x_max_m"] - radius_m
        and COMPONENT["y_min_m"] + radius_m <= y_m <= COMPONENT["y_max_m"] - radius_m
    )


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
    labels = label_components_8(cliff)
    patch_ids = _patch_ids(labels)
    gradient_x, gradient_y = surface_gradients(elevation)
    clearance = distance_lower_bound(protected, PIXEL_SIZE_M)

    view = (
        slice(COMPONENT["row_min"], COMPONENT["row_max"] + 1),
        slice(COMPONENT["col_min"], COMPONENT["col_max"] + 1),
    )
    score = slope.astype(np.float64) + roughness.astype(np.float64) * 4.0
    score += np.where(np.isfinite(step), step, 0.0).astype(np.float64) * 12.0

    plates: list[dict[str, object]] = []
    for row0 in range(COMPONENT["row_min"], COMPONENT["row_max"] + 1, CLIFF_BLOCK_CELLS):
        row1 = min(row0 + CLIFF_BLOCK_CELLS, COMPONENT["row_max"] + 1)
        for col0 in range(COMPONENT["col_min"], COMPONENT["col_max"] + 1, CLIFF_BLOCK_CELLS):
            col1 = min(col0 + CLIFF_BLOCK_CELLS, COMPONENT["col_max"] + 1)
            representative = _representative(cliff, score, row0, row1, col0, col1)
            if representative is None:
                continue
            row, col, occupancy = representative
            if occupancy < 2:
                continue

            gx = float(gradient_x[row, col])
            gy = float(gradient_y[row, col])
            horizontal = math.hypot(gx, gy)
            if not math.isfinite(horizontal) or horizontal <= 1e-6:
                continue

            downhill_x, downhill_y = -gx / horizontal, -gy / horizontal
            jitter = _unit_interval(f"plate:{row}:{col}")
            yaw_jitter = (jitter - 0.5) * 14.0
            downhill_x, downhill_y = _rotate(
                downhill_x, downhill_y, yaw_jitter
            )
            tangent_x, tangent_y = -downhill_y, downhill_x

            occupancy_fraction = occupancy / float(
                (row1 - row0) * (col1 - col0)
            )
            width_m = min(2.8, 1.25 + occupancy_fraction * 1.1 + jitter * 0.45)
            step_m = max(0.0, float(step[row, col]))
            height_m = min(
                4.5,
                max(
                    1.6,
                    1.35
                    + step_m * 1.15
                    + max(0.0, float(slope[row, col]) - 50.0) * 0.025
                    + jitter * 0.45,
                ),
            )
            thickness_m = 0.34 + jitter * 0.28
            footprint_radius_m = (
                math.hypot(width_m * 0.5, thickness_m * 0.5) + 0.25
            )
            x_m, y_m = col * PIXEL_SIZE_M, row * PIXEL_SIZE_M
            if not _inside_component(x_m, y_m, footprint_radius_m):
                continue
            if float(clearance[row, col]) < footprint_radius_m:
                continue

            label = int(labels[row, col])
            if label <= 0 or label not in patch_ids:
                raise ValueError("Cliff representative lost patch identity")
            plate_id = "plate-" + hashlib.sha256(
                f"component230:{row}:{col}".encode()
            ).hexdigest()[:12]
            plates.append(
                {
                    "plate_id": plate_id,
                    "patch_id": patch_ids[label],
                    "source_rc": [row, col],
                    "center_xy_m": [round(x_m, 4), round(y_m, 4)],
                    "downhill_xy": [
                        round(downhill_x, 7),
                        round(downhill_y, 7),
                    ],
                    "tangent_xy": [
                        round(tangent_x, 7),
                        round(tangent_y, 7),
                    ],
                    "width_m": round(width_m, 4),
                    "height_m": round(height_m, 4),
                    "thickness_m": round(thickness_m, 4),
                    "underlap_m": 0.45,
                    "top_inset_m": round(0.12 + jitter * 0.15, 4),
                    "outward_offset_m": round(0.16 + jitter * 0.12, 4),
                    "clearance_lower_bound_m": round(float(clearance[row, col]), 4),
                    "slope_deg": round(float(slope[row, col]), 4),
                    "roughness_m": round(float(roughness[row, col]), 4),
                    "step_proxy_m": round(step_m, 4),
                    "block_occupancy_cells": occupancy,
                    "yaw_jitter_deg": round(yaw_jitter, 4),
                }
            )

    rock_candidates: list[dict[str, object]] = []
    scree_score = roughness.astype(np.float64) * 4.0 + np.where(
        np.isfinite(step), step, 0.0
    ).astype(np.float64) * 8.0
    for row0 in range(COMPONENT["row_min"], COMPONENT["row_max"] + 1, SCREE_BLOCK_CELLS):
        row1 = min(row0 + SCREE_BLOCK_CELLS, COMPONENT["row_max"] + 1)
        for col0 in range(COMPONENT["col_min"], COMPONENT["col_max"] + 1, SCREE_BLOCK_CELLS):
            col1 = min(col0 + SCREE_BLOCK_CELLS, COMPONENT["col_max"] + 1)
            representative = _representative(scree, scree_score, row0, row1, col0, col1)
            if representative is None:
                continue
            row, col, occupancy = representative
            jitter = _unit_interval(f"scree:{row}:{col}")
            radius_m = 0.22 + jitter * 0.24
            required_clearance_m = radius_m + 0.20
            x_m, y_m = col * PIXEL_SIZE_M, row * PIXEL_SIZE_M
            if not _inside_component(x_m, y_m, required_clearance_m):
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
                    "height_m": round(0.18 + jitter * 0.34, 4),
                    "yaw_deg": round(jitter * 360.0, 4),
                    "clearance_lower_bound_m": round(float(clearance[row, col]), 4),
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

    component_labels = labels[view]
    intersecting_labels = np.unique(component_labels[component_labels > 0])
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
        "counts": {
            "component_cliff_cells": int(cliff[view].sum()),
            "component_cliff_area_m2": float(cliff[view].sum()) * 0.25,
            "component_scree_cells": int(scree[view].sum()),
            "component_scree_area_m2": float(scree[view].sum()) * 0.25,
            "intersecting_patch_count": int(len(intersecting_labels)),
            "plate_count": len(plates),
            "scree_rock_count": len(rock_candidates),
            "hard_protected_cells_component": int(protected[view].sum()),
        },
        "plates": plates,
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
    if plan["counts"]["plate_count"] <= 0:
        raise ValueError("Component_230 visual plan produced no cliff plates")

    report = {
        "schema_version": 1,
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
