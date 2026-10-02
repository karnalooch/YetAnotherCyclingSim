#!/usr/bin/env python3
"""Resolve exact CNIG LiDAR/MDS records using the public product-page frontend.

The product site rejects direct backend search calls from non-browser clients.
This helper drives the site's own callArchivosSerie() in headless Chromium.
It never clicks download links and never attempts reCAPTCHA authorization.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pyproj import Transformer
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_sa_calobra_cnig_records import compact_point, dedupe, parse_rows  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def query_page(
    driver: webdriver.Chrome,
    product_url: str,
    queries: list[tuple[str, float, float]],
    extension_pattern: str,
    required_token: str,
    subseries: str | None = None,
) -> dict:
    driver.get(product_url)
    WebDriverWait(driver, 45).until(
        lambda d: d.find_element(By.ID, "coordenadas")
    )
    driver.set_script_timeout(60)

    all_records = []
    receipts = []
    for label, lon, lat in queries:
        coords = compact_point(lon, lat)
        result = driver.execute_async_script(
            """
            const coords = arguments[0];
            const subseries = arguments[1] || '';
            const done = arguments[arguments.length - 1];
            if (typeof jQuery === 'undefined') {
              done({ok:false, error:'jQuery missing'});
              return;
            }
            jQuery.ajax({
              url: 'archivosSerie',
              data: {
                numPagina: '1',
                codAgr: jQuery('#codAgr').val() || '',
                codSerie: jQuery('#codSerie').val() || '',
                coordenadas: coords,
                series: jQuery('#series').val() || '',
                codComAutonoma: '',
                codProvincia: '',
                codIne: '',
                codTipoArchivo: '',
                codIdiomaInf: '',
                todaEspania: '',
                todoMundo: '',
                idProductor: '',
                rutaNombre: '',
                numHoja: '',
                numHoja25: '',
                totalArchivos: jQuery('#totalArchivos').val() || '',
                codSubSerie: subseries,
                contieneArc: '',
                keySearch: '',
                referCatastral: '',
                orderBy: ''
              },
              dataType: 'html'
            }).done(function(html) {
              done({ok:true, html:html});
            }).fail(function(xhr, textStatus, errorThrown) {
              done({
                ok:false,
                status:xhr.status,
                textStatus:textStatus,
                error:String(errorThrown || ''),
                response:String(xhr.responseText || '').slice(0, 1000)
              });
            });
            """,
            coords,
            subseries or "",
        )
        if not result or not result.get("ok"):
            raise RuntimeError(
                f"CNIG browser search failed for {label}: {json.dumps(result, ensure_ascii=False)}"
            )
        html = result["html"]
        rows = parse_rows(html, extension_pattern)
        accepted = [row for row in rows if required_token.lower() in row["name"].lower()]
        for row in accepted:
            row["query_labels"] = [label]
        all_records.extend(accepted)
        receipts.append(
            {
                "label": label,
                "lon_lat": [lon, lat],
                "all_rows": len(rows),
                "accepted_rows": len(accepted),
            }
        )
    return {
        "records": dedupe(all_records),
        "query_receipts": receipts,
    }

def main() -> None:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    sources = {source["id"]: source for source in manifest["sources"]}
    transformer = Transformer.from_crs("EPSG:25831", "EPSG:4326", always_xy=True)

    lidar_queries = []
    for locator in manifest["selection"]["lidar_grid_locator_hints"]:
        e_km, n_km = (int(v) for v in locator.split("-"))
        lon, lat = transformer.transform(e_km * 1000 + 500.0, n_km * 1000 + 500.0)
        lidar_queries.append((locator, lon, lat))

    min_e, min_n, max_e, max_n = map(float, manifest["aoi"]["bounds_m"])
    mds_metric = [
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
    mds_queries = [(label, *transformer.transform(e, n)) for label, e, n in mds_metric]

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--lang=es-ES")

    output = {
        "schema_version": 1,
        "issue": manifest["issue"],
        "method": "headless Chromium executing CNIG public product-page search only",
        "aoi": manifest["aoi"],
        "sources": {},
    }

    driver = webdriver.Chrome(options=options)
    try:
        lidar = query_page(
            driver,
            sources["pnoa_lidar_cob3_npc03"]["product_url"],
            lidar_queries,
            r"LAZ",
            "NPC03",
            subseries="A2403",
        )
        output["sources"]["pnoa_lidar_cob3_npc03"] = {
            **lidar,
            "record_count": len(lidar["records"]),
            "download_boundary": "Search only. recaptcha_authorized download links are not executed.",
        }

        mds = query_page(
            driver,
            sources["mds50cm_cob3_v1"]["product_url"],
            mds_queries,
            r"TIF|TIFF",
            "MDS50CM",
        )
        output["sources"]["mds50cm_cob3_v1"] = {
            **mds,
            "record_count": len(mds["records"]),
            "download_boundary": "Search only. Download authorization is not bypassed.",
        }

        ortho = query_page(
            driver,
            sources["pnoa_maxima_actualidad_2024"]["product_url"],
            mds_queries,
            r"TIF|TIFF",
            "PNOA",
        )
        output["sources"]["pnoa_maxima_actualidad_2024"] = {
            **ortho,
            "record_count": len(ortho["records"]),
            "download_boundary": (
                "Exact source COG discovery only. WMS working extracts remain separately "
                "acquirable without bypassing download authorization."
            ),
        }
    finally:
        driver.quit()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
