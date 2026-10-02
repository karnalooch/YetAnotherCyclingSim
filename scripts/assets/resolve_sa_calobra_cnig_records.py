#!/usr/bin/env python3
"""Resolve exact CNIG records intersecting the active Sa Calobra working space.

Search/listing is performed through the public Centro de Descargas archivosSerie
endpoint used by the product page itself. This script does not attempt to bypass
download authorization or reCAPTCHA.
"""

from __future__ import annotations

import argparse
import json
import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from pyproj import Transformer

USER_AGENT = "YetAnotherCyclingSim/WorldDataStack-Issue335 (+https://github.com/karnalooch/YetAnotherCyclingSim)"
TIMEOUT = 90


class Inputs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "input":
            return
        data = {k: (v or "") for k, v in attrs}
        name = data.get("name", "")
        if name:
            self.values.setdefault(name, data.get("value", ""))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def compact_point(lon: float, lat: float) -> str:
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                }
            ],
        },
        separators=(",", ":"),
    )


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(unescape(text).split())


def parse_rows(html: str, extension_pattern: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, flags=re.IGNORECASE | re.DOTALL):
        filename_match = re.search(
            rf"([A-Za-z0-9_.-]+\.(?:{extension_pattern}))",
            row,
            flags=re.IGNORECASE,
        )
        if not filename_match:
            continue
        filename = filename_match.group(1)
        sec_match = re.search(r"detalleArchivo\?sec=(\d+)", row, flags=re.IGNORECASE)
        s3_match = re.search(r"id=[\"']linkDescDirS3_(\d+)[\"']", row, flags=re.IGNORECASE)
        normal_match = re.search(r"id=[\"']linkDescDir_(\d+)[\"']", row, flags=re.IGNORECASE)
        sec = sec_match.group(1) if sec_match else (s3_match or normal_match).group(1) if (s3_match or normal_match) else None

        row_text = strip_tags(row)
        mb_match = re.search(r"\bMB\b\s*([0-9]+(?:[.,][0-9]+)?)", row_text, flags=re.IGNORECASE)
        if not mb_match:
            # Current table order is name, format, date, scale, size; recover the
            # last decimal immediately before Acciones/Descarga when labels collapse.
            mb_match = re.search(
                r"([0-9]+(?:[.,][0-9]+)?)\s+Acciones\b",
                row_text,
                flags=re.IGNORECASE,
            )
        year_match = re.search(r"\b(20\d{2})\b", row_text)
        scale_match = re.search(r"\b(0[.,]50\s*m|5\s*ptos/m2)\b", row_text, flags=re.IGNORECASE)

        results.append(
            {
                "name": filename,
                "sec": int(sec) if sec else None,
                "detail_url": f"https://centrodedescargas.cnig.es/CentroDescargas/detalleArchivo?sec={sec}" if sec else None,
                "download_mode": "s3_direct_form" if s3_match else "recaptcha_authorized" if normal_match else "unknown",
                "year": int(year_match.group(1)) if year_match else None,
                "size_mb_display": float(mb_match.group(1).replace(",", ".")) if mb_match else None,
                "scale_or_density": scale_match.group(1) if scale_match else None,
                "row_text": row_text[:800],
            }
        )
    return results


def product_defaults(session: requests.Session, product_url: str) -> tuple[dict[str, str], dict[str, Any]]:
    response = session.get(product_url, timeout=TIMEOUT)
    response.raise_for_status()
    parser = Inputs()
    parser.feed(response.text)
    values = parser.values
    required = ["codAgr", "codSerie", "totalArchivos"]
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise RuntimeError(f"{product_url}: missing hidden defaults {missing}")
    return values, {
        "landing_url": response.url,
        "codAgr": values["codAgr"],
        "codSerie": values["codSerie"],
        "totalArchivos": values["totalArchivos"],
    }


def search_point(
    session: requests.Session,
    product_url: str,
    defaults: dict[str, str],
    lon: float,
    lat: float,
    extension_pattern: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    endpoint = urljoin(product_url, "archivosSerie")
    params = {
        "numPagina": "1",
        "codAgr": defaults.get("codAgr", ""),
        "codSerie": defaults.get("codSerie", ""),
        "coordenadas": compact_point(lon, lat),
        "series": defaults.get("series", ""),
        "codComAutonoma": "",
        "codProvincia": "",
        "codIne": "",
        "codTipoArchivo": "",
        "codIdiomaInf": "",
        "todaEspania": "",
        "todoMundo": "",
        "idProductor": "",
        "rutaNombre": "",
        "numHoja": "",
        "numHoja25": "",
        "totalArchivos": defaults.get("totalArchivos", ""),
        "codSubSerie": "",
        "contieneArc": "",
        "keySearch": "",
        "referCatastral": "",
        "orderBy": "",
    }
    response = session.get(
        endpoint,
        params=params,
        timeout=TIMEOUT,
        headers={
            "Referer": product_url,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "text/html, */*; q=0.01",
        },
    )
    response.raise_for_status()
    rows = parse_rows(response.text, extension_pattern)
    return rows, {
        "request_url": response.url,
        "status_code": response.status_code,
        "result_count_on_page": len(rows),
    }


def dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for record in records:
        key = record["name"].upper()
        if key not in merged:
            merged[key] = {**record, "query_labels": list(record.get("query_labels", []))}
        else:
            existing = merged[key]
            existing["query_labels"] = sorted(
                set(existing.get("query_labels", [])) | set(record.get("query_labels", []))
            )
            for field in ("sec", "detail_url", "download_mode", "year", "size_mb_display", "scale_or_density"):
                if existing.get(field) is None and record.get(field) is not None:
                    existing[field] = record[field]
    return sorted(merged.values(), key=lambda item: item["name"].upper())


def main() -> None:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 2:
        raise SystemExit("Resolver requires working-space manifest schema_version 2")

    sources = {source["id"]: source for source in manifest["sources"]}
    transformer = Transformer.from_crs("EPSG:25831", "EPSG:4326", always_xy=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})

    min_e, min_n, max_e, max_n = map(float, manifest["aoi"]["bounds_m"])

    lidar_queries: list[tuple[str, float, float]] = []
    for locator in manifest["selection"]["lidar_grid_locator_hints"]:
        e_km, n_km = (int(value) for value in locator.split("-"))
        e, n = e_km * 1000 + 500.0, n_km * 1000 + 500.0
        # Edge cells are queried even if their center is just outside the 2.0165 km
        # AOI; each listed 1 km cell genuinely intersects the AOI.
        lon, lat = transformer.transform(e, n)
        lidar_queries.append((locator, lon, lat))

    mds_metric_queries = [
        ("center", (min_e + max_e) / 2, (min_n + max_n) / 2),
        ("sw", min_e + 1, min_n + 1),
        ("se", max_e - 1, min_n + 1),
        ("ne", max_e - 1, max_n - 1),
        ("nw", min_e + 1, max_n - 1),
        ("south", (min_e + max_e) / 2, min_n + 1),
        ("east", max_e - 1, (min_n + max_n) / 2),
        ("north", (min_e + max_e) / 2, max_n - 1),
        ("west", min_e + 1, (min_n + max_n) / 2),
    ]
    mds_queries = [
        (label, *transformer.transform(e, n)) for label, e, n in mds_metric_queries
    ]

    jobs = [
        (
            "pnoa_lidar_cob3_npc03",
            sources["pnoa_lidar_cob3_npc03"]["product_url"],
            lidar_queries,
            r"LAZ",
            "NPC03",
        ),
        (
            "mds50cm_cob3_v1",
            sources["mds50cm_cob3_v1"]["product_url"],
            mds_queries,
            r"TIF|TIFF",
            "MDS50CM",
        ),
    ]

    output: dict[str, Any] = {
        "schema_version": 1,
        "issue": manifest["issue"],
        "aoi": manifest["aoi"],
        "sources": {},
    }

    for source_id, product_url, queries, extension_pattern, required_token in jobs:
        defaults, product = product_defaults(session, product_url)
        collected: list[dict[str, Any]] = []
        query_receipts = []
        for label, lon, lat in queries:
            rows, receipt = search_point(
                session, product_url, defaults, lon, lat, extension_pattern
            )
            filtered = [
                row for row in rows if required_token.lower() in row["name"].lower()
            ]
            for row in filtered:
                row["query_labels"] = [label]
            collected.extend(filtered)
            query_receipts.append(
                {
                    "label": label,
                    "lon_lat": [lon, lat],
                    "all_rows": len(rows),
                    "accepted_rows": len(filtered),
                    **receipt,
                }
            )
        records = dedupe(collected)
        output["sources"][source_id] = {
            "product": product,
            "query_receipts": query_receipts,
            "records": records,
            "record_count": len(records),
            "download_authorization_note": (
                "recaptcha_authorized records require normal CNIG browser authorization; "
                "this resolver does not bypass it. s3_direct_form records may use the "
                "provider's direct S3 form endpoint."
            ),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
