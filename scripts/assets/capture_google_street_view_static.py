#!/usr/bin/env python3
"""Capture one explicitly selected Google Street View Static API image."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ENDPOINT = "https://maps.googleapis.com/maps/api/streetview"
API_KEY_ENV = "GOOGLE_STREET_VIEW_API_KEY"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
PANO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


class CaptureError(RuntimeError):
    """A sanitized capture failure that never includes the URL or API key."""


def validate_request(
    pano_id: str,
    width: int,
    height: int,
    scale: int,
    heading: float,
    pitch: float,
    fov: float,
) -> None:
    if not PANO_ID_PATTERN.fullmatch(pano_id):
        raise CaptureError("panorama ID has an unsupported format")
    if not 1 <= width <= 640 or not 1 <= height <= 640:
        raise CaptureError("image dimensions must be between 1 and 640 pixels")
    if scale not in {1, 2}:
        raise CaptureError("image scale must be 1 or 2")
    if any(not math.isfinite(value) for value in (heading, pitch, fov)):
        raise CaptureError("view values must be finite numbers")
    if not 0.0 <= heading < 360.0:
        raise CaptureError("heading must be between 0 and 360 degrees")
    if not -90.0 <= pitch <= 90.0:
        raise CaptureError("pitch must be between -90 and 90 degrees")
    if not 10.0 <= fov <= 120.0:
        raise CaptureError("field of view must be between 10 and 120 degrees")


def request_image(
    *,
    pano_id: str,
    width: int,
    height: int,
    scale: int,
    heading: float,
    pitch: float,
    fov: float,
    api_key: str,
    opener: Callable = urlopen,
) -> bytes:
    if not api_key.strip():
        raise CaptureError(f"{API_KEY_ENV} is missing")
    query = urlencode(
        {
            "pano": pano_id,
            "size": f"{width}x{height}",
            "scale": str(scale),
            "heading": f"{heading:.3f}",
            "pitch": f"{pitch:.3f}",
            "fov": f"{fov:.3f}",
            "return_error_code": "true",
            "key": api_key,
        }
    )
    request = Request(
        f"{ENDPOINT}?{query}",
        headers={"User-Agent": "YACS-StreetView-Static-Capture/1"},
    )
    try:
        with opener(request, timeout=30) as response:
            content_type = response.headers.get("Content-Type", "")
            body = response.read(MAX_IMAGE_BYTES + 1)
    except HTTPError as exc:
        raise CaptureError(f"Google image request returned HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise CaptureError("Google image request failed before a response") from None
    if len(body) > MAX_IMAGE_BYTES:
        raise CaptureError("Google image response exceeded the size limit")
    if content_type.split(";", 1)[0].strip().lower() != "image/jpeg":
        raise CaptureError("Google image response was not JPEG")
    if not body.startswith(b"\xff\xd8\xff") or not body.endswith(b"\xff\xd9"):
        raise CaptureError("Google image response had invalid JPEG framing")
    return body


def write_atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def write_receipt(path: Path, receipt: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pano-id", required=True)
    parser.add_argument("--width", default=640, type=int)
    parser.add_argument("--height", default=640, type=int)
    parser.add_argument("--scale", default=2, type=int)
    parser.add_argument("--heading", required=True, type=float)
    parser.add_argument("--pitch", required=True, type=float)
    parser.add_argument("--fov", required=True, type=float)
    parser.add_argument("--output-image", required=True, type=Path)
    parser.add_argument("--output-receipt", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request_attempted = False
    request_parameters = {
        "pano_id": args.pano_id,
        "width": args.width,
        "height": args.height,
        "scale": args.scale,
        "heading": args.heading,
        "pitch": args.pitch,
        "fov": args.fov,
    }
    try:
        validate_request(**request_parameters)
        request_attempted = True
        image = request_image(
            **request_parameters,
            api_key=os.environ.get(API_KEY_ENV, ""),
        )
        write_atomic_bytes(args.output_image, image)
        receipt = {
            "schema_version": 1,
            "service": "google_street_view_static",
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "OK",
            "request": request_parameters,
            "billable_image_request_attempted": True,
            "image_pixels_requested": True,
            "request_count": 1,
            "metric_geometry_admitted": False,
            "image": {
                "file_name": args.output_image.name,
                "byte_count": len(image),
                "sha256": hashlib.sha256(image).hexdigest(),
            },
        }
        write_receipt(args.output_receipt, receipt)
        print(
            "STREET_VIEW_STATIC status=OK request_count=1 "
            f"bytes={len(image)} sha256={receipt['image']['sha256']}"
        )
        return 0
    except CaptureError as exc:
        write_receipt(
            args.output_receipt,
            {
                "schema_version": 1,
                "service": "google_street_view_static",
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "status": "CAPTURE_ERROR",
                "error": str(exc),
                "request": request_parameters,
                "billable_image_request_attempted": request_attempted,
                "image_pixels_requested": request_attempted,
                "request_count": 1 if request_attempted else 0,
                "metric_geometry_admitted": False,
            },
        )
        print(f"STREET_VIEW_STATIC error={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
