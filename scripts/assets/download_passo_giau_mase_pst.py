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
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

RELEASE_TAG = "data-mase-pst-passo-giau-dtm-2026-09-28"
ARCHIVE_NAME = "MASE_PST_8309f0171e3340c6aba45798c4812d54_1372858_DTM.zip"
ARCHIVE_URL = (
    "https://github.com/karnalooch/YetAnotherCyclingSim/releases/download/"
    f"{RELEASE_TAG}/{ARCHIVE_NAME}"
)
RELEASE_PAGE = (
    "https://github.com/karnalooch/YetAnotherCyclingSim/releases/tag/"
    f"{RELEASE_TAG}"
)
ARCHIVE_BYTES = 853_162_557
ARCHIVE_SHA256 = "4215d1d37fb8540c44442aedd164b6cda3f1845f3552413a975a6b7b1461e93c"
EXPECTED_TILE_COUNT = 204
SOURCE_PACKAGE_ID = 1372858
EXPECTED_TILE_SUFFIX = "_DTM.tiff"
EXPECTED_DSM_TILE_COUNT = 0
SOURCE_CRS = "EPSG:4326"
SOURCE_PIXEL_SIZES_DEG = (0.00001, 0.000005)
NODATA = -9999.0
LICENSE = "CC BY 4.0"
CHUNK_BYTES = 1024 * 1024
DOWNLOAD_ATTEMPTS = 6
DOWNLOAD_TIMEOUT_SECONDS = 300
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
    if temp.is_file() and temp.stat().st_size > ARCHIVE_BYTES:
        temp.unlink()

    last_error: Exception | None = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        written = temp.stat().st_size if temp.is_file() else 0

        if written == ARCHIVE_BYTES:
            actual_sha = sha256_file(temp)
            if actual_sha == ARCHIVE_SHA256:
                temp.replace(path)
                validate_archive(path)
                print(
                    f"[download] completed verified archive after {attempt - 1} retries"
                )
                return
            print(
                "[download] complete partial file has wrong SHA-256; "
                "discarding and restarting"
            )
            temp.unlink(missing_ok=True)
            written = 0

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/zip,*/*",
        }
        if written > 0:
            headers["Range"] = f"bytes={written}-"
            print(
                f"[download {attempt}/{DOWNLOAD_ATTEMPTS}] "
                f"resuming at byte {written}/{ARCHIVE_BYTES}"
            )
        else:
            print(
                f"[download {attempt}/{DOWNLOAD_ATTEMPTS}] "
                f"starting {ARCHIVE_NAME}"
            )

        request = urllib.request.Request(ARCHIVE_URL, headers=headers)

        try:
            with urllib.request.urlopen(
                request,
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
            ) as response:
                status = int(getattr(response, "status", response.getcode()))

                if written > 0 and status == 206:
                    content_range = str(response.headers.get("Content-Range", ""))
                    expected_prefix = f"bytes {written}-"
                    if not content_range.startswith(expected_prefix):
                        temp.unlink(missing_ok=True)
                        raise RuntimeError(
                            "resume response has unexpected Content-Range: "
                            f"{content_range!r}; expected prefix {expected_prefix!r}"
                        )
                    mode = "ab"
                    current = written
                elif status == 200:
                    if written > 0:
                        print(
                            "[download] server ignored Range; restarting from byte 0"
                        )
                    mode = "wb"
                    current = 0
                else:
                    raise RuntimeError(
                        f"unexpected HTTP status {status} while downloading archive"
                    )

                with temp.open(mode) as out:
                    while True:
                        chunk = response.read(CHUNK_BYTES)
                        if not chunk:
                            break
                        out.write(chunk)
                        current += len(chunk)
                        if current > ARCHIVE_BYTES:
                            temp.unlink(missing_ok=True)
                            raise RuntimeError(
                                f"download exceeded expected {ARCHIVE_BYTES} bytes"
                            )

            if current == ARCHIVE_BYTES:
                actual_sha = sha256_file(temp)
                if actual_sha != ARCHIVE_SHA256:
                    temp.unlink(missing_ok=True)
                    raise RuntimeError(
                        "download SHA-256 mismatch: "
                        f"expected {ARCHIVE_SHA256}, got {actual_sha}"
                    )
                temp.replace(path)
                validate_archive(path)
                print(
                    f"[download] verified {ARCHIVE_BYTES} bytes / {ARCHIVE_SHA256}"
                )
                return

            if current < ARCHIVE_BYTES:
                last_error = RuntimeError(
                    "download ended before expected byte size: "
                    f"{current}/{ARCHIVE_BYTES}"
                )
                print(
                    f"[download] partial archive retained: "
                    f"{current}/{ARCHIVE_BYTES} bytes"
                )
            else:
                raise RuntimeError(
                    f"unexpected download size {current}; expected {ARCHIVE_BYTES}"
                )

        except (
            TimeoutError,
            urllib.error.URLError,
            OSError,
            RuntimeError,
        ) as exc:
            last_error = exc
            if isinstance(exc, RuntimeError) and (
                "SHA-256 mismatch" in str(exc)
                or "exceeded expected" in str(exc)
            ):
                temp.unlink(missing_ok=True)

            if attempt >= DOWNLOAD_ATTEMPTS:
                break

            retained = temp.stat().st_size if temp.is_file() else 0
            delay = min(2 ** (attempt - 1), 10)
            print(
                f"[download] attempt {attempt} failed: {exc}; "
                f"retained={retained} bytes; retrying in {delay}s",
                file=sys.stderr,
            )
            time.sleep(delay)

    retained = temp.stat().st_size if temp.is_file() else 0
    raise RuntimeError(
        "pinned MASE archive download failed after "
        f"{DOWNLOAD_ATTEMPTS} attempts; retained={retained}/{ARCHIVE_BYTES} bytes; "
        f"last_error={last_error}"
    )


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
        non_dtm = [name for name in names if not name.endswith(EXPECTED_TILE_SUFFIX)]
        if non_dtm:
            raise RuntimeError(
                "source archive contains non-DTM GeoTIFFs: "
                + ", ".join(sorted(non_dtm)[:10])
            )
        dsm_names = [name for name in names if "_DSM" in name.upper()]
        if len(dsm_names) != EXPECTED_DSM_TILE_COUNT:
            raise RuntimeError(
                f"expected zero DSM tiles, found {len(dsm_names)}"
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
            "source_package_id": SOURCE_PACKAGE_ID,
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
                "tile_dimensions": "source-defined; validated during terrain preparation",
                "pixel_sizes_degrees": [[size, size] for size in SOURCE_PIXEL_SIZES_DEG],
                "nodata": NODATA,
                "selected_aoi_wgs84": [
                    11.9791322014,
                    46.4496045260,
                    12.1305375358,
                    46.5198136019,
                ],
                "tile_union_wgs84": [11.97, 46.44, 12.14, 46.52],
                "tile_suffix": EXPECTED_TILE_SUFFIX,
                "dsm_tile_count": EXPECTED_DSM_TILE_COUNT,
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
