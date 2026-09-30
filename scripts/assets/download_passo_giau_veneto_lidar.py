#!/usr/bin/env python3
"""Download official Regione Veneto LiDAR-derived 5 m DTM tiles for Passo Giau.

The tile index is discovered through the official Veneto WFS. Raster tiles are
then fetched through the same public endpoint used by the Geoportal downloader.

External data is presentation-only and must never become authoritative YACS
route or physics geometry.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WFS_ENDPOINT = "https://idt2-geoserver.regione.veneto.it/geoserver/wfs"
TYPE_NAME = "rv:c0101071_lidar5m"
DOWNLOAD_ENDPOINT = (
    "https://idt2.regione.veneto.it/idt/download/layerDownload/downloadDtmLidar5"
)
METADATA_URL = (
    "https://geodati.gov.it/geoportale/visualizzazione-metadati/"
    "scheda-metadati?metadataid=r_veneto%3Ac0101071_Lidar5m"
)
LICENSE = "IODL 2.0"
SOURCE_CRS = "EPSG:7795"  # RDN2008 / Zone 12 (E,N), raster x/y convention.
SOURCE_CRS_METADATA = "RDN2008-12NE / Fuso 12 (metadata EPSG:6876)"

# Envelope of the canonical 8 km x 8 km YACS Passo Giau AOI, transformed from
# EPSG:32632 bounds [730406.587, 5148246.775, 738406.587, 5156246.775].
AOI_BBOX_WGS84 = (11.9999, 46.4455, 12.1082, 46.5205)
PASSO_GIAU_WGS84 = (12.05321, 46.48284)
EXPECTED_CENTRAL_TILE = "12_2K_0294"
EXPECTED_CENTRAL_ID = "273"
USER_AGENT = (
    "YetAnotherCyclingSim-VenetoLidarDownloader/1.0 "
    "(+https://github.com/karnalooch/YetAnotherCyclingSim)"
)
MAX_TILES = 64
MAX_TILE_BYTES = 16 * 1024 * 1024


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def output_root() -> Path:
    return (
        repository_root()
        / "ExternalAssets"
        / "Terrain"
        / "PassoGiau"
        / "Veneto_Lidar5m"
    )


def fetch_bytes(url: str, *, accept: str = "*/*", timeout: int = 60) -> tuple[bytes, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(MAX_TILE_BYTES + 1)
        if len(payload) > MAX_TILE_BYTES:
            raise RuntimeError(f"response exceeded {MAX_TILE_BYTES} bytes: {url}")
        return payload, response.headers


def query_index() -> tuple[str, list[dict[str, Any]]]:
    bbox = ",".join(f"{value:.6f}" for value in AOI_BBOX_WGS84) + ",EPSG:4326"
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": TYPE_NAME,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "BBOX": bbox,
        "maxFeatures": str(MAX_TILES),
    }
    url = f"{WFS_ENDPOINT}?{urllib.parse.urlencode(params)}"
    payload, _headers = fetch_bytes(url, accept="application/json,*/*")
    parsed = json.loads(payload.decode("utf-8"))
    features = parsed.get("features")
    if not isinstance(features, list):
        raise RuntimeError("Veneto WFS response has no GeoJSON feature list")
    if not features:
        raise RuntimeError("Veneto WFS returned no LiDAR 5 m tiles for the YACS AOI")
    if len(features) >= MAX_TILES:
        raise RuntimeError(
            f"Veneto WFS hit safety cap ({MAX_TILES}); AOI/index query is too broad"
        )
    return url, [feature for feature in features if isinstance(feature, dict)]


def sanitize_tile(feature: dict[str, Any]) -> dict[str, str]:
    props = feature.get("properties")
    if not isinstance(props, dict):
        raise RuntimeError(f"WFS feature has invalid properties: {feature.get('id')}")
    id_pol = str(props.get("id_pol") or "").strip()
    name = str(props.get("nome") or "").strip()
    zone = str(props.get("fuso") or "").strip()
    kind = str(props.get("tipologia") or "").strip()
    if not re.fullmatch(r"\d+", id_pol):
        raise RuntimeError(f"invalid Veneto id_pol: {id_pol!r}")
    if not re.fullmatch(r"12_2K_\d{4}", name):
        raise RuntimeError(f"unexpected Veneto tile name: {name!r}")
    if kind.upper() != "DTM LIDAR 5M":
        raise RuntimeError(f"unexpected Veneto tile type for {name}: {kind!r}")
    return {"id_pol": id_pol, "name": name, "zone": zone, "kind": kind}


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def download_tile(tile: dict[str, str], tile_dir: Path) -> dict[str, Any]:
    params = urllib.parse.urlencode({"dataDtmLidarId": tile["id_pol"]})
    url = f"{DOWNLOAD_ENDPOINT}?{params}"
    payload, headers = fetch_bytes(url)
    if not payload.startswith(b"PK\x03\x04"):
        raise RuntimeError(f"{tile['name']} payload is not a ZIP archive")

    disposition = str(headers.get("Content-Disposition") or "")
    expected_zip = f'{tile["name"]}.asc.zip'
    if expected_zip not in disposition:
        raise RuntimeError(
            f"{tile['name']} unexpected Content-Disposition: {disposition!r}"
        )

    zip_path = tile_dir / expected_zip
    asc_path = tile_dir / f"{tile['name']}.asc"
    zip_path.write_bytes(payload)

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"{tile['name']} corrupt ZIP member: {bad}")
        names = archive.namelist()
        expected_member = f"{tile['name']}.asc"
        if names != [expected_member]:
            raise RuntimeError(
                f"{tile['name']} unexpected ZIP members: {names!r}"
            )
        asc_payload = archive.read(expected_member)

    header = asc_payload.splitlines()[:6]
    header_text = "\n".join(line.decode("ascii", errors="strict") for line in header)
    required_tokens = ("ncols", "nrows", "xllcenter", "yllcenter", "cellsize", "nodata_value")
    for token in required_tokens:
        if token not in header_text.lower():
            raise RuntimeError(f"{tile['name']} ASC header missing {token}")
    if not re.search(r"(?im)^ncols\s+400\s*$", header_text):
        raise RuntimeError(f"{tile['name']} expected ncols=400")
    if not re.search(r"(?im)^nrows\s+400\s*$", header_text):
        raise RuntimeError(f"{tile['name']} expected nrows=400")
    if not re.search(r"(?im)^cellsize\s+5(?:\.0+)?\s*$", header_text):
        raise RuntimeError(f"{tile['name']} expected cellsize=5 m")

    asc_path.write_bytes(asc_payload)
    return {
        **tile,
        "download_url": url,
        "zip_file": zip_path.name,
        "asc_file": asc_path.name,
        "zip_bytes": len(payload),
        "asc_bytes": len(asc_payload),
        "zip_sha256": sha256(payload),
        "asc_sha256": sha256(asc_payload),
        "content_disposition": disposition,
        "asc_header": header_text.splitlines(),
    }


def main() -> int:
    root = output_root()
    tile_dir = root / "tiles"
    tile_dir.mkdir(parents=True, exist_ok=True)

    try:
        index_url, features = query_index()
        tiles = [sanitize_tile(feature) for feature in features]
        unique = {(tile["id_pol"], tile["name"]): tile for tile in tiles}
        tiles = sorted(unique.values(), key=lambda item: int(item["id_pol"]))

        if not any(
            tile["id_pol"] == EXPECTED_CENTRAL_ID
            and tile["name"] == EXPECTED_CENTRAL_TILE
            for tile in tiles
        ):
            raise RuntimeError(
                "official WFS query does not contain the expected Passo Giau central tile"
            )

        records = []
        for index, tile in enumerate(tiles, start=1):
            print(
                f"[download {index}/{len(tiles)}] "
                f"{tile['name']} id={tile['id_pol']}"
            )
            records.append(download_tile(tile, tile_dir))

        report = {
            "schema_version": 1,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "provider": "Regione del Veneto",
            "dataset": "DTM 5 m derivato dai rilievi LiDAR",
            "index_layer": TYPE_NAME,
            "metadata_url": METADATA_URL,
            "license": LICENSE,
            "source_crs_for_raster_xy": SOURCE_CRS,
            "source_crs_metadata_label": SOURCE_CRS_METADATA,
            "aoi_bbox_wgs84": {
                "west": AOI_BBOX_WGS84[0],
                "south": AOI_BBOX_WGS84[1],
                "east": AOI_BBOX_WGS84[2],
                "north": AOI_BBOX_WGS84[3],
            },
            "passo_giau_wgs84": {
                "lon": PASSO_GIAU_WGS84[0],
                "lat": PASSO_GIAU_WGS84[1],
            },
            "wfs_query_url": index_url,
            "tile_count": len(records),
            "tiles": records,
            "yacs_policy": {
                "presentation_only": True,
                "authoritative_route_geometry": False,
                "authoritative_physics": False,
            },
        }
        report_path = root / "veneto-lidar-download-report.json"
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        print(
            f"[ok] Veneto LiDAR 5 m: {len(records)} tiles, "
            f"report={report_path}"
        )
        return 0
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
