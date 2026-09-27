#!/usr/bin/env python3
"""Download a bounded Passo Giau DEM from the official TINITALY 1.1 WCS.

The raw GeoTIFF is written under ExternalAssets/, which is intentionally
ignored by Git. The downloader records provenance, license/citation data,
the exact WCS request and a SHA-256 checksum.

This script does not import or convert terrain into Unreal Engine and does
not make external terrain authoritative for YACS route or physics data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY_URL = "https://github.com/karnalooch/YetAnotherCyclingSim"

DATASET_NAME = "TINITALY 1.1"
PROVIDER = "Istituto Nazionale di Geofisica e Vulcanologia (INGV)"
SOURCE_HOME = "https://tinitaly.pi.ingv.it/"
WCS_ENDPOINT = "https://tinitaly.pi.ingv.it/TINItaly_1_1/wcs"
COVERAGE = "TINItaly_1_1:tinitaly_dem"
SOURCE_CRS = "EPSG:32632"
NATIVE_RESOLUTION_M = 10.0
LICENSE = "CC BY 4.0"
DOI = "https://doi.org/10.13127/tinitaly/1.1"
CITATION = (
    "Tarquini S., I. Isola, M. Favalli, A. Battistini, G. Dotta (2023). "
    "TINITALY, a digital elevation model of Italy with a 10 meters cell "
    "size (Version 1.1). Istituto Nazionale di Geofisica e Vulcanologia "
    "(INGV). https://doi.org/10.13127/tinitaly/1.1"
)

# Passo Giau is approximately 46.483 N, 12.054 E. These coordinates are
# the corresponding UTM WGS84 Zone 32N values used by the TINITALY WCS.
DEFAULT_CENTER_EASTING_M = 734_406.587
DEFAULT_CENTER_NORTHING_M = 5_152_246.775
DEFAULT_SIZE_KM = 8.0
DEFAULT_RESOLUTION_M = 10.0

CHUNK_SIZE = 1024 * 1024
MAX_PIXELS_PER_AXIS = 4096
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_ATTEMPTS = 3

USER_AGENT = (
    "YetAnotherCyclingSim-PassoGiauDEM/1.0 "
    f"(+{REPOSITORY_URL})"
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download a bounded Passo Giau terrain source from the official "
            "TINITALY 1.1 WCS."
        )
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=(
            repository_root()
            / "ExternalAssets"
            / "Terrain"
            / "PassoGiau"
            / "TINITALY_1_1"
        ),
        help="Ignored local source-data directory (default: %(default)s).",
    )
    parser.add_argument(
        "--size-km",
        type=float,
        default=DEFAULT_SIZE_KM,
        help="Square AOI width/height in kilometres (default: %(default)s).",
    )
    parser.add_argument(
        "--resolution-m",
        type=float,
        default=DEFAULT_RESOLUTION_M,
        help=(
            "Requested grid resolution in metres. Values below the native "
            "10 m dataset resolution are rejected (default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--center-easting",
        type=float,
        default=DEFAULT_CENTER_EASTING_M,
        help="AOI centre easting in EPSG:32632 (default: %(default)s).",
    )
    parser.add_argument(
        "--center-northing",
        type=float,
        default=DEFAULT_CENTER_NORTHING_M,
        help="AOI centre northing in EPSG:32632 (default: %(default)s).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="HTTP timeout in seconds (default: %(default)s).",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=DEFAULT_ATTEMPTS,
        help="Download attempts with exponential backoff (default: %(default)s).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the exact WCS request and planned output without downloading.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing cached GeoTIFF.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not (0.1 <= args.size_km <= 40.0):
        raise ValueError("--size-km must be between 0.1 and 40")
    if args.resolution_m < NATIVE_RESOLUTION_M:
        raise ValueError(
            f"--resolution-m must be >= {NATIVE_RESOLUTION_M:g}; "
            "requesting a finer grid would only upsample the source DEM"
        )
    if args.resolution_m > 1000.0:
        raise ValueError("--resolution-m must be <= 1000")
    if args.timeout <= 0:
        raise ValueError("--timeout must be > 0")
    if not (1 <= args.attempts <= 10):
        raise ValueError("--attempts must be between 1 and 10")


def build_request(
    *,
    center_easting_m: float,
    center_northing_m: float,
    size_km: float,
    resolution_m: float,
) -> tuple[str, dict[str, Any]]:
    size_m = size_km * 1000.0
    half_size_m = size_m / 2.0

    min_x = center_easting_m - half_size_m
    min_y = center_northing_m - half_size_m
    max_x = center_easting_m + half_size_m
    max_y = center_northing_m + half_size_m

    pixels = max(2, int(round(size_m / resolution_m)))
    if pixels > MAX_PIXELS_PER_AXIS:
        raise ValueError(
            f"Requested grid would be {pixels}x{pixels}; "
            f"maximum is {MAX_PIXELS_PER_AXIS}x{MAX_PIXELS_PER_AXIS}"
        )

    params = {
        "SERVICE": "WCS",
        "VERSION": "1.0.0",
        "REQUEST": "GetCoverage",
        "FORMAT": "GeoTIFF",
        "COVERAGE": COVERAGE,
        "BBOX": f"{min_x:.3f},{min_y:.3f},{max_x:.3f},{max_y:.3f}",
        "CRS": SOURCE_CRS,
        "RESPONSE_CRS": SOURCE_CRS,
        "WIDTH": str(pixels),
        "HEIGHT": str(pixels),
    }
    url = f"{WCS_ENDPOINT}?{urllib.parse.urlencode(params)}"
    request_metadata: dict[str, Any] = {
        "center": {
            "easting_m": center_easting_m,
            "northing_m": center_northing_m,
            "crs": SOURCE_CRS,
        },
        "bbox": {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
            "crs": SOURCE_CRS,
        },
        "size_km": size_km,
        "requested_resolution_m": resolution_m,
        "width_px": pixels,
        "height_px": pixels,
    }
    return url, request_metadata


def is_tiff(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 4:
        return False
    with path.open("rb") as handle:
        header = handle.read(4)
    return header in {
        b"II*\x00",  # little-endian TIFF
        b"MM\x00*",  # big-endian TIFF
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def response_preview(path: Path, limit: int = 500) -> str:
    try:
        raw = path.read_bytes()[:limit]
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return "<unable to read response preview>"


def download(url: str, destination: Path, timeout: int, attempts: int) -> None:
    temp_path = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/tiff,application/octet-stream,*/*",
        },
    )

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            print(f"[download] attempt {attempt}/{attempts}")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise RuntimeError(f"unexpected HTTP status {status}")
                with temp_path.open("wb") as output:
                    while True:
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        output.write(chunk)

            if temp_path.stat().st_size < 1024:
                raise RuntimeError(
                    "downloaded payload is unexpectedly small: "
                    f"{temp_path.stat().st_size} bytes"
                )
            if not is_tiff(temp_path):
                preview = response_preview(temp_path)
                raise RuntimeError(
                    "WCS response is not a TIFF; it may be an OGC service "
                    f"exception. Response preview: {preview!r}"
                )

            os.replace(temp_path, destination)
            return
        except (
            OSError,
            TimeoutError,
            urllib.error.HTTPError,
            urllib.error.URLError,
            RuntimeError,
        ) as exc:
            last_error = exc
            temp_path.unlink(missing_ok=True)
            if attempt < attempts:
                wait_seconds = 2 ** (attempt - 1)
                print(
                    f"[retry] {exc}; waiting {wait_seconds}s",
                    file=sys.stderr,
                )
                time.sleep(wait_seconds)

    raise RuntimeError(
        f"failed to download DEM after {attempts} attempts: {last_error}"
    )


def source_and_license_text() -> str:
    return "\n".join(
        [
            "YACS external terrain source",
            "",
            f"Dataset: {DATASET_NAME}",
            f"Provider: {PROVIDER}",
            f"Homepage: {SOURCE_HOME}",
            f"License: {LICENSE}",
            f"DOI: {DOI}",
            "",
            "Citation:",
            CITATION,
            "",
            "YACS policy:",
            "- raw source download stays under gitignored ExternalAssets/",
            "- imported terrain is presentation data only",
            "- imported terrain must not become authoritative route/physics geometry",
            "",
        ]
    ) + "\n"


def output_filename(size_km: float, resolution_m: float) -> str:
    size_token = f"{size_km:g}".replace(".", "p")
    resolution_token = f"{resolution_m:g}".replace(".", "p")
    return (
        "passo_giau_tinitaly_1_1_"
        f"{size_token}km_{resolution_token}m_epsg32632.tif"
    )


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
        url, request_metadata = build_request(
            center_easting_m=args.center_easting,
            center_northing_m=args.center_northing,
            size_km=args.size_km,
            resolution_m=args.resolution_m,
        )
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    destination_dir = args.destination.resolve()
    destination = destination_dir / output_filename(
        args.size_km,
        args.resolution_m,
    )
    index_path = destination_dir / "download-index.json"
    license_path = destination_dir / "SOURCE_AND_LICENSE.txt"

    print("Passo Giau DEM bootstrap")
    print(f"  dataset:      {DATASET_NAME}")
    print(f"  provider:     {PROVIDER}")
    print(f"  size:         {args.size_km:g} x {args.size_km:g} km")
    print(f"  resolution:   {args.resolution_m:g} m")
    print(
        "  grid:         "
        f"{request_metadata['width_px']} x "
        f"{request_metadata['height_px']}"
    )
    print(f"  CRS:          {SOURCE_CRS}")
    print(f"  output:       {destination}")
    print(f"  request:      {url}")

    if args.dry_run:
        print("[dry-run] no files written")
        return 0

    destination_dir.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not args.force:
        if not is_tiff(destination):
            print(
                "[error] cached file exists but is not a valid TIFF; "
                "use --force to replace it",
                file=sys.stderr,
            )
            return 3
        print("[cache] existing TIFF is valid; skipping download")
    else:
        try:
            download(
                url,
                destination,
                timeout=args.timeout,
                attempts=args.attempts,
            )
        except RuntimeError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 4

    file_size = destination.stat().st_size
    digest = sha256_file(destination)

    provenance = {
        "schema_version": 1,
        "asset": "Passo Giau DEM",
        "dataset": DATASET_NAME,
        "provider": PROVIDER,
        "license": LICENSE,
        "doi": DOI,
        "citation": CITATION,
        "source_home": SOURCE_HOME,
        "wcs_endpoint": WCS_ENDPOINT,
        "coverage": COVERAGE,
        "request_url": url,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "request": request_metadata,
        "output": {
            "file": destination.name,
            "bytes": file_size,
            "sha256": digest,
        },
        "yacs_policy": {
            "raw_source_committed_to_git": False,
            "authoritative_route_geometry": False,
            "authoritative_physics": False,
            "intended_use": (
                "Stage 3G R4.1 macro-terrain / visual-reference spike"
            ),
        },
    }
    index_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    license_path.write_text(source_and_license_text(), encoding="utf-8")

    print()
    print("[ok] DEM cache is ready")
    print(f"[ok] bytes:  {file_size}")
    print(f"[ok] sha256: {digest}")
    print(f"[ok] index:   {index_path}")
    print(f"[ok] license: {license_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
