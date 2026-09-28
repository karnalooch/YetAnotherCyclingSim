#!/usr/bin/env python3
"""Fetch the immutable MASE PST Passo Giau LiDAR DTM 1x1 source checkpoint.

The authoring lane downloads the captured GitHub Release asset instead of
depending on the live MASE service. The release asset is pinned by byte size and
SHA-256. External terrain data is presentation-only and must never become
authoritative YACS route or physics geometry.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

RELEASE_TAG = "data-mase-pst-passo-giau-dtm-2026-09-28"
ARCHIVE_NAME = "MASE_PST_7eea00c532f94df29dd81e17e6bc8fed_1372707.zip"
ARCHIVE_URL = (
    "https://github.com/karnalooch/YetAnotherCyclingSim/releases/download/"
    f"{RELEASE_TAG}/{ARCHIVE_NAME}"
)
RELEASE_PAGE = (
    "https://github.com/karnalooch/YetAnotherCyclingSim/releases/tag/"
    f"{RELEASE_TAG}"
)
ARCHIVE_BYTES = 356_503_497
ARCHIVE_SHA256 = "0e2a133fcc80f225aee2b61aa04bc7a858aa3754c6b80a7c640b8a6ab7d14b8c"
EXPECTED_TILE_COUNT = 89
EXPECTED_CENTRAL_TILE = "areadolomitica_145_D46481205_0101_DTM.tiff"
SOURCE_CRS = "EPSG:4326"
SOURCE_PIXEL_SIZE_DEG = 0.00001
NODATA = -9999.0
LICENSE = "CC BY 4.0"
CHUNK_BYTES = 1024 * 1024
USER_AGENT = (
    "YetAnotherCyclingSim-MASE-PST-Release-Downloader/1.0 "
    "(+https://github.com/karnalooch/YetAnotherCyclingSim)"
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def output_root() -> Path:
    return (
        repository_root()
        / "ExternalAssets"
        / "Terrain"
        / "PassoGiau"
        / "MASE_PST_Lidar1x1"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_archive(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"source archive is missing: {path}")
    size = path.stat().st_size
    if size != ARCHIVE_BYTES:
        raise RuntimeError(
            f"source archive byte size mismatch: expected {ARCHIVE_BYTES}, got {size}"
        )
    digest = sha256_file(path)
    if digest != ARCHIVE_SHA256:
        raise RuntimeError(
            f"source archive SHA-256 mismatch: expected {ARCHIVE_SHA256}, got {digest}"
        )


def download_archive(path: Path) -> None:
    if path.is_file():
        try:
            validate_archive(path)
            print(f"[reuse] verified immutable source archive: {path.name}")
            return
        except Exception:
            path.unlink(missing_ok=True)

    temp = path.with_suffix(path.suffix + ".part")
    temp.unlink(missing_ok=True)
    request = urllib.request.Request(
        ARCHIVE_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/zip,*/*"},
    )

    digest = hashlib.sha256()
    written = 0
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temp.open("wb") as out:
            while True:
                chunk = response.read(CHUNK_BYTES)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                written += len(chunk)
                if written > ARCHIVE_BYTES:
                    raise RuntimeError(
                        f"download exceeded expected {ARCHIVE_BYTES} bytes"
                    )

        if written != ARCHIVE_BYTES:
            raise RuntimeError(
                f"download byte size mismatch: expected {ARCHIVE_BYTES}, got {written}"
            )
        actual_sha = digest.hexdigest()
        if actual_sha != ARCHIVE_SHA256:
            raise RuntimeError(
                f"download SHA-256 mismatch: expected {ARCHIVE_SHA256}, got {actual_sha}"
            )
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)

    validate_archive(path)


def copy_and_hash(source: BinaryIO, destination: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    written = 0
    with destination.open("wb") as out:
        while True:
            chunk = source.read(CHUNK_BYTES)
            if not chunk:
                break
            out.write(chunk)
            digest.update(chunk)
            written += len(chunk)
    return written, digest.hexdigest()


def extract_tiles(archive_path: Path, tile_dir: Path) -> list[dict[str, object]]:
    tile_dir.mkdir(parents=True, exist_ok=True)
    for stale in list(tile_dir.glob("*.tif")) + list(tile_dir.glob("*.tiff")):
        stale.unlink()

    with zipfile.ZipFile(archive_path) as archive:
        infos = [
            info
            for info in archive.infolist()
            if not info.is_dir()
            and Path(info.filename).suffix.lower() in {".tif", ".tiff"}
        ]
        names = [Path(info.filename).name for info in infos]
        if len(infos) != EXPECTED_TILE_COUNT:
            raise RuntimeError(
                f"expected {EXPECTED_TILE_COUNT} GeoTIFF tiles, found {len(infos)}"
            )
        if len(set(names)) != len(names):
            raise RuntimeError("source archive contains duplicate GeoTIFF basenames")
        if EXPECTED_CENTRAL_TILE not in names:
            raise RuntimeError(
                f"source archive does not contain central tile {EXPECTED_CENTRAL_TILE}"
            )

        records: list[dict[str, object]] = []
        for index, info in enumerate(
            sorted(infos, key=lambda item: Path(item.filename).name),
            start=1,
        ):
            name = Path(info.filename).name
            destination = tile_dir / name
            print(f"[extract {index}/{len(infos)}] {name}")
            with archive.open(info, "r") as source:
                byte_count, digest = copy_and_hash(source, destination)
            if byte_count != info.file_size:
                raise RuntimeError(
                    f"{name}: extracted size mismatch {byte_count} != {info.file_size}"
                )
            records.append(
                {
                    "name": name,
                    "bytes": byte_count,
                    "sha256": digest,
                    "zip_crc32": f"{info.CRC:08x}",
                }
            )
        return records


def main() -> int:
    root = output_root()
    root.mkdir(parents=True, exist_ok=True)
    archive_path = root / ARCHIVE_NAME
    tile_dir = root / "tiles"

    try:
        download_archive(archive_path)
        tiles = extract_tiles(archive_path, tile_dir)
        report = {
            "schema_version": 1,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "provider": "Ministero dell'Ambiente e della Sicurezza Energetica (MASE)",
            "program": "Piano Straordinario di Telerilevamento (PST)",
            "dataset": "LiDAR DTM grigliato 1x1",
            "license": LICENSE,
            "release_tag": RELEASE_TAG,
            "release_page": RELEASE_PAGE,
            "archive": {
                "name": ARCHIVE_NAME,
                "url": ARCHIVE_URL,
                "bytes": ARCHIVE_BYTES,
                "sha256": ARCHIVE_SHA256,
            },
            "source_contract": {
                "tile_count": EXPECTED_TILE_COUNT,
                "raster_crs": SOURCE_CRS,
                "raster_dtype": "Float32",
                "tile_pixels": [1000, 1000],
                "pixel_size_degrees": [SOURCE_PIXEL_SIZE_DEG, SOURCE_PIXEL_SIZE_DEG],
                "nodata": NODATA,
                "selected_aoi_wgs84": [
                    11.9791322014,
                    46.4496045260,
                    12.1305375358,
                    46.5198136019,
                ],
                "tile_union_wgs84": [11.97, 46.44, 12.14, 46.52],
                "central_tile": EXPECTED_CENTRAL_TILE,
            },
            "tiles": tiles,
            "yacs_policy": {
                "presentation_only": True,
                "authoritative_route_geometry": False,
                "authoritative_physics": False,
                "immutable_source_checkpoint": True,
                "live_mase_dependency": False,
            },
        }
        report_path = root / "mase-pst-download-report.json"
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"[ok] MASE PST LiDAR DTM 1x1: {len(tiles)} GeoTIFF tiles, "
            f"archive={ARCHIVE_BYTES} bytes, report={report_path}"
        )
        return 0
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
