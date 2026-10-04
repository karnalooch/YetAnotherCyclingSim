"""Decode retained BTN MVT water/infrastructure context with explicit uncertainty."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import rasterize
from shapely.geometry import (
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Polygon,
    box,
    mapping,
)
from shapely.ops import transform as transform_geometry

sys.path.insert(0, str(Path(__file__).resolve().parent))
from world_data_service_evidence import protobuf_fields
from verify_normalized_context import verify
from verify_sa_calobra_lidar_masks import digest
from acquire_sa_calobra_context_alternatives import validate_query

LAYERS = {
    "btn0302l_rio": ("water", 2),
    "btn0328s_alm_agu": ("water", 3),
    "btn0334p_surgen": ("water", 1),
    "btn0308l_tub_serv": ("infrastructure", 2),
    "btn0543l_tunel_l": ("infrastructure", 2),
    "btn0546l_pas_ele": ("infrastructure", 2),
}


def packed_varints(data):
    values, current, shift = [], 0, 0
    for byte in data:
        current |= (byte & 127) << shift
        if byte < 128:
            if current > 0xFFFFFFFF:
                raise ValueError("MVT geometry integer exceeds uint32")
            values.append(current)
            current, shift = 0, 0
        else:
            shift += 7
            if shift > 28:
                raise ValueError("Oversized MVT geometry varint")
    if shift:
        raise ValueError("Truncated MVT geometry varint")
    return values


def decode_geometry(commands, kind):
    parts, current = [], None
    x = y = pos = 0
    while pos < len(commands):
        command = commands[pos]
        pos += 1
        operation, count = command & 7, command >> 3
        if not count or operation not in (1, 2, 7):
            raise ValueError("Unsupported MVT geometry command")
        if operation == 7:
            if (
                kind != 3
                or count != 1
                or current is None
                or len(current) < 3
                or current[0] == current[-1]
            ):
                raise ValueError("Invalid MVT ClosePath")
            current.append(current[0])
            current = None
            continue
        if pos + 2 * count > len(commands):
            raise ValueError("Truncated MVT geometry parameters")
        if operation == 1:
            if kind != 1 and count != 1:
                raise ValueError("Invalid MVT MoveTo count")
            if kind == 3 and current is not None:
                raise ValueError("Unclosed MVT polygon ring")
        elif kind == 1 or current is None:
            raise ValueError("MVT LineTo without valid path")
        for _ in range(count):
            dx, dy = commands[pos : pos + 2]
            pos += 2
            dx, dy = (dx >> 1) ^ -(dx & 1), (dy >> 1) ^ -(dy & 1)
            if operation == 2 and dx == dy == 0:
                raise ValueError("Zero MVT line segment")
            x, y = x + dx, y + dy
            if operation == 1:
                current = []
                parts.append(current)
            current.append((x, y))
    if not parts:
        raise ValueError("Empty MVT geometry")
    if kind == 1:
        geometry = MultiPoint([p[0] for p in parts])
    elif kind == 2:
        if any(len(p) < 2 for p in parts):
            raise ValueError("Incomplete MVT line")
        geometry = MultiLineString(parts)
    elif kind == 3:
        if current is not None:
            raise ValueError("Unclosed MVT polygon")
        polygons, exterior, holes = [], None, []
        for ring in parts:
            area2 = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))
            if area2 > 0:
                if exterior is not None:
                    polygons.append(Polygon(exterior, holes))
                exterior, holes = ring, []
            elif area2 < 0 and exterior is not None:
                holes.append(ring)
            else:
                raise ValueError("MVT polygon winding/area mismatch")
        polygons.append(Polygon(exterior, holes))
        geometry = MultiPolygon(polygons)
    else:
        raise ValueError("Unsupported MVT geometry type")
    if not geometry.is_valid:
        raise ValueError("Invalid decoded MVT geometry; no automatic repair")
    return geometry


def prepare(catalog_path, cache, normalized_manifest, output, regional_receipt=None):
    if output.exists():
        raise FileExistsError("Preserve existing context masks")
    checked = verify(normalized_manifest)
    normalized = json.loads(normalized_manifest.read_text(encoding="utf-8"))
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    sources = sorted(
        [
            a
            for a in catalog["assets"]
            if "/btn_vector_tiles/" in a["path"] and a["path"].endswith(".pbf")
        ],
        key=lambda a: a["path"],
    )
    if len(sources) != 30:
        raise ValueError("Incomplete retained BTN tile inventory")
    with rasterio.open(normalized_manifest.parent / "elevation.tif") as ds:
        profile, shape, affine = ds.profile, ds.shape, ds.transform
    aoi = box(*rasterio.transform.array_bounds(*shape, affine))
    projector = Transformer.from_crs(3857, 25831, always_xy=True)
    records, counts = (
        [],
        {name: {"tile_instances": 0, "clipped_instances": 0} for name in LAYERS},
    )
    inputs = []
    for source in sources:
        relative = Path(source["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe BTN cache path")
        path = cache / relative
        if (
            digest(path) != source["sha256"]
            or path.stat().st_size != source["size_bytes"]
        ):
            raise ValueError("Stale BTN tile: " + source["path"])
        inputs.append(
            {k: source[k] for k in ["asset_id", "path", "sha256", "size_bytes"]}
        )
        z, tx, ty = int(relative.parts[-3]), int(relative.parts[-2]), int(relative.stem)
        span = 2 * math.pi * 6378137 / 2**z
        left, top = -math.pi * 6378137 + tx * span, math.pi * 6378137 - ty * span
        names = set()
        for field, wire, payload in protobuf_fields(path.read_bytes()):
            if (field, wire) != (3, 2):
                raise ValueError("Invalid MVT Tile framing")
            fields = list(protobuf_fields(payload))
            layer_names = [v.decode() for f, w, v in fields if (f, w) == (1, 2)]
            if len(layer_names) != 1 or layer_names[0] in names:
                raise ValueError("Duplicate/missing MVT layer")
            name = layer_names[0]
            names.add(name)
            if name not in LAYERS:
                continue
            if [v for f, w, v in fields if (f, w) == (15, 0)] != [2] or [
                v for f, w, v in fields if (f, w) == (5, 0)
            ] != [4096]:
                raise ValueError("Unsupported BTN MVT version/extent")
            group, expected_type = LAYERS[name]
            for number, feature in enumerate(
                v for f, w, v in fields if (f, w) == (2, 2)
            ):
                values = list(protobuf_fields(feature))
                if [v for f, w, v in values if (f, w) == (3, 0)] != [expected_type]:
                    raise ValueError("Unexpected BTN feature type: " + name)
                packed = [v for f, w, v in values if (f, w) == (4, 2)]
                if len(packed) != 1:
                    raise ValueError("Missing/ambiguous BTN geometry")
                geometry = decode_geometry(packed_varints(packed[0]), expected_type)
                mercator = transform_geometry(
                    lambda x, y, z=None: (
                        left + np.asarray(x) * span / 4096,
                        top - np.asarray(y) * span / 4096,
                    ),
                    geometry,
                )
                clipped = transform_geometry(
                    projector.transform, mercator
                ).intersection(aoi)
                counts[name]["tile_instances"] += 1
                if not clipped.is_empty:
                    if not clipped.is_valid:
                        raise ValueError("Invalid clipped BTN geometry")
                    counts[name]["clipped_instances"] += 1
                    records.append(
                        {
                            "source": source["asset_id"],
                            "layer": name,
                            "tile_feature_index": number,
                            "group": group,
                            "geometry": mapping(clipped),
                        }
                    )
    regional_inputs = []
    if regional_receipt is not None:
        regional = json.loads(regional_receipt.read_text(encoding="utf-8"))
        if regional.get("status") != "ACQUIRED_AOI_CONTEXT" or regional["aoi"] != {
            "crs": "EPSG:25831",
            "bounds_m": [483000, 4407500, 485016.5, 4409516.5],
        }:
            raise ValueError("Regional hydrology failed or AOI mismatch")
        for item in regional["files"]:
            relative = Path(item["path"])
            if relative.is_absolute() or len(relative.parts) != 1:
                raise ValueError("Unsafe regional source path")
            p = regional_receipt.parent / relative
            if p.stat().st_size != item["size_bytes"] or digest(p) != item["sha256"]:
                raise ValueError("Regional hydrology stale source: " + item["path"])
            regional_inputs.append(
                {k: item[k] for k in ["path", "sha256", "size_bytes"]}
            )
        raw = json.loads(
            (regional_receipt.parent / "features.json").read_text(encoding="utf-8")
        )
        ids = json.loads(
            (regional_receipt.parent / "ids.json").read_text(encoding="utf-8")
        )
        count = validate_query(ids, raw)
        if (
            count != regional["feature_count"]
            or raw.get("geometryType") != "esriGeometryPolyline"
        ):
            raise ValueError("Regional hydrology feature count/type mismatch")
        clipped_count = 0
        for feature in raw["features"]:
            paths = feature["geometry"]["paths"]
            if any(
                len(path) < 2
                or any(len(p) != 2 or not np.isfinite(p).all() for p in path)
                for path in paths
            ):
                raise ValueError("Incomplete/nonfinite regional watercourse")
            geometry = MultiLineString(paths).intersection(aoi)
            if not geometry.is_empty:
                clipped_count += 1
                records.append(
                    {
                        "source": "regional-provisional-hydrography",
                        "layer": "Xarxa Hidrografica Provisional",
                        "object_id": feature["attributes"][ids["objectIdFieldName"]],
                        "group": "water",
                        "geometry": mapping(geometry),
                    }
                )
        counts["regional_provisional"] = {
            "unique_source_features": count,
            "clipped_instances": clipped_count,
        }
    output.mkdir(parents=True)
    vector = output / "context-exclusions.json"
    vector.write_text(
        json.dumps(
            {
                "coordinate_contract": "EPSG:25831 metric; not RFC7946",
                "features": records,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    products = [
        {
            "path": vector.name,
            "size_bytes": vector.stat().st_size,
            "sha256": digest(vector),
        }
    ]
    for group in ["water", "infrastructure"]:
        geometry = [(r["geometry"], 1) for r in records if r["group"] == group]
        data = (
            rasterize(
                geometry,
                out_shape=shape,
                transform=affine,
                fill=0,
                dtype="uint8",
                all_touched=True,
            )
            if geometry
            else np.zeros(shape, dtype=np.uint8)
        )
        p = output / (group + "-context.tif")
        with rasterio.open(
            p,
            "w",
            **{
                **profile,
                "dtype": "uint8",
                "count": 1,
                "nodata": 255,
                "compress": "DEFLATE",
            },
        ) as ds:
            ds.write(data, 1)
        products.append(
            {
                "path": p.name,
                "size_bytes": p.stat().st_size,
                "sha256": digest(p),
                "logical_sha256": hashlib.sha256(data.tobytes()).hexdigest(),
                "observed_cells": int(data.sum()),
                "nodata": 255,
                "dtype": "uint8",
            }
        )
    report = {
        "schema_version": 1,
        "status": "BTN_CONTEXT_EXCLUSION_CANDIDATE",
        "geometry_mutation": False,
        "normalized_fingerprint": checked["fingerprint"],
        "grid": normalized["grid"],
        "inputs": inputs,
        "regional_inputs": regional_inputs,
        "regional_receipt_sha256": digest(regional_receipt)
        if regional_receipt is not None
        else None,
        "counts": counts,
        "outputs": products,
        "semantics": "1=source mapped context;0=no mapped feature, NOT completeness or absence proof; point/line widths and location accuracy unresolved; no invented buffer",
        "limits": "Cartographic zoom16 quantization/generalization; repeated tile instances may duplicate source features; no road authority or hydrologic/utility safety admission",
        "specification": "Mapbox MVT 2.x official 2.1 spec; IGN BTN slippy tile source; EPSG3857 projected with always_xy into native EPSG25831",
        "attribution": "BTN IGN/CNIG (CC BY 4.0 compatible terms); DG Recursos Hidrics / GOIB provisional hydrography (dataset-specific Creative Commons Attribution, version unspecified); snapshots retained",
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
    }
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    (output / "context-mask-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--normalized-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--regional-receipt", type=Path)
    args = parser.parse_args()
    result = prepare(
        args.catalog,
        args.cache,
        args.normalized_manifest,
        args.output,
        args.regional_receipt,
    )
    print(json.dumps({"status": result["status"], "counts": result["counts"]}))
