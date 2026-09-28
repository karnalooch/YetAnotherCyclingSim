#!/usr/bin/env python3
"""Probe official Regione Veneto services for a raw 5 m DTM path at Passo Giau.

The probe is metadata-only. It verifies LiDAR coverage and inspects official
WFS/WCS/Geoportal/download endpoints before YACS hard-codes any raster URL.
"""

from __future__ import annotations

import html.parser
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WFS_ENDPOINT = "https://idt2-geoserver.regione.veneto.it/geoserver/wfs"
WCS_ENDPOINTS = (
    "https://idt2-geoserver.regione.veneto.it/geoserver/wcs",
    "https://idt2.regione.veneto.it/geoserver/wcs",
)
TYPE_NAME = "rv:c0101071_lidar5m"
LICENSE = "IODL 2.0"
METADATA_URL = (
    "https://geodati.gov.it/geoportale/visualizzazione-metadati/"
    "scheda-metadati?metadataid=r_veneto%3Ac0101071_Lidar5m"
)
GEOPORTAL_DOCUMENT_URL = (
    "https://idt2.regione.veneto.it/geoportal/rest/document"
    "?id=c0101071_Lidar5m"
)
DOWNLOAD_PAGE = "https://idt2.regione.veneto.it/idt/downloader/download"
PASSO_GIAU_WGS84 = (12.05321, 46.48284)
BBOX_WGS84 = (11.99, 46.42, 12.12, 46.55)
OUTPUT = (
    Path("Saved") / "RuntimeProof" / "CI" / "Stage3GR4_1"
    / "VenetoLidarProbe" / "veneto-lidar-service-probe.json"
)
USER_AGENT = (
    "YetAnotherCyclingSim-VenetoLidarProbe/2.0 "
    "(+https://github.com/karnalooch/YetAnotherCyclingSim)"
)
KEYWORDS = (
    "lidar", "dtm", "coverage", "download", "scarica", "wcs",
    "asc", "tif", "geotiff", "zip", "raster", "api"
)


class ScriptSrcParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "script":
            return
        src = dict(attrs).get("src")
        if src:
            self.sources.append(src)


def request_text(
    url: str,
    *,
    accept: str = "*/*",
    timeout: int = 60,
) -> tuple[int, str, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")
        return int(getattr(response, "status", 200)), str(response.url), payload


def query_url(base: str, params: dict[str, str]) -> str:
    return f"{base}?{urllib.parse.urlencode(params)}"


def snippets(text: str, limit: int = 60) -> list[str]:
    matches: list[str] = []
    lower = text.lower()
    for keyword in KEYWORDS:
        start_at = 0
        while True:
            index = lower.find(keyword, start_at)
            if index < 0:
                break
            start = max(0, index - 260)
            end = min(len(text), index + len(keyword) + 700)
            value = text[start:end].replace("\x00", "")
            if value not in matches:
                matches.append(value)
                if len(matches) >= limit:
                    return matches
            start_at = index + len(keyword)
    return matches


def safe_fetch(label: str, url: str, *, accept: str = "*/*") -> dict[str, Any]:
    try:
        status, final_url, body = request_text(url, accept=accept)
        return {
            "label": label,
            "ok": True,
            "status": status,
            "url": url,
            "final_url": final_url,
            "bytes": len(body.encode("utf-8", errors="replace")),
            "snippets": snippets(body),
            "preview": body[:4000],
        }
    except Exception as exc:
        return {
            "label": label,
            "ok": False,
            "url": url,
            "error": repr(exc),
        }


def probe_wfs() -> dict[str, Any]:
    bbox_token = ",".join(f"{value:.6f}" for value in BBOX_WGS84) + ",EPSG:4326"
    describe_url = query_url(
        WFS_ENDPOINT,
        {
            "service": "WFS",
            "version": "1.0.0",
            "request": "DescribeFeatureType",
            "typeName": TYPE_NAME,
        },
    )
    feature_url = query_url(
        WFS_ENDPOINT,
        {
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetFeature",
            "typeName": TYPE_NAME,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "BBOX": bbox_token,
            "maxFeatures": "100",
        },
    )

    status, final_url, payload = request_text(
        feature_url,
        accept="application/json,*/*",
    )
    parsed = json.loads(payload)
    raw_features = parsed.get("features", [])
    features = [
        {
            "id": feature.get("id"),
            "properties": feature.get("properties", {}),
            "geometry": feature.get("geometry"),
        }
        for feature in raw_features
        if isinstance(feature, dict)
    ]

    lon, lat = PASSO_GIAU_WGS84
    point_tiles: list[dict[str, Any]] = []
    for feature in features:
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        try:
            ring = coordinates[0][0]
            xs = [float(point[0]) for point in ring]
            ys = [float(point[1]) for point in ring]
        except (IndexError, TypeError, ValueError):
            continue
        if min(xs) <= lon <= max(xs) and min(ys) <= lat <= max(ys):
            point_tiles.append(feature)

    return {
        "describe": safe_fetch("WFS DescribeFeatureType", describe_url),
        "get_feature": {
            "status": status,
            "final_url": final_url,
            "feature_count": len(features),
            "passo_giau_point_tiles": point_tiles,
            "features": features,
        },
    }


def probe_wcs() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for endpoint in WCS_ENDPOINTS:
        for version in ("2.0.1", "1.0.0"):
            url = query_url(
                endpoint,
                {
                    "service": "WCS",
                    "version": version,
                    "request": "GetCapabilities",
                },
            )
            results.append(
                safe_fetch(
                    f"WCS GetCapabilities {version}",
                    url,
                    accept="application/xml,text/xml,*/*",
                )
            )
    return results


def probe_download_page() -> dict[str, Any]:
    status, final_url, page = request_text(
        DOWNLOAD_PAGE,
        accept="text/html,*/*",
    )
    parser = ScriptSrcParser()
    parser.feed(page)
    scripts = [
        urllib.parse.urljoin(final_url, src)
        for src in parser.sources
    ]

    script_results: list[dict[str, Any]] = []
    for script_url in scripts:
        result = safe_fetch("download-page script", script_url)
        if result.get("snippets"):
            script_results.append(result)

    return {
        "status": status,
        "final_url": final_url,
        "bytes": len(page.encode("utf-8", errors="replace")),
        "page_snippets": snippets(page),
        "script_count": len(scripts),
        "scripts": scripts,
        "interesting_scripts": script_results,
    }


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema_version": 2,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "Regione del Veneto",
        "dataset": "Quadro Unione DTM 5 metri da voli Lidar",
        "license": LICENSE,
        "metadata_url": METADATA_URL,
        "passo_giau_wgs84": {
            "lon": PASSO_GIAU_WGS84[0],
            "lat": PASSO_GIAU_WGS84[1],
        },
        "bbox_wgs84": {
            "west": BBOX_WGS84[0],
            "south": BBOX_WGS84[1],
            "east": BBOX_WGS84[2],
            "north": BBOX_WGS84[3],
        },
        "wfs": probe_wfs(),
        "wcs": probe_wcs(),
        "geoportal_document": safe_fetch(
            "Geoportal REST document",
            GEOPORTAL_DOCUMENT_URL,
            accept="application/json,application/xml,text/xml,*/*",
        ),
        "download_page": probe_download_page(),
    }

    OUTPUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    point_tiles = report["wfs"]["get_feature"]["passo_giau_point_tiles"]
    print(f"[probe] report={OUTPUT}")
    print(f"[probe] point_tile_count={len(point_tiles)}")
    for tile in point_tiles:
        print(
            "[probe] point_tile="
            + json.dumps(tile.get("properties", {}), ensure_ascii=False)
        )

    for item in report["wcs"]:
        print(
            "[probe] wcs="
            f"{item['label']} ok={item['ok']} status={item.get('status')} "
            f"snippets={len(item.get('snippets', []))}"
        )
        for snippet in item.get("snippets", [])[:8]:
            print("[probe] wcs_snippet=" + snippet[:900].replace("\n", " "))

    doc = report["geoportal_document"]
    print(
        "[probe] geoportal_document="
        f"ok={doc['ok']} status={doc.get('status')} "
        f"snippets={len(doc.get('snippets', []))}"
    )
    for snippet in doc.get("snippets", [])[:12]:
        print("[probe] doc_snippet=" + snippet[:1200].replace("\n", " "))

    page = report["download_page"]
    print(
        "[probe] download_page="
        f"status={page['status']} scripts={page['script_count']} "
        f"interesting={len(page['interesting_scripts'])}"
    )
    for snippet in page.get("page_snippets", [])[:8]:
        print("[probe] page_snippet=" + snippet[:1000].replace("\n", " "))
    for item in page["interesting_scripts"][:12]:
        print("[probe] script_url=" + str(item.get("final_url") or item.get("url")))
        for snippet in item.get("snippets", [])[:8]:
            print("[probe] script_snippet=" + snippet[:1200].replace("\n", " "))

    if not point_tiles:
        print("[probe] ERROR: no 5 m LiDAR tile contains Passo Giau")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
