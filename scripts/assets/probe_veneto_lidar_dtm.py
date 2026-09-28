#!/usr/bin/env python3
"""Probe the official Regione Veneto LiDAR DTM index around Passo Giau."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WFS_ENDPOINT = "https://idt2-geoserver.regione.veneto.it/geoserver/wfs"
TYPE_NAME = "rv:c0101071_lidar5m"
LICENSE = "IODL 2.0"
METADATA_URL = (
    "https://geodati.gov.it/geoportale/visualizzazione-metadati/"
    "scheda-metadati?metadataid=r_veneto%3Ac0101071_Lidar5m"
)
BBOX_WGS84 = (11.99, 46.42, 12.12, 46.55)
OUTPUT = (
    Path("Saved") / "RuntimeProof" / "CI" / "Stage3GR4_1"
    / "VenetoLidarProbe" / "veneto-lidar-wfs-probe.json"
)
USER_AGENT = (
    "YetAnotherCyclingSim-VenetoLidarProbe/1.0 "
    "(+https://github.com/karnalooch/YetAnotherCyclingSim)"
)


def fetch_text(params: dict[str, str], timeout: int = 60) -> tuple[str, str]:
    url = f"{WFS_ENDPOINT}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,application/xml,text/xml,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")
    return url, payload


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema_version": 1,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "Regione del Veneto",
        "dataset": "Quadro Unione DTM 5 metri da voli Lidar",
        "type_name": TYPE_NAME,
        "license": LICENSE,
        "metadata_url": METADATA_URL,
        "bbox_wgs84": {
            "west": BBOX_WGS84[0],
            "south": BBOX_WGS84[1],
            "east": BBOX_WGS84[2],
            "north": BBOX_WGS84[3],
        },
        "requests": [],
    }

    describe_params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "DescribeFeatureType",
        "typeName": TYPE_NAME,
    }
    try:
        url, payload = fetch_text(describe_params)
        report["requests"].append(
            {
                "kind": "DescribeFeatureType",
                "url": url,
                "ok": True,
                "response_preview": payload[:12000],
            }
        )
    except Exception as exc:
        report["requests"].append(
            {
                "kind": "DescribeFeatureType",
                "ok": False,
                "error": repr(exc),
            }
        )

    bbox_token = ",".join(f"{value:.6f}" for value in BBOX_WGS84) + ",EPSG:4326"
    feature_params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": TYPE_NAME,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "BBOX": bbox_token,
        "maxFeatures": "100",
    }

    matched_features: list[dict[str, Any]] = []
    feature_error: str | None = None
    feature_url = ""
    try:
        feature_url, payload = fetch_text(feature_params)
        parsed = json.loads(payload)
        raw_features = parsed.get("features", [])
        if not isinstance(raw_features, list):
            raise RuntimeError("GeoJSON 'features' is not a list")
        for feature in raw_features:
            if not isinstance(feature, dict):
                continue
            matched_features.append(
                {
                    "id": feature.get("id"),
                    "properties": feature.get("properties", {}),
                    "geometry": feature.get("geometry"),
                }
            )
    except Exception as exc:
        feature_error = repr(exc)

    report["get_feature"] = {
        "url": feature_url or None,
        "ok": feature_error is None,
        "error": feature_error,
        "feature_count": len(matched_features),
        "features": matched_features,
    }

    OUTPUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"[probe] wrote {OUTPUT}")
    print(f"[probe] matched features: {len(matched_features)}")
    if feature_error:
        print(f"[probe] GetFeature error: {feature_error}")
        return 2
    if not matched_features:
        print("[probe] official WFS returned zero LiDAR-index features for Passo Giau AOI")
        return 3

    property_keys = sorted(
        {
            str(key)
            for feature in matched_features
            for key in feature.get("properties", {}).keys()
        }
    )
    print("[probe] property keys:")
    for key in property_keys:
        print(f"  - {key}")
    for feature in matched_features:
        print("[probe] feature:")
        print(json.dumps(feature, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
