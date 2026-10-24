"""Authenticate existing mask inputs for #365; never generates or places assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sa_calobra_pcg_masks import verified_manifest

GRID = {
    "crs": "EPSG:25831",
    "width": 4033,
    "height": 4033,
    "pixel_size_m": 0.5,
    "transform": [0.5, 0.0, 483000.0, 0.0, -0.5, 4409516.5],
}
MAPPING = {
    "origin_epsg_m": [483000.25, 4409516.25],
    "world_unit": "centimetres",
    "axis": "X east;Y south",
    "uv": "(UE_XY_cm/50+0.5)/4033",
    "footprint_world_bounds_cm": [-25, -25, 201625, 201625],
}
SOURCES = {
    "pcg": (
        "pcg-masks-v1-2026-10-04/pcg-mask-manifest.json",
        "READY_FOR_BOUNDED_MASK_CONSUMER_WITH_FALLBACKS",
    ),
    "transitions": (
        "mask-transitions-v1a-2026-10-04/transition-manifest.json",
        "TRANSITION_AND_TOPOLOGY_REVIEW_CANDIDATE",
    ),
}
REQUIRED_PRODUCTS = {
    "pcg": {
        "vegetation-selectors.tif": (3, "uint8", 255),
        "exclusion-reasons.tif": (1, "uint16", 65535),
        "exclusion-distance-lower-bound.tif": (1, "float32", -32767),
    },
    "transitions": {"vegetation-density-weight.tif": (3, "float32", -32767)},
}


def validate_products(name, manifest, directory):
    products = manifest["outputs"]
    paths = [product["path"] for product in products]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate authenticated product")
    for filename, (bands, dtype, nodata) in REQUIRED_PRODUCTS[name].items():
        if paths.count(filename) != 1:
            raise ValueError("Missing required authenticated product: " + filename)
        product = products[paths.index(filename)]
        for key, expected in (("bands", bands), ("dtype", dtype), ("nodata", nodata)):
            if key in product and product[key] != expected:
                raise ValueError("Required product metadata mismatch: " + filename)
        with rasterio.open(directory / filename) as raster:
            if (
                raster.count != bands
                or raster.dtypes != (dtype,) * bands
                or raster.nodata != nodata
                or raster.width != GRID["width"]
                or raster.height != GRID["height"]
                or raster.crs.to_string() != GRID["crs"]
                or list(raster.transform)[:6] != GRID["transform"]
            ):
                raise ValueError("Required raster contract mismatch: " + filename)


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_config(config):
    if set(config) != {
        "schema_version",
        "graph_version",
        "seed",
        "grid",
        "world_mapping",
        "sources",
    }:
        raise ValueError("Unexpected graph input configuration fields")
    if (
        type(config["schema_version"]) is not int
        or config["schema_version"] != 1
        or config["graph_version"] != "sa-calobra-world-graph-inputs-v1"
    ):
        raise ValueError("Unsupported graph input version")
    if type(config["seed"]) is not int or not 0 <= config["seed"] <= 2147483647:
        raise ValueError("Seed must be an integer in [0,2147483647]")
    if config["grid"] != GRID or config["world_mapping"] != MAPPING:
        raise ValueError("Unadmitted spatial grid or mapping")
    if set(config["sources"]) != set(SOURCES):
        raise ValueError("Expected both pinned mask sources")
    for name, (path, _) in SOURCES.items():
        source = config["sources"][name]
        if set(source) != {"path", "sha256", "fingerprint"} or source["path"] != path:
            raise ValueError("Unsupported source path")
        if any(
            not isinstance(source[key], str)
            or re.fullmatch("[0-9a-f]{64}", source[key]) is None
            for key in ("sha256", "fingerprint")
        ):
            raise ValueError("Malformed source hash")


def prepare(root: Path, config_path: Path, output: Path):
    if output.exists():
        raise FileExistsError("Preserve existing graph input receipt")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_config(config)
    manifests = {}
    files = []
    for name, (relative, status) in SOURCES.items():
        path = root / relative
        pin = config["sources"][name]
        if digest(path) != pin["sha256"]:
            raise ValueError("Pinned manifest hash mismatch: " + name)
        manifest = verified_manifest(path)
        if (
            manifest["fingerprint"] != pin["fingerprint"]
            or manifest["status"] != status
        ):
            raise ValueError("Pinned manifest fingerprint/status mismatch: " + name)
        if any(manifest["grid"].get(key) != value for key, value in GRID.items()):
            raise ValueError("Mask spatial grid mismatch")
        validate_products(name, manifest, path.parent)
        if name == "pcg" and manifest.get("world_mapping") != MAPPING:
            raise ValueError("Mask spatial mapping mismatch")
        if (
            name == "transitions"
            and manifest.get("hard_exclusions_modified") is not False
        ):
            raise ValueError("Transition changed hard exclusions")
        manifests[name] = manifest
        files.append(
            {
                "path": relative,
                "sha256": pin["sha256"],
                "size_bytes": path.stat().st_size,
            }
        )
        for product in manifest["outputs"]:
            files.append(
                {
                    key: value
                    for key, value in {
                        **product,
                        "path": str(Path(relative).parent / product["path"]).replace(
                            "\\", "/"
                        ),
                    }.items()
                    if key
                    in (
                        "path",
                        "sha256",
                        "size_bytes",
                        "logical_sha256",
                        "dtype",
                        "bands",
                        "nodata",
                    )
                }
            )
    transition_parent = {
        item["path"]: item["sha256"]
        for item in manifests["transitions"]["source_manifests"]
    }
    if transition_parent.get(SOURCES["pcg"][0]) != config["sources"]["pcg"]["sha256"]:
        raise ValueError("Transition parent differs from pinned PCG source")
    receipt = {
        "schema_version": 1,
        "issue": 365,
        "status": "AUTHENTICATED_WORLD_GRAPH_INPUTS_ONLY",
        "configuration": config,
        "config_identity_sha256": hashlib.sha256(canonical(config)).hexdigest(),
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "files": sorted(files, key=lambda item: item["path"]),
        "band_bindings": {
            "vegetation_selectors": {
                "path": "pcg-masks-v1-2026-10-04/vegetation-selectors.tif",
                "bands_1_based": {"low": 1, "medium": 2, "high": 3},
            },
            "density_weights": {
                "path": "mask-transitions-v1a-2026-10-04/vegetation-density-weight.tif",
                "bands_1_based": {"low": 1, "medium": 2, "high": 3},
                "authority": "relative source return share and authored fade only; not plant density",
            },
        },
        "consumer_contract": manifests["pcg"]["consumer_contract"],
        "exclusion_contract": {
            "path": "pcg-masks-v1-2026-10-04/exclusion-reasons.tif",
            "bits": {
                "1": "pavement",
                "2": "shoulder conservative 0.51m envelope",
                "4": "complete BOB affected domain",
                "8": "Catastro/LiDAR buildings",
                "16": "water decorative holdback",
                "32": "infrastructure decorative holdback",
                "64": "other LiDAR class",
                "128": "no LiDAR samples",
            },
            "distance_path": "pcg-masks-v1-2026-10-04/exclusion-distance-lower-bound.tif",
            "evaluate_reference": "scripts/assets/read_sa_calobra_pcg_masks.py:evaluate",
            "subpixel_rule": "Subtract point-to-cell-centre offset from distance lower bound before radius+clearance comparison",
        },
        "unknown_contract": "Reject selector255, outside AOI and unknown clearance; nearest reads only; transitions may reduce eligibility, never promote unknown or bypass exclusions",
        "limitations": manifests["pcg"]["unresolved_world_authority"],
        "geometry_mutation": False,
        "placement": False,
        "qualified_assets": [],
        "native_execution": "NOT_RUN",
        "performance_pass": False,
    }
    receipt["fingerprint"] = hashlib.sha256(canonical(receipt)).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    (output / "world-graph-inputs.json").write_bytes(canonical(receipt))
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "worldgen/sa_calobra/world_graph_inputs_v1.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.root, args.config, args.output)
    print(
        json.dumps({"status": result["status"], "fingerprint": result["fingerprint"]})
    )
