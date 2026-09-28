#!/usr/bin/env python3
"""Download the official Regione del Veneto road graph for the Passo Giau AOI.

The source is presentation/reference data only. It must never silently replace
FRouteGeometryProfile or the Road Physics Profile.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WFS_ENDPOINT = "https://idt2-geoserver.regione.veneto.it/geoserver/wfs"
TYPE_NAME = "rv:c01070240012_elementostradale"
METADATA_URL = (
    "https://idt2.regione.veneto.it/geoportal/catalog/search/resource/"
    "details.page?uuid=r_veneto%3Ac01070240012_ElementoStradale"
)
LICENSE = "IODL 2.0"
ATTRIBUTION = (
    "Regione del Veneto – L.R. n. 28/76 – Formazione della Carta Tecnica Regionale"
)
TARGET_CRS = "EPSG:32632"
TARGET_BOUNDS = (730406.587, 5148246.775, 738406.587, 5156246.775)
ROAD_ROUTE_ID = "000000027157"
ROAD_NAME = "SP 638 DEL PASSO GIAU (BL)"
MAX_FEATURES = 1000
MAX_BYTES = 8 * 1024 * 1024
USER_AGENT = (
    "YetAnotherCyclingSim-RoadDownloader/1.0 "
    "(+https://github.com/karnalooch/YetAnotherCyclingSim)"
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def output_root() -> Path:
    return repository_root() / "ExternalAssets" / "Terrain" / "PassoGiau" / "RoadNetwork"


def fetch_bytes(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise RuntimeError(f"road WFS response exceeded {MAX_BYTES} bytes")
        content_type = str(response.headers.get("Content-Type") or "")
        if "json" not in content_type.lower():
            raise RuntimeError(f"unexpected road WFS content type: {content_type!r}")
        return payload


def build_query_url() -> str:
    bbox = ",".join(str(value) for value in TARGET_BOUNDS) + f",{TARGET_CRS}"
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": TYPE_NAME,
        "outputFormat": "application/json",
        "srsName": TARGET_CRS,
        "bbox": bbox,
        "maxFeatures": str(MAX_FEATURES),
    }
    return f"{WFS_ENDPOINT}?{urllib.parse.urlencode(params)}"


def validate_feature(feature: dict[str, Any]) -> None:
    geometry = feature.get("geometry")
    properties = feature.get("properties")
    if not isinstance(geometry, dict) or geometry.get("type") not in {
        "LineString",
        "MultiLineString",
    }:
        raise RuntimeError(f"unexpected road geometry: {feature.get('id')}")
    if not isinstance(properties, dict):
        raise RuntimeError(f"missing road properties: {feature.get('id')}")


def is_sp638(feature: dict[str, Any]) -> bool:
    props = feature.get("properties") or {}
    return (
        str(props.get("id_perc") or "").strip() == ROAD_ROUTE_ID
        and str(props.get("percorsoam") or "").strip().upper() == ROAD_NAME
    )


def main() -> int:
    try:
        query_url = build_query_url()
        payload = fetch_bytes(query_url)
        parsed = json.loads(payload.decode("utf-8"))
        if parsed.get("type") != "FeatureCollection":
            raise RuntimeError("Veneto road WFS did not return a FeatureCollection")

        features = parsed.get("features")
        if not isinstance(features, list) or not features:
            raise RuntimeError("Veneto road WFS returned no AOI features")
        if len(features) >= MAX_FEATURES:
            raise RuntimeError(
                f"road WFS reached safety cap ({MAX_FEATURES}); query is too broad"
            )
        for feature in features:
            if not isinstance(feature, dict):
                raise RuntimeError("road WFS returned a non-object feature")
            validate_feature(feature)

        road_features = [feature for feature in features if is_sp638(feature)]
        if len(road_features) < 3:
            raise RuntimeError(
                f"expected multiple SP638 features in AOI, got {len(road_features)}"
            )

        for feature in road_features:
            props = feature["properties"]
            if int(props.get("visibile") or 0) != 1:
                raise RuntimeError(f"SP638 feature is not visible: {feature.get('id')}")
            if int(props.get("stato") or 0) != 1:
                raise RuntimeError(f"SP638 feature is not active: {feature.get('id')}")
            if int(props.get("fittizio") or 0) != 0:
                raise RuntimeError(f"SP638 feature is synthetic: {feature.get('id')}")

        out = output_root()
        out.mkdir(parents=True, exist_ok=True)
        raw_path = out / "passo_giau_road_aoi_raw.geojson"
        road_path = out / "passo_giau_sp638_source.geojson"
        report_path = out / "road-download-report.json"

        raw_path.write_bytes(payload)
        selected = {
            "type": "FeatureCollection",
            "name": "SP 638 DEL PASSO GIAU (BL)",
            "crs": parsed.get("crs"),
            "features": road_features,
        }
        road_path.write_text(
            json.dumps(selected, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

        source_lengths = [
            float((feature.get("properties") or {}).get("lunghez") or 0.0)
            for feature in road_features
        ]
        node_ids = sorted(
            {
                str((feature.get("properties") or {}).get(key) or "")
                for feature in road_features
                for key in ("nodo_ini", "nodo_fin")
                if str((feature.get("properties") or {}).get(key) or "")
            }
        )
        report = {
            "schema_version": 1,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "provider": "Regione del Veneto",
            "dataset": "Rete stradale derivata da DataBase strati prioritario in scala 1:10.000",
            "layer": TYPE_NAME,
            "metadata_url": METADATA_URL,
            "license": LICENSE,
            "required_attribution": ATTRIBUTION,
            "reported_positional_accuracy_m": 4.0,
            "query_url": query_url,
            "target_crs": TARGET_CRS,
            "target_bounds_epsg32632": {
                "left": TARGET_BOUNDS[0],
                "bottom": TARGET_BOUNDS[1],
                "right": TARGET_BOUNDS[2],
                "top": TARGET_BOUNDS[3],
            },
            "aoi_feature_count": len(features),
            "road": {
                "name": ROAD_NAME,
                "route_id": ROAD_ROUTE_ID,
                "feature_count": len(road_features),
                "source_length_sum_m": round(sum(source_lengths), 3),
                "node_count": len(node_ids),
                "feature_ids": [str(feature.get("id") or "") for feature in road_features],
            },
            "source_sha256": hashlib.sha256(payload).hexdigest(),
            "outputs": {
                "aoi_raw_geojson": raw_path.name,
                "sp638_source_geojson": road_path.name,
            },
            "yacs_policy": {
                "presentation_only": True,
                "authoritative_route_geometry": False,
                "authoritative_physics": False,
            },
        }
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        print("Passo Giau official road download")
        print(f"  AOI features: {len(features)}")
        print(f"  SP638 features: {len(road_features)}")
        print(f"  source length sum: {sum(source_lengths):.1f} m")
        print(f"  source SHA256: {report['source_sha256']}")
        print(f"[ok] {road_path}")
        return 0
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
