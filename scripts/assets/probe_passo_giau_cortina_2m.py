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
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

WMS_ENDPOINT = "https://idt2-geoserver.regione.veneto.it/geoserver/wms"
WCS_ENDPOINT = "https://idt2-geoserver.regione.veneto.it/geoserver/wcs"
VIEWER_URL = "https://idt2.regione.veneto.it/idt/webgis/viewer?webgisId=86"
PORTFOLIO_URL = "https://idt2.regione.veneto.it/portfolio/webgis-olimpiadi-2026-in-veneto/"
DOWNLOAD_PAGE = "https://idt2.regione.veneto.it/idt/downloader/download"
GENERIC_LAYERS_ENDPOINT = "https://idt2.regione.veneto.it/idt/download/layerDownload/getDownloadableLayersWithPermission"
CSW_ENDPOINT = "https://idt2.regione.veneto.it/geoportal/csw"
TARGET_LAYER_LABEL = "DTM_2m_Cortina"
PREFERRED_WMS_LAYER = "rv:DTM_2m_clip"
PASSO_GIAU_WGS84 = (12.05321, 46.48284)
EXPECTED_RESOLUTION_M = 2.0
RESOLUTION_TOLERANCE_M = 0.25
WCS_VERSIONS = ("2.0.1", "1.1.1", "1.0.0")
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
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}{urllib.parse.urlencode(params)}"


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


def extract_endpoint_candidates(body: str) -> list[str]:
    candidates: list[str] = []
    patterns = (
        r"""(["'])([^"']*(?:download|layerdownload|catalog|rest)[^"']*)\1""",
        r"""\burl\s*[:=]\s*(["'])([^"']+)\1""",
    )
    for pattern in patterns:
        for match in re.findall(pattern, body, flags=re.IGNORECASE):
            value = match[1]
            cleaned = value.strip()
            if not cleaned or len(cleaned) > 500:
                continue
            if cleaned not in candidates:
                candidates.append(cleaned)
    return candidates[:120]


def discover_download_portal() -> dict[str, Any]:
    payload = request_bytes(DOWNLOAD_PAGE)
    page = payload.decode("utf-8", errors="replace")
    script_sources = re.findall(
        r"""<script[^>]+src=["']([^"']+)["']""",
        page,
        flags=re.IGNORECASE,
    )
    terms = ("cortina", "dtm_2m", "dtm2m", "downloaddtm", "lidar")
    hits: list[dict[str, Any]] = []
    likely_sources = [
        raw_src
        for raw_src in script_sources
        if any(
            token in raw_src.lower()
            for token in ("download", "dtm", "configurator")
        )
    ][:24]
    for raw_src in likely_sources:
        url = urllib.parse.urljoin(DOWNLOAD_PAGE, raw_src)
        try:
            body = request_bytes(url, timeout=12).decode("utf-8", errors="replace")
        except Exception as exc:
            hits.append({"url": url, "fetch_error": str(exc)})
            continue
        lower = body.lower()
        matching_terms = [term for term in terms if term in lower]
        if not matching_terms:
            continue
        snippets: list[str] = []
        for term in matching_terms:
            offset = 0
            while len(snippets) < 20:
                index = lower.find(term, offset)
                if index < 0:
                    break
                start = max(0, index - 500)
                end = min(len(body), index + len(term) + 1200)
                snippet = body[start:end]
                if snippet not in snippets:
                    snippets.append(snippet)
                offset = index + len(term)
        hits.append(
            {
                "url": url,
                "matching_terms": matching_terms,
                "endpoint_candidates": extract_endpoint_candidates(body),
                "snippets": snippets,
            }
        )
    return {
        "url": DOWNLOAD_PAGE,
        "script_count": len(script_sources),
        "probed_script_count": len(likely_sources),
        "interesting_scripts": hits,
    }


def discover_viewer_context() -> dict[str, Any]:
    payload = request_bytes(VIEWER_URL)
    page = payload.decode("utf-8", errors="replace")
    lower = page.lower()
    needle = TARGET_LAYER_LABEL.lower()
    index = lower.find(needle)
    if index < 0:
        return {
            "url": VIEWER_URL,
            "contains_target_label": False,
            "bytes": len(payload),
            "snippet": None,
        }
    start = max(0, index - 1200)
    end = min(len(page), index + len(TARGET_LAYER_LABEL) + 1800)
    return {
        "url": VIEWER_URL,
        "contains_target_label": True,
        "bytes": len(payload),
        "snippet": page[start:end],
    }

def portfolio_contract_from_html(page: str) -> dict[str, Any]:
    lower = page.lower()
    resampled_markers = (
        "ricampionati a 2m",
        "ricampionati a 2 m",
    )
    resampled_index = next(
        (lower.find(marker) for marker in resampled_markers if marker in lower),
        -1,
    )
    viewer_ref = "webgisid=86"
    viewer_index = lower.find(viewer_ref)
    start_candidates = [
        index for index in (resampled_index, viewer_index) if index >= 0
    ]
    snippet = None
    if start_candidates:
        center = min(start_candidates)
        snippet = page[max(0, center - 1000): min(len(page), center + 2400)]
    return {
        "mentions_resampled_2m": resampled_index >= 0,
        "links_olympic_viewer_86": viewer_index >= 0,
        "snippet": snippet,
    }


def discover_portfolio_context() -> dict[str, Any]:
    payload = request_bytes(PORTFOLIO_URL)
    page = payload.decode("utf-8", errors="replace")
    contract = portfolio_contract_from_html(page)
    return {
        "url": PORTFOLIO_URL,
        "bytes": len(payload),
        **contract,
    }


def wms_discovery_candidates(root: ET.Element) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for element in root.iter():
        if local_name(element.tag) != "Layer":
            continue
        name = child_text(element, "Name")
        title = child_text(element, "Title")
        haystack = normalized(f"{name or ''} {title or ''}")
        score = sum(token in haystack for token in ("dtm", "2m", "cortina"))
        if score < 2:
            continue
        candidates.append(
            {
                "name": name,
                "title": title,
                "score": score,
                "geographic_bbox_wgs84": geographic_bbox(element),
            }
        )
    return sorted(
        candidates,
        key=lambda item: (-int(item["score"]), str(item.get("name") or "")),
    )[:80]


def request_json(url: str, *, timeout: int = 30) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise RuntimeError(
                f"response exceeded {MAX_RESPONSE_BYTES} bytes: {url}"
            )
    try:
        return json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"endpoint returned invalid JSON: {url}: {exc}") from exc


def json_catalog_matches(value: Any) -> list[dict[str, Any]]:
    targets = (
        normalized(TARGET_LAYER_LABEL),
        normalized(PREFERRED_WMS_LAYER),
        normalized("DTM_2m_clip"),
        normalized("Cortina"),
    )
    matches: list[dict[str, Any]] = []

    def visit(node: Any, path: str) -> None:
        if len(matches) >= 50:
            return
        if isinstance(node, dict):
            primitive_text = " ".join(
                str(item)
                for item in node.values()
                if isinstance(item, (str, int, float, bool))
            )
            haystack = normalized(primitive_text)
            if any(target and target in haystack for target in targets):
                safe: dict[str, Any] = {}
                for key, item in node.items():
                    if isinstance(item, (str, int, float, bool)) or item is None:
                        text_value = str(item)
                        safe[str(key)] = (
                            text_value[:1000]
                            if isinstance(item, str)
                            else item
                        )
                matches.append({"path": path, "item": safe})
                return
            for key, item in node.items():
                visit(item, f"{path}.{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                visit(item, f"{path}[{index}]")

    visit(value, "$")
    return matches


def discover_generic_downloadable_layers() -> dict[str, Any]:
    try:
        payload = request_json(GENERIC_LAYERS_ENDPOINT)
    except Exception as exc:
        return {
            "url": GENERIC_LAYERS_ENDPOINT,
            "status": "FETCH_FAILED",
            "error": str(exc),
        }

    result: dict[str, Any] = {
        "url": GENERIC_LAYERS_ENDPOINT,
        "status": "FETCHED",
        "payload_type": type(payload).__name__,
        "matches": json_catalog_matches(payload),
    }
    if isinstance(payload, dict):
        result["top_level_keys"] = sorted(str(key) for key in payload.keys())
        for key in ("result", "data", "items"):
            item = payload.get(key)
            if isinstance(item, list):
                result["item_count"] = len(item)
                result["item_container"] = key
                break
    elif isinstance(payload, list):
        result["item_count"] = len(payload)
        result["item_container"] = "$"
    return result


def parse_csw_records(root: ET.Element) -> dict[str, Any]:
    search_results: ET.Element | None = None
    for element in root.iter():
        if local_name(element.tag) == "SearchResults":
            search_results = element
            break

    summary: dict[str, Any] = {
        "matched": None,
        "returned": None,
        "records": [],
    }
    if search_results is None:
        return summary

    for source_key, target_key in (
        ("numberOfRecordsMatched", "matched"),
        ("numberOfRecordsReturned", "returned"),
    ):
        raw = search_results.attrib.get(source_key)
        if raw is not None:
            try:
                summary[target_key] = int(raw)
            except ValueError:
                summary[target_key] = raw

    interesting = {
        "identifier",
        "fileIdentifier",
        "title",
        "abstract",
        "description",
        "URI",
        "references",
        "URL",
        "linkage",
        "format",
        "type",
        "rights",
        "license",
        "otherConstraints",
        "useLimitation",
    }
    for child in list(search_results)[:100]:
        values: dict[str, list[str]] = {}
        for element in child.iter():
            name = local_name(element.tag)
            if name not in interesting:
                continue
            text_value = (element.text or "").strip()
            if not text_value:
                continue
            values.setdefault(name, [])
            if text_value not in values[name]:
                values[name].append(text_value[:4000])
        if values:
            summary["records"].append(values)
    return summary


def csw_filter_constraint(term: str) -> str:
    escaped = (
        term.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
    return (
        '<ogc:Filter xmlns:ogc="http://www.opengis.net/ogc" '
        'xmlns:csw="http://www.opengis.net/cat/csw/2.0.2">'
        '<ogc:PropertyIsLike wildCard="%" singleChar="_" escapeChar="\\">'
        '<ogc:PropertyName>csw:AnyText</ogc:PropertyName>'
        f'<ogc:Literal>%{escaped}%</ogc:Literal>'
        '</ogc:PropertyIsLike>'
        '</ogc:Filter>'
    )


def discover_csw_metadata() -> dict[str, Any]:
    queries: list[dict[str, Any]] = []
    for term in ("DTM_2m_Cortina", "DTM_2m_clip", "Cortina DTM"):
        constraint = csw_filter_constraint(term)
        url = query_url(
            CSW_ENDPOINT,
            {
                "service": "CSW",
                "version": "2.0.2",
                "request": "GetRecords",
                "resultType": "results",
                "typeNames": "csw:Record",
                "elementSetName": "full",
                "outputSchema": "http://www.opengis.net/cat/csw/2.0.2",
                "constraintLanguage": "FILTER",
                "constraint_language_version": "1.1.0",
                "constraint": constraint,
                "maxRecords": "50",
            },
        )
        item: dict[str, Any] = {"term": term, "url": url}
        try:
            root = parse_xml(request_bytes(url), "CSW GetRecords")
            item["response_root"] = local_name(root.tag)
            exception_texts = descendant_texts(
                root,
                {"ExceptionText", "ServiceException"},
            )
            if exception_texts:
                item["exception_texts"] = exception_texts
            item.update(parse_csw_records(root))
        except Exception as exc:
            item["error"] = str(exc)
        queries.append(item)
    return {"endpoint": CSW_ENDPOINT, "queries": queries}


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


def descendant_href_values(element: ET.Element, container_name: str) -> list[str]:
    values: list[str] = []
    for container in element:
        if local_name(container.tag) != container_name:
            continue
        for item in container.iter():
            if local_name(item.tag) != "OnlineResource":
                continue
            for key, value in item.attrib.items():
                if local_name(key) == "href" and value and value not in values:
                    values.append(value)
    return values


def flatten_wms_layers(root: ET.Element) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    targets = {
        normalized(TARGET_LAYER_LABEL),
        normalized(PREFERRED_WMS_LAYER),
    }
    for element in root.iter():
        if local_name(element.tag) != "Layer":
            continue
        name = child_text(element, "Name")
        title = child_text(element, "Title")
        if not name and not title:
            continue
        if not targets.intersection({normalized(name), normalized(title)}):
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
                "abstract": child_text(element, "Abstract"),
                "metadata_urls": descendant_href_values(element, "MetadataURL"),
                "data_urls": descendant_href_values(element, "DataURL"),
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
        if local_name(element.tag) not in {
            "CoverageSummary",
            "CoverageOfferingBrief",
        }:
            continue
        identifier = (
            child_text(element, "CoverageId")
            or child_text(element, "Identifier")
            or child_text(element, "name")
        )
        title = (
            child_text(element, "Title")
            or child_text(element, "Label")
            or child_text(element, "label")
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


def fetch_describe_layer() -> tuple[str, list[dict[str, str]]]:
    url = query_url(
        WMS_ENDPOINT,
        {
            "service": "WMS",
            "version": "1.1.1",
            "request": "DescribeLayer",
            "layers": PREFERRED_WMS_LAYER,
        },
    )
    root = parse_xml(request_bytes(url), "WMS DescribeLayer")
    descriptions: list[dict[str, str]] = []
    for element in root.iter():
        if local_name(element.tag) not in {"LayerDescription", "Layer"}:
            continue
        attrs = {
            local_name(key): value
            for key, value in element.attrib.items()
            if value
        }
        name = attrs.get("name") or attrs.get("layerName")
        if normalized(name) != normalized(PREFERRED_WMS_LAYER):
            continue
        descriptions.append(attrs)
    return url, descriptions


def normalize_service_endpoint(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.hostname == "idt2-geoserver.regione.veneto.it"
        and parsed.scheme == "http"
        and parsed.port == 80
    ):
        netloc = parsed.hostname
        return urllib.parse.urlunsplit(
            ("https", netloc, parsed.path, parsed.query, parsed.fragment)
        )
    return value


def wcs_endpoint_candidates(
    descriptions: list[dict[str, str]],
) -> list[str]:
    candidates = [WCS_ENDPOINT]
    for item in descriptions:
        for key in ("owsURL", "owsUrl", "url"):
            value = item.get(key)
            if value:
                normalized_endpoint = normalize_service_endpoint(value)
                if normalized_endpoint not in candidates:
                    candidates.append(normalized_endpoint)
    workspace = PREFERRED_WMS_LAYER.split(":", 1)[0]
    workspace_url = (
        "https://idt2-geoserver.regione.veneto.it/geoserver/"
        f"{workspace}/wcs"
    )
    if workspace_url not in candidates:
        candidates.append(workspace_url)
    return candidates


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
        candidates = wms_discovery_candidates(root)
        raise RuntimeError(
            "expected exactly one raw Cortina 2 m WMS source "
            f"({TARGET_LAYER_LABEL} alias or {PREFERRED_WMS_LAYER}), "
            f"found {len(matches)}; discovery candidates={candidates}"
        )
    layer = matches[0]
    lon, lat = PASSO_GIAU_WGS84
    if not point_inside_bbox(lon, lat, layer["geographic_bbox_wgs84"]):
        raise RuntimeError(
            "Passo Giau is outside the WMS layer's advertised WGS84 extent: "
            f"{layer['geographic_bbox_wgs84']}"
        )
    return url, layer


def discover_wcs_coverage(
    wms_name: str | None,
    endpoints: list[str],
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    found: list[dict[str, Any]] = []
    for endpoint in endpoints:
        for version in WCS_VERSIONS:
            params = {
                "service": "WCS",
                "request": "GetCapabilities",
            }
            if version.startswith("1.1"):
                params["AcceptVersions"] = version
            else:
                params["version"] = version
            url = query_url(endpoint, params)
            attempt: dict[str, Any] = {
                "endpoint": endpoint,
                "requested_version": version,
                "get_capabilities_url": url,
            }
            try:
                root = parse_xml(request_bytes(url), "WCS GetCapabilities")
                attempt["response_version"] = root.attrib.get("version")
                matches = wcs_coverage_candidates(root, wms_name=wms_name)
                attempt["matches"] = matches
                for match in matches:
                    found.append(
                        {
                            "endpoint": endpoint,
                            "version": version,
                            "get_capabilities_url": url,
                            "coverage": match,
                        }
                    )
            except Exception as exc:
                attempt["error"] = str(exc)
            attempts.append(attempt)

    return {"attempts": attempts, "found": found}


def fetch_coverage_description(
    endpoint: str,
    version: str,
    coverage_id: str,
) -> tuple[str, dict[str, Any], list[float]]:
    if version.startswith("2."):
        identifier_param = "coverageId"
    elif version.startswith("1.1"):
        identifier_param = "identifiers"
    else:
        identifier_param = "coverage"
    url = query_url(
        endpoint,
        {
            "service": "WCS",
            "version": version,
            "request": "DescribeCoverage",
            identifier_param: coverage_id,
        },
    )
    root = parse_xml(request_bytes(url), "WCS DescribeCoverage")
    exception_texts = descendant_texts(
        root,
        {"ExceptionText", "ServiceException"},
    )
    if exception_texts:
        raise RuntimeError(
            "WCS DescribeCoverage exception: " + " | ".join(exception_texts)
        )
    description = parse_describe_coverage(root)
    proven_resolution = validate_resolution(description)
    return url, description, proven_resolution


def direct_coverage_ids(wms_name: str | None) -> list[str]:
    """Return deterministic aliases worth probing even when WCS hides coverage."""
    values = [
        wms_name or "",
        (wms_name or "").split(":", 1)[-1],
        PREFERRED_WMS_LAYER,
        PREFERRED_WMS_LAYER.split(":", 1)[-1],
        TARGET_LAYER_LABEL,
    ]
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def probe_direct_wcs_descriptions(
    wms_name: str | None,
    endpoints: list[str],
) -> dict[str, Any]:
    """Try DescribeCoverage directly when GetCapabilities omits the WMS-backed store.

    Veneto's WMS DescribeLayer explicitly advertises the Cortina layer as WCS
    backed. GeoServer can still accept DescribeCoverage for a known coverage
    even when a capabilities document omits it, so this is a legitimate
    fail-closed transport probe rather than a WMS-image workaround.
    """
    attempts: list[dict[str, Any]] = []
    proven: list[dict[str, Any]] = []
    coverage_ids = direct_coverage_ids(wms_name)
    for endpoint in endpoints:
        endpoint_disabled = False
        for version in WCS_VERSIONS:
            if endpoint_disabled:
                break
            for coverage_id in coverage_ids:
                attempt: dict[str, Any] = {
                    "endpoint": endpoint,
                    "version": version,
                    "coverage_id": coverage_id,
                }
                try:
                    url, description, resolution = fetch_coverage_description(
                        endpoint,
                        version,
                        coverage_id,
                    )
                    attempt["describe_coverage_url"] = url
                    attempt["description"] = description
                    attempt["proven_native_resolution_m"] = resolution
                    attempt["status"] = "PROVEN"
                    proven.append(dict(attempt))
                except Exception as exc:
                    error = str(exc)
                    attempt["status"] = "FAILED"
                    attempt["error"] = error
                    if "service wcs is disabled" in error.lower():
                        attempt["terminal_endpoint_error"] = True
                        endpoint_disabled = True
                attempts.append(attempt)
                if endpoint_disabled:
                    break
    return {
        "coverage_ids": coverage_ids,
        "attempts": attempts,
        "proven": proven,
    }


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema_version": 1,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "Regione del Veneto",
        "target_dataset_label": TARGET_LAYER_LABEL,
        "preferred_raw_wms_layer": PREFERRED_WMS_LAYER,
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
        report["viewer"] = discover_viewer_context()
        report["portfolio"] = discover_portfolio_context()
        if not report["portfolio"]["mentions_resampled_2m"]:
            raise RuntimeError(
                "official Olympic portfolio no longer proves the 2 m rasters "
                "as provider-side resamples"
            )
        if not report["portfolio"]["links_olympic_viewer_86"]:
            raise RuntimeError(
                "official Olympic portfolio no longer links WebGIS 86"
            )
        report["download_portal"] = discover_download_portal()
        report["generic_download_catalog"] = discover_generic_downloadable_layers()
        report["csw_metadata"] = discover_csw_metadata()
        wms_url, layer = fetch_wms_layer()
        describe_layer_url, layer_descriptions = fetch_describe_layer()
        report["wms"] = {
            "get_capabilities_url": wms_url,
            "layer": layer,
            "describe_layer_url": describe_layer_url,
            "describe_layer": layer_descriptions,
        }

        endpoints = wcs_endpoint_candidates(layer_descriptions)
        discovery = discover_wcs_coverage(layer.get("name"), endpoints)
        report["wcs"] = discovery
        found = discovery.get("found", [])
        if len(found) > 1:
            raise RuntimeError(
                "expected at most one advertised WCS coverage matching Cortina "
                f"2 m across {len(endpoints)} endpoint(s), found {len(found)}"
            )

        if len(found) == 1:
            selected = found[0]
            coverage = selected["coverage"]
            coverage_id = str(coverage.get("identifier") or "").strip()
            if not coverage_id:
                raise RuntimeError("matched WCS coverage has no identifier")

            describe_url, description, resolution = fetch_coverage_description(
                str(selected["endpoint"]),
                str(selected["version"]),
                coverage_id,
            )
            report["wcs"]["selection_mode"] = "advertised_capabilities"
        else:
            direct = probe_direct_wcs_descriptions(layer.get("name"), endpoints)
            report["wcs"]["direct_describe"] = direct
            proven = direct.get("proven", [])
            if not proven:
                raise RuntimeError(
                    "WCS capabilities omit Cortina 2 m and direct "
                    "DescribeCoverage did not prove a 2 m raw coverage"
                )
            chosen = proven[0]
            coverage_id = str(chosen["coverage_id"])
            describe_url = str(chosen["describe_coverage_url"])
            description = chosen["description"]
            resolution = chosen["proven_native_resolution_m"]
            selected = {
                "endpoint": chosen["endpoint"],
                "version": chosen["version"],
                "coverage": {
                    "identifier": coverage_id,
                    "title": TARGET_LAYER_LABEL,
                },
            }
            report["wcs"]["selection_mode"] = "direct_describe_fallback"

        report["wcs"]["selected"] = selected
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
            f"coverage={report['wcs']['selected']['coverage'].get('identifier')} "
            f"resolution={report['proven_native_resolution_m']}"
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
