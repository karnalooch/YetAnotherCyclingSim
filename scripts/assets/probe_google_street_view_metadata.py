#!/usr/bin/env python3
"""Query one Google Street View metadata point without requesting image pixels."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ENDPOINT = "https://maps.googleapis.com/maps/api/streetview/metadata"
API_KEY_ENV = "GOOGLE_STREET_VIEW_API_KEY"
MAX_RESPONSE_BYTES = 64 * 1024
ALLOWED_SOURCES = {"default", "outdoor"}


class ProbeError(RuntimeError):
    """A sanitized probe failure that never includes the request URL or API key."""


def haversine_m(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    radius_m = 6_371_008.8
    lat1, lat2 = math.radians(a_lat), math.radians(b_lat)
    d_lat = lat2 - lat1
    d_lon = math.radians(b_lon - a_lon)
    value = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2.0) ** 2
    )
    return 2.0 * radius_m * math.asin(min(1.0, math.sqrt(value)))


def validate_request(
    latitude: float,
    longitude: float,
    radius_m: int,
    max_snap_m: float,
    source: str,
) -> None:
    values = (latitude, longitude, float(radius_m), max_snap_m)
    if any(isinstance(value, bool) or not math.isfinite(value) for value in values):
        raise ProbeError("request values must be finite numbers")
    if not -90.0 <= latitude <= 90.0:
        raise ProbeError("latitude must be between -90 and 90")
    if not -180.0 <= longitude <= 180.0:
        raise ProbeError("longitude must be between -180 and 180")
    if not 1 <= radius_m <= 50:
        raise ProbeError("radius must be between 1 and 50 metres")
    if not 0.0 <= max_snap_m <= float(radius_m):
        raise ProbeError("maximum snap distance must be within the search radius")
    if source not in ALLOWED_SOURCES:
        raise ProbeError("unsupported Street View source filter")


def request_metadata(
    *,
    latitude: float,
    longitude: float,
    radius_m: int,
    source: str,
    api_key: str,
    opener: Callable = urlopen,
) -> dict:
    if not api_key.strip():
        raise ProbeError(f"{API_KEY_ENV} is missing")
    query = urlencode(
        {
            "location": f"{latitude:.8f},{longitude:.8f}",
            "radius": str(radius_m),
            "source": source,
            "key": api_key,
        }
    )
    request = Request(
        f"{ENDPOINT}?{query}",
        headers={"User-Agent": "YACS-StreetView-Metadata-Probe/1"},
    )
    try:
        with opener(request, timeout=20) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise ProbeError(f"Google metadata request returned HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise ProbeError("Google metadata request failed before a response") from None
    if len(body) > MAX_RESPONSE_BYTES:
        raise ProbeError("Google metadata response exceeded the size limit")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise ProbeError("Google metadata response was not valid UTF-8 JSON") from None
    if not isinstance(payload, dict):
        raise ProbeError("Google metadata response must be an object")
    return payload


def sanitize_metadata(
    payload: dict,
    *,
    latitude: float,
    longitude: float,
    radius_m: int,
    max_snap_m: float,
    source: str,
) -> dict:
    status = payload.get("status")
    if not isinstance(status, str) or not status:
        raise ProbeError("Google metadata response omitted status")
    receipt = {
        "schema_version": 1,
        "service": "google_street_view_metadata",
        "queried_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "request": {
            "latitude": latitude,
            "longitude": longitude,
            "radius_m": radius_m,
            "max_snap_m": max_snap_m,
            "source": source,
        },
        "image_pixels_requested": False,
        "metric_geometry_admitted": False,
    }
    if status != "OK":
        receipt["panorama"] = None
        return receipt

    location = payload.get("location")
    pano_id = payload.get("pano_id")
    if not isinstance(location, dict) or not isinstance(pano_id, str) or not pano_id:
        raise ProbeError("successful Google metadata response omitted panorama data")
    pano_lat = location.get("lat")
    pano_lon = location.get("lng")
    if (
        isinstance(pano_lat, bool)
        or isinstance(pano_lon, bool)
        or not isinstance(pano_lat, (int, float))
        or not isinstance(pano_lon, (int, float))
        or not math.isfinite(float(pano_lat))
        or not math.isfinite(float(pano_lon))
    ):
        raise ProbeError("successful Google metadata response had invalid coordinates")
    snap_distance_m = haversine_m(
        latitude, longitude, float(pano_lat), float(pano_lon)
    )
    date = payload.get("date")
    receipt["panorama"] = {
        "pano_id": pano_id,
        "latitude": float(pano_lat),
        "longitude": float(pano_lon),
        "date": date if isinstance(date, str) else None,
        "snap_distance_m": round(snap_distance_m, 3),
        "within_max_snap_m": snap_distance_m <= max_snap_m,
    }
    return receipt


def write_receipt(path: Path, receipt: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latitude", required=True, type=float)
    parser.add_argument("--longitude", required=True, type=float)
    parser.add_argument("--radius-m", default=20, type=int)
    parser.add_argument("--max-snap-m", default=20.0, type=float)
    parser.add_argument("--source", choices=sorted(ALLOWED_SOURCES), default="outdoor")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        validate_request(
            args.latitude,
            args.longitude,
            args.radius_m,
            args.max_snap_m,
            args.source,
        )
        payload = request_metadata(
            latitude=args.latitude,
            longitude=args.longitude,
            radius_m=args.radius_m,
            source=args.source,
            api_key=os.environ.get(API_KEY_ENV, ""),
        )
        receipt = sanitize_metadata(
            payload,
            latitude=args.latitude,
            longitude=args.longitude,
            radius_m=args.radius_m,
            max_snap_m=args.max_snap_m,
            source=args.source,
        )
        write_receipt(args.output, receipt)
        panorama = receipt.get("panorama")
        if receipt["status"] != "OK":
            print(f"STREET_VIEW_METADATA status={receipt['status']}", file=sys.stderr)
            return 2
        print(
            "STREET_VIEW_METADATA "
            f"status=OK pano_id={panorama['pano_id']} "
            f"date={panorama['date']} "
            f"snap_distance_m={panorama['snap_distance_m']:.3f}"
        )
        if not panorama["within_max_snap_m"]:
            print(
                "Street View panorama exceeded the maximum snap distance",
                file=sys.stderr,
            )
            return 3
        return 0
    except ProbeError as exc:
        write_receipt(
            args.output,
            {
                "schema_version": 1,
                "service": "google_street_view_metadata",
                "queried_at_utc": datetime.now(timezone.utc).isoformat(),
                "status": "PROBE_ERROR",
                "error": str(exc),
                "image_pixels_requested": False,
                "metric_geometry_admitted": False,
            },
        )
        print(f"STREET_VIEW_METADATA error={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
