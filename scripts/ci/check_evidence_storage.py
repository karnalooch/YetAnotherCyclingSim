"""Validate byte-preserving receipt archives and bounded raw JSON exceptions."""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 1024 * 1024
MAX_RECEIPT_BYTES = 10 * LIMIT
LARGE = "docs/assets/pcg365-large-rocks-20261012"
NATURAL = "docs/assets/pcg365-natural20-20261012"
ARCHIVED_BLOBS = {
    f"{LARGE}/large-yaw-detail01-rock-qualify-receipt.json": "d63c86f1f35d6024eb215df76b5af0b77df24eb6",
    f"{LARGE}/large-shadow-detail03-rock-qualify-receipt.json": "c3fad8425996e4b0c4ea986b1a25858371bbd496",
    f"{LARGE}/large-dynamic-detail01-rock-qualify-receipt.json": "256212eed7fa281fb0c1f62ad8962afe10b4f7d2",
    f"{LARGE}/shadow-first-rock-qualify-receipt.json": "54d4b449d330a0f882e7555fc6d17ea35b6dd06d",
    f"{LARGE}/large-yaw-baseline01-rock-qualify-receipt.json": "c79e34a7de9f81b25145f1bb16f4ef8e337f0f9a",
    f"{LARGE}/large-shadow-baseline02-rock-qualify-receipt.json": "9fbdd66616d8f107eede9d7ee80e1d2b749def6d",
    f"{LARGE}/half-identity-rock-qualify-receipt.json": "29800be0262a8d60c309324cc0d6d3edd06cec61",
    f"{LARGE}/full-size-rock-qualify-receipt.json": "aa43cee8baf46584dea58cb0ef3f65e30698d9f7",
    f"{LARGE}/large-dynamic-detail01-rock-render-receipt.json": "f9f51a261a77558addc916db912b5a0c9c677ed1",
    f"{LARGE}/large-shadow-baseline02-rock-render-receipt.json": "a5a7021297044ba9f29a0fa195de120ee6b80d76",
    f"{LARGE}/large-shadow-detail03-rock-render-receipt.json": "cb2d0e74940c634d19cf20d0c390b3856ceaff31",
    f"{LARGE}/large-yaw-baseline01-rock-render-receipt.json": "954f59a59a8c4c24b3e6f91a57f64bbb68e16854",
    f"{LARGE}/large-yaw-detail01-rock-render-receipt.json": "1d3b54bb34e20843359649d7629e7dff2f2efc23",
    f"{NATURAL}/producer-receipt.json": "d655905fff816205727b14e3c852d74f6644c16e",
}
# Source/replay manifests and observations are not disposable run receipts.
# Exact blob pins forbid silent growth or a wildcard exemption.
RETAINED_BLOBS = {
    "docs/experiments/sa-calobra-road-materials-20261011/b9fd/road-asphalt-saved-manifest.json": "784ee9731fbfbe81b991ae72e33a76b196502257",
    "docs/experiments/sa-calobra-tpp-survey-20261008/manifest.json": "e6e514d80eaba87eace3498648a1ebfefc76c4f6",
    "docs/experiments/sa-calobra-roadside-visibility-prestudy-20261008/observations.json": "ff01ac7b33225b91ce7ece82f438544be6d62983",
    "docs/assets/pcg365-local-rock-pack-20261012/source-variant-pack.json": "885595bf794915153667c9496fe4560016593a4e",
}


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_entry(
    directory: Path, entry: dict, expected_blob: str | None = None
) -> bytes:
    """Verify stored bytes AND decompressed original; never trust JSON equality."""
    original, compressed = entry["original"], entry["gzip"]
    for name in (original, compressed):
        require(
            isinstance(name, str)
            and name not in {"", ".", ".."}
            and "/" not in name
            and "\\" not in name
            and ":" not in name,
            f"unsafe archive basename: {name!r}",
        )
    require(original.endswith(".json"), "original must be JSON")
    require(compressed == original + ".gz", "archive name mismatch")
    path = directory / compressed
    require(not path.is_symlink(), f"archive must not be a symlink: {path}")
    size = entry["original_bytes"]
    require(
        type(size) is int and 0 <= size <= MAX_RECEIPT_BYTES, "invalid original size"
    )
    require(path.stat().st_size <= MAX_RECEIPT_BYTES, "oversized compressed receipt")
    packed = path.read_bytes()
    require(len(packed) == entry["gzip_bytes"], f"compressed size mismatch: {path}")
    require(
        hashlib.sha256(packed).hexdigest() == entry["gzip_sha256"],
        f"compressed hash mismatch: {path}",
    )
    with gzip.open(path, "rb") as stream:
        data = stream.read(size + 1)
    require(len(data) == size, f"original size mismatch: {path}")
    require(
        hashlib.sha256(data).hexdigest() == entry["original_sha256"],
        f"original hash mismatch: {path}",
    )
    if expected_blob is not None:
        require(git_blob(data) == expected_blob, f"original Git blob mismatch: {path}")
    json.loads(data)
    return data


def verify_raw(path: str, data: bytes) -> None:
    if len(data) > LIMIT:
        require(
            path in RETAINED_BLOBS and git_blob(data) == RETAINED_BLOBS[path],
            f"raw evidence JSON exceeds 1 MiB without an exact reviewed exception: {path}",
        )


def main() -> int:
    tracked = (
        subprocess.check_output(["git", "ls-files", "-z", "--", "docs"], cwd=ROOT)
        .decode()
        .split("\0")
    )
    oversized = 0
    for relative in tracked:
        if not relative.endswith(".json"):
            continue
        path = ROOT / relative
        require(path.is_file(), f"tracked JSON missing from checkout: {relative}")
        if path.stat().st_size > LIMIT:
            verify_raw(relative, path.read_bytes())
            oversized += 1
    found = set()
    raw_bytes = compressed_bytes = 0
    for directory in (LARGE, NATURAL):
        entries = json.loads(
            (ROOT / directory / "compressed-evidence.json").read_bytes()
        )
        require(isinstance(entries, list), "archive index must be a list")
        seen = set()
        for entry in entries:
            require(entry["original"] not in seen, "duplicate archive index entry")
            seen.add(entry["original"])
            relative = f"{directory}/{entry['original']}"
            verify_entry(ROOT / directory, entry, ARCHIVED_BLOBS.get(relative))
            if relative in ARCHIVED_BLOBS:
                require(
                    not (ROOT / relative).exists(),
                    f"raw archived receipt returned: {relative}",
                )
                found.add(relative)
                raw_bytes += entry["original_bytes"]
                compressed_bytes += entry["gzip_bytes"]
    require(
        found == set(ARCHIVED_BLOBS),
        f"missing archive entries: {set(ARCHIVED_BLOBS) - found}",
    )
    print(
        f"evidence-storage: PASS; {len(found)} migrated receipts; {raw_bytes} -> {compressed_bytes} bytes; {oversized} exact raw exceptions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
