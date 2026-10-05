#!/usr/bin/env python3
"""Verify and restore the immutable #382 texture-prep checkpoint archive.

The texture-prep backup manifest describes one archive directly. It is
intentionally separate from the workspace-data manifest format consumed by
restore_workspace_data.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def digest_stream(stream) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
        hasher.update(block)
        size += len(block)
    return hasher.hexdigest(), size


def digest_file(path: Path) -> tuple[str, int]:
    with path.open("rb") as stream:
        return digest_stream(stream)


def safe_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in value
        or ":" in value
    ):
        raise ValueError("Unsafe checkpoint member path: " + value)
    return path


def safe_destination(root: Path, value: str) -> Path:
    relative = safe_relative_path(value)
    target = root.joinpath(*relative.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Checkpoint member escapes destination: " + value)
    return target


def load_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported texture checkpoint manifest schema")

    archive = manifest.get("archive")
    if not isinstance(archive, dict):
        raise ValueError("Texture checkpoint manifest requires archive metadata")
    if (
        not isinstance(archive.get("name"), str)
        or type(archive.get("size")) is not int
        or archive["size"] < 0
        or not isinstance(archive.get("sha256"), str)
        or not SHA256.fullmatch(archive["sha256"])
    ):
        raise ValueError("Invalid texture checkpoint archive identity")

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("Texture checkpoint manifest requires files")

    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("Invalid texture checkpoint file record")
        member = item.get("path")
        if not isinstance(member, str):
            raise ValueError("Texture checkpoint file path must be a string")
        safe_relative_path(member)
        if member in seen:
            raise ValueError("Duplicate texture checkpoint file: " + member)
        seen.add(member)
        if type(item.get("size")) is not int or item["size"] < 0:
            raise ValueError("Invalid texture checkpoint file size: " + member)
        if not isinstance(item.get("sha256"), str) or not SHA256.fullmatch(
            item["sha256"]
        ):
            raise ValueError("Invalid texture checkpoint file hash: " + member)

    return manifest


def verify_archive_identity(manifest: dict, archive_path: Path) -> None:
    archive = manifest["archive"]
    if archive_path.name != archive["name"]:
        raise ValueError(
            f"Checkpoint archive name mismatch: {archive_path.name} != {archive['name']}"
        )
    sha256, size = digest_file(archive_path)
    if size != archive["size"] or sha256 != archive["sha256"]:
        raise ValueError("Texture checkpoint archive identity mismatch")


def archive_inventory(
    manifest: dict, archive: zipfile.ZipFile
) -> dict[str, zipfile.ZipInfo]:
    infos: dict[str, zipfile.ZipInfo] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = info.filename
        safe_relative_path(name)
        if name in infos:
            raise ValueError("Duplicate checkpoint archive member: " + name)
        mode = (info.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK:
            raise ValueError("Symlink checkpoint archive member is forbidden: " + name)
        infos[name] = info

    expected = {item["path"] for item in manifest["files"]}
    actual = set(infos)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(
            f"Checkpoint archive inventory mismatch: missing={missing} extra={extra}"
        )
    return infos


def verify_or_restore(
    manifest_path: Path,
    archive_path: Path,
    destination: Path,
    apply: bool = False,
) -> dict:
    manifest = load_manifest(manifest_path)
    verify_archive_identity(manifest, archive_path)

    destination = destination.resolve()
    if destination.exists():
        if not destination.is_dir():
            raise ValueError("Checkpoint destination exists and is not a directory")
        if any(destination.iterdir()):
            raise ValueError("Checkpoint destination must be empty")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path) as archive:
        infos = archive_inventory(manifest, archive)
        if not apply:
            for item in manifest["files"]:
                with archive.open(infos[item["path"]]) as stream:
                    sha256, size = digest_stream(stream)
                if size != item["size"] or sha256 != item["sha256"]:
                    raise ValueError(
                        "Checkpoint member identity mismatch: " + item["path"]
                    )
            return {
                "status": "PASS",
                "archive": manifest["archive"],
                "verified_files": len(manifest["files"]),
                "restored_files": 0,
            }

        with tempfile.TemporaryDirectory(
            prefix=".yacs-texture-restore-", dir=destination.parent
        ) as temp:
            staged_root = Path(temp) / "payload"
            staged_root.mkdir()
            for item in manifest["files"]:
                info = infos[item["path"]]
                target = safe_destination(staged_root, item["path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                hasher = hashlib.sha256()
                size = 0
                with archive.open(info) as source, target.open("xb") as output:
                    for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
                        output.write(block)
                        hasher.update(block)
                        size += len(block)
                if size != item["size"] or hasher.hexdigest() != item["sha256"]:
                    raise ValueError(
                        "Checkpoint member identity mismatch: " + item["path"]
                    )

            if destination.exists():
                destination.rmdir()
            staged_root.rename(destination)

    return {
        "status": "PASS",
        "archive": manifest["archive"],
        "verified_files": len(manifest["files"]),
        "restored_files": len(manifest["files"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    report = verify_or_restore(
        args.manifest.resolve(strict=True),
        args.archive.resolve(strict=True),
        args.destination,
        apply=args.apply,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
