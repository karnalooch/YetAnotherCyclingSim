"""Acquire AOI-only provisional regional hydrography; preserve errors and licenses."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import acquire_sa_calobra_world_data as base
from acquire_sa_calobra_context_alternatives import validate_query

SERVICE = "https://ideib.caib.es/geoserveis/rest/services/public/GOIB_XarxaHidro_RiscInun_IB/MapServer"
LICENSE = (
    "https://intranet.caib.es/opendatacataleg/es/dataset/xarxa-hidrografica-provisional"
)
BOUNDS = [483000, 4407500, 485016.5, 4409516.5]


def acquire(output):
    if output.exists():
        raise FileExistsError(
            "Preserve previous provider responses; choose a new directory"
        )
    output.mkdir(parents=True)
    client, rows = base.session(), []

    def fetch(name, url, params=None):
        response = base.request_with_retry(client, "GET", url, params=params)
        if len(response.content) > 16 * 1024 * 1024:
            raise ValueError("AOI provider response exceeds 16MiB safety limit")
        path = output / name
        row = base.write_bytes(path, response.content, False)
        row.pop("path")
        row.update(
            {
                "path": name,
                "url": url,
                "params": params,
                "http": base.response_record(response),
            }
        )
        rows.append(row)
        return response.content

    report = {
        "schema_version": 1,
        "aoi": {"crs": "EPSG:25831", "bounds_m": BOUNDS},
        "sources_committed": False,
        "acquired_utc": datetime.now(timezone.utc).isoformat(),
        "files": rows,
    }
    try:
        service = json.loads(fetch("service.json", SERVICE, {"f": "pjson"}))
        name = "Xarxa Hidrogràfica Provisional"
        layers = [layer for layer in service.get("layers", []) if layer["name"] == name]
        if len(layers) != 1 or layers[0].get("geometryType") != "esriGeometryPolyline":
            raise ValueError("Missing/ambiguous provisional hydrography layer")
        url = SERVICE + "/" + str(layers[0]["id"])
        metadata = json.loads(fetch("layer.json", url, {"f": "pjson"}))
        item = json.loads(
            fetch("iteminfo.json", SERVICE + "/info/iteminfo", {"f": "pjson"})
        )
        license_text = fetch("dataset-license.html", LICENSE).decode("utf-8")
        if (
            "Creative Commons Attribution" not in license_text
            or "IDEIB_SIG.XH_Xarxa_Hidrografica" not in license_text
        ):
            raise ValueError(
                "Explicit provisional hydrography dataset license not verified"
            )
        if (
            metadata.get("name") != name
            or metadata.get("geometryType") != "esriGeometryPolyline"
        ):
            raise ValueError("Provider layer metadata mismatch")
        params = {
            "f": "json",
            "geometry": ",".join(map(str, BOUNDS)),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "25831",
            "spatialRel": "esriSpatialRelIntersects",
            "where": "1=1",
            "returnIdsOnly": "true",
        }
        ids = json.loads(fetch("ids.json", url + "/query", params))
        if (
            ids.get("error")
            or not isinstance(ids.get("objectIds"), list)
            or len(ids["objectIds"]) > 500
        ):
            raise ValueError(
                "Object-ID inventory error or AOI limit exceeded: " + str(ids)
            )
        if ids["objectIds"]:
            params = {
                "f": "json",
                "objectIds": ",".join(map(str, ids["objectIds"])),
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": "25831",
            }
        else:
            params = {
                "f": "json",
                "where": "1=0",
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": "25831",
            }
        features = json.loads(fetch("features.json", url + "/query", params))
        count = validate_query(ids, features)
        if features.get("geometryType") != "esriGeometryPolyline":
            raise ValueError("Unexpected hydrography response geometry type")
        report.update(
            {
                "status": "ACQUIRED_AOI_CONTEXT",
                "feature_count": count,
                "feature_types": 1,
                "layer_id": layers[0]["id"],
                "layer_name": name,
                "license": "Dataset-specific Creative Commons Attribution; version not stated; retain dataset license snapshot. Service-wide iteminfo requests contacting distributor; dataset-specific public license applies to this named provisional dataset only, not other service layers.",
                "service_license_text": item.get("licenseInfo"),
                "attribution": "DG Recursos Hidrics / Govern de les Illes Balears, Xarxa Hidrografica Provisional",
                "limitations": "Provisional watercourses, not surveyed channel widths or permanent water; no flood-model or other regional layer admitted",
            }
        )
    except Exception as exc:
        report.update(
            {
                "status": "FAILED_CLOSED",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
    (output / "acquisition-receipt.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = acquire(args.output)
    print(
        json.dumps(
            {k: report[k] for k in ["status", "feature_count", "error"] if k in report}
        )
    )
    raise SystemExit(0 if report["status"] == "ACQUIRED_AOI_CONTEXT" else 2)
