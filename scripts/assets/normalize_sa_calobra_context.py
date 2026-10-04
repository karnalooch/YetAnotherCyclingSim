"""Normalize pinned working-space terrain and historical vector context outside Git."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
import rasterio
import shapely
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.windows import Window, from_bounds
from shapely.geometry import Polygon, box, mapping
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECIPE = Path(__file__).with_name("sa_calobra_context_recipe_v1.json")
NODATA = -32767.0
GML = "{http://www.opengis.net/gml/3.2}"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, data):
    path.write_text(
        json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def verified(path, identity):
    if (
        not path.is_file()
        or path.stat().st_size != identity["size_bytes"]
        or sha256(path) != identity["sha256"]
    ):
        raise ValueError(
            f"Pinned source missing/stale: {identity.get('cache_relative_path', identity.get('file'))}"
        )


def valid_polygon(geometry, identity):
    if (
        geometry.is_empty
        or not geometry.is_valid
        or geometry.geom_type not in {"Polygon", "MultiPolygon"}
    ):
        raise ValueError(f"Invalid/unhandled source polygon: {identity}")
    if not all(np.isfinite(geometry.bounds)):
        raise ValueError(f"Non-finite source coordinates: {identity}")
    return geometry


def esri_polygon(rings):
    # Esri specifies even-odd fill; symmetric difference preserves holes/islands.
    geometry = Polygon()
    for ring in rings:
        if len(ring) < 4 or ring[0] != ring[-1] or any(len(p) != 2 for p in ring):
            raise ValueError("Unclosed/non-2D Esri ring")
        geometry = geometry.symmetric_difference(
            valid_polygon(Polygon(ring), "Esri ring")
        )
    return valid_polygon(geometry, "Esri polygon")


def complete_features(data, ids):
    if (
        data.get("error")
        or ids.get("error")
        or data.get("exceededTransferLimit")
        or ids.get("exceededTransferLimit")
    ):
        raise ValueError("Provider error/transfer limit")
    expected = ids.get("objectIds")
    field = ids.get("objectIdFieldName")
    if (
        not isinstance(expected, list)
        or not field
        or len(expected) != len(set(expected))
    ):
        raise ValueError("Missing/duplicate source ID inventory")
    features = data.get("features", [])
    actual = [f["attributes"][field] for f in features]
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise ValueError("Incomplete/duplicate source feature identities")
    if data.get("spatialReference", {}).get("wkid") != 25831:
        raise ValueError("Unexpected vector CRS")
    return sorted(features, key=lambda f: f["attributes"][field])


def terrain_layers(halo, spacing, nodata):
    z = halo.astype(np.float64)
    neighbors = [
        z[dy : dy + z.shape[0] - 2, dx : dx + z.shape[1] - 2]
        for dy in range(3)
        for dx in range(3)
    ]
    valid = np.logical_and.reduce([np.isfinite(n) & (n != nodata) for n in neighbors])
    dx = (neighbors[5] - neighbors[3]) / (2 * spacing)
    dn = (neighbors[1] - neighbors[7]) / (2 * spacing)
    magnitude = np.hypot(dx, dn)
    slope = np.degrees(np.arctan(magnitude))
    aspect = np.degrees(np.arctan2(-dx, -dn)) % 360
    roughness = np.maximum.reduce(neighbors) - np.minimum.reduce(neighbors)

    def output(values, mask):
        return np.where(mask, values, NODATA).astype("<f4")

    return {
        "elevation": output(
            z[1:-1, 1:-1], np.isfinite(z[1:-1, 1:-1]) & (z[1:-1, 1:-1] != nodata)
        ),
        "slope": output(slope, valid),
        "aspect": output(aspect, valid & (magnitude > 1e-12)),
        "roughness": output(roughness, valid),
    }


def gml_polygons(feature):
    crs = {n.get("srsName") for n in feature.iter() if n.get("srsName")}
    if not crs or crs != {"urn:ogc:def:crs:EPSG::25831"}:
        raise ValueError("Unexpected/missing Catastro CRS")
    polygons = []
    for node in (
        n for n in feature.iter() if n.tag in {GML + "Polygon", GML + "PolygonPatch"}
    ):

        def ring(boundary):
            r = boundary.find(".//" + GML + "LinearRing")
            if r is None:
                raise ValueError("Unsupported GML ring")
            pos = r.find(GML + "posList")
            if pos is None or pos.get("srsDimension", "2") != "2":
                raise ValueError("Unsupported GML coordinate dimension")
            values = list(map(float, pos.text.split()))
            if len(values) % 2:
                raise ValueError("Odd GML coordinate count")
            points = list(zip(values[::2], values[1::2]))
            if len(points) < 4 or points[0] != points[-1]:
                raise ValueError("Unclosed GML ring")
            return points

        exterior = node.find(GML + "exterior")
        if exterior is None:
            raise ValueError("GML polygon without exterior")
        polygons.append(
            valid_polygon(
                Polygon(
                    ring(exterior), [ring(b) for b in node.findall(GML + "interior")]
                ),
                feature.get(GML + "id"),
            )
        )
    if not polygons:
        raise ValueError("Catastro feature without supported polygons")
    return valid_polygon(unary_union(polygons), feature.get(GML + "id"))


def run(recipe_path, cache, dtm, output):
    if output.exists() and any(output.iterdir()):
        raise ValueError(
            "Output directory must be empty; retained derived bytes are not overwritten"
        )
    output.mkdir(parents=True, exist_ok=True)
    recipe = json.loads(recipe_path.read_text(encoding="utf-8-sig"))
    if recipe["aoi"]["crs"] != "EPSG:25831" or recipe["grid"]["pixel_size_m"] != 0.5:
        raise ValueError("Unadmitted grid/CRS recipe")
    inputs = recipe["inputs"]
    for identity in inputs:
        relative = Path(identity["cache_relative_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe source cache path")
        verified(cache / relative, identity)
    baseline_path = (
        ROOT
        / "worldgen/terrain/benchmarks/sa_calobra/sa_calobra_8x8km_mdt50cm_epsg25831.json"
    )
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    verified(dtm, baseline)
    bounds = recipe["aoi"]["bounds_m"]
    aoi = box(*bounds)

    def source(name):
        matches = [i for i in inputs if Path(i["cache_relative_path"]).name == name]
        if len(matches) != 1:
            raise ValueError(f"Ambiguous source identity: {name}")
        return cache / matches[0]["cache_relative_path"]

    municipality = complete_features(
        json.loads(source("features.json").read_bytes()),
        json.loads(source("ids.json").read_bytes()),
    )
    admitted = [
        esri_polygon(f["geometry"]["rings"])
        for f in municipality
        if f["attributes"]["ID"] == recipe["municipality"]
    ]
    if len(admitted) != 1 or not admitted[0].covers(aoi):
        raise ValueError(
            "Escorca package does not cover complete AOI under verified municipal geometry"
        )
    si = complete_features(
        json.loads(source("siose14-features.json").read_bytes()),
        json.loads(source("siose14-ids.json").read_bytes()),
    )
    siose = []
    for f in si:
        clipped = esri_polygon(f["geometry"]["rings"]).intersection(aoi)
        if not clipped.is_empty:
            valid_polygon(clipped, f["attributes"]["OBJECTID"])
            siose.append((f["attributes"], clipped))
    coverage = unary_union([g for _, g in siose])
    uncovered = aoi.difference(coverage).area
    # Overlapping evidence is preserved as conflict rather than painter-order authority.
    overlap = sum(g.area for _, g in siose) - coverage.area
    catastro = []
    counts = {}
    with zipfile.ZipFile(source("A.ES.SDGC.BU.07019.zip")) as archive:
        if archive.testzip():
            raise ValueError("Catastro CRC failure")
        for suffix, typename in (
            ("building", "Building"),
            ("buildingpart", "BuildingPart"),
            ("otherconstruction", "OtherConstruction"),
        ):
            members = [
                n for n in archive.namelist() if n.endswith("." + suffix + ".gml")
            ]
            if len(members) != 1:
                raise ValueError(f"Missing/ambiguous Catastro {typename}")
            tree = ET.fromstring(archive.read(members[0]))
            features = [n for n in tree.iter() if n.tag.rsplit("}", 1)[-1] == typename]
            counts[typename] = {"source": len(features), "aoi": 0}
            for f in features:
                clipped = gml_polygons(f).intersection(aoi)
                if not clipped.is_empty:
                    valid_polygon(clipped, f.get(GML + "id"))
                    counts[typename]["aoi"] += 1
                    catastro.append(
                        (
                            {"source_id": f.get(GML + "id"), "feature_type": typename},
                            clipped,
                        )
                    )
    shape = (recipe["grid"]["height"], recipe["grid"]["width"])
    transform = from_origin(bounds[0], bounds[3], 0.5, 0.5)
    if shape != (
        round((bounds[3] - bounds[1]) / 0.5),
        round((bounds[2] - bounds[0]) / 0.5),
    ):
        raise ValueError("Grid dimensions/bounds mismatch")
    with rasterio.open(dtm) as ds:
        if (
            ds.crs != rasterio.crs.CRS.from_epsg(25831)
            or ds.res != (0.5, 0.5)
            or ds.count != 1
        ):
            raise ValueError("Unexpected Base_DTM CRS/grid/band count")
        window = from_bounds(*bounds, transform=ds.transform)
        if any(
            abs(v - round(v)) > 1e-8
            for v in (window.col_off, window.row_off, window.width, window.height)
        ):
            raise ValueError("AOI does not align to native Base_DTM")
        if not box(*ds.bounds).covers(aoi.buffer(0.5, cap_style="square")):
            raise ValueError("Missing native derivative halo")
        halo = ds.read(
            1,
            window=Window(
                round(window.col_off) - 1,
                round(window.row_off) - 1,
                shape[1] + 2,
                shape[0] + 2,
            ),
        )
        arrays = terrain_layers(halo, 0.5, ds.nodata)
    # 0 means no mapped Catastro footprint at provider snapshot, not no real structure.
    buildings = (
        rasterize(
            [(mapping(g), 1) for _, g in catastro],
            out_shape=shape,
            transform=transform,
            fill=0,
            dtype="uint8",
            all_touched=True,
        )
        if catastro
        else np.zeros(shape, dtype="uint8")
    )
    index = np.zeros(shape, dtype="uint16")
    occupied = np.zeros(shape, dtype="uint8")
    for number, (_, g) in enumerate(siose, start=1):
        mask = rasterize(
            [(mapping(g), 1)],
            out_shape=shape,
            transform=transform,
            fill=0,
            dtype="uint8",
        )
        conflict = (mask > 0) & (occupied > 0)
        index[(mask > 0) & (occupied == 0)] = number
        index[conflict] = 65535
        occupied |= mask
    arrays.update(catastro_mapped_footprint=buildings, siose_2014_feature_index=index)
    outputs = []
    for name, values in arrays.items():
        nodata = (
            NODATA
            if values.dtype.kind == "f"
            else (255 if name.startswith("catastro") else 0)
        )
        path = output / (name + ".tif")
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=shape[0],
            width=shape[1],
            count=1,
            dtype=values.dtype.name,
            crs="EPSG:25831",
            transform=transform,
            nodata=nodata,
            compress="deflate",
            predictor=3 if values.dtype.kind == "f" else 2,
            tiled=True,
            blockxsize=256,
            blockysize=256,
            num_threads=1,
        ) as ds:
            ds.write(values, 1)
        outputs.append(
            {
                "layer_id": name,
                "path": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "logical_sha256": hashlib.sha256(values.tobytes(order="C")).hexdigest(),
                "dtype": values.dtype.name,
                "nodata": nodata,
                "valid_cells": int(np.count_nonzero(values != nodata)),
                "owner": "World Data Stack spatial evidence",
                "consumers": [
                    "GIS QA",
                    "future presentation consumer adapter; not integrated",
                ],
            }
        )
    for name, geometries in (
        ("siose_2014_aoi", siose),
        ("catastro_aoi", catastro),
        (
            "municipal_coverage_aoi",
            [(municipality[0]["attributes"], admitted[0].intersection(aoi))],
        ),
    ):
        path = output / (name + ".json")
        write_json(
            path,
            {
                "type": "FeatureCollection",
                "coordinate_contract": "EPSG:25831 metric geometry; not RFC7946",
                "features": [
                    {"type": "Feature", "properties": p, "geometry": mapping(g)}
                    for p, g in geometries
                ],
            },
        )
        outputs.append(
            {
                "layer_id": name,
                "path": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "logical_sha256": sha256(path),
                "owner": "historical/provider context evidence",
            }
        )
    inputs = [
        *inputs,
        {
            "source_id": "accepted_base_dtm",
            "file": baseline["file"],
            "size_bytes": baseline["size_bytes"],
            "sha256": baseline["sha256"],
        },
    ]
    report = {
        "schema_version": 1,
        "status": "normalized_candidate",
        "issue": 335,
        "derivation_version": recipe["derivation_version"],
        "recipe_sha256": sha256(recipe_path),
        "producer_lf_sha256": hashlib.sha256(
            Path(__file__)
            .read_text(encoding="utf-8-sig")
            .replace("\r\n", "\n")
            .encode()
        ).hexdigest(),
        "versions": {
            "numpy": np.__version__,
            "rasterio": rasterio.__version__,
            "gdal": rasterio.__gdal_version__,
            "shapely": shapely.__version__,
        },
        "aoi": recipe["aoi"],
        "grid": {**recipe["grid"], "transform": list(transform)[:6]},
        "inputs": inputs,
        "outputs": outputs,
        "coverage": {
            "municipality": "07019 Escorca",
            "uncovered_municipal_area_m2": 0.0,
            "siose_uncovered_area_m2": uncovered,
            "siose_overlap_area_m2": overlap,
            "catastro_counts": counts,
        },
        "semantics": {
            "terrain": "native accepted Base_DTM; inherited vertical reference, not independently remeasured",
            "slope": "degrees; centered finite difference at 0.5 m; all 3x3 neighbors valid",
            "aspect": "degrees clockwise from north, downslope; flat/invalid is NoData",
            "roughness": "3x3 max-minus-min metres; no terrain smoothing",
            "catastro_mapped_footprint": "0 no mapped provider footprint, 1 conservative all-touched candidate, 255 unknown; mapped coverage is not current real-world completeness",
            "siose_2014_feature_index": "0 unknown, 1..N sorted OBJECTID context index, 65535 overlapping evidence conflict; attributes in siose_2014_aoi.json; no current biome classification",
        },
        "blocked_layers": recipe["blocked_layers"],
        "runtime_integration": False,
        "acceptance": "GIS candidate; visual review and remaining layers required before 2A completion",
    }
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            report,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()
    write_json(output / "manifest.json", report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--recipe", type=Path, default=DEFAULT_RECIPE)
    p.add_argument("--cache-root", type=Path, required=True)
    p.add_argument("--base-dtm", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    try:
        report = run(
            a.recipe, a.cache_root.resolve(), a.base_dtm.resolve(), a.output.resolve()
        )
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "fingerprint": report["fingerprint"],
                    "coverage": report["coverage"],
                }
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - retain exact failure, never promote partial output
        a.output.mkdir(parents=True, exist_ok=True)
        write_json(
            a.output / "failure_receipt.json",
            {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)},
        )
        print(type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
