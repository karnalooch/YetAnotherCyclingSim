"""Derive non-destructive cliff/scree presentation selectors from frozen terrain evidence.

This tool does not smooth, erode or otherwise mutate the accepted Landscape or
source DTM.  It produces replayable presentation candidates for later PCG/mesh
consumers from the existing native 0.5 m terrain derivatives and conservative
presentation exclusions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sa_calobra_pcg_masks import verified_manifest  # noqa: E402
from prepare_sa_calobra_road_masks import distance_lower_bound  # noqa: E402
from verify_normalized_context import verify as verify_normalized  # noqa: E402
from verify_sa_calobra_lidar_masks import digest  # noqa: E402

GRID = ("EPSG:25831", 4033, 4033, [0.5, 0.0, 483000.0, 0.0, -0.5, 4409516.5])
NODATA = -32767.0
PROTECTED_REASON_BITS = 1 | 2 | 4 | 8 | 16 | 32
DEFAULT_PARAMETERS = {
    "cliff_slope_min_deg": 50.0,
    "cliff_roughness_min_m": 0.75,
    "scree_slope_min_deg": 24.0,
    "scree_slope_max_deg": 42.0,
    "scree_roughness_min_m": 0.35,
    "scree_cliff_proximity_m": 20.0,
}


def _valid_float(values: np.ndarray) -> np.ndarray:
    return np.isfinite(values) & (values != NODATA)


def terrain_diagnostics(elevation: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return valid-interior mask, local curvature proxy and max cardinal step."""
    if elevation.ndim != 2:
        raise ValueError("Elevation must be a 2D grid")
    if min(elevation.shape) < 3:
        raise ValueError("Elevation grid must contain a 3x3 neighborhood")

    center = elevation[1:-1, 1:-1]
    north = elevation[:-2, 1:-1]
    south = elevation[2:, 1:-1]
    west = elevation[1:-1, :-2]
    east = elevation[1:-1, 2:]
    valid_inner = np.logical_and.reduce(
        [_valid_float(v) for v in (center, north, south, west, east)]
    )

    curvature = np.full(elevation.shape, NODATA, dtype=np.float32)
    step = np.full(elevation.shape, NODATA, dtype=np.float32)
    neighbor_mean = (north + south + west + east) * 0.25
    local_curvature = np.abs(center - neighbor_mean)
    local_step = np.maximum.reduce(
        [
            np.abs(center - north),
            np.abs(center - south),
            np.abs(center - west),
            np.abs(center - east),
        ]
    )
    curvature[1:-1, 1:-1] = np.where(valid_inner, local_curvature, NODATA)
    step[1:-1, 1:-1] = np.where(valid_inner, local_step, NODATA)
    valid = np.zeros(elevation.shape, dtype=bool)
    valid[1:-1, 1:-1] = valid_inner
    return valid, curvature, step


def _validated_parameters(parameters: dict[str, float] | None) -> dict[str, float]:
    values = dict(DEFAULT_PARAMETERS if parameters is None else parameters)
    if set(values) != set(DEFAULT_PARAMETERS):
        raise ValueError("Cliff selector parameter set differs from the pinned contract")
    if not all(np.isfinite(float(value)) for value in values.values()):
        raise ValueError("Cliff selector parameters must be finite")
    if not 0.0 < values["cliff_slope_min_deg"] < 90.0:
        raise ValueError("Cliff slope threshold outside 0..90 degrees")
    if values["cliff_roughness_min_m"] <= 0.0:
        raise ValueError("Cliff roughness threshold must be positive")
    if not (
        0.0
        < values["scree_slope_min_deg"]
        < values["scree_slope_max_deg"]
        < values["cliff_slope_min_deg"]
    ):
        raise ValueError("Scree slope band must be ordered below the cliff threshold")
    if values["scree_roughness_min_m"] <= 0.0:
        raise ValueError("Scree roughness threshold must be positive")
    if values["scree_cliff_proximity_m"] <= 0.0:
        raise ValueError("Scree proximity must be positive")
    return {name: float(value) for name, value in values.items()}


def classify(
    slope: np.ndarray,
    roughness: np.ndarray,
    elevation: np.ndarray,
    protected: np.ndarray,
    *,
    pixel_size_m: float = 0.5,
    parameters: dict[str, float] | None = None,
) -> dict[str, np.ndarray | dict[str, float]]:
    """Classify presentation candidates without changing source arrays."""
    if not (
        slope.ndim == roughness.ndim == elevation.ndim == protected.ndim == 2
        and slope.shape == roughness.shape == elevation.shape == protected.shape
    ):
        raise ValueError("Cliff selector inputs must share one 2D grid")
    if not np.isfinite(pixel_size_m) or pixel_size_m <= 0.0:
        raise ValueError("Pixel size must be positive and finite")
    if protected.dtype != np.bool_:
        protected = protected.astype(bool, copy=False)

    params = _validated_parameters(parameters)
    terrain_valid, curvature, step_proxy = terrain_diagnostics(elevation)
    valid = terrain_valid & _valid_float(slope) & _valid_float(roughness)
    if np.any((slope[valid] < 0.0) | (slope[valid] > 90.0)):
        raise ValueError("Slope values outside 0..90 degrees")
    if np.any(roughness[valid] < 0.0):
        raise ValueError("Roughness cannot be negative")

    cliff_raw = (
        valid
        & (slope >= params["cliff_slope_min_deg"])
        & (roughness >= params["cliff_roughness_min_m"])
    )
    cliff = cliff_raw & ~protected
    if cliff.any():
        distance_to_cliff = distance_lower_bound(cliff, pixel_size_m)
    else:
        distance_to_cliff = np.full(slope.shape, np.inf, dtype=np.float32)

    scree_raw = (
        valid
        & (slope >= params["scree_slope_min_deg"])
        & (slope <= params["scree_slope_max_deg"])
        & (roughness >= params["scree_roughness_min_m"])
        & (distance_to_cliff <= params["scree_cliff_proximity_m"])
        & ~cliff
    )
    scree = scree_raw & ~protected

    cliff_selector = np.where(valid, cliff.astype(np.uint8), 255).astype(np.uint8)
    scree_selector = np.where(valid, scree.astype(np.uint8), 255).astype(np.uint8)
    return {
        "valid": valid,
        "curvature_proxy_m": curvature,
        "step_proxy_m": step_proxy,
        "distance_to_cliff_m": distance_to_cliff,
        "cliff_selector": cliff_selector,
        "scree_selector": scree_selector,
        "parameters": params,
    }


def _grid_tuple(manifest: dict[str, object]) -> tuple[object, ...]:
    grid = manifest["grid"]
    return (
        grid["crs"],
        grid["width"],
        grid["height"],
        [float(value) for value in grid["transform"]],
    )


def _write_raster(path: Path, profile: dict[str, object], data: np.ndarray, nodata):
    bands = data.reshape((-1, *data.shape[-2:]))
    with rasterio.open(
        path,
        "w",
        **{
            **profile,
            "dtype": str(data.dtype),
            "count": bands.shape[0],
            "nodata": nodata,
            "compress": "DEFLATE",
        },
    ) as dataset:
        dataset.write(bands)


def prepare(normalized_path: Path, pcg_path: Path, output: Path):
    if output.exists():
        raise FileExistsError("Preserve previous cliff/erosion selector packages")

    verify_normalized(normalized_path)
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    pcg = verified_manifest(pcg_path)
    if _grid_tuple(normalized) != GRID or _grid_tuple(pcg) != GRID:
        raise ValueError("Cliff selector input grid is not the frozen native grid")
    if pcg["status"] != "READY_FOR_BOUNDED_MASK_CONSUMER_WITH_FALLBACKS":
        raise ValueError("Unsupported PCG exclusion authority")

    def read(root: Path, name: str) -> tuple[np.ndarray, dict[str, object]]:
        with rasterio.open(root / name) as dataset:
            return dataset.read(1), dataset.profile

    elevation, profile = read(normalized_path.parent, "elevation.tif")
    slope, _ = read(normalized_path.parent, "slope.tif")
    roughness, _ = read(normalized_path.parent, "roughness.tif")
    reasons, _ = read(pcg_path.parent, "exclusion-reasons.tif")
    protected = (reasons & PROTECTED_REASON_BITS) != 0
    result = classify(slope, roughness, elevation, protected)

    output.mkdir(parents=True)
    products = []
    raster_products = [
        (
            "cliff-candidate.tif",
            result["cliff_selector"],
            255,
            "1=steep rough presentation candidate;0=not selected/protected;255=invalid terrain neighborhood",
        ),
        (
            "scree-candidate.tif",
            result["scree_selector"],
            255,
            "1=moderate rough slope within bounded distance of admitted cliff candidate;0=not selected/protected;255=invalid terrain neighborhood",
        ),
        (
            "curvature-step-proxy.tif",
            np.stack([result["curvature_proxy_m"], result["step_proxy_m"]]),
            NODATA,
            "band1=abs(center-cardinal-neighbor-mean) metres;band2=max cardinal elevation step metres;diagnostic only",
        ),
        (
            "cliff-distance-lower-bound.tif",
            np.where(
                np.isfinite(result["distance_to_cliff_m"]),
                result["distance_to_cliff_m"],
                NODATA,
            ).astype(np.float32),
            NODATA,
            "conservative planar distance lower bound to cliff candidate cells in metres",
        ),
    ]
    for name, values, nodata, semantics in raster_products:
        path = output / name
        _write_raster(path, profile, np.asarray(values), nodata)
        products.append(
            {
                "path": name,
                "size_bytes": path.stat().st_size,
                "sha256": digest(path),
                "logical_sha256": hashlib.sha256(
                    np.asarray(values).tobytes(order="C")
                ).hexdigest(),
                "dtype": str(np.asarray(values).dtype),
                "bands": int(np.asarray(values).reshape((-1, *values.shape[-2:])).shape[0]),
                "nodata": nodata,
                "semantics": semantics,
            }
        )

    valid = np.asarray(result["valid"])
    cliff = np.asarray(result["cliff_selector"]) == 1
    scree = np.asarray(result["scree_selector"]) == 1
    image = np.zeros((*valid.shape, 4), dtype=np.uint8)
    image[..., 0] = cliff.astype(np.uint8) * 255
    image[..., 1] = scree.astype(np.uint8) * 255
    image[..., 2] = protected.astype(np.uint8) * 255
    image[..., 3] = valid.astype(np.uint8) * 255
    preview = output / "cliff-erosion-selectors.png"
    Image.fromarray(image).save(preview)
    products.append(
        {
            "path": preview.name,
            "size_bytes": preview.stat().st_size,
            "sha256": digest(preview),
            "semantics": "R cliff candidate;G scree candidate;B protected presentation holdback;A valid terrain neighborhood",
        }
    )

    report = {
        "schema_version": 1,
        "status": "CLIFF_EROSION_PRESENTATION_SELECTOR_CANDIDATE",
        "geometry_mutation": False,
        "canonical_landscape_mutation": False,
        "grid": normalized["grid"],
        "world_mapping": pcg["world_mapping"],
        "parameters": result["parameters"],
        "protected_reason_bits": {
            "mask": PROTECTED_REASON_BITS,
            "meanings": [
                "pavement",
                "shoulder envelope",
                "BOB affected domain",
                "building",
                "water holdback",
                "infrastructure holdback",
            ],
        },
        "sources": [
            {"path": str(normalized_path), "sha256": digest(normalized_path)},
            {"path": str(pcg_path), "sha256": digest(pcg_path)},
        ],
        "counts": {
            "valid_cells": int(valid.sum()),
            "protected_cells": int(protected.sum()),
            "cliff_candidate_cells": int(cliff.sum()),
            "scree_candidate_cells": int(scree.sum()),
        },
        "coverage": {
            "cell_area_m2": 0.25,
            "cliff_candidate_area_m2": float(cliff.sum()) * 0.25,
            "scree_candidate_area_m2": float(scree.sum()) * 0.25,
            "component_230": "PENDING_EXACT_UE_COMPONENT_BOUNDS",
        },
        "semantics": {
            "authority": "presentation selector only; not a new DEM, geology survey or terrain edit",
            "slope": "existing normalized centered-difference terrain slope",
            "roughness": "existing normalized 3x3 max-minus-min local relief",
            "curvature_proxy": "diagnostic local deviation from cardinal-neighbor mean; not geologic curvature",
            "step_proxy": "diagnostic maximum cardinal elevation step; flags abrupt heightfield response without claiming artificial terracing",
            "cliff": "bounded art candidate requiring steep slope plus local relief, then hard presentation exclusions",
            "scree": "bounded art candidate on moderate rough slopes near cliff candidates; not source-observed talus geology",
            "protected": "road/shoulder/BOB/building/water/infrastructure presentation holdbacks",
        },
        "consumer_contract": {
            "geometry": "Do not write selector effects into canonical Landscape/Base_DTM. Later mesh/PCG consumers are overlays only.",
            "roads": "Road, shoulder and BOB domains remain authoritative and excluded.",
            "unknown": "Invalid terrain neighborhoods remain 255 and cannot authorize placement.",
            "pcg": "A later PCG/PCGEx graph may consume only exact-grid selector==1 cells and must preserve source/proof identity.",
        },
        "outputs": products,
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
    }
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    (output / "cliff-erosion-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized-manifest", required=True, type=Path)
    parser.add_argument("--pcg-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = prepare(args.normalized_manifest, args.pcg_manifest, args.output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "fingerprint": result["fingerprint"],
                "counts": result["counts"],
            }
        )
    )
