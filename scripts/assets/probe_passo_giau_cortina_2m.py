#!/usr/bin/env python3
"""Fail-closed discovery probe for the official Veneto Cortina 2 m DTM.

This probe intentionally does not download or resample elevation data. It first
proves that the official Regione del Veneto services expose one unambiguous
DTM_2m_Cortina layer/coverage, that Passo Giau lies inside its advertised
geographic extent, and that WCS DescribeCoverage reports an approximately 2 m
native grid in a projected coordinate system.

External terrain remains presentation-only and must never become authoritative
YACS route or physics geometry.
"""

from __future__ import annotations

import json
import math
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

WMS_ENDPOINT = "https://idt2-geoserver.regione.veneto.it/geoserver/wms"
WCS_ENDPOINT = "https://idt2-geoserver.regione.veneto.it/geoserver/wcs"
TARGET_LAYER_LABEL = "DTM_2m_Cortina"
PASSO_GIAU_WGS84 = (12.05321, 46.48284)
EXPECTED_RESOLUTION_M = 2.0
RESOLUTION_TOLERANCE_M = 0.25
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
USER_AGENT = (
    "YetAnotherCyclingSim-Cortina2mProbe/1.0 "
    "(+https://github.com/karnalooch/YetAnotherCyclingSim)"
)
OUTPUT = (
    Path("Saved")
    / "RuntimeProof"
    / "CI"
    / "Stage3GR4_1"
    / "Cortina2mProbe"
    / "cortina-2m-source-probe.json"
)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def normalized(value: str | None) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def query_url(base: str, params: dict[str, str]) -> str:
    return f"{base}?{urllib.parse.urlencode(params)}"


def request_bytes(url: str, *, timeout: int = 60) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/xml,text/xml,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise RuntimeError(
                f"response exceeded {MAX_RESPONSE_BYTES} bytes: {url}"
            )
        return payload


def parse_xml(payload: bytes, label: str) -> ET.Element:
    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise RuntimeError(f"{label} returned invalid XML: {exc}") from exc


def child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if local_name(child.tag) == name and child.text:
            return child.text.strip()
    return None


def descendant_texts(element: ET.Element, names: set[str]) -> list[str]:
    values: list[str] = []
    for item in element.iter():
        if local_name(item.tag) in names and item.text:
            value = item.text.strip()
            if value and value not in values:
                values.append(value)
    return values


def parse_float_pair(text: str | None) -> tuple[float, float] | None:
    if not text:
        return None
    parts = text.replace(",", " ").split()
    if len(parts) != 2:
        return None
    return float(parts[0]), float(parts[1])


def geographic_bbox(layer: ET.Element) -> dict[str, float] | None:
    for child in layer:
        if local_name(child.tag) != "EX_GeographicBoundingBox":
            continue
        values: dict[str, float] = {}
        mapping = {
            "westBoundLongitude": "west",
            "eastBoundLongitude": "east",
            "southBoundLatitude": "south",
            "northBoundLatitude": "north",
        }
        for part in child:
            key = mapping.get(local_name(part.tag))
            if key and part.text:
                values[key] = float(part.text.strip())
        if len(values) == 4:
            return values
    return None


def flatten_wms_layers(root: ET.Element) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    target = normalized(TARGET_LAYER_LABEL)
    for element in root.iter():
        if local_name(element.tag) != "Layer":
            continue
        name = child_text(element, "Name")
        title = child_text(element, "Title")
        if not name and not title:
            continue
        if target not in {normalized(name), normalized(title)}:
            continue
        crs_values = [
            child.text.strip()
            for child in element
            if local_name(child.tag) in {"CRS", "SRS"} and child.text
        ]
        layers.append(
            {
                "name": name,
                "title": title,
                "crs": sorted(set(crs_values)),
                "geographic_bbox_wgs84": geographic_bbox(element),
            }
        )
    return layers


def point_inside_bbox(
    lon: float,
    lat: float,
    bbox: dict[str, float] | None,
) -> bool:
    if bbox is None:
        return False
    return (
        bbox["west"] <= lon <= bbox["east"]
        and bbox["south"] <= lat <= bbox["north"]
    )


def wcs_coverage_candidates(
    root: ET.Element,
    *,
    wms_name: str | None,
) -> list[dict[str, str | None]]:
    expected = {
        normalized(TARGET_LAYER_LABEL),
        normalized(wms_name),
    }
    expected.discard("")
    matches: list[dict[str, str | None]] = []
    for element in root.iter():
        if local_name(element.tag) != "CoverageSummary":
            continue
        identifier = child_text(element, "CoverageId") or child_text(
            element, "Identifier"
        )
        title = (
            child_text(element, "Title")
            or child_text(element, "Label")
            or child_text(element, "Description")
        )
        values = {normalized(identifier), normalized(title)}
        if expected.intersection(values):
            matches.append({"identifier": identifier, "title": title})
    return matches


def parse_offset_vectors(root: ET.Element) -> list[tuple[float, ...]]:
    vectors: list[tuple[float, ...]] = []
    for element in root.iter():
        if local_name(element.tag) != "offsetVector" or not element.text:
            continue
        parts = element.text.replace(",", " ").split()
        try:
            vector = tuple(float(value) for value in parts)
        except ValueError:
            continue
        if vector:
            vectors.append(vector)
    return vectors


def vector_magnitude(vector: Iterable[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def parse_describe_coverage(root: ET.Element) -> dict[str, Any]:
    srs_names: list[str] = []
    envelope: dict[str, Any] | None = None
    for element in root.iter():
        if local_name(element.tag) != "Envelope":
            continue
        srs_name = element.attrib.get("srsName")
        if srs_name and srs_name not in srs_names:
            srs_names.append(srs_name)
        lower = child_text(element, "lowerCorner")
        upper = child_text(element, "upperCorner")
        lower_pair = parse_float_pair(lower)
        upper_pair = parse_float_pair(upper)
        if lower_pair and upper_pair and envelope is None:
            envelope = {
                "srs_name": srs_name,
                "lower_corner": list(lower_pair),
                "upper_corner": list(upper_pair),
            }

    vectors = parse_offset_vectors(root)
    magnitudes = [vector_magnitude(vector) for vector in vectors]
    return {
        "srs_names": srs_names,
        "envelope": envelope,
        "offset_vectors": [list(vector) for vector in vectors],
        "offset_magnitudes": magnitudes,
    }


def validate_resolution(description: dict[str, Any]) -> list[float]:
    magnitudes = [
        float(value)
        for value in description.get("offset_magnitudes", [])
        if float(value) > 0.0
    ]
    if len(magnitudes) < 2:
        raise RuntimeError(
            "DescribeCoverage did not expose at least two non-zero grid "
            "offset vectors"
        )
    ordered = sorted(magnitudes)[:2]
    for value in ordered:
        if abs(value - EXPECTED_RESOLUTION_M) > RESOLUTION_TOLERANCE_M:
            raise RuntimeError(
                "Cortina coverage is not proven as a 2 m grid: "
                f"offset magnitude {value:.6f} m"
            )
    return ordered


def fetch_wms_layer() -> tuple[str, dict[str, Any]]:
    url = query_url(
        WMS_ENDPOINT,
        {
            "service": "WMS",
            "version": "1.3.0",
            "request": "GetCapabilities",
        },
    )
    root = parse_xml(request_bytes(url), "WMS GetCapabilities")
    matches = flatten_wms_layers(root)
    if len(matches) != 1:
        raise RuntimeError(
            "expected exactly one WMS DTM_2m_Cortina layer, "
            f"found {len(matches)}: {matches}"
        )
    layer = matches[0]
    lon, lat = PASSO_GIAU_WGS84
    if not point_inside_bbox(lon, lat, layer["geographic_bbox_wgs84"]):
        raise RuntimeError(
            "Passo Giau is outside the WMS layer's advertised WGS84 extent: "
            f"{layer['geographic_bbox_wgs84']}"
        )
    return url, layer


def fetch_wcs_coverage(wms_name: str | None) -> tuple[str, dict[str, Any]]:
    url = query_url(
        WCS_ENDPOINT,
        {
            "service": "WCS",
            "version": "2.0.1",
            "request": "GetCapabilities",
        },
    )
    root = parse_xml(request_bytes(url), "WCS GetCapabilities")
    matches = wcs_coverage_candidates(root, wms_name=wms_name)
    if len(matches) != 1:
        raise RuntimeError(
            "expected exactly one WCS coverage matching DTM_2m_Cortina, "
            f"found {len(matches)}: {matches}"
        )
    return url, matches[0]


def fetch_coverage_description(
    coverage_id: str,
) -> tuple[str, dict[str, Any], list[float]]:
    url = query_url(
        WCS_ENDPOINT,
        {
            "service": "WCS",
            "version": "2.0.1",
            "request": "DescribeCoverage",
            "coverageId": coverage_id,
        },
    )
    root = parse_xml(request_bytes(url), "WCS DescribeCoverage")
    description = parse_describe_coverage(root)
    proven_resolution = validate_resolution(description)
    return url, description, proven_resolution


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema_version": 1,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "Regione del Veneto",
        "target_dataset_label": TARGET_LAYER_LABEL,
        "passo_giau_wgs84": {
            "lon": PASSO_GIAU_WGS84[0],
            "lat": PASSO_GIAU_WGS84[1],
        },
        "expected_native_resolution_m": EXPECTED_RESOLUTION_M,
        "resolution_tolerance_m": RESOLUTION_TOLERANCE_M,
        "yacs_policy": {
            "presentation_only": True,
            "authoritative_route_geometry": False,
            "authoritative_physics": False,
            "download_or_resample_performed": False,
        },
    }

    try:
        wms_url, layer = fetch_wms_layer()
        report["wms"] = {
            "get_capabilities_url": wms_url,
            "layer": layer,
        }

        wcs_url, coverage = fetch_wcs_coverage(layer.get("name"))
        report["wcs"] = {
            "get_capabilities_url": wcs_url,
            "coverage": coverage,
        }

        coverage_id = str(coverage.get("identifier") or "").strip()
        if not coverage_id:
            raise RuntimeError("matched WCS coverage has no identifier")

        describe_url, description, resolution = fetch_coverage_description(
            coverage_id
        )
        report["wcs"]["describe_coverage_url"] = describe_url
        report["wcs"]["description"] = description
        report["proven_native_resolution_m"] = resolution
        report["status"] = "PROVEN_2M_SOURCE_CONTRACT"
        exit_code = 0
    except Exception as exc:
        report["status"] = "BLOCKED"
        report["error"] = str(exc)
        exit_code = 2

    OUTPUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"[cortina-2m] status={report['status']}")
    print(f"[cortina-2m] report={OUTPUT}")
    if exit_code:
        print(f"[cortina-2m] ERROR: {report['error']}", file=sys.stderr)
    else:
        print(
            "[cortina-2m] layer="
            f"{report['wms']['layer'].get('name')} "
            f"coverage={report['wcs']['coverage'].get('identifier')} "
            f"resolution={report['proven_native_resolution_m']}"
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
