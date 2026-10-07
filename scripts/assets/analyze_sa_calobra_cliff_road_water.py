"""Audit cliff/scree exclusion impact using roads and mapped hydrology only.

Diagnostic only. It compares exact pavement/shoulder authority with mapped
water geometry at explicit line/point buffers. It does not modify Phase 1
selector policy, canonical Landscape, BOB, buildings or infrastructure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from rasterio.features import rasterize
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sa_calobra_cliff_erosion import (  # noqa: E402
    GRID,
    classify,
)
from prepare_sa_calobra_pcg_masks import verified_manifest  # noqa: E402
from verify_normalized_context import verify as verify_normalized  # noqa: E402
from verify_sa_calobra_lidar_masks import digest  # noqa: E402

PIXEL_SIZE_M = 0.5
CURRENT_BROAD_BITS = 1 | 2 | 4 | 8 | 16 | 32
ROAD_BIT = 1
SHOULDER_BIT = 2
WATER_BIT = 16
WATER_BUFFERS_M = (0.0, 0.5, 1.0, 2.0, 3.0, 5.0)
COMPONENT_230 = (slice(882, 1009), slice(756, 883))


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


def water_mask(
    features: list[dict[str, object]],
    *,
    buffer_m: float,
    out_shape: tuple[int, int],
    transform,
) -> np.ndarray:
    if not np.isfinite(buffer_m) or buffer_m < 0:
        raise ValueError("Water buffer must be finite and non-negative")
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
        raise ValueError("No mapped water geometry available")
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


def _scenario_stats(result, protected: np.ndarray) -> dict[str, object]:
    cliff = np.asarray(result["cliff_selector"]) == 1
    scree = np.asarray(result["scree_selector"]) == 1
    view = COMPONENT_230
    return {
        "protected_cells": int(protected.sum()),
        "protected_area_m2": float(protected.sum()) * 0.25,
        "cliff_candidate_cells": int(cliff.sum()),
        "cliff_candidate_area_m2": float(cliff.sum()) * 0.25,
        "scree_candidate_cells": int(scree.sum()),
        "scree_candidate_area_m2": float(scree.sum()) * 0.25,
        "component_230": {
            "protected_cells": int(protected[view].sum()),
            "cliff_candidate_cells": int(cliff[view].sum()),
            "cliff_candidate_area_m2": float(cliff[view].sum()) * 0.25,
            "scree_candidate_cells": int(scree[view].sum()),
            "scree_candidate_area_m2": float(scree[view].sum()) * 0.25,
        },
    }


def _panel(
    raw_cliff: np.ndarray,
    admitted_cliff: np.ndarray,
    road: np.ndarray,
    water: np.ndarray,
    title: str,
    size: int = 640,
) -> Image.Image:
    rgb = np.zeros((*raw_cliff.shape, 3), dtype=np.uint8)
    rgb[raw_cliff] = [48, 48, 48]
    rgb[admitted_cliff] = [220, 55, 55]
    rgb[water] = [30, 120, 255]
    rgb[road] = [245, 245, 245]
    image = Image.fromarray(rgb).resize((size, size), Image.Resampling.NEAREST)
    canvas = Image.new("RGB", (size, size + 24))
    canvas.paste(image, (0, 24))
    ImageDraw.Draw(canvas).text((6, 6), title, fill=(255, 255, 255))
    return canvas


def _component_panel(
    raw_cliff: np.ndarray,
    admitted_cliff: np.ndarray,
    road: np.ndarray,
    water: np.ndarray,
    title: str,
    size: int = 400,
) -> Image.Image:
    view = COMPONENT_230
    return _panel(
        raw_cliff[view],
        admitted_cliff[view],
        road[view],
        water[view],
        title,
        size=size,
    )


def _board(panels: list[Image.Image], columns: int) -> Image.Image:
    rows = (len(panels) + columns - 1) // columns
    width = max(panel.width for panel in panels)
    height = max(panel.height for panel in panels)
    board = Image.new("RGB", (columns * width, rows * height))
    for index, panel in enumerate(panels):
        board.paste(panel, ((index % columns) * width, (index // columns) * height))
    return board


def prepare(
    normalized_path: Path,
    pcg_path: Path,
    context_path: Path,
    output: Path,
):
    if output.exists():
        raise FileExistsError("Preserve previous road/water audits")
    normalized_check = verify_normalized(normalized_path)
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    pcg = verified_manifest(pcg_path)
    context = verified_manifest(context_path)
    if not (
        _grid_tuple(normalized)
        == _grid_tuple(pcg)
        == _grid_tuple(context)
        == GRID
    ):
        raise ValueError("Audit inputs do not share frozen native grid")
    if pcg["status"] != "READY_FOR_BOUNDED_MASK_CONSUMER_WITH_FALLBACKS":
        raise ValueError("Unsupported PCG mask authority")
    if context["status"] != "BTN_CONTEXT_EXCLUSION_CANDIDATE":
        raise ValueError("Unsupported mapped context authority")

    elevation, profile = _read(normalized_path.parent, "elevation.tif")
    slope, _ = _read(normalized_path.parent, "slope.tif")
    roughness, _ = _read(normalized_path.parent, "roughness.tif")
    reasons, _ = _read(pcg_path.parent, "exclusion-reasons.tif")
    records = json.loads(
        (context_path.parent / "context-exclusions.json").read_text(encoding="utf-8")
    )["features"]

    road = (reasons & ROAD_BIT) != 0
    shoulder = (reasons & SHOULDER_BIT) != 0
    road_plus_shoulder = road | shoulder
    broad = (reasons & CURRENT_BROAD_BITS) != 0

    raw_result = classify(
        slope,
        roughness,
        elevation,
        np.zeros_like(road, dtype=bool),
        pixel_size_m=PIXEL_SIZE_M,
    )
    raw_cliff = np.asarray(raw_result["cliff_selector"]) == 1

    broad_result = classify(
        slope,
        roughness,
        elevation,
        broad,
        pixel_size_m=PIXEL_SIZE_M,
    )
    broad_stats = _scenario_stats(broad_result, broad)

    road_result = classify(
        slope,
        roughness,
        elevation,
        road,
        pixel_size_m=PIXEL_SIZE_M,
    )
    shoulder_result = classify(
        slope,
        roughness,
        elevation,
        road_plus_shoulder,
        pixel_size_m=PIXEL_SIZE_M,
    )

    scenarios: dict[str, object] = {
        "none": _scenario_stats(
            raw_result, np.zeros_like(road, dtype=bool)
        ),
        "pavement_only": _scenario_stats(road_result, road),
        "pavement_plus_shoulder": _scenario_stats(
            shoulder_result, road_plus_shoulder
        ),
        "current_broad_protected_union": broad_stats,
    }

    whole_panels = []
    component_panels = []
    water_counts = {}
    scenario_masks = {}
    for buffer_m in WATER_BUFFERS_M:
        water = water_mask(
            records,
            buffer_m=buffer_m,
            out_shape=elevation.shape,
            transform=profile["transform"],
        )
        protected = road_plus_shoulder | water
        result = classify(
            slope,
            roughness,
            elevation,
            protected,
            pixel_size_m=PIXEL_SIZE_M,
        )
        key = f"road_shoulder_water_{buffer_m:g}m"
        stats = _scenario_stats(result, protected)
        stats["water_cells"] = int(water.sum())
        stats["water_area_m2"] = float(water.sum()) * 0.25
        stats["recovered_vs_current_broad"] = {
            "protected_cells": int(broad.sum()) - int(protected.sum()),
            "cliff_candidate_cells": (
                stats["cliff_candidate_cells"]
                - broad_stats["cliff_candidate_cells"]
            ),
            "cliff_candidate_area_m2": (
                stats["cliff_candidate_area_m2"]
                - broad_stats["cliff_candidate_area_m2"]
            ),
            "scree_candidate_cells": (
                stats["scree_candidate_cells"]
                - broad_stats["scree_candidate_cells"]
            ),
            "scree_candidate_area_m2": (
                stats["scree_candidate_area_m2"]
                - broad_stats["scree_candidate_area_m2"]
            ),
        }
        scenarios[key] = stats
        water_counts[f"{buffer_m:g}m"] = int(water.sum())
        admitted_cliff = np.asarray(result["cliff_selector"]) == 1
        whole_panels.append(
            _panel(
                raw_cliff,
                admitted_cliff,
                road_plus_shoulder,
                water,
                f"water buffer {buffer_m:g} m",
            )
        )
        component_panels.append(
            _component_panel(
                raw_cliff,
                admitted_cliff,
                road_plus_shoulder,
                water,
                f"Component_230 / {buffer_m:g} m",
            )
        )
        scenario_masks[key] = {
            "protected_logical_sha256": hashlib.sha256(
                protected.tobytes(order="C")
            ).hexdigest(),
            "water_logical_sha256": hashlib.sha256(
                water.tobytes(order="C")
            ).hexdigest(),
        }

    output.mkdir(parents=True)
    whole_board = output / "road-water-audit-whole-area.png"
    _board(whole_panels, 3).save(whole_board)
    component_board = output / "road-water-audit-component230.png"
    _board(component_panels, 3).save(component_board)

    report = {
        "schema_version": 1,
        "status": "CLIFF_ROAD_WATER_EXCLUSION_DIAGNOSTIC",
        "geometry_mutation": False,
        "canonical_landscape_mutation": False,
        "selector_policy_mutation": False,
        "grid": normalized["grid"],
        "scope": {
            "active_for_analysis": [
                "pavement",
                "conservative shoulder envelope",
                "mapped water geometry",
            ],
            "explicitly_deferred": [
                "BOB affected rectangles",
                "buildings",
                "infrastructure",
                "other/unknown LiDAR classes",
            ],
        },
        "water": {
            "feature_records": sum(
                1 for record in records if record.get("group") == "water"
            ),
            "buffers_m": list(WATER_BUFFERS_M),
            "cell_counts": water_counts,
            "semantics": (
                "0m is mapped source geometry rasterized all_touched; positive "
                "buffers apply only to non-polygon water geometry. They are "
                "diagnostic art holdbacks, not measured channel widths."
            ),
        },
        "roads": {
            "pavement_cells": int(road.sum()),
            "pavement_area_m2": float(road.sum()) * 0.25,
            "shoulder_cells": int(shoulder.sum()),
            "shoulder_area_m2": float(shoulder.sum()) * 0.25,
            "pavement_plus_shoulder_cells": int(road_plus_shoulder.sum()),
            "pavement_plus_shoulder_area_m2": (
                float(road_plus_shoulder.sum()) * 0.25
            ),
        },
        "scenarios": scenarios,
        "scenario_logical_hashes": scenario_masks,
        "sources": {
            "normalized_manifest": {
                "path": str(normalized_path),
                "sha256": digest(normalized_path),
                "fingerprint": normalized_check["fingerprint"],
            },
            "pcg_manifest": {
                "path": str(pcg_path),
                "sha256": digest(pcg_path),
                "fingerprint": pcg["fingerprint"],
            },
            "context_manifest": {
                "path": str(context_path),
                "sha256": digest(context_path),
                "fingerprint": context["fingerprint"],
            },
        },
        "preview": {
            "whole_area": {
                "path": whole_board.name,
                "sha256": digest(whole_board),
                "legend": "dark gray=raw cliff;red=admitted cliff;white=road+shoulder;blue=water",
            },
            "component_230": {
                "path": component_board.name,
                "sha256": digest(component_board),
                "legend": "dark gray=raw cliff;red=admitted cliff;white=road+shoulder;blue=water",
            },
        },
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
    manifest = output / "road-water-cliff-audit.json"
    manifest.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "fingerprint": report["fingerprint"],
                "roads": report["roads"],
                "water": report["water"],
                "scenarios": report["scenarios"],
            },
            separators=(",", ":"),
        )
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized-manifest", required=True, type=Path)
    parser.add_argument("--pcg-manifest", required=True, type=Path)
    parser.add_argument("--context-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    prepare(
        args.normalized_manifest,
        args.pcg_manifest,
        args.context_manifest,
        args.output,
    )
