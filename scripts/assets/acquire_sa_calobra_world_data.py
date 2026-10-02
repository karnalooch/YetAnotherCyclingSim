#!/usr/bin/env python3
"""Acquire bounded real-world source material for the active Sa Calobra working space.

Large source payloads are retained on the trusted self-hosted runner outside Git.
The script writes a small receipt/probe bundle for CI evidence.

It deliberately fails closed on source identity: CNIG file names and download URLs
must be discovered from provider responses; they are never synthesized from grid
coordinates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests


USER_AGENT = "YetAnotherCyclingSim/WorldDataStack-Issue335 (+https://github.com/karnalooch/YetAnotherCyclingSim)"
TIMEOUT = 90
RETRIES = 4


class FormInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.current_select: dict[str, Any] | None = None
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {k: (v or "") for k, v in attrs}
        if tag == "form":
            self.current = {
                "action": data.get("action", ""),
                "method": data.get("method", "GET").upper(),
                "fields": [],
            }
            self.forms.append(self.current)
        elif tag == "input" and self.current is not None:
            self.current["fields"].append(
                {
                    "tag": "input",
                    "name": data.get("name", ""),
                    "type": data.get("type", "text"),
                    "value": data.get("value", ""),
                }
            )
        elif tag == "select" and self.current is not None:
            self.current_select = {
                "tag": "select",
                "name": data.get("name", ""),
                "options": [],
            }
            self.current["fields"].append(self.current_select)
        elif tag == "option" and self.current_select is not None:
            self.current_select["options"].append(
                {"value": data.get("value", ""), "selected": "selected" in data}
            )
        elif tag == "a":
            href = data.get("href", "")
            if href:
                self.links.append({"href": href, "text": ""})

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self.current = None
        elif tag == "select":
            self.current_select = None

    def handle_data(self, data: str) -> None:
        if self.links and data.strip():
            self.links[-1]["text"] += data.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--persistent-root", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    return s


def request_with_retry(s: requests.Session, method: str, url: str, **kwargs: Any) -> requests.Response:
    last: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            response = s.request(method, url, timeout=TIMEOUT, allow_redirects=True, **kwargs)
            response.raise_for_status()
            return response
        except Exception as exc:  # noqa: BLE001 - evidence collector records provider failures
            last = exc
            if attempt == RETRIES:
                break
            time.sleep(min(2**attempt, 10))
    raise RuntimeError(f"{method} {url} failed after {RETRIES} attempts: {last}")


def write_bytes(path: Path, data: bytes, force: bool) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "reused": True,
        }
    path.write_bytes(data)
    return {
        "path": str(path),
        "size_bytes": len(data),
        "sha256": sha256(path),
        "reused": False,
    }


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def response_record(response: requests.Response) -> dict[str, Any]:
    return {
        "url": response.url,
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "content_length_header": response.headers.get("content-length"),
        "etag": response.headers.get("etag"),
        "last_modified": response.headers.get("last-modified"),
    }


def source_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {source["id"]: source for source in manifest["sources"]}


def acquire_ortho(
    s: requests.Session,
    source: dict[str, Any],
    bounds: list[float],
    root: Path,
    force: bool,
) -> dict[str, Any]:
    out = root / "pnoa_ortho_2024"
    service = source["service_url"]
    caps = request_with_retry(
        s,
        "GET",
        service,
        params={"SERVICE": "WMS", "REQUEST": "GetCapabilities", "VERSION": "1.3.0"},
    )
    cap_file = write_bytes(out / "GetCapabilities.xml", caps.content, force)

    # Current service metadata documents <=2000 px wide / <=1700 px high.
    # A 5x5 grid keeps the ~0.25 m request close to native Baleares PNOA GSD.
    min_e, min_n, max_e, max_n = map(float, bounds)
    cols = rows = 5
    tiles: list[dict[str, Any]] = []
    for row in range(rows):
        y0 = min_n + (max_n - min_n) * row / rows
        y1 = min_n + (max_n - min_n) * (row + 1) / rows
        for col in range(cols):
            x0 = min_e + (max_e - min_e) * col / cols
            x1 = min_e + (max_e - min_e) * (col + 1) / cols
            width = min(2000, max(50, math.ceil((x1 - x0) / 0.25)))
            height = min(1700, max(50, math.ceil((y1 - y0) / 0.25)))
            params = {
                "SERVICE": "WMS",
                "VERSION": "1.3.0",
                "REQUEST": "GetMap",
                "LAYERS": "OI.OrthoimageCoverage",
                "STYLES": "",
                "CRS": "EPSG:25831",
                "BBOX": f"{x0},{y0},{x1},{y1}",
                "WIDTH": str(width),
                "HEIGHT": str(height),
                "FORMAT": "image/jpeg",
                "TRANSPARENT": "false",
            }
            response = request_with_retry(s, "GET", service, params=params)
            content_type = (response.headers.get("content-type") or "").lower()
            if "image" not in content_type:
                raise RuntimeError(
                    f"PNOA WMS tile r{row}c{col} returned {content_type}: "
                    + response.text[:300]
                )
            path = out / f"r{row:02d}_c{col:02d}.jpg"
            file_rec = write_bytes(path, response.content, force)
            tiles.append(
                {
                    **file_rec,
                    "bbox_epsg25831": [x0, y0, x1, y1],
                    "request_size_px": [width, height],
                    "request_pixel_size_m": [(x1 - x0) / width, (y1 - y0) / height],
                    "http": response_record(response),
                }
            )
    manifest_path = out / "tiles.json"
    write_text(
        manifest_path,
        json.dumps(
            {
                "source": source["product"],
                "service": service,
                "layer": "OI.OrthoimageCoverage",
                "aoi_bounds_epsg25831": bounds,
                "note": "WMS service extract for World Data Stack. Request pixel spacing is not a native-source accuracy claim.",
                "capabilities": cap_file,
                "tiles": tiles,
            },
            indent=2,
        )
        + "\n",
    )
    return {"status": "downloaded", "tile_count": len(tiles), "manifest": str(manifest_path)}


def lonlat_to_tile(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    lat = max(min(lat, 85.05112878), -85.05112878)
    n = 2**zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def acquire_btn(
    s: requests.Session,
    source: dict[str, Any],
    corners: dict[str, list[float]],
    root: Path,
    force: bool,
) -> dict[str, Any]:
    out = root / "btn_vector_tiles"
    zoom = int(source["service_zoom"])
    lons = [float(v[0]) for v in corners.values()]
    lats = [float(v[1]) for v in corners.values()]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    x0, y_south = lonlat_to_tile(min_lon, min_lat, zoom)
    x1, y_north = lonlat_to_tile(max_lon, max_lat, zoom)
    template = source["service_template"]
    records = []
    for y in range(y_north, y_south + 1):
        for x in range(x0, x1 + 1):
            url = template.format(z=zoom, x=x, y=y)
            response = request_with_retry(s, "GET", url)
            rec = write_bytes(out / str(zoom) / str(x) / f"{y}.pbf", response.content, force)
            records.append({**rec, "z": zoom, "x": x, "y": y, "http": response_record(response)})
    manifest_path = out / "tiles.json"
    write_text(
        manifest_path,
        json.dumps(
            {
                "source": source["product"],
                "service_template": template,
                "zoom": zoom,
                "wgs84_bbox_lon_lat": [min_lon, min_lat, max_lon, max_lat],
                "tiles": records,
            },
            indent=2,
        )
        + "\n",
    )
    return {"status": "downloaded", "tile_count": len(records), "manifest": str(manifest_path)}


def xml_feature_type_names(xml_text: str) -> list[str]:
    return sorted(
        set(
            match.group(1).strip()
            for match in re.finditer(
                r"<(?:\\w+:)?Name>\\s*([^<]+?)\\s*</(?:\\w+:)?Name>",
                xml_text,
                flags=re.IGNORECASE,
            )
        )
    )


def acquire_siose(
    s: requests.Session,
    source: dict[str, Any],
    corners: dict[str, list[float]],
    root: Path,
    force: bool,
) -> dict[str, Any]:
    out = root / "siose_2014"
    service = source["service_url"]
    caps = request_with_retry(
        s,
        "GET",
        service,
        params={"SERVICE": "WFS", "REQUEST": "GetCapabilities", "VERSION": "2.0.0"},
    )
    cap_path = out / "GetCapabilities.xml"
    cap_rec = write_bytes(cap_path, caps.content, force)
    names = xml_feature_type_names(caps.text)
    land_names = [name for name in names if "landcover" in name.lower() or "land_cover" in name.lower()]
    if not land_names:
        # Preserve capabilities and fail closed rather than guessing a typename.
        return {
            "status": "capabilities_only",
            "capabilities": cap_rec,
            "feature_type_names": names,
            "reason": "No LandCover typename discovered automatically",
        }

    lons = [float(v[0]) for v in corners.values()]
    lats = [float(v[1]) for v in corners.values()]
    bbox = [min(lons), min(lats), max(lons), max(lats)]
    downloads = []
    for name in land_names:
        params = {
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "REQUEST": "GetFeature",
            "TYPENAMES": name,
            "SRSNAME": "EPSG:4258",
            "BBOX": ",".join(map(str, bbox)) + ",EPSG:4258",
            "COUNT": "10000",
        }
        response = request_with_retry(s, "GET", service, params=params)
        if "exception" in response.text[:2000].lower():
            # Axis-order fallback for strict ETRS89 geographic services.
            swapped = [bbox[1], bbox[0], bbox[3], bbox[2]]
            params["BBOX"] = ",".join(map(str, swapped)) + ",EPSG:4258"
            response = request_with_retry(s, "GET", service, params=params)
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
        rec = write_bytes(out / f"{safe}.gml", response.content, force)
        downloads.append({**rec, "typename": name, "http": response_record(response)})
    manifest_path = out / "extract.json"
    write_text(
        manifest_path,
        json.dumps(
            {
                "source": source["product"],
                "capabilities": cap_rec,
                "feature_types": land_names,
                "bbox_epsg4258": bbox,
                "files": downloads,
            },
            indent=2,
        )
        + "\n",
    )
    return {"status": "downloaded", "files": len(downloads), "manifest": str(manifest_path)}


def split_bbox(bounds: list[float], nx: int, ny: int) -> list[list[float]]:
    min_x, min_y, max_x, max_y = map(float, bounds)
    result = []
    for iy in range(ny):
        y0 = min_y + (max_y - min_y) * iy / ny
        y1 = min_y + (max_y - min_y) * (iy + 1) / ny
        for ix in range(nx):
            x0 = min_x + (max_x - min_x) * ix / nx
            x1 = min_x + (max_x - min_x) * (ix + 1) / nx
            result.append([x0, y0, x1, y1])
    return result


def acquire_catastro(
    s: requests.Session,
    source: dict[str, Any],
    bounds: list[float],
    root: Path,
    force: bool,
) -> dict[str, Any]:
    out = root / "catastro_buildings"
    service = source["service_url"]
    caps = request_with_retry(
        s,
        "GET",
        service,
        params={"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"},
    )
    cap_rec = write_bytes(out / "GetCapabilities.xml", caps.content, force)
    feature_types = ["BU.BUILDING", "BU.BUILDINGPART", "BU.OTHERCONSTRUCTION"]
    # The service limits BBOX queries to 4 km2. Four subqueries keep us comfortably below.
    quadrants = split_bbox(bounds, 2, 2)
    files = []
    for qi, bbox in enumerate(quadrants):
        for typename in feature_types:
            response = request_with_retry(
                s,
                "GET",
                service,
                params={
                    "service": "wfs",
                    "version": "2.0.0",
                    "request": "getfeature",
                    "typenames": typename,
                    "bbox": ",".join(map(str, bbox)),
                    "srsname": "EPSG::25831",
                },
            )
            safe = typename.replace(".", "_")
            rec = write_bytes(out / f"q{qi}_{safe}.gml", response.content, force)
            files.append(
                {
                    **rec,
                    "quadrant": qi,
                    "bbox_epsg25831": bbox,
                    "typename": typename,
                    "http": response_record(response),
                }
            )
    manifest_path = out / "extract.json"
    write_text(
        manifest_path,
        json.dumps(
            {
                "source": source["product"],
                "capabilities": cap_rec,
                "files": files,
            },
            indent=2,
        )
        + "\n",
    )
    return {"status": "downloaded", "files": len(files), "manifest": str(manifest_path)}


def parse_forms(html: str) -> dict[str, Any]:
    parser = FormInspector()
    parser.feed(html)
    return {"forms": parser.forms, "links": parser.links}


def field_default(field: dict[str, Any]) -> str:
    if field["tag"] == "input":
        return str(field.get("value", ""))
    options = field.get("options", [])
    selected = [opt["value"] for opt in options if opt.get("selected")]
    return str((selected or [opt["value"] for opt in options if opt.get("value")] or [""])[0])


def choose_search_form(forms: list[dict[str, Any]]) -> dict[str, Any] | None:
    scored = []
    for form in forms:
        names = " ".join(str(field.get("name", "")).lower() for field in form["fields"])
        score = sum(token in names for token in ("huso", "coord", ".x", ".y", "utm"))
        if score:
            scored.append((score, form))
    return max(scored, key=lambda pair: pair[0])[1] if scored else None


def set_by_name_hint(payload: dict[str, str], fields: list[dict[str, Any]], hints: tuple[str, ...], value: str) -> bool:
    candidates = []
    for field in fields:
        name = str(field.get("name", ""))
        low = name.lower()
        if name and any(hint in low for hint in hints):
            candidates.append(name)
    if not candidates:
        return False
    # Prefer the shortest matching field name; old Spring forms often use filtro.x / filtro.y.
    payload[sorted(candidates, key=len)[0]] = value
    return True


def extract_candidate_files(html: str, extension_pattern: str) -> list[dict[str, str]]:
    parser = FormInspector()
    parser.feed(html)
    filename_re = re.compile(rf"([A-Za-z0-9_.-]+\\.(?:{extension_pattern}))", re.IGNORECASE)
    found: dict[str, dict[str, str]] = {}
    for match in filename_re.finditer(html):
        name = match.group(1)
        found.setdefault(name.lower(), {"name": name, "detail_url": ""})
    for link in parser.links:
        text = link.get("text", "")
        href = link.get("href", "")
        match = filename_re.search(text + " " + href)
        if match:
            name = match.group(1)
            found.setdefault(name.lower(), {"name": name, "detail_url": ""})
            found[name.lower()]["detail_url"] = href
        if "detallearchivo" in href.lower():
            nearby = filename_re.search(text)
            if nearby:
                found.setdefault(nearby.group(1).lower(), {"name": nearby.group(1), "detail_url": href})
                found[nearby.group(1).lower()]["detail_url"] = href
    return list(found.values())


def direct_download_links(base_url: str, html: str, filename: str) -> list[str]:
    parser = FormInspector()
    parser.feed(html)
    candidates = []
    for link in parser.links:
        href = link["href"]
        low = href.lower()
        if filename.lower() in low or any(token in low for token in ("descarg", "download")):
            candidates.append(urljoin(base_url, href))
    # De-duplicate while preserving order.
    return list(dict.fromkeys(candidates))


def submit_cnig_search(
    s: requests.Session,
    product_url: str,
    easting: float,
    northing: float,
    evidence_dir: Path,
    label: str,
) -> tuple[requests.Response | None, dict[str, Any]]:
    page = request_with_retry(s, "GET", product_url)
    info = parse_forms(page.text)
    write_text(evidence_dir / f"{label}_landing.html", page.text)
    form = choose_search_form(info["forms"])
    summary: dict[str, Any] = {
        "landing": response_record(page),
        "forms": info["forms"],
        "search_attempted": False,
    }
    if form is None:
        return None, summary

    payload = {
        field["name"]: field_default(field)
        for field in form["fields"]
        if field.get("name")
    }
    set_by_name_hint(payload, form["fields"], ("checkcoord",), "S")
    set_by_name_hint(payload, form["fields"], ("huso", "zone"), "31")
    x_set = set_by_name_hint(payload, form["fields"], (".x", "_x", "coordx", "coordenadax", "easting"), f"{easting:.3f}")
    y_set = set_by_name_hint(payload, form["fields"], (".y", "_y", "coordy", "coordenaday", "northing"), f"{northing:.3f}")

    # Fall back to exact terminal field names "x" / "y" when heuristics did not match.
    if not x_set:
        for field in form["fields"]:
            if str(field.get("name", "")).lower().split(".")[-1] == "x":
                payload[field["name"]] = f"{easting:.3f}"
                x_set = True
                break
    if not y_set:
        for field in form["fields"]:
            if str(field.get("name", "")).lower().split(".")[-1] == "y":
                payload[field["name"]] = f"{northing:.3f}"
                y_set = True
                break

    summary["payload_field_names"] = sorted(payload)
    summary["coordinate_fields_found"] = {"x": x_set, "y": y_set}
    if not (x_set and y_set):
        return None, summary

    action = urljoin(page.url, form.get("action") or page.url)
    method = form.get("method", "GET").upper()
    response = request_with_retry(
        s,
        method,
        action,
        params=payload if method == "GET" else None,
        data=payload if method != "GET" else None,
    )
    summary["search_attempted"] = True
    summary["search"] = response_record(response)
    write_text(evidence_dir / f"{label}_search.html", response.text)
    return response, summary


def acquire_cnig_product(
    s: requests.Session,
    source: dict[str, Any],
    query_points: list[tuple[float, float, str]],
    extension_pattern: str,
    required_filename_token: str | None,
    root: Path,
    receipt_root: Path,
    force: bool,
) -> dict[str, Any]:
    product_url = source["product_url"]
    evidence_dir = receipt_root / "cnig_probe" / source["id"]
    raw_dir = root / source["id"]
    all_files: dict[str, dict[str, str]] = {}
    probes = []
    for easting, northing, label in query_points:
        response, summary = submit_cnig_search(
            s, product_url, easting, northing, evidence_dir, label
        )
        probes.append({"point": [easting, northing], "label": label, **summary})
        if response is None:
            continue
        for candidate in extract_candidate_files(response.text, extension_pattern):
            name = candidate["name"]
            if required_filename_token and required_filename_token.lower() not in name.lower():
                continue
            detail = candidate.get("detail_url", "")
            if detail:
                detail = urljoin(response.url, detail)
            all_files.setdefault(name.lower(), {"name": name, "detail_url": detail})

    downloaded = []
    unresolved = []
    for candidate in all_files.values():
        name = candidate["name"]
        detail_url = candidate.get("detail_url")
        if not detail_url:
            unresolved.append({**candidate, "reason": "No detail URL found in search response"})
            continue
        detail = request_with_retry(s, "GET", detail_url)
        write_text(evidence_dir / f"detail_{re.sub(r'[^A-Za-z0-9_.-]+', '_', name)}.html", detail.text)
        links = direct_download_links(detail.url, detail.text, name)
        if not links:
            unresolved.append({**candidate, "detail_url": detail.url, "reason": "No direct download link discovered"})
            continue
        success = None
        errors = []
        for link in links:
            try:
                response = request_with_retry(s, "GET", link)
                content_type = (response.headers.get("content-type") or "").lower()
                if "text/html" in content_type and len(response.content) < 2_000_000:
                    errors.append({"url": link, "reason": f"HTML response {content_type}"})
                    continue
                success = (link, response)
                break
            except Exception as exc:  # noqa: BLE001
                errors.append({"url": link, "reason": str(exc)})
        if success is None:
            unresolved.append({**candidate, "detail_url": detail.url, "download_attempts": errors})
            continue
        link, response = success
        rec = write_bytes(raw_dir / name, response.content, force)
        downloaded.append(
            {
                **rec,
                "name": name,
                "detail_url": detail.url,
                "download_url": response.url,
                "http": response_record(response),
            }
        )

    return {
        "status": "downloaded" if downloaded and not unresolved else "partial",
        "product_url": product_url,
        "discovered_file_count": len(all_files),
        "downloaded_files": downloaded,
        "unresolved_files": unresolved,
        "probes": probes,
    }


def main() -> None:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 2:
        raise SystemExit("Acquisition requires working-space manifest schema_version 2")

    persistent_root = args.persistent_root.resolve()
    receipt_root = args.receipt_out.resolve()
    persistent_root.mkdir(parents=True, exist_ok=True)
    receipt_root.mkdir(parents=True, exist_ok=True)

    aoi = manifest["aoi"]
    bounds = [float(v) for v in aoi["bounds_m"]]
    corners = aoi["wgs84_corners_lon_lat"]
    sources = source_map(manifest)
    s = session()

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "issue": manifest["issue"],
        "exact_sha": os.environ.get("GITHUB_SHA"),
        "aoi": aoi,
        "persistent_root": str(persistent_root),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256(manifest_path),
        "sources": {},
    }

    def run(name: str, fn: Any) -> None:
        print(f"::group::{name}", flush=True)
        try:
            result = fn()
            receipt["sources"][name] = result
            print(json.dumps(result, indent=2), flush=True)
        except Exception as exc:  # noqa: BLE001
            result = {"status": "failed", "error": str(exc)}
            receipt["sources"][name] = result
            print(json.dumps(result, indent=2), flush=True)
        finally:
            print("::endgroup::", flush=True)

    run(
        "pnoa_maxima_actualidad_2024",
        lambda: acquire_ortho(
            s, sources["pnoa_maxima_actualidad_2024"], bounds, persistent_root, args.force
        ),
    )
    run(
        "btn_vector_context",
        lambda: acquire_btn(
            s, sources["btn_vector_context"], corners, persistent_root, args.force
        ),
    )
    run(
        "siose_2014_wfs",
        lambda: acquire_siose(
            s, sources["siose_2014_wfs"], corners, persistent_root, args.force
        ),
    )
    run(
        "catastro_buildings_wfs",
        lambda: acquire_catastro(
            s, sources["catastro_buildings_wfs"], bounds, persistent_root, args.force
        ),
    )

    # LiDAR queries use the nine exact 1 km cells intersecting the current AOI.
    lidar_points = []
    for locator in manifest["selection"]["lidar_grid_locator_hints"]:
        e_km, n_km = [int(part) for part in locator.split("-")]
        lidar_points.append((e_km * 1000 + 500.0, n_km * 1000 + 500.0, locator))
    run(
        "pnoa_lidar_cob3_npc03",
        lambda: acquire_cnig_product(
            s,
            sources["pnoa_lidar_cob3_npc03"],
            lidar_points,
            r"LAZ",
            "NPC03",
            persistent_root,
            receipt_root,
            args.force,
        ),
    )

    # MDS/ortho CNIG downloads use center + corners + edge-midpoints to discover every
    # provider sheet intersecting this 2.0165 km square without guessing sheet names.
    min_e, min_n, max_e, max_n = bounds
    cnig_points = [
        ((min_e + max_e) / 2, (min_n + max_n) / 2, "center"),
        (min_e + 1.0, min_n + 1.0, "sw"),
        (max_e - 1.0, min_n + 1.0, "se"),
        (max_e - 1.0, max_n - 1.0, "ne"),
        (min_e + 1.0, max_n - 1.0, "nw"),
        ((min_e + max_e) / 2, min_n + 1.0, "south"),
        (max_e - 1.0, (min_n + max_n) / 2, "east"),
        ((min_e + max_e) / 2, max_n - 1.0, "north"),
        (min_e + 1.0, (min_n + max_n) / 2, "west"),
    ]
    run(
        "mds50cm_cob3_v1",
        lambda: acquire_cnig_product(
            s,
            sources["mds50cm_cob3_v1"],
            cnig_points,
            r"TIF|TIFF",
            "MDS50CM",
            persistent_root,
            receipt_root,
            args.force,
        ),
    )

    receipt_path = receipt_root / "world-data-acquisition-receipt.json"
    write_text(receipt_path, json.dumps(receipt, indent=2) + "\n")
    print(f"Receipt: {receipt_path}", flush=True)

    failed = [name for name, value in receipt["sources"].items() if value["status"] == "failed"]
    partial = [name for name, value in receipt["sources"].items() if value["status"] in {"partial", "capabilities_only"}]
    print(f"Failed sources: {failed}", flush=True)
    print(f"Partial sources: {partial}", flush=True)

    # External-source acquisition is an evidence operation: complete service failures are
    # fatal, while CNIG portal discovery can remain partial with preserved probe evidence.
    if failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
