"""Package the complete frozen working AOI for future material authoring.

The existing visual-fill amplitudes are presentation inputs, not new ground
classification. This producer preserves their original observations, inference
and every placement holdback. It does not change terrain, roads or mesh detail.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import tempfile
import zlib
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from PIL import __version__ as PILLOW_VERSION
from rasterio.io import MemoryFile
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[2]
GRID = {
    "crs": "EPSG:25831",
    "height": 4033,
    "width": 4033,
    "pixel_size_m": 0.5,
    "transform": [0.5, 0.0, 483000.0, 0.0, -0.5, 4409516.5],
}
WORLD_MAPPING = {
    "origin_epsg_m": [483000.25, 4409516.25],
    "world_unit": "centimetres",
    "axis": "X east;Y south",
    "uv": "(UE_XY_cm/50+0.5)/4033",
    "footprint_world_bounds_cm": [-25, -25, 201625, 201625],
}
SOURCE_FINGERPRINT = "45fee07de3e0ebbb40f46cc3ef297e8b5f4b84e8c1d598539964527261d2ee50"
SOURCE_PRODUCTS = {
    "material_weights": {
        "path": "material-weights.png",
        "sha256": "af16fc7c43ec8a3a3b2e000fe716232a3229fe0ac6b4e9708baae5842ef99f6c",
        "size_bytes": 28497885,
        "mode": "RGBA",
    },
    "sample_availability": {
        "path": "sample-availability.png",
        "sha256": "9c9906268977a8f49ba20c194cecb101e8bb8c25c44b51ee30f66e7e88a7522a",
        "size_bytes": 861726,
        "mode": "L",
    },
    "inference_kind": {
        "path": "inference-kind.png",
        "sha256": "cc3bc3490878c5a96c20586cd28b0cd3cc812c5506ae97a7110c59e6ed3a3176",
        "size_bytes": 879841,
        "mode": "L",
    },
}
PLACEMENT_MANIFEST = {
    "path": "pcg-mask-manifest.json",
    "sha256": "465788e5d74cf3eccf59bdddc1480fa4d7dac50d6f22255ca69ac3b9f174b5df",
    "size_bytes": 5881,
    "fingerprint": "c9191f8dadf21d1820bebc80dd92e91641f4f4b74eb9d90342d7459611473864",
}
EXCLUSION_REASONS = {
    "path": "exclusion-reasons.tif",
    "sha256": "c74bde6ae8589304fe3d52f4e1e20801b0fe5647de6ffbc268c9b2ca65eaa941",
    "size_bytes": 2994730,
}
PILOT_MASK = {
    "path": "docs/experiments/sa-calobra-component230-detail-pilot-20261008/pilot/triangle-bands.json",
    "sha256": "6ec02a0e3dac9756923d29c8b603c0c1d79db411d06f3a20bb30956e11390953",
    "size_bytes": 321818,
    "mesh_sha256": "a9d34dbfb32a59b592dca561a7d7b0e53f7d02d90c095cff7c0812c249247965",
}
ROLES = (
    "low_vegetation_appearance",
    "forest_litter_appearance",
    "exposed_rock_appearance",
    "neutral_mineral_appearance",
    "dry_channel_appearance",
)
INFERENCE = {
    "0": "observed",
    "1": "neighbor_fill",
    "2": "neutral_fallback",
    "3": "protected_road_building",
}
EXCLUSION_BITS = {
    "1": "pavement",
    "2": "shoulder_envelope",
    "4": "bob_affected_domain",
    "8": "catastro_or_lidar_building",
    "16": "mapped_water_holdback",
    "32": "infrastructure_holdback",
    "64": "other_lidar_class",
    "128": "no_lidar_samples",
}
SECTOR_PIXELS = 256
ROLE_DENOMINATOR = 255 * 255


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
        "utf-8"
    )


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked_bytes(path, expected):
    """Read once, then use these verified bytes for decoding and export."""
    require(
        path.stat().st_size == expected["size_bytes"],
        f"Input size mismatch: {path.name}",
    )
    data = path.read_bytes()
    require(
        len(data) == expected["size_bytes"] and sha(data) == expected["sha256"],
        f"Input SHA256 mismatch: {path.name}",
    )
    return data


def checked_manifest(data, expected_fingerprint):
    value = json.loads(data)
    require(isinstance(value, dict), "Manifest must be an object")
    content = {k: v for k, v in value.items() if k != "fingerprint"}
    require(
        value.get("fingerprint") == expected_fingerprint
        and fingerprint(content) == expected_fingerprint,
        "Manifest fingerprint mismatch",
    )
    require(value.get("geometry_mutation") is False, "Source permits geometry mutation")
    require(
        all(value.get("grid", {}).get(k) == v for k, v in GRID.items()),
        "Source grid mismatch",
    )
    require(
        value.get("world_mapping") == WORLD_MAPPING, "Source world mapping mismatch"
    )
    return value


def output_row(path, **extra):
    data = path.read_bytes()
    return {"path": path.name, "sha256": sha(data), "size_bytes": len(data), **extra}


def validate_pixel_block(weights, available, inference, reasons):
    """Validate evidence/appearance relationships without modifying any input."""
    require(
        available.dtype == np.uint8 and available.ndim == 2,
        "Availability must be a byte plane",
    )
    require(
        weights.dtype == np.uint8 and weights.shape == (*available.shape, 4),
        "Weights must be registered RGBA8",
    )
    require(
        inference.dtype == np.uint8 and inference.shape == available.shape,
        "Inference must be a registered byte plane",
    )
    require(
        reasons.dtype == np.uint16 and reasons.shape == available.shape,
        "Reasons must be a registered uint16 plane",
    )
    require(not (reasons > 255).any(), "Unresolved NoData or undeclared exclusion bits")
    require(np.isin(available, [0, 255]).all(), "Invalid sample availability")
    require((inference <= 3).all(), "Unknown inference kind")
    require(
        (weights[..., :3].sum(axis=2, dtype=np.uint16) <= 255).all(),
        "RGB coverage exceeds one",
    )
    unknown = available == 0
    hard = (reasons & (1 | 8)) != 0
    require(
        np.array_equal(unknown, (reasons & 128) != 0),
        "Availability disagrees with source unknown bit",
    )
    require(
        np.array_equal(inference == 3, hard),
        "Protected inference disagrees with road/building mask",
    )
    require(
        np.array_equal(inference == 0, ~unknown & ~hard),
        "Observed inference disagrees with original samples",
    )
    require(
        not weights[hard].any(), "Appearance leaks into protected road/building pixels"
    )
    require(
        not weights[..., :3][inference == 2].any(),
        "No-donor fallback invents ground appearance",
    )


def role_weight_numerators(weights):
    """Exact five-role sums, with denominator 255² per pixel; no quantization."""
    rgb = weights[..., :3].astype(np.uint16)
    require((rgb.sum(axis=2, dtype=np.uint16) <= 255).all(), "RGB coverage exceeds one")
    alpha = weights[..., 3].astype(np.uint16)
    remainder = 255 - rgb.sum(axis=2, dtype=np.uint16)
    base = [rgb[..., index] for index in range(3)] + [remainder]
    values = [int((channel * (255 - alpha)).sum(dtype=np.uint64)) for channel in base]
    values.append(int(alpha.sum(dtype=np.uint64)) * 255)
    require(
        sum(values) == weights.shape[0] * weights.shape[1] * ROLE_DENOMINATOR,
        "Material roles do not partition coverage",
    )
    return dict(zip(ROLES, values, strict=True))


def block_coverage(weights, available, inference, reasons):
    return {
        "cells": int(available.size),
        "observed_samples": int((available == 255).sum()),
        "unknown_samples": int((available == 0).sum()),
        "inference_cells": {
            name: int((inference == int(code)).sum())
            for code, name in INFERENCE.items()
        },
        "exclusion_bit_cells": {
            name: int(((reasons & int(bit)) != 0).sum())
            for bit, name in EXCLUSION_BITS.items()
        },
        "any_exclusion_cells": int((reasons != 0).sum()),
        "no_exclusion_cells": int((reasons == 0).sum()),
        "role_weight_numerators": role_weight_numerators(weights),
    }


def add_coverage(total, partial):
    for key, value in partial.items():
        if isinstance(value, dict):
            target = total.setdefault(key, {})
            for name, count in value.items():
                target[name] = target.get(name, 0) + count
        else:
            total[key] = total.get(key, 0) + value


def _open_image(data, mode):
    image = Image.open(io.BytesIO(data))
    require(
        image.format == "PNG" and image.mode == mode,
        "Unexpected source image format/mode",
    )
    require(
        image.size == (GRID["width"], GRID["height"]),
        "Source image dimensions mismatch",
    )
    image.load()
    return image


def _pilot_data():
    data = checked_bytes(ROOT / PILOT_MASK["path"], PILOT_MASK)
    value = json.loads(data)
    require(
        value.get("mesh_sha256") == PILOT_MASK["mesh_sha256"],
        "Pilot is bound to a different mesh",
    )
    require(
        len(value.get("bands", "")) == 58216
        and {band: value["bands"].count(band) for band in "ABCDU"}
        == {"A": 324, "B": 211, "C": 0, "D": 0, "U": 57681},
        "Pilot scope changed",
    )
    return data


def prepare(source_inputs: Path, placement_inputs: Path, output: Path):
    """Build a self-contained package; fixed pins are not caller-overridable."""
    source_inputs, placement_inputs, output = map(
        Path, (source_inputs, placement_inputs, output)
    )
    if output.exists():
        raise FileExistsError(
            "Preserve existing preparation; choose a new output directory"
        )
    material_path = source_inputs / "material-input-manifest.json"
    require(material_path.stat().st_size <= 64 * 1024, "Oversized material manifest")
    source = checked_manifest(material_path.read_bytes(), SOURCE_FINGERPRINT)
    require(
        source.get("status") == "PRESENTATION_VISUAL_FILL_CANDIDATE"
        and source.get("current_cover_admitted") is False,
        "Unsupported appearance authority",
    )
    placement_bytes = checked_bytes(
        placement_inputs / PLACEMENT_MANIFEST["path"], PLACEMENT_MANIFEST
    )
    placement = checked_manifest(placement_bytes, PLACEMENT_MANIFEST["fingerprint"])
    require(
        placement.get("status") == "READY_FOR_BOUNDED_MASK_CONSUMER_WITH_FALLBACKS",
        "Unsupported placement authority",
    )
    source_rows = {row["path"]: row for row in source["outputs"]}
    require(
        len(source_rows) == len(source["outputs"]) == len(SOURCE_PRODUCTS),
        "Material source inventory mismatch",
    )
    blobs = {}
    for key, expected in SOURCE_PRODUCTS.items():
        row = source_rows.get(expected["path"], {})
        require(
            all(
                row.get(field) == expected[field]
                for field in ("path", "sha256", "size_bytes")
            ),
            "Material source pin mismatch",
        )
        blobs[key] = checked_bytes(source_inputs / expected["path"], expected)
    reason_rows = [
        row for row in placement["outputs"] if row["path"] == EXCLUSION_REASONS["path"]
    ]
    require(
        len(reason_rows) == 1
        and all(
            reason_rows[0].get(field) == EXCLUSION_REASONS[field]
            for field in ("path", "sha256", "size_bytes")
        ),
        "Placement reason pin mismatch",
    )
    reason_bytes = checked_bytes(
        placement_inputs / EXCLUSION_REASONS["path"], EXCLUSION_REASONS
    )
    pilot_bytes = _pilot_data()
    images = {
        key: _open_image(blobs[key], row["mode"])
        for key, row in SOURCE_PRODUCTS.items()
    }
    reason_image = np.empty((GRID["height"], GRID["width"]), dtype=np.uint8)
    sectors, total = [], {}
    logical_reasons = hashlib.sha256()
    # Only a 256-row strip is decoded into NumPy at once. No raw LiDAR stack,
    # distance transform, full float64 AOI or new geographic inference is needed.
    with (
        rasterio.Env(GDAL_CACHEMAX=32 * 1024 * 1024),
        MemoryFile(reason_bytes) as memory,
        memory.open() as dataset,
    ):
        require(
            dataset.count == 1
            and dataset.dtypes == ("uint16",)
            and dataset.nodata == 65535,
            "Unexpected exclusion raster representation",
        )
        require(
            dataset.width == GRID["width"]
            and dataset.height == GRID["height"]
            and dataset.crs.to_string() == GRID["crs"]
            and list(dataset.transform)[:6] == GRID["transform"],
            "Exclusion raster registration mismatch",
        )
        for y in range(0, GRID["height"], SECTOR_PIXELS):
            height = min(SECTOR_PIXELS, GRID["height"] - y)
            box = (0, y, GRID["width"], y + height)
            weights, available, inference = (
                np.asarray(images[key].crop(box)) for key in SOURCE_PRODUCTS
            )
            reasons = dataset.read(1, window=Window(0, y, GRID["width"], height))
            validate_pixel_block(weights, available, inference, reasons)
            logical_reasons.update(reasons.astype("<u2", copy=False).tobytes())
            reason_image[y : y + height] = reasons
            for x in range(0, GRID["width"], SECTOR_PIXELS):
                width = min(SECTOR_PIXELS, GRID["width"] - x)
                sl = np.s_[:, x : x + width]
                coverage = block_coverage(
                    weights[sl], available[sl], inference[sl], reasons[sl]
                )
                add_coverage(total, coverage)
                sectors.append(
                    {
                        "sector": [x // SECTOR_PIXELS, y // SECTOR_PIXELS],
                        "pixel_window": [x, y, width, height],
                        "world_footprint_cm": [
                            x * 50 - 25,
                            y * 50 - 25,
                            (x + width) * 50 - 25,
                            (y + height) * 50 - 25,
                        ],
                        **coverage,
                    }
                )
    for image in images.values():
        image.close()
    require(
        logical_reasons.hexdigest() == reason_rows[0].get("logical_sha256"),
        "Exclusion raster logical hash mismatch",
    )
    require(
        total["cells"] == GRID["width"] * GRID["height"]
        and sum(total["inference_cells"].values()) == total["cells"],
        "Incomplete full-grid accounting",
    )
    require(
        total["unknown_samples"]
        == source["counts"]["original_unknown"]
        == placement["counts"]["unknown_sample_cells"],
        "Source unknown count mismatch",
    )
    for name, key in (
        ("observed", "observed"),
        ("neighbor_fill", "neighbor_filled"),
        ("neutral_fallback", "neutral_fallback"),
        ("protected_road_building", "protected_road_building"),
    ):
        require(
            total["inference_cells"][name] == source["counts"][key],
            "Source inference count mismatch",
        )
    require(
        total["any_exclusion_cells"] == placement["counts"]["excluded_cells"]
        and total["exclusion_bit_cells"]["mapped_water_holdback"]
        == placement["counts"]["water_holdback_cells"],
        "Source exclusion count mismatch",
    )
    recipe = {
        "schema_version": 1,
        "grid": GRID,
        "world_mapping": WORLD_MAPPING,
        "material_roles": list(ROLES),
        "material_formula": "[R,G,B,max(0,1-R-G-B)]*(1-A), then dry-channel A; channels divided by255",
        "role_statistics_denominator_per_cell": ROLE_DENOMINATOR,
        "material_sampling": "linear-data bilinear clamp; appearance only",
        "categorical_sampling": "nearest clamp no mipmaps; reject outside AOI before sampling",
        "inference_codes": INFERENCE,
        "exclusion_bits": EXCLUSION_BITS,
        "placement_permission": "NOT_ADMITTED; unchanged selectors, radius and clearance contracts remain required",
        "sector_pixels": SECTOR_PIXELS,
        "surface_demand": "A/B source-face pilot only; U elsewhere; no distance or camera-radius relabeling",
        "distance_detail": "Camera-distance rendering policy belongs to the native material consumer; this package does not assign LOD or A-D bands",
        "encoding": {
            "exclusion_png": "L8 exact low byte of verified uint16 reasons",
            "pillow": PILLOW_VERSION,
            "zlib": zlib.ZLIB_VERSION,
            "compress_level": 9,
        },
    }
    coverage_report = {
        "schema_version": 1,
        "grid": GRID,
        "sector_pixels": SECTOR_PIXELS,
        "sectors_across": (GRID["width"] + SECTOR_PIXELS - 1) // SECTOR_PIXELS,
        "sectors_down": (GRID["height"] + SECTOR_PIXELS - 1) // SECTOR_PIXELS,
        "sector_identity": "fixed raster review sectors, not Unreal Landscape component IDs",
        "role_statistics_denominator_per_cell": ROLE_DENOMINATOR,
        "totals": total,
        "sectors": sectors,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".surface-prep-", dir=output.parent))
    try:
        sources = {}
        for key, row in SOURCE_PRODUCTS.items():
            path = stage / row["path"]
            path.write_bytes(blobs[key])
            sources[key] = output_row(path)
        for key, name, data in (
            (
                "material_manifest",
                "source-material-input-manifest.json",
                json_bytes(source),
            ),
            ("placement_manifest", "source-placement-manifest.json", placement_bytes),
            ("exclusion_reasons", "exclusion-reasons.tif", reason_bytes),
            ("component230_mask", "component230-triangle-bands.json", pilot_bytes),
        ):
            path = stage / name
            path.write_bytes(data)
            sources[key] = output_row(path)
        sources["material_manifest"]["fingerprint"] = SOURCE_FINGERPRINT
        sources["material_manifest"]["encoding"] = (
            "canonical pretty JSON with LF; original source fingerprint retained"
        )
        sources["placement_manifest"]["fingerprint"] = PLACEMENT_MANIFEST["fingerprint"]
        sources["component230_mask"]["mesh_sha256"] = PILOT_MASK["mesh_sha256"]
        Image.fromarray(reason_image).save(
            stage / "exclusion-reasons.png", compress_level=9
        )
        with Image.open(stage / "exclusion-reasons.png") as readback:
            require(
                readback.mode == "L"
                and np.array_equal(np.asarray(readback), reason_image),
                "Exclusion PNG readback changed values",
            )
        (stage / "sector-coverage.json").write_bytes(json_bytes(coverage_report))
        report = {
            "schema_version": 1,
            "status": "WHOLE_MAP_MATERIAL_PREPARATION_CANDIDATE",
            "geometry_mutation": False,
            "current_cover_admitted": False,
            "production_planting": "NOT_ADMITTED",
            "owner_review": "PENDING",
            "performance_admission": "NOT_MEASURED",
            "grid": source["grid"],
            "world_mapping": WORLD_MAPPING,
            "expected_landscape_component_count": 1024,
            "component_count_status": "Expected frozen Landscape inventory; actual native count must be verified by consumer",
            "sources": sources,
            "recipe": recipe,
            "recipe_sha256": fingerprint(recipe),
            "producer_file": "scripts/assets/prepare_sa_calobra_whole_map_surface_prep.py",
            "producer_sha256_lf": sha(
                Path(__file__).read_bytes().replace(b"\r\n", b"\n")
            ),
            "coverage": total,
            "coverage_sector_count": len(sectors),
            "demand_registration": {
                "whole_grid": "U_UNREVIEWED",
                "raster_demand_mask_generated": False,
                "pilot_mask": "component230-triangle-bands.json",
                "pilot_mesh_sha256": PILOT_MASK["mesh_sha256"],
                "pilot_triangle_row_counts": {
                    "A": 324,
                    "B": 211,
                    "C": 0,
                    "D": 0,
                    "U": 57681,
                },
                "pilot_owner_review": "PENDING",
                "scope": "Pilot rows address only the pinned Component230 source mesh; never map these indices or camera windows across the Landscape",
            },
            "outputs": [output_row(path) for path in sorted(stage.iterdir())],
        }
        report["fingerprint"] = fingerprint(report)
        (stage / "surface-prep-manifest.json").write_bytes(json_bytes(report))
        if output.exists():
            raise FileExistsError("Output appeared while preparing; refusing overwrite")
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-inputs", type=Path, required=True)
    parser.add_argument("--placement-inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source_inputs, args.placement_inputs, args.output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "fingerprint": result["fingerprint"],
                "coverage": result["coverage"],
            }
        )
    )
