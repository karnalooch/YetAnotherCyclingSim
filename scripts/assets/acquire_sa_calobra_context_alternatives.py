"""Acquire official alternative P1 paths; preserve payloads outside Git."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import acquire_sa_calobra_world_data as base

ATOM = {"a": "http://www.w3.org/2005/Atom"}
REGIONAL = (
    "https://ideib.caib.es/geoserveis/rest/services/public/GOIB_SIOSE14_IB/MapServer"
)
NATIONAL = "https://www.catastro.hacienda.gob.es/INSPIRE/buildings/ES.SDGC.BU.atom.xml"


def validate_query(ids: dict, data: dict) -> int:
    if (
        ids.get("error")
        or data.get("error")
        or ids.get("exceededTransferLimit")
        or data.get("exceededTransferLimit")
    ):
        raise ValueError(
            f"ArcGIS error/partial result: {ids.get('error')}, {data.get('error')}, transferLimit={data.get('exceededTransferLimit')}"
        )
    expected = ids.get("objectIds")
    field = ids.get("objectIdFieldName")
    if (
        not isinstance(expected, list)
        or not field
        or len(expected) != len(set(expected))
    ):
        raise ValueError("Missing explicit object ID inventory")
    actual = [f["attributes"][field] for f in data.get("features", [])]
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise ValueError(
            "Feature identities do not match complete AOI object ID inventory"
        )
    if data.get("spatialReference", {}).get("wkid") != 25831:
        raise ValueError("Unverified response CRS; expected EPSG:25831")
    return len(actual)


def inspect_buildings(path: Path, bounds: list) -> dict:
    types = {
        "building": "Building",
        "buildingpart": "BuildingPart",
        "otherconstruction": "OtherConstruction",
    }
    counts, candidates, members = {}, {}, []
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():
            raise ValueError("ZIP CRC failure")
        for suffix, typename in types.items():
            matches = [
                n for n in archive.namelist() if n.endswith("." + suffix + ".gml")
            ]
            if len(matches) != 1:
                raise ValueError(f"Missing/ambiguous {typename} package member")
            payload = archive.read(matches[0])
            tree = ET.fromstring(payload)
            features = [n for n in tree.iter() if n.tag.split("}")[-1] == typename]
            counts[typename] = len(features)
            candidates[typename] = 0
            for feature in features:
                coords = []
                for node in feature.iter():
                    if node.get("srsName") and not node.get("srsName").endswith(
                        "::25831"
                    ):
                        raise ValueError(
                            f"Unexpected Catastro CRS {node.get('srsName')}"
                        )
                    if node.tag.split("}")[-1] in {"posList", "pos"} and node.text:
                        values = list(map(float, node.text.split()))
                        if len(values) % 2:
                            raise ValueError("Unverified coordinate dimension")
                        coords.extend(zip(values[::2], values[1::2]))
                if not coords:
                    raise ValueError(f"{typename} feature has no inspected coordinates")
                xs, ys = zip(*coords)
                if (
                    min(xs) <= bounds[2]
                    and max(xs) >= bounds[0]
                    and min(ys) <= bounds[3]
                    and max(ys) >= bounds[1]
                ):
                    candidates[typename] += 1
            import hashlib

            members.append(
                {
                    "name": matches[0],
                    "size_bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "feature_count": len(features),
                }
            )
    return {
        "feature_counts": counts,
        "aoi_bbox_candidate_counts": candidates,
        "members": members,
        "feature_types": list(types.values()),
        "note": "Municipality package; bbox candidates are not clipped geometry or proof of complete AOI municipal coverage.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--persistent-root", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    bounds = manifest["aoi"]["bounds_m"]
    root = args.persistent_root.resolve()
    client = base.session()
    rows = []
    sources = {}

    def fetch(name, url, params=None):
        path = root / name
        if path.exists():
            data = path.read_bytes()
            row = {
                "name": name,
                "size_bytes": len(data),
                "sha256": base.sha256(path),
                "url": url,
                "params": params,
                "reused": True,
            }
        else:
            response = base.request_with_retry(client, "GET", url, params=params)
            data = response.content
            row = base.write_bytes(path, data, False)
            row.pop("path")
            row.update(
                {
                    "name": name,
                    "url": url,
                    "params": params,
                    "http": base.response_record(response),
                }
            )
        rows.append(row)
        return data

    def catastro():
        national = ET.fromstring(fetch("catastro-national.atom.xml", NATIONAL))
        entry = next(
            e
            for e in national.findall("a:entry", ATOM)
            if "07 Baleares" in e.findtext("a:title", "", ATOM)
        )
        regional_url = entry.find("a:link", ATOM).get("href")
        regional = ET.fromstring(fetch("catastro-baleares.atom.xml", regional_url))
        entry = next(
            e
            for e in regional.findall("a:entry", ATOM)
            if "07019-ESCORCA" in e.findtext("a:title", "", ATOM)
        )
        url = entry.find("a:link", ATOM).get("href")
        name = url.rsplit("/", 1)[-1]
        fetch(name, url)
        return {
            "status": "acquired",
            "municipality": "07019-ESCORCA",
            "provider_updated": entry.findtext("a:updated", "", ATOM),
            "license": "DG Catastro INSPIRE v1 July 2016; raw original redistribution not authorized",
            **inspect_buildings(root / name, bounds),
        }

    def siose():
        service = json.loads(fetch("siose14-service.json", REGIONAL, {"f": "pjson"}))
        layer = next(x for x in service["layers"] if x["name"] == "SIOSE 2014")
        url = REGIONAL + "/" + str(layer["id"])
        metadata = json.loads(fetch("siose14-layer.json", url, {"f": "pjson"}))
        item = json.loads(
            fetch("siose14-iteminfo.json", REGIONAL + "/info/iteminfo", {"f": "pjson"})
        )
        if "SIOSE 2014" != metadata.get("name") or "SIOSE" not in item.get(
            "licenseInfo", ""
        ):
            raise ValueError("Unverified SIOSE 2014 identity/license")
        ids = json.loads(
            fetch(
                "siose14-ids.json",
                url + "/query",
                {
                    "f": "json",
                    "geometry": ",".join(map(str, bounds)),
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": "25831",
                    "spatialRel": "esriSpatialRelIntersects",
                    "where": "1=1",
                    "returnIdsOnly": "true",
                },
            )
        )
        if ids.get("error") or not isinstance(ids.get("objectIds"), list):
            raise ValueError(f"Object ID query failed: {ids}")
        data = json.loads(
            fetch(
                "siose14-features.json",
                url + "/query",
                {
                    "f": "json",
                    "objectIds": ",".join(map(str, ids["objectIds"])),
                    "outFields": "*",
                    "returnGeometry": "true",
                    "outSR": "25831",
                },
            )
        )
        return {
            "status": "acquired",
            "layer_id": layer["id"],
            "layer_name": layer["name"],
            "feature_count": validate_query(ids, data),
            "field_count": len(metadata["fields"]),
            "crs": "EPSG:25831",
            "license_evidence": "siose14-iteminfo.json",
            "attribution": "SIOSE © INSTITUTO GEOGRÁFICO NACIONAL DE ESPAÑA - SITIBSA - GOIB",
            "note": "Historical supporting context; intersecting features may extend past AOI. No normalized masks generated.",
        }

    for source_id, operation in [
        ("catastro_buildings_atom", catastro),
        ("siose_2014_ideib", siose),
    ]:
        start = len(rows)
        try:
            result = operation()
        except Exception as exc:  # noqa: BLE001 - persist provider failure, then exit nonzero
            result = {"status": "failed", "error": str(exc)}
        result["files"] = rows[start:]
        sources[source_id] = result
        print(source_id, result["status"])
    receipt = {
        "schema_version": 1,
        "issue": 335,
        "verified_date": "2026-10-04",
        "aoi": manifest["aoi"],
        "raw_sources_committed": False,
        "sources": sources,
    }
    base.write_text(
        args.receipt_out, json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
    )
    return 2 if any(s["status"] != "acquired" for s in sources.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
