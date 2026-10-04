"""Prepare native-grid diagnostic colors for frozen Landscape; no heightmap output."""

from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.enums import Resampling
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_normalized_context import verify
from normalize_sa_calobra_context import sha256

ROOT = Path(__file__).resolve().parents[2]
PALETTE = {0: [0, 0, 0], 1: [255, 166, 0], 2: [0, 230, 255], 3: [185, 185, 185]}


def uv_at_xy(x_cm, y_cm, width=4033, spacing_cm=50.0):
    return [(x_cm / spacing_cm + 0.5) / width, (y_cm / spacing_cm + 0.5) / width]


def diagnostic_classes(relief, buildings, nodata=-32767.0):
    if relief.shape != buildings.shape:
        raise ValueError("Mask dimensions differ")
    out = np.zeros(relief.shape, dtype=np.uint8)
    out[relief > 10] = 1
    out[buildings == 1] = 2
    out[(relief == nodata) | ~np.isfinite(relief) | (buildings == 255)] = 3
    if np.any(~np.isin(buildings, [0, 1, 255])):
        raise ValueError("Unknown building mask value")
    return out


def prepare(manifest_path, cache_root, output):
    if output.exists():
        raise FileExistsError(
            "Preserve existing review outputs; choose a new directory"
        )
    verified = verify(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    grid = manifest["grid"]
    if grid != {
        **grid,
        "width": 4033,
        "height": 4033,
        "crs": "EPSG:25831",
        "transform": [0.5, 0.0, 483000.0, 0.0, -0.5, 4409516.5],
    }:
        raise ValueError("Unadmitted frozen Landscape grid")

    def read(name):
        with rasterio.open(manifest_path.parent / name) as ds:
            return ds.read(1)

    elevation = read("elevation.tif")
    relief = read("roughness.tif")
    classes = diagnostic_classes(relief, read("catastro_mapped_footprint.tif"))
    catalog = json.loads(
        (ROOT / "tools/julka/data/catalog.json").read_text(encoding="utf-8")
    )
    rows = [
        a for a in catalog["assets"] if a.get("gis_metadata_profile") == "pnoa_ortho"
    ]
    if not rows:  # Original catalog stores the profile by provider filename.
        rows = [
            a for a in catalog["assets"] if Path(a["path"]).name.startswith("PNOA_MA_")
        ]
    if len(rows) != 4:
        raise ValueError("Expected four pinned orthophotos")
    sources = []
    try:
        for row in rows:
            relative = Path(row["path"])
            if relative.parts[0] != "sa-calobra-working-v1" or ".." in relative.parts:
                raise ValueError("Unsafe orthophoto cache path")
            path = cache_root.joinpath(*relative.parts[1:])
            if (
                path.stat().st_size != row["size_bytes"]
                or sha256(path) != row["sha256"]
            ):
                raise ValueError("Orthophoto identity mismatch: " + path.name)
            ds = rasterio.open(path)
            sources.append(ds)
            if ds.crs.to_string() != "EPSG:25831" or ds.count < 3:
                raise ValueError("Unadmitted orthophoto CRS/bands")
        ortho, transform = merge(
            sources,
            bounds=[483000, 4407500, 485016.5, 4409516.5],
            res=0.5,
            indexes=[1, 2, 3],
            masked=True,
            resampling=Resampling.bilinear,
        )
        if list(transform)[:6] != grid["transform"] or ortho.shape != (3, 4033, 4033):
            raise ValueError("Orthophoto/grid mismatch")
        unknown = np.ma.getmaskarray(ortho).any(axis=0)
        classes[unknown] = 3
        rgb = np.asarray(ortho.filled(100), dtype=np.uint8).transpose(1, 2, 0)
    finally:
        for ds in sources:
            ds.close()
    colors = np.asarray([PALETTE[i] for i in range(4)], dtype=np.uint8)[classes]
    overlay = rgb.copy()
    affected = classes != 0
    overlay[affected] = np.rint(rgb[affected] * 0.3 + colors[affected] * 0.7).astype(
        np.uint8
    )
    index = read("siose_2014_feature_index.tif")
    ids = sorted(int(v) for v in np.unique(index) if v not in (0, 65535))
    historical = np.full(rgb.shape, 185, dtype=np.uint8)
    for i in ids:
        historical[index == i] = [
            (i * 67) % 180 + 50,
            (i * 103) % 180 + 50,
            (i * 151) % 180 + 50,
        ]
    # These colors identify historical polygons only, not current biome classes.
    output.mkdir(parents=True)
    for name, pixels in [
        ("orthophoto.png", rgb),
        ("review-overlay.png", overlay),
        ("historical-context.png", historical),
    ]:
        Image.fromarray(pixels).save(output / name)
    with rasterio.open(
        output / "review-class.tif",
        "w",
        driver="GTiff",
        width=4033,
        height=4033,
        count=1,
        dtype="uint8",
        crs="EPSG:25831",
        transform=transform,
        nodata=255,
        compress="DEFLATE",
    ) as ds:
        ds.write(classes, 1)
    points = [
        (r, c)
        for r in (16, 1000, 2016, 3000, 4016)
        for c in (16, 1000, 2016, 3000, 4016)
    ]
    mr, mc = np.unravel_index(np.argmax(relief), relief.shape)
    points.append((int(mr), int(mc)))
    low, high = float(elevation.min()), float(elevation.max())
    report = {
        "schema_version": 1,
        "status": "diagnostic_candidate",
        "geometry_mutation": False,
        "normalized_fingerprint": verified["fingerprint"],
        "grid": grid,
        "source_manifest_sha256": sha256(manifest_path),
        "orthophoto_inputs": [
            {"path": a["path"], "sha256": a["sha256"], "size_bytes": a["size_bytes"]}
            for a in rows
        ],
        "world_mapping": {
            "origin_epsg_m": [483000.25, 4409516.25],
            "axis": "X=easting-origin; Y=origin-northing; Z unchanged",
            "uv": "(UE_XY_cm/50 + 0.5)/4033",
            "texture_span_cm": 201650.0,
            "texture_origin_world_cm": [-25.0, -25.0],
        },
        "expected_landscape": {
            "map": "/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline",
            "components": 1024,
            "scale_xy_cm": 50.0,
            "scale_z": (high - low) * 100 * 128 / 65535,
            "location_z_cm": (low + (high - low) * 32768 / 65535) * 100,
        },
        "legend": {
            "amber": "native 3x3 relief >10m; review only, NOT confirmed terrain error",
            "cyan": "mapped Catastro footprint candidate; NOT freshness/completeness proof",
            "gray": "unknown evidence / imagery gap",
            "unchanged_ortho": "source context, NOT an alignment or geometry PASS",
            "historical_colors": "SIOSE 2014 object identity, NOT current biome classes",
            "red": "reserved for measured disagreement; none fabricated from relief",
        },
        "counts": {str(i): int((classes == i).sum()) for i in range(4)},
        "registration_samples": [
            {
                "row": r,
                "column": c,
                "world_cm": [c * 50.0, r * 50.0],
                "native_elevation_m": float(elevation[r, c]),
                "uv": uv_at_xy(c * 50, r * 50),
            }
            for r, c in points
        ],
        "blocked_layers": manifest["blocked_layers"],
        "road_domains": "UNKNOWN until admitted frozen road/BOB masks are provided; not inferred from imagery",
        "outputs": [
            {"path": p.name, "size_bytes": p.stat().st_size, "sha256": sha256(p)}
            for p in sorted(output.iterdir())
        ],
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "attribution": [
            "Obra derivada de PNOA CC-BY 4.0 scne.es",
            "SIOSE © INSTITUTO GEOGRÁFICO NACIONAL DE ESPAÑA - SITIBSA - GOIB",
            "DG Catastro INSPIRE Buildings; transformed local review only",
        ],
        "human_visual_acceptance": "PENDING",
        "whole_2a": "INCOMPLETE",
    }
    (output / "review-manifest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized-manifest", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(args.normalized_manifest, args.cache_root, args.output)["counts"]
        )
    )
