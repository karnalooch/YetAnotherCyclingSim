"""Package bounded vegetation selectors and conservative presentation exclusions."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.features import rasterize
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_sa_calobra_lidar_masks import digest, verify as verify_lidar
from verify_normalized_context import verify as verify_normalized
from prepare_sa_calobra_road_masks import distance_lower_bound


def verified_manifest(path):
    report = json.loads(path.read_text(encoding="utf-8"))
    content = {k: v for k, v in report.items() if k != "fingerprint"}
    actual = hashlib.sha256(
        json.dumps(
            content, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    if actual != report["fingerprint"] or report["geometry_mutation"] is not False:
        raise ValueError("Stale/mutating mask manifest")
    for row in report["outputs"]:
        relative = Path(row["path"])
        if relative.is_absolute() or len(relative.parts) != 1:
            raise ValueError("Unsafe mask product path")
        p = path.parent / relative
        if p.stat().st_size != row["size_bytes"] or digest(p) != row["sha256"]:
            raise ValueError("Stale mask product: " + row["path"])
        if "logical_sha256" in row:
            with rasterio.open(p) as ds:
                values = ds.read()
                if (
                    ds.crs.to_string() != report["grid"]["crs"]
                    or list(ds.transform)[:6] != report["grid"]["transform"]
                    or ds.width != report["grid"]["width"]
                    or ds.height != report["grid"]["height"]
                ):
                    raise ValueError("Mask product grid mismatch")
            if hashlib.sha256(values.tobytes()).hexdigest() != row["logical_sha256"]:
                raise ValueError("Mask product logical hash mismatch")
    return report


def selectors(counts, quality, excluded):
    observed = counts.sum(axis=0, dtype=np.uint64) > 0
    result = (counts[1:4] > 0).astype(np.uint8)
    result[:, excluded] = 0
    result[2, (quality & 1) != 0] = 0
    result[:, ~observed] = 255
    return result


def prepare(normalized_path, lidar_path, road_path, context_path, output):
    if output.exists():
        raise FileExistsError("Preserve previous PCG package")
    verify_normalized(normalized_path)
    verify_lidar(lidar_path)
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    road, context = verified_manifest(road_path), verified_manifest(context_path)
    lidar = json.loads(lidar_path.read_text(encoding="utf-8"))
    if not (road["grid"] == context["grid"] == lidar["grid"] == normalized["grid"]):
        raise ValueError("PCG input grid disagreement")
    if (
        road["status"] != "FROZEN_PRESENTATION_ROAD_MASKS"
        or context["status"] != "BTN_CONTEXT_EXCLUSION_CANDIDATE"
    ):
        raise ValueError("Unsupported road/context authority")

    def read(root, name):
        with rasterio.open(root / name) as ds:
            return ds.read(1)

    with rasterio.open(lidar_path.parent / "class-counts.tif") as ds:
        counts, profile = ds.read(), ds.profile
    quality = read(lidar_path.parent, "height-review-flags.tif")
    pavement = read(road_path.parent, "road-footprint.tif") > 0
    shoulder = read(road_path.parent, "shoulder-exclusion-envelope.tif") > 0
    bob = read(road_path.parent, "bob-affected-domain.tif") > 0
    buildings = (read(normalized_path.parent, "catastro_mapped_footprint.tif") == 1) | (
        counts[4] > 0
    )
    vectors = json.loads(
        (context_path.parent / "context-exclusions.json").read_text(encoding="utf-8")
    )["features"]

    def envelope(group):
        # These are deliberate decorative holdbacks around mapped context, not
        # inferred channel widths, regulatory utility buffers or flood extents.
        polygons = [
            (
                r["geometry"]
                if shape(r["geometry"]).geom_type in ("Polygon", "MultiPolygon")
                else shape(r["geometry"]).buffer(5).__geo_interface__,
                1,
            )
            for r in vectors
            if r["group"] == group
        ]
        return (
            rasterize(
                polygons,
                out_shape=pavement.shape,
                transform=profile["transform"],
                dtype="uint8",
                all_touched=True,
            )
            > 0
            if polygons
            else np.zeros(pavement.shape, dtype=bool)
        )

    water, infrastructure = envelope("water"), envelope("infrastructure")
    unknown = counts.sum(axis=0, dtype=np.uint64) == 0
    other = counts[5] > 0
    reasons = np.zeros(pavement.shape, dtype=np.uint16)
    for bit, mask in [
        (1, pavement),
        (2, shoulder),
        (4, bob),
        (8, buildings),
        (16, water),
        (32, infrastructure),
        (64, other),
        (128, unknown),
    ]:
        reasons[mask] |= bit
    excluded = reasons != 0
    eligible = selectors(counts, quality, excluded)
    clearance = distance_lower_bound(excluded, 0.5)
    output.mkdir(parents=True)
    products = []
    for name, data, nodata, meaning in [
        (
            "vegetation-selectors.tif",
            eligible,
            255,
            "overlapping low/medium/high candidate selectors;1=source-supported outside holdbacks;0=not selected;255=unknown samples;high rejects invalid height",
        ),
        (
            "exclusion-reasons.tif",
            reasons[np.newaxis],
            65535,
            "bits1 pavement,2 shoulder envelope,4 BOB affected,8 Catastro/LiDAR building,16 water holdback,32 infrastructure holdback,64 other LiDAR class,128 no LiDAR samples",
        ),
        (
            "exclusion-distance-lower-bound.tif",
            clearance[np.newaxis],
            -32767,
            "planar distance lower bound to all excluded raster cells; consumer must require asset horizontal radius plus explicit clearance and stay inside AOI",
        ),
    ]:
        p = output / name
        with rasterio.open(
            p,
            "w",
            **{
                **profile,
                "dtype": str(data.dtype),
                "count": len(data),
                "nodata": nodata,
                "compress": "DEFLATE",
            },
        ) as ds:
            ds.write(data)
        products.append(
            {
                "path": name,
                "size_bytes": p.stat().st_size,
                "sha256": digest(p),
                "logical_sha256": hashlib.sha256(data.tobytes()).hexdigest(),
                "dtype": str(data.dtype),
                "bands": len(data),
                "nodata": nodata,
                "semantics": meaning,
            }
        )
    image = np.zeros((*pavement.shape, 4), dtype=np.uint8)
    image[:, :, :3] = np.moveaxis(np.where(eligible == 1, 255, 0), 0, 2)
    image[:, :, 3] = np.where(unknown, 0, 255)
    p = output / "vegetation-selectors.png"
    Image.fromarray(image).save(p)
    products.append(
        {
            "path": p.name,
            "size_bytes": p.stat().st_size,
            "sha256": digest(p),
            "semantics": "R low/G medium/B high; A observed; linear data, nearest, no mips; alpha must reject unknown; raster distance still required",
        }
    )
    report = {
        "schema_version": 1,
        "status": "READY_FOR_BOUNDED_MASK_CONSUMER_WITH_FALLBACKS",
        "geometry_mutation": False,
        "grid": normalized["grid"],
        "source_manifests": [
            {"path": p.parent.name + "/" + p.name, "sha256": digest(p)}
            for p in [normalized_path, lidar_path, road_path, context_path]
        ],
        "world_mapping": {
            "origin_epsg_m": [483000.25, 4409516.25],
            "world_unit": "centimetres",
            "axis": "X east;Y south",
            "uv": "(UE_XY_cm/50+0.5)/4033",
            "footprint_world_bounds_cm": [-25, -25, 201625, 201625],
        },
        "counts": {
            "selected_low": int((eligible[0] == 1).sum()),
            "selected_medium": int((eligible[1] == 1).sum()),
            "selected_high": int((eligible[2] == 1).sum()),
            "excluded_cells": int(excluded.sum()),
            "unknown_sample_cells": int(unknown.sum()),
            "water_holdback_cells": int(water.sum()),
        },
        "fallbacks": {
            "vegetation": "Owner-accepted broad source class character; low may be grass/low shrubs, medium/high not species; dated source presence, not current exhaustive land cover",
            "height": "Invalid heights stay unknown. High selector rejects those cells; low/medium use source class, not repaired height. Heights/fractions remain in original pinned LiDAR products",
            "shoulder": "Verified .51m maximum extent envelope; source geometry unchanged",
            "earthworks": "Exclude complete source patch rectangles, including guard/unchanged cells; exact cut/fill magnitudes and all inner/outer semantics remain unadmitted",
            "water_infrastructure": "5m decorative holdback around mapped points/lines; retain mapped surface polygons. Not measured channel width, flood/utility safety or exhaustive completeness; regional source epochs may be 2010",
            "rock_bare_soil": "Unknown subtype; no yellow-to-rock inference; selectors generate no rocks or bare-soil geography",
        },
        "consumer_contract": {
            "required_asset_parameters": [
                "horizontal_footprint_radius_m",
                "additional_clearance_m",
            ],
            "decision": "Reject unknown/outside AOI. Select requested vegetation band==1. Require exclusion distance lower bound >= radius+clearance. Entire radius must fit inside AOI. Never use interpolation to promote unknown or class boundary",
            "texture": "Data PNG: sRGB=false, nearest, no mipmaps. PNG alone cannot authorize placement; clearance raster and source manifest identity required",
            "density": "Original native/5m return fraction is sampling evidence, not plant count or crown cover; downstream selects explicit density/seed within admitted domains",
            "execution": "Mask readiness only; no PCGEx graph, asset placement, runtime import or gameplay/performance admission claimed",
        },
        "unresolved_world_authority": [
            "complete current-cover/canopy admission",
            "water/infrastructure completeness and widths",
            "exact shoulder/CUT/FILL/inner/outer semantics",
            "native production graph and performance admission",
        ],
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
    (output / "pcg-mask-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in [
        "normalized-manifest",
        "lidar-manifest",
        "road-manifest",
        "context-manifest",
        "output",
    ]:
        parser.add_argument("--" + name, required=True, type=Path)
    a = parser.parse_args()
    result = prepare(
        a.normalized_manifest,
        a.lidar_manifest,
        a.road_manifest,
        a.context_manifest,
        a.output,
    )
    print(json.dumps({"status": result["status"], "counts": result["counts"]}))
