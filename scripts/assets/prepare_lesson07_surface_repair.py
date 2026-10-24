"""Prepare the fixed CC0 rock candidate and retained Grass data for Lesson07.

This is an offline adapter for the existing five-slice Pegasus material. It
does not import into Unreal or write world geometry/masks. Original scans are
retained. The dark rock is an appearance proxy; its geology is not verified.

Sources and licence: https://polyhaven.com/a/dark_rock_02 and
https://polyhaven.com/license . Pillow PNG mode/16-bit behavior:
https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#png
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import urllib.request
import zlib

import numpy as np
from PIL import Image


SIZE = (2048, 2048)
ASSET = "dark_rock_02"
PACKAGE_ID = "lesson07-surface-repair-20261021"
SOURCE_MAPS = {
    "diff": ("bf440eca64d945962c417a524b07fbc3aaa1591bd76d2d3fb60b0df8a05f1c54", 24251872),
    "nor_dx": ("8f446aad3271078e9cdf94c9744363ae26339c392f3727619de3ef104a9976de", 25556874),
    "ao": ("fbb0c970a95edec729c725ce5289169a646498bf3ca0befab78260fb84d091ee", 4519546),
    "rough": ("0ba3d020f4cbf5a4cd452612476f6ee42ddf22b97d1f6f5221818221e057766e", 7095869),
    "disp": ("f1f452f2bbc13b2c094f52262b39e0e4e7fd7114bb4eaea33f805f1cd972ae4f", 5456217),
}
GRASS_MAPS = {
    "Grass_Normal": {"file": "slice_0_grass_normal.png", "sha256": "6cfe99fee469d538d07f6770bcd10714bac5f59db904cb665f26f3fddcdfb239", "size_bytes": 10689967},
    "Grass_Masks": {"file": "slice_0_grass_masks.png", "sha256": "bc9131bb40a06e00c14544785b873bce6430797c59eb3c7369b34fbaff318d1c", "size_bytes": 3756633},
}
CLIFF_NAMES = {
    "Cliffs_Colour": "slice_3_cliffs_colour.png",
    "Cliffs_Normal": "slice_3_cliffs_normal.png",
    "Cliffs_Masks": "slice_3_cliffs_masks.png",
}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def plain_path(path: Path) -> None:
    for item in (path, *path.parents):
        if item.is_symlink() or (item.exists() and getattr(item, "is_junction", lambda: False)()):
            raise ValueError("Redirected source/output path")


def verified_file(path: Path, digest: str, size: int) -> None:
    plain_path(path)
    if not path.is_file() or path.stat().st_size != size or sha256(path) != digest:
        raise ValueError(f"Source identity mismatch: {path.name}")


def source_records() -> dict:
    return {
        key: {
            "file": f"{ASSET}_{key}_2k.png",
            "url": f"https://dl.polyhaven.org/file/ph-assets/Textures/png/2k/{ASSET}/{ASSET}_{key}_2k.png",
            "sha256": digest, "size_bytes": size,
        }
        for key, (digest, size) in SOURCE_MAPS.items()
    }


def acquire(cache: Path, *, download: bool) -> None:
    plain_path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    for entry in source_records().values():
        path = cache / entry["file"]
        if not path.exists():
            if not download:
                raise FileNotFoundError(path)
            temporary = path.with_suffix(".png.partial")
            plain_path(temporary)
            # Fixed official URLs only. A 403/redirect outside the provider is
            # an error; no alternate identity, mirror or automatic retry.
            request = urllib.request.Request(entry["url"], headers={"User-Agent": "YACS-Lesson07/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status != 200 or not response.geturl().startswith("https://dl.polyhaven.org/"):
                    raise ValueError("Unexpected source response")
                received = 0
                with temporary.open("xb") as stream:
                    while block := response.read(1024 * 1024):
                        received += len(block)
                        if received > entry["size_bytes"]:
                            raise ValueError("Source exceeds pinned size")
                        stream.write(block)
            verified_file(temporary, entry["sha256"], entry["size_bytes"])
            temporary.rename(path)
        verified_file(path, entry["sha256"], entry["size_bytes"])


def png_header(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(26)
    if (header[:8] != b"\x89PNG\r\n\x1a\n" or len(header) != 26
            or struct.unpack(">II", header[16:24]) != SIZE):
        raise ValueError("Expected 2048-square source PNG")
    return header[24], header[25]


def scalar_u8(path: Path) -> np.ndarray:
    """Quantize normalized PNG16 data, never Pillow's clipping L conversion."""
    bits, colour_type = png_header(path)
    if bits != 16 or colour_type != 0:
        raise ValueError("Expected original grayscale16 scalar map")
    with Image.open(path) as image:
        values = np.asarray(image)
        if values.shape != (SIZE[1], SIZE[0]) or values.dtype != np.uint16:
            raise ValueError("Scalar source did not decode as uint16")
        return np.rint(values.astype(np.float64) / 257.0).astype(np.uint8)


def rgba_u8(path: Path) -> np.ndarray:
    """Pillow reads the high eight bits; no gamma/color transform on data."""
    bits, colour_type = png_header(path)
    if bits != 16 or colour_type != 6:
        raise ValueError("Expected original RGBA16 map")
    with Image.open(path) as image:
        if image.mode != "RGBA":
            raise ValueError("RGBA source decode differs")
        values = np.asarray(image).copy()
    if values.dtype != np.uint8 or not np.all(values[:, :, 3] == 255):
        raise ValueError("Expected opaque RGBA image")
    return values


def neutral_albedo(rgba: np.ndarray) -> np.ndarray:
    """Preserve linear Rec.709 luminance, remove brown chroma only.

    Achromatic output also avoids adding a new hue shift when the existing
    colour-array grade (shared with accepted Grass2) is preserved by import.
    """
    srgb = rgba[:, :, :3].astype(np.float64) / 255.0
    linear = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    luminance = np.sum(linear * np.array([0.2126, 0.7152, 0.0722]), axis=2)
    neutral = np.where(luminance <= 0.0031308, luminance * 12.92,
                       1.055 * luminance ** (1.0 / 2.4) - 0.055)
    grey = np.rint(np.clip(neutral, 0.0, 1.0) * 255.0).astype(np.uint8)
    return np.stack([grey, grey, grey, rgba[:, :, 3]], axis=2)


def save_png_exact(path: Path, pixels: np.ndarray) -> None:
    """Serialize RGBA8 identically on Linux/Windows, without a PNG compressor.

    A local Pillow regeneration did not reproduce the retained Grass bytes.
    Fixed filter-zero rows and RFC1951 stored blocks remove compression-library
    variation from this new package; they do not change pixels. The ~16 MiB
    staging files are not committed to Git or used as runtime texture formats.
    PNG: https://www.w3.org/TR/png-3/ ; RFC1950/RFC1951 stored-block format.
    """
    if pixels.shape != (SIZE[1], SIZE[0], 4) or pixels.dtype != np.uint8:
        raise ValueError("Exact PNG requires the fixed RGBA8 raster")
    rows = b"".join(b"\0" + row.tobytes() for row in pixels)
    blocks = [b"\x78\x01"]
    for offset in range(0, len(rows), 65535):
        block = rows[offset:offset + 65535]
        final = offset + len(block) == len(rows)
        blocks.append(bytes([int(final)]) + struct.pack("<HH", len(block), len(block) ^ 0xFFFF) + block)
    blocks.append(struct.pack(">I", zlib.adler32(rows)))

    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

    header = struct.pack(">IIBBBBB", SIZE[0], SIZE[1], 8, 6, 0, 0, 0)
    with path.open("xb") as stream:
        stream.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                     + chunk(b"IDAT", b"".join(blocks)) + chunk(b"IEND", b""))


def cliff_images(cache: Path) -> dict:
    colour = neutral_albedo(rgba_u8(cache / f"{ASSET}_diff_2k.png"))
    normal = rgba_u8(cache / f"{ASSET}_nor_dx_2k.png")
    ao, rough, height = [scalar_u8(cache / f"{ASSET}_{name}_2k.png") for name in ("ao", "rough", "disp")]
    return {"Cliffs_Colour": colour, "Cliffs_Normal": normal,
            "Cliffs_Masks": np.stack([ao, rough, height, ao], axis=2)}


def make_manifest(cliff_records: dict) -> dict:
    return {
        "schema_version": 1, "package_id": PACKAGE_ID, "size": list(SIZE),
        "normal_convention": "DirectX",
        "masks_channels": {"R": "AO", "G": "Roughness", "B": "Height"},
        "classification_changed": False, "terrain_changed": False,
        "maps": {**GRASS_MAPS, **cliff_records},
        "provenance": {
            "asset_id": ASSET, "title": "Dark Rock 02", "author": "Amal Kumar",
            "provider": "Poly Haven", "source_url": "https://polyhaven.com/a/dark_rock_02",
            "license": "CC0-1.0", "license_url": "https://polyhaven.com/license",
            "license_checked": "2026-10-21", "source_files": source_records(),
            "physical_dimensions_m": [2.0009167194366455, 2.000917911529541],
            "geology": "unverified; dark-grey rock appearance proxy, not authenticated limestone",
            "albedo_transform": "sRGB high8bit -> linear Rec709 luminance -> achromatic sRGB; luminance preserved",
            "normal_transform": "RGBA16 high8bit; no gamma transform; no green inversion",
            "scalar_transform": "PNG16 raw /257, round-to-nearest ties-to-even; no gamma transform",
            "package_png_encoding": "RGBA8 filter0 RFC1951 stored blocks65535; deterministic bytes",
            "packed_masks_alpha": "AO", "runtime_displacement_enabled": False,
            "grass_source_run": "39519585751", "grass_colour_unchanged": True,
            "grass_normal_family": "aerial_grass_rock", "grass_roughness_source_channel": "G",
            "class_order": ["Grass", "Grass2", "Sand", "Cliffs", "Scree"],
            "unchanged_slots": [1, 2, 4], "native_ue_verified": False,
        },
    }


def prepare(output: Path, cache: Path, grass: Path, *, download: bool = False) -> dict:
    for path in (output, cache, grass):
        plain_path(path)
    if output.exists():
        raise FileExistsError("Package output must be new")
    if not output.parent.is_dir():
        raise ValueError("Output parent must exist")
    # Check retained Grass before downloads or output writes.
    for entry in GRASS_MAPS.values():
        verified_file(grass / entry["file"], entry["sha256"], entry["size_bytes"])
        if png_header(grass / entry["file"]) != (8, 6):
            raise ValueError("Retained Grass must be RGBA8")
    acquire(cache, download=download)
    images = cliff_images(cache)
    output.mkdir(exist_ok=False)
    for key, pixels in images.items():
        save_png_exact(output / CLIFF_NAMES[key], pixels)
    for entry in GRASS_MAPS.values():
        target = output / entry["file"]
        shutil.copyfile(grass / entry["file"], target)
        verified_file(target, entry["sha256"], entry["size_bytes"])
    cliff_records = {
        key: {"file": filename, "sha256": sha256(output / filename),
              "size_bytes": (output / filename).stat().st_size}
        for key, filename in CLIFF_NAMES.items()
    }
    result = make_manifest(cliff_records)
    with (output / "surface-repair-package.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-cache", type=Path, required=True)
    parser.add_argument("--grass-sources", type=Path, required=True)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    result = prepare(args.output, args.source_cache, args.grass_sources, download=args.download)
    print(json.dumps({"status": "PACKAGE_PREPARED_IMPORT_NOT_RUN", "maps": result["maps"],
                      "manifest_sha256": sha256(args.output / "surface-repair-package.json")}, indent=2))


if __name__ == "__main__":
    main()
